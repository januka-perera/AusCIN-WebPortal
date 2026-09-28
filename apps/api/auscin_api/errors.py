"""Controlled error responses. Messages are fixed strings — request input,
filesystem paths and exception details are never echoed back."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from .schemas import ErrorBody, ErrorResponse


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


class NotFoundError(ApiError):
    def __init__(self, code: str, message: str):
        super().__init__(404, code, message)


def site_not_found() -> NotFoundError:
    return NotFoundError("site_not_found", "No public CoastSnap site has this identifier.")


def observation_not_found() -> NotFoundError:
    return NotFoundError("observation_not_found", "No observation with this identifier exists at this site.")


def media_not_found() -> NotFoundError:
    return NotFoundError("media_not_found", "No public media has this identifier.")


def rendition_not_available(kind: str) -> NotFoundError:
    return NotFoundError(f"{kind}_not_available", f"No {kind} is available for this observation.")


_LEVEL_LABELS = {
    "level0": "the untouched source image (Level 0)",
    "level1": "the provenance copy (Level 1)",
}


def download_not_permitted(level: str) -> ApiError:
    return ApiError(
        403, "download_not_permitted", f"Downloading {_LEVEL_LABELS[level]} is not permitted for this observation."
    )


def media_unavailable() -> ApiError:
    return ApiError(503, "media_unavailable", "This media file is temporarily unavailable.")


def _error(status_code: int, code: str, message: str) -> JSONResponse:
    body = ErrorResponse(error=ErrorBody(code=code, message=message))
    return JSONResponse(status_code=status_code, content=body.model_dump(by_alias=True))


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return _error(exc.status_code, exc.code, exc.message)

    @app.exception_handler(StarletteHTTPException)
    async def _http_error(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        # Unmatched routes and methods get the same controlled shape as
        # catalogue lookups, instead of framework defaults.
        if exc.status_code == 404:
            return _error(404, "not_found", "No resource exists at this address.")
        if exc.status_code == 405:
            return _error(405, "method_not_allowed", "This method is not allowed for this resource.")
        return _error(exc.status_code, "http_error", "The request could not be completed.")
