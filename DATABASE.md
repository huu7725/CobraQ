# MySQL cho CobraQ

## 0. Cài MySQL Server (nếu chưa có)

Trên Windows, cần **MySQL đang chạy** (cổng 3306 mặc định). Ví dụ:

- [MySQL Installer](https://dev.mysql.com/downloads/installer/) (nhớ bật Windows Service)
- Hoặc **XAMPP / Laragon** — bật service MySQL

Nếu lệnh `python create_mysql_database.py` báo không kết nối được, MySQL chưa chạy hoặc sai mật khẩu.

## 1. Tạo database (tự động)

Sau khi chỉnh `DB_USER` / `DB_PASSWORD` trong file `.env` (đã có sẵn trong project, không commit lên git):

```bash
python create_mysql_database.py
```

Hoặc tạo thủ công trong MySQL:

```sql
CREATE DATABASE cobraq CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS 'cobraq'@'localhost' IDENTIFIED BY 'your_password';
GRANT ALL PRIVILEGES ON cobraq.* TO 'cobraq'@'localhost';
FLUSH PRIVILEGES;
```

## 2. Biến môi trường

File `.env` ở thư mục gốc project (đã được `db.py` nạp qua `python-dotenv`) gồm `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD`.

Có thể copy từ `.env.example` nếu cần tạo lại.

## 3. Cài package

```bash
pip install -r requirements.txt
```

Khi chạy server, bảng được tạo tự động từ `schema.sql` (startup FastAPI).

## 4. Migrate dữ liệu JSON cũ (một lần)

Sau khi DB trống hoặc đã backup:

```bash
python migrate_json_to_mysql.py
```

Chỉ nên chạy **một lần** mỗi môi trường; chạy lại có thể **nhân đôi lịch sử làm bài** (`quiz_history`).

## 5. Chạy server

```bash
uvicorn main_updated:app --host 127.0.0.1 --port 8000
```

hoặc `start.bat`.
