"""Tests for Rule-Based File Classification Engine and Model Configuration (Increment 1).

Validates deterministic Python classification rules:
- Extension taxonomy (Documents, Spreadsheets, Presentations, Images, Videos, Audio, Archives, Code, Datasets)
- Disambiguation of CSV/TSV via filename patterns
- Security anomaly detection (double extensions like .pdf.exe)
- Temporary lock file filtering
- Known extensionless files (Dockerfile, Makefile, README)
- Standard library MIME type fallback
- API endpoints /api/classify and /api/v1/classify
- Model configuration defaults to qwen3:4b
- Zero mutation verification
"""

from pathlib import Path
from fastapi.testclient import TestClient

from backend.app.config import settings
from backend.app.main import app
from backend.app.schemas import (
    ClassificationSource,
    FileCategory,
)
from backend.app.services.classifier import (
    classify_file,
    classify_files_batch,
)
from backend.app.services.roots_registry import roots_registry

client = TestClient(app)


# ==============================================================================
# Unit Tests: Extension Taxonomy
# ==============================================================================

def test_classify_documents_by_extension():
    """Document extensions map deterministically to Documents category."""
    for filename in ["report.pdf", "contract.docx", "notes.txt", "guide.md", "paper.odt"]:
        item = classify_file(filename)
        assert item.category == FileCategory.DOCUMENTS
        assert item.source in (ClassificationSource.EXTENSION_RULE, ClassificationSource.FILENAME_RULE)
        assert item.is_ambiguous is False


def test_classify_spreadsheets_by_extension():
    """Spreadsheet extensions map to Spreadsheets category."""
    for filename in ["sales.xlsx", "budget.xls", "expenses.ods", "tracker.numbers"]:
        item = classify_file(filename)
        assert item.category == FileCategory.SPREADSHEETS
        assert item.is_ambiguous is False


def test_classify_presentations_by_extension():
    """Presentation extensions map to Presentations category."""
    for filename in ["pitch.pptx", "slides.ppt", "talk.odp", "deck.key"]:
        item = classify_file(filename)
        assert item.category == FileCategory.PRESENTATIONS
        assert item.is_ambiguous is False


def test_classify_images_by_extension():
    """Image extensions map to Images category."""
    for filename in ["photo.png", "logo.svg", "banner.jpg", "graphic.webp", "anim.gif"]:
        item = classify_file(filename)
        assert item.category == FileCategory.IMAGES
        assert item.is_ambiguous is False


def test_classify_videos_and_audio():
    """Video and audio extensions map to respective categories."""
    for filename in ["clip.mp4", "movie.mkv", "recording.mov", "video.webm"]:
        item = classify_file(filename)
        assert item.category == FileCategory.VIDEOS
        assert item.is_ambiguous is False

    for filename in ["track.mp3", "audio.flac", "podcast.wav", "song.m4a"]:
        item = classify_file(filename)
        assert item.category == FileCategory.AUDIO
        assert item.is_ambiguous is False


def test_classify_archives_and_code():
    """Archive and code extensions map to respective categories."""
    for filename in ["bundle.zip", "data.tar.gz", "archive.7z", "package.rar"]:
        item = classify_file(filename)
        assert item.category == FileCategory.ARCHIVES
        assert item.is_ambiguous is False

    for filename in ["script.py", "app.ts", "component.tsx", "main.rs", "server.go", "style.css"]:
        item = classify_file(filename)
        assert item.category == FileCategory.CODE
        assert item.is_ambiguous is False


def test_classify_datasets():
    """Data container extensions map to Datasets."""
    for filename in ["analytics.parquet", "feed.arrow", "model_weights.hdf5", "records.sqlite3"]:
        item = classify_file(filename)
        assert item.category == FileCategory.DATASETS
        assert item.is_ambiguous is False


# ==============================================================================
# Unit Tests: Filename Disambiguation & Pattern Rules
# ==============================================================================

def test_classify_csv_tsv_disambiguation():
    """CSV/TSV files with dataset keywords map to Datasets; otherwise Spreadsheets."""
    dataset_item = classify_file("telemetry_data_train.csv")
    assert dataset_item.category == FileCategory.DATASETS
    assert dataset_item.source == ClassificationSource.FILENAME_RULE

    spreadsheet_item = classify_file("quarterly_payroll.csv")
    assert spreadsheet_item.category == FileCategory.SPREADSHEETS
    assert spreadsheet_item.source == ClassificationSource.EXTENSION_RULE


