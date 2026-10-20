"""Tests for TidyAI exact duplicate detection using chunked SHA-256 hashing.

All tests operate exclusively on isolated temporary directories (tmp_path).
Verifies read-only behavior: files are never modified, renamed, moved, or deleted.
"""

import hashlib
import os
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas import DuplicateDetectionResponse
from backend.app.services.duplicates import compute_chunked_sha256, FileHashingError
from backend.app.services.roots_registry import roots_registry


@pytest.fixture(autouse=True)
def clean_roots():
    """Ensure roots registry is clean before and after each test."""
    roots_registry.clear_all()
    yield
    roots_registry.clear_all()


@pytest.fixture
def client():
    """TestClient fixture with app lifecycle managed."""
    with TestClient(app) as test_client:
        yield test_client


def test_identical_content_different_names(client, tmp_path):
    """Files with different names but identical content are grouped as exact duplicates."""
    content = b"The exact same payload content for testing duplicates."
    expected_hash = hashlib.sha256(content).hexdigest()

    (tmp_path / "original.txt").write_bytes(content)
    (tmp_path / "copy_with_different_name.pdf").write_bytes(content)
    (tmp_path / "third_copy.dat").write_bytes(content)
    (tmp_path / "unrelated.txt").write_bytes(b"Different content completely.")

    # Approve root
    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post("/api/duplicates", json={"root_id": root_id})
    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())

    assert data.notice == "DETECTION ONLY: No files have been deleted, moved, or altered."
    assert data.summary.duplicate_groups_count == 1
    assert data.summary.duplicate_files_count == 3
    assert data.summary.total_files_evaluated == 4
    assert data.summary.potential_savings_bytes == len(content) * 2

    group = data.groups[0]
    assert group.sha256 == expected_hash
    assert group.size_bytes == len(content)
    assert group.file_count == 3
    assert len(group.files) == 3

    rel_names = {f.filename for f in group.files}
    assert rel_names == {"original.txt", "copy_with_different_name.pdf", "third_copy.dat"}


def test_same_name_different_content(client, tmp_path):
    """Files with identical names in different subfolders but different content are NOT duplicates."""
    sub1 = tmp_path / "sub1"
    sub2 = tmp_path / "sub2"
    sub1.mkdir()
    sub2.mkdir()

    (sub1 / "report.pdf").write_bytes(b"First quarterly report data")
    (sub2 / "report.pdf").write_bytes(b"Second quarterly report with differing data")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post("/api/duplicates", json={"root_id": root_id})
    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())

    # Should have 0 duplicate groups
    assert data.summary.duplicate_groups_count == 0
    assert len(data.groups) == 0


def test_same_size_different_content(client, tmp_path):
    """Files with exact same byte size but different content are NOT duplicates."""
    # Both are 16 bytes
    (tmp_path / "alpha.bin").write_bytes(b"AAAAAAAAAAAAAAAA")
    (tmp_path / "bravo.bin").write_bytes(b"BBBBBBBBBBBBBBBB")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post("/api/duplicates", json={"root_id": root_id})
    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())

    assert data.summary.candidate_files_hashed == 2
    assert data.summary.duplicate_groups_count == 0
    assert len(data.groups) == 0


def test_empty_files_duplicates(client, tmp_path):
    """Multiple 0-byte files form an exact duplicate group with empty SHA-256."""
    (tmp_path / "empty1.txt").write_bytes(b"")
    (tmp_path / "empty2.txt").write_bytes(b"")

    empty_sha = hashlib.sha256(b"").hexdigest()

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post("/api/duplicates", json={"root_id": root_id, "min_size_bytes": 0})
    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())

    assert data.summary.duplicate_groups_count == 1
    group = data.groups[0]
    assert group.sha256 == empty_sha
    assert group.size_bytes == 0
    assert group.potential_savings_bytes == 0


def test_chunked_hashing_large_file(tmp_path):
    """Files exceeding chunk size (e.g. 150 KB) hash correctly in chunks."""
    large_payload = b"X" * (150 * 1024)
    file_p = tmp_path / "large.dat"
    file_p.write_bytes(large_payload)

    expected = hashlib.sha256(large_payload).hexdigest()
    # Compute with small 32KB chunks
    computed = compute_chunked_sha256(file_p, expected_size=len(large_payload), chunk_size=32768)
    assert computed == expected


def test_duplicate_read_failure_warning(client, tmp_path):
    """Permission failure on a candidate file is reported as a structured warning without crashing."""
    content = b"Candidate duplicate content"
    (tmp_path / "file1.txt").write_bytes(content)
    (tmp_path / "file2.txt").write_bytes(content)

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    # Mock compute_chunked_sha256 to raise FileHashingError for file2
    original_compute = compute_chunked_sha256

    def mock_compute(file_path, expected_size, chunk_size=65536):
        if "file2" in str(file_path):
            raise FileHashingError("permission_denied", "Simulated permission error")
        return original_compute(file_path, expected_size, chunk_size)

    with patch("backend.app.services.duplicates.compute_chunked_sha256", side_effect=mock_compute):
        resp = client.post("/api/duplicates", json={"root_id": root_id})

    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())
    assert any(w.warning_type == "permission_denied" for w in data.warnings)


def test_duplicate_file_modified_during_hash_warning(client, tmp_path):
    """File modified or truncated during hashing generates file_modified_during_hash warning."""
    content = b"Candidate content"
    (tmp_path / "file1.txt").write_bytes(content)
    (tmp_path / "file2.txt").write_bytes(content)

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    def mock_compute(file_path, expected_size, chunk_size=65536):
        if "file2" in str(file_path):
            raise FileHashingError("file_modified_during_hash", "File changed during read")
        return hashlib.sha256(content).hexdigest()

    with patch("backend.app.services.duplicates.compute_chunked_sha256", side_effect=mock_compute):
        resp = client.post("/api/duplicates", json={"root_id": root_id})

    assert resp.status_code == 200
    data = DuplicateDetectionResponse(**resp.json())
    assert any(w.warning_type == "file_modified_during_hash" for w in data.warnings)


def test_duplicate_detection_path_traversal_fails(client, tmp_path):
    """Subpath attempting traversal is rejected with 400."""
    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post(
        "/api/duplicates",
        json={"root_id": root_id, "subpath": "../escape"},
    )
    assert resp.status_code == 400
    assert "Path traversal detected" in resp.json()["detail"]


def test_duplicate_detection_unregistered_root_404(client):
    """Unregistered root ID returns 404."""
    resp = client.post("/api/duplicates", json={"root_id": "nonexistent-id-999"})
    assert resp.status_code == 404


def test_zero_mutations_during_duplicate_detection(client, tmp_path):
    """Verify that duplicate detection performs ZERO filesystem mutations."""
    content = b"Zero mutation verification payload"
    f1 = tmp_path / "doc1.txt"
    f2 = tmp_path / "doc2.txt"
    f1.write_bytes(content)
    f2.write_bytes(content)

    # Record directory state before
    entries_before = {p.name: (p.stat().st_size, p.stat().st_mtime) for p in tmp_path.iterdir()}

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    resp = client.post("/api/duplicates", json={"root_id": root_id})
    assert resp.status_code == 200

    # Verify directory state after is 100% identical
    entries_after = {p.name: (p.stat().st_size, p.stat().st_mtime) for p in tmp_path.iterdir()}
    assert entries_before == entries_after
