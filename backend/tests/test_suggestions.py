"""Tests for Phase 5 AI Categorization and Suggestion Engine.

Validates deterministic sanitization, Windows-safe filename validation, path traversal
rejection, reserved device names, disk/batch collision detection, low-confidence flagging,
graceful error handling, and the mandatory zero-mutation guarantee.
"""

import os
from pathlib import Path
from unittest.mock import AsyncMock, patch
import pytest
from fastapi.testclient import TestClient

from backend.app.main import app
from backend.app.schemas import (
    ApprovedRoot,
    OllamaFileSuggestion,
    OllamaSuggestionBatch,
)
from backend.app.services.ollama import (
    OllamaConnectionError,
    OllamaJsonParseError,
    OllamaModelNotFoundError,
)
from backend.app.services.roots_registry import roots_registry
from backend.app.services.suggestions import (
    check_destination_collision,
    generate_suggestions,
    validate_and_sanitize_filename,
    validate_and_sanitize_subfolder,
)

client = TestClient(app)


# ==============================================================================
# Unit Tests: Filename Validation & Sanitization
# ==============================================================================

def test_validate_and_sanitize_filename_valid():
    """Valid filename preserving extension passes cleanly."""
    valid, clean, err = validate_and_sanitize_filename("Quarterly_Report_2026.pdf", "old_draft.pdf")
    assert valid is True
    assert clean == "Quarterly_Report_2026.pdf"
    assert err is None


def test_validate_and_sanitize_filename_empty():
    """Empty proposed filename fails closed and reverts to original."""
    valid, clean, err = validate_and_sanitize_filename("   ", "original.txt")
    assert valid is False
    assert clean == "original.txt"
    assert "cannot be empty" in err.lower()


def test_validate_and_sanitize_filename_invalid_chars():
    """Characters forbidden on Windows (< > : \" / \\ | ? *) fail closed."""
    for bad_name in [
        "report<1>.pdf",
        "budget:2026.xlsx",
        "my*cool?pic.png",
        "slash/name.txt",
        "back\\slash.doc",
        'quote"name".csv',
        "pipe|test.mp3",
    ]:
        valid, clean, err = validate_and_sanitize_filename(bad_name, "original.pdf")
        assert valid is False
        assert clean == "original.pdf"
        assert "invalid characters" in err.lower() or "path separators" in err.lower()


def test_validate_and_sanitize_filename_windows_reserved():
    """Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9) fail closed."""
    reserved_stems = ["con", "PRN", "aux", "Nul", "com1", "COM9", "lpt1", "LPT9"]
    for stem in reserved_stems:
        bad_name = f"{stem}.txt"
        valid, clean, err = validate_and_sanitize_filename(bad_name, "original.txt")
        assert valid is False
        assert clean == "original.txt"
        assert "reserved windows device name" in err.lower()


def test_validate_and_sanitize_filename_extension_mismatch():
    """Altered or omitted file extension fails closed."""
    # Altered extension
    valid, clean, err = validate_and_sanitize_filename("report.exe", "report.pdf")
    assert valid is False
    assert clean == "report.pdf"
    assert "does not match original extension" in err.lower()

    # Omitted extension
    valid, clean, err = validate_and_sanitize_filename("report", "report.pdf")
    assert valid is False
    assert clean == "report.pdf"
    assert "omitted extension" in err.lower()


def test_validate_and_sanitize_filename_trailing_dots_spaces():
    """Trailing dots and spaces are stripped cleanly or rejected if empty."""
    valid, clean, err = validate_and_sanitize_filename("valid_name.txt. ", "old.txt")
    assert valid is True
    assert clean == "valid_name.txt"

    # Only dots
    valid, clean, err = validate_and_sanitize_filename("... ", "old.txt")
    assert valid is False
    assert clean == "old.txt"


# ==============================================================================
# Unit Tests: Subfolder Validation & Containment
# ==============================================================================

def test_validate_and_sanitize_subfolder_valid(tmp_path: Path):
    """Valid relative destination subfolder passes."""
    valid, norm, err = validate_and_sanitize_subfolder("Documents/Finance/2026", tmp_path)
    assert valid is True
    assert norm == "Documents/Finance/2026"
    assert err is None

    # Empty subfolder means root
    valid, norm, err = validate_and_sanitize_subfolder("", tmp_path)
    assert valid is True
    assert norm == ""


