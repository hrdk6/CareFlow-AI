import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Request, Response
from sqlalchemy import func, select

from app.api.deps import DB, CurrentUser
from app.audit.service import audit
from app.auth.dependencies import SESSION_COOKIE
from app.core.config import get_settings
from app.core.errors import AppError, AuthenticationError, PermissionDeniedError, ValidationFailedError
from app.core.ratelimit import login_limiter
from app.core.security import create_access_token, hash_password, verify_password
from app.models import User
from app.schemas.auth import ChangePasswordIn, LoginIn, TokenOut, UserOut
from app.seed.catalog import DEMO_EMAILS

router = APIRouter(prefix="/auth", tags=["auth"])

# Verifying against a fixed dummy hash keeps response time similar for unknown emails (no user enumeration).
_DUMMY_HASH = hash_password("dummy-password-for-timing")


class TooManyAttempts(AppError):
    status_code = 429
    code = "too_many_attempts"


def user_out(u: User) -> UserOut:
    return UserOut(id=u.id, email=u.email, full_name=u.full_name, role=u.role.name,
                   permissions=sorted(u.permission_codes), doctor_id=u.doctor_id, department_id=u.department_id)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, request: Request, response: Response, db: DB) -> TokenOut:
    email = body.email.lower()
    key = f"{request.client.host if request.client else '-'}:{email}"
    email_ref = hashlib.sha256(email.encode()).hexdigest()[:12]
    if login_limiter.blocked(key):
        audit("auth.login_blocked", outcome="denied", details={"email_ref": email_ref})
        raise TooManyAttempts("Too many failed sign-in attempts. Try again in 15 minutes.")
    user = db.scalar(select(User).where(func.lower(User.email) == email))
    valid = verify_password(user.password_hash if user else _DUMMY_HASH, body.password)
    if not user or not valid or not user.is_active:
        login_limiter.hit(key)
        audit("auth.login_failed", user=user, outcome="denied", details={"email_ref": email_ref})
        raise AuthenticationError("Invalid email or password")
    login_limiter.reset(key)
    user.last_login_at = datetime.now(UTC)
    token, expires = create_access_token(user.id, user.role.name)
    s = get_settings()
    response.set_cookie(SESSION_COOKIE, token, max_age=expires, httponly=True, secure=s.cookie_secure,
                        samesite="strict", path="/")
    audit("auth.login", user=user)
    return TokenOut(access_token=token, expires_in=expires, user=user_out(user))


@router.post("/logout", status_code=204)
def logout(response: Response, user: CurrentUser) -> Response:
    response.delete_cookie(SESSION_COOKIE, path="/")
    audit("auth.logout", user=user)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserOut)
def me(user: CurrentUser) -> UserOut:
    return user_out(user)


@router.post("/change-password", status_code=204)
def change_password(body: ChangePasswordIn, user: CurrentUser, db: DB) -> Response:
    if get_settings().demo_protected and user.email in DEMO_EMAILS:
        audit("auth.password_change_blocked", user=user, outcome="denied")
        raise PermissionDeniedError("Demo accounts keep their shared password so every visitor can sign in.")
    if not verify_password(user.password_hash, body.current_password):
        audit("auth.password_change_failed", user=user, outcome="denied")
        raise AuthenticationError("Current password is incorrect")
    if body.new_password == body.current_password:
        raise ValidationFailedError("The new password must differ from the current one")
    user.password_hash = hash_password(body.new_password)
    audit("auth.password_changed", user=user)
    return Response(status_code=204)
