/**
 * API client and types for interacting with TidyAI backend.
 * Binds strictly to local backend on 127.0.0.1:8765.
 */

export const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://127.0.0.1:8765";

export interface HealthResponse {
  status: "ok" | "degraded" | string;
  version: string;
  service: string;
  host: string;
  port: number;
  database_connected: boolean;
  ollama_configured: boolean;
  ollama_model: string;
  timestamp: string;
}

export interface OllamaStatusResponse {
  state: "healthy" | "server_unreachable" | "model_missing";
  reachable: boolean;
  version?: string | null;
  model_installed: boolean;
  model_name: string;
  available_models: string[];
  base_url: string;
  message: string;
  install_command?: string | null;
}

export interface OllamaGenerateResponse {
  model: string;
  response_text: string;
  duration_ms: number;
}

export interface ApprovedRoot {
  id: string;
  canonical_path: string;
  label: string;
  added_at: string;
}

export interface ApprovedRootListResponse {
  roots: ApprovedRoot[];
}

export type BroadFileType =
  | "document"
  | "image"
  | "audio"
  | "video"
  | "archive"
  | "code"
  | "other";

export interface FileEntry {
  relative_path: string;
  filename: string;
  extension: string;
  size_bytes: number;
  file_type: BroadFileType;
  created_at?: string | null;
  modified_at?: string | null;
  is_symlink: boolean;
}

export interface ScanWarning {
  path: string;
  warning_type: string;
  message: string;
}

export interface ScanSummary {
  root_id: string;
  root_path: string;
  total_files: number;
  total_size_bytes: number;
  directories_scanned: number;
  skipped_count: number;
  duration_ms: number;
  truncated: boolean;
}

export interface ScanRequest {
  root_id: string;
  subpath?: string;
  recursive?: boolean;
  max_files?: number;
  max_depth?: number;
}

export interface ScanResponse {
  scan_id: string;
  summary: ScanSummary;
  files: FileEntry[];
  warnings: ScanWarning[];
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE_URL}/api/health`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch health status: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchOllamaStatus(): Promise<OllamaStatusResponse> {
  const res = await fetch(`${API_BASE_URL}/api/ollama/status`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch Ollama status: ${res.statusText}`);
  }
  return res.json();
}

export async function fetchApprovedRoots(): Promise<ApprovedRootListResponse> {
  const res = await fetch(`${API_BASE_URL}/api/roots`, {
    cache: "no-store",
  });
  if (!res.ok) {
    throw new Error(`Failed to fetch approved roots: ${res.statusText}`);
  }
  return res.json();
}

export async function approveRoot(
  path: string,
  label?: string
): Promise<ApprovedRoot> {
  const res = await fetch(`${API_BASE_URL}/api/roots/approve`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ path, label }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Failed to approve root: ${res.statusText}`);
  }
  return res.json();
}

export async function deleteApprovedRoot(
  rootId: string
): Promise<{ message: string; id: string }> {
  const res = await fetch(`${API_BASE_URL}/api/roots/${rootId}`, {
    method: "DELETE",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to delete approved root: ${res.statusText}`
    );
  }
  return res.json();
}

export async function executeScan(req: ScanRequest): Promise<ScanResponse> {
  const res = await fetch(`${API_BASE_URL}/api/scan`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(errorData.detail || `Scan failed: ${res.statusText}`);
  }
  return res.json();
}

export interface DuplicateFileEntry {
  relative_path: string;
  filename: string;
  extension: string;
  size_bytes: number;
  modified_at?: string | null;
}

export interface DuplicateGroup {
  sha256: string;
  size_bytes: number;
  file_count: number;
  potential_savings_bytes: number;
  files: DuplicateFileEntry[];
}

export interface DuplicateWarning {
  path: string;
  warning_type: string;
  message: string;
}

export interface DuplicateSummary {
  root_id: string;
  root_path: string;
  total_files_evaluated: number;
  candidate_files_hashed: number;
  duplicate_groups_count: number;
  duplicate_files_count: number;
  potential_savings_bytes: number;
  duration_ms: number;
}

export interface DuplicateDetectionRequest {
  root_id: string;
  subpath?: string;
  min_size_bytes?: number;
}

