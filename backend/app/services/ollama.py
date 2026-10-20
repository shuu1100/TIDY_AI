"""Local Ollama AI provider for TidyAI.

Integrates Ollama through a local-only HTTP interface (127.0.0.1:11434).
Treats all model output as untrusted and enforces strict JSON validation.
Never initiates automatic model downloads or falls back to cloud services.
"""

import asyncio
import json
import re
import time
from typing import Any, Dict, List, Optional, Tuple, Type, TypeVar
import httpx
from pydantic import BaseModel, ValidationError
from backend.app.config import settings
from backend.app.schemas import OllamaHealthState, OllamaStatusResponse

T = TypeVar("T", bound=BaseModel)


class OllamaError(Exception):
    """Base exception for all Ollama-related failures."""
    pass


class OllamaConnectionError(OllamaError):
    """Raised when Ollama local daemon is unreachable or connection is refused."""
    pass


class OllamaTimeoutError(OllamaError):
    """Raised when Ollama request exceeds timeout limit."""
    pass


class OllamaModelNotFoundError(OllamaError):
    """Raised when the requested model is not installed in the local Ollama instance."""
    pass


class OllamaResponseError(OllamaError):
    """Raised when Ollama returns an unexpected HTTP error status."""
    pass


class OllamaJsonParseError(OllamaError):
    """Raised when model response cannot be parsed or validated against the expected schema."""
    pass


def clean_markdown_json(raw_text: str) -> str:
    """Clean markdown code fences from model response to isolate raw JSON."""
    text = raw_text.strip()
    # Match ```json ... ``` or ``` ... ```
    pattern = r"^```(?:json)?\s*([\s\S]*?)\s*```$"
    match = re.search(pattern, text, re.IGNORECASE)
    if match:
        return match.group(1).strip()
    return text


