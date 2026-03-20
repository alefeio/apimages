import io
import uuid
import zipfile
from pathlib import Path

from fastapi import HTTPException, UploadFile, status
from PIL import Image, ImageOps, UnidentifiedImageError

from app.config import settings

_RESAMPLE = Image.Resampling.LANCZOS if hasattr(Image, "Resampling") else Image.LANCZOS

_OLE_MAGIC = b"\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1"
_RASTER_IMAGE_TYPES = frozenset(
    {"image/jpeg", "image/png", "image/gif", "image/webp"},
)
_OOXML_TYPES = frozenset(
    {
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    },
)
_OOXML_LEGACY_ZIP = frozenset(
    {
        "application/vnd.oasis.opendocument.text",
        "application/vnd.oasis.opendocument.spreadsheet",
        "application/vnd.oasis.opendocument.presentation",
    },
)
_OLE_TYPES = frozenset(
    {
        "application/msword",
        "application/vnd.ms-excel",
        "application/vnd.ms-powerpoint",
    },
)


def _normalize_mime(raw: str | None) -> str | None:
    if not raw:
        return None
    return raw.split(";")[0].strip().lower()


def _ensure_storage() -> Path:
    path = settings.storage_path.resolve()
    path.mkdir(parents=True, exist_ok=True)
    return path


def _validate_pdf(body: bytes) -> None:
    if not body.startswith(b"%PDF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="PDF inválido ou corrompido",
        )


def _validate_zip_container(body: bytes) -> None:
    if not zipfile.is_zipfile(io.BytesIO(body)):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo ZIP/Office inválido ou corrompido",
        )


def _validate_ole(body: bytes) -> None:
    if len(body) < 8 or body[:8] != _OLE_MAGIC:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Documento Office legado inválido ou corrompido",
        )


def _validate_rtf(body: bytes) -> None:
    head = body[:256].lstrip().upper()
    if not head.startswith(b"{\\RTF"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="RTF inválido",
        )


def _validate_textish(body: bytes) -> None:
    sample = body[:4096]
    if b"\x00" in sample:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo não parece texto puro",
        )


def _validate_svg(body: bytes) -> None:
    head = body[:512].lstrip().lower()
    if not (head.startswith(b"<?xml") or head.startswith(b"<svg")):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="SVG inválido",
        )


def _has_orientation_exif(im: Image.Image) -> bool:
    exif = im.getexif()
    if exif is None:
        return False
    o = exif.get(274)
    try:
        return o is not None and int(o) != 1
    except (TypeError, ValueError):
        return False


def _to_rgb_for_jpeg(im: Image.Image) -> Image.Image:
    if im.mode in ("RGB", "L"):
        return im.convert("RGB") if im.mode == "L" else im
    if im.mode == "RGBA":
        base = Image.new("RGB", im.size, (255, 255, 255))
        base.paste(im, mask=im.split()[3])
        return base
    if im.mode == "LA":
        base = Image.new("RGB", im.size, (255, 255, 255))
        base.paste(im.convert("RGBA"), mask=im.split()[1])
        return base
    if im.mode == "P":
        if "transparency" in im.info:
            return _to_rgb_for_jpeg(im.convert("RGBA"))
        return im.convert("RGB")
    return im.convert("RGB")


def _encode_raster(work: Image.Image, content_type: str) -> bytes:
    buf = io.BytesIO()
    if content_type == "image/jpeg":
        rgb = _to_rgb_for_jpeg(work)
        rgb.save(
            buf,
            format="JPEG",
            quality=settings.image_jpeg_quality,
            optimize=True,
            progressive=True,
            subsampling=0,
        )
    elif content_type == "image/png":
        png = work
        if png.mode not in ("1", "L", "P", "RGB", "RGBA"):
            png = png.convert("RGBA")
        png.save(buf, format="PNG", optimize=True)
    elif content_type == "image/webp":
        work.save(
            buf,
            format="WEBP",
            quality=settings.image_webp_quality,
            method=6,
        )
    elif content_type == "image/gif":
        g = work.convert("RGB")
        try:
            g = g.quantize(
                colors=256,
                method=Image.Quantize.MEDIANCUT,
                dither=Image.Dither.FLOYDSTEINBERG,
            )
        except AttributeError:
            g = g.quantize(colors=256)
        g.save(buf, format="GIF", optimize=True)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Encoder raster não implementado",
        )
    return buf.getvalue()


