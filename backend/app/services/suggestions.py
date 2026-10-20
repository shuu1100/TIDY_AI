"""AI Categorization and Suggestion Engine for TidyAI.

Generates reviewable category, clean filename, and destination subfolder proposals.
Strictly read-only: never modifies, renames, moves, or deletes any files.
Deterministic backend validation: all model outputs are validated and sanitized.
"""

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
from backend.app.services.scanner import scan_approved_root
from backend.app.services.security import (
    SecurityBoundaryError,
    resolve_and_verify_containment,
)

# Windows reserved device names (cannot be used as file base names)
WINDOWS_RESERVED_NAMES: Set[str] = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}

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


def build_system_prompt() -> str:
    """System prompt enforcing strict structured JSON output and safe organization practices."""
    return (
        "You are TidyAI's File Organization Specialist. Your task is to analyze file metadata "
        "(filename, extension, size, existing relative path) and suggest clean organizational "
        "categories, descriptive filenames, and appropriate relative subfolders.\n\n"
        "STRICT RULES:\n"
        "1. Never rename file extensions. Preserve original extension exactly.\n"
        "2. Keep filenames concise, descriptive, and human-readable. Use letters, numbers, hyphens, and underscores.\n"
        "3. Destination subfolder must be a relative path (e.g. 'Documents/Invoices' or 'Images/Wallpapers'). Never use drive letters, '..', or absolute paths.\n"
        "4. Assign a category (e.g. 'Documents/Work', 'Media/Photos', 'Code/Scripts').\n"
        "5. Assign a confidence score between 0.0 and 1.0. If the file purpose is ambiguous or unclear, use a lower score (e.g. 0.4 - 0.6).\n"
        "6. Provide a concise rationale for each suggestion.\n"
        "7. Return strictly valid JSON matching the requested schema."
    )


def build_user_prompt(files: List[FileEntry]) -> str:
    """Format file metadata into a clear JSON payload for the AI model."""
    files_meta = []
    for f in files:
        files_meta.append(
            {
                "file_id": f.relative_path,
                "current_relative_path": f.relative_path,
                "filename": f.filename,
                "extension": f.extension,
                "size_bytes": f.size_bytes,
                "file_type": f.file_type.value,
            }
        )

    return (
        f"Analyze these {len(files_meta)} files and propose organization suggestions:\n"
        f"```json\n{files_meta}\n```\n\n"
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
        for item in batch_output.suggestions:
            raw_by_id[item.file_id] = item
            raw_by_id[item.current_relative_path] = item

    seen_in_batch: Set[str] = set()
    ambiguous_count = 0
    collisions_count = 0

    for cand in candidate_files:
        raw_sugg = raw_by_id.get(cand.relative_path)

        if not raw_sugg:
            # Model skipped this file: fallback safely to original location
            warnings.append(
                SuggestionWarning(
                    path=cand.relative_path,
                    warning_type="model_error",
                    message="Model did not return a suggestion for this file. Preserved current location.",
                )
            )
            validated_suggestions.append(
                SuggestionItem(
                    file_id=cand.relative_path,
                    current_relative_path=cand.relative_path,
                    category="Uncategorized",
                    proposed_filename=cand.filename,
                    proposed_subfolder=str(Path(cand.relative_path).parent.as_posix()).replace(".", ""),
                    proposed_relative_path=cand.relative_path,
                    rationale="Preserved original location due to missing model completion.",
                    confidence=0.5,
                    is_ambiguous=True,
                    collision_detected=False,
                    collision_details=None,
                    is_valid=False,
                    validation_error="Missing suggestion from AI model",
                )
            )
            ambiguous_count += 1
            continue

        # 3a. Validate proposed filename
        fn_valid, clean_filename, fn_err = validate_and_sanitize_filename(
            raw_sugg.proposed_filename, cand.filename
        )

        # 3b. Validate proposed subfolder
        sub_valid, clean_subfolder, sub_err = validate_and_sanitize_subfolder(
            raw_sugg.proposed_subfolder, root_path
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

        # 3c. Collision Detection
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

        # 3d. Ambiguity evaluation
        is_ambiguous = (
            raw_sugg.confidence < confidence_threshold
            or collided
            or not is_valid
        )
        if is_ambiguous:
            ambiguous_count += 1

        validated_suggestions.append(
            SuggestionItem(
                file_id=cand.relative_path,
                current_relative_path=cand.relative_path,
                category=raw_sugg.category if is_valid else "Uncategorized",
                proposed_filename=clean_filename,
                proposed_subfolder=clean_subfolder,
                proposed_relative_path=proposed_rel,
                rationale=raw_sugg.rationale,
                confidence=raw_sugg.confidence,
                is_ambiguous=is_ambiguous,
                collision_detected=collided,
                collision_details=coll_details,
                is_valid=is_valid,
                validation_error=validation_error,
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
