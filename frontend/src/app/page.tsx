"use client";

import { useEffect, useState, useCallback, useMemo } from "react";
import {
  FolderCheck,
  ShieldCheck,
  Cpu,
  Database,
  Layers,
  Sparkles,
  History,
  FileSearch,
  AlertCircle,
  RefreshCw,
  Copy,
  Lock,
  ArrowRight,
  ChevronRight,
  Plus,
  Trash2,
  FileText,
  Image as ImageIcon,
  Code2,
  Archive,
  Music,
  Video,
  FileQuestion,
  Filter,
  Search,
  Clock,
  AlertTriangle,
  Fingerprint,
  CheckCircle2,
  Check,
  X,
  Edit3,
  RotateCcw,
  SlidersHorizontal,
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
  HealthResponse,
  OllamaStatusResponse,
  ApprovedRoot,
  ScanResponse,
  DuplicateDetectionResponse,
  SuggestionBatchResponse,
  SuggestionItem,
  BroadFileType,
} from "@/lib/api";

type TabKey =
  | "overview"
  | "folders"
  | "scan"
  | "duplicates"
  | "suggestions"
  | "operations"
  | "history";

function formatBytes(bytes: number): string {
  if (bytes === 0) return "0 B";
  const k = 1024;
  const sizes = ["B", "KB", "MB", "GB", "TB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return `${parseFloat((bytes / Math.pow(k, i)).toFixed(1))} ${sizes[i]}`;
}

function getFileIcon(type: BroadFileType) {
  switch (type) {
    case "document":
      return <FileText className="h-4 w-4 text-blue-400" />;
    case "image":
      return <ImageIcon className="h-4 w-4 text-emerald-400" />;
    case "code":
      return <Code2 className="h-4 w-4 text-amber-400" />;
    case "archive":
      return <Archive className="h-4 w-4 text-purple-400" />;
    case "audio":
      return <Music className="h-4 w-4 text-pink-400" />;
    case "video":
      return <Video className="h-4 w-4 text-rose-400" />;
    default:
      return <FileQuestion className="h-4 w-4 text-neutral-400" />;
  }
}

export default function Home() {
  const [activeTab, setActiveTab] = useState<TabKey>("overview");
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [ollama, setOllama] = useState<OllamaStatusResponse | null>(null);
  const [roots, setRoots] = useState<ApprovedRoot[]>([]);
  const [selectedRootId, setSelectedRootId] = useState<string>("");
  const [scanResult, setScanResult] = useState<ScanResponse | null>(null);
  const [duplicateResult, setDuplicateResult] = useState<DuplicateDetectionResponse | null>(null);
  const [suggestionResult, setSuggestionResult] = useState<SuggestionBatchResponse | null>(null);

  // Loading & Error States
  const [loading, setLoading] = useState<boolean>(true);
  const [scanning, setScanning] = useState<boolean>(false);
  const [detectingDuplicates, setDetectingDuplicates] = useState<boolean>(false);
  const [generatingSuggestions, setGeneratingSuggestions] = useState<boolean>(false);
  const [testingOllama, setTestingOllama] = useState<boolean>(false);
  const [ollamaTestResult, setOllamaTestResult] = useState<string | null>(null);
  const [approving, setApproving] = useState<boolean>(false);
  const [error, setError] = useState<string | null>(null);
  const [lastChecked, setLastChecked] = useState<string>("");

  // Suggestion Filters & Review State (Phase 5)
  const [suggestionFilter, setSuggestionFilter] = useState<string>("all");
  const [suggestionSearch, setSuggestionSearch] = useState<string>("");
  const [suggestionMaxFiles, setSuggestionMaxFiles] = useState<number>(25);
  const [suggestionConfidenceThreshold, setSuggestionConfidenceThreshold] = useState<number>(0.7);
  const [userDecisions, setUserDecisions] = useState<Record<string, "accepted" | "rejected">>({});
  const [userEdits, setUserEdits] = useState<
    Record<string, { proposed_filename: string; proposed_subfolder: string }>
  >({});
  const [editingFileId, setEditingFileId] = useState<string | null>(null);
  const [tempEditFilename, setTempEditFilename] = useState<string>("");
  const [tempEditSubfolder, setTempEditSubfolder] = useState<string>("");


  // New Root Form
  const [newPath, setNewPath] = useState<string>("");
  const [newLabel, setNewLabel] = useState<string>("");

  // Scan Filtering
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [typeFilter, setTypeFilter] = useState<string>("all");

  const refreshAll = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [healthData, ollamaData, rootsData] = await Promise.all([
        fetchHealth().catch((err) => {
          console.warn("Backend health check failed:", err);
          return null;
        }),
        fetchOllamaStatus().catch((err) => {
          console.warn("Ollama status check failed:", err);
          return null;
        }),
        fetchApprovedRoots().catch((err) => {
          console.warn("Roots fetch failed:", err);
          return { roots: [] };
        }),
      ]);

      setHealth(healthData);
      setOllama(ollamaData);
      setRoots(rootsData.roots);
      if (rootsData.roots.length > 0 && !selectedRootId) {
        setSelectedRootId(rootsData.roots[0].id);
      }
      setLastChecked(new Date().toLocaleTimeString());
      if (!healthData) {
        setError(
          "Backend is unreachable on 127.0.0.1:8765. Start with 'powershell -File scripts/run_backend.ps1'."
        );
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to load data";
      setError(msg);
    } finally {
      setLoading(false);
    }
  }, [selectedRootId]);

  useEffect(() => {
    let cancelled = false;
    async function loadInitial() {
      try {
        const [healthData, ollamaData, rootsData] = await Promise.all([
          fetchHealth().catch(() => null),
          fetchOllamaStatus().catch(() => null),
          fetchApprovedRoots().catch(() => ({ roots: [] })),
        ]);
        if (!cancelled) {
          setHealth(healthData);
          setOllama(ollamaData);
          setRoots(rootsData.roots);
          if (rootsData.roots.length > 0) {
            setSelectedRootId(rootsData.roots[0].id);
          }
          setLastChecked(new Date().toLocaleTimeString());
          if (!healthData) {
            setError(
              "Backend is unreachable on 127.0.0.1:8765. Start with 'powershell -File scripts/run_backend.ps1'."
            );
          }
        }
      } catch (err: unknown) {
        if (!cancelled) {
          const msg = err instanceof Error ? err.message : "Initialization error";
          setError(msg);
        }
      } finally {
        if (!cancelled) {
          setLoading(false);
        }
      }
    }
    loadInitial();
    return () => {
      cancelled = true;
    };
  }, []);

  const handleApproveRoot = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!newPath.trim()) return;
    setApproving(true);
    setError(null);
    try {
      const approved = await approveRoot(newPath.trim(), newLabel.trim() || undefined);
      setRoots((prev) => [approved, ...prev.filter((r) => r.id !== approved.id)]);
      setSelectedRootId(approved.id);
      setNewPath("");
      setNewLabel("");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to approve directory";
      setError(msg);
    } finally {
      setApproving(false);
    }
  };

  const handleDeleteRoot = async (rootId: string) => {
    if (!confirm("Remove this directory from approved roots? (No files will be deleted)")) {
      return;
    }
    try {
      await deleteApprovedRoot(rootId);
      setRoots((prev) => prev.filter((r) => r.id !== rootId));
      if (selectedRootId === rootId) {
        setSelectedRootId(roots.find((r) => r.id !== rootId)?.id || "");
      }
      if (scanResult?.summary.root_id === rootId) {
        setScanResult(null);
      }
      if (duplicateResult?.summary.root_id === rootId) {
        setDuplicateResult(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to remove root";
      setError(msg);
    }
  };

  const handleStartScan = async () => {
    if (!selectedRootId) return;
    setScanning(true);
    setError(null);
    try {
      const res = await executeScan({
        root_id: selectedRootId,
        recursive: true,
        max_files: 10000,
      });
      setScanResult(res);
      setActiveTab("scan");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Scan failed";
      setError(msg);
    } finally {
      setScanning(false);
    }
  };

  const handleStartDuplicateDetection = async () => {
    if (!selectedRootId) return;
    setDetectingDuplicates(true);
    setError(null);
    try {
      const res = await executeDuplicateDetection({
        root_id: selectedRootId,
        min_size_bytes: 0,
      });
      setDuplicateResult(res);
      setActiveTab("duplicates");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Duplicate detection failed";
      setError(msg);
    } finally {
      setDetectingDuplicates(false);
    }
  };

  const handleTestOllama = async () => {
    setTestingOllama(true);
    setOllamaTestResult(null);
    try {
      const res = await testOllamaInference(
        'Respond with valid JSON: {"status": "ok", "agent": "TidyAI Local"}'
      );
      setOllamaTestResult(`Connected (${res.duration_ms}ms): ${res.response_text}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Inference test failed";
      setOllamaTestResult(`Error: ${msg}`);
    } finally {
      setTestingOllama(false);
    }
  };

  const filteredFiles = useMemo(() => {
    if (!scanResult) return [];
    return scanResult.files.filter((f) => {
      const matchesSearch =
        f.filename.toLowerCase().includes(searchQuery.toLowerCase()) ||
        f.relative_path.toLowerCase().includes(searchQuery.toLowerCase());
      const matchesType = typeFilter === "all" || f.file_type === typeFilter;
      return matchesSearch && matchesType;
    });
  }, [scanResult, searchQuery, typeFilter]);

  // Phase 5 Suggestion Handlers
  const handleStartSuggestions = async () => {
    if (!selectedRootId) {
      setError("Please select an approved directory root first.");
      return;
    }
    setGeneratingSuggestions(true);
    setError(null);
    try {
      const res = await executeSuggestions({
        root_id: selectedRootId,
        max_files: suggestionMaxFiles,
        confidence_threshold: suggestionConfidenceThreshold,
      });
      setSuggestionResult(res);

      // Prepopulate decision states and editable paths
      const initialDecisions: Record<string, "accepted" | "rejected"> = {};
      const initialEdits: Record<string, { proposed_filename: string; proposed_subfolder: string }> = {};

      for (const s of res.suggestions) {
        // High-confidence, non-colliding valid items are accepted by default;
        // ambiguous, colliding, or validation-failed items are rejected by default for review.
        const shouldAccept = !s.is_ambiguous && !s.collision_detected && s.is_valid;
        initialDecisions[s.file_id] = shouldAccept ? "accepted" : "rejected";
        initialEdits[s.file_id] = {
          proposed_filename: s.proposed_filename,
          proposed_subfolder: s.proposed_subfolder,
        };
      }
      setUserDecisions(initialDecisions);
      setUserEdits(initialEdits);
      setActiveTab("suggestions");
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Failed to generate suggestions";
      setError(msg);
    } finally {
      setGeneratingSuggestions(false);
    }
  };

  const toggleDecision = (fileId: string) => {
    setUserDecisions((prev) => ({
      ...prev,
      [fileId]: prev[fileId] === "accepted" ? "rejected" : "accepted",
    }));
  };

  const handleStartEditing = (item: SuggestionItem) => {
    setEditingFileId(item.file_id);
    const active = userEdits[item.file_id] || {
      proposed_filename: item.proposed_filename,
      proposed_subfolder: item.proposed_subfolder,
    };
    setTempEditFilename(active.proposed_filename);
    setTempEditSubfolder(active.proposed_subfolder);
  };

  const handleSaveEdit = (fileId: string) => {
    if (!tempEditFilename.trim()) return;
    setUserEdits((prev) => ({
      ...prev,
      [fileId]: {
        proposed_filename: tempEditFilename.trim(),
        proposed_subfolder: tempEditSubfolder.trim().replace(/\\/g, "/"),
      },
    }));
    setEditingFileId(null);
  };

  const handleCancelEdit = () => {
    setEditingFileId(null);
  };

  const handleAcceptAll = () => {
    if (!suggestionResult) return;
    const updated = { ...userDecisions };
    for (const s of filteredSuggestions) {
      updated[s.file_id] = "accepted";
    }
    setUserDecisions(updated);
  };

  const handleRejectAll = () => {
    if (!suggestionResult) return;
    const updated = { ...userDecisions };
    for (const s of filteredSuggestions) {
      updated[s.file_id] = "rejected";
    }
    setUserDecisions(updated);
  };

  const handleResetEdits = () => {
    if (!suggestionResult) return;
    const resetEdits: Record<string, { proposed_filename: string; proposed_subfolder: string }> = {};
    for (const s of suggestionResult.suggestions) {
      resetEdits[s.file_id] = {
        proposed_filename: s.proposed_filename,
        proposed_subfolder: s.proposed_subfolder,
      };
    }
    setUserEdits(resetEdits);
  };

  const filteredSuggestions = (suggestionResult?.suggestions || []).filter((item) => {
    // Status filter
    if (suggestionFilter === "ambiguous" && !item.is_ambiguous) return false;
    if (suggestionFilter === "collisions" && !item.collision_detected) return false;
    if (suggestionFilter === "accepted" && userDecisions[item.file_id] !== "accepted") return false;
    if (suggestionFilter === "rejected" && userDecisions[item.file_id] !== "rejected") return false;

    // Text search
    if (suggestionSearch.trim()) {
      const query = suggestionSearch.toLowerCase();
      const activeEdit = userEdits[item.file_id];
      const dispFilename = activeEdit?.proposed_filename || item.proposed_filename;
      const dispSubfolder = activeEdit?.proposed_subfolder || item.proposed_subfolder;

      const match =
        item.current_relative_path.toLowerCase().includes(query) ||
        dispFilename.toLowerCase().includes(query) ||
        dispSubfolder.toLowerCase().includes(query) ||
        item.category.toLowerCase().includes(query) ||
        item.rationale.toLowerCase().includes(query);
      if (!match) return false;
    }

    return true;
  });

  const suggestionStats = suggestionResult
    ? {
        total: suggestionResult.suggestions.length,
        accepted: suggestionResult.suggestions.filter(
          (s) => userDecisions[s.file_id] === "accepted"
        ).length,
        rejected: suggestionResult.suggestions.filter(
          (s) => userDecisions[s.file_id] !== "accepted"
        ).length,
        ambiguous: suggestionResult.summary.ambiguous_count,
        collisions: suggestionResult.summary.collisions_count,
      }
    : null;


  return (

    <div className="min-h-screen flex flex-col bg-neutral-950 text-neutral-100">
      {/* Top Navigation Bar */}
      <header className="border-b border-neutral-800 bg-neutral-900/60 backdrop-blur-md sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
          <div className="flex items-center space-x-3">
            <div className="h-9 w-9 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400">
              <FolderCheck className="h-5 w-5" />
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className="font-bold text-lg tracking-tight text-white">
                  TidyAI
                </span>
                <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-neutral-800 text-neutral-300 border border-neutral-700">
                  v0.1.0
                </span>
              </div>
              <p className="text-xs text-neutral-400">
                Safe, Local-First File Organization
              </p>
            </div>
          </div>

          <div className="flex items-center space-x-4">
            {/* Privacy Badge */}
            <div className="hidden sm:flex items-center space-x-2 px-3 py-1.5 rounded-full bg-emerald-950/40 border border-emerald-800/40 text-emerald-300 text-xs font-medium">
              <Lock className="h-3.5 w-3.5" />
              <span>Zero Cloud Telemetry • 127.0.0.1</span>
            </div>

            {/* Quick Refresh & Last Checked */}
            <div className="flex items-center space-x-2">
              {lastChecked && (
                <span className="hidden lg:inline text-[11px] text-neutral-500 font-mono">
                  Checked: {lastChecked}
                </span>
              )}
              <button
                onClick={refreshAll}
                disabled={loading}
                className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 transition"
                title="Refresh local service status"
              >
                <RefreshCw
                  className={`h-3.5 w-3.5 ${loading ? "animate-spin text-emerald-400" : ""}`}
                />
                <span className="hidden md:inline">Refresh Status</span>
              </button>
            </div>
          </div>
        </div>
      </header>

      {/* Main Content Area */}
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 flex-1 w-full space-y-6">
        {/* Navigation Tabs */}
        <nav className="flex space-x-1 border-b border-neutral-800 pb-2 overflow-x-auto">
          {[
            { id: "overview", label: "Overview", icon: Layers },
            { id: "folders", label: "Approved Folders", icon: FolderCheck },
            { id: "scan", label: "Scan Inventory", icon: FileSearch },
            { id: "duplicates", label: "Duplicates", icon: Copy },
            { id: "suggestions", label: "AI Suggestions", icon: Sparkles },
            { id: "operations", label: "Operations & Dry-Run", icon: ShieldCheck },
            { id: "history", label: "History & Undo", icon: History },
          ].map((tab) => {
            const Icon = tab.icon;
            const active = activeTab === tab.id;
            return (
              <button
                key={tab.id}
                onClick={() => setActiveTab(tab.id as TabKey)}
                className={`flex items-center space-x-2 px-3.5 py-2 rounded-lg text-xs font-medium transition whitespace-nowrap ${
                  active
                    ? "bg-neutral-800 text-white border border-neutral-700 shadow-sm"
                    : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-900"
                }`}
              >
                <Icon className={`h-4 w-4 ${active ? "text-emerald-400" : ""}`} />
                <span>{tab.label}</span>
                {tab.id === "folders" && roots.length > 0 && (
                  <span className="ml-1 text-[10px] bg-neutral-700 px-1.5 py-0.2 rounded-full font-mono text-neutral-300">
                    {roots.length}
                  </span>
                )}
                {tab.id === "scan" && scanResult && (
                  <span className="ml-1 text-[10px] bg-emerald-950/80 border border-emerald-700/60 px-1.5 py-0.2 rounded-full font-mono text-emerald-400">
                    {scanResult.summary.total_files}
                  </span>
                )}
                {tab.id === "duplicates" && duplicateResult && (
                  <span className="ml-1 text-[10px] bg-purple-950/80 border border-purple-700/60 px-1.5 py-0.2 rounded-full font-mono text-purple-300">
                    {duplicateResult.summary.duplicate_groups_count}
                  </span>
                )}
                {tab.id === "suggestions" && suggestionResult && (
                  <span className="ml-1 text-[10px] bg-indigo-950/80 border border-indigo-700/60 px-1.5 py-0.2 rounded-full font-mono text-indigo-300">
                    {suggestionResult.summary.suggestions_generated}
                  </span>
                )}
              </button>
            );
          })}
        </nav>

        {/* Global Error Notice */}
        {error && (
          <div className="rounded-xl border border-rose-900/50 bg-rose-950/20 p-4 flex items-start space-x-3 text-rose-200 text-xs">
            <AlertCircle className="h-4 w-4 text-rose-400 shrink-0 mt-0.5" />
            <div className="space-y-1">
              <p className="font-medium text-rose-300">Notice</p>
              <p>{error}</p>
            </div>
          </div>
        )}

        {/* TAB: OVERVIEW */}
        {activeTab === "overview" && (
          <div className="space-y-6">
            {/* Safety & Isolation Banner */}
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 backdrop-blur-sm">
              <div className="flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
                <div className="flex items-start space-x-3.5">
                  <div className="h-10 w-10 rounded-xl bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center text-emerald-400 shrink-0 mt-0.5">
                    <ShieldCheck className="h-5 w-5" />
                  </div>
                  <div>
                    <h2 className="text-sm font-semibold text-white">
                      Deterministic Safety Boundaries Active
                    </h2>
                    <p className="text-xs text-neutral-400 mt-0.5 leading-relaxed">
                      TidyAI strictly confines all scans and file operations to explicitly user-approved directories.
                      AI models propose changes only; duplicate detection is read-only; nothing is moved or deleted without your explicit review and confirmation.
                    </p>
                  </div>
                </div>

                <div className="flex items-center space-x-2 text-xs text-neutral-400 self-end md:self-center">
                  <span className="inline-block h-2 w-2 rounded-full bg-emerald-500 animate-pulse"></span>
                  <span>Local Host Safe Mode</span>
                </div>
              </div>
            </div>

            {/* Quick Metrics */}
            <div className="grid grid-cols-2 sm:grid-cols-4 gap-4">
              {[
                {
                  label: "Approved Folders",
                  value: roots.length.toString(),
                  hint: "Registered root boundaries",
                },
                {
                  label: "Files Scanned",
                  value: scanResult ? scanResult.summary.total_files.toString() : "0",
                  hint: scanResult
                    ? `${formatBytes(scanResult.summary.total_size_bytes)} total`
                    : "Read-only inventory",
                },
                {
                  label: "Duplicate Groups",
                  value: duplicateResult
                    ? duplicateResult.summary.duplicate_groups_count.toString()
                    : "0",
                  hint: duplicateResult
                    ? `${formatBytes(duplicateResult.summary.potential_savings_bytes)} reclaimable`
                    : "Exact SHA-256 matches",
                },
                {
                  label: "Pending Changes",
                  value: suggestionStats ? suggestionStats.accepted.toString() : "0",
                  hint: suggestionStats ? `${suggestionStats.total} proposals reviewed` : "Awaiting review",
                },
              ].map((item, i) => (
                <div
                  key={i}
                  className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4"
                >
                  <p className="text-xs text-neutral-400">{item.label}</p>
                  <p className="text-2xl font-bold text-white mt-1">{item.value}</p>
                  <p className="text-xs text-neutral-500 mt-1">{item.hint}</p>
                </div>
              ))}
            </div>

            {/* System Health Cards */}
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-neutral-400 flex items-center gap-1.5">
                    <Cpu className="h-4 w-4 text-emerald-400" />
                    Backend Service
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
                      health?.status === "ok"
                        ? "bg-emerald-950/60 text-emerald-400 border-emerald-800/60"
                        : "bg-amber-950/60 text-amber-400 border-amber-800/60"
                    }`}
                  >
                    {health ? `Status: ${health.status}` : "Disconnected"}
                  </span>
                </div>
                <div className="mt-3">
                  <p className="text-sm font-semibold text-white">
                    FastAPI • 127.0.0.1:8765
                  </p>
                  <p className="text-xs text-neutral-400 mt-1">
                    {health
                      ? `Version ${health.version} • SQLite connected`
                      : "Start backend server to activate API"}
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-neutral-400 flex items-center gap-1.5">
                    <Database className="h-4 w-4 text-blue-400" />
                    Audit Ledger
                  </span>
                  <span className="text-xs px-2 py-0.5 rounded-full font-medium bg-blue-950/60 text-blue-400 border border-blue-800/60">
                    SQLite 3
                  </span>
                </div>
                <div className="mt-3">
                  <p className="text-sm font-semibold text-white">tidy_ai.db</p>
                  <p className="text-xs text-neutral-400 mt-1">
                    Stores approved roots & operation audit logs (never file contents).
                  </p>
                </div>
              </div>

              <div className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-medium text-neutral-400 flex items-center gap-1.5">
                    <Sparkles className="h-4 w-4 text-purple-400" />
                    Local AI Provider
                  </span>
                  <span
                    className={`text-xs px-2 py-0.5 rounded-full font-medium border ${
                      ollama?.state === "healthy"
                        ? "bg-emerald-950/60 text-emerald-300 border-emerald-800/60"
                        : ollama?.state === "model_missing"
                        ? "bg-amber-950/60 text-amber-300 border-amber-800/60"
                        : "bg-rose-950/60 text-rose-300 border-rose-800/60"
                    }`}
                  >
                    {ollama?.state === "healthy"
                      ? "Ollama Ready"
                      : ollama?.state === "model_missing"
                      ? "Model Missing"
                      : "Daemon Offline"}
                  </span>
                </div>
                <div>
                  <div className="flex items-center justify-between">
                    <p className="text-sm font-semibold text-white">
                      {ollama?.model_name || "qwen3-vl:8b"}
                    </p>
                    {ollama?.reachable && (
                      <button
                        type="button"
                        onClick={handleTestOllama}
                        disabled={testingOllama}
                        className="text-[11px] px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 text-purple-300 border border-neutral-700 font-medium transition"
                        title="Test inference without mutating files"
                      >
                        {testingOllama ? "Testing..." : "Test Ping"}
                      </button>
                    )}
                  </div>
                  <p className="text-xs text-neutral-400 mt-1">
                    {ollama?.message || "Local daemon on http://127.0.0.1:11434"}
                  </p>
                  {ollama?.install_command && (
                    <div className="mt-2 text-[11px] bg-neutral-950 p-1.5 rounded font-mono text-amber-300 border border-neutral-800">
                      <code>{ollama.install_command}</code>
                    </div>
                  )}
                  {ollamaTestResult && (
                    <div className="mt-2 text-[11px] bg-neutral-950 p-1.5 rounded font-mono text-neutral-300 border border-neutral-800 break-all">
                      {ollamaTestResult}
                    </div>
                  )}
                </div>
              </div>
            </div>

            {/* Workflow Pipeline */}
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/30 p-6 space-y-4">
              <div className="flex items-center justify-between">
                <div>
                  <h3 className="text-sm font-semibold text-white">
                    TidyAI Safe Execution Workflow
                  </h3>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    Step-by-step organization pipeline from directory selection to reversible execution.
                  </p>
                </div>
                <span className="text-xs font-mono text-emerald-400 px-2.5 py-1 rounded bg-emerald-950/50 border border-emerald-800/50">
                  Phase 5 Ready
                </span>
              </div>

              <div className="grid grid-cols-1 md:grid-cols-5 gap-3 pt-2">
                {[
                  {
                    step: "1",
                    title: "Approve Root",
                    desc: "Select bounded directory",
                    status: roots.length > 0 ? "Complete" : "Action Needed",
                    highlight: true,
                  },
                  {
                    step: "2",
                    title: "Read Inventory",
                    desc: "Scan metadata only",
                    status: scanResult ? "Scanned" : "Ready to Scan",
                    highlight: true,
                  },
                  {
                    step: "3",
                    title: "Detect Duplicates",
                    desc: "Chunked SHA-256 hashing",
                    status: duplicateResult
                      ? `${duplicateResult.summary.duplicate_groups_count} Groups Found`
                      : "Ready to Run",
                    highlight: true,
                  },
                  {
                    step: "4",
                    title: "AI Suggestions",
                    desc: "Categories & tidy paths",
                    status: suggestionResult
                      ? `${suggestionResult.summary.suggestions_generated} Suggestions Ready`
                      : "Ready to Run",
                    highlight: true,
                  },
                  {
                    step: "5",
                    title: "Dry-Run & Apply",
                    desc: "Explicit user confirmation",
                    status: "Upcoming",
                    highlight: false,
                  },
                ].map((s, idx) => (
                  <div
                    key={idx}
                    className={`p-3.5 rounded-xl border relative flex flex-col justify-between ${
                      s.highlight
                        ? "border-emerald-800/50 bg-emerald-950/10"
                        : "border-neutral-800/80 bg-neutral-900/60"
                    }`}
                  >
                    <div>
                      <div className="flex items-center justify-between text-xs font-bold text-neutral-500 mb-2">
                        <span>STEP {s.step}</span>
                        <ChevronRight className="h-3.5 w-3.5 text-neutral-600" />
                      </div>
                      <p className="text-xs font-semibold text-neutral-200">
                        {s.title}
                      </p>
                      <p className="text-xs text-neutral-400 mt-1 leading-snug">
                        {s.desc}
                      </p>
                    </div>
                    <div className="mt-3 pt-2 border-t border-neutral-800/60">
                      <span
                        className={`text-[11px] font-medium ${
                          s.highlight ? "text-emerald-400" : "text-neutral-500"
                        }`}
                      >
                        {s.status}
                      </span>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {/* TAB: APPROVED FOLDERS */}
        {activeTab === "folders" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-white">
                  Approved Directory Roots
                </h2>
                <p className="text-xs text-neutral-400 mt-0.5">
                  TidyAI will only operate inside explicitly approved boundaries. Filesystem roots and OS folders are blocked.
                </p>
              </div>
              <button
                type="button"
                onClick={() => {
                  setNewPath("sample_data");
                  setNewLabel("Synthetic Sample Data");
                }}
                className="self-start sm:self-auto text-xs px-3 py-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-200 border border-neutral-700 font-medium transition flex items-center space-x-1.5"
              >
                <span>Quick-Fill Sample Data</span>
              </button>
            </div>

            {/* Form to approve a new root */}
            <form
              onSubmit={handleApproveRoot}
              className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-4 space-y-4"
            >
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-400 flex items-center gap-1.5">
                <Plus className="h-3.5 w-3.5 text-emerald-400" />
                Register New Directory Root
              </h3>

              <div className="grid grid-cols-1 md:grid-cols-3 gap-3">
                <div className="md:col-span-2 space-y-1">
                  <label className="text-xs font-medium text-neutral-300">
                    Directory Path
                  </label>
                  <input
                    type="text"
                    value={newPath}
                    onChange={(e) => setNewPath(e.target.value)}
                    placeholder="e.g. sample_data or C:\path\to\safe_folder"
                    className="w-full text-xs rounded-lg bg-neutral-950 border border-neutral-700 px-3 py-2 text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500"
                    required
                  />
                </div>
                <div className="space-y-1">
                  <label className="text-xs font-medium text-neutral-300">
                    Label (Optional)
                  </label>
                  <input
                    type="text"
                    value={newLabel}
                    onChange={(e) => setNewLabel(e.target.value)}
                    placeholder="e.g. My Documents"
                    className="w-full text-xs rounded-lg bg-neutral-950 border border-neutral-700 px-3 py-2 text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500"
                  />
                </div>
              </div>

              <div className="flex justify-end pt-1">
                <button
                  type="submit"
                  disabled={approving || !newPath.trim()}
                  className="inline-flex items-center space-x-1.5 px-4 py-2 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white transition shadow-sm"
                >
                  <FolderCheck className="h-4 w-4" />
                  <span>{approving ? "Validating..." : "Approve Root Directory"}</span>
                </button>
              </div>
            </form>

            {/* List of Approved Roots */}
            <div className="space-y-3">
              <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                Registered Boundaries ({roots.length})
              </h3>

              {roots.length === 0 ? (
                <div className="rounded-xl border border-dashed border-neutral-800 p-8 text-center space-y-2">
                  <FolderCheck className="h-8 w-8 text-neutral-600 mx-auto" />
                  <p className="text-sm font-medium text-neutral-300">
                    No directory roots approved yet
                  </p>
                  <p className="text-xs text-neutral-500 max-w-sm mx-auto">
                    Register a directory above or click &ldquo;Quick-Fill Sample Data&rdquo; to test with safe synthetic files.
                  </p>
                </div>
              ) : (
                <div className="grid grid-cols-1 gap-3">
                  {roots.map((root) => {
                    const isSelected = selectedRootId === root.id;
                    return (
                      <div
                        key={root.id}
                        className={`rounded-xl border p-4 transition flex flex-col sm:flex-row sm:items-center justify-between gap-3 ${
                          isSelected
                            ? "border-emerald-700/60 bg-emerald-950/20"
                            : "border-neutral-800 bg-neutral-900/40 hover:bg-neutral-900/60"
                        }`}
                      >
                        <div className="space-y-1">
                          <div className="flex items-center space-x-2">
                            <span className="text-sm font-semibold text-white">
                              {root.label}
                            </span>
                            {isSelected && (
                              <span className="text-[10px] font-medium bg-emerald-950/80 text-emerald-400 border border-emerald-700/50 px-2 py-0.5 rounded-full">
                                Active Root
                              </span>
                            )}
                          </div>
                          <p className="text-xs font-mono text-neutral-400 break-all">
                            {root.canonical_path}
                          </p>
                          <p className="text-[11px] text-neutral-500">
                            Approved: {new Date(root.added_at).toLocaleString()}
                          </p>
                        </div>

                        <div className="flex items-center space-x-2 self-end sm:self-center">
                          <button
                            type="button"
                            onClick={() => {
                              setSelectedRootId(root.id);
                              handleStartScan();
                            }}
                            disabled={scanning}
                            className="inline-flex items-center space-x-1.5 px-3 py-1.5 rounded-lg text-xs font-medium bg-neutral-800 hover:bg-neutral-700 text-white border border-neutral-700 transition"
                          >
                            <FileSearch className="h-3.5 w-3.5 text-emerald-400" />
                            <span>Scan Now</span>
                          </button>
                          <button
                            type="button"
                            onClick={() => handleDeleteRoot(root.id)}
                            className="p-1.5 rounded-lg text-neutral-400 hover:text-rose-400 hover:bg-rose-950/20 transition"
                            title="Unregister root"
                          >
                            <Trash2 className="h-4 w-4" />
                          </button>
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          </div>
        )}

        {/* TAB: SCAN INVENTORY */}
        {activeTab === "scan" && (
          <div className="space-y-6">
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <h2 className="text-base font-semibold text-white">
                  Read-Only File Scanner & Inventory
                </h2>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Reads file metadata only (names, sizes, types, timestamps). Never inspects or modifies file contents.
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <select
                  value={selectedRootId}
                  onChange={(e) => setSelectedRootId(e.target.value)}
                  className="text-xs bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="" disabled>
                    Select an Approved Root
                  </option>
                  {roots.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  onClick={handleStartScan}
                  disabled={scanning || !selectedRootId}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-emerald-600 hover:bg-emerald-500 disabled:opacity-50 text-white transition shadow-sm"
                >
                  <FileSearch
                    className={`h-3.5 w-3.5 ${scanning ? "animate-spin" : ""}`}
                  />
                  <span>{scanning ? "Scanning..." : "Execute Scan"}</span>
                </button>
              </div>
            </div>

            {/* Scan Summary & Warnings Card */}
            {scanResult && (
              <div className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Total Files</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {scanResult.summary.total_files}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Total Size</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {formatBytes(scanResult.summary.total_size_bytes)}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Folders Visited</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {scanResult.summary.directories_scanned}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Filtered / Skipped</p>
                    <p className="text-xl font-bold text-neutral-300 mt-0.5">
                      {scanResult.summary.skipped_count}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Scan Duration</p>
                    <p className="text-xl font-bold text-emerald-400 mt-0.5 flex items-center gap-1">
                      <Clock className="h-4 w-4" />
                      {scanResult.summary.duration_ms} ms
                    </p>
                  </div>
                </div>

                {/* Structured Warnings */}
                {scanResult.warnings.length > 0 && (
                  <div className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-4 space-y-2">
                    <div className="flex items-center space-x-2 text-amber-400 font-semibold text-xs">
                      <AlertTriangle className="h-4 w-4" />
                      <span>
                        Structured Scan Warnings ({scanResult.warnings.length})
                      </span>
                    </div>
                    <div className="divide-y divide-amber-900/40 text-xs">
                      {scanResult.warnings.map((w, idx) => (
                        <div key={idx} className="py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-amber-200">
                          <span className="font-mono text-[11px] text-amber-300">
                            [{w.warning_type}] {w.path}
                          </span>
                          <span className="text-neutral-400">{w.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Search & Filter Toolbar */}
                <div className="flex flex-col sm:flex-row items-stretch sm:items-center justify-between gap-3 pt-2">
                  <div className="relative flex-1 max-w-md">
                    <Search className="h-4 w-4 text-neutral-500 absolute left-3 top-2.5" />
                    <input
                      type="text"
                      value={searchQuery}
                      onChange={(e) => setSearchQuery(e.target.value)}
                      placeholder="Filter files by name or relative path..."
                      className="w-full text-xs rounded-lg bg-neutral-900 border border-neutral-800 pl-9 pr-3 py-2 text-white placeholder-neutral-500 focus:outline-none focus:border-emerald-500"
                    />
                  </div>

                  <div className="flex items-center space-x-2">
                    <Filter className="h-4 w-4 text-neutral-400" />
                    <select
                      value={typeFilter}
                      onChange={(e) => setTypeFilter(e.target.value)}
                      className="text-xs bg-neutral-900 border border-neutral-800 rounded-lg px-3 py-2 text-white focus:outline-none focus:border-emerald-500"
                    >
                      <option value="all">All File Types</option>
                      <option value="document">Documents</option>
                      <option value="image">Images</option>
                      <option value="audio">Audio</option>
                      <option value="video">Video</option>
                      <option value="archive">Archives</option>
                      <option value="code">Code</option>
                      <option value="other">Other</option>
                    </select>
                  </div>
                </div>

                {/* File Inventory Table */}
                <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 overflow-hidden">
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead className="bg-neutral-900/80 text-neutral-400 border-b border-neutral-800 uppercase tracking-wider text-[11px]">
                        <tr>
                          <th className="px-4 py-3">File / Relative Path</th>
                          <th className="px-4 py-3">Category</th>
                          <th className="px-4 py-3">Size</th>
                          <th className="px-4 py-3">Extension</th>
                          <th className="px-4 py-3">Modified</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-neutral-800/60 font-mono">
                        {filteredFiles.length === 0 ? (
                          <tr>
                            <td
                              colSpan={5}
                              className="px-4 py-8 text-center text-neutral-500 font-sans"
                            >
                              No files match your current search/filter.
                            </td>
                          </tr>
                        ) : (
                          filteredFiles.map((file, idx) => (
                            <tr
                              key={idx}
                              className="hover:bg-neutral-800/30 transition"
                            >
                              <td className="px-4 py-2.5">
                                <div className="flex items-center space-x-2.5">
                                  {getFileIcon(file.file_type)}
                                  <div>
                                    <p className="text-neutral-200 font-medium font-sans">
                                      {file.filename}
                                    </p>
                                    <p className="text-[11px] text-neutral-500">
                                      {file.relative_path}
                                    </p>
                                  </div>
                                </div>
                              </td>
                              <td className="px-4 py-2.5 capitalize font-sans text-neutral-300">
                                {file.file_type}
                              </td>
                              <td className="px-4 py-2.5 text-neutral-300">
                                {formatBytes(file.size_bytes)}
                              </td>
                              <td className="px-4 py-2.5 text-neutral-400">
                                {file.extension || "none"}
                              </td>
                              <td className="px-4 py-2.5 text-neutral-400 font-sans text-[11px]">
                                {file.modified_at
                                  ? new Date(file.modified_at).toLocaleDateString()
                                  : "—"}
                              </td>
                            </tr>
                          ))
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              </div>
            )}

            {!scanResult && (
              <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center space-y-3">
                <FileSearch className="h-10 w-10 text-neutral-600 mx-auto" />
                <h3 className="text-sm font-semibold text-neutral-300">
                  Ready to Index Directory
                </h3>
                <p className="text-xs text-neutral-500 max-w-sm mx-auto">
                  Select an approved directory root above and click &ldquo;Execute Scan&rdquo; to build a read-only inventory.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB: DUPLICATES */}
        {activeTab === "duplicates" && (
          <div className="space-y-6">
            {/* Header with Mandatory Safety Notice */}
            <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
              <div>
                <div className="flex items-center space-x-2">
                  <h2 className="text-base font-semibold text-white">
                    Exact Duplicate Detection
                  </h2>
                  <span className="text-[11px] font-medium bg-amber-950/60 text-amber-300 border border-amber-800/60 px-2 py-0.5 rounded-full">
                    Detection Only
                  </span>
                </div>
                <p className="text-xs text-neutral-400 mt-0.5">
                  Identifies identical files using streaming chunked SHA-256. Strictly no automated cleanup or deletion.
                </p>
              </div>

              <div className="flex items-center space-x-3">
                <select
                  value={selectedRootId}
                  onChange={(e) => setSelectedRootId(e.target.value)}
                  className="text-xs bg-neutral-900 border border-neutral-700 rounded-lg px-3 py-1.5 text-white focus:outline-none focus:border-emerald-500"
                >
                  <option value="" disabled>
                    Select an Approved Root
                  </option>
                  {roots.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label}
                    </option>
                  ))}
                </select>

                <button
                  type="button"
                  onClick={handleStartDuplicateDetection}
                  disabled={detectingDuplicates || !selectedRootId}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white transition shadow-sm"
                >
                  <Copy
                    className={`h-3.5 w-3.5 ${
                      detectingDuplicates ? "animate-spin" : ""
                    }`}
                  />
                  <span>
                    {detectingDuplicates ? "Hashing..." : "Find Duplicates"}
                  </span>
                </button>
              </div>
            </div>

            {/* Non-Destructive Guardrail Banner */}
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-4 flex items-center space-x-3 text-xs text-neutral-300">
              <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0" />
              <div>
                <p className="font-semibold text-white">
                  Read-Only Exact Hash Matching
                </p>
                <p className="text-neutral-400 mt-0.5 leading-relaxed">
                  Files are streamed in 64 KB chunks to compute exact SHA-256 digests. Filenames and sizes alone are never treated as proof of duplication. No deletion action is available.
                </p>
              </div>
            </div>

            {/* Duplicates Results */}
            {duplicateResult && (
              <div className="space-y-5">
                {/* Statistics Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Files Inspected</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {duplicateResult.summary.total_files_evaluated}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Candidates Hashed</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {duplicateResult.summary.candidate_files_hashed}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Duplicate Groups</p>
                    <p className="text-xl font-bold text-purple-400 mt-0.5">
                      {duplicateResult.summary.duplicate_groups_count}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Duplicate Copies</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {duplicateResult.summary.duplicate_files_count}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Potential Reclaim</p>
                    <p className="text-xl font-bold text-amber-400 mt-0.5">
                      {formatBytes(duplicateResult.summary.potential_savings_bytes)}
                    </p>
                  </div>
                </div>

                {/* Structured Warnings if any */}
                {duplicateResult.warnings.length > 0 && (
                  <div className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-4 space-y-2">
                    <div className="flex items-center space-x-2 text-amber-400 font-semibold text-xs">
                      <AlertTriangle className="h-4 w-4" />
                      <span>
                        Warnings Encountered During Hashing ({duplicateResult.warnings.length})
                      </span>
                    </div>
                    <div className="divide-y divide-amber-900/40 text-xs">
                      {duplicateResult.warnings.map((w, idx) => (
                        <div key={idx} className="py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-amber-200">
                          <span className="font-mono text-[11px] text-amber-300">
                            [{w.warning_type}] {w.path}
                          </span>
                          <span className="text-neutral-400">{w.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Groups List */}
                {duplicateResult.groups.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center space-y-2">
                    <CheckCircle2 className="h-10 w-10 text-emerald-500 mx-auto" />
                    <p className="text-sm font-semibold text-neutral-200">
                      Zero Exact Duplicates Found
                    </p>
                    <p className="text-xs text-neutral-500">
                      All inspected files within this approved directory have distinct cryptographic content.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-4">
                    <h3 className="text-xs font-semibold uppercase tracking-wider text-neutral-400">
                      Identified Duplicate Groups ({duplicateResult.groups.length})
                    </h3>

                    {duplicateResult.groups.map((group, gIdx) => (
                      <div
                        key={gIdx}
                        className="rounded-xl border border-neutral-800 bg-neutral-900/50 p-4 space-y-3"
                      >
                        {/* Group Header */}
                        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2 border-b border-neutral-800/80 pb-3">
                          <div className="flex items-center space-x-2">
                            <Fingerprint className="h-4 w-4 text-purple-400" />
                            <span className="text-xs font-mono text-neutral-300">
                              SHA-256: {group.sha256.substring(0, 16)}...{group.sha256.substring(group.sha256.length - 8)}
                            </span>
                            <span className="text-[10px] bg-neutral-800 border border-neutral-700 px-2 py-0.5 rounded text-neutral-400 font-mono">
                              {formatBytes(group.size_bytes)} each
                            </span>
                          </div>

                          <div className="flex items-center space-x-2 self-end sm:self-auto">
                            <span className="text-xs font-medium text-neutral-400">
                              {group.file_count} identical files
                            </span>
                            {group.potential_savings_bytes > 0 && (
                              <span className="text-xs px-2 py-0.5 rounded font-medium bg-amber-950/60 text-amber-300 border border-amber-800/60">
                                ~{formatBytes(group.potential_savings_bytes)} reclaimable
                              </span>
                            )}
                          </div>
                        </div>

                        {/* File Instances */}
                        <div className="grid grid-cols-1 gap-2">
                          {group.files.map((file, fIdx) => (
                            <div
                              key={fIdx}
                              className="p-2.5 rounded-lg bg-neutral-950/70 border border-neutral-800/70 flex flex-col sm:flex-row sm:items-center justify-between text-xs gap-2"
                            >
                              <div className="flex items-center space-x-2.5">
                                <Copy className="h-3.5 w-3.5 text-neutral-500" />
                                <div>
                                  <p className="font-semibold text-neutral-200">
                                    {file.filename}
                                  </p>
                                  <p className="text-[11px] font-mono text-neutral-500">
                                    {file.relative_path}
                                  </p>
                                </div>
                              </div>

                              <div className="flex items-center space-x-3 text-neutral-400 self-end sm:self-auto text-[11px]">
                                <span>{formatBytes(file.size_bytes)}</span>
                                {file.modified_at && (
                                  <span>
                                    Modified: {new Date(file.modified_at).toLocaleDateString()}
                                  </span>
                                )}
                              </div>
                            </div>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            )}

            {!duplicateResult && (
              <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center space-y-3">
                <Copy className="h-10 w-10 text-neutral-600 mx-auto" />
                <h3 className="text-sm font-semibold text-neutral-300">
                  Ready to Run Exact Duplicate Detection
                </h3>
                <p className="text-xs text-neutral-500 max-w-sm mx-auto">
                  Select an approved folder above and click &ldquo;Find Duplicates&rdquo; to compute chunked SHA-256 digests and group identical files.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TAB: AI SUGGESTIONS (Phase 5) */}
        {activeTab === "suggestions" && (
          <div className="space-y-6">
            {/* Header & Controls Bar */}
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/40 p-5 flex flex-col md:flex-row items-start md:items-center justify-between gap-4">
              <div className="flex items-center space-x-3.5">
                <div className="h-10 w-10 rounded-xl bg-purple-500/10 border border-purple-500/20 flex items-center justify-center text-purple-400">
                  <Sparkles className="h-5 w-5" />
                </div>
                <div>
                  <div className="flex items-center space-x-2">
                    <h2 className="text-sm font-semibold text-white">
                      AI Categorization & Path Suggestions
                    </h2>
                    <span className="text-[10px] bg-neutral-800 text-purple-300 border border-neutral-700 px-2 py-0.5 rounded font-mono">
                      Phase 5: Proposals Only
                    </span>
                  </div>
                  <p className="text-xs text-neutral-400 mt-0.5">
                    Analyzes file metadata using local Ollama ({ollama?.model_name || "qwen3-vl:8b"}). Proposals require your review and confirmation.
                  </p>
                </div>
              </div>

              {/* Action Toolbar */}
              <div className="flex flex-wrap items-center gap-2.5 w-full md:w-auto">
                <select
                  value={selectedRootId}
                  onChange={(e) => setSelectedRootId(e.target.value)}
                  className="bg-neutral-800 border border-neutral-700 rounded-lg px-3 py-1.5 text-xs text-white focus:outline-none focus:ring-1 focus:ring-purple-500"
                >
                  <option value="" disabled>
                    Select Approved Folder...
                  </option>
                  {roots.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.label} ({r.canonical_path})
                    </option>
                  ))}
                </select>

                <div className="flex items-center space-x-1.5 bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1 text-xs text-neutral-300">
                  <SlidersHorizontal className="h-3.5 w-3.5 text-neutral-400" />
                  <span className="text-neutral-400 text-[11px]">Max:</span>
                  <select
                    value={suggestionMaxFiles}
                    onChange={(e) => setSuggestionMaxFiles(Number(e.target.value))}
                    className="bg-transparent text-white font-mono text-xs focus:outline-none cursor-pointer"
                  >
                    <option value={10} className="bg-neutral-800">10 files</option>
                    <option value={25} className="bg-neutral-800">25 files</option>
                    <option value={50} className="bg-neutral-800">50 files</option>
                  </select>
                </div>

                <div className="flex items-center space-x-1.5 bg-neutral-800 border border-neutral-700 rounded-lg px-2.5 py-1 text-xs text-neutral-300">
                  <span className="text-neutral-400 text-[11px]">Conf &ge;</span>
                  <select
                    value={suggestionConfidenceThreshold}
                    onChange={(e) => setSuggestionConfidenceThreshold(Number(e.target.value))}
                    className="bg-transparent text-white font-mono text-xs focus:outline-none cursor-pointer"
                  >
                    <option value={0.5} className="bg-neutral-800">50%</option>
                    <option value={0.6} className="bg-neutral-800">60%</option>
                    <option value={0.7} className="bg-neutral-800">70% (Default)</option>
                    <option value={0.8} className="bg-neutral-800">80%</option>
                    <option value={0.9} className="bg-neutral-800">90%</option>
                  </select>
                </div>

                <button
                  type="button"
                  onClick={handleStartSuggestions}
                  disabled={generatingSuggestions || !selectedRootId}
                  className="inline-flex items-center space-x-1.5 px-4 py-1.5 rounded-lg text-xs font-medium bg-purple-600 hover:bg-purple-500 disabled:opacity-50 text-white transition shadow-sm"
                >
                  <Sparkles
                    className={`h-3.5 w-3.5 ${
                      generatingSuggestions ? "animate-spin text-purple-200" : ""
                    }`}
                  />
                  <span>
                    {generatingSuggestions ? "Generating Proposals..." : "Generate Suggestions"}
                  </span>
                </button>
              </div>
            </div>

            {/* Non-Destructive Guardrail Banner */}
            <div className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-4 flex items-center space-x-3 text-xs text-neutral-300">
              <ShieldCheck className="h-5 w-5 text-emerald-400 shrink-0" />
              <div>
                <p className="font-semibold text-white">
                  Deterministic Non-Destructive Verification
                </p>
                <p className="text-neutral-400 mt-0.5 leading-relaxed">
                  Suggestions are strictly proposals for your review. No files are moved, renamed, or modified.
                  All paths are checked against Windows reserved names, invalid characters, traversal escapes, and existing disk collisions.
                </p>
              </div>
            </div>

            {/* Loading Indicator */}
            {generatingSuggestions && (
              <div className="rounded-2xl border border-purple-800/40 bg-purple-950/20 p-10 text-center space-y-3 animate-pulse">
                <Sparkles className="h-8 w-8 text-purple-400 mx-auto animate-spin" />
                <h3 className="text-sm font-semibold text-purple-200">
                  Consulting Local Ollama ({ollama?.model_name || "qwen3-vl:8b"})...
                </h3>
                <p className="text-xs text-neutral-400 max-w-md mx-auto">
                  Streaming file metadata inventory to model. Content is never read or transmitted. Deterministic backend validation will enforce Windows-safe filenames upon completion.
                </p>
              </div>
            )}

            {/* Suggestions Results */}
            {suggestionResult && !generatingSuggestions && (
              <div className="space-y-5">
                {/* Statistics Summary */}
                <div className="grid grid-cols-2 sm:grid-cols-6 gap-3">
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Files Evaluated</p>
                    <p className="text-xl font-bold text-white mt-0.5">
                      {suggestionResult.summary.total_files_analyzed}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Proposals Generated</p>
                    <p className="text-xl font-bold text-purple-400 mt-0.5">
                      {suggestionResult.summary.suggestions_generated}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Accepted for Stage</p>
                    <p className="text-xl font-bold text-emerald-400 mt-0.5">
                      {suggestionStats?.accepted ?? 0}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Rejected / Kept</p>
                    <p className="text-xl font-bold text-neutral-400 mt-0.5">
                      {suggestionStats?.rejected ?? 0}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Review Needed</p>
                    <p
                      className={`text-xl font-bold mt-0.5 ${
                        suggestionResult.summary.ambiguous_count > 0
                          ? "text-amber-400"
                          : "text-neutral-500"
                      }`}
                    >
                      {suggestionResult.summary.ambiguous_count}
                    </p>
                  </div>
                  <div className="rounded-xl border border-neutral-800 bg-neutral-900/40 p-3">
                    <p className="text-[11px] text-neutral-400">Collisions Detected</p>
                    <p
                      className={`text-xl font-bold mt-0.5 ${
                        suggestionResult.summary.collisions_count > 0
                          ? "text-rose-400"
                          : "text-emerald-500"
                      }`}
                    >
                      {suggestionResult.summary.collisions_count}
                    </p>
                  </div>
                </div>

                {/* Filter & Search Toolbar */}
                <div className="rounded-xl border border-neutral-800 bg-neutral-900/30 p-3 flex flex-col md:flex-row items-center justify-between gap-3">
                  {/* Status Filter Chips */}
                  <div className="flex flex-wrap items-center gap-1.5 w-full md:w-auto">
                    {[
                      { id: "all", label: `All (${suggestionResult.suggestions.length})` },
                      {
                        id: "ambiguous",
                        label: `Review Needed (${suggestionResult.summary.ambiguous_count})`,
                        color: "amber",
                      },
                      {
                        id: "collisions",
                        label: `Collisions (${suggestionResult.summary.collisions_count})`,
                        color: "rose",
                      },
                      {
                        id: "accepted",
                        label: `Accepted (${suggestionStats?.accepted ?? 0})`,
                        color: "emerald",
                      },
                      {
                        id: "rejected",
                        label: `Rejected (${suggestionStats?.rejected ?? 0})`,
                        color: "neutral",
                      },
                    ].map((chip) => {
                      const active = suggestionFilter === chip.id;
                      return (
                        <button
                          key={chip.id}
                          onClick={() => setSuggestionFilter(chip.id)}
                          className={`text-xs px-2.5 py-1 rounded-lg font-medium transition ${
                            active
                              ? "bg-neutral-800 text-white border border-neutral-600 shadow-sm"
                              : "text-neutral-400 hover:text-neutral-200 hover:bg-neutral-800/50 border border-transparent"
                          }`}
                        >
                          {chip.label}
                        </button>
                      );
                    })}
                  </div>

                  {/* Search and Bulk Actions */}
                  <div className="flex items-center space-x-2 w-full md:w-auto justify-between md:justify-end">
                    <div className="relative flex-1 md:w-48">
                      <Search className="h-3.5 w-3.5 text-neutral-500 absolute left-2.5 top-1/2 -translate-y-1/2" />
                      <input
                        type="text"
                        placeholder="Search proposals..."
                        value={suggestionSearch}
                        onChange={(e) => setSuggestionSearch(e.target.value)}
                        className="w-full bg-neutral-950 border border-neutral-800 rounded-lg pl-8 pr-3 py-1 text-xs text-white placeholder-neutral-500 focus:outline-none focus:border-purple-500"
                      />
                    </div>

                    <button
                      type="button"
                      onClick={handleAcceptAll}
                      title="Accept all currently filtered suggestions"
                      className="text-xs px-2.5 py-1 rounded-lg bg-emerald-950/60 hover:bg-emerald-900/60 text-emerald-300 border border-emerald-800/60 font-medium transition"
                    >
                      Accept All
                    </button>

                    <button
                      type="button"
                      onClick={handleRejectAll}
                      title="Reject all currently filtered suggestions"
                      className="text-xs px-2.5 py-1 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-300 border border-neutral-700 font-medium transition"
                    >
                      Reject All
                    </button>

                    <button
                      type="button"
                      onClick={handleResetEdits}
                      title="Reset edited names and folders back to AI defaults"
                      className="text-xs p-1.5 rounded-lg bg-neutral-800 hover:bg-neutral-700 text-neutral-400 hover:text-neutral-200 border border-neutral-700 transition"
                    >
                      <RotateCcw className="h-3.5 w-3.5" />
                    </button>
                  </div>
                </div>

                {/* Warnings Section */}
                {suggestionResult.warnings.length > 0 && (
                  <div className="rounded-xl border border-amber-800/60 bg-amber-950/20 p-4 space-y-2">
                    <div className="flex items-center space-x-2 text-amber-400 font-semibold text-xs">
                      <AlertTriangle className="h-4 w-4" />
                      <span>
                        Validation & Collision Warnings ({suggestionResult.warnings.length})
                      </span>
                    </div>
                    <div className="divide-y divide-amber-900/40 text-xs">
                      {suggestionResult.warnings.map((w, idx) => (
                        <div
                          key={idx}
                          className="py-1.5 flex flex-col sm:flex-row sm:items-center justify-between gap-1 text-amber-200"
                        >
                          <span className="font-mono text-[11px] text-amber-300">
                            [{w.warning_type}] {w.path}
                          </span>
                          <span className="text-neutral-400">{w.message}</span>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Suggestions List */}
                {filteredSuggestions.length === 0 ? (
                  <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center space-y-2">
                    <Sparkles className="h-10 w-10 text-neutral-600 mx-auto" />
                    <p className="text-sm font-semibold text-neutral-200">
                      No Suggestions Match Filter
                    </p>
                    <p className="text-xs text-neutral-500">
                      Try resetting search keywords or selecting the &ldquo;All&rdquo; tab above.
                    </p>
                  </div>
                ) : (
                  <div className="space-y-3">
                    {filteredSuggestions.map((item) => {
                      const decision = userDecisions[item.file_id] || "accepted";
                      const isAccepted = decision === "accepted";
                      const activeEdit = userEdits[item.file_id];
                      const dispFilename =
                        activeEdit?.proposed_filename || item.proposed_filename;
                      const dispSubfolder =
                        activeEdit?.proposed_subfolder !== undefined
                          ? activeEdit.proposed_subfolder
                          : item.proposed_subfolder;
                      const dispProposedPath = dispSubfolder
                        ? `${dispSubfolder}/${dispFilename}`
                        : dispFilename;
                      const isEditing = editingFileId === item.file_id;

                      // Border styling based on state
                      let cardBorder = "border-neutral-800 bg-neutral-900/40";
                      if (!isAccepted) {
                        cardBorder = "border-neutral-800/80 bg-neutral-950/60 opacity-60";
                      } else if (item.collision_detected) {
                        cardBorder = "border-rose-900/70 bg-rose-950/20";
                      } else if (item.is_ambiguous) {
                        cardBorder = "border-amber-900/70 bg-amber-950/20";
                      } else if (isAccepted) {
                        cardBorder = "border-emerald-900/60 bg-neutral-900/60";
                      }

                      // Confidence badge styling
                      const confPct = Math.round(item.confidence * 100);
                      let confBadge =
                        "bg-emerald-950/60 text-emerald-300 border-emerald-800/60";
                      if (confPct < 70) {
                        confBadge = "bg-rose-950/60 text-rose-300 border-rose-800/60";
                      } else if (confPct < 85) {
                        confBadge = "bg-amber-950/60 text-amber-300 border-amber-800/60";
                      }

                      return (
                        <div
                          key={item.file_id}
                          className={`rounded-xl border p-4 space-y-3.5 transition ${cardBorder}`}
                        >
                          {/* Card Top: Badges and Accept/Reject Toggle */}
                          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2.5 border-b border-neutral-800/80 pb-3">
                            <div className="flex flex-wrap items-center gap-2">
                              {/* Category Badge */}
                              <span className="text-[11px] font-medium px-2 py-0.5 rounded bg-blue-950/80 text-blue-300 border border-blue-800/60">
                                {item.category}
                              </span>

                              {/* Confidence Score Pill */}
                              <span
                                className={`text-[11px] font-mono px-2 py-0.5 rounded border ${confBadge}`}
                              >
                                {confPct}% confidence
                              </span>

                              {/* Ambiguity Alert */}
                              {item.is_ambiguous && (
                                <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded bg-amber-950/80 text-amber-300 border border-amber-800/60">
                                  <AlertTriangle className="h-3 w-3" />
                                  <span>Review Needed</span>
                                </span>
                              )}

                              {/* Collision Alert */}
                              {item.collision_detected && (
                                <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/60">
                                  <AlertCircle className="h-3 w-3" />
                                  <span>Collision</span>
                                </span>
                              )}

                              {/* Validation Notice */}
                              {!item.is_valid && (
                                <span className="inline-flex items-center space-x-1 text-[11px] font-medium px-2 py-0.5 rounded bg-rose-950/80 text-rose-300 border border-rose-800/60">
                                  <span>Invalid Proposal (Reverted)</span>
                                </span>
                              )}
                            </div>

                            {/* Decision Toggle */}
                            <div className="flex items-center space-x-2 self-end sm:self-auto">
                              <button
                                type="button"
                                onClick={() => toggleDecision(item.file_id)}
                                className={`inline-flex items-center space-x-1.5 px-3 py-1 rounded-lg text-xs font-semibold transition ${
                                  isAccepted
                                    ? "bg-emerald-600 hover:bg-emerald-500 text-white shadow-sm"
                                    : "bg-neutral-800 hover:bg-neutral-700 text-neutral-400 border border-neutral-700"
                                }`}
                              >
                                {isAccepted ? (
                                  <>
                                    <Check className="h-3.5 w-3.5" />
                                    <span>Accepted</span>
                                  </>
                                ) : (
                                  <>
                                    <X className="h-3.5 w-3.5" />
                                    <span>Rejected</span>
                                  </>
                                )}
                              </button>
                            </div>
                          </div>

                          {/* Card Middle: Original vs Proposed Path */}
                          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                            {/* Original Path */}
                            <div className="space-y-1">
                              <span className="text-[10px] uppercase tracking-wider font-semibold text-neutral-500">
                                Current Location
                              </span>
                              <div className="flex items-center space-x-2 p-2 rounded-lg bg-neutral-950/80 border border-neutral-800">
                                <FileText className="h-4 w-4 text-neutral-500 shrink-0" />
                                <span className="font-mono text-xs text-neutral-300 truncate">
                                  {item.current_relative_path}
                                </span>
                              </div>
                            </div>

                            {/* Proposed Destination */}
                            <div className="space-y-1">
                              <div className="flex items-center justify-between">
                                <span className="text-[10px] uppercase tracking-wider font-semibold text-emerald-400">
                                  Proposed Destination
                                </span>
                                {!isEditing && (
                                  <button
                                    type="button"
                                    onClick={() => handleStartEditing(item)}
                                    className="inline-flex items-center space-x-1 text-[11px] text-neutral-400 hover:text-white px-2 py-0.5 rounded bg-neutral-800 hover:bg-neutral-700 border border-neutral-700 transition"
                                  >
                                    <Edit3 className="h-3 w-3 text-neutral-400" />
                                    <span>Edit Path</span>
                                  </button>
                                )}
                              </div>

                              {isEditing ? (
                                <div className="p-2.5 rounded-lg bg-neutral-950 border border-purple-800/80 space-y-2">
                                  <div>
                                    <label className="text-[10px] text-neutral-400 block mb-0.5">
                                      Destination Subfolder (e.g. Documents/Finance)
                                    </label>
                                    <input
                                      type="text"
                                      value={tempEditSubfolder}
                                      onChange={(e) => setTempEditSubfolder(e.target.value)}
                                      className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                                      placeholder="Subfolder path (leave blank for root)"
                                    />
                                  </div>
                                  <div>
                                    <label className="text-[10px] text-neutral-400 block mb-0.5">
                                      Proposed Filename (must retain extension)
                                    </label>
                                    <input
                                      type="text"
                                      value={tempEditFilename}
                                      onChange={(e) => setTempEditFilename(e.target.value)}
                                      className="w-full bg-neutral-900 border border-neutral-700 rounded px-2 py-1 text-xs text-white font-mono focus:outline-none focus:border-purple-500"
                                    />
                                  </div>
                                  <div className="flex items-center space-x-2 pt-1 justify-end">
                                    <button
                                      type="button"
                                      onClick={handleCancelEdit}
                                      className="px-2.5 py-0.5 rounded text-xs text-neutral-400 hover:text-white bg-neutral-800 hover:bg-neutral-700 transition"
                                    >
                                      Cancel
                                    </button>
                                    <button
                                      type="button"
                                      onClick={() => handleSaveEdit(item.file_id)}
                                      className="px-2.5 py-0.5 rounded text-xs text-white bg-purple-600 hover:bg-purple-500 font-medium transition"
                                    >
                                      Save Edits
                                    </button>
                                  </div>
                                </div>
                              ) : (
                                <div className="flex items-center space-x-2 p-2 rounded-lg bg-emerald-950/20 border border-emerald-900/40">
                                  <ArrowRight className="h-4 w-4 text-emerald-400 shrink-0" />
                                  <span className="font-mono text-xs font-semibold text-emerald-300 truncate">
                                    {dispProposedPath}
                                  </span>
                                </div>
                              )}
                            </div>
                          </div>

                          {/* Card Bottom: Rationale & Collision Details */}
                          <div className="pt-1 space-y-1 text-xs">
                            <p className="text-neutral-400 leading-relaxed">
                              <span className="font-semibold text-neutral-300">Rationale: </span>
                              {item.rationale}
                            </p>

                            {item.collision_detected && item.collision_details && (
                              <p className="text-rose-400 font-mono text-[11px] flex items-center gap-1.5 pt-0.5">
                                <AlertCircle className="h-3.5 w-3.5 shrink-0" />
                                <span>Collision: {item.collision_details}</span>
                              </p>
                            )}

                            {!item.is_valid && item.validation_error && (
                              <p className="text-amber-300 font-mono text-[11px] flex items-center gap-1.5 pt-0.5">
                                <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
                                <span>Safety Violation: {item.validation_error}</span>
                              </p>
                            )}
                          </div>
                        </div>
                      );
                    })}
                  </div>
                )}
              </div>
            )}

            {/* Zero State */}
            {!suggestionResult && !generatingSuggestions && (
              <div className="rounded-xl border border-dashed border-neutral-800 p-12 text-center space-y-3">
                <Sparkles className="h-10 w-10 text-neutral-600 mx-auto" />
                <h3 className="text-sm font-semibold text-neutral-300">
                  Ready to Generate AI Organization Suggestions
                </h3>
                <p className="text-xs text-neutral-500 max-w-sm mx-auto">
                  Select an approved folder above and click &ldquo;Generate Suggestions&rdquo; to consult local Ollama for smart category, filename, and subfolder proposals.
                </p>
              </div>
            )}
          </div>
        )}

        {/* TABS 6–7: Placeholders with clear milestone notices */}
        {activeTab !== "overview" &&
          activeTab !== "folders" &&
          activeTab !== "scan" &&
          activeTab !== "duplicates" &&
          activeTab !== "suggestions" && (
            <div className="rounded-2xl border border-neutral-800 bg-neutral-900/30 p-8 text-center space-y-3">
              <div className="h-12 w-12 rounded-2xl bg-neutral-800 border border-neutral-700 mx-auto flex items-center justify-center text-neutral-400">
                <Layers className="h-6 w-6" />
              </div>
              <h3 className="text-sm font-semibold text-white capitalize">
                {activeTab} Module
              </h3>
              <p className="text-xs text-neutral-400 max-w-md mx-auto">
                This dashboard view is scaffolded and will connect to upcoming phase endpoints
                (Operations, Dry-Run, & Undo in Phase 6).
              </p>
              <div className="pt-2">
                <button
                  onClick={() => setActiveTab("overview")}
                  className="inline-flex items-center space-x-1 text-xs text-emerald-400 hover:text-emerald-300 font-medium"
                >
                  <span>Return to Overview</span>
                  <ArrowRight className="h-3 w-3" />
                </button>
              </div>
            </div>
          )}
      </div>


      {/* Footer */}
      <footer className="border-t border-neutral-800 bg-neutral-950 py-4 mt-auto">
        <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 flex flex-col sm:flex-row items-center justify-between text-xs text-neutral-400 gap-2">
          <span>TidyAI • Privacy-First Local Assistant</span>
          <div className="flex items-center space-x-4">
            <span>FastAPI: 127.0.0.1:8765</span>
            <span>Next.js: 127.0.0.1:3000</span>
            <span>Ollama: 127.0.0.1:11434</span>
          </div>
        </div>
      </footer>
    </div>
  );
}
