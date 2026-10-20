"""Main FastAPI application entrypoint for TidyAI."""

from contextlib import asynccontextmanager
from datetime import datetime, timezone
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from backend.app import __version__
from backend.app.config import settings
from backend.app.database import check_db_connection, init_db
from backend.app.schemas import (
    ApprovedRoot,
    ApprovedRootCreate,
    ApprovedRootListResponse,
    DuplicateDetectionRequest,
    DuplicateDetectionResponse,
    HealthResponse,
    OllamaGenerateRequest,
    OllamaGenerateResponse,
    OllamaStatusResponse,
    ScanRequest,
    ScanResponse,
    SuggestionBatchRequest,
    SuggestionBatchResponse,
    SuggestionStageRequest,
    SuggestionStageResponse,
    ClassificationBatchRequest,
    ClassificationBatchResponse,
    DryRunRequest,
    DryRunResponse,
    ApplyOperationsRequest,
    ApplyOperationsResponse,
    OperationHistoryResponse,
    UndoResponse,
)
from backend.app.services.classifier import classify_files_batch
from backend.app.services.duplicates import detect_duplicates
from backend.app.services.suggestions import (
    generate_suggestions,
    stage_accepted_suggestions_batch,
)
from backend.app.services.operations import (
    apply_operation_plan,
    get_operation_history,
    simulate_dry_run,
    undo_operation_batch,
)
from backend.app.services.ollama import (
    OllamaConnectionError,
    OllamaError,
    OllamaJsonParseError,
    OllamaModelNotFoundError,
    OllamaResponseError,
    OllamaTimeoutError,
    ollama_service,
)
from backend.app.services.roots_registry import roots_registry
from backend.app.services.scanner import scan_approved_root
from backend.app.services.security import SecurityBoundaryError


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager to initialize resources safely."""
    # Initialize SQLite database schema
    init_db()
    yield


app = FastAPI(
    title="TidyAI Backend API",
    version=__version__,
    description="Local-first, privacy-focused file organization assistant API",
    lifespan=lifespan,
)

# CORS restricted strictly to localhost frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        settings.frontend_origin,
    ],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# ==============================================================================
# General & Health Endpoints
# ==============================================================================

@app.get("/", tags=["General"])
async def root():
    """Root endpoint welcoming local clients."""
    return {
        "message": "Welcome to TidyAI API. All operations run locally on 127.0.0.1.",
        "docs_url": "/docs",
        "health_url": "/api/health",
        "version": __version__,
    }


@app.get(
    "/api/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
)
@app.get(
    "/api/v1/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    tags=["System"],
    include_in_schema=False,
)
async def get_health():
    """Typed health check endpoint verifying database connectivity and configuration."""
    db_ok = check_db_connection()
    overall_status = "ok" if db_ok else "degraded"

    return HealthResponse(
        status=overall_status,
        version=__version__,
        service="tidy-ai-backend",
        host=settings.host,
        port=settings.port,
        database_connected=db_ok,
        ollama_configured=bool(settings.ollama_base_url),
        ollama_model=settings.ollama_model,
        timestamp=datetime.now(timezone.utc),
    )


@app.get(
    "/api/ollama/status",
    response_model=OllamaStatusResponse,
    tags=["Ollama AI"],
)
@app.get(
    "/api/v1/ai/health",
    response_model=OllamaStatusResponse,
    tags=["Ollama AI"],
    include_in_schema=False,
)
async def get_ollama_status():
    """Check availability of local Ollama server and configured model."""
    return await ollama_service.get_status()


@app.post(
    "/api/ollama/test",
    response_model=OllamaGenerateResponse,
    tags=["Ollama AI"],
)
async def test_ollama_inference(req: OllamaGenerateRequest):
    """Test local Ollama completion without modifying any files or scanning personal directories."""
    try:
        raw_text, duration_ms = await ollama_service.generate_completion(
            prompt=req.prompt,
            system_prompt=req.system_prompt,
            temperature=req.temperature,
            enforce_json=False,
        )
        return OllamaGenerateResponse(
            model=ollama_service.model_name,
            response_text=raw_text,
            duration_ms=duration_ms,
        )
    except OllamaConnectionError as exc:
        msg = str(exc)
        if not msg.lower().startswith("local ollama server is unreachable"):
            msg = f"Local Ollama server is unreachable: {msg}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=msg,
        )
    except OllamaModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested Ollama model is not installed: {str(exc)}",
        )
    except OllamaTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Ollama inference timed out: {str(exc)}",
        )
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama error: {str(exc)}",
        )


# ==============================================================================
# Approved Roots Management Endpoints
# ==============================================================================

@app.post(
    "/api/roots/approve",
    response_model=ApprovedRoot,
    status_code=status.HTTP_201_CREATED,
    tags=["Approved Roots"],
)
async def approve_directory_root(payload: ApprovedRootCreate):
    """Validate, canonicalize, and register a user-approved directory boundary.

    Enforces that filesystem roots or critical system folders are rejected.
    """
    try:
        return roots_registry.approve_root(payload.path, payload.label)
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to register directory root: {str(exc)}",
        )


@app.get(
    "/api/roots",
    response_model=ApprovedRootListResponse,
    tags=["Approved Roots"],
)
async def list_approved_roots():
    """Return all currently registered approved directory roots."""
    return ApprovedRootListResponse(roots=roots_registry.list_roots())


@app.delete(
    "/api/roots/{root_id}",
    status_code=status.HTTP_200_OK,
    tags=["Approved Roots"],
)
async def unregister_approved_root(root_id: str):
    """Remove a previously approved directory boundary."""
    deleted = roots_registry.remove_root(root_id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{root_id}' was not found.",
        )
    return {"message": "Root unregistered successfully.", "id": root_id}


# ==============================================================================
# Secure Read-Only File Scanner Endpoints
# ==============================================================================

@app.post(
    "/api/scan",
    response_model=ScanResponse,
    status_code=status.HTTP_200_OK,
    tags=["Scanner"],
)
async def scan_inventory(req: ScanRequest):
    """Execute a bounded read-only metadata scan of an approved root directory.

    Strictly refuses to follow escaping symlinks or traverse outside the approved boundary.
    Never inspects or modifies file contents.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return scan_approved_root(
            root=approved,
            subpath=req.subpath,
            recursive=req.recursive,
            max_files=req.max_files,
            max_depth=req.max_depth,
        )
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error executing file scan: {str(exc)}",
        )


