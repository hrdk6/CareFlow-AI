"""Password hashing (Argon2id) and JWT access tokens."""
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError

from app.core.config import get_settings
from app.core.errors import AuthenticationError

_hasher = PasswordHasher()  # argon2id with library-recommended parameters


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def create_access_token(user_id: int, role: str) -> tuple[str, int]:
    s = get_settings()
    now = datetime.now(UTC)
    expires = now + timedelta(minutes=s.access_token_minutes)
    claims = {"sub": str(user_id), "role": role, "iat": now, "exp": expires, "jti": uuid.uuid4().hex}
    return jwt.encode(claims, s.jwt_secret or "test-secret-not-for-production-use-only!!", algorithm=s.jwt_algorithm), \
        s.access_token_minutes * 60


def decode_access_token(token: str) -> dict:
    s = get_settings()
    try:
        return jwt.decode(
            token,
            s.jwt_secret or "test-secret-not-for-production-use-only!!",
            algorithms=[s.jwt_algorithm],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthenticationError("Session expired - please sign in again") from exc
    except jwt.PyJWTError as exc:
        raise AuthenticationError("Invalid authentication token") from exc
