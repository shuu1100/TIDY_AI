"""Pydantic schemas for TidyAI backend."""

from datetime import datetime, timezone
from enum import Enum
from typing import List, Optional
from pydantic import BaseModel, Field


# ==============================================================================
# System & Health Schemas
# ==============================================================================

class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str = Field(..., description="Overall health status: 'ok' or 'degraded'")
    version: str = Field(..., description="Application version")
    service: str = Field("tidy-ai-backend", description="Service identifier")
    host: str = Field(..., description="Bound host interface")
    port: int = Field(..., description="Bound port")
    database_connected: bool = Field(..., description="SQLite connectivity status")
    ollama_configured: bool = Field(..., description="Ollama endpoint configuration status")
    ollama_model: str = Field(..., description="Configured local model name")
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp of response",
    )


class OllamaHealthState(str, Enum):
    """Health states for Ollama local provider."""

    HEALTHY = "healthy"
    SERVER_UNREACHABLE = "server_unreachable"
    MODEL_MISSING = "model_missing"


class OllamaStatusResponse(BaseModel):
    """Ollama local AI status schema."""

    state: OllamaHealthState = Field(..., description="High-level state: healthy, server_unreachable, model_missing")
    reachable: bool = Field(..., description="Whether Ollama local server responds")
    version: Optional[str] = Field(None, description="Ollama server version if reachable")
    model_installed: bool = Field(..., description="Whether configured model is present locally")
    model_name: str = Field(..., description="Target model name")
    available_models: List[str] = Field(default_factory=list, description="Models currently downloaded in local Ollama")
    base_url: str = Field(..., description="Target local HTTP base URL")
    message: str = Field(..., description="Diagnostic summary")
    install_command: Optional[str] = Field(None, description="CLI command to pull model if missing")


class OllamaGenerateRequest(BaseModel):
    """Test inference request schema."""

    prompt: str = Field(..., min_length=1, max_length=10000, description="User prompt text")
    system_prompt: Optional[str] = Field(None, description="Optional system prompt")
    temperature: float = Field(0.1, ge=0.0, le=1.0, description="Sampling temperature")


class OllamaGenerateResponse(BaseModel):
    """Test inference response schema."""

    model: str = Field(..., description="Model used for generation")
    response_text: str = Field(..., description="Raw generated response")
    duration_ms: float = Field(..., ge=0, description="Elapsed inference time in milliseconds")


# ==============================================================================
# Approved Roots Schemas
# ==============================================================================

class ApprovedRootCreate(BaseModel):
    """Request schema for registering a new approved root."""

    path: str = Field(..., description="Absolute or relative path to the directory to approve")
    label: Optional[str] = Field(None, description="Optional user-friendly label for the directory")


class ApprovedRoot(BaseModel):
    """Approved root representation schema."""

    id: str = Field(..., description="Unique identifier for this approved root")
    canonical_path: str = Field(..., description="Resolved, canonicalized filesystem path")
    label: str = Field(..., description="User-friendly display label")
    added_at: datetime = Field(..., description="UTC timestamp when root was approved")


class ApprovedRootListResponse(BaseModel):
    """List of currently approved directory roots."""

    roots: List[ApprovedRoot] = Field(default_factory=list)


# ==============================================================================
# File Inventory & Scanner Schemas
# ==============================================================================

class BroadFileType(str, Enum):
    """Broad categorization for scanned files."""

    DOCUMENT = "document"
    IMAGE = "image"
    AUDIO = "audio"
    VIDEO = "video"
    ARCHIVE = "archive"
    CODE = "code"
    OTHER = "other"


class FileEntry(BaseModel):
    """Metadata-only file entry in scan inventory."""

    relative_path: str = Field(..., description="Path relative to the approved root (forward slashes)")
    filename: str = Field(..., description="Name of the file including extension")
    extension: str = Field(..., description="Normalized lowercase file extension (e.g. '.pdf')")
    size_bytes: int = Field(..., ge=0, description="File size in bytes")
    file_type: BroadFileType = Field(..., description="Broad category of file")
    created_at: Optional[datetime] = Field(None, description="Creation timestamp if available")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")
    is_symlink: bool = Field(False, description="Whether this file entry is a symlink")


class ScanWarning(BaseModel):
    """Structured warning or partial failure encountered during scan."""

    path: str = Field(..., description="Relative or absolute path associated with warning")
    warning_type: str = Field(
        ...,
        description="Category: 'permission_denied', 'file_not_found', 'symlink_escape', 'os_error', 'path_invalid'",
    )
    message: str = Field(..., description="Human-readable warning detail")


