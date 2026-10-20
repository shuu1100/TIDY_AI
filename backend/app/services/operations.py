"""Safe reversible file operations service for TidyAI.

Enforces:
- Zero Unconfirmed Mutations: Requires explicit confirmation to execute changes.
- Dry-Run Non-Invariance: Preview simulation NEVER moves, renames, deletes, or creates directories.
- Zero Silent Overwrites: Collisions at target paths fail closed.
- Pre-Flight Atomic Revalidation: Immediate recheck before any move.
- Reversible Undo: Restores original paths safely into SQLite audit ledger.
"""

import os
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional, Set

from backend.app.database import (
    get_batch_by_id,
    get_batches,
    get_items_by_batch_id,
    record_batch,
    record_batch_items,
    update_batch_undo_status,
    update_item_undo_status,
)
from backend.app.schemas import (
    ApplyOperationsResponse,
    DryRunItem,
    DryRunResponse,
    DryRunSummary,
    ExecutedItem,
    OperationBatchHistoryItem,
    OperationHistoryResponse,
    OperationPlanItem,
    UndoItem,
    UndoResponse,
)
from backend.app.services.roots_registry import ApprovedRoot
from backend.app.services.security import SecurityBoundaryError, resolve_and_verify_containment


def simulate_dry_run(
    root: ApprovedRoot,
    operations: List[OperationPlanItem],
) -> DryRunResponse:
    """Execute a strictly read-only dry-run simulation of an operations plan.

    NEVER moves, renames, deletes files, or creates directories on disk.
    Detects disk collisions, batch target collisions, boundary escapes, and missing source files.
    """
    root_path = Path(root.canonical_path).resolve()
    batch_id = f"sim-{uuid.uuid4().hex[:12]}"
    dry_run_items: List[DryRunItem] = []
    
    # Track destinations within the batch to detect internal duplicate collisions
    batch_targets: Set[str] = set()

    safe_count = 0
    blocked_count = 0

    for item in operations:
        norm_source = item.source_rel_path.strip().replace("\\", "/")
        norm_target = item.target_rel_path.strip().replace("\\", "/")

        # Check if user opted out / unapproved
        if not item.approved:
            blocked_count += 1
            dry_run_items.append(
                DryRunItem(
                    source_rel_path=norm_source,
                    target_rel_path=norm_target,
                    operation_type=item.operation_type.value if hasattr(item.operation_type, "value") else str(item.operation_type),
                    approved=False,
                    is_safe=False,
                    validation_error="Operation unapproved by user.",
                    will_create_subfolder=None,
                    collision_detected=False,
                    source_exists=True,
                    target_exists=False,
                )
            )
            continue

        # Revalidation of source path
        source_exists = False
        target_exists = False
        collision_detected = False
        validation_error: Optional[str] = None
        will_create_subfolder: Optional[str] = None

        if not norm_source or norm_source.endswith("/"):
            validation_error = f"Source path must specify a file, not a directory or empty string: '{norm_source}'"
        elif not norm_target or norm_target.endswith("/"):
            validation_error = f"Target path must specify a file destination: '{norm_target}'"

        try:
            source_canonical = resolve_and_verify_containment(root_path, norm_source)
            if not source_canonical.exists():
                validation_error = f"Source file does not exist: '{norm_source}'"
            elif not source_canonical.is_file():
                validation_error = f"Source path is not a regular file: '{norm_source}'"
            else:
                source_exists = True
        except SecurityBoundaryError as exc:
            validation_error = f"Security boundary violation for source: {str(exc)}"

        # Revalidation of target path
        if not validation_error:
            try:
                target_canonical = resolve_and_verify_containment(root_path, norm_target)
                
                # Check for same path no-op
                if source_canonical == target_canonical:
                    validation_error = "Source and target paths are identical (no-op)."
                else:
                    # Check disk collision (fail closed!)
                    if target_canonical.exists():
                        target_exists = True
                        collision_detected = True
                        validation_error = f"Target path already exists on disk: '{norm_target}' (silent overwrites forbidden)"
                    
                    # Check batch internal collision
                    lower_target = norm_target.lower()
                    if lower_target in batch_targets:
                        collision_detected = True
                        validation_error = f"Duplicate target collision within batch: '{norm_target}'"
                    else:
                        batch_targets.add(lower_target)

                    # Check if target subfolder creation will be required on apply
                    target_parent = target_canonical.parent
                    if not target_parent.exists():
                        try:
                            rel_parent = target_parent.relative_to(root_path).as_posix()
                            will_create_subfolder = rel_parent if rel_parent != "." else None
                        except ValueError:
                            pass
            except SecurityBoundaryError as exc:
                validation_error = f"Security boundary violation for target: {str(exc)}"

        is_safe = (validation_error is None) and source_exists and (not target_exists) and (not collision_detected)

        if is_safe:
            safe_count += 1
        else:
            blocked_count += 1

        dry_run_items.append(
            DryRunItem(
                source_rel_path=norm_source,
                target_rel_path=norm_target,
                operation_type=item.operation_type.value if hasattr(item.operation_type, "value") else str(item.operation_type),
                approved=True,
                is_safe=is_safe,
                validation_error=validation_error,
                will_create_subfolder=will_create_subfolder,
                collision_detected=collision_detected,
                source_exists=source_exists,
                target_exists=target_exists,
            )
        )

    summary = DryRunSummary(
        root_id=root.id,
        root_path=str(root_path),
        total_operations=len(operations),
        safe_operations=safe_count,
        blocked_operations=blocked_count,
        is_executable=(safe_count > 0 and blocked_count == 0),
    )

    return DryRunResponse(
        batch_id=batch_id,
        summary=summary,
        items=dry_run_items,
    )