def test_classify_filename_patterns():
    """Filename patterns (invoices, screenshots) generate descriptive subfolders."""
    invoice_item = classify_file("Invoice_2026_Q1.pdf")
    assert invoice_item.category == FileCategory.DOCUMENTS
    assert invoice_item.suggested_subfolder == "Documents/Invoices"
    assert invoice_item.source == ClassificationSource.FILENAME_RULE

    screenshot_item = classify_file("Screenshot_2026-02-14.png")
    assert screenshot_item.category == FileCategory.IMAGES
    assert screenshot_item.suggested_subfolder == "Images/Screenshots"
    assert screenshot_item.source == ClassificationSource.FILENAME_RULE


def test_classify_exact_extensionless_names():
    """Known extensionless files are classified without error."""
    assert classify_file("Dockerfile").category == FileCategory.CODE
    assert classify_file("Makefile").category == FileCategory.CODE
    assert classify_file("README").category == FileCategory.DOCUMENTS
    assert classify_file("LICENSE").category == FileCategory.DOCUMENTS


def test_classify_double_extension_security_flag():
    """Double extension attack patterns (e.g. .pdf.exe) fail closed into Needs review."""
    item = classify_file("Urgent_Document.pdf.exe")
    assert item.category == FileCategory.NEEDS_REVIEW
    assert item.is_ambiguous is True
    assert "double file extension" in item.reason.lower()


def test_classify_temporary_and_lock_files():
    """Temporary and partial download files are flagged for review."""
    item1 = classify_file("~$contract_draft.docx")
    assert item1.category == FileCategory.NEEDS_REVIEW
    assert item1.is_ambiguous is True

    item2 = classify_file("large_archive.zip.crdownload")
    assert item2.category == FileCategory.NEEDS_REVIEW
    assert item2.is_ambiguous is True


def test_classify_unknown_extension_fallback():
    """Completely unknown extension falls back to Needs review with ambiguity flag."""
    item = classify_file("mystery_blob.xyz8910")
    assert item.category == FileCategory.NEEDS_REVIEW
    assert item.is_ambiguous is True


# ==============================================================================
# Endpoint & Configuration Tests
# ==============================================================================

def test_default_model_configured_as_qwen3_4b():
    """Verify that settings default to qwen3:4b as specified in requirements."""
    assert settings.ollama_model == "qwen3:4b"


def test_api_v1_health_and_ai_health():
    """Check /api/v1/health and /api/v1/ai/health compatibility routes."""
    res_health = client.get("/api/v1/health")
    assert res_health.status_code == 200
    assert res_health.json()["ollama_model"] == "qwen3:4b"

    res_ai = client.get("/api/v1/ai/health")
    assert res_ai.status_code == 200
    assert "state" in res_ai.json()


def test_api_classify_endpoints(tmp_path: Path):
    """Test POST /api/classify and POST /api/v1/classify endpoints."""
    # Create test synthetic files
    (tmp_path / "budget_2026.xlsx").write_text("dummy")
    (tmp_path / "invoice_march.pdf").write_text("dummy")
    (tmp_path / "unknown_binary.xyz").write_text("dummy")

    root = roots_registry.approve_root(str(tmp_path), "Classifier Test Root")

    # Test /api/classify
    res = client.post("/api/classify", json={"root_id": root.id})
    assert res.status_code == 200
    data = res.json()

    assert data["summary"]["total_files"] == 3
    assert data["summary"]["classified_by_rules"] == 3
    assert data["summary"]["needs_review_count"] >= 1
    assert "READ ONLY" in data["notice"]

    # Verify categories present
    cats = {c["filename"]: c["category"] for c in data["classifications"]}
    assert cats["budget_2026.xlsx"] == "Spreadsheets"
    assert cats["invoice_march.pdf"] == "Documents"
    assert cats["unknown_binary.xyz"] == "Needs review"

    # Test /api/v1/classify alias
    res_v1 = client.post("/api/v1/classify", json={"root_id": root.id})
    assert res_v1.status_code == 200
    assert len(res_v1.json()["classifications"]) == 3


def test_zero_filesystem_mutations_during_classification(tmp_path: Path):
    """Mandatory verification: classification never moves, renames, or touches files."""
    f = tmp_path / "untouched_file.docx"
    f.write_text("original content")
    stat_before = f.stat()

    root = roots_registry.approve_root(str(tmp_path), "Zero Mutation Root")
    res = client.post("/api/classify", json={"root_id": root.id})
    assert res.status_code == 200

    assert f.exists()
    assert f.read_text() == "original content"
    stat_after = f.stat()
    assert stat_before.st_mtime == stat_after.st_mtime
    assert stat_before.st_size == stat_after.st_size
