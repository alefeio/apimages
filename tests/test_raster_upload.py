import base64
import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from app.config import settings
from app.main import app
from app.storage_service import _save_raster_image

API_KEY = "test-key"
VALID_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAIAAACQd1PeAAAADElEQVR4nGP4z8AAAAMBAQDJ/pLvAAAAAElFTkSuQmCC"
)
BROKEN_IDAT_PNG = bytes([
    0x89, 0x50, 0x4E, 0x47, 0x0D, 0x0A, 0x1A, 0x0A,
    0x00, 0x00, 0x00, 0x0D, 0x49, 0x48, 0x44, 0x52,
    0x00, 0x00, 0x00, 0x01, 0x00, 0x00, 0x00, 0x01,
    0x08, 0x02, 0x00, 0x00, 0x00, 0x90, 0x77, 0x53, 0xDE,
    0x00, 0x00, 0x00, 0x0C, 0x49, 0x44, 0x41, 0x54,
    0x08, 0xD7, 0x63, 0xF8, 0xCF, 0xC0, 0x00, 0x00, 0x00, 0x03, 0x00, 0x01,
    0x00, 0x05, 0xFE, 0x02, 0xFE,
    0x00, 0x00, 0x00, 0x00, 0x49, 0x45, 0x4E, 0x44, 0xAE, 0x42, 0x60, 0x82,
])


def _jpeg() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (1, 1), (10, 20, 30)).save(buffer, format="JPEG")
    return buffer.getvalue()


@pytest.fixture
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> TestClient:
    monkeypatch.setattr(settings, "api_key", API_KEY)
    monkeypatch.setattr(settings, "api_key_secondary", "")
    monkeypatch.setattr(settings, "storage_path", tmp_path)
    monkeypatch.setattr(settings, "base_url", "https://apimg.com.br")
    return TestClient(app, raise_server_exceptions=False)


def _upload(client: TestClient, body: bytes, mime: str, name: str, key: str = API_KEY):
    return client.post(
        "/v1/upload",
        headers={"X-API-Key": key},
        files={"file": (name, body, mime)},
    )


def test_valid_png_upload(client: TestClient) -> None:
    response = _upload(client, VALID_PNG, "image/png", "pixel.png")
    assert response.status_code == 200
    body = response.json()
    assert body["url"].startswith("https://apimg.com.br/i/")
    assert body["public_id"]
    assert body["format"] == "PNG"
    assert body["bytes"] > 0
    assert body["width"] == 1
    assert body["height"] == 1


def test_valid_jpeg_upload(client: TestClient) -> None:
    response = _upload(client, _jpeg(), "image/jpeg", "pixel.jpg")
    assert response.status_code == 200
    body = response.json()
    assert body["format"] == "JPG"
    assert body["bytes"] > 0
    assert body["public_id"]


def test_broken_idat_png_is_400(client: TestClient) -> None:
    response = _upload(client, BROKEN_IDAT_PNG, "image/png", "broken.png")
    assert response.status_code == 400
    assert response.json()["detail"] == "Imagem corrompida ou inválida"


def test_random_bytes_declared_as_png_are_400(client: TestClient) -> None:
    response = _upload(client, b"\x00\x01not-a-png", "image/png", "random.png")
    assert response.status_code == 400
    assert response.json()["detail"] == "Imagem corrompida ou inválida"


def test_empty_file_is_400(client: TestClient) -> None:
    response = _upload(client, b"", "image/png", "empty.png")
    assert response.status_code == 400
    assert response.json()["detail"] == "Arquivo vazio"


def test_mismatched_mime_is_400(client: TestClient) -> None:
    response = _upload(client, VALID_PNG, "image/jpeg", "pixel.jpg")
    assert response.status_code == 400
    assert response.json()["detail"] == "Conteúdo não corresponde ao tipo declarado"


def test_filesystem_failure_is_not_masked_as_invalid_image(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "storage_path", tmp_path)

    def fail_write(self: Path, data: bytes) -> None:
        raise PermissionError("read-only filesystem")

    monkeypatch.setattr(Path, "write_bytes", fail_write)
    with pytest.raises(PermissionError):
        _save_raster_image(VALID_PNG, "image/png", tmp_path / "pixel.png")


def test_invalid_api_key_stays_401(client: TestClient) -> None:
    response = _upload(client, VALID_PNG, "image/png", "pixel.png", key="wrong-key")
    assert response.status_code == 401
    assert response.json()["detail"] == "Chave de API inválida ou ausente"
