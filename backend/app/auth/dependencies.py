"""FastAPI dependencies: authentication and permission checks."""
from collections.abc import Callable

from fastapi import Depends, Request
from sqlalchemy.orm import Session

from app.audit.service import audit
from app.core.errors import AuthenticationError, PermissionDeniedError
from app.core.security import decode_access_token
from app.db.session import get_db
from app.models import User

SESSION_COOKIE = "careflow_session"
CSRF_HEADER = "x-careflow-csrf"
_UNSAFE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


def _extract_token(request: Request) -> tuple[str | None, bool]:
    header = request.headers.get("authorization", "")
    if header.lower().startswith("bearer "):
        return header[7:].strip() or None, False
    cookie = request.cookies.get(SESSION_COOKIE)
    return (cookie, True) if cookie else (None, False)


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    token, via_cookie = _extract_token(request)
    if not token:
        raise AuthenticationError("Not authenticated")
    # Cookie sessions must prove same-origin intent on state-changing requests: browsers cannot attach
    # a custom header cross-site without a CORS preflight, which our CORS policy rejects.
    if via_cookie and request.method in _UNSAFE_METHODS and request.headers.get(CSRF_HEADER) != "1":
        raise PermissionDeniedError("Missing CSRF protection header")
    claims = decode_access_token(token)
    user = db.get(User, int(claims["sub"]))
    if user is None or not user.is_active:
        raise AuthenticationError("Account not found or disabled")
    request.state.user = user
    request.state.user_id = user.id  # plain value: safe to read after the session is closed
    return user


def require(*permissions: str) -> Callable[..., User]:
    """Dependency factory: the current user must hold ALL listed permissions."""

    def dependency(request: Request, user: User = Depends(get_current_user)) -> User:
        missing = [p for p in permissions if p not in user.permission_codes]
        if missing:
            audit("permission.denied", user=user, outcome="denied",
                  details={"required": missing, "method": request.method, "path": request.url.path})
            raise PermissionDeniedError("You do not have permission to perform this action")
        return user

    return dependency
