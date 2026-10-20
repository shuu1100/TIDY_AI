"""AI Categorization and Suggestion Engine for TidyAI.

Generates reviewable category, clean filename, and destination subfolder proposals.
Strictly read-only: never modifies, renames, moves, or deletes any files.
Deterministic backend validation: all model outputs are validated and sanitized.
"""

import json
import os
import re
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

from backend.app.schemas import (
    ApprovedRoot,
    FileEntry,
    OllamaFileSuggestion,
    OllamaSuggestionBatch,
    OperationPlanItem,
    SuggestionBatchRequest,
    SuggestionBatchResponse,
    SuggestionItem,
    SuggestionSummary,
    SuggestionWarning,
)
from backend.app.services.ollama import (
    OllamaConnectionError,
    OllamaError,
    OllamaJsonParseError,
    OllamaModelNotFoundError,
    OllamaTimeoutError,
    ollama_service,
)
from backend.app.services.classifier import classify_file
from backend.app.services.scanner import scan_approved_root
from backend.app.services.security import (
    WINDOWS_RESERVED_NAMES,
    SecurityBoundaryError,
    resolve_and_verify_containment,
)

# Regex for invalid characters in Windows filenames (< > : " / \ | ? * and ASCII control characters)
INVALID_FILENAME_CHARS_REGEX = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def validate_and_sanitize_filename(
    proposed_filename: str, original_filename: str
) -> Tuple[bool, str, Optional[str]]:
    """Deterministically validate and sanitize proposed filename.

    Rules:
    - Must not be empty or solely whitespace/dots.
    - Must not contain Windows invalid characters: < > : " / \\ | ? * or control chars.
    - Must not contain directory separators (/ or \\).
    - Base stem must not be a Windows reserved device name (CON, PRN, AUX, NUL, COM1-9, LPT1-9).
    - Preserves original file extension (fail-closed if altered or omitted).

    Returns:
        (is_valid, sanitized_name, error_reason)
    """
    if not proposed_filename or not proposed_filename.strip():
        return False, original_filename, "Proposed filename cannot be empty."

    raw = proposed_filename.strip()

    # Reject path separators in filename
    if "/" in raw or "\\" in raw:
        return (
            False,
            original_filename,
            "Proposed filename cannot contain path separators ('/' or '\\').",
        )

    # Reject invalid characters
    if INVALID_FILENAME_CHARS_REGEX.search(raw):
        return (
            False,
            original_filename,
            'Proposed filename contains invalid characters (< > : " / \\ | ? *) or control codes.',
        )

    # Clean trailing spaces and dots (Windows rejects them)
    cleaned = raw.rstrip(". ")
    if not cleaned:
        return (
            False,
            original_filename,
            "Proposed filename cannot consist solely of dots or spaces.",
        )

    # Check stem against Windows reserved device names
    stem = Path(cleaned).stem.upper()
    if stem in WINDOWS_RESERVED_NAMES:
        return (
            False,
            original_filename,
            f"Proposed filename uses reserved Windows device name '{stem}'.",
        )

    # Enforce original extension preservation
    orig_ext = Path(original_filename).suffix.lower()
    prop_ext = Path(cleaned).suffix.lower()

    if orig_ext and not prop_ext:
        return (
            False,
            original_filename,
            f"Proposed filename omitted extension (expected '{orig_ext}').",
        )

    if orig_ext and prop_ext != orig_ext:
        return (
            False,
            original_filename,
            f"Proposed extension '{prop_ext}' does not match original extension '{orig_ext}'.",
        )

    return True, cleaned, None


