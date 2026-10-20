# TidyAI Phase 0 — Workspace Audit and Planning

## Goal
Audit the selected workspace and plan the project. Do not implement features.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Inspect current directory, files, Git status, installed Node/npm/Python/Git/Ollama, and available ports. Do not stop processes to free ports.
2. If this is not clearly a dedicated TidyAI folder, ask the user to confirm a safe path before writing files.
3. Propose: Next.js App Router + TypeScript + Tailwind; FastAPI + Pydantic; Ollama local HTTP; SQLite; Pytest.
4. Define MVP: approved-folder scanning, read-only inventory, categories/name/folder suggestions, SHA-256 exact duplicates, review/approval, dry-run, history, safe undo.
5. Document risks: path traversal, Windows drive/UNC paths, symlinks/junctions, collisions, interrupted moves, AI outage, undo conflicts.
6. In the confirmed project folder only, create `PLAN.md` and `WORKSPACE_AUDIT.md`; otherwise provide findings without writing.
## Acceptance
No real user folders scanned; no unrelated files changed; record findings, assumptions, risks, port status, and next steps. Stop before Phase 1.
