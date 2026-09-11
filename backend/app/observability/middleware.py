"""Request context middleware: request ids, client ip, latency metrics, one structured log line."""
import logging
import re
import time
import uuid

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from app.core.logging import client_ip_var, request_id_var
from app.observability.metrics import HTTP_LATENCY

logger = logging.getLogger("careflow.http")
_SAFE_ID = re.compile(r"^[A-Za-z0-9\-]{8,64}$")


class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        incoming = request.headers.get("x-request-id", "")
        rid = incoming if _SAFE_ID.match(incoming) else uuid.uuid4().hex[:16]
        request_id_var.set(rid)
        client_ip_var.set(request.client.host if request.client else None)
        start = time.perf_counter()
        status = 500
        try:
            response = await call_next(request)
            status = response.status_code
            response.headers["X-Request-ID"] = rid
            return response
        finally:
            elapsed = time.perf_counter() - start
            route = request.scope.get("route")
            template = getattr(route, "path", "unmatched")  # templated path: no ids in metric labels
            HTTP_LATENCY.labels(request.method, template, str(status)).observe(elapsed)
            logger.info("request", extra={"fields": {
                "method": request.method, "route": template, "status": status,
                "ms": round(elapsed * 1000, 1), "user_id": getattr(request.state, "user_id", None),
            }})
