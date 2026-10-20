"""Deterministic Rule-Based File Classification Engine for TidyAI.

Classifies files based on explicit Python rules first:
1. File extension mapping against centralized catalog.
2. Standard library MIME type inference (mimetypes).
3. Filename patterns (e.g. invoices, screenshots, logs, datasets).
4. Flags ambiguous, missing, or conflicting signals as 'Needs review'.

Zero-mutation: Never alters or moves files.
Metadata-only: Does not read or transmit file contents.
"""

import mimetypes
import re
import time
import uuid
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from backend.app.schemas import (
    ApprovedRoot,
    ClassificationBatchResponse,
    ClassificationSource,
    ClassificationSummary,
    FileCategory,
    FileClassificationItem,
)
from backend.app.services.scanner import scan_approved_root
from backend.app.services.security import (
    SecurityBoundaryError,
    resolve_and_verify_containment,
)

# Centralized extension taxonomy mapping:
# extension -> (Category, Suggested Subfolder, Reason)
EXTENSION_CATALOG: Dict[str, Tuple[FileCategory, str, str]] = {
    # Documents
    ".pdf": (FileCategory.DOCUMENTS, "Documents", "PDF document extension"),
    ".docx": (FileCategory.DOCUMENTS, "Documents", "Microsoft Word document extension"),
    ".doc": (FileCategory.DOCUMENTS, "Documents", "Legacy Microsoft Word document extension"),
    ".odt": (FileCategory.DOCUMENTS, "Documents", "OpenDocument text extension"),
    ".rtf": (FileCategory.DOCUMENTS, "Documents", "Rich Text Format extension"),
    ".txt": (FileCategory.DOCUMENTS, "Documents", "Plain text file extension"),
    ".md": (FileCategory.DOCUMENTS, "Documents", "Markdown documentation extension"),
    ".epub": (FileCategory.DOCUMENTS, "Documents/Ebooks", "Electronic publication extension"),
    ".pages": (FileCategory.DOCUMENTS, "Documents", "Apple Pages document extension"),

    # Spreadsheets
    ".xlsx": (FileCategory.SPREADSHEETS, "Spreadsheets", "Microsoft Excel workbook extension"),
    ".xls": (FileCategory.SPREADSHEETS, "Spreadsheets", "Legacy Microsoft Excel spreadsheet extension"),
    ".ods": (FileCategory.SPREADSHEETS, "Spreadsheets", "OpenDocument spreadsheet extension"),
    ".numbers": (FileCategory.SPREADSHEETS, "Spreadsheets", "Apple Numbers spreadsheet extension"),

    # Presentations
    ".pptx": (FileCategory.PRESENTATIONS, "Presentations", "Microsoft PowerPoint presentation extension"),
    ".ppt": (FileCategory.PRESENTATIONS, "Presentations", "Legacy Microsoft PowerPoint presentation extension"),
    ".odp": (FileCategory.PRESENTATIONS, "Presentations", "OpenDocument presentation extension"),
    ".key": (FileCategory.PRESENTATIONS, "Presentations", "Apple Keynote presentation extension"),

    # Images
    ".png": (FileCategory.IMAGES, "Images", "Portable Network Graphics extension"),
    ".jpg": (FileCategory.IMAGES, "Images", "JPEG image extension"),
    ".jpeg": (FileCategory.IMAGES, "Images", "JPEG image extension"),
    ".webp": (FileCategory.IMAGES, "Images", "WebP image extension"),
    ".gif": (FileCategory.IMAGES, "Images", "GIF animation/image extension"),
    ".svg": (FileCategory.IMAGES, "Images", "Scalable Vector Graphics extension"),
    ".bmp": (FileCategory.IMAGES, "Images", "Bitmap image extension"),
    ".tiff": (FileCategory.IMAGES, "Images", "TIFF image extension"),
    ".tif": (FileCategory.IMAGES, "Images", "TIFF image extension"),
    ".ico": (FileCategory.IMAGES, "Images/Icons", "Icon image extension"),
    ".heic": (FileCategory.IMAGES, "Images", "High Efficiency Image Container extension"),
    ".raw": (FileCategory.IMAGES, "Images/RAW", "Raw camera image extension"),

    # Videos
    ".mp4": (FileCategory.VIDEOS, "Videos", "MPEG-4 video extension"),
    ".mkv": (FileCategory.VIDEOS, "Videos", "Matroska video container extension"),
    ".mov": (FileCategory.VIDEOS, "Videos", "QuickTime video extension"),
    ".avi": (FileCategory.VIDEOS, "Videos", "Audio Video Interleave extension"),
    ".webm": (FileCategory.VIDEOS, "Videos", "WebM video container extension"),
    ".wmv": (FileCategory.VIDEOS, "Videos", "Windows Media Video extension"),
    ".flv": (FileCategory.VIDEOS, "Videos", "Flash video extension"),

    # Audio
    ".mp3": (FileCategory.AUDIO, "Audio", "MP3 audio extension"),
    ".wav": (FileCategory.AUDIO, "Audio", "WAVE audio extension"),
    ".flac": (FileCategory.AUDIO, "Audio", "Free Lossless Audio Codec extension"),
    ".aac": (FileCategory.AUDIO, "Audio", "Advanced Audio Coding extension"),
    ".m4a": (FileCategory.AUDIO, "Audio", "MPEG-4 audio extension"),
    ".ogg": (FileCategory.AUDIO, "Audio", "Ogg Vorbis audio extension"),
    ".wma": (FileCategory.AUDIO, "Audio", "Windows Media Audio extension"),

    # Archives
    ".zip": (FileCategory.ARCHIVES, "Archives", "ZIP compressed archive extension"),
    ".tar": (FileCategory.ARCHIVES, "Archives", "TAR archive container extension"),
    ".gz": (FileCategory.ARCHIVES, "Archives", "GZIP compressed archive extension"),
    ".7z": (FileCategory.ARCHIVES, "Archives", "7-Zip compressed archive extension"),
    ".rar": (FileCategory.ARCHIVES, "Archives", "RAR compressed archive extension"),
    ".bz2": (FileCategory.ARCHIVES, "Archives", "BZIP2 compressed archive extension"),
    ".xz": (FileCategory.ARCHIVES, "Archives", "XZ compressed archive extension"),

    # Code
    ".py": (FileCategory.CODE, "Code/Python", "Python script extension"),
    ".js": (FileCategory.CODE, "Code/JavaScript", "JavaScript script extension"),
    ".ts": (FileCategory.CODE, "Code/TypeScript", "TypeScript script extension"),
    ".tsx": (FileCategory.CODE, "Code/React", "React TypeScript JSX component extension"),
    ".jsx": (FileCategory.CODE, "Code/React", "React JSX component extension"),
    ".html": (FileCategory.CODE, "Code/HTML", "HTML markup extension"),
    ".css": (FileCategory.CODE, "Code/CSS", "CSS stylesheet extension"),
    ".json": (FileCategory.CODE, "Code/Data", "JSON data interchange extension"),
    ".yaml": (FileCategory.CODE, "Code/Config", "YAML configuration extension"),
    ".yml": (FileCategory.CODE, "Code/Config", "YAML configuration extension"),
    ".sql": (FileCategory.CODE, "Code/SQL", "SQL database query script extension"),
    ".sh": (FileCategory.CODE, "Code/Scripts", "Shell script extension"),
    ".ps1": (FileCategory.CODE, "Code/Scripts", "PowerShell script extension"),
    ".c": (FileCategory.CODE, "Code/C", "C source code extension"),
    ".cpp": (FileCategory.CODE, "Code/Cpp", "C++ source code extension"),
    ".h": (FileCategory.CODE, "Code/Headers", "C/C++ header extension"),
    ".rs": (FileCategory.CODE, "Code/Rust", "Rust source code extension"),
    ".go": (FileCategory.CODE, "Code/Go", "Go source code extension"),
    ".java": (FileCategory.CODE, "Code/Java", "Java source code extension"),

    # Datasets
    ".parquet": (FileCategory.DATASETS, "Datasets", "Apache Parquet columnar dataset extension"),
    ".arrow": (FileCategory.DATASETS, "Datasets", "Apache Arrow dataset extension"),
    ".feather": (FileCategory.DATASETS, "Datasets", "Feather format dataset extension"),
    ".hdf5": (FileCategory.DATASETS, "Datasets", "HDF5 scientific data container extension"),
    ".h5": (FileCategory.DATASETS, "Datasets", "HDF5 scientific data container extension"),
    ".sqlite3": (FileCategory.DATASETS, "Datasets/Databases", "SQLite 3 database file extension"),
    ".db": (FileCategory.DATASETS, "Datasets/Databases", "Database file extension"),
}

