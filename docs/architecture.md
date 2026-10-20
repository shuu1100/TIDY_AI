# TidyAI Architecture Overview

## Privacy & Safety Mandates

1. **Local-First Processing**: All scanning, hashing, analysis, and Ollama inference occurs exclusively on the local host (`127.0.0.1`).
2. **Approved Root Sandboxing**: File operations are confined to explicitly user-approved directories. Any path resolution outside the boundary raises immediate security exceptions.
3. **No Automatic Mutations**: Duplicate detection and AI suggestions are non-destructive proposals. File moves/renames require explicit human approval and a dry-run preview.
4. **Zero Cloud Telemetry**: No tracking, metrics, third-party CDNs, or external APIs are integrated.

## System Components

- **Frontend (Next.js 15, App Router, TypeScript, Tailwind CSS)**:
  - Responsive, calm, and accessible dashboard.
  - Interacts exclusively with the local FastAPI backend.
  - Displays real-time operational status, scan inventories, duplicate groups, and diff reviews.

- **Backend (FastAPI, Python 3.14, Pydantic v2)**:
  - Canonical path resolution and boundary containment enforcement.
  - Streaming chunked SHA-256 duplicate detection.
  - SQLite persistence for operation ledger and safe undo tracking.
  - Reusable Ollama client stub with health verification and timeout controls.
