"""Tests for TidyAI local Ollama AI provider.

All network calls are mocked to ensure zero dependency on external services
or running background daemons during automated testing.
"""

from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from fastapi.testclient import TestClient
from pydantic import BaseModel
from backend.app.config import settings
from backend.app.main import app
from backend.app.schemas import OllamaHealthState, OllamaStatusResponse
from backend.app.services.ollama import (
    OllamaConnectionError,
    OllamaJsonParseError,
    OllamaModelNotFoundError,
    OllamaService,
    OllamaTimeoutError,
    clean_markdown_json,
)


@pytest.fixture
def client():
    """TestClient fixture with app lifecycle managed."""
    with TestClient(app) as test_client:
        yield test_client


class MockCategorySchema(BaseModel):
    category: str
    confidence: float
    rationale: str


# ==============================================================================
# Helper Unit Tests
# ==============================================================================

def test_clean_markdown_json():
    """Verify markdown code block fences are stripped cleanly."""
    raw_fenced = "```json\n{\"key\": \"value\"}\n```"
    assert clean_markdown_json(raw_fenced) == '{"key": "value"}'

    raw_generic = "```\n{\"key\": \"value\"}\n```"
    assert clean_markdown_json(raw_generic) == '{"key": "value"}'

    raw_plain = '{"key": "value"}'
    assert clean_markdown_json(raw_plain) == '{"key": "value"}'


# ==============================================================================
# Health & Status Checks (Mocked HTTP)
# ==============================================================================

@pytest.mark.asyncio
async def test_ollama_status_healthy():
    """Server is reachable and configured model is installed."""
    service = OllamaService(model_name="qwen3:4b")

    mock_version = MagicMock(status_code=200)
    mock_version.json.return_value = {"version": "0.40.6"}

    mock_tags = MagicMock(status_code=200)
    mock_tags.json.return_value = {
        "models": [{"name": "qwen3:4b"}, {"name": "mistral:latest"}]
    }

    with patch("httpx.AsyncClient.get", side_effect=[mock_version, mock_tags]):
        status_res = await service.get_status()

    assert status_res.state == OllamaHealthState.HEALTHY
    assert status_res.reachable is True
    assert status_res.model_installed is True
    assert status_res.version == "0.40.6"
    assert "qwen3:4b" in status_res.available_models
    assert status_res.install_command is None


@pytest.mark.asyncio
async def test_ollama_status_server_unreachable():
    """Server cannot be reached on 127.0.0.1:11434."""
    service = OllamaService(model_name="qwen3:4b")

    with patch("httpx.AsyncClient.get", side_effect=httpx.ConnectError("Connection refused")):
        status_res = await service.get_status()

    assert status_res.state == OllamaHealthState.SERVER_UNREACHABLE
    assert status_res.reachable is False
    assert status_res.model_installed is False
    assert status_res.install_command == "ollama serve"
    assert "unreachable" in status_res.message.lower()


@pytest.mark.asyncio
async def test_ollama_status_timeout():
    """Server connection times out during version health check."""
    service = OllamaService(model_name="qwen3:4b")

    with patch("httpx.AsyncClient.get", side_effect=httpx.TimeoutException("Connect timed out")):
        status_res = await service.get_status()

    assert status_res.state == OllamaHealthState.SERVER_UNREACHABLE
    assert status_res.reachable is False
    assert status_res.model_installed is False
    assert status_res.install_command == "ollama serve"
    assert "timed out" in status_res.message.lower()


@pytest.mark.asyncio
async def test_ollama_status_model_missing():
    """Server is running, but configured model is not downloaded."""
    service = OllamaService(model_name="qwen3:4b")

    mock_version = MagicMock(status_code=200)
    mock_version.json.return_value = {"version": "0.40.6"}

    mock_tags = MagicMock(status_code=200)
    mock_tags.json.return_value = {
        "models": [{"name": "llama3:8b"}, {"name": "nomic-embed:latest"}]
    }

    with patch("httpx.AsyncClient.get", side_effect=[mock_version, mock_tags]):
        status_res = await service.get_status()

    assert status_res.state == OllamaHealthState.MODEL_MISSING
    assert status_res.reachable is True
    assert status_res.model_installed is False
    assert status_res.install_command == "ollama pull qwen3:4b"
    assert "not installed" in status_res.message.lower()


