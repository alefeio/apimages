from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    base_url: str = "http://localhost:8000"
    api_key: str = ""
    storage_path: Path = Path("./data/uploads")
    max_upload_bytes: int = 10 * 1024 * 1024

    # Imagens raster: maior lado em pixels; 0 = não redimensionar. Padrão adequado para web (hero/retina).
    image_max_edge_px: int = Field(default=2560, ge=0)
    # JPEG/WebP: valores altos preservam detalhe após redimensionamento (subsampling 4:4:4 no JPEG).
    image_jpeg_quality: int = Field(default=90, ge=1, le=100)
    image_webp_quality: int = Field(default=92, ge=1, le=100)

    # MIME (normalizado, sem parâmetros) → extensão no disco
    allowed_mime: dict[str, str] = {
        # Imagens
        "image/jpeg": ".jpg",
        "image/png": ".png",
        "image/gif": ".gif",
        "image/webp": ".webp",
        "image/svg+xml": ".svg",
        # Documentos
        "application/pdf": ".pdf",
        "application/msword": ".doc",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document": ".docx",
        "application/vnd.ms-excel": ".xls",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": ".xlsx",
        "application/vnd.ms-powerpoint": ".ppt",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation": ".pptx",
        "application/rtf": ".rtf",
        "text/csv": ".csv",
        "text/plain": ".txt",
        # OpenDocument (mesmo padrão ZIP que OOXML)
        "application/vnd.oasis.opendocument.text": ".odt",
        "application/vnd.oasis.opendocument.spreadsheet": ".ods",
        "application/vnd.oasis.opendocument.presentation": ".odp",
    }


settings = Settings()
