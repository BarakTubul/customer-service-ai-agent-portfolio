from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.core.errors import AppError
from app.core.settings import get_settings

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def app_error_handler(_: Request, exc: AppError) -> JSONResponse:
        payload = {
            "error": {
                "code": exc.error_code,
                "message": exc.message,
                "details": exc.details,
            }
        }
        return JSONResponse(status_code=exc.status_code, content=payload)

    @app.exception_handler(RequestValidationError)
    async def request_validation_error_handler(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "error": {
                    "code": "request_validation_error",
                    "message": "Request validation failed",
                    "details": {"errors": exc.errors()},
                }
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(_: Request, exc: Exception) -> JSONResponse:
        settings = get_settings()
        logger.exception("Unhandled exception", exc_info=exc)
        payload = {
            "error": {
                "code": "internal_error",
                "message": "Unexpected server error",
            }
        }
        if settings.expose_error_details:
            payload["error"]["details"] = {"exception": str(exc)}
        return JSONResponse(status_code=500, content=payload)