export interface DuplicateDetectionResponse {
  detection_id: string;
  notice: string;
  summary: DuplicateSummary;
  groups: DuplicateGroup[];
  warnings: DuplicateWarning[];
}

export async function executeDuplicateDetection(
  req: DuplicateDetectionRequest
): Promise<DuplicateDetectionResponse> {
  const res = await fetch(`${API_BASE_URL}/api/duplicates`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Duplicate detection failed: ${res.statusText}`
    );
  }
  return res.json();
}

export async function testOllamaInference(
  prompt: string,
  systemPrompt?: string
): Promise<OllamaGenerateResponse> {
  const res = await fetch(`${API_BASE_URL}/api/ollama/test`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ prompt, system_prompt: systemPrompt }),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Ollama inference test failed: ${res.statusText}`
    );
  }
  return res.json();
}

export interface SuggestionItem {
  file_id: string;
  root_id?: string;
  original_filename?: string;
  original_absolute_path?: string;
  current_relative_path: string;
  category: string;
  proposed_filename: string;
  proposed_subfolder: string;
  proposed_relative_path: string;
  destination_absolute_path?: string;
  rationale: string;
  confidence: number;
  is_ambiguous: boolean;
  collision_detected: boolean;
  collision_details?: string | null;
  is_valid: boolean;
  validation_error?: string | null;
  validation_status?: "valid" | "collision" | "invalid" | "no_change" | string;
  operation_type?: "move" | "rename" | "organize" | "none" | string;
}

export interface SuggestionWarning {
  path: string;
  warning_type: string;
  message: string;
}

export interface SuggestionSummary {
  root_id: string;
  root_path: string;
  total_files_analyzed: number;
  suggestions_generated: number;
  ambiguous_count: number;
  collisions_count: number;
  model_used: string;
  duration_ms: number;
}

export interface SuggestionBatchRequest {
  root_id: string;
  subpath?: string;
  file_paths?: string[];
  max_files?: number;
  confidence_threshold?: number;
}

export interface SuggestionBatchResponse {
  batch_id: string;
  notice: string;
  summary: SuggestionSummary;
  suggestions: SuggestionItem[];
  warnings: SuggestionWarning[];
}

export async function executeSuggestions(
  req: SuggestionBatchRequest
): Promise<SuggestionBatchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/suggestions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `AI suggestions request failed: ${res.statusText}`
    );
  }
  return res.json();
}

export interface SuggestionStageRequest {
  root_id: string;
  suggestions: SuggestionItem[];
  decisions: Record<string, string>;
  edits?: Record<string, { proposed_filename?: string; proposed_subfolder?: string }>;
}

export interface SuggestionStageResponse {
  operations: OperationPlanItem[];
  counts: {
    staged: number;
    skipped_no_change: number;
    skipped_invalid: number;
    skipped_collision: number;
    skipped_unapproved: number;
  };
  notice: string;
}

export async function stageSuggestions(
  req: SuggestionStageRequest
): Promise<SuggestionStageResponse> {
  const res = await fetch(`${API_BASE_URL}/api/suggestions/stage`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Staging suggestions failed: ${res.statusText}`
    );
  }
  return res.json();
}

export type FileCategory =
  | "Documents"
  | "Spreadsheets"
  | "Presentations"
  | "Images"
  | "Videos"
  | "Audio"
  | "Archives"
  | "Code"
  | "Datasets"
  | "Other"
  | "Needs review";

export type ClassificationSource =
  | "extension_rule"
  | "mime_rule"
  | "filename_rule"
  | "ollama";

export interface FileClassificationItem {
  relative_path: string;
  filename: string;
  extension: string;
  size_bytes: number;
  category: FileCategory;
  confidence: number;
  source: ClassificationSource;
  reason: string;
  suggested_subfolder: string;
  is_ambiguous: boolean;
}

export interface ClassificationSummary {
  root_id: string;
  root_path: string;
  total_files: number;
  classified_by_rules: number;
  needs_review_count: number;
  categories_count: Record<string, number>;
  duration_ms: number;
}

export interface ClassificationBatchRequest {
  root_id: string;
  subpath?: string;
  file_paths?: string[];
  max_files?: number;
}

export interface ClassificationBatchResponse {
  batch_id: string;
  notice: string;
  summary: ClassificationSummary;
  classifications: FileClassificationItem[];
}

export async function executeClassification(
  req: ClassificationBatchRequest
): Promise<ClassificationBatchResponse> {
  const res = await fetch(`${API_BASE_URL}/api/classify`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Classification request failed: ${res.statusText}`
    );
  }
  return res.json();
}