def apply_operation_plan(
    root: ApprovedRoot,
    operations: List[OperationPlanItem],
    confirmed: bool,
) -> ApplyOperationsResponse:
    """Execute a confirmed operation plan on disk within the approved root sandbox.

    Requires confirmed=True.
    Revalidates every item atomically immediately prior to moving.
    Fails closed on missing sources or occupied targets.
    Records every executed mutation into the SQLite audit ledger.
    """
    if not confirmed:
        raise ValueError("Explicit user confirmation (confirmed=True) is required to execute filesystem operations.")

    root_path = Path(root.canonical_path).resolve()
    batch_id = f"batch-{uuid.uuid4().hex[:12]}"
    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.now(timezone.utc)

    executed_items: List[ExecutedItem] = []
    db_items: list = []

    applied_count = 0
    failed_count = 0
    skipped_count = 0

    for item in operations:
        item_id = f"item-{uuid.uuid4().hex[:12]}"
        norm_source = item.source_rel_path.strip().replace("\\", "/")
        norm_target = item.target_rel_path.strip().replace("\\", "/")
        op_type = item.operation_type.value if hasattr(item.operation_type, "value") else str(item.operation_type)

        if not item.approved:
            skipped_count += 1
            rec = ExecutedItem(
                id=item_id,
                source_rel_path=norm_source,
                target_rel_path=norm_target,
                operation_type=op_type,
                status="skipped",
                error_message="Skipped: unapproved by user.",
                executed_at=None,
                is_undone=False,
            )
            executed_items.append(rec)
            db_items.append({
                "id": item_id,
                "batch_id": batch_id,
                "source_rel_path": norm_source,
                "target_rel_path": norm_target,
                "operation_type": op_type,
                "status": "skipped",
                "error_message": "Skipped: unapproved by user.",
                "executed_at": None,
                "is_undone": False,
                "undone_at": None,
            })
            continue

        # Atomic pre-flight revalidation
        error_msg: Optional[str] = None
        if not norm_source or norm_source.endswith("/"):
            error_msg = f"Source path must specify a file, not a directory or empty string: '{norm_source}'"
        elif not norm_target or norm_target.endswith("/"):
            error_msg = f"Target path must specify a file destination: '{norm_target}'"
        else:
            try:
                source_canonical = resolve_and_verify_containment(root_path, norm_source)
                target_canonical = resolve_and_verify_containment(root_path, norm_target)

                if not source_canonical.exists():
                    error_msg = f"Source file does not exist on disk: '{norm_source}'"
                elif not source_canonical.is_file():
                    error_msg = f"Source path is not a file: '{norm_source}'"
                elif source_canonical == target_canonical:
                    error_msg = "Source and target paths are identical (no-op)."
                elif target_canonical.exists():
                    error_msg = f"Target already exists on disk: '{norm_target}' (silent overwrites forbidden)"
            except SecurityBoundaryError as exc:
                error_msg = f"Security boundary violation: {str(exc)}"

        if error_msg:
            failed_count += 1
            rec = ExecutedItem(
                id=item_id,
                source_rel_path=norm_source,
                target_rel_path=norm_target,
                operation_type=op_type,
                status="failed",
                error_message=error_msg,
                executed_at=None,
                is_undone=False,
            )
            executed_items.append(rec)
            db_items.append({
                "id": item_id,
                "batch_id": batch_id,
                "source_rel_path": norm_source,
                "target_rel_path": norm_target,
                "operation_type": op_type,
                "status": "failed",
                "error_message": error_msg,
                "executed_at": None,
                "is_undone": False,
                "undone_at": None,
            })
            continue

        # Execute the move safely
        try:
            target_parent = target_canonical.parent
            if not target_parent.exists():
                target_parent.mkdir(parents=True, exist_ok=True)

            shutil.move(str(source_canonical), str(target_canonical))
            item_time = datetime.now(timezone.utc)
            applied_count += 1

            rec = ExecutedItem(
                id=item_id,
                source_rel_path=norm_source,
                target_rel_path=norm_target,
                operation_type=op_type,
                status="applied",
                error_message=None,
                executed_at=item_time,
                is_undone=False,
            )
            executed_items.append(rec)
            db_items.append({
                "id": item_id,
                "batch_id": batch_id,
                "source_rel_path": norm_source,
                "target_rel_path": norm_target,
                "operation_type": op_type,
                "status": "applied",
                "error_message": None,
                "executed_at": item_time.isoformat(),
                "is_undone": False,
                "undone_at": None,
            })
        except Exception as exc:
            failed_count += 1
            err_str = f"Filesystem move failed: {str(exc)}"
            rec = ExecutedItem(
                id=item_id,
                source_rel_path=norm_source,
                target_rel_path=norm_target,
                operation_type=op_type,
                status="failed",
                error_message=err_str,
                executed_at=None,
                is_undone=False,
            )
            executed_items.append(rec)
            db_items.append({
                "id": item_id,
                "batch_id": batch_id,
                "source_rel_path": norm_source,
                "target_rel_path": norm_target,
                "operation_type": op_type,
                "status": "failed",
                "error_message": err_str,
                "executed_at": None,
                "is_undone": False,
                "undone_at": None,
            })

    # Determine overall batch status
    if applied_count == len(operations):
        overall_status = "completed"
    elif applied_count > 0:
        overall_status = "partial"
    else:
        overall_status = "failed"

    # Persist in SQLite audit ledger
    record_batch(
        batch_id=batch_id,
        created_at=now_iso,
        approved_root=str(root_path),
        total_items=len(operations),
        status=overall_status,
        is_dry_run=False,
        root_id=root.id,
    )
    if db_items:
        record_batch_items(db_items)

    return ApplyOperationsResponse(
        batch_id=batch_id,
        root_id=root.id,
        root_path=str(root_path),
        total_requested=len(operations),
        total_applied=applied_count,
        failed_count=failed_count,
        skipped_count=skipped_count,
        status=overall_status,
        items=executed_items,
        executed_at=now_dt,
    )