class ScanSummary(BaseModel):
    """Statistical summary of a scan execution."""

    root_id: str = Field(..., description="ID of approved root scanned")
    root_path: str = Field(..., description="Canonical path of approved root")
    total_files: int = Field(..., ge=0, description="Total files successfully indexed")
    total_size_bytes: int = Field(..., ge=0, description="Combined size of indexed files in bytes")
    directories_scanned: int = Field(..., ge=0, description="Number of directories visited")
    skipped_count: int = Field(..., ge=0, description="Number of entries skipped due to filters or errors")
    duration_ms: float = Field(..., ge=0, description="Scan elapsed time in milliseconds")
    truncated: bool = Field(False, description="Whether scan reached maximum file limit")


class ScanRequest(BaseModel):
    """Request schema for initiating a read-only scan."""

    root_id: str = Field(..., description="ID of approved root to scan")
    subpath: str = Field("", description="Optional subfolder within root to restrict scan (must not escape root)")
    recursive: bool = Field(True, description="Whether to scan child directories recursively")
    max_files: int = Field(10000, ge=1, le=50000, description="Maximum files to index before truncating")
    max_depth: int = Field(20, ge=1, le=50, description="Maximum directory traversal depth")


class ScanResponse(BaseModel):
    """Complete scan result response."""

    scan_id: str = Field(..., description="Unique ID for this scan session")
    summary: ScanSummary = Field(..., description="Statistical summary of the scan")
    files: List[FileEntry] = Field(default_factory=list, description="Indexed file entries")
    warnings: List[ScanWarning] = Field(default_factory=list, description="Structured scan warnings")


# ==============================================================================
# Exact Duplicate Detection Schemas
# ==============================================================================

class DuplicateFileEntry(BaseModel):
    """Individual file belonging to a duplicate group."""

    relative_path: str = Field(..., description="Relative path from approved root (forward slashes)")
    filename: str = Field(..., description="Filename including extension")
    extension: str = Field(..., description="Normalized file extension")
    size_bytes: int = Field(..., ge=0, description="Exact file size in bytes")
    modified_at: Optional[datetime] = Field(None, description="Last modification timestamp")


class DuplicateGroup(BaseModel):
    """Group of files sharing identical SHA-256 hash."""

    sha256: str = Field(..., description="Hex SHA-256 hash representing exact content")
    size_bytes: int = Field(..., ge=0, description="Size of each individual file in bytes")
    file_count: int = Field(..., ge=2, description="Number of identical files in this group")
    potential_savings_bytes: int = Field(..., ge=0, description="Bytes reclaimable if all but 1 were removed")
    files: List[DuplicateFileEntry] = Field(..., min_length=2, description="List of identical files")


class DuplicateWarning(BaseModel):
    """Structured warning encountered during duplicate detection hashing."""

    path: str = Field(..., description="Relative or canonical path of problem file")
    warning_type: str = Field(
        ...,
        description="Category: 'permission_denied', 'file_not_found', 'file_modified_during_hash', 'os_error'",
    )
    message: str = Field(..., description="Human-readable warning detail")


class DuplicateSummary(BaseModel):
    """Statistical summary of duplicate detection run."""

    root_id: str = Field(..., description="ID of approved root evaluated")
    root_path: str = Field(..., description="Canonical path of approved root")
    total_files_evaluated: int = Field(..., ge=0, description="Total files inspected")
    candidate_files_hashed: int = Field(..., ge=0, description="Files hashed because of matching sizes")
    duplicate_groups_count: int = Field(..., ge=0, description="Number of duplicate groups found")
    duplicate_files_count: int = Field(..., ge=0, description="Total count of duplicate files across all groups")
    potential_savings_bytes: int = Field(..., ge=0, description="Total potential reclaimable space in bytes")
    duration_ms: float = Field(..., ge=0, description="Detection run elapsed time in milliseconds")


class DuplicateDetectionRequest(BaseModel):
    """Request schema for initiating duplicate detection."""

    root_id: str = Field(..., description="ID of approved root to evaluate")
    subpath: str = Field("", description="Optional subfolder within root to restrict duplicate search")
    min_size_bytes: int = Field(0, ge=0, description="Minimum file size in bytes to evaluate (default 0)")


class DuplicateDetectionResponse(BaseModel):
    """Complete duplicate detection report."""

    detection_id: str = Field(..., description="Unique ID for this duplicate detection run")
    notice: str = Field(
        "DETECTION ONLY: No files have been deleted, moved, or altered.",
        description="Mandatory read-only notice",
    )
    summary: DuplicateSummary = Field(..., description="Statistical summary")
    groups: List[DuplicateGroup] = Field(default_factory=list, description="Identified duplicate groups")
    warnings: List[DuplicateWarning] = Field(default_factory=list, description="Structured warnings during hashing")


