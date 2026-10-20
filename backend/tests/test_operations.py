"""Comprehensive tests for TidyAI Operations, Dry-Run Simulation, and Safe Undo."""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    OperationPlanItem,
    OperationType,
)
from backend.app.services.operations import (
    apply_operation_plan,
    get_operation_history,
    simulate_dry_run,
    undo_operation_batch,
)
from backend.app.services.roots_registry import roots_registry


@pytest.fixture
def temp_root(tmp_path: Path):
    """Register and return an approved root in a clean temporary directory."""
    root_dir = tmp_path / "test_ops_root"
    root_dir.mkdir(parents=True, exist_ok=True)
    approved = roots_registry.approve_root(str(root_dir), "Test Ops Root")
    yield approved
    roots_registry.remove_root(approved.id)


def test_dry_run_non_invariance(temp_root):
    """Dry run MUST NEVER move, rename, delete files, or create directories on disk."""
    root_path = Path(temp_root.canonical_path)
    file1 = root_path / "invoice.pdf"
    file2 = root_path / "photo.jpg"
    file1.write_text("invoice content", encoding="utf-8")
    file2.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 20)

    # Snapshot directory state before dry-run
    entries_before = sorted(os.listdir(root_path))
    assert entries_before == ["invoice.pdf", "photo.jpg"]

    ops = [
        OperationPlanItem(
            source_rel_path="invoice.pdf",
            target_rel_path="Documents/Invoices/invoice.pdf",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
        OperationPlanItem(
            source_rel_path="photo.jpg",
            target_rel_path="Images/photo.jpg",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
    ]

    res = simulate_dry_run(temp_root, ops)
    assert res.summary.total_operations == 2
    assert res.summary.safe_operations == 2
    assert res.summary.blocked_operations == 0
    assert res.summary.is_executable is True

    assert res.items[0].is_safe is True
    assert res.items[0].will_create_subfolder == "Documents/Invoices"
    assert res.items[1].is_safe is True
    assert res.items[1].will_create_subfolder == "Images"

    # Filesystem check: absolutely NOTHING was created or moved on disk
    entries_after = sorted(os.listdir(root_path))
    assert entries_after == entries_before
    assert not (root_path / "Documents").exists()
    assert not (root_path / "Images").exists()
    assert file1.exists()
    assert file2.exists()


def test_dry_run_disk_collision_detection(temp_root):
    """Dry run detects existing destination files and fails closed."""
    root_path = Path(temp_root.canonical_path)
    src = root_path / "report.pdf"
    src.write_text("new report", encoding="utf-8")

    # Pre-create conflicting target file
    dest_dir = root_path / "Documents"
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing_dest = dest_dir / "report.pdf"
    existing_dest.write_text("existing conflict", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="report.pdf",
            target_rel_path="Documents/report.pdf",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    res = simulate_dry_run(temp_root, ops)
    assert res.summary.total_operations == 1
    assert res.summary.safe_operations == 0
    assert res.summary.blocked_operations == 1
    assert res.summary.is_executable is False

    item = res.items[0]
    assert item.is_safe is False
    assert item.collision_detected is True
    assert "already exists on disk" in item.validation_error


def test_dry_run_batch_duplicate_collision(temp_root):
    """Detects multiple items within the same batch targeting the identical path."""
    root_path = Path(temp_root.canonical_path)
    (root_path / "docA.txt").write_text("A", encoding="utf-8")
    (root_path / "docB.txt").write_text("B", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="docA.txt",
            target_rel_path="Archive/target.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
        OperationPlanItem(
            source_rel_path="docB.txt",
            target_rel_path="Archive/target.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
    ]

    res = simulate_dry_run(temp_root, ops)
    assert res.summary.safe_operations == 1
    assert res.summary.blocked_operations == 1
    assert res.items[1].collision_detected is True
    assert "Duplicate target collision within batch" in res.items[1].validation_error


def test_dry_run_boundary_escape(temp_root):
    """Dry run flags traversal attacks as safety violations."""
    root_path = Path(temp_root.canonical_path)
    (root_path / "secret.txt").write_text("secret", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="secret.txt",
            target_rel_path="../../escape.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    res = simulate_dry_run(temp_root, ops)
    assert res.summary.safe_operations == 0
    assert res.summary.blocked_operations == 1
    assert res.items[0].is_safe is False
    assert "Path traversal detected" in res.items[0].validation_error


def test_apply_requires_explicit_confirmation(temp_root):
    """Applying without confirmed=True must raise ValueError."""
    root_path = Path(temp_root.canonical_path)
    (root_path / "test.txt").write_text("content", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="test.txt",
            target_rel_path="Dest/test.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    with pytest.raises(ValueError, match="Explicit user confirmation"):
        apply_operation_plan(temp_root, ops, confirmed=False)


def test_apply_and_safe_undo_lifecycle(temp_root):
    """Complete lifecycle: Apply moves files, records ledger, and undo restores them."""
    root_path = Path(temp_root.canonical_path)
    f1 = root_path / "file1.txt"
    f2 = root_path / "file2.txt"
    f1.write_text("file 1 content", encoding="utf-8")
    f2.write_text("file 2 content", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="file1.txt",
            target_rel_path="Subfolder1/file1.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
        OperationPlanItem(
            source_rel_path="file2.txt",
            target_rel_path="Subfolder2/Nested/file2.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
    ]

    # Apply
    apply_res = apply_operation_plan(temp_root, ops, confirmed=True)
    assert apply_res.status == "completed"
    assert apply_res.total_applied == 2
    assert apply_res.failed_count == 0

    # Verify moved on disk
    assert not f1.exists()
    assert not f2.exists()
    moved1 = root_path / "Subfolder1" / "file1.txt"
    moved2 = root_path / "Subfolder2" / "Nested" / "file2.txt"
    assert moved1.exists() and moved1.read_text("utf-8") == "file 1 content"
    assert moved2.exists() and moved2.read_text("utf-8") == "file 2 content"

    # Safe Undo
    undo_res = undo_operation_batch(apply_res.batch_id)
    assert undo_res.status == "fully_undone"
    assert undo_res.total_reverted == 2
    assert undo_res.blocked_count == 0

    # Verify restored on disk
    assert f1.exists() and f1.read_text("utf-8") == "file 1 content"
    assert f2.exists() and f2.read_text("utf-8") == "file 2 content"
    assert not moved1.exists()
    assert not moved2.exists()

    # Re-running undo on already undone batch raises ValueError
    with pytest.raises(ValueError, match="already been fully undone"):
        undo_operation_batch(apply_res.batch_id)


def test_apply_fails_closed_on_occupied_target(temp_root):
    """Apply fails closed and will not silently overwrite an occupied target."""
    root_path = Path(temp_root.canonical_path)
    src = root_path / "item.txt"
    src.write_text("source version", encoding="utf-8")

    # Conflict destination already existing
    dest_dir = root_path / "Docs"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_file = dest_dir / "item.txt"
    dest_file.write_text("original occupied target", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="item.txt",
            target_rel_path="Docs/item.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    res = apply_operation_plan(temp_root, ops, confirmed=True)
    assert res.status == "failed"
    assert res.total_applied == 0
    assert res.failed_count == 1
    assert "already exists on disk" in res.items[0].error_message

    # Verify original files were preserved without corruption or overwrite
    assert src.exists() and src.read_text("utf-8") == "source version"
    assert dest_file.exists() and dest_file.read_text("utf-8") == "original occupied target"


def test_undo_fails_closed_if_original_path_occupied(temp_root):
    """Undo refuses to overwrite if original source path has since been occupied."""
    root_path = Path(temp_root.canonical_path)
    f = root_path / "data.log"
    f.write_text("first version", encoding="utf-8")

    ops = [
        OperationPlanItem(
            source_rel_path="data.log",
            target_rel_path="Logs/data.log",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    apply_res = apply_operation_plan(temp_root, ops, confirmed=True)
    assert apply_res.status == "completed"

    # Now create a new file at original location 'data.log'
    (root_path / "data.log").write_text("new occupant", encoding="utf-8")

    undo_res = undo_operation_batch(apply_res.batch_id)
    assert undo_res.total_reverted == 0
    assert undo_res.blocked_count == 1
    assert undo_res.status == "failed"
    assert "currently occupied on disk" in undo_res.items[0].error_message

    # Neither file should be deleted
    assert (root_path / "data.log").read_text("utf-8") == "new occupant"
    assert (root_path / "Logs" / "data.log").read_text("utf-8") == "first version"


def test_api_operations_endpoints_roundtrip(temp_root):
    """Test full HTTP API endpoint flow for preview, apply, history, and undo."""
    client = TestClient(app)
    root_path = Path(temp_root.canonical_path)
    (root_path / "doc.txt").write_text("API test content", encoding="utf-8")

    plan = [
        {
            "source_rel_path": "doc.txt",
            "target_rel_path": "Processed/doc.txt",
            "operation_type": "move",
            "approved": True,
        }
    ]

    # 1. Preview (Dry Run)
    preview_res = client.post(
        "/api/operations/preview",
        json={"root_id": temp_root.id, "operations": plan},
    )
    assert preview_res.status_code == 200
    preview_data = preview_res.json()
    assert preview_data["summary"]["safe_operations"] == 1
    assert preview_data["summary"]["is_executable"] is True
    # Disk check: doc.txt still at root, Processed/ does not exist
    assert (root_path / "doc.txt").exists()
    assert not (root_path / "Processed").exists()

    # 2. Unconfirmed Apply should return 400
    bad_apply = client.post(
        "/api/operations/apply",
        json={"root_id": temp_root.id, "operations": plan, "confirmed": False},
    )
    assert bad_apply.status_code == 400

    # 3. Confirmed Apply
    apply_res = client.post(
        "/api/operations/apply",
        json={"root_id": temp_root.id, "operations": plan, "confirmed": True},
    )
    assert apply_res.status_code == 200
    apply_data = apply_res.json()
    batch_id = apply_data["batch_id"]
    assert apply_data["status"] == "completed"
    assert (root_path / "Processed" / "doc.txt").exists()

    # 4. History
    history_res = client.get(f"/api/operations/history?root_id={temp_root.id}")
    assert history_res.status_code == 200
    history_data = history_res.json()
    assert len(history_data["batches"]) >= 1
    assert any(b["batch_id"] == batch_id for b in history_data["batches"])

    # 5. Undo
    undo_res = client.post(f"/api/operations/{batch_id}/undo")
    assert undo_res.status_code == 200
    undo_data = undo_res.json()
    assert undo_data["status"] == "fully_undone"
    assert (root_path / "doc.txt").exists()
    assert not (root_path / "Processed" / "doc.txt").exists()


def test_apply_partial_failure_and_partial_undo(temp_root):
    """Verify partial failure handling when one file is missing and undo reverts only applied items."""
    root_path = Path(temp_root.canonical_path)
    (root_path / "exists.txt").write_text("exists content", encoding="utf-8")
    # "missing.txt" does not exist

    ops = [
        OperationPlanItem(
            source_rel_path="exists.txt",
            target_rel_path="Folder/exists.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
        OperationPlanItem(
            source_rel_path="missing.txt",
            target_rel_path="Folder/missing.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        ),
    ]

    apply_res = apply_operation_plan(temp_root, ops, confirmed=True)
    assert apply_res.status == "partial"
    assert apply_res.total_applied == 1
    assert apply_res.failed_count == 1
    assert (root_path / "Folder" / "exists.txt").exists()

    # Safe undo should only revert the 1 applied file
    undo_res = undo_operation_batch(apply_res.batch_id)
    assert undo_res.status == "fully_undone"
    assert undo_res.total_reverted == 1
    assert (root_path / "exists.txt").exists()
    assert not (root_path / "Folder" / "exists.txt").exists()


def test_undo_nonexistent_batch_404(temp_root):
    """Attempting to undo a nonexistent batch raises KeyError."""
    with pytest.raises(KeyError, match="was not found in audit ledger"):
        undo_operation_batch("batch-nonexistent999")

