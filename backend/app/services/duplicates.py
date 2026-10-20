"""Exact duplicate detection service for TidyAI using chunked SHA-256 hashing.

Detects identical files under approved roots without loading entire files into memory.
Performs read-only detection only — NEVER modifies, renames, moves, or deletes files.
"""

import hashlib
import time
import uuid
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from backend.app.schemas import (
    ApprovedRoot,
    DuplicateDetectionResponse,
    DuplicateFileEntry,
    DuplicateGroup,
    DuplicateSummary,
    DuplicateWarning,
)
from backend.app.services.scanner import scan_approved_root
from backend.app.services.security import resolve_and_verify_containment


class FileHashingError(Exception):
    """Raised when an issue occurs during file content hashing."""

    def __init__(self, warning_type: str, message: str):
        super().__init__(message)
        self.warning_type = warning_type
        self.message = message


def compute_chunked_sha256(
    file_path: Path,
    expected_size: int,
    chunk_size: int = 65536,
) -> str:
    """Stream file in chunks and compute its SHA-256 digest.

    Ensures large files do not exhaust system memory and detects if a file
    changes during the read operation.
    """
    hasher = hashlib.sha256()
    bytes_read = 0

    try:
        initial_stat = file_path.stat()
        initial_mtime = initial_stat.st_mtime
    except FileNotFoundError:
        raise FileHashingError("file_not_found", "File disappeared before hashing started.")
    except PermissionError as p_err:
        raise FileHashingError("permission_denied", f"Permission denied accessing file: {p_err}")
    except OSError as os_err:
        raise FileHashingError("os_error", f"OS error accessing file: {os_err}")

    try:
        with open(file_path, "rb") as f:
            while True:
                chunk = f.read(chunk_size)
                if not chunk:
                    break
                hasher.update(chunk)
                bytes_read += len(chunk)

        # Re-check that file did not change during read
        current_stat = file_path.stat()
        if current_stat.st_size != expected_size or current_stat.st_mtime != initial_mtime:
            raise FileHashingError(
                "file_modified_during_hash",
                f"File content was modified while hashing: expected {expected_size} bytes, read {bytes_read} bytes.",
            )

    except FileNotFoundError:
        raise FileHashingError("file_not_found", "File disappeared while hashing.")
    except PermissionError as p_err:
        raise FileHashingError("permission_denied", f"Permission denied reading file: {p_err}")
    except OSError as os_err:
        if isinstance(os_err, FileHashingError):
            raise
        raise FileHashingError("os_error", f"I/O error during chunked hashing: {os_err}")

    return hasher.hexdigest()


def detect_duplicates(
    root: ApprovedRoot,
    subpath: str = "",
    min_size_bytes: int = 0,
    chunk_size: int = 65536,
) -> DuplicateDetectionResponse:
    """Detect exact content duplicates under an approved root via chunked SHA-256.

    Optimization Pipeline:
    1. Scan directory metadata to get candidate inventory.
    2. Group files by exact byte size. Only size buckets with >= 2 files are hashed.
    3. Stream chunked SHA-256 hashing on candidate files only.
    4. Group matches by SHA-256 hash.
    5. Return read-only report with potential space savings.
    """
    start_time = time.perf_counter()
    root_path = Path(root.canonical_path).resolve()

    # Verify subpath containment
    resolve_and_verify_containment(root_path, subpath)

    # 1. Inventory scan
    scan_res = scan_approved_root(root=root, subpath=subpath, recursive=True)
    all_files = scan_res.files

    # Filter files by min_size_bytes
    eligible_files = [f for f in all_files if f.size_bytes >= min_size_bytes]

    # 2. Size bucketing: Group eligible files by exact file size
    size_buckets: Dict[int, List] = defaultdict(list)
    for f in eligible_files:
        size_buckets[f.size_bytes].append(f)

    # Keep only buckets with >= 2 files
    candidate_buckets = {size: flist for size, flist in size_buckets.items() if len(flist) >= 2}

    candidate_files_count = sum(len(flist) for flist in candidate_buckets.values())

    warnings: List[DuplicateWarning] = []
    # Propagate any warnings encountered during the initial inventory scan
    for w in scan_res.warnings:
        warnings.append(
            DuplicateWarning(
                path=w.path,
                warning_type=w.warning_type,
                message=w.message,
            )
        )

    # 3. Hash candidate files and group by SHA-256
    # hash -> list of DuplicateFileEntry
    hash_groups: Dict[Tuple[str, int], List[DuplicateFileEntry]] = defaultdict(list)

    for size, file_list in candidate_buckets.items():
        for file_entry in file_list:
            full_path = root_path / file_entry.relative_path

            try:
                file_hash = compute_chunked_sha256(
                    file_path=full_path,
                    expected_size=size,
                    chunk_size=chunk_size,
                )
                hash_groups[(file_hash, size)].append(
                    DuplicateFileEntry(
                        relative_path=file_entry.relative_path,
                        filename=file_entry.filename,
                        extension=file_entry.extension,
                        size_bytes=file_entry.size_bytes,
                        modified_at=file_entry.modified_at,
                    )
                )
            except FileHashingError as err:
                warnings.append(
                    DuplicateWarning(
                        path=file_entry.relative_path,
                        warning_type=err.warning_type,
                        message=err.message,
                    )
                )

    # 4. Form Duplicate Groups (only where >= 2 files share exact SHA-256)
    duplicate_groups: List[DuplicateGroup] = []
    total_duplicate_files = 0
    total_potential_savings = 0

    for (sha256_hash, size), matched_files in hash_groups.items():
        if len(matched_files) >= 2:
            count = len(matched_files)
            savings = (count - 1) * size
            total_duplicate_files += count
            total_potential_savings += savings

            # Sort matched files by relative path for deterministic reporting
            matched_files.sort(key=lambda x: x.relative_path)

            duplicate_groups.append(
                DuplicateGroup(
                    sha256=sha256_hash,
                    size_bytes=size,
                    file_count=count,
                    potential_savings_bytes=savings,
                    files=matched_files,
                )
            )

    # Sort groups by potential savings descending, then by file count descending
    duplicate_groups.sort(key=lambda g: (g.potential_savings_bytes, g.file_count), reverse=True)

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    summary = DuplicateSummary(
        root_id=root.id,
        root_path=root.canonical_path,
        total_files_evaluated=len(all_files),
        candidate_files_hashed=candidate_files_count,
        duplicate_groups_count=len(duplicate_groups),
        duplicate_files_count=total_duplicate_files,
        potential_savings_bytes=total_potential_savings,
        duration_ms=round(elapsed_ms, 2),
    )

    return DuplicateDetectionResponse(
        detection_id=str(uuid.uuid4()),
        notice="DETECTION ONLY: No files have been deleted, moved, or altered.",
        summary=summary,
        groups=duplicate_groups,
        warnings=warnings,
    )
