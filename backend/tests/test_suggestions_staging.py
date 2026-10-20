"""Tests for TidyAI AI Suggestion Destination Paths and Staging.

Verifies:
1. Same source and target is not staged (no-op skipped).
2. Valid move to a different directory is staged correctly with operation_type='move'.
3. Rename to a different filename is staged correctly with operation_type='rename'.
4. Move plus rename resolves the correct target path and operation_type='move'.
5. Existing target causes a conflict (collision detected, silent overwrites forbidden).
6. Invalid destination or unapproved root is rejected (security containment).
7. Bulk acceptance skips invalid/colliding/unchanged suggestions and reports skipped counts.
8. Dry-run does not modify the filesystem (read-only guarantee, no folders created).
"""

import os
from pathlib import Path
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    OperationPlanItem,
    OperationType,
    SuggestionItem,
    SuggestionStageRequest,
)
from backend.app.services.operations import simulate_dry_run
from backend.app.services.roots_registry import roots_registry
from backend.app.services.suggestions import (
    stage_accepted_suggestions_batch,
    stage_suggestion_item,
)

client = TestClient(app)


@pytest.fixture
def temp_root(tmp_path: Path):
    """Register and return an approved root in a clean temporary directory."""
    root_dir = tmp_path / "test_staging_root"
    root_dir.mkdir(parents=True, exist_ok=True)
    approved = roots_registry.approve_root(str(root_dir), "Test Staging Root")
    yield approved
    roots_registry.remove_root(approved.id)


