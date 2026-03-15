import uuid
from typing import Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars


class RequestIdMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, header_name: str = "X-Request-Id"):
        super().__init__(app)
        self.header_name = header_name

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        clear_contextvars()

        request_id = request.headers.get(self.header_name) or str(uuid.uuid4())
        bind_contextvars(request_id=request_id)

        response = await call_next(request)
        response.headers[self.header_name] = request_id

        structlog.get_logger(__name__).info(
            "request.completed",
            method=request.method,
            path=str(request.url.path),
            status_code=response.status_code,
        )
        return response