def undo_operation_batch(batch_id: str) -> UndoResponse:
    """Safely undo a previously executed operation batch.

    Restores files back to their original recorded source paths.
    Fails closed if the original location is now occupied or if the target file has moved/disappeared.
    Updates the SQLite audit ledger.
    """
    batch = get_batch_by_id(batch_id)
    if not batch:
        raise KeyError(f"Operation batch with ID '{batch_id}' was not found in audit ledger.")

    if batch.get("is_dry_run"):
        raise ValueError("Cannot undo a dry-run simulation batch.")

    if batch.get("status") == "undone":
        raise ValueError(f"Batch '{batch_id}' has already been fully undone.")

    root_path = Path(batch["approved_root"]).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise FileNotFoundError(f"Approved root '{root_path}' no longer exists on disk.")

    raw_items = get_items_by_batch_id(batch_id)
    # Process only applied items that have not yet been undone, in reverse execution order (LIFO)
    applied_items = [
        item for item in raw_items
        if item.get("status") == "applied" and not item.get("is_undone")
    ]
    applied_items.reverse()

    now_iso = datetime.now(timezone.utc).isoformat()
    now_dt = datetime.now(timezone.utc)
    undo_items: List[UndoItem] = []

    total_reverted = 0
    blocked_count = 0

    for item in applied_items:
        item_id = item["id"]
        curr_rel = item["target_rel_path"]   # File is currently here
        orig_rel = item["source_rel_path"]   # File needs to be restored to here

        try:
            curr_canonical = resolve_and_verify_containment(root_path, curr_rel)
            orig_canonical = resolve_and_verify_containment(root_path, orig_rel)

            if not curr_canonical.exists() or not curr_canonical.is_file():
                err = f"Current file not found at expected location: '{curr_rel}'"
                blocked_count += 1
                update_item_undo_status(item_id, "failed", False, err, now_iso)
                undo_items.append(UndoItem(
                    item_id=item_id,
                    source_rel_path=orig_rel,
                    target_rel_path=curr_rel,
                    status="failed",
                    error_message=err,
                ))
                continue

            if orig_canonical.exists():
                err = f"Original path is currently occupied on disk: '{orig_rel}' (refusing overwrite)"
                blocked_count += 1
                update_item_undo_status(item_id, "failed", False, err, now_iso)
                undo_items.append(UndoItem(
                    item_id=item_id,
                    source_rel_path=orig_rel,
                    target_rel_path=curr_rel,
                    status="failed",
                    error_message=err,
                ))
                continue

            # Ensure original parent directory exists
            orig_parent = orig_canonical.parent
            if not orig_parent.exists():
                orig_parent.mkdir(parents=True, exist_ok=True)

            # Move back safely
            shutil.move(str(curr_canonical), str(orig_canonical))
            total_reverted += 1

            # Safely clean up empty parent directories of curr_canonical if empty and inside root
            try:
                curr_parent = curr_canonical.parent
                while curr_parent != root_path and root_path in curr_parent.parents:
                    if not any(curr_parent.iterdir()):
                        curr_parent.rmdir()
                        curr_parent = curr_parent.parent
                    else:
                        break
            except Exception:
                pass

            update_item_undo_status(item_id, "reverted", True, None, now_iso)
            undo_items.append(UndoItem(
                item_id=item_id,
                source_rel_path=orig_rel,
                target_rel_path=curr_rel,
                status="reverted",
                error_message=None,
            ))

        except Exception as exc:
            err = f"Error reverting file: {str(exc)}"
            blocked_count += 1
            update_item_undo_status(item_id, "failed", False, err, now_iso)
            undo_items.append(UndoItem(
                item_id=item_id,
                source_rel_path=orig_rel,
                target_rel_path=curr_rel,
                status="failed",
                error_message=err,
            ))

    # Update batch status in database
    if total_reverted == len(applied_items) and total_reverted > 0:
        batch_final_status = "undone"
        undo_status = "fully_undone"
    elif total_reverted > 0:
        batch_final_status = "partially_undone"
        undo_status = "partially_undone"
    else:
        batch_final_status = "failed"
        undo_status = "failed"

    update_batch_undo_status(batch_id, batch_final_status, now_iso)

    return UndoResponse(
        batch_id=batch_id,
        total_items=len(applied_items),
        total_reverted=total_reverted,
        blocked_count=blocked_count,
        status=undo_status,
        items=undo_items,
        undone_at=now_dt,
    )