def test_1_same_source_and_target_not_staged(temp_root):
    """Test 1: Same source and target is not staged (rejected as no-op)."""
    root_path = Path(temp_root.canonical_path)
    file_path = root_path / "meeting-notes.txt"
    file_path.write_text("Team meeting notes", encoding="utf-8")

    # Suggestion with identical source and target (e.g. root to root with same filename)
    suggestion = SuggestionItem(
        file_id="meeting-notes.txt",
        root_id=temp_root.id,
        original_filename="meeting-notes.txt",
        original_absolute_path=str(file_path),
        current_relative_path="meeting-notes.txt",
        category="Documents",
        proposed_filename="meeting-notes.txt",
        proposed_subfolder="",
        proposed_relative_path="meeting-notes.txt",
        destination_absolute_path=str(file_path),
        rationale="Documents folder suggestion with unchanged path",
        confidence=0.95,
        is_ambiguous=False,
        collision_detected=False,
        is_valid=True,
        validation_status="no_change",
        operation_type="none",
    )

    # 1a: Unit service function returns None and reason "no_change"
    op, reason = stage_suggestion_item(suggestion)
    assert op is None
    assert reason == "no_change"

    # 1b: API endpoint excludes identical source & target and reports skipped count
    res = client.post(
        "/api/suggestions/stage",
        json={
            "root_id": temp_root.id,
            "suggestions": [suggestion.model_dump()],
            "decisions": {"meeting-notes.txt": "accepted"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["operations"]) == 0
    assert data["counts"]["staged"] == 0
    assert data["counts"]["skipped_no_change"] == 1

    # 1c: If an identical operation is simulated in dry-run, it fails closed as no-op
    dry_res = simulate_dry_run(
        temp_root,
        [
            OperationPlanItem(
                source_rel_path="meeting-notes.txt",
                target_rel_path="meeting-notes.txt",
                operation_type=OperationType.MOVE,
                approved=True,
            )
        ],
    )
    assert dry_res.summary.safe_operations == 0
    assert dry_res.summary.blocked_operations == 1
    assert "identical" in dry_res.items[0].validation_error.lower()


def test_2_valid_move_to_different_directory_staged_correctly(temp_root):
    """Test 2: Valid move to a different directory is staged correctly with operation_type='move'."""
    root_path = Path(temp_root.canonical_path)
    file_path = root_path / "meeting-notes.txt"
    file_path.write_text("Weekly team sync", encoding="utf-8")

    suggestion = SuggestionItem(
        file_id="meeting-notes.txt",
        root_id=temp_root.id,
        original_filename="meeting-notes.txt",
        original_absolute_path=str(file_path),
        current_relative_path="meeting-notes.txt",
        category="Documents",
        proposed_filename="meeting-notes.txt",
        proposed_subfolder="Documents/Work",
        proposed_relative_path="Documents/Work/meeting-notes.txt",
        destination_absolute_path=str(root_path / "Documents/Work/meeting-notes.txt"),
        rationale="Categorized under Documents/Work",
        confidence=0.95,
        is_ambiguous=False,
        collision_detected=False,
        is_valid=True,
        validation_status="valid",
        operation_type="move",
    )

    op, reason = stage_suggestion_item(suggestion)
    assert reason == "staged"
    assert op is not None
    assert op.source_rel_path == "meeting-notes.txt"
    assert op.target_rel_path == "Documents/Work/meeting-notes.txt"
    assert op.operation_type == "move" or op.operation_type == OperationType.MOVE

    # Verify via API endpoint
    res = client.post(
        "/api/suggestions/stage",
        json={
            "root_id": temp_root.id,
            "suggestions": [suggestion.model_dump()],
            "decisions": {"meeting-notes.txt": "accepted"},
        },
    )
    assert res.status_code == 200
    data = res.json()
    assert len(data["operations"]) == 1
    assert data["operations"][0]["target_rel_path"] == "Documents/Work/meeting-notes.txt"
    assert data["operations"][0]["operation_type"] == "move"
    assert data["counts"]["staged"] == 1


def test_3_rename_to_different_filename_staged_correctly(temp_root):
    """Test 3: Rename to a different filename in same directory is staged with operation_type='rename'."""
    root_path = Path(temp_root.canonical_path)
    docs_dir = root_path / "Documents"
    docs_dir.mkdir(parents=True, exist_ok=True)
    file_path = docs_dir / "draft_copy.txt"
    file_path.write_text("Draft copy content", encoding="utf-8")

    suggestion = SuggestionItem(
        file_id="Documents/draft_copy.txt",
        root_id=temp_root.id,
        original_filename="draft_copy.txt",
        original_absolute_path=str(file_path),
        current_relative_path="Documents/draft_copy.txt",
        category="Documents",
        proposed_filename="final_report.txt",
        proposed_subfolder="Documents",
        proposed_relative_path="Documents/final_report.txt",
        destination_absolute_path=str(docs_dir / "final_report.txt"),
        rationale="Renamed draft to final report",
        confidence=0.90,
        is_ambiguous=False,
        collision_detected=False,
        is_valid=True,
        validation_status="valid",
        operation_type="rename",
    )

    op, reason = stage_suggestion_item(suggestion)
    assert reason == "staged"
    assert op is not None
    assert op.source_rel_path == "Documents/draft_copy.txt"
    assert op.target_rel_path == "Documents/final_report.txt"
    assert op.operation_type == "rename" or op.operation_type == OperationType.RENAME


def test_4_move_plus_rename_resolves_correct_target(temp_root):
    """Test 4: Move plus rename resolves the correct target path with operation_type='move'."""
    root_path = Path(temp_root.canonical_path)
    file_path = root_path / "raw_receipt_123.pdf"
    file_path.write_text("Receipt content", encoding="utf-8")

    suggestion = SuggestionItem(
        file_id="raw_receipt_123.pdf",
        root_id=temp_root.id,
        original_filename="raw_receipt_123.pdf",
        original_absolute_path=str(file_path),
        current_relative_path="raw_receipt_123.pdf",
        category="Finance",
        proposed_filename="Receipt_2026_01.pdf",
        proposed_subfolder="Finance/Invoices",
        proposed_relative_path="Finance/Invoices/Receipt_2026_01.pdf",
        destination_absolute_path=str(root_path / "Finance/Invoices/Receipt_2026_01.pdf"),
        rationale="Organized to Finance/Invoices with standardized date name",
        confidence=0.92,
        is_ambiguous=False,
        collision_detected=False,
        is_valid=True,
        validation_status="valid",
        operation_type="organize",
    )

    op, reason = stage_suggestion_item(suggestion)
    assert reason == "staged"
    assert op is not None
    assert op.source_rel_path == "raw_receipt_123.pdf"
    assert op.target_rel_path == "Finance/Invoices/Receipt_2026_01.pdf"
    assert op.operation_type == "move" or op.operation_type == OperationType.MOVE


def test_5_existing_target_causes_conflict(temp_root):
    """Test 5: Existing target on disk causes a collision conflict and is blocked."""
    root_path = Path(temp_root.canonical_path)
    src_file = root_path / "report.txt"
    src_file.write_text("Source report", encoding="utf-8")

    # Create destination file so it already exists on disk
    dest_dir = root_path / "Documents/Reports"
    dest_dir.mkdir(parents=True, exist_ok=True)
    existing_file = dest_dir / "report.txt"
    existing_file.write_text("Existing report file", encoding="utf-8")

    # Dry-run must detect collision and block execution (fail closed)
    plan = [
        OperationPlanItem(
            source_rel_path="report.txt",
            target_rel_path="Documents/Reports/report.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    dry_res = simulate_dry_run(temp_root, plan)
    assert dry_res.summary.safe_operations == 0
    assert dry_res.summary.blocked_operations == 1
    assert dry_res.items[0].collision_detected is True
    assert "already exists" in dry_res.items[0].validation_error.lower()

    # Suggestion with collision_detected=True cannot be staged
    colliding_sugg = SuggestionItem(
        file_id="report.txt",
        root_id=temp_root.id,
        original_filename="report.txt",
        original_absolute_path=str(src_file),
        current_relative_path="report.txt",
        category="Documents",
        proposed_filename="report.txt",
        proposed_subfolder="Documents/Reports",
        proposed_relative_path="Documents/Reports/report.txt",
        destination_absolute_path=str(existing_file),
        rationale="Collides with existing file",
        confidence=0.85,
        is_ambiguous=True,
        collision_detected=True,
        collision_details="Target path already exists on disk",
        is_valid=True,
        validation_status="collision",
        operation_type="move",
    )

    op, reason = stage_suggestion_item(colliding_sugg)
    assert op is None
    assert reason == "collision"


def test_6_invalid_destination_or_unapproved_root_rejected(temp_root):
    """Test 6: Invalid destination, path traversal, or unapproved root is rejected."""
    root_path = Path(temp_root.canonical_path)
    src_file = root_path / "valid.txt"
    src_file.write_text("test", encoding="utf-8")

    # 6a: Path traversal out of approved root is blocked in dry-run
    traversal_plan = [
        OperationPlanItem(
            source_rel_path="valid.txt",
            target_rel_path="../../escaped.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]
    dry_res = simulate_dry_run(temp_root, traversal_plan)
    assert dry_res.summary.safe_operations == 0
    assert dry_res.summary.blocked_operations == 1
    assert "boundary" in dry_res.items[0].validation_error.lower()

    # 6b: Suggestion with invalid path traversal is rejected during staging
    invalid_sugg = SuggestionItem(
        file_id="valid.txt",
        root_id=temp_root.id,
        original_filename="valid.txt",
        original_absolute_path=str(src_file),
        current_relative_path="valid.txt",
        category="Documents",
        proposed_filename="escaped.txt",
        proposed_subfolder="../outside",
        proposed_relative_path="../outside/escaped.txt",
        destination_absolute_path="",
        rationale="Invalid traversal",
        confidence=0.5,
        is_ambiguous=True,
        collision_detected=False,
        is_valid=False,
        validation_status="invalid",
        validation_error="Path traversal forbidden",
        operation_type="move",
    )
    op, reason = stage_suggestion_item(invalid_sugg)
    assert op is None
    assert reason == "invalid"

    # 6c: Unapproved root ID is rejected with 404
    res = client.post(
        "/api/suggestions/stage",
        json={
            "root_id": "non-existent-root-id",
            "suggestions": [],
            "decisions": {},
        },
    )
    assert res.status_code == 404


def test_7_bulk_acceptance_skips_invalid_suggestions(temp_root):
    """Test 7: Bulk acceptance excludes invalid, colliding, and unchanged suggestions and tracks counts."""
    root_path = Path(temp_root.canonical_path)

    # Valid move
    f1 = root_path / "f1.txt"
    f1.write_text("f1", encoding="utf-8")
    s1 = SuggestionItem(
        file_id="f1.txt",
        root_id=temp_root.id,
        original_filename="f1.txt",
        original_absolute_path=str(f1),
        current_relative_path="f1.txt",
        category="Documents",
        proposed_filename="f1.txt",
        proposed_subfolder="Documents/Work",
        proposed_relative_path="Documents/Work/f1.txt",
        destination_absolute_path=str(root_path / "Documents/Work/f1.txt"),
        rationale="Valid move",
        confidence=0.9,
        is_valid=True,
        validation_status="valid",
        operation_type="move",
    )

    # Unchanged (source == target)
    f2 = root_path / "f2.txt"
    f2.write_text("f2", encoding="utf-8")
    s2 = SuggestionItem(
        file_id="f2.txt",
        root_id=temp_root.id,
        original_filename="f2.txt",
        original_absolute_path=str(f2),
        current_relative_path="f2.txt",
        category="Documents",
        proposed_filename="f2.txt",
        proposed_subfolder="",
        proposed_relative_path="f2.txt",
        destination_absolute_path=str(f2),
        rationale="No change",
        confidence=0.9,
        is_valid=True,
        validation_status="no_change",
        operation_type="none",
    )

    # Colliding
    f3 = root_path / "f3.txt"
    f3.write_text("f3", encoding="utf-8")
    s3 = SuggestionItem(
        file_id="f3.txt",
        root_id=temp_root.id,
        original_filename="f3.txt",
        original_absolute_path=str(f3),
        current_relative_path="f3.txt",
        category="Documents",
        proposed_filename="f3.txt",
        proposed_subfolder="Documents/Work",
        proposed_relative_path="Documents/Work/f3.txt",
        destination_absolute_path=str(root_path / "Documents/Work/f3.txt"),
        rationale="Collision",
        confidence=0.8,
        collision_detected=True,
        is_valid=True,
        validation_status="collision",
        operation_type="move",
    )

    # Invalid
    f4 = root_path / "f4.txt"
    f4.write_text("f4", encoding="utf-8")
    s4 = SuggestionItem(
        file_id="f4.txt",
        root_id=temp_root.id,
        original_filename="f4.txt",
        original_absolute_path=str(f4),
        current_relative_path="f4.txt",
        category="Documents",
        proposed_filename="f4.txt",
        proposed_subfolder="../outside",
        proposed_relative_path="../outside/f4.txt",
        destination_absolute_path="",
        rationale="Invalid",
        confidence=0.4,
        is_valid=False,
        validation_status="invalid",
        operation_type="move",
    )

    all_suggestions = [s1, s2, s3, s4]
    decisions = {s.file_id: "accepted" for s in all_suggestions}

    staged, counts = stage_accepted_suggestions_batch(all_suggestions, decisions)

    # Exactly 1 should be staged (s1)
    assert len(staged) == 1
    assert staged[0].source_rel_path == "f1.txt"
    assert staged[0].target_rel_path == "Documents/Work/f1.txt"

    # Verify breakdown of skipped items
    assert counts["staged"] == 1
    assert counts["skipped_no_change"] == 1
    assert counts["skipped_collision"] == 1
    assert counts["skipped_invalid"] == 1


def test_8_dry_run_does_not_modify_filesystem(temp_root):
    """Test 8: Dry-run simulation is strictly read-only and does not mutate disk or create folders."""
    root_path = Path(temp_root.canonical_path)
    file_path = root_path / "original_meeting_notes.txt"
    file_content = "Pre-meeting brainstorm notes: non-modifiable content"
    file_path.write_text(file_content, encoding="utf-8")

    subfolder = root_path / "Documents" / "Work"
    assert not subfolder.exists()

    stat_before = file_path.stat()
    entries_before = sorted(os.listdir(root_path))
    assert entries_before == ["original_meeting_notes.txt"]

    plan = [
        OperationPlanItem(
            source_rel_path="original_meeting_notes.txt",
            target_rel_path="Documents/Work/original_meeting_notes.txt",
            operation_type=OperationType.MOVE,
            approved=True,
        )
    ]

    res = simulate_dry_run(temp_root, plan)

    # Dry-run reported safe
    assert res.summary.safe_operations == 1
    assert res.summary.blocked_operations == 0
    assert res.items[0].is_safe is True
    assert res.items[0].will_create_subfolder == "Documents/Work"

    # Verify zero disk mutations
    entries_after = sorted(os.listdir(root_path))
    assert entries_after == entries_before
    assert file_path.exists()
    assert file_path.read_text(encoding="utf-8") == file_content
    stat_after = file_path.stat()
    assert stat_before.st_mtime == stat_after.st_mtime
    assert stat_before.st_size == stat_after.st_size

    # Subfolder MUST NOT be created during dry-run
    assert not subfolder.exists()