def validate_and_sanitize_subfolder(
    proposed_subfolder: str, root_path: Path
) -> Tuple[bool, str, Optional[str]]:
    """Deterministically validate and sanitize proposed destination subfolder.

    Rules:
    - Must be a relative path strictly contained within root_path.
    - Cannot contain drive letters (e.g. C:), UNC paths (\\\\ or //), or parent traversals (..).
    - Each folder component must not contain invalid characters, trailing dots/spaces, or reserved names.

    Returns:
        (is_valid, normalized_subfolder, error_reason)
    """
    if not proposed_subfolder or not proposed_subfolder.strip():
        return True, "", None

    folder = proposed_subfolder.replace("\\", "/").strip()
    if folder in ("", ".", "/"):
        return True, "", None

    # Reject absolute, drive, or UNC paths
    if (
        folder.startswith(("/", "\\"))
        or ":" in folder
        or folder.startswith(("//", "\\\\"))
    ):
        return (
            False,
            "",
            "Destination subfolder cannot be absolute, UNC, or specify a drive letter.",
        )

    # Split into components and validate each individually
    parts = [p.strip() for p in folder.split("/") if p.strip()]
    cleaned_parts: List[str] = []

    for part in parts:
        if part in ("..", "."):
            return (
                False,
                "",
                "Destination subfolder contains path traversal ('..' or '.').",
            )

        if INVALID_FILENAME_CHARS_REGEX.search(part):
            return (
                False,
                "",
                f"Subfolder component '{part}' contains invalid characters.",
            )

        part_cleaned = part.rstrip(". ")
        if not part_cleaned:
            return (
                False,
                "",
                f"Subfolder component '{part}' cannot consist solely of dots or spaces.",
            )

        stem = Path(part_cleaned).stem.upper()
        if stem in WINDOWS_RESERVED_NAMES:
            return (
                False,
                "",
                f"Subfolder component '{part}' uses reserved Windows device name '{stem}'.",
            )

        cleaned_parts.append(part_cleaned)

    normalized = "/".join(cleaned_parts)

    # Verify containment using canonical security validator
    try:
        resolve_and_verify_containment(root_path, normalized)
    except SecurityBoundaryError as sec_err:
        return False, "", f"Security boundary violation: {str(sec_err)}"
    except Exception as exc:
        return False, "", f"Failed to resolve destination subfolder: {str(exc)}"

    return True, normalized, None


def check_destination_collision(
    root_path: Path,
    current_rel_path: str,
    proposed_rel_path: str,
    seen_in_batch: Set[str],
) -> Tuple[bool, Optional[str]]:
    """Check if proposed destination path collides on disk or with another item in this batch."""
    norm_proposed = proposed_rel_path.replace("\\", "/").strip("/").lower()
    norm_current = current_rel_path.replace("\\", "/").strip("/").lower()

    # 1. Batch collision check
    if norm_proposed in seen_in_batch:
        return True, f"Destination '{proposed_rel_path}' collides with another file in this batch."

    # 2. Filesystem collision check
    target_disk = root_path / proposed_rel_path
    current_disk = root_path / current_rel_path

    if target_disk.exists():
        try:
            # If target resolves to the same exact file, it's not a collision (file staying in place)
            if target_disk.resolve() != current_disk.resolve():
                return True, f"A file already exists on disk at '{proposed_rel_path}'."
        except Exception:
            return True, f"A file already exists on disk at '{proposed_rel_path}'."

    return False, None


