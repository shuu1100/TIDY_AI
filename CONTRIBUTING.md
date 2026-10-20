# Contributing to TidyAI

Thank you for your interest in contributing to **TidyAI**! 

TidyAI is built under strict safety and privacy principles. All contributions must respect and preserve these non-negotiable boundaries.

---

## 🔒 Non-Negotiable Safety Rules

Every feature or bug fix must satisfy the following criteria:

1. **Local-Only Operation (`127.0.0.1`)**:
   - The application must never make external cloud API calls or introduce third-party telemetry, remote trackers, or cloud fallbacks.
2. **Approved Root Sandboxing**:
   - Filesystem operations must be strictly confined to user-approved directories.
   - All paths must be canonicalized and checked via `resolve_and_verify_containment()`.
   - Rejection of path traversal (`..`), Windows drive escapes (`C:`, `D:`), UNC paths (`\\server\share`), and alternate data streams (`:`) is strictly required.
3. **Deterministic Backend Authority**:
   - AI outputs (from local Ollama) are treated as untrusted proposals. All categories, filenames, and paths must be validated by deterministic backend logic.
4. **Zero Unconfirmed Mutations**:
   - The backend must strictly require explicit user confirmation (`confirmed: true`) before making any disk modifications.
   - Dry-run simulation must remain strictly read-only with guaranteed zero disk mutations.
5. **No Silent Overwrites / No Auto-Deletions**:
   - Duplicate detection is diagnostic only. Automatic deletions are forbidden.
   - Collisions at target paths must fail closed (`silent overwrites forbidden`).
6. **Reversible Undo**:
   - All disk mutations must be recorded in the SQLite audit ledger with safe LIFO reversal capabilities.

---

## 🛠️ Development Setup (Windows PowerShell)

### Prerequisites
- Python 3.11+
- Node.js 20+ (with npm)
- Ollama running locally on `http://127.0.0.1:11434` with model `qwen3:4b` (`ollama pull qwen3:4b`)

### Quickstart
1. Clone the repository and navigate into the project directory:
   ```powershell
   cd TIDY_AI
   ```
2. Copy the environment configuration:
   ```powershell
   Copy-Item .env.example .env
   ```
3. Run the backend service (FastAPI on `127.0.0.1:8765`):
   ```powershell
   powershell -File scripts/run_backend.ps1
   ```
4. In a separate terminal, run the frontend dashboard (Next.js on `127.0.0.1:3000`):
   ```powershell
   powershell -File scripts/run_frontend.ps1
   ```

---

## 🧪 Testing Standards

Before opening a pull request, run the full test suite:
```powershell
powershell -File scripts/run_tests.ps1
```

This runner executes:
1. **Pytest Backend Suite**: All unit, integration, and security audit tests.
2. **Frontend Type Check**: `npx tsc --noEmit`.
3. **Frontend Linter**: `npm run lint`.

### Rules for Tests:
- **Never touch real user files**. Always use `tmp_path` fixtures or synthetic files from `sample_data/`.
- New security-sensitive features must include regression tests in `backend/tests/test_security_audit.py`.

---

## 📝 Pull Request Guidelines

1. Ensure all tests and lint checks pass cleanly.
2. Keep PRs focused on a single feature or bug fix.
3. Provide a clear description of the change, test evidence, and any security considerations.