def test_validate_and_sanitize_subfolder_traversal_fails(tmp_path: Path):
    """Path traversal ('..') is strictly rejected."""
    for bad_sub in ["../escape", "sub/../../other", "..", "folder/.."]:
        valid, norm, err = validate_and_sanitize_subfolder(bad_sub, tmp_path)
        assert valid is False
        assert "traversal" in err.lower() or "security" in err.lower()


def test_validate_and_sanitize_subfolder_absolute_or_drive_fails(tmp_path: Path):
    """Absolute paths, drive letters, and UNC prefixes are strictly rejected."""
    for bad_sub in ["/absolute/path", "C:\\Windows", "\\\\server\\share", "D:/data"]:
        valid, norm, err = validate_and_sanitize_subfolder(bad_sub, tmp_path)
        assert valid is False
        assert "cannot be absolute" in err.lower() or "security" in err.lower()


def test_validate_and_sanitize_subfolder_reserved_names(tmp_path: Path):
    """Subfolders containing Windows reserved device names fail closed."""
    valid, norm, err = validate_and_sanitize_subfolder("records/AUX/invoices", tmp_path)
    assert valid is False
    assert "reserved windows device name" in err.lower()


# ==============================================================================
# Unit Tests: Collision Detection
# ==============================================================================

def test_collision_detection_on_disk(tmp_path: Path):
    """Existing file on disk at proposed path is flagged as a collision."""
    existing_file = tmp_path / "Documents" / "existing.pdf"
    existing_file.parent.mkdir(parents=True, exist_ok=True)
    existing_file.write_text("existing content")

    source_file = tmp_path / "Downloads" / "incoming.pdf"
    source_file.parent.mkdir(parents=True, exist_ok=True)
    source_file.write_text("source content")

    collided, details = check_destination_collision(
        root_path=tmp_path,
        current_rel_path="Downloads/incoming.pdf",
        proposed_rel_path="Documents/existing.pdf",
        seen_in_batch=set(),
    )
    assert collided is True
    assert "already exists on disk" in details


def test_collision_detection_in_batch(tmp_path: Path):
    """Two files targeting the same proposed relative path trigger a batch collision."""
    seen: set = {"documents/target.pdf"}

    collided, details = check_destination_collision(
        root_path=tmp_path,
        current_rel_path="Downloads/other.pdf",
        proposed_rel_path="Documents/Target.pdf",  # case-insensitive on Windows
        seen_in_batch=seen,
    )
    assert collided is True
    assert "collides with another file in this batch" in details


# ==============================================================================
# Endpoint & Mocked AI Suggestion Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_api_suggestions_success_mocked(tmp_path: Path):
    """Successfully generate, validate, and return suggestions using mocked Ollama output."""
    file1 = tmp_path / "invoice_draft.pdf"
    file1.write_text("sample invoice")

    file2 = tmp_path / "photo.jpg"
    file2.write_bytes(b"\xff\xd8\xff\xe0\x00\x10JFIF")

    root = roots_registry.approve_root(str(tmp_path), "Test Root")

    mock_batch = OllamaSuggestionBatch(
        suggestions=[
            OllamaFileSuggestion(
                file_id="invoice_draft.pdf",
                current_relative_path="invoice_draft.pdf",
                category="Finance/Invoices",
                proposed_filename="Invoice_2026_Q1.pdf",
                proposed_subfolder="Documents/Invoices",
                rationale="Organized under Finance Invoices with clean naming.",
                confidence=0.92,
            ),
            OllamaFileSuggestion(
                file_id="photo.jpg",
                current_relative_path="photo.jpg",
                category="Media/Images",
                proposed_filename="Vacation_Photo.jpg",
                proposed_subfolder="Images/Vacation",
                rationale="Classified as personal image.",
                confidence=0.88,
            ),
        ]
    )

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (mock_batch, 125.0)

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id, "max_files": 10},
        )

        assert response.status_code == 200
        data = response.json()

        assert "batch_id" in data
        assert "PROPOSAL ONLY" in data["notice"]
        assert data["summary"]["total_files_analyzed"] == 2
        assert data["summary"]["suggestions_generated"] == 2
        assert len(data["suggestions"]) == 2

        sugg1 = next(s for s in data["suggestions"] if s["current_relative_path"] == "invoice_draft.pdf")
        assert sugg1["proposed_filename"] == "Invoice_2026_Q1.pdf"
        assert sugg1["proposed_subfolder"] == "Documents/Invoices"
        assert sugg1["proposed_relative_path"] == "Documents/Invoices/Invoice_2026_Q1.pdf"
        assert sugg1["confidence"] == 0.92
        assert sugg1["is_ambiguous"] is False
        assert sugg1["is_valid"] is True