def resolve_suggested_destination(
    raw_subfolder: Optional[str],
    category: Optional[str],
    rationale: Optional[str],
    filename: str,
    current_rel_path: str,
    rule_subfolder: str,
) -> str:
    """Deterministically resolve a clean destination subfolder from model output and metadata.

    Guarantees:
    - Never leaves files unorganized in root if category or classification is known.
    - Uses model's concrete proposed_subfolder if provided.
    - If model provided compound category (e.g. 'Documents/Work'), parses and uses it.
    - Analyzes rationale and filename for specific folder intents ('Work', 'Reports', 'Invoices').
    - Falls back to rule-based subfolder when model subfolder is empty.
    """
    if raw_subfolder and raw_subfolder.strip() and raw_subfolder.strip() not in (".", "/"):
        return raw_subfolder.strip().replace("\\", "/").strip("/")

    cat = (category or "").strip()
    r_lower = (rationale or "").lower()
    fn_lower = filename.lower()

    # If category contains path separators like "Documents/Work" or "Media/Photos"
    if "/" in cat or "\\" in cat:
        return cat.replace("\\", "/").strip("/")

    # Check for specific subfolder indicators in rationale and filename
    # 1. Work / Meeting notes
    if (
        "meeting" in fn_lower
        or "notes" in fn_lower
        or "work" in r_lower
        or "meeting" in r_lower
        or "agenda" in fn_lower
    ):
        base = cat if cat else (rule_subfolder or "Documents")
        return f"{base}/Work" if not base.endswith("/Work") else base

    # 2. Reports
    if "report" in fn_lower or "summary" in fn_lower or "report" in r_lower:
        base = cat if cat else (rule_subfolder or "Documents")
        return f"{base}/Reports" if not base.endswith("/Reports") else base

    # 3. Invoices / Receipts / Taxes
    if (
        "invoice" in fn_lower
        or "receipt" in fn_lower
        or "tax" in fn_lower
        or "invoice" in r_lower
        or "bill" in fn_lower
    ):
        base = cat if cat else (rule_subfolder or "Documents")
        return f"{base}/Invoices" if not base.endswith("/Invoices") else base

    # 4. Use category directly if non-empty
    if cat and cat not in ("Other", "Needs review"):
        return cat

    # 5. Use deterministic rule subfolder
    if rule_subfolder and rule_subfolder not in (".", "/"):
        return rule_subfolder

    # 6. If already in a subfolder, keep existing subfolder
    parent = Path(current_rel_path).parent.as_posix()
    if parent and parent != ".":
        return parent

    return "Documents"


def build_system_prompt() -> str:
    """System prompt enforcing strict structured JSON output and safe organization practices."""
    return (
        "You are TidyAI's File Organization Specialist. Your task is to analyze file metadata "
        "(filename, extension, size, existing relative path) and suggest clean organizational "
        "categories, descriptive filenames, and appropriate relative destination subfolders.\n\n"
        "STRICT RULES:\n"
        "1. Never rename file extensions. Preserve original extension exactly.\n"
        "2. Keep filenames concise, descriptive, and human-readable. If the filename is already clean, keep it as proposed_filename.\n"
        "3. Destination subfolder (proposed_subfolder) is REQUIRED. Always propose a specific relative subfolder (e.g. 'Documents/Work', 'Documents/Reports', 'Documents/Invoices', 'Images/Wallpapers', 'Code/Scripts'). Never use drive letters, '..', or absolute paths.\n"
        "4. Assign a category (e.g. 'Documents/Work', 'Documents/Reports', 'Media/Photos', 'Code/Scripts').\n"
        "5. Assign a confidence score between 0.0 and 1.0. If the file purpose is ambiguous or unclear, use a lower score (e.g. 0.4 - 0.6).\n"
        "6. Provide a concise rationale for each suggestion.\n"
        "7. Return strictly valid JSON matching the requested schema."
    )


def build_user_prompt(files: List[FileEntry]) -> str:
    """Format file metadata into a clear JSON payload for the AI model."""
    files_meta = []
    for f in files:
        rule_info = classify_file(f.filename, f.relative_path, f.size_bytes)
        files_meta.append(
            {
                "file_id": f.relative_path,
                "current_relative_path": f.relative_path,
                "filename": f.filename,
                "extension": f.extension,
                "size_bytes": f.size_bytes,
                "file_type": f.file_type.value,
                "rule_category": rule_info.category.value,
                "rule_subfolder": rule_info.suggested_subfolder,
            }
        )

    json_payload = json.dumps(files_meta, indent=2)
    return (
        f"Analyze these {len(files_meta)} files and propose organization suggestions:\n"
        f"```json\n{json_payload}\n```\n\n"
        "Return a JSON object with a 'suggestions' array containing an entry for each file."
    )


