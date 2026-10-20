"""Secure read-only file scanner for TidyAI.

Performs metadata-only scanning under approved roots with strict boundary
enforcement, depth/file bounds, and structured warning reporting.
Never mutates the filesystem or reads file contents.
"""

import os
import time
import uuid
from collections import deque
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Tuple
from backend.app.schemas import (
    ApprovedRoot,
    BroadFileType,
    FileEntry,
    ScanResponse,
    ScanSummary,
    ScanWarning,
)
from backend.app.services.security import (
    DEFAULT_IGNORED_FILES,
    DEFAULT_IGNORED_NAMES,
    is_safe_child,
    resolve_and_verify_containment,
)

# File extension mappings to BroadFileType
EXTENSION_CATEGORIES = {
    # Documents
    ".pdf": BroadFileType.DOCUMENT,
    ".docx": BroadFileType.DOCUMENT,
    ".doc": BroadFileType.DOCUMENT,
    ".txt": BroadFileType.DOCUMENT,
    ".rtf": BroadFileType.DOCUMENT,
    ".odt": BroadFileType.DOCUMENT,
    ".csv": BroadFileType.DOCUMENT,
    ".tsv": BroadFileType.DOCUMENT,
    ".xlsx": BroadFileType.DOCUMENT,
    ".xls": BroadFileType.DOCUMENT,
    ".pptx": BroadFileType.DOCUMENT,
    ".ppt": BroadFileType.DOCUMENT,
    ".md": BroadFileType.DOCUMENT,
    ".epub": BroadFileType.DOCUMENT,
    ".tex": BroadFileType.DOCUMENT,
    # Images
    ".jpg": BroadFileType.IMAGE,
    ".jpeg": BroadFileType.IMAGE,
    ".png": BroadFileType.IMAGE,
    ".gif": BroadFileType.IMAGE,
    ".bmp": BroadFileType.IMAGE,
    ".svg": BroadFileType.IMAGE,
    ".webp": BroadFileType.IMAGE,
    ".tiff": BroadFileType.IMAGE,
    ".tif": BroadFileType.IMAGE,
    ".ico": BroadFileType.IMAGE,
    ".heic": BroadFileType.IMAGE,
    ".raw": BroadFileType.IMAGE,
    # Audio
    ".mp3": BroadFileType.AUDIO,
    ".wav": BroadFileType.AUDIO,
    ".aac": BroadFileType.AUDIO,
    ".flac": BroadFileType.AUDIO,
    ".ogg": BroadFileType.AUDIO,
    ".m4a": BroadFileType.AUDIO,
    ".wma": BroadFileType.AUDIO,
    # Video
    ".mp4": BroadFileType.VIDEO,
    ".mkv": BroadFileType.VIDEO,
    ".avi": BroadFileType.VIDEO,
    ".mov": BroadFileType.VIDEO,
    ".wmv": BroadFileType.VIDEO,
    ".webm": BroadFileType.VIDEO,
    ".flv": BroadFileType.VIDEO,
    # Archives
    ".zip": BroadFileType.ARCHIVE,
    ".tar": BroadFileType.ARCHIVE,
    ".gz": BroadFileType.ARCHIVE,
    ".bz2": BroadFileType.ARCHIVE,
    ".xz": BroadFileType.ARCHIVE,
    ".7z": BroadFileType.ARCHIVE,
    ".rar": BroadFileType.ARCHIVE,
    ".iso": BroadFileType.ARCHIVE,
    # Code
    ".py": BroadFileType.CODE,
    ".js": BroadFileType.CODE,
    ".ts": BroadFileType.CODE,
    ".tsx": BroadFileType.CODE,
    ".jsx": BroadFileType.CODE,
    ".html": BroadFileType.CODE,
    ".htm": BroadFileType.CODE,
    ".css": BroadFileType.CODE,
    ".json": BroadFileType.CODE,
    ".yaml": BroadFileType.CODE,
    ".yml": BroadFileType.CODE,
    ".sh": BroadFileType.CODE,
    ".ps1": BroadFileType.CODE,
    ".bat": BroadFileType.CODE,
    ".cmd": BroadFileType.CODE,
    ".c": BroadFileType.CODE,
    ".cpp": BroadFileType.CODE,
    ".h": BroadFileType.CODE,
    ".hpp": BroadFileType.CODE,
    ".rs": BroadFileType.CODE,
    ".go": BroadFileType.CODE,
    ".java": BroadFileType.CODE,
    ".sql": BroadFileType.CODE,
    ".xml": BroadFileType.CODE,
    ".toml": BroadFileType.CODE,
    ".ini": BroadFileType.CODE,
}


def determine_file_type(extension: str) -> BroadFileType:
    """Classify a file extension into a broad category."""
    norm_ext = extension.strip().lower()
    return EXTENSION_CATEGORIES.get(norm_ext, BroadFileType.OTHER)