// ==============================================================================
// Operations, Dry-Run, History & Undo Types & Methods (Phase 6)
// ==============================================================================

export type OperationType = "move" | "rename" | "organize";

export interface OperationPlanItem {
  source_rel_path: string;
  target_rel_path: string;
  operation_type?: OperationType;
  approved?: boolean;
}

export interface DryRunItem {
  source_rel_path: string;
  target_rel_path: string;
  operation_type: string;
  approved: boolean;
  is_safe: boolean;
  validation_error?: string | null;
  will_create_subfolder?: string | null;
  collision_detected: boolean;
  source_exists: boolean;
  target_exists: boolean;
}

export interface DryRunSummary {
  root_id: string;
  root_path: string;
  total_operations: number;
  safe_operations: number;
  blocked_operations: number;
  is_executable: boolean;
}

export interface DryRunRequest {
  root_id: string;
  operations: OperationPlanItem[];
}

export interface DryRunResponse {
  batch_id: string;
  notice: string;
  summary: DryRunSummary;
  items: DryRunItem[];
}

export interface ApplyOperationsRequest {
  root_id: string;
  operations: OperationPlanItem[];
  confirmed: boolean;
}

export interface ExecutedItem {
  id?: string | null;
  source_rel_path: string;
  target_rel_path: string;
  operation_type: string;
  status: "applied" | "failed" | "skipped" | string;
  error_message?: string | null;
  executed_at?: string | null;
  is_undone?: boolean;
}

export interface ApplyOperationsResponse {
  batch_id: string;
  root_id: string;
  root_path: string;
  total_requested: number;
  total_applied: number;
  failed_count: number;
  skipped_count: number;
  status: "completed" | "partial" | "failed" | string;
  items: ExecutedItem[];
  executed_at: string;
}

export interface UndoItem {
  item_id?: string | null;
  source_rel_path: string;
  target_rel_path: string;
  status: "reverted" | "failed" | "skipped" | string;
  error_message?: string | null;
}

export interface UndoResponse {
  batch_id: string;
  total_items: number;
  total_reverted: number;
  blocked_count: number;
  status: "fully_undone" | "partially_undone" | "failed" | string;
  items: UndoItem[];
  undone_at: string;
}

export interface OperationBatchHistoryItem {
  batch_id: string;
  created_at: string;
  approved_root: string;
  root_id?: string | null;
  total_items: number;
  status: string;
  is_dry_run: boolean;
  is_undone: boolean;
  undone_at?: string | null;
  items: ExecutedItem[];
}

export interface OperationHistoryResponse {
  batches: OperationBatchHistoryItem[];
}

export async function executeDryRun(
  req: DryRunRequest
): Promise<DryRunResponse> {
  const res = await fetch(`${API_BASE_URL}/api/operations/preview`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Dry-run preview failed: ${res.statusText}`
    );
  }
  return res.json();
}

export async function executeApplyOperations(
  req: ApplyOperationsRequest
): Promise<ApplyOperationsResponse> {
  const res = await fetch(`${API_BASE_URL}/api/operations/apply`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(req),
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Operation execution failed: ${res.statusText}`
    );
  }
  return res.json();
}

export async function executeUndo(batchId: string): Promise<UndoResponse> {
  const res = await fetch(`${API_BASE_URL}/api/operations/${batchId}/undo`, {
    method: "POST",
  });
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Undo operation failed: ${res.statusText}`
    );
  }
  return res.json();
}

export async function fetchOperationHistory(
  rootId?: string,
  limit: number = 50
): Promise<OperationHistoryResponse> {
  const query = new URLSearchParams();
  if (rootId) query.set("root_id", rootId);
  query.set("limit", limit.toString());

  const res = await fetch(
    `${API_BASE_URL}/api/operations/history?${query.toString()}`,
    {
      cache: "no-store",
    }
  );
  if (!res.ok) {
    const errorData = await res.json().catch(() => ({}));
    throw new Error(
      errorData.detail || `Failed to fetch history: ${res.statusText}`
    );
  }
  return res.json();
}