async def generate_suggestions(
    root: ApprovedRoot,
    subpath: str = "",
    file_paths: Optional[List[str]] = None,
    max_files: int = 50,
    confidence_threshold: float = 0.70,
) -> SuggestionBatchResponse:
    """Generate reviewable AI categorization and path suggestions for files in an approved root.

    Deterministic safety guarantees:
    - Never mutates filesystem.
    - Validates all model outputs against Windows filename and boundary rules.
    - Detects collisions on disk and within the batch.
    - Bounded file batch size.
    """
    root_path = Path(root.canonical_path).resolve()
    batch_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    warnings: List[SuggestionWarning] = []
    validated_suggestions: List[SuggestionItem] = []

    # 1. Gather target file metadata
    candidate_files: List[FileEntry] = []

    if file_paths:
        # User specified specific files to analyze
        for rel_p in file_paths[:max_files]:
            try:
                verified_p = resolve_and_verify_containment(root_path, rel_p)
                if not verified_p.is_file():
                    warnings.append(
                        SuggestionWarning(
                            path=rel_p,
                            warning_type="file_not_found",
                            message=f"File not found at '{rel_p}'.",
                        )
                    )
                    continue

                stat = verified_p.stat()
                norm_rel = verified_p.relative_to(root_path).as_posix()
                candidate_files.append(
                    FileEntry(
                        relative_path=norm_rel,
                        filename=verified_p.name,
                        extension=verified_p.suffix.lower(),
                        size_bytes=stat.st_size,
                        file_type="document",  # broad classification
                        is_symlink=verified_p.is_symlink(),
                    )
                )
            except SecurityBoundaryError as sec_err:
                warnings.append(
                    SuggestionWarning(
                        path=rel_p,
                        warning_type="path_traversal",
                        message=f"Security error: {str(sec_err)}",
                    )
                )
            except Exception as exc:
                warnings.append(
                    SuggestionWarning(
                        path=rel_p,
                        warning_type="validation_error",
                        message=f"Error inspecting file '{rel_p}': {str(exc)}",
                    )
                )
    else:
        # Scan approved root up to max_files
        scan_res = scan_approved_root(
            root=root,
            subpath=subpath,
            recursive=True,
            max_files=max_files,
            max_depth=15,
        )
        candidate_files = scan_res.files
        warnings.extend(
            [
                SuggestionWarning(
                    path=w.path,
                    warning_type=w.warning_type,
                    message=w.message,
                )
                for w in scan_res.warnings
            ]
        )

    # Empty candidate list: return immediately
    if not candidate_files:
        duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
        return SuggestionBatchResponse(
            batch_id=batch_id,
            summary=SuggestionSummary(
                root_id=root.id,
                root_path=str(root_path),
                total_files_analyzed=0,
                suggestions_generated=0,
                ambiguous_count=0,
                collisions_count=0,
                model_used=ollama_service.model_name,
                duration_ms=duration_ms,
            ),
            suggestions=[],
            warnings=warnings,
        )

    # 2. Send metadata to local Ollama model
    system_prompt = build_system_prompt()
    user_prompt = build_user_prompt(candidate_files)

    batch_output: Optional[OllamaSuggestionBatch] = None
    try:
        batch_output, _ = await ollama_service.generate_structured(
            prompt=user_prompt,
            response_model=OllamaSuggestionBatch,
            system_prompt=system_prompt,
            temperature=0.1,
        )
    except (
        OllamaConnectionError,
        OllamaModelNotFoundError,
        OllamaTimeoutError,
    ):
        raise
    except OllamaJsonParseError as parse_err:
        warnings.append(
            SuggestionWarning(
                path=str(root_path),
                warning_type="model_error",
                message=f"Model response failed schema parsing: {str(parse_err)}",
            )
        )
        batch_output = OllamaSuggestionBatch(suggestions=[])
    except OllamaError as o_err:
        warnings.append(
            SuggestionWarning(
                path=str(root_path),
                warning_type="model_error",
                message=f"Ollama generation error: {str(o_err)}",
            )
        )
        batch_output = OllamaSuggestionBatch(suggestions=[])

    # 3. Deterministic Validation & Collision Detection
    raw_by_id: Dict[str, OllamaFileSuggestion] = {}
    if batch_output and batch_output.suggestions:
        for idx, item in enumerate(batch_output.suggestions):
            if item.file_id:
                raw_by_id[item.file_id] = item
            if item.current_relative_path:
                raw_by_id[item.current_relative_path] = item
            if item.proposed_filename:
                raw_by_id[item.proposed_filename] = item
            # Also allow positional matching when the batch length aligns with candidate files
            if len(batch_output.suggestions) == len(candidate_files) and idx < len(candidate_files):
                cand_pos = candidate_files[idx]
                if cand_pos.relative_path not in raw_by_id:
                    raw_by_id[cand_pos.relative_path] = item
                if cand_pos.filename not in raw_by_id:
                    raw_by_id[cand_pos.filename] = item

    seen_in_batch: Set[str] = set()
    ambiguous_count = 0
    collisions_count = 0

    for cand in candidate_files:
        raw_sugg = raw_by_id.get(cand.relative_path) or raw_by_id.get(cand.filename)

        rule_info = classify_file(cand.filename, cand.relative_path, cand.size_bytes)

        if not raw_sugg:
            # Model skipped this file: fallback safely to rule-based category and destination
            warnings.append(
                SuggestionWarning(
                    path=cand.relative_path,
                    warning_type="model_error",
                    message=f"Model did not return a suggestion for this file. Preserved current location with rule category '{rule_info.category.value}'.",
                )
            )
            fallback_sub = resolve_suggested_destination(
                raw_subfolder=None,
                category=rule_info.category.value,
                rationale=rule_info.reason,
                filename=cand.filename,
                current_rel_path=cand.relative_path,
                rule_subfolder=rule_info.suggested_subfolder,
            )
            _, clean_sub, _ = validate_and_sanitize_subfolder(fallback_sub, root_path)
            prop_rel = f"{clean_sub}/{cand.filename}" if clean_sub else cand.filename

            source_canonical = (root_path / cand.relative_path).resolve()
            dest_canonical = (root_path / prop_rel).resolve()

            cur_parent = Path(cand.relative_path).parent.as_posix().replace(".", "")
            tar_parent = clean_sub.replace(".", "")
            dir_changed = (tar_parent != cur_parent)
            op_type = "move" if dir_changed else "none"

            validated_suggestions.append(
                SuggestionItem(
                    file_id=cand.relative_path,
                    root_id=root.id,
                    original_filename=cand.filename,
                    original_absolute_path=str(source_canonical),
                    current_relative_path=cand.relative_path,
                    category=rule_info.category.value,
                    proposed_filename=cand.filename,
                    proposed_subfolder=clean_sub,
                    proposed_relative_path=prop_rel,
                    destination_absolute_path=str(dest_canonical),
                    rationale=f"Preserved original location with rule recommendation (Rule fallback: {rule_info.reason}).",
                    confidence=rule_info.confidence,
                    is_ambiguous=True,
                    collision_detected=False,
                    collision_details=None,
                    is_valid=False,
                    validation_error="Missing suggestion from AI model",
                    validation_status="invalid",
                    operation_type=op_type,
                )
            )
            ambiguous_count += 1
            continue

        # 3a. Validate proposed filename
        proposed_fn = raw_sugg.proposed_filename or cand.filename
        fn_valid, clean_filename, fn_err = validate_and_sanitize_filename(
            proposed_fn, cand.filename
        )

        # 3b. Resolve and validate proposed destination subfolder
        raw_sub = raw_sugg.proposed_subfolder or ""
        resolved_sub = resolve_suggested_destination(
            raw_subfolder=raw_sub,
            category=raw_sugg.category,
            rationale=raw_sugg.rationale,
            filename=cand.filename,
            current_rel_path=cand.relative_path,
            rule_subfolder=rule_info.suggested_subfolder,
        )
        sub_valid, clean_subfolder, sub_err = validate_and_sanitize_subfolder(
            resolved_sub, root_path
        )

        is_valid = fn_valid and sub_valid
        validation_error = fn_err or sub_err

        if not is_valid:
            warnings.append(
                SuggestionWarning(
                    path=cand.relative_path,
                    warning_type="validation_error",
                    message=f"Validation failed: {validation_error}. Reverting to original filename/path.",
                )
            )
            clean_filename = cand.filename
            clean_subfolder = str(Path(cand.relative_path).parent.as_posix()).replace(".", "")

        # Compute full proposed relative path
        if clean_subfolder:
            proposed_rel = f"{clean_subfolder}/{clean_filename}"
        else:
            proposed_rel = clean_filename

        # 3c. Absolute paths and operation classification
        source_canonical = (root_path / cand.relative_path).resolve()
        orig_abs = str(source_canonical)

        destination_canonical = (root_path / proposed_rel).resolve()
        dest_abs = str(destination_canonical)

        cur_parent = Path(cand.relative_path).parent.as_posix().replace(".", "")
        tar_parent = clean_subfolder.replace(".", "")
        fn_changed = (clean_filename != cand.filename)
        dir_changed = (tar_parent != cur_parent)

        if not fn_changed and not dir_changed:
            op_type = "none"
        elif dir_changed and not fn_changed:
            op_type = "move"
        elif fn_changed and not dir_changed:
            op_type = "rename"
        else:
            op_type = "organize"

        # 3d. Collision Detection
        collided, coll_details = check_destination_collision(
            root_path=root_path,
            current_rel_path=cand.relative_path,
            proposed_rel_path=proposed_rel,
            seen_in_batch=seen_in_batch,
        )

        if collided:
            collisions_count += 1
            warnings.append(
                SuggestionWarning(
                    path=cand.relative_path,
                    warning_type="collision_disk" if "already exists" in (coll_details or "") else "collision_batch",
                    message=coll_details or "Destination collision detected.",
                )
            )

        # Register in batch destination set
        seen_in_batch.add(proposed_rel.lower())

        # 3e. Ambiguity and Validation Status
        is_ambiguous = (
            raw_sugg.confidence < confidence_threshold
            or collided
            or not is_valid
        )
        if is_ambiguous:
            ambiguous_count += 1

        if not is_valid:
            val_status = "invalid"
        elif collided:
            val_status = "collision"
        elif op_type == "none":
            val_status = "no_change"
        else:
            val_status = "valid"

        validated_suggestions.append(
            SuggestionItem(
                file_id=cand.relative_path,
                root_id=root.id,
                original_filename=cand.filename,
                original_absolute_path=orig_abs,
                current_relative_path=cand.relative_path,
                category=raw_sugg.category if is_valid else rule_info.category.value,
                proposed_filename=clean_filename,
                proposed_subfolder=clean_subfolder,
                proposed_relative_path=proposed_rel,
                destination_absolute_path=dest_abs,
                rationale=raw_sugg.rationale,
                confidence=raw_sugg.confidence,
                is_ambiguous=is_ambiguous,
                collision_detected=collided,
                collision_details=coll_details,
                is_valid=is_valid,
                validation_error=validation_error,
                validation_status=val_status,
                operation_type=op_type,
            )
        )

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return SuggestionBatchResponse(
        batch_id=batch_id,
        summary=SuggestionSummary(
            root_id=root.id,
            root_path=str(root_path),
            total_files_analyzed=len(candidate_files),
            suggestions_generated=len(validated_suggestions),
            ambiguous_count=ambiguous_count,
            collisions_count=collisions_count,
            model_used=ollama_service.model_name,
            duration_ms=duration_ms,
        ),
        suggestions=validated_suggestions,
        warnings=warnings,
    )


