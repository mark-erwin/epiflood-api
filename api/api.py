import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.config import settings
from core.errors import register_error_handlers
from db.dependencies import open_api_db
from middleware.cache_headers import CacheHeadersMiddleware
from middleware.request_context import RequestContextMiddleware
from routes import analysis, cases, map_layers, meta, rainfall, reference

logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Initialize DB connection and attach to app.state
    try:
        app.state.db = open_api_db()
        yield
    finally:
        if hasattr(app.state, "db") and app.state.db:
            app.state.db.close()

app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)
app.add_middleware(CacheHeadersMiddleware)
app.add_middleware(RequestContextMiddleware)

register_error_handlers(app)

for router_module in (meta, reference, cases, rainfall, map_layers, analysis):
    app.include_router(router_module.router, prefix=settings.api_prefix)
