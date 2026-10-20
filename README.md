# TidyAI — Privacy-First File Organization Assistant

[![Status](https://img.shields.io/badge/Status-Phase%201%20Complete-emerald)](#)
[![License](https://img.shields.io/badge/Privacy-100%25%20Local-blue)](#)
[![Security](https://img.shields.io/badge/Security-Fail--Closed%20Boundaries-purple)](#)

**TidyAI** is an intelligent, local-first file organization assistant designed to help users categorize, deduplicate, and tidy disorganized folders with absolute privacy and deterministic safety.

---

## 🔒 Core Safety Principles

1. **Strict Local Processing (`127.0.0.1`)**: All operations run locally. Backend binds exclusively to `127.0.0.1:8765`, frontend to `127.0.0.1:3000`, and AI inference to local Ollama on `127.0.0.1:11434`. Zero cloud telemetry or external network calls.
2. **Approved Root Sandboxing**: File operations are confined to explicitly user-approved directories. Operations outside approved roots are rejected immediately.
3. **AI Proposes, Backend Disposes**: AI models generate suggestions only. Deterministic backend logic validates every filename, extension, path containment, and collision check.
4. **No Silent Overwrites / No Auto-Deletions**: Duplicate detection is purely diagnostic. Files are never deleted automatically.
5. **Two-Stage Execution**: Every filesystem mutation requires human review, dry-run simulation, and explicit secondary confirmation, backed by a safe, reversible SQLite undo ledger.

---

## 🏗️ Architecture & Technology Stack

```
TidyAI
├── frontend/               # Next.js 16 (App Router) + TypeScript + Tailwind CSS
│   ├── src/app/            # Responsive, calm dashboard shell & views
│   └── src/lib/api.ts      # Typed local API client
├── backend/                # Python 3.14 + FastAPI + Pydantic v2
│   ├── app/                # Core application package
│   │   ├── config.py       # Pydantic Settings & environment config
│   │   ├── database.py     # SQLite connection & audit ledger schema
│   │   ├── schemas.py      # Typed API request/response models
│   │   ├── services/       # Ollama provider stub & service helpers
│   │   └── main.py         # FastAPI routes, CORS, and lifespan management
│   ├── tests/              # Pytest test suite (health, boundary checks)
│   └── requirements.txt    # Python dependencies
├── sample_data/            # Harmless synthetic files for safe development & tests
├── scripts/                # Windows PowerShell execution scripts
├── docs/                   # Architecture and security documentation
├── .env.example            # Safe environment template
├── PLAN.md                 # Master architecture specification & phase roadmap
└── WORKSPACE_AUDIT.md      # Phase 0 workspace & environment audit
```

---

## 📋 Prerequisites

- **Node.js**: v20+ (Verified on `v24.20.0`, npm `11.19.0`)
- **Python**: 3.11+ (Verified on `3.14.6`)
- **Git**: 2.40+ (Verified on `2.55.0.windows.2`)
- **Ollama**: Local daemon running with a model such as `qwen3-vl:8b` (optional for Phase 1 skeleton, required in Phase 4+)

---

## 🚀 Windows PowerShell Quickstart

### 1. Configure Environment
Copy the environment template:
```powershell
Copy-Item .env.example .env
```

### 2. Run Backend (FastAPI on 127.0.0.1:8765)
The backend script automatically initializes the virtual environment (`backend/.venv`) if missing, installs dependencies, and launches Uvicorn:
```powershell
powershell -File scripts/run_backend.ps1
```
*Health Endpoint*: Visit [http://127.0.0.1:8765/api/health](http://127.0.0.1:8765/api/health)  
*API Docs*: Visit [http://127.0.0.1:8765/docs](http://127.0.0.1:8765/docs)

### 3. Run Frontend (Next.js Dashboard on 127.0.0.1:3000)
In a new PowerShell terminal:
```powershell
powershell -File scripts/run_frontend.ps1
```
Visit [http://127.0.0.1:3000](http://127.0.0.1:3000) to view the TidyAI dashboard shell.

### 4. Run Automated Tests
Execute the unified test runner to verify Python backend tests, TypeScript types, and ESLint:
```powershell
powershell -File scripts/run_tests.ps1
```

---

## 🧪 Synthetic Test Data (`sample_data/`)

To prevent accidental modification of real user folders, development and testing use synthetic files in `sample_data/`:
- `invoices/`: Simulated invoices and receipts (`.txt`)
- `photos/`: Simulated image files and exact content duplicates
- `reports/`: Harmless CSV tabular data
- `notes/`: Text meeting notes
- `empty_files/`: Zero-byte edge-case test file

---

## 🗺️ Project Roadmap

- [x] **Phase 0**: Workspace Audit & Architecture Planning ([WORKSPACE_AUDIT.md](file:///c:/local_disc_D/Hackathan/TIDY_AI/WORKSPACE_AUDIT.md), [PLAN.md](file:///c:/local_disc_D/Hackathan/TIDY_AI/PLAN.md))
- [x] **Phase 1**: Project Scaffolding (Skeleton, SQLite, Ollama Stub, Dashboard Shell, Tests)
- [ ] **Phase 2**: Secure Read-Only File Scanner (Containment checks & metadata inventory)
- [ ] **Phase 3**: Exact Duplicate Detection (Chunked SHA-256 hashing)
- [ ] **Phase 4**: Local Ollama AI Integration (Client, health verification & retry logic)
- [ ] **Phase 5**: AI Categorization & Suggestion Engine (Structured path proposals)
- [ ] **Phase 6**: Safe Operations, Dry-Run, History & Reversible Undo
- [ ] **Phase 7**: Frontend Dashboard Integration (Full interactive workflow)
- [ ] **Phase 8**: QA & Security Audit (Path traversal, Windows quirks & regression suite)
- [ ] **Phase 9**: Documentation, Demo & Release Preparation
