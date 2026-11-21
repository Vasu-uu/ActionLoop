"""ActionLoop API: Meeting-to-Action agent."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import __version__, errors
from .config import get_settings
from .db import init_db
from .routers import exports, meetings, tasks
from .services.llm import get_provider
from .services.transcribe import ffmpeg_available

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")


@asynccontextmanager
async def lifespan(_: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="ActionLoop API", version=__version__, lifespan=lifespan,
    description="Turn messy meetings into finished follow-through: transcript -> decisions, tasks, emails, exports.",
)
errors.install(app)
settings = get_settings()
app.add_middleware(
    CORSMiddleware, allow_origins=settings.cors_list, allow_methods=["*"], allow_headers=["*"],
    expose_headers=["Content-Disposition"],
)

JSON_LIMIT = 2 * 1024 * 1024  # non-upload requests


@app.middleware("http")
async def limit_request_size(request: Request, call_next):
    """Reject oversize requests early based on Content-Length (uploads are also limited while streaming)."""
    length = request.headers.get("content-length")
    is_upload = request.url.path in ("/api/meetings/audio", "/api/transcribe")
    cap = (settings.max_upload_mb + 2) * 1024 * 1024 if is_upload else JSON_LIMIT
    if length and length.isdigit() and int(length) > cap:
        return JSONResponse({"error": {"code": "too_large", "message": "Request body is too large."}}, status_code=413)
    resp = await call_next(request)
    resp.headers.setdefault("X-Content-Type-Options", "nosniff")
    resp.headers.setdefault("Referrer-Policy", "no-referrer")
    return resp


@app.get("/api/health", tags=["health"])
def health():
    p = get_provider()
    return {
        "status": "ok", "version": __version__,
        "llm": p.describe(), "requested_provider": settings.effective_provider,
        "whisper": {"model": settings.whisper_model, "ffmpeg": ffmpeg_available()},
        "privacy": "Nothing leaves this machine." if p.local else f"Transcript text is sent to the {p.name} API.",
        "max_upload_mb": settings.max_upload_mb,
    }


app.include_router(meetings.router)
app.include_router(tasks.router)
app.include_router(exports.router)

# Serve the built frontend (Docker / production). In dev, Vite serves it on :5173.
_dist = Path(settings.frontend_dist)
if _dist.exists():
    app.mount("/assets", StaticFiles(directory=_dist / "assets"), name="assets")

    @app.get("/{path:path}", include_in_schema=False)
    def spa(path: str):
        if path.startswith("api/"):
            return JSONResponse({"error": {"code": "not_found", "message": "Not found."}}, status_code=404)
        f = (_dist / path).resolve()
        if path and f.is_file() and _dist.resolve() in f.parents:
            return FileResponse(f)
        return FileResponse(_dist / "index.html")