# Known extensionless files
KNOWN_EXACT_NAMES: Dict[str, Tuple[FileCategory, str, str]] = {
    "dockerfile": (FileCategory.CODE, "Code/Docker", "Standard Docker configuration file"),
    "makefile": (FileCategory.CODE, "Code/Build", "Standard Make build specification"),
    "readme": (FileCategory.DOCUMENTS, "Documents", "Standard README documentation file"),
    "license": (FileCategory.DOCUMENTS, "Documents/Legal", "Standard software license file"),
    ".gitignore": (FileCategory.CODE, "Code/Config", "Git ignore specification"),
    ".env": (FileCategory.CODE, "Code/Config", "Environment variable configuration"),
    ".editorconfig": (FileCategory.CODE, "Code/Config", "EditorConfig specification"),
}

# Filename regex patterns for special classification rules
RE_DOUBLE_EXT = re.compile(
    r"\.(pdf|docx|xlsx|pptx|jpg|png|zip)\.(exe|bat|cmd|vbs|ps1|scr|pif|com)$",
    re.IGNORECASE,
)
RE_INVOICE = re.compile(r"(invoice|receipt|bill|statement|factura|rechnung)", re.IGNORECASE)
RE_SCREENSHOT = re.compile(r"(screenshot|screen_shot|screengrab|capture|captura)", re.IGNORECASE)
RE_DATASET = re.compile(r"(dataset|data_train|data_test|train_|test_|metrics|telemetry)", re.IGNORECASE)
RE_LOG = re.compile(r"(log|_log|\.log$)", re.IGNORECASE)
RE_BACKUP = re.compile(r"(backup|_bak|\.bak$|old_|temp_)", re.IGNORECASE)
RE_TEMP_LOCK = re.compile(r"(^~\$|\.tmp$|\.crdownload$|\.part$)", re.IGNORECASE)


