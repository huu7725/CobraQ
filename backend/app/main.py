import os
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

# Resolve data dir: respect DATA_DIR env (Render Persistent Disk mounts at
# e.g. /var/data). Falls back to <repo>/backend/data for local dev.
# On Render free tier the disk is ephemeral — without a Persistent Disk
# attached, $DATA_DIR must be set to a path Render guarantees to retain.
_env_data_dir = os.environ.get("DATA_DIR", "").strip()
if _env_data_dir:
    _target = Path(_env_data_dir)
    _target.mkdir(parents=True, exist_ok=True)
else:
    _target = _root / "data"

# Make code that uses bare Path("data/...") work regardless of whether the
# data dir is local or on a persistent disk. We symlink <repo>/backend/data
# to the resolved target when they differ — that way every existing file
# (group_scores.json, users_store.json, chroma_db/, ...) keeps working
# without refactoring each call site.
DATA_ROOT = _root / "data"
_local_data = _root / "data"
if _env_data_dir and _target.resolve() != _local_data.resolve():
    # Ensure expected subdirs exist on the mount, then symlink the
    # in-repo `data/` to the mount path. This way call sites that use
    # bare `Path("data/...")` continue to work without code changes.
    for sub in ("users", "uploads", "chroma_db"):
        (_target / sub).mkdir(parents=True, exist_ok=True)
    if _local_data.exists() and not _local_data.is_symlink():
        # Local data dir exists and is a real dir — don't touch it (this
        # branch should only fire in dev / without DATA_DIR).
        pass
    elif _local_data.is_symlink():
        # Already a symlink — refresh its target.
        _local_data.unlink()
        _local_data.symlink_to(_target, target_is_directory=True)
    else:
        _local_data.symlink_to(_target, target_is_directory=True)
else:
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
