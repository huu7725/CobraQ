from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from pathlib import Path
from contextlib import asynccontextmanager
from .core.config import get_settings, data_path

from .api.router import api_router

_root = Path(__file__).resolve().parent.parent.parent
FRONTEND_PATH = _root / "CobraQ_v3.html"
DATA_ROOT = data_path()
DATA_ROOT.mkdir(parents=True, exist_ok=True)

limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(application):
    from .services.document_store import document_jobs
    import asyncio
    jobs=document_jobs()
    if get_settings().profile != "sandbox":
        from .db.database import Base, engine
        from .models import historical_event, map_quiz_question, map_quiz_session, map_quiz_answer, user_map_progress, user, quiz_history
        Base.metadata.create_all(bind=engine)
        from .services.seed_map_data import seed_events
        seed_events()
        from .services.seed_admin import seed_admin
        seed_admin()
    yield
    await asyncio.to_thread(jobs.close)
    document_jobs.cache_clear()
    from .db.database import engine
    engine.dispose()

app = FastAPI(
    title="CobraQ API",
    description="Hệ thống ôn tập thông minh — FastAPI backend",
    version="3.0.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[] if get_settings().profile == "sandbox" else ["*"],
    allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:[0-9]+)?$" if get_settings().profile == "sandbox" else None,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")


@app.get("/")
def root():
    if FRONTEND_PATH.exists():
        if get_settings().profile == "sandbox":
            html = FRONTEND_PATH.read_text(encoding="utf-8").replace("<body>", '<body><div id="sandbox-banner" role="status" style="position:fixed;top:6px;right:12px;z-index:250;background:#fef3c7;color:#78350f;padding:5px 12px;border:1px solid #f59e0b;border-radius:8px;font:600 12px sans-serif">SANDBOX · Dữ liệu thử nghiệm</div><style>.main{padding-top:52px}</style>', 1)
            return HTMLResponse(html, headers={"Cache-Control": "no-store", "X-CobraQ-Environment": "sandbox"})
        return FileResponse(FRONTEND_PATH, headers={"Cache-Control": "no-cache, no-store, must-revalidate", "Pragma": "no-cache", "Expires": "0"})
    return {
        "name": "CobraQ API",
        "version": "3.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/map")
def map_page():
    return FileResponse(_root / "cobraq_v4_map_test.html", headers={"Referrer-Policy":"strict-origin-when-cross-origin"})


@app.get("/assets/history12/page/{page_number}")
def history12_page(page_number: int):
    from fastapi import HTTPException
    if not 1 <= page_number <= 200:
        raise HTTPException(404,"Trang khong hop le")
    path = _root / "outputs/cobraq_ocr_review/pages" / f"page_{page_number:03d}.jpg"
    if not path.is_file():
        raise HTTPException(404,"Chua co anh trang sach")
    return FileResponse(path,media_type="image/jpeg")


@app.get("/health")
def health():
    return {"status": "ok", "profile": get_settings().profile,
            "external_ai_enabled": get_settings().external_ai_enabled}


@app.get("/research-ui.js", include_in_schema=False)
def research_ui():
    return FileResponse(_root / "frontend/research.js", media_type="text/javascript",
                        headers={"Cache-Control": "no-cache"})


@app.get("/favicon.ico")
def favicon():
    return FileResponse(_root / "favicon.svg", media_type="image/svg+xml")


app.mount("/assets", StaticFiles(directory=_root / "frontend"), name="frontend-assets")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
