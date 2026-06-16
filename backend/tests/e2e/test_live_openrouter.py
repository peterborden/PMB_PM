import os

import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.mark.skipif(
    not os.getenv("OPENROUTER_API_KEY"),
    reason="OPENROUTER_API_KEY not configured",
)
def test_live_openrouter_diagnostic() -> None:
    client = TestClient(create_app())
    login_response = client.post(
        "/api/auth/login",
        json={"username": "user", "password": "password"},
    )
    assert login_response.status_code == 200

    response = client.get("/api/ai/diagnostic")
    assert response.status_code == 200
    payload = response.json()
    assert payload["model"] == "openai/gpt-oss-120b"
    assert payload["prompt"] == "2+2"
    assert isinstance(payload["answer"], str)
    assert payload["answer"].strip() != ""
