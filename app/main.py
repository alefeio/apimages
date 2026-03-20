import mimetypes

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse

from app.auth import require_api_key
from app.config import settings
from app.schemas import HealthResponse, UploadResponse
from app.storage_service import file_path, save_upload

_EXTRA_MIMES: list[tuple[str, str]] = [
    (".pdf", "application/pdf"),
    (".doc", "application/msword"),
    (
        ".docx",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ),
    (".xls", "application/vnd.ms-excel"),
    (
        ".xlsx",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ),
    (".ppt", "application/vnd.ms-powerpoint"),
    (
        ".pptx",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ),
    (".rtf", "application/rtf"),
    (".odt", "application/vnd.oasis.opendocument.text"),
    (".ods", "application/vnd.oasis.opendocument.spreadsheet"),
    (".odp", "application/vnd.oasis.opendocument.presentation"),
]

for _ext, _mime in _EXTRA_MIMES:
    mimetypes.add_type(_mime, _ext, strict=False)

app = FastAPI(
    title="Apimages",
    description="API de hospedagem de arquivos (imagens, PDF, Office, texto; upload autenticado, leitura pública).",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        storage=str(settings.storage_path.resolve()),
    )


@app.post("/v1/upload", response_model=UploadResponse)
async def upload_file(
    _: None = Depends(require_api_key),
    file: UploadFile = File(..., description="Arquivo (imagem, PDF, Office, CSV, TXT, etc.)"),
) -> UploadResponse:
    public_id, fmt, width, height, size = await save_upload(file)
    base = settings.base_url.rstrip("/")
    url = f"{base}/i/{public_id}"
    return UploadResponse(
        url=url,
        public_id=public_id,
        width=width,
        height=height,
        format=fmt,
        bytes=size,
    )


@app.get("/i/{public_id}")
def get_file(public_id: str):
    path = file_path(public_id)
    if path is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Não encontrado")
    media_type, _ = mimetypes.guess_type(str(path))
    if not media_type:
        media_type = "application/octet-stream"
    return FileResponse(path, media_type=media_type, filename=path.name)


@app.get("/")
def root():
    return {
        "service": "Apimages",
        "docs": "/docs",
        "upload": "POST /v1/upload (header X-API-Key)",
        "serve": "GET /i/{public_id}",
    }
