from fastapi import APIRouter, HTTPException, Depends, Header
from pydantic import BaseModel
import json
from pathlib import Path
from typing import Optional

from ..core.security import get_current_user_optional
from ..core.audit import audit_log, EventType

router = APIRouter(prefix="/config", tags=["config"])

CONFIG_FILE = Path("data/config.json")


def load_config():
    cfg = {"ai_parse_enabled": True}
    try:
        if CONFIG_FILE.exists():
            cfg.update(json.loads(CONFIG_FILE.read_text(encoding="utf-8")))
    except:
        pass
    return cfg


def save_config(data: dict):
    CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
    CONFIG_FILE.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


@router.get("")
def get_config(current_user: Optional[dict] = Depends(get_current_user_optional)):
    cfg = load_config()
    from ..core.config import get_settings
    settings = get_settings()
    has_key = bool(settings.anthropic_api_key and settings.anthropic_api_key != "YOUR_KEY_HERE")
    return {
        "ai_parse_enabled": cfg.get("ai_parse_enabled", True),
        "has_api_key": has_key,
        "key_preview": "sk-ant-...***" if has_key else "",
    }


class ConfigBody(BaseModel):
    ai_parse_enabled: bool = True


@router.post("")
def update_config(body: ConfigBody, current_user: Optional[dict] = Depends(get_current_user_optional)):
    save_config({"ai_parse_enabled": body.ai_parse_enabled})
    from ..core.config import get_settings
    settings = get_settings()
    audit_log.log(EventType.CONFIG_UPDATE, user_id=current_user.get("sub") if current_user else "unknown",
                  details={"ai_parse_enabled": body.ai_parse_enabled})
    return {"message": "Đã lưu cài đặt"}


@router.get("/ai")
def get_ai_status(current_user: Optional[dict] = Depends(get_current_user_optional)):
    cfg = load_config()
    from ..core.config import get_settings
    settings = get_settings()
    has_key = bool(settings.anthropic_api_key and settings.anthropic_api_key != "YOUR_KEY_HERE")
    return {
        "ai_available": has_key,
        "ai_enabled": cfg.get("ai_parse_enabled", True),
        "has_api_key": has_key,
    }
