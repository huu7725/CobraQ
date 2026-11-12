# Giao diện CobraQ

Frontend vẫn chạy HTML/JavaScript thuần, không cần build hoặc npm.

- `mission_map.js`, `mission_map.css`: bản đồ nhiệm vụ lớp 12, lọc theo thời gian,
  chứng cứ và bài giải thích; quy trình kiểm tra/mở nhiệm vụ và chấm giáo viên.
- `vendor/leaflet`: Leaflet 1.9.4 cục bộ, kèm giấy phép; nền bản đồ tải từ
  OpenStreetMap. Xem `../MISSION_MAP.md` để biết nguồn và phạm vi bản đầu.

- `../CobraQ_v3.html`: màn hình đăng nhập, điều hướng, trang chủ theo vai trò,
  tài liệu, bài làm, kết quả và quản trị.
- `ui.css`: kiểu chữ, màu, các thành phần chung và bố cục desktop/mobile.
  Được nạp sau CSS cũ để áp dụng bộ giao diện thống nhất cho cả các màn hình quản lý.
- `research.js`: tra cứu SGK, luyện câu đã duyệt và duyệt nguồn/câu hỏi/gold.
- `documents.js`: đưa Word/PDF vào hàng đợi nền, theo dõi từng trang OCR, hiển thị
  văn bản/chunks/cảnh báo, mở trang PDF gốc và tải lại tệp nguồn. Hiện dùng trên
  môi trường chính cổng 8000; xem `../DOCUMENT_EXTRACTION.md`.

Các tệp trong thư mục này được backend phục vụ qua `/assets`. Giao diện nghiên cứu
tiếp tục được nạp qua `/research-ui.js`. Chạy `start_sandbox.bat` và mở cổng 8010
để thử bằng dữ liệu sandbox.

Giao diện dùng font Be Vietnam Pro, fallback Segoe UI/sans-serif khi không tải được
font mạng. Màu chính xanh trầm, nền sáng; không dùng emoji hoặc hình raster để trang
trí. SVG chỉ dùng cho menu, hướng đi và tải tài liệu. Ưu tiên tên thao tác rõ ràng.

Mobile dưới 860 px dùng menu mở gọn và bốn mục điều hướng nhanh, thay cho hàng menu
dài phải cuộn ngang. Nguồn SGK nằm cạnh câu hỏi trên desktop và chuyển xuống dưới
trên điện thoại. Có focus bàn phím, nhãn trường nhập, nút hiện/ẩn mật khẩu, thông báo
trạng thái, hỗ trợ giảm chuyển động và giữ focus trong hộp thoại.

Ảnh kiểm tra nằm trong `../output/qa/ui-dashboard-desktop.jpg`,
`../output/qa/ui-dashboard-mobile.jpg` và `../output/qa/ui-login-desktop.jpg`.
Các luồng trình duyệt đã kiểm tra: đăng nhập cả ba vai trò, đổi tài khoản về trang
chủ đúng vai trò, chọn và hoàn thành bài 5 câu, xem kết quả, tải danh sách tài liệu,
mở menu mobile, mở trang SGK, lưu bản nháp trong sandbox, và trạng thái thiếu nhãn
đánh giá. Không sử dụng thao tác duyệt dữ liệu thật trong quá trình QA giao diện.
