# TidyAI Local Ollama AI Setup & Troubleshooting Guide

TidyAI is designed with a **strict local privacy mandate**. All generative reasoning, file categorization, and destination suggestions are executed locally using **Ollama** on `http://127.0.0.1:11434`.

---

## 1. Prerequisites & Installation

1. **Download Ollama for Windows**:
   - Official installer: [https://ollama.com/download/windows](https://ollama.com/download/windows)
2. **Install**: Run the installer and complete the setup wizard.
3. **Verify Daemon**:
   Open Windows PowerShell and verify:
   ```powershell
   ollama --version
   ```

---

## 2. Recommended Primary Model: Qwen3 4B

TidyAI is configured by default to use **`qwen3:4b`**, which offers exceptionally fast, structured JSON reasoning with a minimal memory footprint (~2.5 GB VRAM/RAM):

```powershell
# Pull the default primary model
ollama pull qwen3:4b
```

### Alternative Models
You can also use larger or vision-enabled local models if your hardware allows:
```powershell
# Larger reasoning model
ollama pull qwen3:8b

# Vision-language model
ollama pull qwen3-vl:8b

# Alternative compact model
ollama pull mistral:7b
```

---

## 3. Configuring TidyAI Environment

Copy `.env.example` to `.env` in the repository root and adjust your model if needed:

```env
# Backend Binding (Strictly Local)
HOST=127.0.0.1
PORT=8765

# Local Ollama Provider (Zero Cloud Calls)
# Native Windows: http://127.0.0.1:11434 | Docker backend: http://host.docker.internal:11434
OLLAMA_BASE_URL=http://127.0.0.1:11434
OLLAMA_MODEL=qwen3:4b
OLLAMA_CONNECT_TIMEOUT_SECONDS=5.0
OLLAMA_READ_TIMEOUT_SECONDS=90.0
OLLAMA_TIMEOUT_SECONDS=90.0
```

> **Performance Note (`think: false`)**: TidyAI automatically sends `"think": false` in Ollama API calls for thinking-capable models like Qwen3. This bypasses redundant chain-of-thought token generation and accelerates structured JSON proposal generation from ~40–90 seconds down to **~3–5 seconds** on local CPUs/GPUs.

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
   Visit the **API & AI Status** tab in the TidyAI dashboard (`http://127.0.0.1:3000`) and click **"Test Local Inference Ping"**, or test via PowerShell:
   ```powershell
   Invoke-RestMethod -Uri http://127.0.0.1:8765/api/ollama/status
   ```
