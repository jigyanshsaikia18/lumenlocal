"""Canonical API error envelope (05_API_Specification.md §1).

Every error response is shaped ``{ "error": { "code", "message", "details" } }``.
``APIError`` carries that contract; ``install_error_handlers`` renders it. Later
tickets reuse this for entitlement (403 feature_disabled), quota (429) and policy
(422) failures, so the envelope is identical platform-wide.
"""
from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class APIError(Exception):
    """An error that serialises to the §1 envelope with a stable machine code."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details or {}

    def to_response(self) -> JSONResponse:
        return JSONResponse(
            status_code=self.status_code,
            content={
                "error": {
                    "code": self.code,
                    "message": self.message,
                    "details": self.details,
                }
            },
        )


def install_error_handlers(app: FastAPI) -> None:
    """Wire the §1 envelope onto an app (the main app and any test app)."""

    @app.exception_handler(APIError)
    async def _api_error_handler(_: Request, exc: APIError) -> JSONResponse:
        return exc.to_response()

    @app.exception_handler(StarletteHTTPException)
    async def _http_error_handler(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Normalise stray HTTPExceptions (e.g. 404 routing) into the same envelope.
        detail = exc.detail if isinstance(exc.detail, str) else "http_error"
        return JSONResponse(
            status_code=exc.status_code,
            content={"error": {"code": "http_error", "message": detail, "details": {}}},
        )
