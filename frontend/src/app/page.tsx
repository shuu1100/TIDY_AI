"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  LayoutDashboard,
  FolderOpen,
  Folder,
  FolderPlus,
  FolderX,
  FolderInput,
  Files,
  FileText,
  FileCode,
  FileArchive,
  FileImage,
  FileAudio,
  FileVideo,
  Copy,
  Wand2,
  ListChecks,
  History,
  RotateCcw,
  Sliders,
  RefreshCw,
  ShieldCheck,
  CheckCircle2,
  AlertTriangle,
  AlertCircle,
  Info,
  Check,
  X,
  Search,
  SearchX,
  ArrowUp,
  ArrowDown,
  ArrowRight,
  ChevronRight,
  ChevronLeft,
  Edit3,
  Eye,
  Clock,
  Trash2,
  Zap,
  Plus,
  Server,
  Database,
  Cpu,
} from "lucide-react";
import {
  fetchHealth,
  fetchOllamaStatus,
  fetchApprovedRoots,
  approveRoot,
  deleteApprovedRoot,
  executeScan,
  executeDuplicateDetection,
  executeSuggestions,
  testOllamaInference,
  executeDryRun,
  executeApplyOperations,
  executeUndo,
  fetchOperationHistory,
  HealthResponse,
  OllamaStatusResponse,
  ApprovedRoot,
  ScanResponse,
  DuplicateDetectionResponse,
  SuggestionBatchResponse,
  OperationPlanItem,
  DryRunResponse,
  ApplyOperationsResponse,
  OperationBatchHistoryItem,
} from "@/lib/api";

type TabKey =
  | "overview"
  | "folders"
  | "all-files"
  | "duplicates"
  | "ai-suggestions"
  | "review-changes"
  | "history"
  | "settings-ai-status";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function formatDate(dateStr?: string | null): string {
  if (!dateStr) return "—";
  try {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
  } catch {
    return dateStr;
  }
}