# ==============================================================================
# Exact Duplicate Detection Endpoints (Detection Only)
# ==============================================================================

@app.post(
    "/api/duplicates",
    response_model=DuplicateDetectionResponse,
    status_code=status.HTTP_200_OK,
    tags=["Duplicates"],
)
async def find_duplicates(req: DuplicateDetectionRequest):
    """Detect exact content duplicates within an approved root via chunked SHA-256.

    DETECTION ONLY: Never deletes, moves, or alters any file.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return detect_duplicates(
            root=approved,
            subpath=req.subpath,
            min_size_bytes=req.min_size_bytes,
        )
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error during duplicate detection: {str(exc)}",
        )


# ==============================================================================
# AI Suggestion Engine Endpoints (Phase 5 - Proposal Only)
# ==============================================================================

@app.post(
    "/api/suggestions",
    response_model=SuggestionBatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Suggestions"],
)
async def generate_file_suggestions(req: SuggestionBatchRequest):
    """Generate reviewable AI categorization, clean filename, and destination subfolder proposals.

    PROPOSAL ONLY: Strictly read-only. Never modifies, renames, moves, or deletes any files.
    All model proposals are deterministically validated by backend code.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return await generate_suggestions(
            root=approved,
            subpath=req.subpath,
            file_paths=req.file_paths,
            max_files=req.max_files,
            confidence_threshold=req.confidence_threshold,
        )
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except OllamaConnectionError as exc:
        msg = str(exc)
        if not msg.lower().startswith("local ollama server is unreachable"):
            msg = f"Local Ollama server is unreachable: {msg}"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=msg,
        )
    except OllamaModelNotFoundError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Requested Ollama model is not installed: {str(exc)}",
        )
    except OllamaTimeoutError as exc:
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail=f"Ollama inference timed out: {str(exc)}",
        )
    except OllamaError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Ollama error: {str(exc)}",
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Unexpected error generating suggestions: {str(exc)}",
        )


