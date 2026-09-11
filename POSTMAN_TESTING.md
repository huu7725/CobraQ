# Kiểm thử CobraQ bằng Postman

Server local: `http://127.0.0.1:8000`

## Import collection

1. Mở Postman và chọn **Import**.
2. Chọn file `postman/CobraQ.postman_collection.json`.
3. Mở collection **CobraQ - Lịch sử 12 API**.
4. Collection đã có biến `base_url=http://127.0.0.1:8000`.

## Thứ tự kiểm thử khuyến nghị

### 1. Kiểm tra server

Chạy `01. Hệ thống / Health check`.

Kết quả mong đợi:

```json
{"status": "ok"}
```

### 2. Đăng nhập

Chạy lần lượt:

1. `02. Tài khoản / Đăng ký học sinh` nếu tài khoản chưa tồn tại.
2. `02. Tài khoản / Đăng nhập và lưu JWT`.
3. `02. Tài khoản / Thông tin người dùng hiện tại`.

Script của request đăng nhập tự lưu JWT vào biến collection `token`. Những API
cần đăng nhập dùng header:

```text
Authorization: Bearer {{token}}
```

Nếu email mẫu đã tồn tại, có thể bỏ qua đăng ký và chạy đăng nhập trực tiếp.

### 3. Kiểm thử luyện tập

Chạy theo thứ tự:

1. `Danh mục 17 bài`.
2. `Bắt đầu 5 câu trắc nghiệm`.
3. `Nộp phiên luyện tập`.

Request bắt đầu tự lưu `session_id` vào biến `practice_session_id`. Request nộp
bài sử dụng biến này. Một session chỉ được nộp một lần; muốn thử lại phải chạy
request bắt đầu trước.

Để lọc theo bài, thay `lesson_id` trong body, ví dụ:

```json
{
  "lesson_id": "lesson_07",
  "question_type": "multiple_choice",
  "num_questions": 5
}
```

### 4. Kiểm thử RAG

Chạy `04. Tra cứu SGK / Tìm Chiến dịch Điện Biên Phủ`.

Mỗi kết quả cần có:

- `chunk_id`: mã đoạn nguồn;
- `page`: trang SGK;
- `text`: nội dung truy xuất;
- `score`: điểm truy xuất;
- `metadata.lesson_id`: bài học tương ứng.

Request `Xem ảnh trang SGK 42` kiểm tra ảnh trang nguồn mà frontend hiển thị.

### 5. Endpoint AQG C3

Request trong folder `05. AQG thực nghiệm` chỉ chạy sau khi adapter v2.1 huấn
luyện xong và qua pilot. Trong trạng thái hiện tại, phản hồi `503` là đúng vì hệ
thống không được phép giả lập adapter chưa hoàn tất.

## Mã lỗi thường gặp

| Mã | Ý nghĩa | Cách xử lý |
|---:|---|---|
| 200 | Thành công | Kiểm tra JSON và test tab |
| 400 | Body không hợp lệ | Kiểm tra email, mật khẩu hoặc tham số |
| 401 | Thiếu/sai JWT | Chạy lại request đăng nhập |
| 404 | Không có dữ liệu/session | Tạo session mới hoặc đổi bài |
| 422 | Sai schema request | Đối chiếu body với Swagger `/docs` |
| 503 | Model/adapter chưa sẵn sàng | Không chạy AQG trước khi pilot GO |

Swagger UI có tại `http://127.0.0.1:8000/docs`.