export default function Home() {
  // Navigation State
  const [activeTab, setActiveTab] = useState<TabKey>("overview");

  // Core System States
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ollama, setOllama] = useState<OllamaStatusResponse | null>(null);
  const [roots, setRoots] = useState<ApprovedRoot[]>([]);
  const [selectedRootId, setSelectedRootId] = useState<string>("");
  const [lastChecked, setLastChecked] = useState<string>("");

  // Scan & Inventory State
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [fileSearch, setFileSearch] = useState<string>("");
  const [categoryFilter, setCategoryFilter] = useState<string>("all");
  const [sortBy, setSortBy] = useState<"modified" | "name" | "size">("modified");
  const [sortAsc, setSortAsc] = useState<boolean>(false);
  const [selectedFiles, setSelectedFiles] = useState<Set<string>>(new Set());
  const [currentPage, setCurrentPage] = useState<number>(1);
  const itemsPerPage = 25;

  // Duplicates State
  const [duplicateResult, setDuplicateResult] = useState<DuplicateDetectionResponse | null>(null);

  // AI Suggestions State
  const [suggestionResult, setSuggestionResult] = useState<SuggestionBatchResponse | null>(null);
  const [suggestionMaxFiles, setSuggestionMaxFiles] = useState<number>(25);
  const [suggestionConfidenceThreshold, setSuggestionConfidenceThreshold] = useState<number>(0.7);
  const [userDecisions, setUserDecisions] = useState<Record<string, "accepted" | "rejected">>({});
  const [userEdits, setUserEdits] = useState<
    Record<string, { proposed_filename: string; proposed_subfolder: string }>
  >({});
  const [editingFileId, setEditingFileId] = useState<string | null>(null);
  const [tempEditFilename, setTempEditFilename] = useState<string>("");
  const [tempEditSubfolder, setTempEditSubfolder] = useState<string>("");

  // Review & Operations State
  const [stagedPlan, setStagedPlan] = useState<OperationPlanItem[]>([]);
  const [dryRunResult, setDryRunResult] = useState<DryRunResponse | null>(null);
  const [showConfirmModal, setShowConfirmModal] = useState<boolean>(false);
  const [applyConfirmed, setApplyConfirmed] = useState<boolean>(false);
  const [applyResult, setApplyResult] = useState<ApplyOperationsResponse | null>(null);

  // History State
  const [historyList, setHistoryList] = useState<OperationBatchHistoryItem[]>([]);
  const [expandedBatchId, setExpandedBatchId] = useState<string | null>(null);

  // Add Folder Modal State
  const [showAddFolderModal, setShowAddFolderModal] = useState<boolean>(false);
  const [newFolderPath, setNewFolderPath] = useState<string>("");
  const [newFolderLabel, setNewFolderLabel] = useState<string>("");
  const [addFolderError, setAddFolderError] = useState<string | null>(null);

  // Loading States
  const [refreshing, setRefreshing] = useState<boolean>(false);
  const [scanning, setScanning] = useState<boolean>(false);
  const [detectingDuplicates, setDetectingDuplicates] = useState<boolean>(false);
  const [generatingSuggestions, setGeneratingSuggestions] = useState<boolean>(false);
  const [dryRunning, setDryRunning] = useState<boolean>(false);
  const [applying, setApplying] = useState<boolean>(false);
  const [undoingBatchId, setUndoingBatchId] = useState<string | null>(null);
  const [testingOllama, setTestingOllama] = useState<boolean>(false);
  const [testPingResult, setTestPingResult] = useState<{
    duration_ms: number;
    response_text: string;
  } | null>(null);

  // Global Error / Diagnostic Notice State
  const [error, setError] = useState<string | null>(null);
  const [dismissedNotice, setDismissedNotice] = useState<boolean>(false);

  // Selected Root Object
  const selectedRoot = useMemo(() => {
    return roots.find((r) => r.id === selectedRootId) || roots[0] || null;
  }, [roots, selectedRootId]);

  // Master refresh function
  const refreshAll = useCallback(async () => {
    setRefreshing(true);
    try {
      const [healthData, ollamaData, rootsData, historyData] = await Promise.all([
        fetchHealth().catch((err) => {
          console.error("Health fetch failed:", err);
          return null;
        }),
        fetchOllamaStatus().catch((err) => {
          console.error("Ollama fetch failed:", err);
          return null;
        }),
        fetchApprovedRoots().catch((err) => {
          console.error("Roots fetch failed:", err);
          return { roots: [] };
        }),
        fetchOperationHistory("", 50).catch((err) => {
          console.error("History fetch failed:", err);
          return { batches: [] };
        }),
      ]);

      setHealth(healthData);
      setOllama(ollamaData);
      setRoots(rootsData.roots);
      setHistoryList(historyData.batches);
      setLastChecked(new Date().toLocaleTimeString());

      if (rootsData.roots.length > 0 && !selectedRootId) {
        setSelectedRootId(rootsData.roots[0].id);
      }
      setError(null);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "System synchronization error";
      setError(msg);
    } finally {
      setRefreshing(false);
    }
  }, [selectedRootId]);

  // Initial load
  useEffect(() => {
    let isMounted = true;
    const initLoad = async () => {
      try {
        const [healthData, ollamaData, rootsData, historyData] = await Promise.all([
          fetchHealth().catch(() => null),
          fetchOllamaStatus().catch(() => null),
          fetchApprovedRoots().catch(() => ({ roots: [] })),
          fetchOperationHistory("", 50).catch(() => ({ batches: [] })),
        ]);
        if (!isMounted) return;
        setHealth(healthData);
        setOllama(ollamaData);
        setRoots(rootsData.roots);
        setHistoryList(historyData.batches);
        setLastChecked(new Date().toLocaleTimeString());
        if (rootsData.roots.length > 0) {
          setSelectedRootId((prev) => prev || rootsData.roots[0].id);
        }
      } catch {
        // ignore
      }
    };
    void initLoad();
    return () => {
      isMounted = false;
    };
  }, []);

  // Handle Scan action
  const handleScan = useCallback(
    async (rootIdToScan?: string) => {
      const targetId = rootIdToScan || selectedRoot?.id;
      if (!targetId) {
        setError("Please select or approve a folder first.");
        return;
      }
      setScanning(true);
      setError(null);
      try {
        const res = await executeScan({ root_id: targetId });
        setScanResult(res);
        setSelectedFiles(new Set());
        setCurrentPage(1);
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Scan failed";
        setError(msg);
      } finally {
        setScanning(false);
      }
    },
    [selectedRoot]
  );

  // Handle Duplicate Detection
  const handleDetectDuplicates = useCallback(async () => {
    if (!selectedRoot) {
      setError("Please select an approved folder first.");
      return;
    }
    setDetectingDuplicates(true);
    setError(null);
    try {
      const res = await executeDuplicateDetection({ root_id: selectedRoot.id });
      setDuplicateResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Duplicate detection failed";
      setError(msg);
    } finally {
      setDetectingDuplicates(false);
    }
  }, [selectedRoot]);

  // Handle AI Suggestions
  const handleGenerateSuggestions = useCallback(async () => {
    if (!selectedRoot) {
      setError("Please select an approved folder first.");
      return;
    }
    setGeneratingSuggestions(true);
    setError(null);
    try {
      const res = await executeSuggestions({
        root_id: selectedRoot.id,
        max_files: suggestionMaxFiles,
        confidence_threshold: suggestionConfidenceThreshold,
      });
      setSuggestionResult(res);
      const initialDecisions: Record<string, "accepted" | "rejected"> = {};
      res.suggestions.forEach((item) => {
        if (item.is_valid && !item.collision_detected && !item.is_ambiguous) {
          initialDecisions[item.file_id] = "accepted";
        }
      });
      setUserDecisions(initialDecisions);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate AI suggestions";
      setError(msg);
    } finally {
      setGeneratingSuggestions(false);
    }
  }, [selectedRoot, suggestionMaxFiles, suggestionConfidenceThreshold]);

  // Stage accepted suggestions into Operations Queue
  const handleStageAccepted = useCallback(() => {
    if (!suggestionResult) return;

    const newOperations: OperationPlanItem[] = [];
    suggestionResult.suggestions.forEach((item) => {
      const decision = userDecisions[item.file_id];
      if (decision === "accepted") {
        const customEdit = userEdits[item.file_id];
        const targetFilename = customEdit?.proposed_filename || item.proposed_filename;
        const targetSubfolder = customEdit?.proposed_subfolder || item.proposed_subfolder;

        const cleanSubfolder = targetSubfolder.replace(/^[\\/]+|[\\/]+$/g, "");
        const targetRelPath = cleanSubfolder
          ? `${cleanSubfolder}/${targetFilename}`
          : targetFilename;

        newOperations.push({
          source_rel_path: item.current_relative_path,
          target_rel_path: targetRelPath,
          operation_type: "move",
          approved: true,
        });
      }
    });

    if (newOperations.length === 0) {
      setError("No accepted suggestions to stage.");
      return;
    }

    setStagedPlan(newOperations);
    setDryRunResult(null);
    setActiveTab("review-changes");
  }, [suggestionResult, userDecisions, userEdits]);

  // Dry-Run Simulation
  const handleRunDryRun = useCallback(async () => {
    if (!selectedRoot || stagedPlan.length === 0) {
      setError("No staged operations to simulate.");
      return;
    }
    setDryRunning(true);
    setError(null);
    try {
      const res = await executeDryRun({
        root_id: selectedRoot.id,
        operations: stagedPlan,
      });
      setDryRunResult(res);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Dry-run simulation failed";
      setError(msg);
    } finally {
      setDryRunning(false);
    }
  }, [selectedRoot, stagedPlan]);

  // Apply Operations with Confirmed Modal
  const handleApplyConfirmed = useCallback(async () => {
    if (!selectedRoot || stagedPlan.length === 0) return;
    if (!applyConfirmed) {
      setError("Please check the confirmation box before applying operations.");
      return;
    }

    setApplying(true);
    setError(null);
    try {
      const res = await executeApplyOperations({
        root_id: selectedRoot.id,
        operations: stagedPlan,
        confirmed: true,
      });
      setApplyResult(res);
      setShowConfirmModal(false);
      setStagedPlan([]);
      setDryRunResult(null);
      setApplyConfirmed(false);

      await handleScan(selectedRoot.id);
      const historyData = await fetchOperationHistory("", 50);
      setHistoryList(historyData.batches);
      setActiveTab("history");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to apply operations";
      setError(msg);
    } finally {
      setApplying(false);
    }
  }, [selectedRoot, stagedPlan, applyConfirmed, handleScan]);

  // Safe Undo
  const handleUndo = useCallback(
    async (batchId: string) => {
      setUndoingBatchId(batchId);
      setError(null);
      try {
        await executeUndo(batchId);
        const historyData = await fetchOperationHistory("", 50);
        setHistoryList(historyData.batches);
        if (selectedRootId) {
          await handleScan(selectedRootId);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Safe undo failed";
        setError(msg);
      } finally {
        setUndoingBatchId(null);
      }
    },
    [selectedRootId, handleScan]
  );

  // Add Folder Submission
  const handleApproveFolder = useCallback(async () => {
    if (!newFolderPath.trim()) {
      setAddFolderError("Folder path is required.");
      return;
    }
    setAddFolderError(null);
    try {
      const approved = await approveRoot(newFolderPath.trim(), newFolderLabel.trim() || undefined);
      setShowAddFolderModal(false);
      setNewFolderPath("");
      setNewFolderLabel("");
      await refreshAll();
      setSelectedRootId(approved.id);
      await handleScan(approved.id);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve folder";
      setAddFolderError(msg);
    }
  }, [newFolderPath, newFolderLabel, refreshAll, handleScan]);

  // Revoke Folder
  const handleRevokeFolder = useCallback(
    async (rootId: string) => {
      if (!confirm("Revoke TidyAI sandboxed access to this folder?")) return;
      try {
        await deleteApprovedRoot(rootId);
        await refreshAll();
        if (selectedRootId === rootId) {
          setSelectedRootId("");
          setScanResult(null);
        }
      } catch (err: unknown) {
        const msg = err instanceof Error ? err.message : "Failed to revoke folder";
        setError(msg);
      }
    },
    [refreshAll, selectedRootId]
  );

  // Test Ollama Inference Ping
  const handleTestOllama = useCallback(async () => {
    setTestingOllama(true);
    setTestPingResult(null);
    setError(null);
    try {
      const res = await testOllamaInference("Reply with exactly: 'TidyAI Local Engine OK'");
      setTestPingResult({
        duration_ms: res.duration_ms,
        response_text: res.response_text,
      });
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Inference ping failed";
      setError(msg);
    } finally {
      setTestingOllama(false);
    }
  }, []);

  // Filtered & Sorted Files for "All Files" screen
  const filteredFiles = useMemo(() => {
    if (!scanResult?.files) return [];
    let list = [...scanResult.files];

    if (categoryFilter !== "all") {
      list = list.filter((f) => f.file_type === categoryFilter);
    }

    if (fileSearch.trim()) {
      const q = fileSearch.toLowerCase();
      list = list.filter(
        (f) =>
          f.filename.toLowerCase().includes(q) ||
          f.relative_path.toLowerCase().includes(q) ||
          f.extension.toLowerCase().includes(q)
      );
    }

    list.sort((a, b) => {
      if (sortBy === "name") {
        return sortAsc
          ? a.filename.localeCompare(b.filename)
          : b.filename.localeCompare(a.filename);
      } else if (sortBy === "size") {
        return sortAsc ? a.size_bytes - b.size_bytes : b.size_bytes - a.size_bytes;
      } else {
        const tA = a.modified_at ? new Date(a.modified_at).getTime() : 0;
        const tB = b.modified_at ? new Date(b.modified_at).getTime() : 0;
        return sortAsc ? tA - tB : tB - tA;
      }
    });

    return list;
  }, [scanResult, categoryFilter, fileSearch, sortBy, sortAsc]);

  const totalPages = Math.max(1, Math.ceil(filteredFiles.length / itemsPerPage));
  const paginatedFiles = useMemo(() => {
    const start = (currentPage - 1) * itemsPerPage;
    return filteredFiles.slice(start, start + itemsPerPage);
  }, [filteredFiles, currentPage]);

  const categoryCounts = useMemo(() => {
    const counts: Record<string, number> = {
      all: scanResult?.files.length || 0,
      document: 0,
      image: 0,
      code: 0,
      archive: 0,
      audio: 0,
      video: 0,
      other: 0,
    };
    scanResult?.files.forEach((f) => {
      counts[f.file_type] = (counts[f.file_type] || 0) + 1;
    });
    return counts;
  }, [scanResult]);

  const selectedBytesTotal = useMemo(() => {
    if (!scanResult?.files) return 0;
    return scanResult.files
      .filter((f) => selectedFiles.has(f.relative_path))
      .reduce((acc, f) => acc + f.size_bytes, 0);
  }, [scanResult, selectedFiles]);

  return (
    <div className="h-screen w-screen flex flex-col bg-[#F7F6F2] text-[#292A26] overflow-hidden select-none font-sans">
      {/* 1. FIXED HEIGHT DESKTOP APPLICATION HEADER (48px / h-12) */}
      <header className="h-12 w-full bg-[#F0EFE9] border-b border-[#E5E3DC] px-4 flex items-center justify-between shrink-0 z-30 min-w-0">
        {/* Left: Folder Logo, Brand Name & Version */}
        <div className="flex items-center gap-2.5 min-w-0 shrink-0">
          <div className="w-7 h-7 rounded bg-[#E5B94F] flex items-center justify-center text-[#292A26] shadow-xs shrink-0">
            <Folder className="w-4 h-4" />
          </div>
          <span className="font-semibold text-[15px] tracking-tight text-[#292A26]">
            TidyAI
          </span>
          <span className="font-tabular text-[11px] text-[#77786F] bg-white px-1.5 py-0.5 rounded border border-[#E5E3DC]">
            v{health?.version || "1.4.2"}
          </span>
        </div>

        {/* Right: Local Privacy Indicator, Engine Status & Refresh */}
        <div className="flex items-center gap-2 sm:gap-3 shrink-0">
          {/* Privacy Pill */}
          <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-white border border-[#E5E3DC] text-[11px] font-medium text-[#292A26]">
            <ShieldCheck className="w-3.5 h-3.5 text-[#136B4D]" />
            <span>Local & Private</span>
          </div>

          {/* Engine Status */}
          <div className="hidden sm:flex items-center gap-1.5 text-xs text-[#77786F]">
            {ollama?.state === "healthy" ? (
              <>
                <CheckCircle2 className="w-3.5 h-3.5 text-[#136B4D]" />
                <span className="truncate max-w-[160px]">Engine Ready ({ollama.model_name})</span>
              </>
            ) : ollama?.state === "model_missing" ? (
              <>
                <AlertTriangle className="w-3.5 h-3.5 text-[#785A00]" />
                <span>Model Missing</span>
              </>
            ) : (
              <>
                <AlertCircle className="w-3.5 h-3.5 text-[#BA1A1A]" />
                <span>Ollama Offline</span>
              </>
            )}
          </div>

          {/* Refresh Button */}
          <button
            onClick={refreshAll}
            disabled={refreshing}
            className="p-1.5 text-[#77786F] hover:text-[#292A26] hover:bg-[#E5E3DC] rounded transition-colors"
            title={`Refresh all system data (Last: ${lastChecked || "just now"})`}
            type="button"
          >
            <RefreshCw className={`w-4 h-4 ${refreshing ? "animate-spin" : ""}`} />
          </button>
        </div>
      </header>

      {/* DISMISSIBLE DIAGNOSTIC NOTICE BANNER */}
      {(!dismissedNotice && (ollama?.state !== "healthy" || error)) && (
        <div className="bg-[#FEF3C7] border-b border-[#FDE68A] px-4 py-2 flex items-center justify-between text-xs text-[#92400E] shrink-0 min-w-0">
          <div className="flex items-center gap-2 truncate">
            <Info className="w-4 h-4 text-[#B45309] shrink-0" />
            <span className="truncate">
              {error ? (
                <>Notice: {error}</>
              ) : ollama?.state === "server_unreachable" ? (
                <>
                  Local Ollama daemon is offline. Run{" "}
                  <code className="bg-[#FDE68A] px-1 py-0.5 rounded font-tabular text-[#292A26]">
                    ollama serve
                  </code>{" "}
                  to enable proposals.
                </>
              ) : (
                <>
                  Model <code className="font-semibold text-[#292A26]">qwen3:4b</code> not found. Run{" "}
                  <code className="bg-[#FDE68A] px-1 py-0.5 rounded font-tabular text-[#292A26]">
                    ollama pull qwen3:4b
                  </code>
                </>
              )}
            </span>
          </div>
          <button
            onClick={() => setDismissedNotice(true)}
            className="text-[#92400E] hover:text-[#292A26] p-0.5 rounded shrink-0 ml-2"
            title="Dismiss notice"
            type="button"
          >
            <X className="w-3.5 h-3.5" />
          </button>
        </div>
      )}

      {/* 2. MAIN APPLICATION WORKSPACE (SIDEBAR + MAIN CANVAS) */}
      <div className="flex-1 flex overflow-hidden min-h-0">
        {/* LEFT NAVIGATION SIDEBAR (224px / w-56) */}
        <aside className="w-56 shrink-0 bg-[#F0EFE9] border-r border-[#E5E3DC] flex flex-col justify-between p-2 overflow-y-auto min-h-0">
          {/* Navigation Items with Uniform Heights and Aligned Labels */}
          <nav className="flex flex-col gap-1">
            {/* 1. Overview */}
            <button
              onClick={() => setActiveTab("overview")}
              className={`h-9 px-3 rounded-md flex items-center gap-2.5 text-[13px] transition-colors w-full ${
                activeTab === "overview"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <LayoutDashboard className="w-4 h-4 shrink-0 text-inherit" />
              <span className="truncate">Overview</span>
            </button>

            {/* 2. Folders */}
            <button
              onClick={() => setActiveTab("folders")}
              className={`h-9 px-3 rounded-md flex items-center justify-between text-[13px] transition-colors w-full ${
                activeTab === "folders"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <div className="flex items-center gap-2.5 truncate">
                <FolderOpen className="w-4 h-4 shrink-0 text-inherit" />
                <span className="truncate">Approved Folders</span>
              </div>
              <span className="font-tabular text-[11px] px-1.5 py-0.2 rounded bg-[#E5E3DC] text-[#77786F]">
                {roots.length}
              </span>
            </button>

            {/* 3. All Files */}
            <button
              onClick={() => setActiveTab("all-files")}
              className={`h-9 px-3 rounded-md flex items-center justify-between text-[13px] transition-colors w-full ${
                activeTab === "all-files"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <div className="flex items-center gap-2.5 truncate">
                <Files className="w-4 h-4 shrink-0 text-inherit" />
                <span className="truncate">All Files</span>
              </div>
              {scanResult?.summary?.total_files ? (
                <span className="font-tabular text-[11px] px-1.5 py-0.2 rounded bg-[#E5E3DC] text-[#77786F]">
                  {scanResult.summary.total_files}
                </span>
              ) : null}
            </button>

            {/* 4. Duplicates */}
            <button
              onClick={() => setActiveTab("duplicates")}
              className={`h-9 px-3 rounded-md flex items-center justify-between text-[13px] transition-colors w-full ${
                activeTab === "duplicates"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <div className="flex items-center gap-2.5 truncate">
                <Copy className="w-4 h-4 shrink-0 text-inherit" />
                <span className="truncate">Duplicates</span>
              </div>
              {duplicateResult?.summary?.duplicate_groups_count ? (
                <span className="font-tabular text-[11px] px-1.5 py-0.2 rounded bg-[#FFDAD6] text-[#BA1A1A] font-semibold">
                  {duplicateResult.summary.duplicate_groups_count}
                </span>
              ) : null}
            </button>

            {/* 5. AI Suggestions */}
            <button
              onClick={() => setActiveTab("ai-suggestions")}
              className={`h-9 px-3 rounded-md flex items-center justify-between text-[13px] transition-colors w-full ${
                activeTab === "ai-suggestions"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <div className="flex items-center gap-2.5 truncate">
                <Wand2 className="w-4 h-4 shrink-0 text-inherit" />
                <span className="truncate">AI Suggestions</span>
              </div>
              {suggestionResult?.suggestions?.length ? (
                <span className="font-tabular text-[11px] px-1.5 py-0.2 rounded bg-[#FEF3C7] text-[#785A00] font-semibold">
                  {suggestionResult.suggestions.length}
                </span>
              ) : null}
            </button>

            {/* 6. Review Changes */}
            <button
              onClick={() => setActiveTab("review-changes")}
              className={`h-9 px-3 rounded-md flex items-center justify-between text-[13px] transition-colors w-full ${
                activeTab === "review-changes"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <div className="flex items-center gap-2.5 truncate">
                <ListChecks className="w-4 h-4 shrink-0 text-inherit" />
                <span className="truncate">Review Changes</span>
              </div>
              {stagedPlan.length > 0 && (
                <span className="font-tabular text-[11px] px-1.5 py-0.2 rounded bg-[#E5B94F] text-[#292A26] font-semibold">
                  {stagedPlan.length}
                </span>
              )}
            </button>

            {/* 7. History */}
            <button
              onClick={() => setActiveTab("history")}
              className={`h-9 px-3 rounded-md flex items-center gap-2.5 text-[13px] transition-colors w-full ${
                activeTab === "history"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <History className="w-4 h-4 shrink-0 text-inherit" />
              <span className="truncate">History</span>
            </button>

            {/* 8. Settings & AI Status */}
            <button
              onClick={() => setActiveTab("settings-ai-status")}
              className={`h-9 px-3 rounded-md flex items-center gap-2.5 text-[13px] transition-colors w-full ${
                activeTab === "settings-ai-status"
                  ? "bg-white text-[#292A26] font-semibold border border-[#E5E3DC] shadow-xs"
                  : "text-[#77786F] hover:bg-white/60 hover:text-[#292A26] font-medium"
              }`}
              type="button"
            >
              <Sliders className="w-4 h-4 shrink-0 text-inherit" />
              <span className="truncate">Settings & AI Status</span>
            </button>
          </nav>

          {/* Compact Sidebar Footer */}
          <div className="px-2 pt-2 border-t border-[#E5E3DC] flex flex-col gap-1 text-[11px]">
            <div className="flex items-center justify-between text-[#77786F] font-tabular">
              <span className="truncate max-w-[130px]" title={selectedRoot?.canonical_path || "No folder"}>
                {selectedRoot?.label || selectedRoot?.canonical_path?.split(/[\\/]/).pop() || "No Folder"}
              </span>
              <span className="text-[#292A26] bg-[#E5E3DC] px-1 py-0.2 rounded font-semibold text-[10px]">
                RO
              </span>
            </div>
            <div className="flex items-center gap-1.5 text-[#77786F]">
              <span className="w-1.5 h-1.5 rounded-full bg-[#136B4D]" />
              <span>Local Watcher Active</span>
            </div>
          </div>
        </aside>

        {/* MAIN SCROLLABLE CONTENT CANVAS */}
        <main className="flex-1 overflow-y-auto bg-[#F7F6F2] p-4 md:p-6 min-w-0">
          <div className="max-w-6xl mx-auto w-full flex flex-col gap-5 min-w-0">
            {/* SCREEN 1: OVERVIEW */}
            {activeTab === "overview" && (
              <div className="flex flex-col w-full gap-5">
                {/* Header Context & Action Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-lg font-semibold text-[#292A26]">Overview</h1>
                      <span className="text-[11px] bg-[#E5E3DC] text-[#77786F] px-1.5 py-0.5 rounded uppercase font-semibold">
                        Local Only
                      </span>
                    </div>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Local file organizer status across your approved directories.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => setShowAddFolderModal(true)}
                      className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] text-[#292A26] text-xs font-medium flex items-center gap-1.5 border border-[#E5E3DC] shadow-xs transition-colors"
                      type="button"
                    >
                      <FolderPlus className="w-3.5 h-3.5" />
                      <span>Add Folder</span>
                    </button>
                    <button
                      onClick={() => handleScan()}
                      disabled={scanning || roots.length === 0}
                      className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium flex items-center gap-1.5 transition-all shadow-xs disabled:opacity-50"
                      type="button"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
                      <span>{scanning ? "Scanning..." : "Scan Approved Folders"}</span>
                    </button>
                  </div>
                </div>

                {/* 3 Aligned Summary Panels */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-w-0">
                  {/* Panel 1: Approved Folders */}
                  <div className="bg-white p-4 rounded-lg border border-[#E5E3DC] shadow-xs flex flex-col justify-between min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col min-w-0">
                        <span className="text-[11px] font-semibold text-[#77786F] uppercase tracking-wider">
                          Approved Folders
                        </span>
                        <div className="flex items-baseline gap-1.5 mt-1">
                          <span className="text-2xl font-semibold text-[#292A26] font-tabular">
                            {roots.length}
                          </span>
                          <span className="text-xs text-[#77786F]">registered paths</span>
                        </div>
                      </div>
                      <div className="w-8 h-8 rounded bg-[#F0EFE9] flex items-center justify-center text-[#77786F] shrink-0">
                        <Folder className="w-4 h-4" />
                      </div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-[#E5E3DC] flex flex-col gap-1 text-[11px]">
                      {roots.length === 0 ? (
                        <span className="text-[#77786F] italic">No approved folders registered.</span>
                      ) : (
                        roots.slice(0, 3).map((r) => (
                          <div
                            key={r.id}
                            className="flex items-center justify-between font-tabular text-[#292A26] gap-2"
                          >
                            <span className="truncate" title={r.canonical_path}>
                              {r.label || r.canonical_path}
                            </span>
                            <span className="text-[#136B4D] font-semibold text-[10px] shrink-0">OK</span>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                  {/* Panel 2: Scanned Files */}
                  <div className="bg-white p-4 rounded-lg border border-[#E5E3DC] shadow-xs flex flex-col justify-between min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col min-w-0">
                        <span className="text-[11px] font-semibold text-[#77786F] uppercase tracking-wider">
                          Scanned Files
                        </span>
                        <div className="flex items-baseline gap-1.5 mt-1">
                          <span className="text-2xl font-semibold text-[#292A26] font-tabular">
                            {scanResult?.summary?.total_files?.toLocaleString() || "0"}
                          </span>
                          <span className="text-xs text-[#77786F]">indexed files</span>
                        </div>
                      </div>
                      <div className="w-8 h-8 rounded bg-[#F0EFE9] flex items-center justify-center text-[#77786F] shrink-0">
                        <Search className="w-4 h-4" />
                      </div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-[#E5E3DC] flex flex-col gap-1 text-[11px] text-[#77786F]">
                      <div className="flex items-center justify-between">
                        <span>Scan status</span>
                        <span className="text-[#136B4D] font-medium flex items-center gap-1">
                          <span className="w-1.5 h-1.5 rounded-full bg-[#136B4D]" />
                          {scanResult ? "Up to date" : "Pending scan"}
                        </span>
                      </div>
                      <div className="flex items-center justify-between font-tabular">
                        <span>Indexed size</span>
                        <span className="text-[#292A26] font-medium">
                          {formatBytes(scanResult?.summary?.total_size_bytes || 0)}
                        </span>
                      </div>
                    </div>
                  </div>

                  {/* Panel 3: Pending Review */}
                  <div className="bg-white p-4 rounded-lg border border-[#E5E3DC] shadow-xs flex flex-col justify-between min-w-0">
                    <div className="flex items-start justify-between gap-2">
                      <div className="flex flex-col min-w-0">
                        <span className="text-[11px] font-semibold text-[#785A00] uppercase tracking-wider">
                          Pending Review
                        </span>
                        <div className="flex items-baseline gap-1.5 mt-1">
                          <span className="text-2xl font-semibold text-[#292A26] font-tabular">
                            {(suggestionResult?.suggestions?.length || 0) + stagedPlan.length}
                          </span>
                          <span className="text-xs text-[#77786F]">actions queued</span>
                        </div>
                      </div>
                      <div className="w-8 h-8 rounded bg-[#FEF3C7] flex items-center justify-center text-[#785A00] shrink-0">
                        <Clock className="w-4 h-4" />
                      </div>
                    </div>
                    <div className="mt-3 pt-2 border-t border-[#E5E3DC] flex flex-col gap-1 text-[11px] text-[#77786F]">
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <Wand2 className="w-3.5 h-3.5 text-[#785A00]" />
                          <span>AI Proposals</span>
                        </span>
                        <span className="font-tabular font-semibold text-[#292A26] bg-[#F0EFE9] px-1.5 py-0.2 rounded">
                          {suggestionResult?.suggestions?.length || 0}
                        </span>
                      </div>
                      <div className="flex items-center justify-between">
                        <span className="flex items-center gap-1">
                          <FolderInput className="w-3.5 h-3.5 text-[#77786F]" />
                          <span>Staged Operations</span>
                        </span>
                        <span className="font-tabular font-semibold text-[#292A26] bg-[#F0EFE9] px-1.5 py-0.2 rounded">
                          {stagedPlan.length}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Primary Split: Needs Review & Recent Activity */}
                <div className="grid grid-cols-1 lg:grid-cols-12 gap-5 items-start min-w-0">
                  {/* Left: Needs Review (7 cols) */}
                  <div className="lg:col-span-7 flex flex-col gap-3 min-w-0">
                    <div className="flex items-center justify-between pb-2 border-b border-[#E5E3DC]">
                      <div className="flex items-center gap-2">
                        <CheckCircle2 className="w-4 h-4 text-[#785A00]" />
                        <h2 className="text-sm font-semibold text-[#292A26]">Needs Review</h2>
                        <span className="px-1.5 py-0.5 rounded-full bg-[#FEF3C7] text-[#785A00] text-[11px] font-semibold font-tabular">
                          {(suggestionResult?.suggestions?.length || 0) + stagedPlan.length} Items
                        </span>
                      </div>
                      <button
                        onClick={() => setActiveTab("ai-suggestions")}
                        className="text-xs font-medium text-[#785A00] hover:underline flex items-center gap-1"
                        type="button"
                      >
                        <span>View Suggestions</span>
                        <ArrowRight className="w-3 h-3" />
                      </button>
                    </div>

                    {/* Action Box 1: AI Proposals */}
                    <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 min-w-0">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-9 h-9 rounded bg-[#E5B94F] flex items-center justify-center text-[#292A26] shrink-0">
                          <Wand2 className="w-5 h-5" />
                        </div>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs text-[#292A26]">
                              {suggestionResult?.suggestions?.length || 0} Organization Suggestions
                            </span>
                            <span className="text-[10px] font-medium text-[#136B4D] bg-[#E8F5EE] px-1.5 py-0.2 rounded">
                              Low Risk
                            </span>
                          </div>
                          <p className="text-xs text-[#77786F] mt-0.5 truncate">
                            {suggestionResult
                              ? `Generated ${suggestionResult.suggestions.length} proposals via Qwen3 4B.`
                              : "Review AI categorization proposals and customized subfolder structures."}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => setActiveTab("ai-suggestions")}
                        className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] text-[#292A26] text-xs font-medium shrink-0 flex items-center justify-center gap-1 border border-[#E5E3DC] transition-colors"
                        type="button"
                      >
                        <span>Review</span>
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Action Box 2: Staged Operations */}
                    <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] shadow-xs flex flex-col sm:flex-row items-start sm:items-center justify-between gap-3 min-w-0">
                      <div className="flex items-start gap-3 min-w-0">
                        <div className="w-9 h-9 rounded bg-[#F0EFE9] flex items-center justify-center text-[#77786F] shrink-0">
                          <FolderInput className="w-5 h-5" />
                        </div>
                        <div className="flex flex-col min-w-0">
                          <div className="flex items-center gap-1.5">
                            <span className="font-semibold text-xs text-[#292A26]">
                              {stagedPlan.length} Staged File Moves
                            </span>
                            <span className="text-[10px] font-medium text-[#77786F] bg-[#F0EFE9] px-1.5 py-0.2 rounded">
                              {dryRunResult ? "Simulated" : "Pending Dry-Run"}
                            </span>
                          </div>
                          <p className="text-xs text-[#77786F] mt-0.5 truncate">
                            {stagedPlan.length > 0
                              ? "Ready to run pre-flight checks and simulate collision safety."
                              : "No file moves staged. Select and accept suggestions to begin."}
                          </p>
                        </div>
                      </div>
                      <button
                        onClick={() => setActiveTab("review-changes")}
                        disabled={stagedPlan.length === 0}
                        className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shrink-0 flex items-center justify-center gap-1 transition-colors disabled:opacity-40"
                        type="button"
                      >
                        <span>Preview</span>
                        <Eye className="w-3.5 h-3.5" />
                      </button>
                    </div>

                    {/* Staged Operations Preview Strip */}
                    {stagedPlan.length > 0 && (
                      <div className="bg-white border border-[#E5E3DC] rounded-lg overflow-hidden text-xs shadow-xs min-w-0">
                        <div className="px-3 py-2 bg-[#F0EFE9] border-b border-[#E5E3DC] flex items-center justify-between font-semibold text-[#77786F] text-[11px] uppercase tracking-wider">
                          <span>Upcoming File Operations</span>
                          <span>Target Destination</span>
                        </div>
                        <div className="divide-y divide-[#E5E3DC]">
                          {stagedPlan.slice(0, 3).map((item, idx) => (
                            <div
                              key={idx}
                              className="px-3 py-2 flex items-center justify-between hover:bg-[#F7F6F2] transition-colors gap-2"
                            >
                              <div className="flex items-center gap-1.5 truncate">
                                <FileText className="w-3.5 h-3.5 text-[#77786F] shrink-0" />
                                <span className="font-tabular text-[#292A26] truncate">
                                  {item.source_rel_path}
                                </span>
                              </div>
                              <div className="font-tabular text-[#77786F] shrink-0 flex items-center gap-1.5">
                                <span>→</span>
                                <span className="font-medium text-[#292A26]">{item.target_rel_path}</span>
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Right: Recent Activity (5 cols) */}
                  <div className="lg:col-span-5 flex flex-col gap-3 min-w-0">
                    <div className="flex items-center justify-between pb-2 border-b border-[#E5E3DC]">
                      <div className="flex items-center gap-2">
                        <Clock className="w-4 h-4 text-[#77786F]" />
                        <h2 className="text-sm font-semibold text-[#292A26]">Recent Activity</h2>
                      </div>
                      <span className="text-[11px] font-tabular text-[#77786F]">Session Ledger</span>
                    </div>

                    <div className="flex flex-col gap-2 bg-white p-3 rounded-lg border border-[#E5E3DC] shadow-xs">
                      {historyList.length === 0 ? (
                        <div className="py-6 text-center text-[#77786F] text-xs">
                          No historical operations recorded in SQLite yet.
                        </div>
                      ) : (
                        historyList.slice(0, 4).map((b) => (
                          <div
                            key={b.batch_id}
                            className="p-2.5 rounded bg-[#F7F6F2] flex items-start gap-2.5 border border-[#E5E3DC]"
                          >
                            <div className="w-6 h-6 rounded bg-white flex items-center justify-center text-[#136B4D] shrink-0 mt-0.5 border border-[#E5E3DC]">
                              {b.is_undone ? (
                                <RotateCcw className="w-3.5 h-3.5 text-[#785A00]" />
                              ) : (
                                <CheckCircle2 className="w-3.5 h-3.5 text-[#136B4D]" />
                              )}
                            </div>
                            <div className="flex flex-col flex-1 min-w-0">
                              <div className="flex items-center justify-between text-xs gap-2">
                                <span className="font-medium text-[#292A26] truncate">
                                  {b.total_items} file{b.total_items > 1 ? "s" : ""}{" "}
                                  {b.is_undone ? "reverted (undone)" : "organized"}
                                </span>
                                <span className="font-tabular text-[#77786F] text-[11px] shrink-0">
                                  {formatDate(b.created_at)}
                                </span>
                              </div>
                              <span className="font-tabular text-[11px] text-[#77786F] truncate">
                                Batch: {b.batch_id.slice(0, 16)}...
                              </span>
                            </div>
                          </div>
                        ))
                      )}

                      <div className="px-3 py-2 rounded bg-[#F0EFE9] flex items-center justify-between text-[#77786F] text-xs font-medium border border-[#E5E3DC]">
                        <div className="flex items-center gap-1.5">
                          <span className="w-2 h-2 rounded-full bg-[#136B4D]" />
                          <span>Background file watcher idle</span>
                        </div>
                        <span className="font-tabular">0 ops pending</span>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Footer and Safety Note */}
                <div className="pt-3 border-t border-[#E5E3DC] flex items-center justify-between flex-wrap gap-2 text-xs text-[#77786F]">
                  <div className="flex items-center gap-1.5">
                    <ShieldCheck className="w-4 h-4 text-[#136B4D] shrink-0" />
                    <span>
                      File scanning is read-only. No files are moved or deleted without your explicit confirmation.
                    </span>
                  </div>
                  <div className="flex items-center gap-2 font-tabular">
                    <span>Database: {health?.database_connected ? "tidy_ai.db (Connected)" : "Disconnected"}</span>
                    <span>|</span>
                    <span>Zero cloud telemetry</span>
                  </div>
                </div>
              </div>
            )}

            {/* SCREEN 2: FOLDERS */}
            {activeTab === "folders" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Top Bar */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-lg font-semibold text-[#292A26]">Folders</h1>
                      <span className="font-tabular text-[11px] px-1.5 py-0.5 rounded bg-[#E5E3DC] text-[#77786F]">
                        {roots.length} active
                      </span>
                    </div>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      TidyAI operates strictly within folders you explicitly grant access to.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={() => refreshAll()}
                      className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] border border-[#E5E3DC] text-[#292A26] text-xs font-medium transition-colors shadow-xs flex items-center gap-1.5"
                      type="button"
                    >
                      <RefreshCw className="w-3.5 h-3.5 text-[#77786F]" />
                      <span>Rescan All</span>
                    </button>
                    <button
                      onClick={() => setShowAddFolderModal(true)}
                      className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium transition-all shadow-xs flex items-center gap-1.5"
                      type="button"
                    >
                      <Plus className="w-3.5 h-3.5" />
                      <span>Add Folder</span>
                    </button>
                  </div>
                </div>

                {/* Summary Strip */}
                <div className="flex items-center justify-between gap-3 text-xs text-[#77786F] font-tabular">
                  <div>
                    <span>Total Authorized Directories: </span>
                    <strong className="text-[#292A26]">{roots.length}</strong>
                  </div>
                  <div>
                    <span>Indexed Files: </span>
                    <strong className="text-[#292A26]">{scanResult?.summary?.total_files || 0}</strong>
                    <span className="mx-1">•</span>
                    <strong className="text-[#292A26]">
                      {formatBytes(scanResult?.summary?.total_size_bytes || 0)}
                    </strong>
                  </div>
                </div>

                {/* Approved Folders Table with Horizontal Scroll */}
                <div className="w-full bg-white border border-[#E5E3DC] rounded-lg overflow-x-auto shadow-xs text-xs">
                  <table className="w-full border-collapse text-left min-w-[640px]">
                    <thead>
                      <tr className="bg-[#F0EFE9] border-b border-[#E5E3DC] text-[11px] uppercase text-[#77786F] font-semibold tracking-wider">
                        <th className="py-2.5 pl-3 pr-2">Folder Name / Label</th>
                        <th className="py-2.5 px-2">Canonical Path</th>
                        <th className="py-2.5 px-2">Approved Date</th>
                        <th className="py-2.5 px-2">Access Status</th>
                        <th className="py-2.5 pl-2 pr-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E5E3DC]">
                      {roots.length === 0 ? (
                        <tr>
                          <td colSpan={5} className="py-8 text-center text-[#77786F]">
                            <FolderX className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                            <p className="font-medium text-[#292A26]">No authorized folders registered</p>
                            <p className="text-[11px] text-[#77786F] mt-0.5">
                              Click &quot;Add Folder&quot; above to approve a local directory for organizing.
                            </p>
                          </td>
                        </tr>
                      ) : (
                        roots.map((r) => (
                          <tr key={r.id} className="hover:bg-[#F7F6F2] transition-colors">
                            <td className="py-2.5 pl-3 pr-2">
                              <div className="flex items-center gap-2">
                                <Folder className="w-4 h-4 text-[#785A00] shrink-0" />
                                <span className="font-medium text-[#292A26] truncate max-w-[200px]">
                                  {r.label || r.canonical_path.split(/[\\/]/).pop() || "Folder"}
                                </span>
                              </div>
                            </td>
                            <td className="py-2.5 px-2 font-tabular text-[#77786F]">
                              <span className="bg-[#F7F6F2] px-1.5 py-0.5 rounded border border-[#E5E3DC] truncate block max-w-[280px]">
                                {r.canonical_path}
                              </span>
                            </td>
                            <td className="py-2.5 px-2 font-tabular text-[#77786F]">
                              {formatDate(r.added_at)}
                            </td>
                            <td className="py-2.5 px-2">
                              <div className="inline-flex items-center gap-1.5 px-2 py-0.5 rounded-full bg-[#E8F5EE] text-[#136B4D] text-[11px] font-medium">
                                <span className="w-1.5 h-1.5 rounded-full bg-[#136B4D]" />
                                <span>Sandboxed & Active</span>
                              </div>
                            </td>
                            <td className="py-2.5 pl-2 pr-3 text-right">
                              <div className="flex items-center justify-end gap-1.5">
                                <button
                                  onClick={() => {
                                    setSelectedRootId(r.id);
                                    handleScan(r.id);
                                    setActiveTab("all-files");
                                  }}
                                  className="px-2 py-1 rounded bg-[#F0EFE9] hover:bg-[#E5E3DC] text-[#292A26] text-[11px] font-medium transition-colors"
                                  title="Scan and browse files"
                                  type="button"
                                >
                                  Scan Files
                                </button>
                                <button
                                  onClick={() => handleRevokeFolder(r.id)}
                                  className="px-2 py-1 rounded hover:bg-[#FFDAD6] text-[#BA1A1A] text-[11px] font-medium transition-colors"
                                  title="Revoke sandboxed access"
                                  type="button"
                                >
                                  Revoke
                                </button>
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Safety Boundary Note */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-[#E5E3DC] text-xs text-[#77786F]">
                  <ShieldCheck className="w-4 h-4 text-[#136B4D] shrink-0" />
                  <span>
                    <strong className="font-semibold text-[#292A26]">Sandboxed Isolation:</strong> Directories
                    outside this approved list cannot be scanned, indexed, or modified. Windows drive roots (
                    <code className="text-[#BA1A1A]">C:\</code>) and OS folders (<code className="text-[#BA1A1A]">C:\Windows</code>) are blocked.
                  </span>
                </div>
              </div>
            )}

            {/* SCREEN 3: ALL FILES */}
            {activeTab === "all-files" && (
              <div className="flex flex-col w-full gap-3 text-xs">
                {/* Top Control Bar */}
                <div className="flex flex-col gap-2 bg-white rounded-lg p-3 border border-[#E5E3DC] shadow-xs">
                  {/* Row 1: Folder Scope, Search, Actions */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                    <div className="flex items-center gap-1.5 min-w-0">
                      <div className="flex items-center gap-1.5 px-2.5 py-1 rounded bg-[#F7F6F2] border border-[#E5E3DC] text-[#292A26]">
                        <Folder className="w-4 h-4 text-[#785A00] shrink-0" />
                        <select
                          value={selectedRootId}
                          onChange={(e) => {
                            setSelectedRootId(e.target.value);
                            handleScan(e.target.value);
                          }}
                          className="bg-transparent font-medium text-xs text-[#292A26] focus:outline-none cursor-pointer max-w-[200px] truncate"
                        >
                          {roots.map((r) => (
                            <option key={r.id} value={r.id}>
                              {r.label || r.canonical_path}
                            </option>
                          ))}
                        </select>
                      </div>
                      <span className="text-[#77786F] font-tabular">
                        {scanResult?.summary?.total_files || 0} indexed items
                      </span>
                    </div>

                    <div className="relative flex-1 max-w-sm">
                      <span className="absolute inset-y-0 left-2.5 flex items-center pointer-events-none text-[#77786F]">
                        <Search className="w-3.5 h-3.5" />
                      </span>
                      <input
                        type="text"
                        value={fileSearch}
                        onChange={(e) => {
                          setFileSearch(e.target.value);
                          setCurrentPage(1);
                        }}
                        placeholder="Search filename, extension (.pdf), path..."
                        className="w-full pl-8 pr-12 py-1 rounded bg-[#F7F6F2] text-[#292A26] border border-[#E5E3DC] focus:outline-none focus:border-[#785A00] text-xs"
                      />
                      <span className="absolute right-2 top-1/2 -translate-y-1/2 font-tabular text-[10px] text-[#77786F] bg-white px-1 py-0.2 rounded border border-[#E5E3DC]">
                        Ctrl+F
                      </span>
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0">
                      <button
                        onClick={() => handleScan()}
                        disabled={scanning || !selectedRoot}
                        className="h-7 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shadow-xs transition-all flex items-center gap-1 disabled:opacity-50"
                        type="button"
                      >
                        <RefreshCw className={`w-3.5 h-3.5 ${scanning ? "animate-spin" : ""}`} />
                        <span>Rescan Folder</span>
                      </button>
                    </div>
                  </div>

                  {/* Row 2: Category Filter Pills & Sort */}
                  <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 pt-2 border-t border-[#E5E3DC]">
                    <div className="flex items-center gap-1 overflow-x-auto py-0.5">
                      {[
                        { key: "all", label: "All Categories", count: categoryCounts.all },
                        { key: "document", label: "Documents", count: categoryCounts.document },
                        { key: "image", label: "Images", count: categoryCounts.image },
                        { key: "code", label: "Code & Config", count: categoryCounts.code },
                        { key: "archive", label: "Archives", count: categoryCounts.archive },
                        { key: "audio", label: "Audio", count: categoryCounts.audio },
                        { key: "video", label: "Video", count: categoryCounts.video },
                        { key: "other", label: "Other", count: categoryCounts.other },
                      ].map((cat) => (
                        <button
                          key={cat.key}
                          onClick={() => {
                            setCategoryFilter(cat.key);
                            setCurrentPage(1);
                          }}
                          className={`flex items-center gap-1 px-2.5 py-0.5 rounded-full text-[11px] font-medium transition-colors shrink-0 ${
                            categoryFilter === cat.key
                              ? "bg-[#E5B94F] text-[#292A26] font-semibold"
                              : "bg-[#F7F6F2] text-[#77786F] hover:bg-[#F0EFE9] border border-[#E5E3DC]"
                          }`}
                          type="button"
                        >
                          <span>{cat.label}</span>
                          <span className="font-tabular opacity-75 text-[10px]">({cat.count})</span>
                        </button>
                      ))}
                    </div>

                    <div className="flex items-center gap-1.5 shrink-0 text-[#77786F]">
                      <span className="text-[11px]">Sort:</span>
                      <select
                        value={sortBy}
                        onChange={(e) => setSortBy(e.target.value as "modified" | "name" | "size")}
                        className="bg-[#F7F6F2] border border-[#E5E3DC] rounded px-1.5 py-0.5 text-[11px] text-[#292A26] focus:outline-none"
                      >
                        <option value="modified">Last Modified</option>
                        <option value="name">Name</option>
                        <option value="size">Size</option>
                      </select>
                      <button
                        onClick={() => setSortAsc(!sortAsc)}
                        className="p-1 bg-[#F7F6F2] border border-[#E5E3DC] rounded text-[#292A26] hover:bg-[#F0EFE9]"
                        title={sortAsc ? "Sort Descending" : "Sort Ascending"}
                        type="button"
                      >
                        {sortAsc ? <ArrowUp className="w-3.5 h-3.5" /> : <ArrowDown className="w-3.5 h-3.5" />}
                      </button>
                    </div>
                  </div>
                </div>

                {/* File Table with Horizontal Scroll */}
                <div className="w-full bg-white border border-[#E5E3DC] rounded-lg overflow-x-auto shadow-xs flex flex-col">
                  <div className="min-w-[760px]">
                    {/* Header */}
                    <div className="grid grid-cols-[36px_28px_minmax(200px,2fr)_minmax(150px,1.2fr)_110px_90px_130px] items-center px-3 py-2 bg-[#F0EFE9] text-[#77786F] text-[11px] font-semibold border-b border-[#E5E3DC] uppercase tracking-wider">
                      <div className="flex items-center justify-center">
                        <input
                          type="checkbox"
                          checked={
                            paginatedFiles.length > 0 &&
                            paginatedFiles.every((f) => selectedFiles.has(f.relative_path))
                          }
                          onChange={(e) => {
                            const next = new Set(selectedFiles);
                            if (e.target.checked) {
                              paginatedFiles.forEach((f) => next.add(f.relative_path));
                            } else {
                              paginatedFiles.forEach((f) => next.delete(f.relative_path));
                            }
                            setSelectedFiles(next);
                          }}
                          className="w-3.5 h-3.5 rounded accent-[#785A00] cursor-pointer"
                          title="Select all on this page"
                        />
                      </div>
                      <div />
                      <div>NAME</div>
                      <div>RELATIVE PATH</div>
                      <div>CATEGORY</div>
                      <div className="text-right">SIZE</div>
                      <div className="text-right">LAST MODIFIED</div>
                    </div>

                    {/* Rows */}
                    <div className="divide-y divide-[#E5E3DC] max-h-[500px] overflow-y-auto">
                      {paginatedFiles.length === 0 ? (
                        <div className="py-12 text-center text-[#77786F]">
                          <SearchX className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                          <p className="font-medium text-[#292A26]">No matching files found</p>
                          <p className="text-[11px] text-[#77786F] mt-0.5">
                            Try adjusting search terms, category filters, or click &quot;Rescan Folder&quot;.
                          </p>
                        </div>
                      ) : (
                        paginatedFiles.map((file) => {
                          const isSelected = selectedFiles.has(file.relative_path);
                          return (
                            <div
                              key={file.relative_path}
                              onClick={() => {
                                const next = new Set(selectedFiles);
                                if (isSelected) {
                                  next.delete(file.relative_path);
                                } else {
                                  next.add(file.relative_path);
                                }
                                setSelectedFiles(next);
                              }}
                              className={`grid grid-cols-[36px_28px_minmax(200px,2fr)_minmax(150px,1.2fr)_110px_90px_130px] items-center px-3 py-2 cursor-pointer transition-colors ${
                                isSelected
                                  ? "bg-[#FEF3C7]/40 border-l-2 border-[#785A00]"
                                  : "hover:bg-[#F7F6F2]"
                              }`}
                            >
                              <div
                                className="flex items-center justify-center"
                                onClick={(e) => e.stopPropagation()}
                              >
                                <input
                                  type="checkbox"
                                  checked={isSelected}
                                  onChange={(e) => {
                                    const next = new Set(selectedFiles);
                                    if (e.target.checked) {
                                      next.add(file.relative_path);
                                    } else {
                                      next.delete(file.relative_path);
                                    }
                                    setSelectedFiles(next);
                                  }}
                                  className="w-3.5 h-3.5 rounded accent-[#785A00] cursor-pointer"
                                />
                              </div>
                              <div className="flex items-center justify-center">
                                {file.file_type === "image" ? (
                                  <FileImage className="w-4 h-4 text-[#785A00]" />
                                ) : file.file_type === "code" ? (
                                  <FileCode className="w-4 h-4 text-[#785A00]" />
                                ) : file.file_type === "archive" ? (
                                  <FileArchive className="w-4 h-4 text-[#785A00]" />
                                ) : file.file_type === "audio" ? (
                                  <FileAudio className="w-4 h-4 text-[#785A00]" />
                                ) : file.file_type === "video" ? (
                                  <FileVideo className="w-4 h-4 text-[#785A00]" />
                                ) : (
                                  <FileText className="w-4 h-4 text-[#785A00]" />
                                )}
                              </div>
                              <div className="min-w-0 pr-2">
                                <span className="font-medium text-[#292A26] truncate block" title={file.filename}>
                                  {file.filename}
                                </span>
                              </div>
                              <div className="min-w-0 pr-2 font-tabular text-[#77786F]">
                                <span className="truncate block" title={file.relative_path}>
                                  {file.relative_path}
                                </span>
                              </div>
                              <div>
                                <span className="px-2 py-0.5 rounded text-[10px] font-medium bg-[#F0EFE9] text-[#292A26]">
                                  {file.file_type}
                                </span>
                              </div>
                              <div className="text-right font-tabular text-[#292A26]">
                                {formatBytes(file.size_bytes)}
                              </div>
                              <div className="text-right font-tabular text-[#77786F]">
                                {formatDate(file.modified_at)}
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>

                {/* Bottom Pagination Bar */}
                <footer className="flex items-center justify-between px-3 py-1.5 bg-white rounded-lg text-[#77786F] font-tabular text-[11px] border border-[#E5E3DC] shadow-xs">
                  <div className="flex items-center gap-3">
                    <span className="text-[#292A26] font-medium">
                      Showing {filteredFiles.length === 0 ? 0 : (currentPage - 1) * itemsPerPage + 1}–
                      {Math.min(currentPage * itemsPerPage, filteredFiles.length)} of {filteredFiles.length} files
                    </span>
                    <span>•</span>
                    <span className="text-[#785A00] font-semibold">
                      {selectedFiles.size} selected ({formatBytes(selectedBytesTotal)})
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span>
                      Page {currentPage} of {totalPages}
                    </span>
                    <div className="flex items-center gap-1">
                      <button
                        onClick={() => setCurrentPage((p) => Math.max(1, p - 1))}
                        disabled={currentPage <= 1}
                        className="p-1 rounded bg-[#F7F6F2] text-[#292A26] border border-[#E5E3DC] disabled:opacity-40"
                        title="Previous page"
                        type="button"
                      >
                        <ChevronLeft className="w-3.5 h-3.5" />
                      </button>
                      <button
                        onClick={() => setCurrentPage((p) => Math.min(totalPages, p + 1))}
                        disabled={currentPage >= totalPages}
                        className="p-1 rounded bg-[#F7F6F2] text-[#292A26] border border-[#E5E3DC] disabled:opacity-40"
                        title="Next page"
                        type="button"
                      >
                        <ChevronRight className="w-3.5 h-3.5" />
                      </button>
                    </div>
                  </div>
                </footer>
              </div>
            )}

            {/* SCREEN 4: DUPLICATES */}
            {activeTab === "duplicates" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-lg font-semibold text-[#292A26]">Duplicates</h1>
                      <span className="text-[11px] bg-[#E5E3DC] text-[#77786F] px-1.5 py-0.5 rounded uppercase font-semibold">
                        Diagnostic Only
                      </span>
                    </div>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Identifies exact byte-for-byte duplicates via streaming chunked SHA-256. Zero auto-deletion.
                    </p>
                  </div>
                  <button
                    onClick={handleDetectDuplicates}
                    disabled={detectingDuplicates || !selectedRoot}
                    className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shadow-xs transition-all flex items-center gap-1.5 disabled:opacity-50 shrink-0"
                    type="button"
                  >
                    <Copy className={`w-3.5 h-3.5 ${detectingDuplicates ? "animate-spin" : ""}`} />
                    <span>{detectingDuplicates ? "Hashing Files..." : "Run Duplicate Audit"}</span>
                  </button>
                </div>

                {/* Savings Summary Banner */}
                {duplicateResult && (
                  <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] flex items-center justify-between shadow-xs">
                    <div className="flex items-center gap-3">
                      <div className="w-9 h-9 rounded bg-[#FFDAD6] flex items-center justify-center text-[#BA1A1A] shrink-0">
                        <Trash2 className="w-5 h-5" />
                      </div>
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-semibold text-sm text-[#292A26] font-tabular">
                            {formatBytes(duplicateResult.summary.potential_savings_bytes)} Reclaimable Space
                          </span>
                          <span className="font-tabular text-[11px] text-[#77786F] bg-[#F7F6F2] px-1.5 py-0.2 rounded border border-[#E5E3DC]">
                            {duplicateResult.summary.duplicate_groups_count} redundant groups (
                            {duplicateResult.summary.duplicate_files_count} files)
                          </span>
                        </div>
                        <p className="text-[11px] text-[#77786F] mt-0.5">
                          Evaluated {duplicateResult.summary.total_files_evaluated} files in{" "}
                          {duplicateResult.summary.duration_ms}ms.
                        </p>
                      </div>
                    </div>
                  </div>
                )}

                {/* Guarantee Banner */}
                <div className="flex items-center gap-2 px-3 py-2 rounded-lg bg-white border border-[#E5E3DC] text-xs text-[#77786F]">
                  <ShieldCheck className="w-4 h-4 text-[#136B4D] shrink-0" />
                  <span>
                    <strong className="font-semibold text-[#292A26]">Zero-Auto-Delete Guarantee:</strong> Duplicate
                    detection is purely diagnostic. TidyAI never deletes or overwrites duplicate copies automatically.
                  </span>
                </div>

                {/* Duplicate Groups List */}
                {duplicateResult?.groups && duplicateResult.groups.length > 0 ? (
                  <div className="flex flex-col gap-3">
                    {duplicateResult.groups.map((grp, idx) => (
                      <div
                        key={idx}
                        className="bg-white border border-[#E5E3DC] rounded-lg overflow-hidden shadow-xs"
                      >
                        <div className="px-3 py-2 bg-[#F0EFE9] border-b border-[#E5E3DC] flex items-center justify-between font-tabular text-[11px]">
                          <div className="flex items-center gap-2">
                            <span className="font-semibold text-[#292A26]">
                              Group #{idx + 1} ({grp.file_count} copies)
                            </span>
                            <span className="text-[#77786F] bg-white px-1.5 py-0.2 rounded border border-[#E5E3DC]">
                              SHA-256: {grp.sha256.slice(0, 16)}...
                            </span>
                          </div>
                          <div className="text-[#BA1A1A] font-medium">
                            {formatBytes(grp.potential_savings_bytes)} redundant
                          </div>
                        </div>
                        <div className="divide-y divide-[#E5E3DC]">
                          {grp.files.map((file, fIdx) => (
                            <div
                              key={fIdx}
                              className="px-3 py-2 flex items-center justify-between hover:bg-[#F7F6F2] transition-colors"
                            >
                              <div className="flex items-center gap-2 font-tabular">
                                <FileText className="w-3.5 h-3.5 text-[#77786F]" />
                                <span className="text-[#292A26] font-medium">{file.relative_path}</span>
                              </div>
                              <div className="font-tabular text-[#77786F] text-[11px]">
                                {formatBytes(file.size_bytes)} • {formatDate(file.modified_at)}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                ) : (
                  <div className="py-12 text-center text-[#77786F]">
                    <CheckCircle2 className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                    <p className="font-medium text-[#292A26]">
                      {duplicateResult ? "No duplicate files found" : "Audit Not Yet Run"}
                    </p>
                    <p className="text-[11px] text-[#77786F] mt-0.5">
                      {duplicateResult
                        ? "All files in this approved root have unique cryptographic content hashes."
                        : "Click 'Run Duplicate Audit' above to evaluate byte-for-byte duplicates."}
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* SCREEN 5: AI SUGGESTIONS */}
            {activeTab === "ai-suggestions" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <div className="flex items-center gap-2">
                      <h1 className="text-lg font-semibold text-[#292A26]">AI Suggestions</h1>
                      <span className="text-[11px] bg-[#FEF3C7] text-[#785A00] px-1.5 py-0.5 rounded font-semibold">
                        {ollama?.model_name || "qwen3:4b"}
                      </span>
                    </div>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Review intelligent categorization and subfolder proposals before staging.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={handleGenerateSuggestions}
                      disabled={generatingSuggestions || !selectedRoot}
                      className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shadow-xs transition-all flex items-center gap-1.5 disabled:opacity-50"
                      type="button"
                    >
                      <Wand2 className={`w-3.5 h-3.5 ${generatingSuggestions ? "animate-spin" : ""}`} />
                      <span>
                        {generatingSuggestions ? "Analyzing via Local Model..." : "Generate Suggestions"}
                      </span>
                    </button>
                    {suggestionResult && (
                      <button
                        onClick={handleStageAccepted}
                        className="h-8 px-3 rounded bg-[#136B4D] hover:bg-[#00593E] text-white text-xs font-medium shadow-xs transition-all flex items-center gap-1"
                        type="button"
                      >
                        <span>Stage Accepted</span>
                        <ArrowRight className="w-3.5 h-3.5" />
                      </button>
                    )}
                  </div>
                </div>

                {/* Controls Bar */}
                <div className="p-3 bg-white rounded-lg border border-[#E5E3DC] flex flex-wrap items-center justify-between gap-3 shadow-xs">
                  <div className="flex items-center gap-4">
                    <div className="flex items-center gap-1.5 text-[#77786F]">
                      <span>Batch Size:</span>
                      <select
                        value={suggestionMaxFiles}
                        onChange={(e) => setSuggestionMaxFiles(Number(e.target.value))}
                        className="bg-[#F7F6F2] border border-[#E5E3DC] rounded px-2 py-0.5 text-[11px] font-tabular text-[#292A26]"
                      >
                        <option value={10}>10 Files</option>
                        <option value={25}>25 Files</option>
                        <option value={50}>50 Files</option>
                      </select>
                    </div>
                    <div className="flex items-center gap-1.5 text-[#77786F]">
                      <span>Confidence Threshold:</span>
                      <input
                        type="range"
                        min={0.5}
                        max={0.9}
                        step={0.05}
                        value={suggestionConfidenceThreshold}
                        onChange={(e) => setSuggestionConfidenceThreshold(parseFloat(e.target.value))}
                        className="w-24 accent-[#785A00]"
                      />
                      <span className="font-tabular font-medium text-[#292A26]">
                        {(suggestionConfidenceThreshold * 100).toFixed(0)}%
                      </span>
                    </div>
                  </div>
                  {suggestionResult && (
                    <div className="flex items-center gap-2">
                      <button
                        onClick={() => {
                          const allAccepted: Record<string, "accepted" | "rejected"> = {};
                          suggestionResult.suggestions.forEach((s) => {
                            if (s.is_valid && !s.collision_detected) {
                              allAccepted[s.file_id] = "accepted";
                            }
                          });
                          setUserDecisions(allAccepted);
                        }}
                        className="text-[11px] text-[#136B4D] hover:underline font-medium"
                        type="button"
                      >
                        Accept All Valid
                      </button>
                      <span className="text-[#77786F]">•</span>
                      <button
                        onClick={() => setUserDecisions({})}
                        className="text-[11px] text-[#BA1A1A] hover:underline font-medium"
                        type="button"
                      >
                        Reject All
                      </button>
                    </div>
                  )}
                </div>

                {/* Suggestions List */}
                {suggestionResult?.suggestions && suggestionResult.suggestions.length > 0 ? (
                  <div className="flex flex-col gap-3">
                    {suggestionResult.suggestions.map((item) => {
                      const decision = userDecisions[item.file_id];
                      const customEdit = userEdits[item.file_id];
                      const isEditing = editingFileId === item.file_id;
                      const activeFilename = customEdit?.proposed_filename || item.proposed_filename;
                      const activeSubfolder = customEdit?.proposed_subfolder || item.proposed_subfolder;

                      return (
                        <div
                          key={item.file_id}
                          className={`p-3.5 rounded-lg border transition-colors shadow-xs ${
                            decision === "accepted"
                              ? "bg-[#FEF3C7]/20 border-[#E5B94F]"
                              : decision === "rejected"
                              ? "bg-[#FFDAD6]/20 border-[#BA1A1A]/30 opacity-70"
                              : "bg-white border-[#E5E3DC]"
                          }`}
                        >
                          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                            <div className="flex-1 min-w-0">
                              <div className="flex flex-col gap-1 font-tabular">
                                <div className="flex items-center gap-1.5 text-[#77786F]">
                                  <span className="text-[11px] uppercase font-semibold w-16">Original:</span>
                                  <span className="text-[#292A26] truncate">{item.current_relative_path}</span>
                                </div>
                                <div className="flex items-center gap-1.5 text-[#785A00]">
                                  <span className="text-[11px] uppercase font-semibold w-16">Proposed:</span>
                                  {isEditing ? (
                                    <div className="flex items-center gap-1.5 flex-1">
                                      <input
                                        type="text"
                                        value={tempEditSubfolder}
                                        onChange={(e) => setTempEditSubfolder(e.target.value)}
                                        placeholder="Subfolder..."
                                        className="px-1.5 py-0.5 rounded border border-[#E5E3DC] text-[11px] w-36 bg-white"
                                      />
                                      <span>/</span>
                                      <input
                                        type="text"
                                        value={tempEditFilename}
                                        onChange={(e) => setTempEditFilename(e.target.value)}
                                        placeholder="Filename..."
                                        className="px-1.5 py-0.5 rounded border border-[#E5E3DC] text-[11px] flex-1 bg-white"
                                      />
                                      <button
                                        onClick={() => {
                                          setUserEdits((prev) => ({
                                            ...prev,
                                            [item.file_id]: {
                                              proposed_filename: tempEditFilename,
                                              proposed_subfolder: tempEditSubfolder,
                                            },
                                          }));
                                          setEditingFileId(null);
                                        }}
                                        className="px-2 py-0.5 rounded bg-[#136B4D] text-white text-[11px]"
                                        type="button"
                                      >
                                        Save
                                      </button>
                                      <button
                                        onClick={() => setEditingFileId(null)}
                                        className="px-2 py-0.5 rounded bg-[#F0EFE9] text-[#292A26] text-[11px]"
                                        type="button"
                                      >
                                        Cancel
                                      </button>
                                    </div>
                                  ) : (
                                    <span className="font-semibold text-[#292A26] truncate flex items-center gap-1">
                                      <span>
                                        {activeSubfolder ? `${activeSubfolder}/` : ""}
                                        {activeFilename}
                                      </span>
                                      <button
                                        onClick={() => {
                                          setEditingFileId(item.file_id);
                                          setTempEditFilename(activeFilename);
                                          setTempEditSubfolder(activeSubfolder);
                                        }}
                                        className="p-0.5 text-[#77786F] hover:text-[#292A26]"
                                        title="Edit proposed filename and subfolder"
                                        type="button"
                                      >
                                        <Edit3 className="w-3.5 h-3.5" />
                                      </button>
                                    </span>
                                  )}
                                </div>
                              </div>

                              <div className="flex flex-wrap items-center gap-1.5 mt-2">
                                <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#F0EFE9] text-[#292A26]">
                                  {item.category}
                                </span>
                                <span className="px-2 py-0.5 rounded text-[10px] font-tabular bg-[#F7F6F2] text-[#77786F] border border-[#E5E3DC]">
                                  Confidence: {(item.confidence * 100).toFixed(0)}%
                                </span>
                                {item.collision_detected ? (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFDAD6] text-[#BA1A1A]">
                                    Collision: Target Exists
                                  </span>
                                ) : (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E8F5EE] text-[#136B4D]">
                                    Collision-Free
                                  </span>
                                )}
                                {item.is_ambiguous && (
                                  <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FEF3C7] text-[#785A00]">
                                    Needs Review
                                  </span>
                                )}
                              </div>
                              <p className="text-[11px] text-[#77786F] mt-1 italic">
                                &quot;{item.rationale}&quot;
                              </p>
                            </div>

                            <div className="flex items-center gap-1.5 shrink-0">
                              <button
                                onClick={() =>
                                  setUserDecisions((prev) => {
                                    const next = { ...prev };
                                    if (decision === "accepted") {
                                      delete next[item.file_id];
                                    } else {
                                      next[item.file_id] = "accepted";
                                    }
                                    return next;
                                  })
                                }
                                disabled={item.collision_detected}
                                className={`px-2.5 py-1 rounded text-[11px] font-medium flex items-center gap-1 border transition-colors ${
                                  decision === "accepted"
                                    ? "bg-[#136B4D] text-white border-[#136B4D]"
                                    : "bg-white text-[#136B4D] border-[#E5E3DC] hover:bg-[#E8F5EE]"
                                } disabled:opacity-40`}
                                type="button"
                              >
                                <Check className="w-3.5 h-3.5" />
                                <span>Accept</span>
                              </button>
                              <button
                                onClick={() =>
                                  setUserDecisions((prev) => {
                                    const next = { ...prev };
                                    if (decision === "rejected") {
                                      delete next[item.file_id];
                                    } else {
                                      next[item.file_id] = "rejected";
                                    }
                                    return next;
                                  })
                                }
                                className={`px-2.5 py-1 rounded text-[11px] font-medium flex items-center gap-1 border transition-colors ${
                                  decision === "rejected"
                                    ? "bg-[#BA1A1A] text-white border-[#BA1A1A]"
                                    : "bg-white text-[#BA1A1A] border-[#E5E3DC] hover:bg-[#FFDAD6]"
                                }`}
                                type="button"
                              >
                                <X className="w-3.5 h-3.5" />
                                <span>Reject</span>
                              </button>
                            </div>
                          </div>
                        </div>
                      );
                    })}
                  </div>
                ) : (
                  <div className="py-12 text-center text-[#77786F]">
                    <Wand2 className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                    <p className="font-medium text-[#292A26]">No suggestions generated yet</p>
                    <p className="text-[11px] text-[#77786F] mt-0.5">
                      Click &quot;Generate Suggestions&quot; above to have local Qwen3 4B categorize files and propose subfolders.
                    </p>
                  </div>
                )}
              </div>
            )}

            {/* SCREEN 6: REVIEW CHANGES */}
            {activeTab === "review-changes" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <h1 className="text-lg font-semibold text-[#292A26]">Review Changes</h1>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Inspect staged file operations, run read-only dry-run simulation, and confirm execution.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={handleRunDryRun}
                      disabled={dryRunning || stagedPlan.length === 0}
                      className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] text-[#292A26] border border-[#E5E3DC] text-xs font-medium transition-colors shadow-xs flex items-center gap-1.5 disabled:opacity-40"
                      type="button"
                    >
                      <Eye className={`w-3.5 h-3.5 ${dryRunning ? "animate-spin" : ""}`} />
                      <span>{dryRunning ? "Simulating..." : "Run Dry-Run Simulation"}</span>
                    </button>
                    <button
                      onClick={() => setShowConfirmModal(true)}
                      disabled={stagedPlan.length === 0}
                      className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shadow-xs transition-all flex items-center gap-1.5 disabled:opacity-40"
                      type="button"
                    >
                      <CheckCircle2 className="w-3.5 h-3.5" />
                      <span>Apply Operations ({stagedPlan.length})</span>
                    </button>
                  </div>
                </div>

                {/* Dry Run Status Banner */}
                {dryRunResult && (
                  <div
                    className={`p-3 rounded-lg border flex items-center justify-between font-tabular shadow-xs ${
                      dryRunResult.summary.blocked_operations > 0
                        ? "bg-[#FFDAD6]/30 border-[#BA1A1A]/40 text-[#BA1A1A]"
                        : "bg-[#E8F5EE] border-[#136B4D]/40 text-[#136B4D]"
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      {dryRunResult.summary.blocked_operations > 0 ? (
                        <AlertTriangle className="w-4 h-4 shrink-0" />
                      ) : (
                        <CheckCircle2 className="w-4 h-4 shrink-0" />
                      )}
                      <span className="font-semibold">
                        Simulation Result: {dryRunResult.summary.safe_operations} of{" "}
                        {dryRunResult.summary.total_operations} Safe to Move
                      </span>
                    </div>
                    <span>
                      {dryRunResult.summary.blocked_operations > 0
                        ? `${dryRunResult.summary.blocked_operations} Conflict(s) Detected`
                        : "Collision-Free & Contained"}
                    </span>
                  </div>
                )}

                {/* Staged Operations Table with Horizontal Scroll */}
                <div className="w-full bg-white border border-[#E5E3DC] rounded-lg overflow-x-auto shadow-xs text-xs">
                  <div className="min-w-[680px]">
                    <div className="grid grid-cols-[minmax(200px,2fr)_32px_minmax(200px,2fr)_90px_120px_36px] items-center px-3 py-2 bg-[#F0EFE9] text-[#77786F] text-[11px] font-semibold border-b border-[#E5E3DC] uppercase tracking-wider">
                      <div>SOURCE PATH</div>
                      <div />
                      <div>TARGET PATH</div>
                      <div>TYPE</div>
                      <div>DRY-RUN STATUS</div>
                      <div />
                    </div>
                    <div className="divide-y divide-[#E5E3DC]">
                      {stagedPlan.length === 0 ? (
                        <div className="py-12 text-center text-[#77786F]">
                          <ListChecks className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                          <p className="font-medium text-[#292A26]">No file operations staged</p>
                          <p className="text-[11px] text-[#77786F] mt-0.5">
                            Accept proposals in &quot;AI Suggestions&quot; and click &quot;Stage Accepted&quot; to queue operations.
                          </p>
                        </div>
                      ) : (
                        stagedPlan.map((op, idx) => {
                          const simItem = dryRunResult?.items.find(
                            (item) => item.source_rel_path === op.source_rel_path
                          );
                          return (
                            <div
                              key={idx}
                              className="grid grid-cols-[minmax(200px,2fr)_32px_minmax(200px,2fr)_90px_120px_36px] items-center px-3 py-2 hover:bg-[#F7F6F2] font-tabular transition-colors"
                            >
                              <div className="truncate text-[#292A26]" title={op.source_rel_path}>
                                {op.source_rel_path}
                              </div>
                              <div className="text-center text-[#77786F]">→</div>
                              <div className="truncate text-[#785A00] font-medium" title={op.target_rel_path}>
                                {op.target_rel_path}
                              </div>
                              <div>
                                <span className="px-1.5 py-0.5 rounded text-[10px] bg-[#F0EFE9] text-[#292A26] uppercase font-semibold">
                                  {op.operation_type || "move"}
                                </span>
                              </div>
                              <div>
                                {simItem ? (
                                  simItem.is_safe ? (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#E8F5EE] text-[#136B4D]">
                                      Safe to Move
                                    </span>
                                  ) : (
                                    <span className="px-2 py-0.5 rounded text-[10px] font-semibold bg-[#FFDAD6] text-[#BA1A1A]">
                                      {simItem.validation_error || "Collision"}
                                    </span>
                                  )
                                ) : (
                                  <span className="text-[#77786F] text-[11px]">Unsimulated</span>
                                )}
                              </div>
                              <div className="text-right">
                                <button
                                  onClick={() => {
                                    setStagedPlan((prev) => prev.filter((_, i) => i !== idx));
                                    setDryRunResult(null);
                                  }}
                                  className="text-[#77786F] hover:text-[#BA1A1A] p-1"
                                  title="Remove from queue"
                                  type="button"
                                >
                                  <X className="w-3.5 h-3.5" />
                                </button>
                              </div>
                            </div>
                          );
                        })
                      )}
                    </div>
                  </div>
                </div>
              </div>
            )}

            {/* SCREEN 7: HISTORY */}
            {activeTab === "history" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <h1 className="text-lg font-semibold text-[#292A26]">History & Safe Undo</h1>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Cryptographic SQLite audit ledger of all executed operations with 1-click reversible LIFO undo.
                    </p>
                  </div>
                  <button
                    onClick={() => refreshAll()}
                    className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] text-[#292A26] border border-[#E5E3DC] text-xs font-medium transition-colors shadow-xs flex items-center gap-1.5 shrink-0"
                    type="button"
                  >
                    <RefreshCw className="w-3.5 h-3.5 text-[#77786F]" />
                    <span>Refresh Ledger</span>
                  </button>
                </div>

                {/* Success Banner */}
                {applyResult && (
                  <div className="p-3 bg-[#E8F5EE] border border-[#136B4D]/40 rounded-lg text-[#136B4D] flex items-center justify-between font-tabular shadow-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#136B4D] shrink-0" />
                      <span>
                        Successfully applied <strong>{applyResult.total_applied} operation(s)</strong> in batch{" "}
                        <code className="font-semibold">{applyResult.batch_id.slice(0, 16)}...</code>.
                      </span>
                    </div>
                    <button
                      onClick={() => setApplyResult(null)}
                      className="text-[#136B4D] hover:opacity-75 p-0.5 rounded"
                      title="Dismiss"
                      type="button"
                    >
                      <X className="w-3.5 h-3.5" />
                    </button>
                  </div>
                )}

                {/* Batches Table with Horizontal Scroll */}
                <div className="w-full bg-white border border-[#E5E3DC] rounded-lg overflow-x-auto shadow-xs text-xs">
                  <table className="w-full border-collapse text-left min-w-[640px]">
                    <thead>
                      <tr className="bg-[#F0EFE9] border-b border-[#E5E3DC] text-[11px] uppercase text-[#77786F] font-semibold tracking-wider font-tabular">
                        <th className="py-2.5 pl-3 pr-2">Batch ID</th>
                        <th className="py-2.5 px-2">Executed Timestamp</th>
                        <th className="py-2.5 px-2">Approved Root</th>
                        <th className="py-2.5 px-2">Total Operations</th>
                        <th className="py-2.5 px-2">Status</th>
                        <th className="py-2.5 pl-2 pr-3 text-right">Actions</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y divide-[#E5E3DC]">
                      {historyList.length === 0 ? (
                        <tr>
                          <td colSpan={6} className="py-12 text-center text-[#77786F]">
                            <History className="w-8 h-8 text-[#77786F] mx-auto mb-1" />
                            <p className="font-medium text-[#292A26]">No operation history recorded</p>
                            <p className="text-[11px] text-[#77786F] mt-0.5">
                              Executed file moves and renames will appear here with full rollback capabilities.
                            </p>
                          </td>
                        </tr>
                      ) : (
                        historyList.map((batch) => (
                          <tr key={batch.batch_id} className="hover:bg-[#F7F6F2] font-tabular transition-colors">
                            <td className="py-2.5 pl-3 pr-2 font-mono text-[11px] text-[#292A26]">
                              {batch.batch_id.slice(0, 16)}...
                            </td>
                            <td className="py-2.5 px-2 text-[#77786F]">{formatDate(batch.created_at)}</td>
                            <td className="py-2.5 px-2 text-[#292A26] truncate max-w-[180px]" title={batch.approved_root}>
                              {batch.approved_root}
                            </td>
                            <td className="py-2.5 px-2 text-[#292A26] font-semibold">
                              {batch.total_items} item(s)
                            </td>
                            <td className="py-2.5 px-2">
                              {batch.is_undone ? (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#F0EFE9] text-[#77786F] text-[10px] font-semibold">
                                  <span className="w-1.5 h-1.5 rounded-full bg-[#77786F]" />
                                  <span>Undone</span>
                                </span>
                              ) : (
                                <span className="inline-flex items-center gap-1 px-2 py-0.5 rounded-full bg-[#E8F5EE] text-[#136B4D] text-[10px] font-semibold">
                                  <span className="w-1.5 h-1.5 rounded-full bg-[#136B4D]" />
                                  <span>Applied</span>
                                </span>
                              )}
                            </td>
                            <td className="py-2.5 pl-2 pr-3 text-right">
                              <div className="flex items-center justify-end gap-2">
                                <button
                                  onClick={() =>
                                    setExpandedBatchId(
                                      expandedBatchId === batch.batch_id ? null : batch.batch_id
                                    )
                                  }
                                  className="text-[11px] text-[#77786F] hover:text-[#292A26] hover:underline"
                                  type="button"
                                >
                                  {expandedBatchId === batch.batch_id ? "Hide Details" : "Details"}
                                </button>
                                {!batch.is_undone && (
                                  <button
                                    onClick={() => handleUndo(batch.batch_id)}
                                    disabled={undoingBatchId === batch.batch_id}
                                    className="px-2 py-1 rounded bg-[#F0EFE9] hover:bg-[#E5E3DC] text-[#292A26] text-[11px] font-medium border border-[#E5E3DC] transition-colors disabled:opacity-40"
                                    type="button"
                                  >
                                    {undoingBatchId === batch.batch_id ? "Undoing..." : "Undo Batch"}
                                  </button>
                                )}
                              </div>
                            </td>
                          </tr>
                        ))
                      )}
                    </tbody>
                  </table>
                </div>

                {/* Expanded Batch Details */}
                {expandedBatchId && (
                  <div className="p-3 bg-white border border-[#E5E3DC] rounded-lg font-tabular text-[11px] shadow-xs">
                    <h3 className="font-semibold text-[#292A26] mb-2">
                      Batch Details: {expandedBatchId}
                    </h3>
                    <div className="divide-y divide-[#E5E3DC] bg-[#F7F6F2] rounded border border-[#E5E3DC] max-h-48 overflow-y-auto">
                      {historyList
                        .find((b) => b.batch_id === expandedBatchId)
                        ?.items.map((item, idx) => (
                          <div key={idx} className="p-2 flex items-center justify-between gap-2">
                            <span className="truncate max-w-[45%] text-[#77786F]" title={item.source_rel_path}>
                              {item.source_rel_path}
                            </span>
                            <span className="text-[#77786F]">→</span>
                            <span className="truncate max-w-[45%] text-[#785A00] font-medium" title={item.target_rel_path}>
                              {item.target_rel_path}
                            </span>
                          </div>
                        ))}
                    </div>
                  </div>
                )}
              </div>
            )}

            {/* SCREEN 8: SETTINGS & AI STATUS */}
            {activeTab === "settings-ai-status" && (
              <div className="flex flex-col w-full gap-4 text-xs">
                {/* Header */}
                <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-3 pb-3 border-b border-[#E5E3DC]">
                  <div>
                    <h1 className="text-lg font-semibold text-[#292A26]">Settings & AI Status</h1>
                    <p className="text-xs text-[#77786F] mt-0.5">
                      Real-time diagnostics for local FastAPI, SQLite, and Ollama services.
                    </p>
                  </div>
                  <div className="flex items-center gap-2 shrink-0">
                    <button
                      onClick={refreshAll}
                      disabled={refreshing}
                      className="h-8 px-3 rounded bg-white hover:bg-[#F0EFE9] text-[#292A26] border border-[#E5E3DC] text-xs font-medium transition-colors shadow-xs flex items-center gap-1.5"
                      type="button"
                    >
                      <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
                      <span>Refresh Status</span>
                    </button>
                    <button
                      onClick={handleTestOllama}
                      disabled={testingOllama}
                      className="h-8 px-3 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] text-xs font-medium shadow-xs transition-all flex items-center gap-1.5 disabled:opacity-40"
                      type="button"
                    >
                      <Zap className={`w-3.5 h-3.5 ${testingOllama ? "animate-spin" : ""}`} />
                      <span>{testingOllama ? "Pinging..." : "Test Local Ping"}</span>
                    </button>
                  </div>
                </div>

                {/* Service Cards Grid */}
                <div className="grid grid-cols-1 md:grid-cols-3 gap-4 min-w-0">
                  {/* Card 1: FastAPI */}
                  <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] flex flex-col justify-between shadow-xs">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Server className="w-4 h-4 text-[#292A26]" />
                          <span className="font-semibold text-[#292A26] text-xs">FastAPI Backend</span>
                        </div>
                        <span
                          className={`w-2 h-2 rounded-full ${
                            health?.status === "ok" ? "bg-[#136B4D]" : "bg-[#BA1A1A]"
                          }`}
                        />
                      </div>
                      <div className="flex flex-col gap-1 text-[11px] font-tabular text-[#77786F]">
                        <div className="flex justify-between">
                          <span>Endpoint:</span>
                          <span className="font-semibold text-[#292A26]">http://127.0.0.1:8765</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Status:</span>
                          <span className="text-[#136B4D] font-semibold">{health?.status || "offline"}</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Version:</span>
                          <span>{health?.version || "—"}</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Card 2: SQLite */}
                  <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] flex flex-col justify-between shadow-xs">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Database className="w-4 h-4 text-[#292A26]" />
                          <span className="font-semibold text-[#292A26] text-xs">SQLite Database</span>
                        </div>
                        <span
                          className={`w-2 h-2 rounded-full ${
                            health?.database_connected ? "bg-[#136B4D]" : "bg-[#BA1A1A]"
                          }`}
                        />
                      </div>
                      <div className="flex flex-col gap-1 text-[11px] font-tabular text-[#77786F]">
                        <div className="flex justify-between">
                          <span>File:</span>
                          <span className="font-semibold text-[#292A26]">tidy_ai.db</span>
                        </div>
                        <div className="flex justify-between">
                          <span>Connection:</span>
                          <span className="text-[#136B4D] font-semibold">
                            {health?.database_connected ? "Connected" : "Disconnected"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Audit Ledger:</span>
                          <span>{historyList.length} batches recorded</span>
                        </div>
                      </div>
                    </div>
                  </div>

                  {/* Card 3: Ollama */}
                  <div className="p-4 rounded-lg bg-white border border-[#E5E3DC] flex flex-col justify-between shadow-xs">
                    <div>
                      <div className="flex items-center justify-between mb-2">
                        <div className="flex items-center gap-2">
                          <Cpu className="w-4 h-4 text-[#292A26]" />
                          <span className="font-semibold text-[#292A26] text-xs">Local Ollama AI</span>
                        </div>
                        <span
                          className={`w-2 h-2 rounded-full ${
                            ollama?.state === "healthy"
                              ? "bg-[#136B4D]"
                              : ollama?.state === "model_missing"
                              ? "bg-[#785A00]"
                              : "bg-[#BA1A1A]"
                          }`}
                        />
                      </div>
                      <div className="flex flex-col gap-1 text-[11px] font-tabular text-[#77786F]">
                        <div className="flex justify-between">
                          <span>Endpoint:</span>
                          <span className="font-semibold text-[#292A26]">
                            {ollama?.base_url || "http://127.0.0.1:11434"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>Model:</span>
                          <span className="text-[#785A00] font-semibold">
                            {ollama?.model_name || "qwen3:4b"}
                          </span>
                        </div>
                        <div className="flex justify-between">
                          <span>State:</span>
                          <span className="font-semibold text-[#292A26]">
                            {ollama?.state === "healthy"
                              ? "Healthy"
                              : ollama?.state === "model_missing"
                              ? "Model Missing"
                              : "Daemon Offline"}
                          </span>
                        </div>
                      </div>
                    </div>
                  </div>
                </div>

                {/* Ping Result Box */}
                {testPingResult && (
                  <div className="p-3 bg-white border border-[#E5E3DC] rounded-lg flex items-center justify-between font-tabular text-xs shadow-xs">
                    <div className="flex items-center gap-2">
                      <CheckCircle2 className="w-4 h-4 text-[#136B4D] shrink-0" />
                      <span>
                        Latency Test Passed in <strong>{testPingResult.duration_ms}ms</strong>.
                      </span>
                    </div>
                    <span className="text-[#77786F] italic">
                      Output: &quot;{testPingResult.response_text.trim()}&quot;
                    </span>
                  </div>
                )}

                {/* Installed Models List */}
                {ollama?.available_models && (
                  <div className="p-3 bg-white border border-[#E5E3DC] rounded-lg text-xs shadow-xs">
                    <h3 className="font-semibold text-[#292A26] mb-1.5">Installed Local Models</h3>
                    <div className="flex flex-wrap gap-1.5">
                      {ollama.available_models.map((m) => (
                        <span
                          key={m}
                          className="px-2 py-0.5 rounded bg-[#F0EFE9] text-[#292A26] font-tabular text-[11px] border border-[#E5E3DC]"
                        >
                          {m}
                        </span>
                      ))}
                    </div>
                  </div>
                )}

                {/* Troubleshooting & Quick Commands Guide */}
                <div className="p-4 bg-white border border-[#E5E3DC] rounded-lg text-xs flex flex-col gap-2 shadow-xs">
                  <h3 className="font-semibold text-[#292A26]">Quick Setup & Troubleshooting Commands</h3>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2 text-[11px] font-tabular">
                    <div className="bg-[#F7F6F2] p-2.5 rounded border border-[#E5E3DC]">
                      <span className="text-[#77786F] block mb-0.5">Start Local Ollama Daemon:</span>
                      <code className="text-[#292A26] font-semibold">ollama serve</code>
                    </div>
                    <div className="bg-[#F7F6F2] p-2.5 rounded border border-[#E5E3DC]">
                      <span className="text-[#77786F] block mb-0.5">Download Primary Qwen3 Model:</span>
                      <code className="text-[#292A26] font-semibold">ollama pull qwen3:4b</code>
                    </div>
                    <div className="bg-[#F7F6F2] p-2.5 rounded border border-[#E5E3DC]">
                      <span className="text-[#77786F] block mb-0.5">Launch Backend:</span>
                      <code className="text-[#292A26] font-semibold">powershell -File scripts/run_backend.ps1</code>
                    </div>
                    <div className="bg-[#F7F6F2] p-2.5 rounded border border-[#E5E3DC]">
                      <span className="text-[#77786F] block mb-0.5">Run Unified Tests:</span>
                      <code className="text-[#292A26] font-semibold">powershell -File scripts/run_tests.ps1</code>
                    </div>
                  </div>
                </div>
              </div>
            )}
          </div>
        </main>
      </div>

      {/* 3. ADD FOLDER MODAL DIALOG */}
      {showAddFolderModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-[#292A26]/40 backdrop-blur-xs flex items-center justify-center p-4 select-none"
        >
          <div className="bg-white rounded-lg border border-[#E5E3DC] p-5 max-w-md w-full shadow-xl flex flex-col gap-3 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-[#E5E3DC]">
              <h2 className="text-sm font-semibold text-[#292A26]">Authorize Folder Access</h2>
              <button
                onClick={() => {
                  setShowAddFolderModal(false);
                  setAddFolderError(null);
                }}
                className="text-[#77786F] hover:text-[#292A26] p-0.5 rounded"
                type="button"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-2.5">
              <div>
                <label className="font-medium text-[#292A26] block mb-1">Directory Absolute Path</label>
                <input
                  type="text"
                  value={newFolderPath}
                  onChange={(e) => setNewFolderPath(e.target.value)}
                  placeholder="e.g. C:\Users\Username\Downloads or sample_data"
                  className="w-full px-2.5 py-1.5 rounded bg-[#F7F6F2] border border-[#E5E3DC] font-tabular text-[#292A26] focus:outline-none focus:border-[#785A00]"
                />
              </div>

              {/* Sample Data Quick-Fill Preset */}
              <div className="flex items-center gap-1.5 text-[11px] text-[#77786F]">
                <span>Quick Preset:</span>
                <button
                  type="button"
                  onClick={() => {
                    setNewFolderPath("c:\\local_disc_D\\Hackathan\\TIDY_AI\\sample_data");
                    setNewFolderLabel("Synthetic Sample Sandbox");
                  }}
                  className="px-2 py-0.5 rounded bg-[#F0EFE9] hover:bg-[#E5E3DC] border border-[#E5E3DC] text-[#785A00] font-medium"
                >
                  sample_data
                </button>
              </div>

              <div>
                <label className="font-medium text-[#292A26] block mb-1">Friendly Label (Optional)</label>
                <input
                  type="text"
                  value={newFolderLabel}
                  onChange={(e) => setNewFolderLabel(e.target.value)}
                  placeholder="e.g. Downloads Sandbox, Tax Archive"
                  className="w-full px-2.5 py-1.5 rounded bg-[#F7F6F2] border border-[#E5E3DC] text-[#292A26] focus:outline-none focus:border-[#785A00]"
                />
              </div>

              {addFolderError && (
                <div className="p-2 rounded bg-[#FFDAD6] text-[#BA1A1A] text-[11px] font-medium">
                  {addFolderError}
                </div>
              )}

              <p className="text-[11px] text-[#77786F]">
                TidyAI enforces fail-closed sandboxing: filesystem roots (<code>C:\</code>) and operating system
                folders (<code>C:\Windows</code>) are forbidden.
              </p>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[#E5E3DC]">
              <button
                onClick={() => {
                  setShowAddFolderModal(false);
                  setAddFolderError(null);
                }}
                className="px-3 py-1.5 rounded bg-[#F0EFE9] hover:bg-[#E5E3DC] text-[#292A26] font-medium"
                type="button"
              >
                Cancel
              </button>
              <button
                onClick={handleApproveFolder}
                className="px-3 py-1.5 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] font-medium shadow-xs"
                type="button"
              >
                Authorize Access
              </button>
            </div>
          </div>
        </div>
      )}

      {/* 4. TWO-STAGE CONFIRMATION MODAL */}
      {showConfirmModal && (
        <div
          role="dialog"
          aria-modal="true"
          className="fixed inset-0 z-50 bg-[#292A26]/40 backdrop-blur-xs flex items-center justify-center p-4 select-none"
        >
          <div className="bg-white rounded-lg border border-[#E5E3DC] p-5 max-w-lg w-full shadow-xl flex flex-col gap-3 text-xs">
            <div className="flex items-center justify-between pb-2 border-b border-[#E5E3DC]">
              <div className="flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 text-[#785A00]" />
                <h2 className="text-sm font-semibold text-[#292A26]">
                  Confirm File Operations ({stagedPlan.length})
                </h2>
              </div>
              <button
                onClick={() => {
                  setShowConfirmModal(false);
                  setApplyConfirmed(false);
                }}
                className="text-[#77786F] hover:text-[#292A26] p-0.5 rounded"
                type="button"
              >
                <X className="w-4 h-4" />
              </button>
            </div>

            <div className="flex flex-col gap-2.5">
              <p className="text-[#292A26]">
                You are about to execute <strong>{stagedPlan.length} file operation(s)</strong> on disk in{" "}
                <code className="font-tabular font-semibold text-[#292A26]">{selectedRoot?.canonical_path}</code>.
              </p>

              {/* Full Paths Audit Box */}
              <div className="max-h-48 overflow-y-auto divide-y divide-[#E5E3DC] bg-[#F7F6F2] rounded border border-[#E5E3DC] p-2 text-[11px] font-tabular">
                {stagedPlan.map((op, idx) => (
                  <div key={idx} className="py-1 flex items-center justify-between gap-2">
                    <span className="truncate max-w-[45%] text-[#77786F]" title={op.source_rel_path}>
                      {op.source_rel_path}
                    </span>
                    <span className="text-[#77786F]">→</span>
                    <span className="truncate max-w-[45%] text-[#785A00] font-medium" title={op.target_rel_path}>
                      {op.target_rel_path}
                    </span>
                  </div>
                ))}
              </div>

              {/* Safety Assurances */}
              <div className="text-[11px] text-[#77786F] flex flex-col gap-0.5">
                <span>• Backend validates collisions atomically before moving each file.</span>
                <span>• Operations are recorded in the SQLite audit ledger with safe LIFO undo.</span>
                <span>• Silent overwrites are strictly forbidden.</span>
              </div>

              {/* Mandatory Human Review Checkbox */}
              <label className="flex items-start gap-2 p-2.5 rounded bg-[#FEF3C7]/40 border border-[#E5B94F] cursor-pointer mt-1">
                <input
                  type="checkbox"
                  checked={applyConfirmed}
                  onChange={(e) => setApplyConfirmed(e.target.checked)}
                  className="mt-0.5 w-4 h-4 rounded accent-[#785A00] cursor-pointer"
                />
                <span className="font-medium text-[#292A26] text-[11px]">
                  I have reviewed and approved these file operations.
                </span>
              </label>
            </div>

            <div className="flex justify-end gap-2 pt-3 border-t border-[#E5E3DC]">
              <button
                onClick={() => {
                  setShowConfirmModal(false);
                  setApplyConfirmed(false);
                }}
                className="px-3 py-1.5 rounded bg-[#F0EFE9] hover:bg-[#E5E3DC] text-[#292A26] font-medium"
                type="button"
              >
                Cancel
              </button>
              <button
                onClick={handleApplyConfirmed}
                disabled={!applyConfirmed || applying}
                className="px-3 py-1.5 rounded bg-[#E5B94F] hover:bg-[#D6A93F] text-[#292A26] font-medium shadow-xs disabled:opacity-40 transition-all"
                type="button"
              >
                {applying ? "Executing Moves..." : "Confirm & Execute Operations"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
