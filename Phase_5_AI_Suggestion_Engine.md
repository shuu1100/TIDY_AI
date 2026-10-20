# TidyAI Phase 5 — AI Categorization and Suggestions

Generate reviewable category, filename, and destination suggestions only. Do not apply them.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Tasks
1. Define strict schemas for file ID/current relative path, category, proposed filename, destination subfolder, rationale, confidence/uncertainty, and warnings.
2. Use metadata only by default. Use local Ollama provider; handle unavailable model gracefully.
3. Require structured JSON and validate every field. Reject absolute/drive/UNC paths, `..`, reserved Windows names, invalid characters, empty names, unexpected extensions, and paths outside the approved root.
4. Validate model output in deterministic backend code; model output never defines permissions or executable actions.
5. Detect collisions and never overwrite; mark ambiguous suggestions for review.
6. UI must show original vs proposed path and let users edit/reject suggestions; show uncertainty.
7. Test malformed JSON, missing fields, traversal, reserved names, invalid characters, collisions, low confidence, and model outage using mocks/temp directories.
## Acceptance
Suggestions are never applied automatically; invalid output fails closed. Stop after Phase 5.
