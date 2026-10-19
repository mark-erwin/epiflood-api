import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware


# measure request processing time and add as a custom response header
class ProcessTimeMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.perf_counter()

        response = await call_next(
            request
        )  # Pass the request down to the router/endpoint

        process_time = time.perf_counter() - start_time  # Logic after endpointe reached
        response.headers["X-Process-Time"] = f"{process_time:.4f}s"

        return response