def stage_suggestion_item(
    item: SuggestionItem,
    custom_filename: Optional[str] = None,
    custom_subfolder: Optional[str] = None,
) -> Tuple[Optional[OperationPlanItem], str]:
    """Convert a suggestion item into a staged OperationPlanItem.

    Returns:
        (operation_plan_item or None, status_reason)
        status_reason is one of:
        - "staged": Successfully staged
        - "no_change": Source and target paths are identical (no-op)
        - "invalid": Suggestion is invalid or contains forbidden path characters
        - "collision": Collision detected with an existing file
    """
    if not item.is_valid:
        return None, "invalid"
    if item.collision_detected:
        return None, "collision"

    target_fn = (custom_filename if custom_filename is not None else item.proposed_filename).strip()
    target_sub = (custom_subfolder if custom_subfolder is not None else item.proposed_subfolder).strip()
    clean_sub = target_sub.replace("\\", "/").strip("/")

    if clean_sub:
        target_rel = f"{clean_sub}/{target_fn}"
    else:
        target_rel = target_fn

    norm_source = item.current_relative_path.replace("\\", "/").strip("/")
    norm_target = target_rel.replace("\\", "/").strip("/")

    # Security check on relative path
    if ".." in norm_target.split("/") or norm_target.startswith("/"):
        return None, "invalid"

    orig_fn = item.original_filename or (norm_source.split("/")[-1] if "/" in norm_source else norm_source)
    orig_sub = norm_source.rsplit("/", 1)[0] if "/" in norm_source else ""

    folder_changed = (clean_sub != orig_sub)
    filename_changed = (target_fn != orig_fn)

    if not folder_changed and not filename_changed:
        return None, "no_change"

    # If only folder changes -> MOVE
    # If only filename changes -> RENAME
    # If both change -> MOVE with new filename
    if folder_changed and not filename_changed:
        op_type = "move"
    elif not folder_changed and filename_changed:
        op_type = "rename"
    else:
        op_type = "move"

    op = OperationPlanItem(
        source_rel_path=norm_source,
        target_rel_path=norm_target,
        operation_type=op_type,
        approved=True,
    )
    return op, "staged"