@pytest.mark.asyncio
async def test_api_suggestions_low_confidence_marked_ambiguous(tmp_path: Path):
    """Suggestions with confidence below threshold are flagged as is_ambiguous=True."""
    f = tmp_path / "random_notes.txt"
    f.write_text("some cryptic text")

    root = roots_registry.approve_root(str(tmp_path), "Test Low Conf")

    mock_batch = OllamaSuggestionBatch(
        suggestions=[
            OllamaFileSuggestion(
                file_id="random_notes.txt",
                current_relative_path="random_notes.txt",
                category="Miscellaneous",
                proposed_filename="Uncertain_Notes.txt",
                proposed_subfolder="Misc",
                rationale="Content purpose is ambiguous.",
                confidence=0.45,  # Below default 0.70 threshold
            )
        ]
    )

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (mock_batch, 90.0)

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id, "confidence_threshold": 0.70},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["summary"]["ambiguous_count"] == 1
        assert data["suggestions"][0]["is_ambiguous"] is True


@pytest.mark.asyncio
async def test_api_suggestions_model_offline_503(tmp_path: Path):
    """When Ollama daemon is unreachable, endpoint gracefully returns 503."""
    f = tmp_path / "data.csv"
    f.write_text("a,b,c")
    root = roots_registry.approve_root(str(tmp_path), "Test Offline")

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = OllamaConnectionError("Connection refused on 127.0.0.1:11434")

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id},
        )

        assert response.status_code == 503
        assert "Local Ollama server is unreachable" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_suggestions_model_missing_404(tmp_path: Path):
    """When Ollama model is not installed, endpoint gracefully returns 404 with command."""
    f = tmp_path / "doc.pdf"
    f.write_text("pdf content")
    root = roots_registry.approve_root(str(tmp_path), "Test Missing Model")

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = OllamaModelNotFoundError("Model 'qwen3-vl:8b' not found")

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id},
        )

        assert response.status_code == 404
        assert "Requested Ollama model is not installed" in response.json()["detail"]


@pytest.mark.asyncio
async def test_api_suggestions_malformed_json_fallback(tmp_path: Path):
    """When Ollama returns malformed JSON, endpoint handles gracefully with fallback and warnings."""
    f = tmp_path / "notes.txt"
    f.write_text("notes")
    root = roots_registry.approve_root(str(tmp_path), "Test Malformed")

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.side_effect = OllamaJsonParseError("Invalid JSON structure")

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id},
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["warnings"]) >= 1
        assert any(w["warning_type"] == "model_error" for w in data["warnings"])
        # File falls back safely to original name/path
        assert data["suggestions"][0]["proposed_filename"] == "notes.txt"
        assert data["suggestions"][0]["is_valid"] is False


@pytest.mark.asyncio
async def test_suggestions_never_mutate_filesystem(tmp_path: Path):
    """Mandatory non-negotiable: files remain 100% unaltered before and after suggestions."""
    target_file = tmp_path / "important_contract.docx"
    test_content = b"ORIGINAL CONTRACT CONTENT DO NOT ALTER"
    target_file.write_bytes(test_content)

    stat_before = target_file.stat()
    root = roots_registry.approve_root(str(tmp_path), "Mutation Check Root")

    mock_batch = OllamaSuggestionBatch(
        suggestions=[
            OllamaFileSuggestion(
                file_id="important_contract.docx",
                current_relative_path="important_contract.docx",
                category="Legal/Contracts",
                proposed_filename="Client_Contract_Signed.docx",
                proposed_subfolder="Legal/Contracts/2026",
                rationale="Organize into contracts archive",
                confidence=0.95,
            )
        ]
    )

    with patch(
        "backend.app.services.suggestions.ollama_service.generate_structured",
        new_callable=AsyncMock,
    ) as mock_gen:
        mock_gen.return_value = (mock_batch, 100.0)

        response = client.post(
            "/api/suggestions",
            json={"root_id": root.id},
        )
        assert response.status_code == 200

    # Verify original file still exists in original location with identical content and timestamps
    assert target_file.exists()
    assert target_file.read_bytes() == test_content
    stat_after = target_file.stat()
    assert stat_before.st_mtime == stat_after.st_mtime
    assert stat_before.st_size == stat_after.st_size

    # Verify proposed destination was NEVER created
    proposed_dest = tmp_path / "Legal" / "Contracts" / "2026" / "Client_Contract_Signed.docx"
    assert not proposed_dest.exists()
