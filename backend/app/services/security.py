"""Security boundary validation and canonicalization for TidyAI.

Enforces strict root containment, rejects traversal attacks, Windows drive escapes,
UNC paths, and escaping symlinks/junctions.
"""

import os
import sys
from pathlib import Path
from typing import Set


class SecurityBoundaryError(ValueError):
    """Raised when a path violates approved boundary or contains forbidden escapes."""
    pass


# Default directory names to ignore during scans
DEFAULT_IGNORED_NAMES: Set[str] = {
    ".git",
    ".venv",
    "venv",
    "env",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    ".next",
    ".idea",
    ".vscode",
    "$RECYCLE.BIN",
    "System Volume Information",
}

# Default file names to ignore during scans
DEFAULT_IGNORED_FILES: Set[str] = {
    ".DS_Store",
    "Thumbs.db",
    "desktop.ini",
}


# Windows reserved device names (cannot be used as file or folder stems)
WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def get_dangerous_system_paths() -> Set[Path]:
    """Return set of normalized paths that must never be registered as scan roots."""
    dangerous: Set[Path] = set()

    if sys.platform == "win32":
        # Windows system drives & directories
        system_root = os.environ.get("SystemRoot", "C:\\Windows")
        dangerous.add(Path(system_root).resolve())
        dangerous.add((Path(system_root) / "System32").resolve())

        prog_files = os.environ.get("ProgramFiles", "C:\\Program Files")
        dangerous.add(Path(prog_files).resolve())

        prog_files_x86 = os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)")
        dangerous.add(Path(prog_files_x86).resolve())

        appdata = os.environ.get("APPDATA")
        if appdata:
            dangerous.add(Path(appdata).resolve())

        # Also add drive roots (e.g. C:\, D:\)
        for drive_letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
            drive_path = Path(f"{drive_letter}:\\")
            if drive_path.exists():
                dangerous.add(drive_path.resolve())
    else:
        # Unix system directories
        for p in ["/", "/etc", "/bin", "/sbin", "/usr", "/var", "/dev", "/proc", "/sys"]:
            dangerous.add(Path(p).resolve())

    return dangerous


def validate_and_canonicalize_root(raw_path: str) -> Path:
    """Validate and canonicalize a requested root path.

    Rules:
    - Must exist and be a directory.
    - Must not be a filesystem root (e.g., C:\\ or /).
    - Must not be a critical operating system directory.
    - Must be canonicalized via resolve().
    """
    if not raw_path or not raw_path.strip():
        raise SecurityBoundaryError("Root path cannot be empty.")

    cleaned = raw_path.strip()

    if "\x00" in cleaned:
        raise SecurityBoundaryError("Null bytes are not permitted in root paths.")

    # Check for UNC path escapes
    if cleaned.startswith(("\\\\", "//")):
        raise SecurityBoundaryError("UNC network paths are not permitted as approved roots.")

    try:
        path_obj = Path(cleaned).resolve(strict=True)
    except FileNotFoundError:
        raise SecurityBoundaryError(f"Directory does not exist: {cleaned}")
    except Exception as exc:
        raise SecurityBoundaryError(f"Invalid path expression: {str(exc)}")

    if not path_obj.is_dir():
        raise SecurityBoundaryError(f"Path is not a directory: {cleaned}")

    # Check if path is a drive/filesystem root
    if path_obj == Path(path_obj.anchor) or len(path_obj.parts) <= 1:
        raise SecurityBoundaryError("Filesystem or drive roots cannot be registered as scan roots.")

    # Check against known dangerous system paths
    dangerous_paths = get_dangerous_system_paths()
    if path_obj in dangerous_paths:
        raise SecurityBoundaryError(f"System directory cannot be registered as an approved root: {path_obj}")

    # Reject Windows directory directly (e.g. C:\Windows or C:\Windows\...)
    for d in dangerous_paths:
        if d != Path(d.anchor) and path_obj == d:
            raise SecurityBoundaryError(f"Protected system directory: {path_obj}")

    return path_obj


def resolve_and_verify_containment(root_path: Path, subpath: str = "") -> Path:
    """Resolve subpath within root_path, strictly enforcing boundary containment.

    Rejects:
    - Null bytes and control characters
    - NTFS alternate data streams (':')
    - Path traversal ('..', parent escapes)
    - Absolute subpaths (e.g. '/etc', 'C:\\Windows')
    - Windows drive prefixes in subpath ('D:', 'C:')
    - UNC prefixes ('\\\\', '//')
    - Windows reserved device names (CON, PRN, AUX, NUL, COM1-9, LPT1-9)
    - Escapes via symlinks or junctions
    """
    root_canonical = root_path.resolve()

    if not subpath or not subpath.strip():
        return root_canonical

    subpath_clean = subpath.strip()

    # Reject null bytes
    if "\x00" in subpath_clean:
        raise SecurityBoundaryError("Null bytes are not permitted in paths.")

    # Reject obvious escapes before path math
    if subpath_clean.startswith(("\\\\", "//")):
        raise SecurityBoundaryError("UNC paths are not permitted as subpaths.")

    sub_p = Path(subpath_clean)

    if sub_p.is_absolute() or sub_p.drive:
        raise SecurityBoundaryError("Absolute paths or drive specifications are not permitted as subpaths.")

    if subpath_clean.startswith(("/", "\\")):
        raise SecurityBoundaryError("Leading path separators are not permitted in subpaths.")

    if ":" in subpath_clean:
        raise SecurityBoundaryError("Colon (':') or alternate data streams are not permitted in subpaths.")

    # Check for reserved Windows device names across all components
    for part in sub_p.parts:
        part_clean = part.strip()
        if part_clean in ("..", "."):
            continue
        part_stem = Path(part_clean).stem.upper()
        if part_stem in WINDOWS_RESERVED_NAMES:
            raise SecurityBoundaryError(f"Reserved Windows device name '{part_stem}' is forbidden in subpath.")

    # Combine and resolve
    combined = root_canonical / subpath_clean
    try:
        target_canonical = combined.resolve()
    except Exception as exc:
        raise SecurityBoundaryError(f"Failed to resolve subpath: {str(exc)}")

    # Enforce containment: target_canonical must be relative to root_canonical
    try:
        target_canonical.relative_to(root_canonical)
    except ValueError:
        raise SecurityBoundaryError(
            f"Path traversal detected: '{subpath}' escapes approved root '{root_canonical}'."
        )

    return target_canonical


def is_safe_child(candidate_path: Path, root_path: Path) -> bool:
    """Check if candidate_path is safely contained within root_path and does not escape via symlink."""
    try:
        root_canonical = root_path.resolve()
        candidate_canonical = candidate_path.resolve()
        candidate_canonical.relative_to(root_canonical)
        return True
    except (ValueError, OSError):
        return False
