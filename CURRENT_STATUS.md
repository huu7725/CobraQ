# Trạng thái CobraQ trong workspace hiện tại

## Cập nhật trích xuất tài liệu trên môi trường chính

Ngày 12/11/2026, luồng Word/PDF/OCR đã chạy trên `http://127.0.0.1:8000`,
profile `local`, dữ liệu lưu trong `backend/data`. Đây là môi trường sử dụng
hiện tại theo yêu cầu mới của người dùng; sandbox không được dùng để chạy dự án.

- Đề cương Word: 120 câu, 120 đáp án, 33 đoạn nguồn; có 3 câu gắn cờ chuẩn hóa nhãn
  phương án cần kiểm tra. Đáp án theo Bài được ghép riêng, không trộn số câu lặp.
- `Câu 1.docx`: 1 câu và 1 đoạn nguồn; không có đáp án trong file, giữ trống để bổ sung.
- PDF SGK gốc 116 trang, 56.543.226 byte: OCR cục bộ đủ 116/116 trang, trích
  310.881 ký tự, 309 đoạn nguồn trong 386,578 giây; 4 trang được gắn cờ kiểm tra.
  11 nội dung được nhận dạng như ứng viên trắc nghiệm chưa có đáp án, không đưa vào
  chấm tự động. Nguồn PDF giữ theo số trang PDF, không tự quy đổi số trang sách.
- Lưu bản gốc và SHA-256, trạng thái nền theo trang, kết quả phân trang; tải lại
  cùng tệp không nhân bản hay ghi đè câu đã sửa. Hai tệp khác nội dung cùng tên
  được lưu riêng. File hỏng/rỗng, PDF có mật khẩu, giới hạn dung lượng/trang và
  OCR timeout có lỗi rõ. Tác vụ bị ngắt được đánh dấu để chạy lại từ tệp gốc.
- Kết quả vẫn đọc được sau khi khởi động lại server; bản gốc tải về khớp SHA-256;
  nguồn tài liệu yêu cầu JWT và không đọc được bằng tài khoản khác hoặc giả X-User-Id.
- 63 kiểm thử core/nghiên cứu/trích xuất đạt, kèm kiểm tra cú pháp frontend và phụ thuộc.
- Kiểm tra giao diện bằng trình duyệt bị cổng cấp quyền từ chối trên origin 8000;
  đã kiểm tra qua HTTP API, các tệp frontend và mã JavaScript, chưa xác nhận trực tiếp
  luồng giao diện trích xuất lần này.

Hướng dẫn: [DOCUMENT_EXTRACTION.md](DOCUMENT_EXTRACTION.md).
Báo cáo lần chạy thật: `output/extraction/LOCAL_EXTRACTION_REPORT.json`.
Văn bản, chunks SGK và 120 câu Word đã xuất riêng trong `output/extraction/`.

## Các cập nhật trước đó

Cập nhật 12/11/2026. Đây là trạng thái của code và dữ liệu đang có trên máy này.

Đã bổ sung sandbox local cổng 8010, ba tài khoản thử nghiệm, dữ liệu/khóa JWT riêng,
khóa API AI bên ngoài và bộ lệnh setup/start/test/stop. Thư viện chạy trong `.venv`
đã được kiểm tra. Xem [SANDBOX.md](SANDBOX.md). Cấu hình container đã tạo nhưng chưa
chạy vì máy hiện chưa có Docker.

Đã cập nhật UI/UX HTML với font Be Vietnam Pro, nền sáng và màu xanh trầm; bỏ emoji,
giảm icon trang trí và gradient. Trang chủ theo vai trò, chọn đề, tải tài liệu,
SGK và duyệt học liệu đã được sắp xếp lại. Mobile dùng menu thu gọn; các trạng thái
chờ duyệt/chưa có dữ liệu hiển thị riêng. Kết quả QA giao diện ở `output/qa/ui-*.jpg`.
Bản CURRENT_STATUS.md ngoài Desktop mô tả một workspace trước đó; không dùng
các kết quả đã ghi trong bản đó để khẳng định tài nguyên hiện có.

## Đã cập nhật code

- Nối `/api/research` vào backend và giao diện: luyện Lịch sử 12, tìm nguồn theo
  bài, xem ảnh trang SGK, duyệt/sửa OCR, câu hỏi và retrieval gold.
- Giáo viên/quản trị viên mới được xem bản nháp và lưu quyết định. Danh tính người
  duyệt lấy từ JWT. Học sinh chỉ được dùng câu và nguồn đã duyệt.
- Mỗi quyết định lưu vào `research/reviews/{chunks,questions,gold}/` bằng tệp riêng,
  có hash trước/sau, thời điểm và ghi chú; dữ liệu khôi phục gốc được giữ nguyên.
  Đây là nhật ký kiểm tra tính toàn vẹn, không phải chữ ký số chống giả mạo.
