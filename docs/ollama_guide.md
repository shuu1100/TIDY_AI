# TidyAI Local Ollama AI Setup & Troubleshooting Guide

TidyAI is designed with a **strict local privacy mandate**. All generative reasoning, file categorization, and destination suggestions are executed locally using **Ollama** on `http://127.0.0.1:11434`.

---

## 1. Prerequisites & Installation

1. **Download Ollama for Windows**:
   - Official installer: [https://ollama.com/download/windows](https://ollama.com/download/windows)
2. **Install**: Run the installer and complete the setup wizard.
3. **Verify Daemon**:
   Open Windows PowerShell and check:
   ```powershell
   ollama --version
   ```

---

## 2. Recommended Local Models

TidyAI defaults to `qwen3-vl:8b`, which provides fast, structured JSON reasoning for categorization and metadata analysis:

```powershell
# Default recommended model
ollama pull qwen3-vl:8b

# Alternative lightweight model
ollama pull llama3:8b

# Alternative compact model
ollama pull mistral:7b
```

---

## 3. Configuring TidyAI Environment

Copy `.env.example` to `.env` in the repository root and adjust your model if needed:

```env
# Backend Binding
HOST=127.0.0.1
PORT=8765

# Local Ollama Provider (Zero Cloud Calls)
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3-vl:8b
OLLAMA_TIMEOUT_SECONDS=15.0
```

---

## 4. Privacy & Safety Guarantees

- **No Automatic Downloads**: TidyAI will **never** automatically initiate model downloads (`/api/pull`) in the background. If a model is not installed, the app reports a clear status error with instructions to run `ollama pull <model>`.
- **No Cloud Fallbacks**: If the local Ollama server is offline or times out, TidyAI **never** falls back to third-party cloud APIs (such as OpenAI, Anthropic, or external proxies).
- **Metadata Only by Default**: Document contents are **never** transmitted to the model during categorization; only sanitized metadata (filename, extension, file size, relative directory structure) is sent.
- **Untrusted Output Defense**: All model outputs are strictly validated by deterministic Pydantic schemas. The model is never permitted to execute code or directly mutate the filesystem.

---

## 5. Offline Operation & Troubleshooting

If Ollama is stopped or unreachable:
1. **Core Features Remain Active**: You can still register approved directory roots, run read-only inventory scans, and perform exact SHA-256 duplicate detection.
2. **Check Daemon Status**:
   In PowerShell:
   ```powershell
   ollama list
   ```
3. **Start the Local Daemon Manually**:
   If the daemon is not running in the background:
   ```powershell
   ollama serve
   ```
4. **Test Connection in TidyAI**:
   Visit the TidyAI dashboard at `http://127.0.0.1:3000` or test via the API:
   ```powershell
   Invoke-RestMethod -Uri http://127.0.0.1:8765/api/ollama/status
   ```
