# CobraQ — Hệ thống ôn tập trắc nghiệm

## 1) Giới thiệu

CobraQ là ứng dụng ôn tập trắc nghiệm gồm:
- **Backend**: FastAPI (`main_updated.py`)
- **Frontend**: HTML/JS (`CobraQ_v3.html`)
- **CSDL**: MySQL

Hỗ trợ upload đề từ:
- `.pdf`
- `.docx`
- `.doc` (hỗ trợ cơ bản, khuyến nghị đổi sang `.docx` để ổn định hơn)

---

## 2) Cấu trúc thư mục chính

```text
CobraQ/
├── main_updated.py      # Backend server (FastAPI)
├── CobraQ_v3.html       # Giao diện web
├── db.py                # Kết nối DB + migration nhẹ
├── repository.py        # Tầng thao tác dữ liệu
├── schema.sql           # Schema MySQL
├── requirements.txt     # Danh sách thư viện Python
├── setup.bat            # Cài đặt lần đầu
├── start.bat            # Khởi động hệ thống
├── stop.bat             # Tắt server (8000/5500)
└── .env                 # Biến môi trường (tự tạo từ .env.example nếu có)
```

---

## 3) Yêu cầu môi trường

- Windows 10/11
- Python **3.11** (khuyến nghị)
- MySQL đang chạy

---

## 4) Cài đặt lần đầu

### Bước 1: Cài Python
- Tải tại: https://www.python.org/downloads/
- Khi cài, nhớ tick **Add Python to PATH**

### Bước 2: Cấu hình `.env`
Nếu chưa có `.env`, bạn có thể:
- tạo thủ công, hoặc
- chạy `setup.bat` để tự tạo từ `.env.example` (nếu tồn tại)

Ví dụ tối thiểu:

```env
DB_HOST=127.0.0.1
DB_PORT=3306
DB_NAME=cobraq
DB_USER=root
DB_PASSWORD=your_password

JWT_SECRET=change-me-in-production
JWT_REFRESH_SECRET=change-me-refresh-secret
JWT_EXPIRE_HOURS=24
JWT_REFRESH_EXPIRE_DAYS=14

ADMIN_EMAIL=admin@cobraq.local
ADMIN_PASSWORD=admin123456
```

### Bước 3: Chạy `setup.bat`
- Double-click `setup.bat`
- Script sẽ:
  - tạo `venv`
  - cài dependencies từ `requirements.txt`
  - kiểm tra kết nối DB

---

## 5) Chạy ứng dụng

Double-click `start.bat`

Script sẽ tự:
- khởi động frontend tại `http://127.0.0.1:5500/CobraQ_v3.html`
- khởi động backend tại `http://127.0.0.1:8000`
- mở trình duyệt đúng URL

> Lưu ý: Giữ cửa sổ backend đang chạy. Đóng cửa sổ này thì backend dừng.

---

## 6) Tắt ứng dụng

Có 2 cách:
1. Nhấn `Ctrl + C` ở cửa sổ backend
2. Double-click `stop.bat` để tắt tiến trình đang nghe port 8000/5500

---

## 7) Đăng nhập mặc định

Theo `.env`:
- Email: `ADMIN_EMAIL` (ví dụ `admin@cobraq.local`)
- Password: `ADMIN_PASSWORD` (ví dụ `admin123456`)

---

## 8) Upload file không ra đề — cách xử lý nhanh

1. Đảm bảo backend đang chạy ở `127.0.0.1:8000`
2. Đảm bảo mở frontend bằng **HTTP**:
   - `http://127.0.0.1:5500/CobraQ_v3.html`
   - không dùng `file://` hoặc `https://`
3. Nhấn `Ctrl + F5`
4. Thử lại bằng `.docx` nếu file `.doc` parse kém

---

## 9) Gợi ý khi làm việc nhóm / đẩy Git

Nên commit:
- `main_updated.py`, `db.py`, `repository.py`, `schema.sql`
- `requirements.txt`
- `setup.bat`, `start.bat`, `stop.bat`
- `README.md`
- `.env.example` (nếu có)

Không nên commit:
- `.env`
- `__pycache__/`
- `*.pyc`
- dữ liệu nhạy cảm (API key, mật khẩu thật)

---

## 10) Ghi chú
- App chưa hỗ trợ tự sinh kết quả ( khuyến khích upload file có đáp án để test và làm )
- App chưa hỗ trợ các môn học như toán lí hóa ( các công thức toán học ) 
- App đã hỗ trợ cơ chế migration nhẹ cho bảng `users` khi startup.
- Với file Word bảng lớn (ví dụ PLDC), hệ thống đã tối ưu parser để nhận câu hỏi tốt hơn.
- Nếu cần độ chính xác cao hơn nữa về map đáp án, ưu tiên file `.docx` có định dạng đáp án rõ (bold/color/highlight hoặc bảng đáp án chuẩn).
