from pydantic import BaseModel, Field


class UploadResponse(BaseModel):
    url: str = Field(..., description="URL pública do arquivo")
    public_id: str = Field(..., description="Identificador único do arquivo")
    width: int | None = Field(
        None, description="Largura em pixels (apenas para imagens raster)"
    )
    height: int | None = Field(
        None, description="Altura em pixels (apenas para imagens raster)"
    )
    format: str = Field(..., description="Extensão / formato do arquivo")
    bytes: int = Field(..., description="Tamanho do arquivo em bytes")


class HealthResponse(BaseModel):
    status: str = "ok"
    storage: str
