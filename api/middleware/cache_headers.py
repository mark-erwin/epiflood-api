"""Cache-Control for successful GETs. Longest prefix wins; None = no-store.

Static layers (hazard, boundaries) change only when the pipelines rebuild the database,
so browsers may keep them for a day. Weekly case layers change when a new report is loaded.
"""

from starlette.middleware.base import BaseHTTPMiddleware

from core.config import settings

CACHE_RULES: dict[str, int | None] = {
    "/health": None,
    "/export": None,
    "/map/hazard": 86400,
    "/map/boundaries": 86400,
    "/map/layers": 3600,
    "/map": 900,
    "/rainfall": 3600,
    "/municipalities": 3600,
    "/schema": 3600,
    "/sources": 3600,
    "/morbidity-weeks": 900,
    "/cases": 900,
    "/analysis": 900,
}

def cache_control_for(path: str) -> str | None:
    if not path.startswith(settings.api_prefix):
        return None
    rel = path[len(settings.api_prefix):]
    for prefix in sorted(CACHE_RULES, key=len, reverse=True):
        if rel == prefix or rel.startswith(prefix + "/") or rel.startswith(prefix + "?"):
            age = CACHE_RULES[prefix]
            if age is None:
                return "no-store"
            return f"public, max-age={age}, stale-while-revalidate={age // 10}"
    return None


class CacheHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        response = await call_next(request)
        if request.method == "GET" and response.status_code == 200 and "cache-control" not in response.headers:
            value = cache_control_for(request.url.path)
            if value:
                response.headers["Cache-Control"] = value
        return response