# ==============================================================================
# AI Suggestion Engine Schemas (Phase 5)
# ==============================================================================

class OllamaFileSuggestion(BaseModel):
    """Raw suggestion item produced by local Ollama model."""

    file_id: str = Field(..., description="Unique file identifier or relative path")
    current_relative_path: str = Field(..., description="Current relative path of the file")
    category: str = Field(..., description="Suggested organizational category (e.g. 'Documents/Invoices')")
    proposed_filename: str = Field(..., description="Suggested clean filename including original extension")
    proposed_subfolder: str = Field(..., description="Suggested relative destination subfolder")
    rationale: str = Field(..., description="Short explanation for the suggestion")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score between 0.0 and 1.0")


class OllamaSuggestionBatch(BaseModel):
    """Container schema for raw structured batch completions from Ollama."""

    suggestions: List[OllamaFileSuggestion] = Field(default_factory=list)


class SuggestionWarning(BaseModel):
    """Structured warning regarding validation, collisions, or model output."""

    path: str = Field(..., description="Relative or canonical path associated with warning")
    warning_type: str = Field(
        ...,
        description="Category: 'invalid_filename', 'path_traversal', 'reserved_name', 'extension_mismatch', 'collision_disk', 'collision_batch', 'validation_error', 'low_confidence', 'model_error'",
    )
    message: str = Field(..., description="Human-readable warning detail")


class SuggestionItem(BaseModel):
    """Deterministically validated suggestion for a single file."""

    file_id: str = Field(..., description="Unique file identifier or current relative path")
    current_relative_path: str = Field(..., description="Existing relative path (forward slashes)")
    category: str = Field(..., description="Validated organizational category")
    proposed_filename: str = Field(..., description="Validated clean filename")
    proposed_subfolder: str = Field(..., description="Validated relative destination subfolder (forward slashes)")
    proposed_relative_path: str = Field(..., description="Full proposed relative path (folder + filename)")
    rationale: str = Field(..., description="Rationale for suggestion")
    confidence: float = Field(..., ge=0.0, le=1.0, description="Confidence score")
    is_ambiguous: bool = Field(False, description="Flagged for user review due to low confidence or collisions")
    collision_detected: bool = Field(False, description="Whether proposed destination collides on disk or in batch")
    collision_details: Optional[str] = Field(None, description="Details if collision detected")
    is_valid: bool = Field(True, description="Whether model suggestion passed deterministic validation")
    validation_error: Optional[str] = Field(None, description="Error reason if validation failed")


class SuggestionSummary(BaseModel):
    """Statistical summary of suggestion generation."""

    root_id: str = Field(..., description="Approved root ID")
    root_path: str = Field(..., description="Canonical approved root path")
    total_files_analyzed: int = Field(..., ge=0, description="Number of files submitted to engine")
    suggestions_generated: int = Field(..., ge=0, description="Number of suggestions produced")
    ambiguous_count: int = Field(..., ge=0, description="Number of suggestions flagged as ambiguous")
    collisions_count: int = Field(..., ge=0, description="Number of suggestions with detected collisions")
    model_used: str = Field(..., description="Ollama model used")
    duration_ms: float = Field(..., ge=0, description="Elapsed time in milliseconds")


class SuggestionBatchRequest(BaseModel):
    """Request schema for generating AI categorization and organization suggestions."""

    root_id: str = Field(..., description="ID of approved root to process")
    subpath: str = Field("", description="Optional subfolder within root to restrict scope")
    file_paths: Optional[List[str]] = Field(None, description="Optional list of specific relative file paths")
    max_files: int = Field(50, ge=1, le=100, description="Maximum files to analyze in one batch")
    confidence_threshold: float = Field(0.70, ge=0.0, le=1.0, description="Threshold below which suggestions are marked ambiguous")


class SuggestionBatchResponse(BaseModel):
    """Complete AI suggestions report."""

    batch_id: str = Field(..., description="Unique ID for this suggestion batch")
    notice: str = Field(
        "PROPOSAL ONLY: Suggestions are strictly proposals. No files have been renamed, moved, or modified.",
        description="Mandatory read-only notice",
    )
    summary: SuggestionSummary = Field(..., description="Statistical summary")
    suggestions: List[SuggestionItem] = Field(default_factory=list, description="Validated suggestions")
    warnings: List[SuggestionWarning] = Field(default_factory=list, description="Structured warnings")


