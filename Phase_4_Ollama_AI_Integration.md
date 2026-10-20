# TidyAI Phase 4 — Ollama Local AI Integration

Integrate Ollama through a reusable local provider. Do not add file mutations.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Read `OLLAMA_BASE_URL` (default `http://127.0.0.1:11434`) and configured model name from environment; never hard-code secrets or assume a model exists.
2. Never pull/download a model automatically and never fall back silently to cloud inference.
3. Implement server/model health checks distinguishing unreachable server, missing model, and successful inference.
4. Use timeouts, bounded retries, typed errors, and strict JSON/Pydantic validation.
5. Treat model output as untrusted. Never execute generated code or commands; send only necessary metadata, not document contents by default.
6. Keep the app usable if Ollama is offline.
7. Mock HTTP responses in tests so tests do not need Ollama or a model.
8. Document how the user can manually install/start Ollama and select a model.
## Acceptance
Inference remains local to configured Ollama endpoint; malformed output and timeouts are handled; no mutation is triggered. Stop after Phase 4.
