# CobraQ — Hệ thống ôn tập trắc nghiệm

## Cấu trúc thư mục

```
CobraQ/
├── main_updated.py     ← Backend server (FastAPI)
├── CobraQ_v3.html      ← Giao diện web
├── requirements.txt    ← Danh sách thư viện
├── start.bat           ← Khởi động (double-click)
├── stop.bat            ← Tắt server
└── data/               ← Dữ liệu người dùng (tự tạo)
```

---

## Cách dùng lần đầu

1. Cài Python 3.9+ tại https://www.python.org/downloads/
   - ⚠️ Nhớ tick **"Add Python to PATH"** khi cài

2. Double-click **`start.bat`**
   - Tự cài thư viện
   - Tự mở trình duyệt
   - Xong!

---

## Các lần sau

Double-click **`start.bat`** là xong.

---

## Lưu ý

- Giữ nguyên cửa sổ CMD khi dùng — đóng CMD là server tắt
- Dữ liệu lưu trong thư mục `data/` — **đừng xóa thư mục này**
- Để tắt server: nhấn **CTRL+C** trong CMD, hoặc double-click `stop.bat`

---

## Tính năng

- Upload đề thi (Word .docx / PDF)
- Làm bài trắc nghiệm ngẫu nhiên
- **Xem & chỉnh sửa câu hỏi** sau khi upload (nút 👁 Xem)
- Thêm / xóa / sửa từng câu hỏi
- Lịch sử kết quả
- AI Vision đọc đáp án từ bảng tô màu (cần API key Anthropic)
