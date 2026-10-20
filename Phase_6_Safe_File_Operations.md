# TidyAI Phase 6 — Safe Operations, Dry-Run, History, and Undo

Highest-risk phase. Review existing scanner and suggestion code before implementing.

## Safety rules
- Work only in the confirmed TidyAI project folder. Never modify ChemRAG, Universal Menu Translator, or unrelated projects.
- Do not scan or change real personal folders during development/tests; use temporary directories and synthetic sample files.
- No destructive commands, silent overwrites, automatic deletes, external AI APIs, telemetry, or model-generated code execution.
- AI only proposes; deterministic backend validation and explicit user approval are required.
- Report files changed, commands/tests actually run, results, and blockers. Stop after this phase.

## Non-negotiable safeguards
- Every mutation requires explicit user confirmation.
- Dry-run must not mutate files or create directories.
- Never silently overwrite; never delete duplicates.
- Revalidate source, destination, root containment, and collisions immediately before mutation.
- Reject traversal, absolute/drive/UNC paths, reserved names, and symlink/junction escapes.
- Never execute shell commands or model-generated code.

## Tasks
1. Create a typed operation plan with source/destination relative paths, operation type, validation, and approval.
2. Dry-run reports exact intended changes without filesystem changes.
3. Separate apply endpoint accepts only approved, validated plans.
4. Revalidate immediately before each operation and refuse collisions.
5. Record per-item success/failure and partial batches accurately; use safe staging/atomic operations where practical.
6. Persist minimal SQLite history: operation ID, timestamp, relative paths, status, and errors; never store file contents.
7. Undo only if current state matches the recorded destination and restoration will not overwrite anything; otherwise refuse.
8. Test dry-run invariance, successful move/rename inside root, collisions, changed/missing source, escape attempts, partial failures, repeated requests, and safe/unsafe undo.
## Acceptance
No silent overwrite or auto-delete; unsafe cases fail closed; undo never overwrites. Stop after Phase 6.
