# TidyAI Phase 1 — Project Scaffolding

Implement the approved skeleton only.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Create `frontend/`, `backend/app/`, `backend/tests/`, `sample_data/`, `docs/`, `.env.example`, `.gitignore`, and `README.md`.
2. Frontend: Next.js App Router, TypeScript, Tailwind; a responsive dashboard shell.
3. Backend: FastAPI, Pydantic, health endpoint, typed response. Bind to `127.0.0.1` by default; use port 8765 only if available.
4. Add SQLite configuration and an Ollama configuration stub; no AI calls yet.
5. Add safe environment configuration; ignore `.env`, databases, caches, virtual environments, and generated files.
6. Include Windows PowerShell setup instructions and harmless synthetic sample data.
7. Run available lint/type/basic tests; never claim checks passed unless they ran.
## Acceptance
App skeleton is documented and starts locally without Docker; no file operations against user folders and no external AI calls. Stop after Phase 1.
