# TidyAI Phase 2 — Secure Read-Only File Scanner

Implement inventory scanning only. Do not add rename/move/copy/delete.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Add Pydantic schemas for approved roots, scan requests, file entries, summaries, and warnings.
2. Require explicit user-approved roots; never scan filesystem roots or personal folders automatically.
3. Scan metadata only by default: relative path, filename, extension, size, timestamps if available, broad type.
4. Resolve/canonicalize paths and enforce containment in approved roots. Reject traversal, absolute/drive/UNC escapes, symlinks/junctions/reparse points escaping the root.
5. Do not read file contents or follow links outside approved roots. Skip `.git`, caches, virtual environments, and configured ignore patterns.
6. Bound long scans and return structured partial errors for inaccessible/disappearing files.
7. Expose typed API endpoints without unrestricted filesystem browsing.
8. Test using temporary directories only: traversal, absolute path, UNC/drive paths, link escape, permissions, empty/nested directories, disappearing files, large inventories.
## Acceptance
Read-only behavior; invalid paths fail closed; no mutations; tests use temporary fixtures. Stop after Phase 2.
