#!/usr/bin/env python3
"""
Tạo database MySQL `cobraq` (và chỉ vậy — bảng do server FastAPI tạo khi startup).
Cần MySQL Server đang chạy và thông tin đăng nhập đúng trong .env

  python create_mysql_database.py
"""
from __future__ import annotations

import os
import sys

# Load .env trước khi đọc biến môi trường
_ROOT = __file__.rsplit(os.sep, 1)[0]
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

import db  # noqa: E402 — kích hoạt load_dotenv trong db.py


def main() -> None:
    host = os.getenv("DB_HOST", "127.0.0.1")
    port = int(os.getenv("DB_PORT", "3306"))
    user = os.getenv("DB_USER", "root")
    password = os.getenv("DB_PASSWORD", "")
    db_name = os.getenv("DB_NAME", "cobraq")

    try:
        import mysql.connector
    except ImportError:
        print("Thiếu mysql-connector-python. Chạy: pip install -r requirements.txt")
        sys.exit(1)

    try:
        conn = mysql.connector.connect(
            host=host,
            port=port,
            user=user,
            password=password,
        )
    except Exception as e:
        print("Không kết nối được MySQL server.")
        print(f"  Lỗi: {e}")
        print()
        print("Hãy cài và khởi động MySQL (Windows):")
        print("  - MySQL Installer: https://dev.mysql.com/downloads/installer/")
        print("  - hoặc XAMPP / Laragon (bật service MySQL).")
        print("Sau đó chỉnh DB_USER / DB_PASSWORD trong file .env nếu cần.")
        sys.exit(1)

    cur = conn.cursor()
    cur.execute(
        f"CREATE DATABASE IF NOT EXISTS `{db_name}` "
        f"CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci"
    )
    conn.commit()
    cur.close()
    conn.close()
    print(f"Đã tạo (hoặc đã có) database: {db_name}")
    print("Chạy server: uvicorn main_updated:app --host 127.0.0.1 --port 8000")
    print("  (bảng sẽ được tạo tự động khi khởi động)")


if __name__ == "__main__":
    main()
