"""Tests for TidyAI secure read-only file scanner and boundary enforcement.

All tests operate exclusively on isolated temporary directories (tmp_path).
"""

import os
import sys
from pathlib import Path
from unittest.mock import patch
import pytest
from fastapi.testclient import TestClient
from backend.app.main import app
from backend.app.schemas import BroadFileType, ScanResponse
from backend.app.services.roots_registry import roots_registry
from backend.app.services.scanner import determine_file_type
from backend.app.services.security import (
    SecurityBoundaryError,
    resolve_and_verify_containment,
    validate_and_canonicalize_root,
)


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


# ==============================================================================
# Security & Boundary Tests
# ==============================================================================

def test_validate_and_canonicalize_valid(tmp_path):
    """Valid directory is canonicalized and resolved."""
    canonical = validate_and_canonicalize_root(str(tmp_path))
    assert canonical == tmp_path.resolve()


def test_validate_and_canonicalize_nonexistent():
    """Non-existent directory fails closed."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        validate_and_canonicalize_root("C:\\nonexistent_test_folder_123456")
    assert "does not exist" in str(exc_info.value)


def test_validate_and_canonicalize_empty():
    """Empty path input is rejected."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        validate_and_canonicalize_root("   ")
    assert "cannot be empty" in str(exc_info.value)


def test_validate_and_canonicalize_unc_escape():
    """UNC network paths are rejected."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        validate_and_canonicalize_root("\\\\remote_server\\shared_folder")
    assert "UNC network paths are not permitted" in str(exc_info.value)


def test_validate_and_canonicalize_drive_root():
    """Filesystem/drive root is rejected."""
    drive = Path(Path.cwd().anchor)
    with pytest.raises(SecurityBoundaryError) as exc_info:
        validate_and_canonicalize_root(str(drive))
    assert "Filesystem or drive roots cannot be registered" in str(exc_info.value)


def test_resolve_and_verify_containment_valid(tmp_path):
    """Subpaths inside approved root resolve properly."""
    sub = tmp_path / "documents" / "2024"
    sub.mkdir(parents=True)
    resolved = resolve_and_verify_containment(tmp_path, "documents/2024")
    assert resolved == sub.resolve()


def test_resolve_and_verify_containment_traversal(tmp_path):
    """Path traversal escaping approved root is rejected."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        resolve_and_verify_containment(tmp_path, "../outside_secret")
    assert "Path traversal detected" in str(exc_info.value)


