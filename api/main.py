import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from core.config import settings
from core.errors import register_error_handlers
from middleware.request_context import RequestContextMiddleware
from routes import cases, export, map_layers, meta, predict, rainfall, reference

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):

    init_db()

    yield


app = FastAPI(title=settings.app_name, version=settings.version, lifespan=lifespan)

# Last added = outermost
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.allowed_hosts)
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
    expose_headers=["Content-Disposition", "X-Request-ID"],
)
app.add_middleware(RequestContextMiddleware)

register_error_handlers(app)

for r in (meta, reference, map_layers, cases, rainfall, predict, export):
    app.include_router(r.router, prefix=settings.api_prefix)
