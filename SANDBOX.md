# Môi trường chạy và sandbox CobraQ

Môi trường Python hiện tại là `.venv` với Python 3.12.14, đã kiểm tra phụ thuộc.
Sandbox local dùng các thư viện trong `.venv`, có cấu hình, tài khoản và dữ liệu
riêng trong `.sandbox`; không sao chép tài khoản, khóa API, lịch sử hay điểm thật.

## Chạy trên Windows

```powershell
.\setup_sandbox.bat  # Khởi tạo một lần; chạy lại giữ nguyên tài khoản và dữ liệu
.\start_sandbox.bat  # http://127.0.0.1:8010
.\test_sandbox.bat   # Kiểm tra API bằng dữ liệu sandbox, ghi kết quả trong sandbox
.\stop_sandbox.bat   # Dừng đúng tiến trình sandbox; giữ nguyên dữ liệu
```

Tài khoản **admin, teacher, student** và mật khẩu ngẫu nhiên nằm trong
`.sandbox/credentials.json`. Không có mật khẩu cố định trong code. File này và
`.sandbox/.env` được loại khỏi Git. Khóa JWT của sandbox được tạo ngẫu nhiên riêng.
`start.bat` tiếp tục chạy môi trường local thông thường trên cổng 8000.

Giao diện sandbox có nhãn **SANDBOX · Dữ liệu thử nghiệm**. Mỗi tài khoản có đề
mô phỏng 10 câu để thử làm bài, chấm điểm và lịch sử. Đề này không phải học liệu
Lịch sử hay kết quả nghiên cứu. Bản sao 199 đoạn nguồn, 60 câu nháp và 51 truy vấn
SGK được giữ ở trạng thái chờ duyệt; thao tác duyệt trong sandbox chỉ ghi vào bản sao.

## Dữ liệu và cấu hình

| Đường dẫn | Nội dung |
| --- | --- |
| `.sandbox/.env` | Cấu hình riêng và khóa JWT |
| `.sandbox/credentials.json` | Ba tài khoản thử nghiệm |
| `.sandbox/data/` | User store, đề thi, nhóm, lịch sử, điểm, audit, evaluation và config |
| `.sandbox/research/` | Bản sao corpus, câu nháp, gold, ảnh nguồn và revision thử nghiệm |
| `.sandbox/models/`, `.sandbox/artifacts/` | Vị trí cấp model/adapter cục bộ nếu cần |
| `.sandbox/cache/` | Cache runtime riêng |
| `.sandbox/logs/smoke-report.json` | Kết quả kiểm tra chức năng gần nhất |
| `.sandbox/run/server.json` | PID và thời điểm tạo tiến trình để dừng đúng server |
| `.sandbox/manifest.json` | Phiên bản sandbox và hash tài liệu đầu vào |

Mọi module lưu trữ đọc đường dẫn từ cấu hình chung, không phụ thuộc thư mục hiện
tại. Mặc định môi trường local dùng `backend/data`; sandbox bắt buộc giữ dữ liệu
và nghiên cứu dưới root riêng và từ chối trỏ tới các thư mục dữ liệu thật.

Sandbox tắt API AI bên ngoài, tắt ChromaDB và dùng keyword fallback cho đề upload.
Các bộ tải model nghiên cứu chỉ được dùng file cục bộ; launcher đặt chế độ offline
cho Hugging Face và cache riêng. Bật AI trong giao diện không vượt được chính sách
sandbox. Upload tối đa 25 MiB, mã đề không được trở thành đường dẫn filesystem.
Server chỉ lắng nghe `127.0.0.1`; không mở cổng LAN.

Sandbox local tách dữ liệu ở tầng ứng dụng, dùng chung tài khoản Windows và thư
viện Python với môi trường local. Nó không tạo ranh giới bảo mật của hệ điều hành.
Cấu hình container bên dưới dùng để tách tiến trình và filesystem khi cần.

## Sandbox khác cho từng lần thử

```powershell
.\.venv\Scripts\python.exe tools/sandbox.py init --root .sandboxes/demo-02
.\.venv\Scripts\python.exe tools/sandbox.py serve --root .sandboxes/demo-02 --port 8012
.\.venv\Scripts\python.exe tools/sandbox.py status --root .sandboxes/demo-02 --port 8012
.\.venv\Scripts\python.exe tools/sandbox.py stop --root .sandboxes/demo-02
```

Muốn dữ liệu mới, tạo profile mới thay vì ghi đè profile cũ. Không có lệnh xóa
dữ liệu tự động. Lệnh kiểm tra chức năng sẽ tạo lịch sử/audit thử nghiệm trong profile đó.

## Container tùy chọn

Đã có `Dockerfile.sandbox`, `compose.sandbox.yml` và `.dockerignore`. Máy hiện tại
chưa có Docker, nên cấu hình này mới được kiểm tra tĩnh, chưa build/chạy container.

Sau khi có Docker Desktop, khởi tạo sandbox trên host và dừng bản local trước:

```powershell
.\setup_sandbox.bat
.\stop_sandbox.bat
docker compose -f compose.sandbox.yml up --build -d
docker compose -f compose.sandbox.yml ps
docker compose -f compose.sandbox.yml down
```

Container chạy user 1000, filesystem hệ thống chỉ đọc, bỏ Linux capabilities,
`no-new-privileges`, giới hạn 2 CPU / 2 GiB / 128 PID, tmpfs 128 MiB. Chỉ các thư mục
sandbox được mount; không mount workspace, dữ liệu thật hay socket Docker. Mạng
runtime đặt `internal: true`, cổng web chỉ publish trên loopback. Build image cần
Internet để tải các thư viện; image CPU nhẹ không cài model hoặc stack GPU.

Container dùng chung **dữ liệu sandbox** với bản local trên host. Chỉ chạy một bản
trên bộ dữ liệu này tại một thời điểm. Dùng `docker compose ... down` để dừng container;
`stop_sandbox.bat` dành cho tiến trình Python trên host.

## Kiểm thử hồi quy

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s research/tests -v
.\.venv\Scripts\python.exe -m unittest discover -s tools/tests -v
.\.venv\Scripts\python.exe -m pip check
```

Kiểm thử sandbox dùng profile tạm riêng, đối chiếu hash dữ liệu thật trước/sau,
kiểm tra mọi module lưu trữ, đăng nhập ba role, làm bài/chấm điểm, khóa cloud AI,
chặn đường dẫn thoát root, dung lượng upload, vòng đời start/status/stop và bảo vệ
tiến trình khác khi PID file đã cũ. Kiểm tra mạng từ chối kết nối ngoài loopback.
