import base64
import logging

import pytest
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app

PRIMARY = "primary-test-key"
SECONDARY = "secondary-test-key"
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


@pytest.fixture
def client(tmp_path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "api_key", PRIMARY)
    monkeypatch.setattr(settings, "api_key_secondary", "")
    monkeypatch.setattr(settings, "storage_path", tmp_path)
    monkeypatch.setattr(settings, "base_url", "https://apimg.com.br")
    return TestClient(app, raise_server_exceptions=False)


def _upload(client: TestClient, key: str | None = PRIMARY, *, bearer: bool = False):
    headers: dict[str, str] = {}
    if key is not None:
        if bearer:
            headers["Authorization"] = f"Bearer {key}"
        else:
            headers["X-API-Key"] = key
    return client.post(
        "/v1/upload",
        headers=headers,
        files={"file": ("pixel.png", VALID_PNG, "image/png")},
    )


def test_primary_key_upload(client: TestClient) -> None:
    response = _upload(client, PRIMARY)
    assert response.status_code == 200
    assert response.json()["public_id"]


def test_secondary_key_upload_when_configured(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_key_secondary", SECONDARY)
    response = _upload(client, SECONDARY)
    assert response.status_code == 200
    assert response.json()["format"] == "PNG"


def test_secondary_key_rejected_when_unset(client: TestClient) -> None:
    response = _upload(client, SECONDARY)
    assert response.status_code == 401
    assert response.json()["detail"] == "Chave de API inválida ou ausente"


def test_invalid_key_is_401(client: TestClient) -> None:
    response = _upload(client, "wrong-key")
    assert response.status_code == 401
    assert response.json()["detail"] == "Chave de API inválida ou ausente"


def test_missing_key_is_401(client: TestClient) -> None:
    response = _upload(client, None)
    assert response.status_code == 401
    assert response.json()["detail"] == "Chave de API inválida ou ausente"


def test_bearer_primary_and_secondary(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    assert _upload(client, PRIMARY, bearer=True).status_code == 200
    assert _upload(client, SECONDARY, bearer=True).status_code == 401
    monkeypatch.setattr(settings, "api_key_secondary", SECONDARY)
    assert _upload(client, SECONDARY, bearer=True).status_code == 200


def test_secrets_are_not_exposed(client: TestClient, monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture) -> None:
    monkeypatch.setattr(settings, "api_key_secondary", SECONDARY)
    with caplog.at_level(logging.DEBUG):
        accepted = _upload(client, SECONDARY)
        rejected = _upload(client, "wrong-key")
    blob = "\n".join([accepted.text, rejected.text, caplog.text]).lower()
    assert PRIMARY not in blob
    assert SECONDARY not in blob
    assert "wrong-key" not in blob
    for marker in ("primary", "secondary", "old key", "new key"):
        assert marker not in blob
    assert rejected.json()["detail"] == "Chave de API inválida ou ausente"