def classify_file(
    filename: str,
    relative_path: str = "",
    size_bytes: int = 0,
) -> FileClassificationItem:
    """Classify a single file deterministically using explicit Python rules.

    Rule Priority:
    1. Double-extension / security anomaly detection -> Needs review.
    2. Temporary / lock file patterns -> Needs review.
    3. Filename patterns (e.g. invoices, screenshots, datasets).
    4. Explicit extension mapping against centralized catalog.
    5. Standard library MIME type resolution.
    6. Fallback to Needs review / Other.
    """
    clean_name = filename.strip()
    norm_rel = relative_path.replace("\\", "/").strip("/") if relative_path else clean_name
    ext = Path(clean_name).suffix.lower()
    stem = Path(clean_name).stem.lower()
    lower_name = clean_name.lower()

    # Rule 1: Double-extension detection (e.g. invoice.pdf.exe)
    if RE_DOUBLE_EXT.search(clean_name):
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=FileCategory.NEEDS_REVIEW,
            confidence=0.95,
            source=ClassificationSource.FILENAME_RULE,
            reason="High-risk double file extension detected (e.g. .pdf.exe). Flagged for security review.",
            suggested_subfolder="Needs_Review/Suspicious",
            is_ambiguous=True,
        )

    # Rule 2: Temporary or lock file detection
    if RE_TEMP_LOCK.search(clean_name):
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=FileCategory.NEEDS_REVIEW,
            confidence=0.90,
            source=ClassificationSource.FILENAME_RULE,
            reason="Temporary lock or incomplete download file detected.",
            suggested_subfolder="Needs_Review/Temporary",
            is_ambiguous=True,
        )

    # Rule 3: Known exact extensionless filenames
    if not ext:
        if lower_name in KNOWN_EXACT_NAMES:
            cat, subfolder, reason = KNOWN_EXACT_NAMES[lower_name]
            return FileClassificationItem(
                relative_path=norm_rel,
                filename=clean_name,
                extension="",
                size_bytes=size_bytes,
                category=cat,
                confidence=0.95,
                source=ClassificationSource.FILENAME_RULE,
                reason=reason,
                suggested_subfolder=subfolder,
                is_ambiguous=False,
            )
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension="",
            size_bytes=size_bytes,
            category=FileCategory.NEEDS_REVIEW,
            confidence=0.40,
            source=ClassificationSource.FILENAME_RULE,
            reason="File has no extension and does not match known system filenames.",
            suggested_subfolder="Needs_Review/No_Extension",
            is_ambiguous=True,
        )

    # Rule 4: Disambiguate CSV / TSV by filename pattern
    if ext in (".csv", ".tsv"):
        if RE_DATASET.search(stem):
            return FileClassificationItem(
                relative_path=norm_rel,
                filename=clean_name,
                extension=ext,
                size_bytes=size_bytes,
                category=FileCategory.DATASETS,
                confidence=0.90,
                source=ClassificationSource.FILENAME_RULE,
                reason=f"Delimited data file with dataset naming pattern ('{stem}').",
                suggested_subfolder="Datasets",
                is_ambiguous=False,
            )
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=FileCategory.SPREADSHEETS,
            confidence=0.88,
            source=ClassificationSource.EXTENSION_RULE,
            reason="Comma/tab-separated values file mapped to Spreadsheets.",
            suggested_subfolder="Spreadsheets",
            is_ambiguous=False,
        )

    # Rule 5: Specific filename sub-categorization for documents & images
    if ext in (".pdf", ".docx", ".doc", ".txt") and RE_INVOICE.search(stem):
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=FileCategory.DOCUMENTS,
            confidence=0.95,
            source=ClassificationSource.FILENAME_RULE,
            reason="Financial keyword in document filename pattern (invoice/receipt).",
            suggested_subfolder="Documents/Invoices",
            is_ambiguous=False,
        )

    if ext in (".png", ".jpg", ".jpeg", ".webp") and RE_SCREENSHOT.search(stem):
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=FileCategory.IMAGES,
            confidence=0.95,
            source=ClassificationSource.FILENAME_RULE,
            reason="Screenshot pattern detected in image filename.",
            suggested_subfolder="Images/Screenshots",
            is_ambiguous=False,
        )

    # Rule 6: Centralized extension catalog lookup
    if ext in EXTENSION_CATALOG:
        cat, subfolder, reason = EXTENSION_CATALOG[ext]
        return FileClassificationItem(
            relative_path=norm_rel,
            filename=clean_name,
            extension=ext,
            size_bytes=size_bytes,
            category=cat,
            confidence=0.92,
            source=ClassificationSource.EXTENSION_RULE,
            reason=reason,
            suggested_subfolder=subfolder,
            is_ambiguous=False,
        )

    # Rule 7: Standard Library MIME type inspection
    mime_type, _ = mimetypes.guess_type(clean_name)
    if mime_type:
        mime_cat = None
        if mime_type.startswith("image/"):
            mime_cat = (FileCategory.IMAGES, "Images", f"MIME type '{mime_type}' indicates image format")
        elif mime_type.startswith("video/"):
            mime_cat = (FileCategory.VIDEOS, "Videos", f"MIME type '{mime_type}' indicates video format")
        elif mime_type.startswith("audio/"):
            mime_cat = (FileCategory.AUDIO, "Audio", f"MIME type '{mime_type}' indicates audio format")
        elif mime_type.startswith("text/"):
            mime_cat = (FileCategory.DOCUMENTS, "Documents", f"MIME type '{mime_type}' indicates text document")
        elif "application/pdf" in mime_type:
            mime_cat = (FileCategory.DOCUMENTS, "Documents", "MIME type indicates PDF document")
        elif "zip" in mime_type or "tar" in mime_type or "archive" in mime_type:
            mime_cat = (FileCategory.ARCHIVES, "Archives", f"MIME type '{mime_type}' indicates compressed archive")

        if mime_cat:
            cat, subfolder, reason = mime_cat
            return FileClassificationItem(
                relative_path=norm_rel,
                filename=clean_name,
                extension=ext,
                size_bytes=size_bytes,
                category=cat,
                confidence=0.85,
                source=ClassificationSource.MIME_RULE,
                reason=reason,
                suggested_subfolder=subfolder,
                is_ambiguous=False,
            )

    # Rule 8: Fallback to Needs review
    return FileClassificationItem(
        relative_path=norm_rel,
        filename=clean_name,
        extension=ext,
        size_bytes=size_bytes,
        category=FileCategory.NEEDS_REVIEW,
        confidence=0.30,
        source=ClassificationSource.EXTENSION_RULE,
        reason=f"Unrecognized file extension '{ext}' and unknown MIME type.",
        suggested_subfolder="Needs_Review/Uncategorized",
        is_ambiguous=True,
    )


