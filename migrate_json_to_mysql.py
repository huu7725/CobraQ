#!/usr/bin/env python3
"""
One-time migration: data/users/* (JSON) + data/config.json -> MySQL.
Chạy sau khi tạo database và cấu hình biến môi trường DB_*.
  python migrate_json_to_mysql.py
"""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

# Ensure project root on path
ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from db import init_schema_from_file  # noqa: E402
import repository as repo  # noqa: E402


def load_json(path: Path, default):
    try:
        if path.exists():
            with open(path, encoding="utf-8") as f:
                return json.load(f)
    except Exception:
        pass
    return default


def migrate_config():
    cfg_path = ROOT / "data" / "config.json"
    data = load_json(cfg_path, {})
    if "ai_parse_enabled" in data:
        repo.set_ai_parse_enabled(bool(data["ai_parse_enabled"]))
        print("  app_config: ai_parse_enabled =", data["ai_parse_enabled"])


def migrate_users():
    users_dir = ROOT / "data" / "users"
    if not users_dir.is_dir():
        print("Không có thư mục data/users — bỏ qua.")
        return
    n = 0
    for user_dir in sorted(users_dir.iterdir()):
        if not user_dir.is_dir():
            continue
        uid = user_dir.name
        repo.ensure_user(uid)
        index = load_json(user_dir / "files_index.json", {})
        for file_id, meta in index.items():
            qpath = user_dir / f"{file_id}.json"
            questions = load_json(qpath, [])
            if not questions:
                print(f"  [skip] {uid}/{file_id}: không có câu hỏi")
                continue
            name = meta.get("name", file_id)
            filename = meta.get("filename", "")
            uploaded_at = meta.get("uploaded_at", "")
            parse_method = meta.get("parse_method", "normal")
            repo.replace_file_questions(
                uid, file_id, questions, name, filename, uploaded_at, parse_method
            )
            print(f"  OK file {uid}/{file_id}: {len(questions)} câu")
            n += 1
        hist = load_json(user_dir / "history.json", [])
        for h in hist:
            repo.append_history(
                uid,
                int(h.get("score", 0)),
                int(h.get("total", 0)),
                int(h.get("percent", 0)),
                int(h.get("time_taken", 0)),
                (h.get("file_id") or "all") or "all",
                h.get("wrong_questions") or [],
            )
        if hist:
            print(f"  OK history {uid}: {len(hist)} bản ghi")
    print(f"Hoàn tất migrate users (đã xử lý ít nhất {n} file có câu hỏi).")


def main():
    os.chdir(ROOT)
    print("Khởi tạo schema...")
    init_schema_from_file()
    print("Migrate config.json...")
    migrate_config()
    print("Migrate data/users...")
    migrate_users()
    print("Xong.")


if __name__ == "__main__":
    main()
