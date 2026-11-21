"""Consistent error responses: {"error": {"code": str, "message": str}}."""
from __future__ import annotations

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class ApiError(HTTPException):
    def __init__(self, status: int, code: str, message: str):
        super().__init__(status_code=status, detail={"code": code, "message": message})


def _body(code: str, message: str) -> dict:
    return {"error": {"code": code, "message": message}}


def install(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        d = exc.detail
        if isinstance(d, dict) and "code" in d:
            return JSONResponse(_body(d["code"], d["message"]), status_code=exc.status_code)
        names = {400: "bad_request", 404: "not_found", 405: "method_not_allowed", 413: "too_large", 415: "unsupported_media"}
        return JSONResponse(_body(names.get(exc.status_code, "error"), str(d)), status_code=exc.status_code)

    @app.exception_handler(RequestValidationError)
    async def _validation(_: Request, exc: RequestValidationError):
        first = exc.errors()[0] if exc.errors() else {}
        loc = ".".join(str(x) for x in first.get("loc", []) if x != "body")
        return JSONResponse(_body("validation_error", f"{loc}: {first.get('msg', 'invalid input')}" if loc else "Invalid input"), status_code=422)

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        return JSONResponse(_body("internal_error", "Something went wrong on the server."), status_code=500)