class OllamaService:
    """Local Ollama service client with health checks, retries, and schema enforcement."""

    def __init__(
        self,
        base_url: Optional[str] = None,
        model_name: Optional[str] = None,
        timeout: Optional[float] = None,
        connect_timeout: Optional[float] = None,
        read_timeout: Optional[float] = None,
        max_retries: int = 1,
    ) -> None:
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model_name = model_name or settings.ollama_model
        self.connect_timeout = (
            connect_timeout
            if connect_timeout is not None
            else settings.ollama_connect_timeout_seconds
        )
        self.read_timeout = (
            read_timeout
            if read_timeout is not None
            else (timeout if timeout is not None else settings.ollama_read_timeout_seconds)
        )
        self.timeout = self.read_timeout  # backwards compatibility
        self.max_retries = max_retries

    @staticmethod
    def _check_model_installed(target_model: str, available_models: List[str]) -> bool:
        """Check if target model is present in Ollama's available models list.

        Handles:
        - Exact match: e.g. "qwen3:4b" == "qwen3:4b"
        - Implicit latest tag: e.g. "qwen3" matches "qwen3:latest", or "qwen3:latest" matches "qwen3"
        - Rejects prefix collisions: e.g. "qwen3-vl:8b" does not falsely match "qwen3:4b".
        """
        target_lower = target_model.strip().lower()
        target_base = target_lower.split(":")[0]
        target_tag = target_lower.split(":")[1] if ":" in target_lower else "latest"

        for m in available_models:
            m_lower = m.strip().lower()
            if m_lower == target_lower:
                return True
            m_base = m_lower.split(":")[0]
            m_tag = m_lower.split(":")[1] if ":" in m_lower else "latest"
            if m_base == target_base and m_tag == target_tag:
                return True
        return False

    async def get_status(self) -> OllamaStatusResponse:
        """Inspect health of local Ollama server and verify target model availability.

        Distinguishes:
        - SERVER_UNREACHABLE: Daemon not running or port 11434 not listening / timed out.
        - MODEL_MISSING: Daemon running, but configured model not in tags.
        - HEALTHY: Daemon running and model installed.
        """
        check_timeout = httpx.Timeout(timeout=5.0, connect=self.connect_timeout)
        try:
            async with httpx.AsyncClient(timeout=check_timeout) as client:
                # 1. Query Ollama version (verifies daemon connectivity)
                try:
                    version_resp = await client.get(f"{self.base_url}/api/version")
                except (httpx.ConnectError, ConnectionRefusedError) as exc:
                    return OllamaStatusResponse(
                        state=OllamaHealthState.SERVER_UNREACHABLE,
                        reachable=False,
                        version=None,
                        model_installed=False,
                        model_name=self.model_name,
                        available_models=[],
                        base_url=self.base_url,
                        message=f"Local Ollama server is unreachable at {self.base_url}. Ensure daemon is running ('ollama serve').",
                        install_command="ollama serve",
                    )
                except (httpx.ConnectTimeout, httpx.TimeoutException) as exc:
                    return OllamaStatusResponse(
                        state=OllamaHealthState.SERVER_UNREACHABLE,
                        reachable=False,
                        version=None,
                        model_installed=False,
                        model_name=self.model_name,
                        available_models=[],
                        base_url=self.base_url,
                        message=f"Connection timed out reaching Ollama server at {self.base_url}.",
                        install_command="ollama serve",
                    )

                if version_resp.status_code != 200:
                    return OllamaStatusResponse(
                        state=OllamaHealthState.SERVER_UNREACHABLE,
                        reachable=False,
                        version=None,
                        model_installed=False,
                        model_name=self.model_name,
                        available_models=[],
                        base_url=self.base_url,
                        message=f"Ollama server returned unexpected HTTP status {version_resp.status_code}.",
                        install_command="ollama serve",
                    )

                version = version_resp.json().get("version", "unknown")

                # 2. Server is reachable; now verify configured model availability
                try:
                    tags_resp = await client.get(f"{self.base_url}/api/tags")
                except httpx.TimeoutException:
                    return OllamaStatusResponse(
                        state=OllamaHealthState.SERVER_UNREACHABLE,
                        reachable=True,
                        version=version,
                        model_installed=False,
                        model_name=self.model_name,
                        available_models=[],
                        base_url=self.base_url,
                        message="Ollama server responded to version check, but listing models timed out.",
                        install_command=f"ollama pull {self.model_name}",
                    )

                available_models: List[str] = []
                model_installed = False

                if tags_resp.status_code == 200:
                    tags_data = tags_resp.json()
                    available_models = [m.get("name", "") for m in tags_data.get("models", [])]
                    model_installed = self._check_model_installed(self.model_name, available_models)

                if not model_installed:
                    return OllamaStatusResponse(
                        state=OllamaHealthState.MODEL_MISSING,
                        reachable=True,
                        version=version,
                        model_installed=False,
                        model_name=self.model_name,
                        available_models=available_models,
                        base_url=self.base_url,
                        message=f"Ollama server is running (v{version}), but model '{self.model_name}' is not installed.",
                        install_command=f"ollama pull {self.model_name}",
                    )

                return OllamaStatusResponse(
                    state=OllamaHealthState.HEALTHY,
                    reachable=True,
                    version=version,
                    model_installed=True,
                    model_name=self.model_name,
                    available_models=available_models,
                    base_url=self.base_url,
                    message=f"Ollama server is healthy (v{version}). Local model '{self.model_name}' is ready.",
                    install_command=None,
                )

        except Exception as exc:
            return OllamaStatusResponse(
                state=OllamaHealthState.SERVER_UNREACHABLE,
                reachable=False,
                version=None,
                model_installed=False,
                model_name=self.model_name,
                available_models=[],
                base_url=self.base_url,
                message=f"Error inspecting Ollama status: {str(exc)}",
                install_command="ollama serve",
            )

    async def generate_completion(
        self,
        prompt: str,
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
        enforce_json: bool = True,
    ) -> Tuple[str, float]:
        """Send chat prompt to local Ollama with bounded retries and timeouts.

        Returns (cleaned_response_text, duration_ms).
        """
        # Pre-check server and model availability
        status_info = await self.get_status()
        if not status_info.reachable:
            raise OllamaConnectionError(f"Ollama server is unreachable at {self.base_url}. {status_info.message}")
        if not status_info.model_installed:
            raise OllamaModelNotFoundError(
                f"Model '{self.model_name}' is not installed locally. Run: '{status_info.install_command}'."
            )

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        payload: Dict[str, Any] = {
            "model": self.model_name,
            "messages": messages,
            "stream": False,
            "think": False,
            "options": {"temperature": max(0.0, min(1.0, temperature))},
        }
        if enforce_json:
            payload["format"] = "json"

        start_time = time.perf_counter()
        last_exception: Optional[Exception] = None
        chat_timeout = httpx.Timeout(timeout=self.read_timeout, connect=self.connect_timeout)

        for attempt in range(self.max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=chat_timeout) as client:
                    resp = await client.post(f"{self.base_url}/api/chat", json=payload)

                    if resp.status_code == 404:
                        raise OllamaModelNotFoundError(
                            f"Model '{self.model_name}' not found by Ollama server: {resp.text}"
                        )
                    if resp.status_code != 200:
                        raise OllamaResponseError(
                            f"Ollama server returned HTTP {resp.status_code}: {resp.text}"
                        )

                    data = resp.json()
                    msg = data.get("message", {}).get("content", "")
                    cleaned = clean_markdown_json(msg)
                    duration_ms = (time.perf_counter() - start_time) * 1000.0
                    return cleaned, round(duration_ms, 2)

            except (httpx.ConnectError, httpx.ConnectTimeout) as exc:
                last_exception = OllamaConnectionError(
                    f"Connection refused connecting to Ollama at {self.base_url}: {str(exc)}"
                )
            except httpx.TimeoutException as exc:
                last_exception = OllamaTimeoutError(
                    f"Ollama request timed out after {self.read_timeout}s: {str(exc)}"
                )
                # Fail fast on inference timeout to avoid multiplying wait time across retries
                break
            except (OllamaModelNotFoundError, OllamaResponseError):
                raise
            except Exception as exc:
                last_exception = OllamaError(f"Unexpected error communicating with Ollama: {str(exc)}")

            # Exponential backoff between retries for transient connection errors
            if attempt < self.max_retries:
                await asyncio.sleep(0.5 * (2 ** attempt))

        if last_exception:
            raise last_exception
        raise OllamaError("Failed to generate completion from local Ollama.")

    async def generate_structured(
        self,
        prompt: str,
        response_model: Type[T],
        system_prompt: Optional[str] = None,
        temperature: float = 0.1,
    ) -> Tuple[T, float]:
        """Generate local completion and strictly validate it against a Pydantic model schema."""
        raw_text, duration_ms = await self.generate_completion(
            prompt=prompt,
            system_prompt=system_prompt,
            temperature=temperature,
            enforce_json=True,
        )

        try:
            parsed_json = json.loads(raw_text)
        except json.JSONDecodeError as j_err:
            raise OllamaJsonParseError(
                f"Model response was not valid JSON: {str(j_err)}\nRaw output: {raw_text[:200]}"
            )

        try:
            validated = response_model.model_validate(parsed_json)
            return validated, duration_ms
        except ValidationError as v_err:
            raise OllamaJsonParseError(
                f"Model output failed schema validation for {response_model.__name__}: {str(v_err)}"
            )


ollama_service = OllamaService()
