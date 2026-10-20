# TidyAI Phase 9 — Documentation, Demo, and Release Preparation

Prepare the project for public review. Do not publish, push, or release without explicit permission.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Write README with overview, privacy principles, features, architecture/Mermaid diagram, prerequisites, Windows PowerShell setup, environment variables, start commands, Ollama setup, tests, safe-use guide, limitations, troubleshooting.
2. Add CONTRIBUTING and issue/PR templates if useful. Do not choose or invent a license; ask the user before adding a specific license.
3. Use genuine screenshots only; do not fabricate images or test results.
4. Write a reproducible demo script: approve sample folder, scan, detect duplicates, request local suggestions, review/edit, dry-run, confirm, inspect history, attempt safe undo.
5. Document data flow and what is local; state clearly that files change only after approval.
6. Add release checklist: clean setup, tests, `.gitignore`, secrets, configuration, Git status.
7. Inspect `git diff` and `git status`; do not commit/push unless asked. Explain suggested Git commands before any publishing action.
8. Be honest about unfinished features, tests not run, and platform limitations.
## Acceptance
Documentation matches actual behavior; demo uses synthetic data; no release/commit/push without permission. Provide readiness summary and next actions. Stop after Phase 9.
