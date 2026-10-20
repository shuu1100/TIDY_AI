# TidyAI Phase 8 — QA and Security Audit

Audit and fix confirmed defects within TidyAI scope; do not add unrelated features.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Audit
1. Path traversal, canonicalization, drive/UNC paths, symlinks/junctions, root containment.
2. Dry-run invariance, explicit confirmation, no overwrite/delete, partial failures, idempotency, undo.
3. AI malformed JSON, prompt injection in filenames, timeout, offline behavior, no cloud fallback, no execution.
4. API local-only binding, request validation, safe errors, restricted CORS, no unrestricted filesystem endpoint.
5. Privacy: no file contents in logs, no telemetry, no remote inference, minimal SQLite history.
6. Frontend duplicate clicks, stale state, error/loading states, accessible dialogs.
7. `.env` ignored, no secrets in source or staged diff.
8. Large directories, chunked hashing, cancellation/time limits, responsiveness.
9. Dependency review where tooling exists; do not blindly upgrade everything.
10. Documentation and platform-specific limitations.

## Actions
Run available backend tests, frontend lint/type checks, inspect Git diff/status, add regression tests for confirmed bugs. Use temporary test folders only. Distinguish confirmed issues from untested risks; never claim tests passed unless run.
## Acceptance
Deliver a security audit report with severity, evidence, fixes, test outcomes, and unresolved risks. Stop after Phase 8.
