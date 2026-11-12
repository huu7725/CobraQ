"""Check that CobraQ's dependencies can actually be imported."""

import importlib
import sys

MODULES = (
    "fastapi", "uvicorn", "multipart", "dotenv", "pydantic",
    "pydantic_settings", "email_validator", "httpx", "aiofiles", "asgiref",
    "anthropic", "tiktoken", "slowapi", "sklearn", "numpy", "pypdf",
    "fitz", "docx", "PIL", "pdf2image", "chromadb",
    "sentence_transformers", "bcrypt", "passlib", "jose", "cryptography",
    "bleach",
)


def main():
    failed = []
    for name in MODULES:
        try:
            importlib.import_module(name)
        except Exception as exc:
            failed.append(name)
            print(f"FAILED {name}: {exc}")
    if failed:
        print(f"{len(failed)} dependencies could not be imported.")
        return 1
    print(f"ALL OK - {len(MODULES)} dependencies imported successfully")
    return 0


if __name__ == "__main__":
    sys.exit(main())
