import hmac

from fastapi import Header, HTTPException, status

from app.config import settings


def _secret_matches(provided: str, expected: str) -> bool:
    candidate = expected.strip()
    if not provided or not candidate:
        return False
    return hmac.compare_digest(provided, candidate)


def require_api_key(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    if not settings.api_key.strip():
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="API_KEY não configurada no servidor",
        )
    token: str | None = None
    if x_api_key:
        token = x_api_key.strip()
    elif authorization and authorization.lower().startswith("bearer "):
        token = authorization[7:].strip()
    if token and (
        _secret_matches(token, settings.api_key)
        or _secret_matches(token, settings.api_key_secondary)
    ):
        return
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Chave de API inválida ou ausente",
    )
