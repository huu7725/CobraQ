from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
import os
from pathlib import Path
from typing import Literal
from pydantic import AliasChoices, Field, model_validator

BACKEND_ROOT = Path(__file__).resolve().parents[2]
PROJECT_ROOT = BACKEND_ROOT.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=BACKEND_ROOT / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
        populate_by_name=True,
        hide_input_in_errors=True,
    )

    app_name: str = "CobraQ"
    debug: bool = False
    profile: Literal["local", "sandbox"] = Field(default="local", validation_alias="COBRAQ_PROFILE")
    sandbox_root: Path | None = Field(default=None, validation_alias="COBRAQ_SANDBOX_ROOT")
    research_dir: Path = Field(default=PROJECT_ROOT / "research", validation_alias="COBRAQ_RESEARCH_ROOT")
    external_ai_enabled: bool = Field(default=True, validation_alias="COBRAQ_EXTERNAL_AI_ENABLED")
    vector_enabled: bool = Field(default=True, validation_alias="COBRAQ_VECTOR_ENABLED")
    max_upload_bytes: int = Field(default=100 * 1024 * 1024, ge=1024, validation_alias="COBRAQ_MAX_UPLOAD_BYTES")
    max_document_pages: int = Field(default=300, ge=1, le=2000, validation_alias="COBRAQ_MAX_DOCUMENT_PAGES")
    extraction_timeout: int = Field(default=900, ge=10, le=7200, validation_alias="COBRAQ_EXTRACTION_TIMEOUT")
    ocr_page_timeout: int = Field(default=45, ge=1, le=300, validation_alias="COBRAQ_OCR_PAGE_TIMEOUT")
    tesseract_cmd: str = Field(default="", validation_alias="COBRAQ_TESSERACT_CMD")
    tessdata_dir: str = Field(default="", validation_alias="COBRAQ_TESSDATA_DIR")

    # JWT
    secret_key: str = "cobraq_super_secret_key_change_this_in_production_32chars_minimum"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 60 * 24  # 24 hours

    # AI
    anthropic_api_key: str = "YOUR_KEY_HERE"

    # Paths
    data_dir: Path = Field(default=BACKEND_ROOT / "data", validation_alias=AliasChoices("COBRAQ_DATA_DIR", "DATA_DIR"))

    @model_validator(mode="after")
    def resolve_paths(self):
        self.data_dir = self.data_dir.expanduser().resolve() if self.data_dir.is_absolute() else (BACKEND_ROOT / self.data_dir).resolve()
        self.research_dir = self.research_dir.expanduser().resolve() if self.research_dir.is_absolute() else (PROJECT_ROOT / self.research_dir).resolve()
        if self.profile == "sandbox":
            if self.sandbox_root is None or not self.sandbox_root.is_absolute():
                raise ValueError("Sandbox requires an absolute COBRAQ_SANDBOX_ROOT")
            self.sandbox_root = self.sandbox_root.resolve()
            for path in (self.data_dir, self.research_dir):
                if path == self.sandbox_root or not path.is_relative_to(self.sandbox_root):
                    raise ValueError("Sandbox data and research paths must stay inside its root")
                if any(path.is_relative_to(protected) for protected in
                       (BACKEND_ROOT / "data", PROJECT_ROOT / "data", PROJECT_ROOT / "research")):
                    raise ValueError("Sandbox cannot use the working dataset")
            self.external_ai_enabled = False
            self.vector_enabled = False
            self.anthropic_api_key = ""
        return self

    @property
    def uploads_dir(self) -> Path:
        return self.data_dir / "uploads"

    @property
    def cloud_ai_available(self) -> bool:
        return self.external_ai_enabled and bool(self.anthropic_api_key and self.anthropic_api_key != "YOUR_KEY_HERE")

@lru_cache
def get_settings() -> Settings:
    return Settings(_env_file=os.environ.get("COBRAQ_ENV_FILE", BACKEND_ROOT / ".env"))


def data_path(*parts: str) -> Path:
    return get_settings().data_dir.joinpath(*parts)
