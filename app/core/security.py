from datetime import datetime, timedelta, timezone
from jose import jwt
import bcrypt
from starlette.responses import Response

from app.core.settings import settings


class _PasswordBackend:
    """Обертка над bcrypt для удобства патчинга в тестах."""

    @staticmethod
    def hash(password_bytes: bytes) -> bytes:
        return bcrypt.hashpw(password_bytes, bcrypt.gensalt())

    @staticmethod
    def verify(password_bytes: bytes, hashed: bytes) -> bool:
        return bcrypt.checkpw(password_bytes, hashed)


_pwd = _PasswordBackend()


def hash_password(password: str) -> str:
    password_bytes = password.encode("utf-8")
    if len(password_bytes) > 72:
        password_bytes = password_bytes[:72]
    hashed = _pwd.hash(password_bytes)
    return hashed.decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        password_bytes = password.encode("utf-8")
        if len(password_bytes) > 72:
            password_bytes = password_bytes[:72]
        return _pwd.verify(password_bytes, password_hash.encode("utf-8"))
    except Exception:
        return False


def create_access_token(user_id: int, role: str, expires_minutes: int = 120) -> str:
    exp = datetime.now(timezone.utc) + timedelta(minutes=expires_minutes)
    payload = {"sub": str(user_id), "role": role, "exp": exp}
    return jwt.encode(payload, settings.JWT_SECRET, algorithm=settings.JWT_ALGORITHM)


def decode_access_token(token: str) -> dict:
    return jwt.decode(token, settings.JWT_SECRET, algorithms=[settings.JWT_ALGORITHM])


def set_auth_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(
        key=settings.AUTH_COOKIE_NAME,
        value=token,
        httponly=True,
        samesite="lax",
        path="/",
    )


def clear_auth_cookie(resp: Response) -> None:
    resp.delete_cookie(settings.AUTH_COOKIE_NAME, path="/")
