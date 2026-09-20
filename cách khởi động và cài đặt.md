# CobraQ - Trợ lý ôn tập và tạo câu hỏi Lịch sử 12

CobraQ là nguyên mẫu web hỗ trợ học sinh ôn tập SGK Lịch sử 12, giáo viên quản lý học liệu/câu hỏi và quản trị viên theo dõi hệ thống. Backend dùng FastAPI, frontend được FastAPI phục vụ trực tiếp từ `CobraQ_v3.html`. Phạm vi học liệu hiện tại là SGK Lịch sử 12 - bộ Kết nối tri thức với cuộc sống.

## Khởi động nhanh trên Windows

### Lần đầu cài đặt

Mở PowerShell tại thư mục dự án:

```powershell
cd "C:\Users\<tên-bạn>\Desktop\CobraQ"
```

Tạo môi trường Python và cài thư viện backend:

```powershell
cd backend
python -m venv venv
.\venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
```

Nếu PowerShell chặn activate, chỉ cần gọi trực tiếp Python trong môi trường:

```powershell
.\venv\Scripts\python.exe -m pip install -r requirements.txt
```

Tạo file cấu hình local (không đưa file này lên Git):

```powershell
Copy-Item .env.example .env
```

Mở `backend/.env` và đổi ít nhất `SECRET_KEY` và `ADMIN_PASSWORD`. `GROK_API_KEY` chỉ cần khi muốn dùng tính năng AI cần API; luồng luyện 60 câu và tra cứu SGK có sẵn có thể dùng để chạy thử local.

### Mỗi lần chạy sau

```powershell
cd "C:\Users\<tên-bạn>\Desktop\CobraQ\backend"
.\venv\Scripts\Activate.ps1
uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Giữ cửa sổ PowerShell này mở. Mở trình duyệt tại:

- Ứng dụng: <http://127.0.0.1:8000>
- Tài liệu API Swagger: <http://127.0.0.1:8000/docs>
- Kiểm tra server: <http://127.0.0.1:8000/health> (kết quả mong đợi: `{"status":"ok"}`)

Dừng server bằng `Ctrl+C`.

### Cho người khác dùng trong cùng mạng Wi-Fi

Trên máy chạy server, lấy địa chỉ IPv4:

```powershell
ipconfig
```

Chạy server lắng nghe các thiết bị trong mạng:

```powershell
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Người dùng khác mở `http://<IPv4-của-máy-chạy-server>:8000`, ví dụ `http://192.168.1.20:8000`. Hai máy phải cùng mạng và Windows Firewall phải cho phép Python/Uvicorn qua mạng riêng. Không mở cổng này ra Internet công cộng; muốn chia sẻ qua Internet hãy dùng deploy Render theo hướng dẫn bên dưới.

### Dùng môi trường đã có sẵn trong máy phát triển

Nếu repository đã có `backend/venv` hoặc `venv2`, không cần tạo lại môi trường:

```powershell
cd "C:\Users\<tên-bạn>\Desktop\CobraQ\backend"
..\venv2\Scripts\python.exe -m uvicorn app.main:app --host 127.0.0.1 --port 8000
```

Lệnh trên cần được chạy từ thư mục `backend` để Python tìm đúng package `app` và dữ liệu local.

## Chạy thử sản phẩm

1. Mở `http://127.0.0.1:8000`.
2. Chọn **Tiếp tục với tư cách khách** rồi vào **Luyện SGK đã duyệt**.
3. Chọn bài, loại câu hỏi và số lượng, sau đó bấm **Bắt đầu luyện**.
4. Chọn đáp án và nộp bài để xem lời giải, nguồn SGK và kết quả.
5. Chọn **Tra cứu SGK** để thử tìm một sự kiện, ví dụ `Chiến dịch Điện Biên Phủ năm 1954`.

Đây là dữ liệu held-out đã duyệt dùng để trình diễn luồng luyện tập. Chức năng sinh câu hỏi mới bằng adapter chỉ được bật sau khi batch verifier và pilot đạt quality gate; không coi JSON hợp lệ hoặc citation đúng provenance là bằng chứng tuyệt đối về tính đúng lịch sử.

## Kiểm thử bằng Postman

Collection có sẵn tại `postman/CobraQ.postman_collection.json`. Import file này vào Postman, giữ biến `base_url` là `http://127.0.0.1:8000`, rồi chạy theo thứ tự Health, đăng ký/đăng nhập, danh mục luyện tập, bắt đầu phiên, nộp phiên và Tra cứu SGK. Hướng dẫn chi tiết và mã lỗi nằm trong [POSTMAN_TESTING.md](./POSTMAN_TESTING.md).

## Chạy bằng Docker

Đã cài Docker Desktop, chạy tại thư mục gốc:

```powershell
docker build -t cobraq .
docker run --rm -p 8000:7860 --env-file backend/.env cobraq
```

Sau đó mở `http://127.0.0.1:8000`. Dockerfile cài Python, Poppler và Tesseract cần cho xử lý tài liệu. Dữ liệu trong container là dữ liệu tạm nếu không mount volume.

## Deploy Render

Repository đã có `Dockerfile`, `render.yaml` và hướng dẫn tại [DEPLOY_RENDER.md](./DEPLOY_RENDER.md). Khi deploy cần khai báo các secret trong Render Dashboard, tối thiểu `SECRET_KEY`; không commit `.env`, API key hoặc dữ liệu người dùng. Gói Free có giới hạn RAM và không có persistent disk, phù hợp demo hơn là vận hành dữ liệu thật.

## Cấu trúc chính

```text
CobraQ/
├── CobraQ_v3.html              # Frontend theo vai trò học sinh/giáo viên/admin
├── backend/app/main.py         # FastAPI entry point và static frontend
├── backend/app/api/             # Auth, luyện tập, file, nhóm, nghiên cứu...
├── backend/requirements.txt
├── data/research/               # Dữ liệu nghiên cứu local
├── artifacts/adapters/          # Adapter local, không bắt buộc để chạy demo
├── postman/                     # Postman collection
├── Dockerfile
├── render.yaml
└── POSTMAN_TESTING.md
```

## Lưu ý cho người nhận repository

- Cần Python 3.11 trở lên; Windows nên dùng PowerShell.
- Không commit `backend/.env`, mật khẩu, API key, database người dùng hoặc file model lớn.
- Nếu chỉ muốn xem giao diện, có thể mở server local và dùng luồng khách; không mở `CobraQ_v3.html` bằng `file://` vì frontend cần API HTTP.
- Nếu cổng 8000 đang bận, dừng tiến trình cũ hoặc dùng cổng khác, ví dụ `--port 8001`, rồi mở đúng URL mới.
- Dữ liệu và model nghiên cứu lớn có thể được loại khỏi Git; cần lấy đúng artifact/data tương ứng trước khi chạy thực nghiệm.

## Công nghệ

FastAPI, Uvicorn, SQLAlchemy/SQLite, JWT, ChromaDB, multilingual-e5-small, Tesseract OCR, TinyLlama và QLoRA/PEFT. Frontend là HTML/CSS/JavaScript một file, không cần bước build Node.js.

## Tài liệu liên quan

- [POSTMAN_TESTING.md](./POSTMAN_TESTING.md) - kiểm thử API.
- [DEPLOY_RENDER.md](./DEPLOY_RENDER.md) - deploy Render.
- [research/README.md](./research/README.md) - pipeline nghiên cứu và đánh giá.
- [research/CURRENT_STATUS.md](./research/CURRENT_STATUS.md) - tiến độ, giới hạn và điều kiện công bố.

MIT - sử dụng cho mục đích cá nhân và giáo dục.
