import base64
from pathlib import Path

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.config import settings
from app.main import app
from app.storage_service import delete_stored_file, validate_public_id

API_KEY = "test-key"
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "api_key", API_KEY)
    monkeypatch.setattr(settings, "api_key_secondary", "")
    monkeypatch.setattr(settings, "storage_path", tmp_path)
    monkeypatch.setattr(settings, "base_url", "https://apimg.com.br")
    return TestClient(app, raise_server_exceptions=False)


def _upload(client: TestClient) -> dict:
    response = client.post(
        "/v1/upload",
        headers={"X-API-Key": API_KEY},
        files={"file": ("pixel.png", VALID_PNG, "image/png")},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("https://apimg.com.br/i/")
    assert body["format"] == "PNG"
    assert body["bytes"] > 0
    assert body["width"] == 1
    assert body["height"] == 1
    return body


def _delete(client: TestClient, public_id: str, key: str | None = API_KEY):
    headers = {} if key is None else {"X-API-Key": key}
    return client.delete(f"/v1/images/{public_id}", headers=headers)


def test_delete_removes_file_and_repeat_is_idempotent(client: TestClient, tmp_path: Path) -> None:
    uploaded = _upload(client)
    public_id = uploaded["public_id"]
    assert (tmp_path / public_id).is_file()
    assert client.get(f"/i/{public_id}").status_code == 200

    deleted = _delete(client, public_id)
    assert deleted.status_code == 200
    assert deleted.json() == {"public_id": public_id, "deleted": True}
    assert not (tmp_path / public_id).exists()
    assert client.get(f"/i/{public_id}").status_code == 404

    again = _delete(client, public_id)
    assert again.status_code == 200
    assert again.json() == {"public_id": public_id, "deleted": False}


def test_missing_asset_is_idempotent(client: TestClient) -> None:
    public_id = "a" * 32 + ".png"
    response = _delete(client, public_id)
    assert response.status_code == 200
    assert response.json() == {"public_id": public_id, "deleted": False}


def test_missing_api_key_is_401(client: TestClient) -> None:
    response = _delete(client, "a" * 32 + ".png", key=None)
    assert response.status_code == 401
    assert response.json()["detail"] == "Chave de API inválida ou ausente"


def test_invalid_api_key_is_401(client: TestClient, tmp_path: Path) -> None:
    uploaded = _upload(client)
    response = _delete(client, uploaded["public_id"], key="wrong-key")
    assert response.status_code == 401
    assert (tmp_path / uploaded["public_id"]).is_file()


@pytest.mark.parametrize(
    "public_id",
    [
        "../etc/passwd",
        "..\\windows\\system32\\x.png",
        "/etc/passwd",
        "C:\\Windows\\system32\\x.png",
        "https://apimg.com.br/i/" + ("a" * 32) + ".png",
        ("a" * 32) + "/evil.png",
        ("a" * 32) + "\\evil.png",
        ("a" * 32) + ".png\x00",
        "not-a-public-id",
    ],
)
def test_unsafe_public_id_is_rejected(public_id: str) -> None:
    with pytest.raises(HTTPException) as exc:
        validate_public_id(public_id)
    assert exc.value.status_code == 400
    assert exc.value.detail == "Identificador inválido"


def test_http_traversal_does_not_escape_storage(client: TestClient, tmp_path: Path) -> None:
    outside = tmp_path.parent / "outside-secret.png"
    outside.write_bytes(b"keep")
    response = client.delete(
        "/v1/images/..%2F..%2Foutside-secret.png",
        headers={"X-API-Key": API_KEY},
    )
    assert response.status_code in (400, 404)
    assert response.status_code != 500
    assert outside.read_bytes() == b"keep"
    outside.unlink()
    assert str(tmp_path) not in response.text
    assert "/data/uploads" not in response.text


def test_resolved_path_outside_storage_is_rejected(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    storage = tmp_path / "storage"
    storage.mkdir()
    monkeypatch.setattr(settings, "storage_path", storage)
    outside = tmp_path / "outside.png"
    outside.write_bytes(b"keep")
    public_id = "b" * 32 + ".png"
    (storage / public_id).write_bytes(b"inside")
    original_resolve = Path.resolve

    def escape(self: Path, strict: bool = False) -> Path:
        if self.name == public_id:
            return outside
        return original_resolve(self, strict=strict)

    monkeypatch.setattr(Path, "resolve", escape)
    with pytest.raises(HTTPException) as exc:
        delete_stored_file(public_id)
    assert exc.value.status_code == 400
    assert outside.read_bytes() == b"keep"
    assert (storage / public_id).is_file()


def test_filesystem_error_is_not_reported_as_deleted(
    client: TestClient, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    uploaded = _upload(client)
    public_id = uploaded["public_id"]
    original_unlink = Path.unlink

    def fail_unlink(self: Path, missing_ok: bool = False) -> None:
        if self.name == public_id:
            raise PermissionError("read-only filesystem")
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", fail_unlink)
    response = _delete(client, public_id)
    assert response.status_code == 500
    assert response.json()["detail"] == "Não foi possível excluir o arquivo"
    assert response.json().get("deleted") is not True
    assert (tmp_path / public_id).is_file()
    assert str(tmp_path) not in response.text
    assert "/data/uploads" not in response.text


def test_race_after_stat_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_path", tmp_path)
    public_id = "c" * 32 + ".png"
    (tmp_path / public_id).write_bytes(b"x")
    original_is_file = Path.is_file
    original_unlink = Path.unlink

    def still_there(self: Path) -> bool:
        if self.name == public_id:
            return True
        return original_is_file(self)

    def already_gone(self: Path, missing_ok: bool = False) -> None:
        if self.name == public_id:
            raise FileNotFoundError(public_id)
        original_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "is_file", still_there)
    monkeypatch.setattr(Path, "unlink", already_gone)
    assert delete_stored_file(public_id) is False