def scan_approved_root(
    root: ApprovedRoot,
    subpath: str = "",
    recursive: bool = True,
    max_files: int = 10000,
    max_depth: int = 20,
) -> ScanResponse:
    """Perform a read-only metadata scan of an approved root directory."""
    start_time = time.perf_counter()
    root_path = Path(root.canonical_path).resolve()

    # Verify and resolve subpath within approved root boundary
    start_dir = resolve_and_verify_containment(root_path, subpath)

    files: List[FileEntry] = []
    warnings: List[ScanWarning] = []
    directories_scanned = 0
    skipped_count = 0
    total_size_bytes = 0
    truncated = False

    # BFS queue holding tuples of (directory_path, current_depth)
    queue: deque[Tuple[Path, int]] = deque([(start_dir, 0)])

    while queue and not truncated:
        current_dir, current_depth = queue.popleft()
        directories_scanned += 1

        try:
            with os.scandir(current_dir) as entries:
                for entry in entries:
                    if truncated:
                        break

                    name = entry.name

                    # 1. Check ignored directory names
                    try:
                        is_dir = entry.is_dir(follow_symlinks=False)
                        is_sym = entry.is_symlink()
                    except OSError as exc:
                        warnings.append(
                            ScanWarning(
                                path=entry.path,
                                warning_type="os_error",
                                message=f"Failed to inspect entry: {str(exc)}",
                            )
                        )
                        skipped_count += 1
                        continue

                    # Directory processing
                    if is_dir:
                        if name in DEFAULT_IGNORED_NAMES:
                            skipped_count += 1
                            continue

                        # Check symlink directory escape
                        if is_sym:
                            if not is_safe_child(Path(entry.path), root_path):
                                warnings.append(
                                    ScanWarning(
                                        path=entry.path,
                                        warning_type="symlink_escape",
                                        message="Symlink directory points outside approved root; skipping descent.",
                                    )
                                )
                                skipped_count += 1
                                continue

                        if recursive and current_depth < max_depth:
                            queue.append((Path(entry.path), current_depth + 1))
                        continue

                    # 2. File processing
                    try:
                        is_file = entry.is_file(follow_symlinks=False)
                    except OSError:
                        is_file = False

                    if is_file or is_sym:
                        if name in DEFAULT_IGNORED_FILES:
                            skipped_count += 1
                            continue

                        # Check symlink file escape
                        if is_sym:
                            if not is_safe_child(Path(entry.path), root_path):
                                warnings.append(
                                    ScanWarning(
                                        path=entry.path,
                                        warning_type="symlink_escape",
                                        message="Symlink file points outside approved root.",
                                    )
                                )
                                skipped_count += 1
                                continue

                        # Read metadata
                        try:
                            stat_res = entry.stat(follow_symlinks=False)
                        except FileNotFoundError:
                            # File disappeared between directory scan and stat
                            warnings.append(
                                ScanWarning(
                                    path=entry.path,
                                    warning_type="file_not_found",
                                    message="File was removed or disappeared during scan.",
                                )
                            )
                            skipped_count += 1
                            continue
                        except PermissionError as p_err:
                            warnings.append(
                                ScanWarning(
                                    path=entry.path,
                                    warning_type="permission_denied",
                                    message=f"Access denied: {str(p_err)}",
                                )
                            )
                            skipped_count += 1
                            continue
                        except OSError as os_err:
                            warnings.append(
                                ScanWarning(
                                    path=entry.path,
                                    warning_type="os_error",
                                    message=f"OS error reading file metadata: {str(os_err)}",
                                )
                            )
                            skipped_count += 1
                            continue

                        entry_p = Path(entry.path)
                        rel_path = entry_p.relative_to(root_path).as_posix()
                        ext = entry_p.suffix.lower()
                        size = stat_res.st_size
                        total_size_bytes += size

                        # Timestamps
                        try:
                            mtime = datetime.fromtimestamp(stat_res.st_mtime, tz=timezone.utc)
                        except Exception:
                            mtime = None

                        try:
                            # st_ctime on Windows is creation time
                            ctime = datetime.fromtimestamp(stat_res.st_ctime, tz=timezone.utc)
                        except Exception:
                            ctime = None

                        files.append(
                            FileEntry(
                                relative_path=rel_path,
                                filename=name,
                                extension=ext,
                                size_bytes=size,
                                file_type=determine_file_type(ext),
                                created_at=ctime,
                                modified_at=mtime,
                                is_symlink=is_sym,
                            )
                        )

                        if len(files) >= max_files:
                            truncated = True
                            break

        except PermissionError as p_err:
            warnings.append(
                ScanWarning(
                    path=str(current_dir),
                    warning_type="permission_denied",
                    message=f"Permission denied reading directory: {str(p_err)}",
                )
            )
            skipped_count += 1
        except FileNotFoundError:
            warnings.append(
                ScanWarning(
                    path=str(current_dir),
                    warning_type="file_not_found",
                    message="Directory disappeared or path no longer exists.",
                )
            )
            skipped_count += 1
        except OSError as os_err:
            warnings.append(
                ScanWarning(
                    path=str(current_dir),
                    warning_type="os_error",
                    message=f"Error accessing directory: {str(os_err)}",
                )
            )
            skipped_count += 1

    elapsed_ms = (time.perf_counter() - start_time) * 1000.0

    summary = ScanSummary(
        root_id=root.id,
        root_path=root.canonical_path,
        total_files=len(files),
        total_size_bytes=total_size_bytes,
        directories_scanned=directories_scanned,
        skipped_count=skipped_count,
        duration_ms=round(elapsed_ms, 2),
        truncated=truncated,
    )

    return ScanResponse(
        scan_id=str(uuid.uuid4()),
        summary=summary,
        files=files,
        warnings=warnings,
    )
