from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path

from .api.router import api_router

_root = Path(__file__).resolve().parent.parent.parent
FRONTEND_PATH = _root / "CobraQ_v3.html"
DATA_ROOT = _root / "data"
DATA_ROOT.mkdir(exist_ok=True)

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="CobraQ API",
    description="Hệ thống ôn tập thông minh — FastAPI backend",
    version="3.0.0",
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    if FRONTEND_PATH.exists():
        return FileResponse(
            FRONTEND_PATH,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Pragma": "no-cache",
                "Expires": "0",
                # Required so YouTube iframe embeds work — without this, YouTube
                # returns "Error 153: Video player configuration error"
                # because the browser does not send a Referer for cross-origin embeds.
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )
    return {
        "name": "CobraQ API",
        "version": "3.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/map")
def map_page():
    """Serve the v4 map test page so YouTube embeds work over HTTP (not file://)."""
    p = _root / "cobraq_v4_map_test.html"
    if p.exists():
        return FileResponse(
            p,
            headers={
                "Cache-Control": "no-cache, no-store, must-revalidate",
                "Referrer-Policy": "strict-origin-when-cross-origin",
            },
        )
    return {"error": "map page not found"}


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/favicon.ico")
def favicon():
    return FileResponse(_root / "favicon.svg", media_type="image/svg+xml")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
