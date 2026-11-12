# Trích xuất tài liệu trên CobraQ

Chạy `start.bat` và mở `http://127.0.0.1:8000`. Đây là môi trường local chính,
dùng `backend/data`, không phải sandbox. Server mặc định chạy một worker và không
tự reload khi sửa file, tránh ngắt OCR đang chạy. Sau khi cập nhật code backend,
dừng server sau khi các tài liệu hoàn tất rồi chạy lại.

## Đưa tài liệu vào

1. Đăng nhập, mở **Tệp đã tải / Tài liệu và đề thi**.
2. Kéo thả hoặc chọn Word `.docx` / PDF. Mặc định tối đa 100 MiB/tệp, 300 trang/PDF.
3. Theo dõi trạng thái chờ/đang đọc và tiến độ từng trang. Đọc PDF scan chạy nền;
   bạn có thể chuyển trang trong ứng dụng hoặc mở lại thư viện để theo dõi.
4. Chọn **Xem trích xuất** để xem văn bản và các đoạn có nguồn. Với PDF, mở ảnh
   trang gốc ngay từ từng đoạn. Có thể tải lại tệp nguồn đã lưu.
5. Nếu tài liệu có trắc nghiệm, chọn **Kiểm tra câu hỏi và đáp án**. Bổ sung đáp án
   bị thiếu, sửa phương án rồi lưu trước khi dùng để chấm bài.

Tài liệu chỉ có văn bản, sách hoặc báo cáo vẫn được lưu thành nội dung học liệu dù
không nhận dạng được câu trắc nghiệm. Những tài liệu này không có đề để tự chấm.

## Nội dung được đọc

- Word: đoạn văn và bảng theo thứ tự trong tài liệu; câu hỏi tách nhiều dòng,
  phương án chung một dòng, đáp án ghi trực tiếp, đáp án tô màu/đỏ và bảng đáp án.
- Bảng đáp án chia theo Bài được ghép theo đúng bài và số câu, kể cả khi số câu
  bắt đầu lại từ 1. Các dấu hiệu gần giống ký tự A/B/C/D được chuẩn hóa ở vị trí
  nhãn và gắn cờ; không thay chữ trong nội dung phương án.
- PDF chữ: lấy text theo trang, giữ nguồn trang và dấu hiệu tô màu/đỏ của phương án.
  Trắc nghiệm bắt đầu ở cuối trang và kết thúc ở trang sau vẫn được ghép.
- PDF scan: dựng từng trang thành ảnh và chạy Tesseract tiếng Việt/Anh cục bộ;
  lưu phương thức đọc, confidence và cảnh báo từng trang. Không gọi API AI để
  trích xuất hay đoán đáp án.
- Văn bản được chia thành các đoạn tối đa khoảng 1.400 ký tự, giữ SHA-256 và số
  trang nguồn. Mỗi đoạn có ID ổn định theo nguồn và nội dung.

Ảnh nhúng trong Word chưa được OCR. Hãy xuất Word sang PDF nếu cần đọc chữ trong
ảnh. Word không có số trang ổn định nên hệ thống ghi vị trí đoạn, không tự gán
số trang. Định dạng đúng/sai và bảng nối cột được giữ trong văn bản nguồn; chỉ
trắc nghiệm A/B/C/D được đưa vào ngân hàng câu hỏi hiện tại.

Trích xuất không đồng nghĩa đã kiểm duyệt học thuật. Các đoạn và câu mới đều có
`review_status=review_required`. Câu thiếu đáp án hoặc sai cấu trúc được giữ để
sửa, không tự đoán và không đưa vào bài tự chấm. Khi có dấu hiệu đáp án mâu thuẫn,
đáp án để trống để người dùng đối chiếu.

## Lưu trữ và chạy lại

Tệp gốc, trạng thái và báo cáo nằm trong:

```text
backend/data/documents/<mã người sở hữu>/<doc-SHA256>/
  source.docx hoặc source.pdf
  status.json
  extraction.json
```