def stage_accepted_suggestions_batch(
    suggestions: List[SuggestionItem],
    decisions: Dict[str, str],
    edits: Optional[Dict[str, Dict[str, str]]] = None,
) -> Tuple[List[OperationPlanItem], Dict[str, int]]:
    """Bulk stage accepted suggestions, skipping invalid, colliding, and no-change items.

    Returns:
        (staged_operations, summary_counts)
        summary_counts keys: 'staged', 'skipped_no_change', 'skipped_invalid', 'skipped_collision', 'skipped_unapproved'
    """
    staged: List[OperationPlanItem] = []
    counts = {
        "staged": 0,
        "skipped_no_change": 0,
        "skipped_invalid": 0,
        "skipped_collision": 0,
        "skipped_unapproved": 0,
    }
    edits = edits or {}

    for item in suggestions:
        decision = decisions.get(item.file_id)
        if decision != "accepted":
            counts["skipped_unapproved"] += 1
            continue

        item_edit = edits.get(item.file_id, {})
        custom_fn = item_edit.get("proposed_filename")
        custom_sub = item_edit.get("proposed_subfolder")

        op, reason = stage_suggestion_item(item, custom_filename=custom_fn, custom_subfolder=custom_sub)
        if op:
            staged.append(op)
            counts["staged"] += 1
        elif reason == "no_change":
            counts["skipped_no_change"] += 1
        elif reason == "collision":
            counts["skipped_collision"] += 1
        else:
            counts["skipped_invalid"] += 1

    return staged, counts

