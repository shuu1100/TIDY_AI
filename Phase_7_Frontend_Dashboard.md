# TidyAI Phase 7 — Frontend Dashboard

Integrate the backend into a polished, accessible Next.js dashboard without weakening backend validation.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Design
Calm, clean, productivity-focused; responsive; restrained colors; clear privacy messaging. Avoid a generic template look.

## Screens/features
1. Overview: scan status, file count, duplicate groups, pending suggestions, recent operations.
2. Approved folders: add/remove roots only through safe backend APIs.
3. Scan results: search/filter by relative path, type, and size.
4. Duplicates: exact-hash groups; no automatic delete.
5. Suggestions review: original/proposed paths, rationale, confidence, edit/approve/reject.
6. Operation preview: selected changes, warnings, dry-run results.
7. Confirmation dialog listing all selected changes.
8. History and backend-authorized safe undo.
9. API/Ollama status.

## Requirements
Use typed API clients and configurable API base URL. Handle loading, empty, offline, timeout, validation, and partial-success states. Prefer relative paths. Accessible keyboard navigation, focus, labels, contrast, and status announcements. No analytics, telemetry, remote fonts, or third-party services without approval. Run lint/type checks and tests where available.
## Acceptance
User can complete the safe workflow; suggestions never auto-apply; UI reports errors accurately. Stop after Phase 7.