@pytest.mark.asyncio
async def test_ollama_status_prefix_safety_rejects_different_model():
    """Having qwen3-vl:8b installed does NOT satisfy requirement for qwen3:4b."""
    service = OllamaService(model_name="qwen3:4b")

    mock_version = MagicMock(status_code=200)
    mock_version.json.return_value = {"version": "0.40.6"}

    mock_tags = MagicMock(status_code=200)
    mock_tags.json.return_value = {
        "models": [{"name": "qwen3-vl:8b"}]
    }

    with patch("httpx.AsyncClient.get", side_effect=[mock_version, mock_tags]):
        status_res = await service.get_status()

    assert status_res.state == OllamaHealthState.MODEL_MISSING
    assert status_res.reachable is True
    assert status_res.model_installed is False
    assert status_res.install_command == "ollama pull qwen3:4b"


# ==============================================================================
# Inference & Schema Enforcement Tests
# ==============================================================================

@pytest.mark.asyncio
async def test_ollama_generate_completion_success():
    """Successful chat completion returns text and duration."""
    service = OllamaService(model_name="qwen3-vl:8b")

    # Mock healthy status
    mock_status = OllamaStatusResponse(
        state=OllamaHealthState.HEALTHY,
        reachable=True,
        version="0.40.6",
        model_installed=True,
        model_name="qwen3-vl:8b",
        available_models=["qwen3-vl:8b"],
        base_url="http://127.0.0.1:11434",
        message="Healthy",
        install_command=None,
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {"content": '{"category": "Documents/Invoices"}'}
    }

    with patch.object(service, "get_status", return_value=mock_status), \
         patch("httpx.AsyncClient.post", return_value=mock_resp):
        content, duration = await service.generate_completion("Categorize this file")

    assert content == '{"category": "Documents/Invoices"}'
    assert duration >= 0


@pytest.mark.asyncio
async def test_ollama_generate_structured_success():
    """Structured response validates against Pydantic schema."""
    service = OllamaService(model_name="qwen3-vl:8b")

    mock_status = OllamaStatusResponse(
        state=OllamaHealthState.HEALTHY,
        reachable=True,
        version="0.40.6",
        model_installed=True,
        model_name="qwen3-vl:8b",
        available_models=["qwen3-vl:8b"],
        base_url="http://127.0.0.1:11434",
        message="Healthy",
        install_command=None,
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {
            "content": '```json\n{"category": "Invoices", "confidence": 0.95, "rationale": "Filename has invoice pattern"}\n```'
        }
    }

    with patch.object(service, "get_status", return_value=mock_status), \
         patch("httpx.AsyncClient.post", return_value=mock_resp):
        result, duration = await service.generate_structured(
            prompt="Analyze invoice_2024.pdf",
            response_model=MockCategorySchema,
        )

    assert isinstance(result, MockCategorySchema)
    assert result.category == "Invoices"
    assert result.confidence == 0.95
    assert "invoice pattern" in result.rationale