def classify_files_batch(
    root: ApprovedRoot,
    subpath: str = "",
    file_paths: Optional[List[str]] = None,
    max_files: int = 500,
) -> ClassificationBatchResponse:
    """Classify a batch of files within an approved root using deterministic rules."""
    root_path = Path(root.canonical_path).resolve()
    batch_id = str(uuid.uuid4())
    start_time = time.perf_counter()

    items: List[FileClassificationItem] = []
    categories_count: Dict[str, int] = {}
    needs_review_count = 0

    if file_paths:
        for rel_p in file_paths[:max_files]:
            try:
                verified_p = resolve_and_verify_containment(root_path, rel_p)
                if not verified_p.is_file():
                    continue
                stat = verified_p.stat()
                norm_rel = verified_p.relative_to(root_path).as_posix()
                item = classify_file(
                    filename=verified_p.name,
                    relative_path=norm_rel,
                    size_bytes=stat.st_size,
                )
                items.append(item)
            except (SecurityBoundaryError, OSError):
                continue
    else:
        scan_res = scan_approved_root(
            root=root,
            subpath=subpath,
            recursive=True,
            max_files=max_files,
            max_depth=20,
        )
        for fe in scan_res.files:
            item = classify_file(
                filename=fe.filename,
                relative_path=fe.relative_path,
                size_bytes=fe.size_bytes,
            )
            items.append(item)

    for item in items:
        cat_name = item.category.value
        categories_count[cat_name] = categories_count.get(cat_name, 0) + 1
        if item.is_ambiguous or item.category == FileCategory.NEEDS_REVIEW:
            needs_review_count += 1

    duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)

    return ClassificationBatchResponse(
        batch_id=batch_id,
        summary=ClassificationSummary(
            root_id=root.id,
            root_path=str(root_path),
            total_files=len(items),
            classified_by_rules=len(items),
            needs_review_count=needs_review_count,
            categories_count=categories_count,
            duration_ms=duration_ms,
        ),
        classifications=items,
    )