@app.post(
    "/api/suggestions/stage",
    response_model=SuggestionStageResponse,
    status_code=status.HTTP_200_OK,
    tags=["Suggestions"],
)
async def stage_suggestions_endpoint(req: SuggestionStageRequest):
    """Validate and stage accepted AI suggestions into the operations queue.

    Deterministic safety:
    - Filters out invalid and colliding suggestions.
    - Excludes items where source and target are identical (no-op).
    - Classifies operations as 'move' or 'rename'.
    - Returns summary counts of staged vs skipped items.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    staged_ops, counts = stage_accepted_suggestions_batch(
        suggestions=req.suggestions,
        decisions=req.decisions,
        edits=req.edits,
    )

    return SuggestionStageResponse(
        operations=staged_ops,
        counts=counts,
    )


# ==============================================================================
# Rule-Based File Classification Endpoints
# ==============================================================================

@app.post(
    "/api/classify",
    response_model=ClassificationBatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Classification"],
)
@app.post(
    "/api/v1/classify",
    response_model=ClassificationBatchResponse,
    status_code=status.HTTP_200_OK,
    tags=["Classification"],
    include_in_schema=False,
)
async def classify_files_endpoint(req: ClassificationBatchRequest):
    """Classify files deterministically using explicit Python rules first.

    Evaluates file extension, standard MIME type, and filename patterns.
    Flags ambiguous items as 'Needs review'.
    Never mutates files or executes external APIs.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return classify_files_batch(
            root=approved,
            subpath=req.subpath,
            file_paths=req.file_paths,
            max_files=req.max_files,
        )
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Classification error: {str(exc)}",
        )


# ==============================================================================
# Operations & Safe Reversible Execution Endpoints (Phase 6)
# ==============================================================================

@app.post(
    "/api/operations/preview",
    response_model=DryRunResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
)
@app.post(
    "/api/v1/operations/preview",
    response_model=DryRunResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    include_in_schema=False,
)
async def preview_operations_endpoint(req: DryRunRequest):
    """Simulate staged file operations in read-only dry-run mode.

    NEVER moves, renames, deletes files, or creates directories.
    Simulates collision detection, safety containment checks, and missing file warnings.
    """
    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return simulate_dry_run(root=approved, operations=req.operations)
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Dry run simulation error: {str(exc)}",
        )


@app.post(
    "/api/operations/apply",
    response_model=ApplyOperationsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
)
@app.post(
    "/api/v1/operations/apply",
    response_model=ApplyOperationsResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    include_in_schema=False,
)
async def apply_operations_endpoint(req: ApplyOperationsRequest):
    """Execute confirmed file operations on disk within approved root.

    ZERO UNCONFIRMED MUTATIONS: confirmed=True is strictly required.
    Performs pre-flight atomic revalidation immediately prior to every move.
    Fails closed on collisions (zero silent overwrites).
    Records batch and items in SQLite audit ledger.
    """
    if not req.confirmed:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Explicit user confirmation (confirmed: true) is strictly required to execute operations.",
        )

    approved = roots_registry.get_root(req.root_id)
    if not approved:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Approved root with id '{req.root_id}' is not registered.",
        )

    try:
        return apply_operation_plan(root=approved, operations=req.operations, confirmed=req.confirmed)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except SecurityBoundaryError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Operation application error: {str(exc)}",
        )


@app.post(
    "/api/operations/{batch_id}/undo",
    response_model=UndoResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
)
@app.post(
    "/api/v1/operations/{batch_id}/undo",
    response_model=UndoResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    include_in_schema=False,
)
async def undo_batch_endpoint(batch_id: str):
    """Safely undo a previously executed operation batch.

    Reverts files back to their original recorded locations.
    Fails closed if the original path is currently occupied or if the target file has moved.
    """
    try:
        return undo_operation_batch(batch_id=batch_id)
    except KeyError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(exc),
        )
    except (ValueError, FileNotFoundError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Undo execution error: {str(exc)}",
        )


@app.get(
    "/api/operations/history",
    response_model=OperationHistoryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
)
@app.get(
    "/api/v1/operations/history",
    response_model=OperationHistoryResponse,
    status_code=status.HTTP_200_OK,
    tags=["Operations"],
    include_in_schema=False,
)
async def get_history_endpoint(root_id: str = "", limit: int = 50):
    """Retrieve historical operation batches and their items from SQLite ledger."""
    root_path = ""
    if root_id:
        approved = roots_registry.get_root(root_id)
        if approved:
            root_path = approved.canonical_path

    try:
        return get_operation_history(root_path=root_path, limit=limit)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Error fetching operations history: {str(exc)}",
        )