def test_resolve_and_verify_containment_absolute_escape(tmp_path):
    """Absolute subpath is rejected."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        resolve_and_verify_containment(tmp_path, "C:\\Windows\\System32")
    assert "Absolute paths or drive specifications" in str(exc_info.value)


def test_resolve_and_verify_containment_unc_escape(tmp_path):
    """UNC subpath is rejected."""
    with pytest.raises(SecurityBoundaryError) as exc_info:
        resolve_and_verify_containment(tmp_path, "\\\\evil\\share")
    assert "UNC paths are not permitted" in str(exc_info.value)


# ==============================================================================
# Roots API Endpoints Tests
# ==============================================================================

def test_api_approve_root_success(client, tmp_path):
    """POST /api/roots/approve successfully registers a valid temporary folder."""
    resp = client.post(
        "/api/roots/approve",
        json={"path": str(tmp_path), "label": "Test Temp Root"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["label"] == "Test Temp Root"
    assert data["canonical_path"] == str(tmp_path.resolve())
    assert "id" in data

    # Verify listing
    list_resp = client.get("/api/roots")
    assert list_resp.status_code == 200
    roots = list_resp.json()["roots"]
    assert len(roots) == 1
    assert roots[0]["id"] == data["id"]


def test_api_approve_root_drive_escape_fails(client):
    """POST /api/roots/approve fails closed when attempting to approve drive root."""
    drive = Path(Path.cwd().anchor)
    resp = client.post(
        "/api/roots/approve",
        json={"path": str(drive), "label": "Dangerous Root"},
    )
    assert resp.status_code == 400
    assert "Filesystem or drive roots cannot be registered" in resp.json()["detail"]


def test_api_unregister_root(client, tmp_path):
    """DELETE /api/roots/{root_id} removes registered root."""
    create_resp = client.post(
        "/api/roots/approve",
        json={"path": str(tmp_path), "label": "To Delete"},
    )
    root_id = create_resp.json()["id"]

    del_resp = client.delete(f"/api/roots/{root_id}")
    assert del_resp.status_code == 200

    list_resp = client.get("/api/roots")
    assert len(list_resp.json()["roots"]) == 0


def test_api_unregister_root_not_found(client):
    """DELETE /api/roots/{unknown_id} returns 404."""
    resp = client.delete("/api/roots/nonexistent-id-000")
    assert resp.status_code == 404


# ==============================================================================
# Scanner Tests (Read-Only & Metadata Verification)
# ==============================================================================

def test_determine_file_type():
    """Verify broad category mapping for common extensions."""
    assert determine_file_type(".pdf") == BroadFileType.DOCUMENT
    assert determine_file_type(".csv") == BroadFileType.DOCUMENT
    assert determine_file_type(".png") == BroadFileType.IMAGE
    assert determine_file_type(".mp3") == BroadFileType.AUDIO
    assert determine_file_type(".mp4") == BroadFileType.VIDEO
    assert determine_file_type(".zip") == BroadFileType.ARCHIVE
    assert determine_file_type(".py") == BroadFileType.CODE
    assert determine_file_type(".unknown_ext") == BroadFileType.OTHER


def test_scan_metadata_inventory(client, tmp_path):
    """Scan reads metadata only and populates inventory accurately."""
    # Create synthetic structure
    doc_dir = tmp_path / "docs"
    img_dir = tmp_path / "photos"
    doc_dir.mkdir()
    img_dir.mkdir()

    f1 = doc_dir / "invoice.pdf"
    f1.write_text("dummy invoice content", encoding="utf-8")

    f2 = img_dir / "vacation.jpg"
    f2.write_bytes(b"\xff\xd8\xff\xe0" + b"\x00" * 50)

    f3 = tmp_path / "notes.txt"
    f3.write_text("harmless notes", encoding="utf-8")

    # Approve root
    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    # Run scan
    scan_resp = client.post(
        "/api/scan",
        json={"root_id": root_id, "recursive": True},
    )
    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())

    assert res.summary.total_files == 3
    assert res.summary.total_size_bytes == f1.stat().st_size + f2.stat().st_size + f3.stat().st_size
    assert res.summary.truncated is False
    assert len(res.warnings) == 0

    rel_paths = {f.relative_path for f in res.files}
    assert "docs/invoice.pdf" in rel_paths
    assert "photos/vacation.jpg" in rel_paths
    assert "notes.txt" in rel_paths

    # Verify type classification
    type_map = {f.relative_path: f.file_type for f in res.files}
    assert type_map["docs/invoice.pdf"] == BroadFileType.DOCUMENT
    assert type_map["photos/vacation.jpg"] == BroadFileType.IMAGE
    assert type_map["notes.txt"] == BroadFileType.DOCUMENT


def test_scan_ignores_system_caches_and_git(client, tmp_path):
    """Ignored directories (.git, node_modules, __pycache__) and files (Thumbs.db) are skipped."""
    git_dir = tmp_path / ".git"
    git_dir.mkdir()
    (git_dir / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")

    pycache_dir = tmp_path / "__pycache__"
    pycache_dir.mkdir()
    (pycache_dir / "module.cpython-314.pyc").write_bytes(b"\x00\x01\x02")

    (tmp_path / "Thumbs.db").write_bytes(b"dummy thumbs cache")

    valid_file = tmp_path / "valid.txt"
    valid_file.write_text("keep me", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    scan_resp = client.post("/api/scan", json={"root_id": root_id})
    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())

    assert res.summary.total_files == 1
    assert res.files[0].relative_path == "valid.txt"
    assert res.summary.skipped_count >= 3


def test_scan_traversal_subpath_fails(client, tmp_path):
    """Subpath attempting traversal is rejected with 400."""
    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    scan_resp = client.post(
        "/api/scan",
        json={"root_id": root_id, "subpath": "../escape"},
    )
    assert scan_resp.status_code == 400
    assert "Path traversal detected" in scan_resp.json()["detail"]


def test_scan_bounded_max_files(client, tmp_path):
    """Scan respects max_files bound and flags truncated=True."""
    for i in range(15):
        (tmp_path / f"file_{i:02d}.txt").write_text(f"content {i}", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    scan_resp = client.post(
        "/api/scan",
        json={"root_id": root_id, "max_files": 5},
    )
    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())
    assert len(res.files) == 5
    assert res.summary.truncated is True


def test_scan_bounded_max_depth(client, tmp_path):
    """Scan respects max_depth limit."""
    # Create 4 levels deep: a/b/c/deep.txt
    deep_dir = tmp_path / "l1" / "l2" / "l3"
    deep_dir.mkdir(parents=True)
    (deep_dir / "deep.txt").write_text("nested deep", encoding="utf-8")
    (tmp_path / "shallow.txt").write_text("shallow", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    # max_depth=1 should only visit root and l1, not l2 or l3
    scan_resp = client.post(
        "/api/scan",
        json={"root_id": root_id, "max_depth": 1},
    )
    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())
    rel_paths = [f.relative_path for f in res.files]
    assert "shallow.txt" in rel_paths
    assert "l1/l2/l3/deep.txt" not in rel_paths


def test_scan_symlink_escape_skipped_with_warning(client, tmp_path):
    """Symlink escaping approved root is skipped and reported as warning."""
    outside_dir = tmp_path.parent / "outside_sandbox_123"
    outside_dir.mkdir(exist_ok=True)
    secret_file = outside_dir / "secret.txt"
    secret_file.write_text("secret outside", encoding="utf-8")

    symlink_path = tmp_path / "escaped_link.txt"
    try:
        symlink_path.symlink_to(secret_file)
    except (OSError, NotImplementedError):
        # On Windows, creating symlinks may require Developer Mode or elevated privileges
        pytest.skip("Symlink creation requires elevated privileges on this system.")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    scan_resp = client.post("/api/scan", json={"root_id": root_id})
    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())

    # Escaped file must NOT be in files
    assert not any("secret" in f.filename for f in res.files)
    # Warning must be recorded
    assert any(w.warning_type == "symlink_escape" for w in res.warnings)


def test_scan_disappearing_file_warning(client, tmp_path):
    """File disappearing between scandir and stat generates structured warning."""
    test_f = tmp_path / "ephemeral.txt"
    test_f.write_text("hello", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    # Patch os.DirEntry.stat to simulate FileNotFoundError on ephemeral.txt
    real_stat = os.DirEntry.stat

    def mock_stat(self, *args, **kwargs):
        if "ephemeral" in self.name:
            raise FileNotFoundError("Simulated disappearing file")
        return real_stat(self, *args, **kwargs)

    with patch.object(os.DirEntry, "stat", mock_stat):
        scan_resp = client.post("/api/scan", json={"root_id": root_id})

    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())
    assert len(res.files) == 0
    assert any(w.warning_type == "file_not_found" for w in res.warnings)


def test_scan_symlink_escape_mock(client, tmp_path):
    """Verify symlink escaping root is detected and logged as warning when escaping root."""
    dummy = tmp_path / "symlink_file.txt"
    dummy.write_text("test", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    with patch("backend.app.services.scanner.is_safe_child", return_value=False), \
         patch.object(os.DirEntry, "is_symlink", return_value=True):
        scan_resp = client.post("/api/scan", json={"root_id": root_id})

    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())
    assert len(res.files) == 0
    assert any(w.warning_type == "symlink_escape" for w in res.warnings)


def test_scan_permission_error_warning(client, tmp_path):
    """Verify permission denied during stat produces permission_denied warning."""
    test_f = tmp_path / "restricted.txt"
    test_f.write_text("secret", encoding="utf-8")

    app_resp = client.post("/api/roots/approve", json={"path": str(tmp_path)})
    root_id = app_resp.json()["id"]

    real_stat = os.DirEntry.stat

    def mock_stat_permission(self, *args, **kwargs):
        if "restricted" in self.name:
            raise PermissionError("Access denied to file")
        return real_stat(self, *args, **kwargs)

    with patch.object(os.DirEntry, "stat", mock_stat_permission):
        scan_resp = client.post("/api/scan", json={"root_id": root_id})

    assert scan_resp.status_code == 200
    res = ScanResponse(**scan_resp.json())
    assert len(res.files) == 0
    assert any(w.warning_type == "permission_denied" for w in res.warnings)
