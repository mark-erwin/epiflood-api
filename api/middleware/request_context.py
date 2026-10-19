# middleware/request_context.py
import logging
import re
import time
import uuid
from starlette.middleware.base import BaseHTTPMiddleware
log = logging.getLogger("epiflood")
# Only accept short, safe IDs from clients
_SAFE_ID = re.compile(r"^[A-Za-z0-9._-]{1,64}$")

class RequestContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        incoming = request.headers.get("X-Request-ID")
        rid = incoming if incoming and _SAFE_ID.match(incoming) else str(uuid.uuid4())
        request.state.request_id = rid

        start = time.perf_counter()
        try:
            response = await call_next(request)
        except Exception:
            ms = (time.perf_counter() - start) * 1000
            log.exception(
                "%s %s -> 500 (%.1fms) [%s]",
                request.method,
                request.url.path,
                ms,
                rid,
            )
            raise

        ms = (time.perf_counter() - start) * 1000
        response.headers["X-Request-ID"] = rid
        response.headers["X-Process-Time"] = f"{ms:.1f}ms"
        log.info(
            "%s %s -> %s (%.1fms) [%s]",
            request.method,
            request.url.path,
            response.status_code,
            ms,
            rid,
        )
        return response