- Sửa nguồn sau khi đã duyệt làm vô hiệu câu luyện tập/gold phụ thuộc, cần duyệt
  lại trước khi sử dụng. Từ chối duyệt tiêu đề/mục tiêu bài học làm bằng chứng.
  Bộ lọc bằng quy tắc chỉ hỗ trợ sàng lọc; giáo viên vẫn cần đối chiếu nội dung.
- Truy xuất BM25, dense embedding đa ngôn ngữ cục bộ và hybrid RRF có bộ lọc bài.
  Thiếu embedding được báo lỗi rõ; không dùng vector giả hoặc tự tải model.
- Sinh C0=base, C1=base+RAG, C2=adapter, C3=adapter+RAG; JSON/schema nghiêm ngặt,
  chặn phương án trùng, sai loại câu và khóa JSON trùng. Citation do server gắn.
- Kiểm tra nguồn, trang, trích dẫn và năm của đáp án/lời giải. Kết quả máy luôn
  `needs_teacher_review`, ngữ nghĩa `not_assessed`; không tự cấp nhãn factuality.
- Batch verifier giữ raw output, lỗi JSON/schema, số liệu latency/token/VRAM,
  truncation và lỗi runtime trong mẫu số. Kiểm tra tách source chunk của test
  khỏi train/validation. Hash code, runner, evaluator, package, model, adapter,
  request, corpus và các tệp dữ liệu để truy vết lần chạy.
- Sửa MRR/Hit Rate/Precision/NDCG/Recall: relevance dựa trên gold; không suy ra
  gold từ việc có citation. Chưa đủ gold đã duyệt thì không công bố điểm trên tập con.
- Bổ sung BLEU-4, ROUGE-L, entity Precision/Recall/F1; factuality cần nhãn giáo viên.
  Bổ sung phân tích pre/post theo gain và Welch t-test giữa hai nhóm độc lập.
- Sửa `.venv` trỏ tới máy cũ; script setup/start phát hiện interpreter không chạy.
  Frontend gọi API cùng origin; sửa lớp đăng nhập và thêm menu đáy trên màn hình hẹp.

## Đã kiểm tra

- 40 kiểm thử offline cho schema, trust, quyền API, revision, gold, leakage,
  công thức retrieval/NLP và thống kê, sử dụng dữ liệu tạm tách biệt.
- Kiểm tra cú pháp JavaScript frontend và Python; `pip check` không báo xung đột.
- Kiểm tra trình duyệt trên bản sao dữ liệu: mở 60 câu / 51 truy vấn, lưu bản nháp,
  mở đúng ảnh SGK trang 10, hiển thị trạng thái chưa có câu đã duyệt, menu đáy.
  Không có lỗi JavaScript trong các luồng này.

## Chưa thể hoàn tất bằng code đơn thuần

- Có 199 đoạn trích khôi phục, 60 câu nháp, 51 truy vấn; chưa có quyết định giáo viên
  trong dữ liệu thật. Không tự tái tạo 600 nhãn đã duyệt hoặc 60 câu held-out đã mất.
- Chưa có model nền, adapter v2.1 và bộ train/validation/test gốc trong workspace.
  Verifier chưa chạy model thật; C0-C3/4-bit và dense chưa được xác nhận trên GPU.
- Prompt đang khôi phục mang tên `history12-rebuild-v1`, không phải bản prompt
  v2.1 gốc đã huấn luyện. Cần khôi phục contract gốc hoặc huấn luyện/kiểm chứng
  lại trước khi so sánh kết quả. Không dùng báo cáo GO cũ cho code mới.
- Chưa khôi phục script huấn luyện và runner pilot/full có cổng GO/NO-GO gốc.
  `full_experiment_allowed=false`. Cần đăng ký pilot mới độc lập và khôi phục các
  ngưỡng gốc trước khi chạy full 40x4; không suy GO từ việc verifier parse được JSON.
- Chưa có chấm mù ba giáo viên, thực nghiệm học sinh và khảo sát. Code đo lường
  đã bổ sung không thay thế dữ liệu hay kết quả thực nghiệm.
- Luồng sinh/duyệt hiện hỗ trợ trắc nghiệm đơn lựa chọn và tự luận ngắn.
  Nối sự kiện/điền từ và NER mô hình học máy chuyên biệt chưa được khôi phục.

## Tiếp tục công việc

1. Chạy `start.bat`, đăng nhập giáo viên, vào **Duyệt học liệu**; sửa và duyệt nguồn
   trước, sau đó duyệt 60 câu và xác nhận 51 truy vấn. Thao tác thật do giáo viên thực hiện.
2. Khôi phục model, adapter và dữ liệu gốc; kiểm tra contract trước khi chạy verifier.
3. Chạy đánh giá retrieval trên đủ gold; khôi phục và đăng ký pilot mới trước full.
4. Chỉ thực nghiệm học sinh khi câu hỏi đã được giáo viên duyệt; nhập điểm thật để
   phân tích bằng công cụ thống kê, giữ riêng nhãn dữ liệu và đánh giá chấm mù.