def get_operation_history(
    root_path: Optional[str] = None,
    limit: int = 50,
) -> OperationHistoryResponse:
    """Retrieve historical operation batches and their items from SQLite ledger."""
    raw_batches = get_batches(root_path=root_path or "", limit=limit)
    batch_items_list: List[OperationBatchHistoryItem] = []

    for b in raw_batches:
        b_id = b["id"]
        raw_items = get_items_by_batch_id(b_id)
        
        parsed_items: List[ExecutedItem] = []
        for it in raw_items:
            exec_time = None
            if it.get("executed_at"):
                try:
                    exec_time = datetime.fromisoformat(it["executed_at"])
                except Exception:
                    pass

            parsed_items.append(
                ExecutedItem(
                    id=it["id"],
                    source_rel_path=it["source_rel_path"],
                    target_rel_path=it["target_rel_path"],
                    operation_type=it["operation_type"],
                    status=it["status"],
                    error_message=it.get("error_message"),
                    executed_at=exec_time,
                    is_undone=bool(it.get("is_undone")),
                )
            )

        created_dt = datetime.fromisoformat(b["created_at"]) if b.get("created_at") else datetime.now(timezone.utc)
        undone_dt = None
        if b.get("undone_at"):
            try:
                undone_dt = datetime.fromisoformat(b["undone_at"])
            except Exception:
                pass

        batch_items_list.append(
            OperationBatchHistoryItem(
                batch_id=b_id,
                created_at=created_dt,
                approved_root=b["approved_root"],
                root_id=b.get("root_id"),
                total_items=b.get("total_items", 0),
                status=b["status"],
                is_dry_run=bool(b.get("is_dry_run")),
                is_undone=(b["status"] == "undone"),
                undone_at=undone_dt,
                items=parsed_items,
            )
        )

    return OperationHistoryResponse(batches=batch_items_list)
