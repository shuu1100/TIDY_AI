"""Tests for TidyAI health endpoints and initial scaffolding."""

import pytest
from fastapi.testclient import TestClient
from backend.app.config import settings
from backend.app.main import app
from backend.app.schemas import HealthResponse, OllamaStatusResponse
from backend.app.services.ollama import ollama_service


@pytest.fixture
def client():
    """TestClient fixture with app lifecycle managed."""
    with TestClient(app) as test_client:
        yield test_client


def test_root_endpoint(client):
    """Test that the root endpoint responds with welcoming message and metadata."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "version" in data
    assert "health_url" in data
    assert "127.0.0.1" in data["message"]


def test_health_endpoint(client):
    """Test that /api/health returns valid schema and reports database connectivity."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    
    # Validate against Pydantic schema
    validated = HealthResponse(**data)
    assert validated.status == "ok"
    assert validated.service == "tidy-ai-backend"
    assert validated.host == "127.0.0.1"
    assert validated.port == 8765
    assert validated.database_connected is True
    assert validated.ollama_configured is True
    assert validated.ollama_model == settings.ollama_model


def test_ollama_status_endpoint(client):
    """Test /api/ollama/status endpoint returns valid OllamaStatusResponse schema."""
    response = client.get("/api/ollama/status")
    assert response.status_code == 200
    data = response.json()
    
    # Validate against Pydantic schema
    validated = OllamaStatusResponse(**data)
    assert validated.model_name == settings.ollama_model
    assert isinstance(validated.reachable, bool)
    assert isinstance(validated.model_installed, bool)
    assert validated.state in ["healthy", "server_unreachable", "model_missing"]