Ngân hàng câu hỏi tương ứng nằm trong thư mục tài khoản ở `backend/data/users/`.
Tài liệu giống nhau được nhận ra theo hash của toàn bộ tệp, kể cả khi đổi tên.
Tải lại không tạo bộ câu trùng và không ghi đè câu đã sửa. Hai tệp khác nội dung
nhưng trùng tên nhận hai ID khác nhau. JSON được ghi bằng tệp tạm rồi thay thế;
các thao tác sửa ngân hàng được tuần tự với việc xuất kết quả trích xuất.

Tác vụ bị ngắt được ghi **Bị gián đoạn** khi server khởi động lại. Bản gốc vẫn
còn; tải lại cùng tệp để chạy lại. Không báo hoàn tất nếu chỉ xử lý được một phần.
Một số trang không đọc được sẽ xuất hiện trong báo cáo kèm cảnh báo cụ thể;
các trang đọc được vẫn có văn bản để kiểm tra.

Giới hạn hàng đợi: tối đa 5 tài liệu/tài khoản và 10 tài liệu chờ/đang xử lý toàn
hệ thống; một tác vụ OCR chạy tại một thời điểm để giới hạn bộ nhớ.

## OCR và cấu hình

Máy hiện tại có Tesseract tại `C:/Program Files/Tesseract-OCR/tesseract.exe`.
Bộ tiếng Việt có sẵn tại `research/tools/tessdata/vie.traineddata`; tiếng Anh được
lấy từ bản Tesseract đã cài. Các model ngôn ngữ OCR được sao chép vào cache của
môi trường, không trộn dữ liệu của sandbox và local.

Các biến tùy chọn trong `backend/.env`:

```dotenv
COBRAQ_MAX_UPLOAD_BYTES=104857600
COBRAQ_MAX_DOCUMENT_PAGES=300
COBRAQ_EXTRACTION_TIMEOUT=900
COBRAQ_OCR_PAGE_TIMEOUT=45
# COBRAQ_TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
# COBRAQ_TESSDATA_DIR=C:/path/to/tessdata
```

Khi triển khai máy khác, cài Tesseract và cung cấp bộ ngôn ngữ `vie`, `eng`.
API capabilities báo rõ khả năng OCR. PDF có mật khẩu, tệp hỏng, tệp rỗng hoặc
vượt giới hạn được trả lỗi cụ thể, không chuyển sang trạng thái thành công giả.

## API

| API | Chức năng |
| --- | --- |
| `GET /api/documents/capabilities` | Định dạng, giới hạn và khả năng OCR |
| `POST /api/documents/upload` | Nhận multipart `file`, trả 202 và ID theo dõi |
| `GET /api/documents` | Danh sách tài liệu của tài khoản |
| `GET /api/documents/{id}` | Trạng thái và tiến độ |
| `GET /api/documents/{id}/content?offset=0&limit=20` | Kết quả, cảnh báo và phân trang các đoạn |
| `GET /api/documents/{id}/source` | Tải tệp gốc |
| `GET /api/documents/{id}/pages/{page}` | Ảnh trang PDF để đối chiếu |
| `POST /api/files/upload` | API tương thích cũ, chờ kết quả đọc rồi trả ngân hàng |

Các API tài liệu riêng yêu cầu JWT đăng nhập; tài liệu của tài khoản khác không
được truy cập bằng cách đổi `X-User-Id`. Endpoint tương thích cũ giữ giao thức của
phiên bản trước. Giao diện mới dùng API chạy nền để tránh chờ request OCR dài.

## Kiểm thử

```powershell
.\.venv\Scripts\python.exe -m unittest tools.tests.test_extraction research.tests.test_pipeline research.tests.test_evaluation -v
```

Kiểm thử API dùng thư mục tạm trên profile local, không chạy dự án trên sandbox
và không sửa dữ liệu tài khoản thật. Bao gồm Word bảng/inline/tô đỏ, đáp án theo
bài, câu qua hai trang, OCR thật, file hỏng, PDF có mật khẩu, chunk không bị cắt
mất chữ, quyền xem bản gốc, lưu/sửa/tải lại, và trạng thái sau khởi động lại.