@pytest.mark.asyncio
async def test_ollama_generate_malformed_json_raises():
    """Non-JSON model output raises typed OllamaJsonParseError."""
    service = OllamaService(model_name="qwen3-vl:8b")

    mock_status = OllamaStatusResponse(
        state=OllamaHealthState.HEALTHY,
        reachable=True,
        version="0.40.6",
        model_installed=True,
        model_name="qwen3-vl:8b",
        available_models=["qwen3-vl:8b"],
        base_url="http://127.0.0.1:11434",
        message="Healthy",
        install_command=None,
    )

    mock_resp = MagicMock(status_code=200)
    mock_resp.json.return_value = {
        "message": {"content": "I am not JSON, just freeform text."}
    }

    with patch.object(service, "get_status", return_value=mock_status), \
         patch("httpx.AsyncClient.post", return_value=mock_resp):
        with pytest.raises(OllamaJsonParseError) as exc_info:
            await service.generate_structured(
                prompt="test",
                response_model=MockCategorySchema,
            )

    assert "not valid JSON" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_generate_missing_model_raises():
    """Attempting inference when model is not installed raises OllamaModelNotFoundError without auto-pull."""
    service = OllamaService(model_name="nonexistent:model")

    mock_status = OllamaStatusResponse(
        state=OllamaHealthState.MODEL_MISSING,
        reachable=True,
        version="0.40.6",
        model_installed=False,
        model_name="nonexistent:model",
        available_models=[],
        base_url="http://127.0.0.1:11434",
        message="Model missing",
        install_command="ollama pull nonexistent:model",
    )

    with patch.object(service, "get_status", return_value=mock_status):
        with pytest.raises(OllamaModelNotFoundError) as exc_info:
            await service.generate_completion("prompt")

    assert "not installed locally" in str(exc_info.value)
    assert "ollama pull" in str(exc_info.value)


@pytest.mark.asyncio
async def test_ollama_generate_timeout_raises():
    """Exceeding timeout raises OllamaTimeoutError."""
    service = OllamaService(model_name="qwen3-vl:8b", timeout=0.1, max_retries=0)

    mock_status = OllamaStatusResponse(
        state=OllamaHealthState.HEALTHY,
        reachable=True,
        version="0.40.6",
        model_installed=True,
        model_name="qwen3-vl:8b",
        available_models=["qwen3-vl:8b"],
        base_url="http://127.0.0.1:11434",
        message="Healthy",
        install_command=None,
    )

    with patch.object(service, "get_status", return_value=mock_status), \
         patch("httpx.AsyncClient.post", side_effect=httpx.TimeoutException("Read timed out")):
        with pytest.raises(OllamaTimeoutError) as exc_info:
            await service.generate_completion("prompt")

    assert "timed out" in str(exc_info.value)


# ==============================================================================
# API Endpoints Integration Tests (Mocked)
# ==============================================================================

def test_api_ollama_test_endpoint_success(client):
    """POST /api/ollama/test succeeds with mock Ollama response."""
    with patch(
        "backend.app.services.ollama.ollama_service.generate_completion",
        new=AsyncMock(return_value=('{"status": "ok"}', 120.5)),
    ):
        resp = client.post(
            "/api/ollama/test",
            json={"prompt": "Ping Ollama"},
        )
    assert resp.status_code == 200
    data = resp.json()
    assert data["model"] == settings.ollama_model
    assert data["response_text"] == '{"status": "ok"}'
    assert data["duration_ms"] == 120.5


def test_api_ollama_test_endpoint_offline_503(client):
    """POST /api/ollama/test returns 503 when local daemon is unreachable."""
    with patch(
        "backend.app.services.ollama.ollama_service.generate_completion",
        side_effect=OllamaConnectionError("Daemon offline"),
    ):
        resp = client.post(
            "/api/ollama/test",
            json={"prompt": "Ping Ollama"},
        )
    assert resp.status_code == 503
    assert "unreachable" in resp.json()["detail"].lower()


def test_api_ollama_test_endpoint_timeout_504(client):
    """POST /api/ollama/test returns 504 when inference times out."""
    with patch(
        "backend.app.services.ollama.ollama_service.generate_completion",
        side_effect=OllamaTimeoutError("Request timed out after 90.0s"),
    ):
        resp = client.post(
            "/api/ollama/test",
            json={"prompt": "Ping Ollama"},
        )
    assert resp.status_code == 504
    assert "timed out" in resp.json()["detail"].lower()


def test_api_ollama_test_endpoint_missing_model_404(client):
    """POST /api/ollama/test returns 404 when requested model is not installed."""
    with patch(
        "backend.app.services.ollama.ollama_service.generate_completion",
        side_effect=OllamaModelNotFoundError("Model 'qwen3:4b' not installed"),
    ):
        resp = client.post(
            "/api/ollama/test",
            json={"prompt": "Ping Ollama"},
        )
    assert resp.status_code == 404
    assert "not installed" in resp.json()["detail"].lower()

