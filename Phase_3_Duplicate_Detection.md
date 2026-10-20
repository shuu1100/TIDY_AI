# TidyAI Phase 3 — Exact Duplicate Detection

Add SHA-256 duplicate detection only. Never delete, move, or rename files.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Hash files in chunks; do not load entire files into memory.
2. Only hash files under approved roots; do not follow escaping links or send data to remote services.
3. Handle empty, unreadable, changing, or disappearing files with structured warnings.
4. Group exact content matches by SHA-256 and report relative paths and sizes. Filename/size alone is not proof of duplication.
5. Add typed API endpoint and a dashboard view clearly labeled “detection only”; no cleanup action.
6. Test identical content with different names, same name with different content, empty files, read failures, changed/disappeared files, and path escapes. Use temporary folders.
## Acceptance
No file mutations; deterministic results and clear warnings. Stop after Phase 3.