def _save_raster_image(body: bytes, content_type: str, dest: Path) -> tuple[int, int, int]:
    try:
        Image.open(io.BytesIO(body)).verify()
    except UnidentifiedImageError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Imagem corrompida ou inválida",
        )
    img = Image.open(io.BytesIO(body))
    fmt = (img.format or "JPEG").upper()
    if content_type == "image/jpeg" and fmt in ("JPEG", "MPO"):
        pass
    elif content_type == "image/png" and fmt == "PNG":
        pass
    elif content_type == "image/gif" and fmt == "GIF":
        pass
    elif content_type == "image/webp" and fmt == "WEBP":
        pass
    else:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Conteúdo não corresponde ao tipo declarado",
        )

    if getattr(img, "n_frames", 1) > 1:
        dest.write_bytes(body)
        w, h = img.size
        return w, h, len(body)

    work = ImageOps.exif_transpose(img)
    w, h = work.size
    max_edge = settings.image_max_edge_px
    need_resize = max_edge > 0 and max(w, h) > max_edge
    if need_resize:
        scale = max_edge / float(max(w, h))
        nw = max(1, int(round(w * scale)))
        nh = max(1, int(round(h * scale)))
        work = work.resize((nw, nh), _RESAMPLE)
        w, h = work.size

    must_reencode = need_resize or _has_orientation_exif(img)
    if not must_reencode:
        dest.write_bytes(body)
        return img.size[0], img.size[1], len(body)

    out = _encode_raster(work, content_type)
    if len(out) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Imagem após processamento excede MAX_UPLOAD_BYTES",
        )
    dest.write_bytes(out)
    return w, h, len(out)


async def save_upload(file: UploadFile) -> tuple[str, str, int | None, int | None, int]:
    mime = _normalize_mime(file.content_type)
    if not mime or mime not in settings.allowed_mime:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail="Tipo não suportado. Veja a documentação em /docs ou o mapeamento em allowed_mime.",
        )

    body = await file.read()
    if len(body) > settings.max_upload_bytes:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"Arquivo acima do limite de {settings.max_upload_bytes} bytes",
        )
    if len(body) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Arquivo vazio",
        )

    ext = settings.allowed_mime[mime]
    public_id = f"{uuid.uuid4().hex}{ext}"
    storage = _ensure_storage()
    dest = storage / public_id

    width: int | None = None
    height: int | None = None
    out_size = len(body)

    if mime in _RASTER_IMAGE_TYPES:
        width, height, out_size = _save_raster_image(body, mime, dest)
    elif mime == "image/svg+xml":
        _validate_svg(body)
        dest.write_bytes(body)
    elif mime == "application/pdf":
        _validate_pdf(body)
        dest.write_bytes(body)
    elif mime in _OOXML_TYPES or mime in _OOXML_LEGACY_ZIP:
        _validate_zip_container(body)
        dest.write_bytes(body)
    elif mime in _OLE_TYPES:
        _validate_ole(body)
        dest.write_bytes(body)
    elif mime == "application/rtf":
        _validate_rtf(body)
        dest.write_bytes(body)
    elif mime in ("text/plain", "text/csv"):
        _validate_textish(body)
        dest.write_bytes(body)
    else:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Tipo mapeado mas não tratado",
        )

    label = ext.lstrip(".").upper()
    return public_id, label, width, height, out_size


def file_path(public_id: str) -> Path | None:
    if ".." in public_id or "/" in public_id or "\\" in public_id:
        return None
    storage = _ensure_storage()
    p = storage / public_id
    if not p.is_file():
        return None
    try:
        p.resolve().relative_to(storage.resolve())
    except ValueError:
        return None
    return p
