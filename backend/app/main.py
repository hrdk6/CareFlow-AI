"""CareFlow AI - FastAPI application factory."""
import logging
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from sqlalchemy import text
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api import admin, ai, auth, clinical, discharge, documents, fhir, imaging, patients, scheduling, vitals
from app.core.config import get_settings
from app.core.errors import AppError
from app.core.logging import configure_logging, request_id_var
from app.db.session import get_engine, get_session_factory
from app.observability.memory import memory_line, memory_snapshot
from app.observability.middleware import RequestContextMiddleware

logger = logging.getLogger("careflow")


def _error(request: Request, status: int, code: str, message: str, details: dict | None = None) -> JSONResponse:
    if request.url.path.startswith("/fhir"):
        # FHIR clients expect an OperationOutcome, not CareFlow's envelope.
        from app.interop.fhir import FHIR_JSON, operation_outcome

        return JSONResponse(status_code=status, content=operation_outcome(status, code, message), media_type=FHIR_JSON)
    return JSONResponse(status_code=status, content={"error": {
        "code": code, "message": message, "request_id": request_id_var.get(), "details": details or {}}})


def _sync_rbac() -> None:
    """Apply the RBAC policy from code to the database (grants live in tables, the policy is code)."""
    from app.auth.provisioning import sync_admin_password, sync_role_permissions

    with get_session_factory()() as db:
        sync_role_permissions(db)
        sync_admin_password(db)
        db.commit()


def _warmup() -> None:
    """Load models in the background so the first user request is not slow. Failures are non-fatal."""
    try:
        from app.ml.registry import get_registry, sync_registry

        logger.info("memory at startup: %s", memory_line())
        with get_session_factory()() as db:
            sync_registry(db)
            db.commit()
        for name in get_registry().active_versions():
            get_registry().get(name)
        logger.info("memory after prediction models: %s", memory_line())
        s = get_settings()
        if s.environment != "test":
            from app.rag.embeddings import get_embedding_service
            from app.rag.reranking import get_reranker

            get_embedding_service().embed_query("warm up")
            logger.info("memory after embedding model: %s", memory_line())
            get_reranker().score("warm up", ["warm up"])
        logger.info("warmup complete; memory: %s", memory_line())
    except Exception:
        logger.exception("warmup failed - components will load lazily")


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Authorization must be correct before the first request, so this one is synchronous and fatal.
    _sync_rbac()
    threading.Thread(target=_warmup, daemon=True).start()
    yield


def create_app() -> FastAPI:
    s = get_settings()
    s.validate_runtime()
    configure_logging(s.log_level)
    app = FastAPI(title="CareFlow AI API", version="1.0.0", lifespan=lifespan,
                  description="Hospital platform API with authorization-aware ML, RAG and LLM orchestration. "
                              "All data is synthetic.")

    @app.middleware("http")
    async def security_headers(request: Request, call_next):
        response = await call_next(request)
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        if request.url.path not in ("/docs", "/openapi.json", "/redoc"):
            response.headers.setdefault("Cache-Control", "no-store")
        return response

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=s.cors_origins, allow_credentials=True,
                       allow_methods=["GET", "POST", "PATCH", "DELETE"],
                       allow_headers=["Authorization", "Content-Type", "X-CareFlow-CSRF", "X-Request-ID"])

    @app.exception_handler(AppError)
    async def app_error(request: Request, exc: AppError):
        return _error(request, exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        # Report where and why, never echo the submitted values (they may contain PHI).
        issues = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        return _error(request, 422, "validation_failed", "The request is invalid", {"issues": issues})

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        return _error(request, exc.status_code, "http_error", str(exc.detail))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("unhandled error")
        return _error(request, 500, "internal_error", "An unexpected error occurred. Quote the request id when reporting it.")

    for module in (auth, patients, scheduling, clinical, vitals, imaging, discharge, documents, ai,
                   admin, fhir):
        app.include_router(module.router)

    @app.get("/", include_in_schema=False)
    @app.head("/", include_in_schema=False)
    def root() -> dict:
        # Hosts probe the root URL; answer instead of logging a 404 on every check.
        return {"service": "CareFlow AI API", "docs": "/docs", "health": "/health"}

    @app.get("/health", tags=["health"])
    @app.head("/health", include_in_schema=False)
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/health/ready", tags=["health"])
    def ready() -> JSONResponse:
        checks = {}
        try:
            with get_engine().connect() as conn:
                conn.execute(text("select 1"))
            checks["database"] = "ok"
        except Exception:
            checks["database"] = "unavailable"
        from app.ml.registry import get_registry

        checks["models"] = get_registry().active_versions() or "missing"
        ok = checks["database"] == "ok" and checks["models"] != "missing"
        return JSONResponse(status_code=200 if ok else 503,
                            content={"status": "ok" if ok else "degraded", **checks, "memory": memory_snapshot()})

    @app.get("/metrics", include_in_schema=False)
    def metrics(request: Request) -> PlainTextResponse:
        if get_settings().demo_protected:
            # On a public deployment the counters are for administrators, not every visitor.
            from app.auth.dependencies import get_current_user
            from app.auth.rbac import Perm
            from app.core.errors import PermissionDeniedError

            with get_session_factory()() as db:
                if Perm.SYSTEM_OBSERVE.value not in get_current_user(request, db).permission_codes:
                    raise PermissionDeniedError("Metrics are available to administrators only")
        return PlainTextResponse(generate_latest(), media_type=CONTENT_TYPE_LATEST)

    return app


app = create_app()
