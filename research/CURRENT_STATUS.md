# Trạng thái triển khai CobraQ

Cập nhật ngày 17-08-2026.

## Đã hoàn thành

- Khóa phạm vi SGK Lịch sử 12, bộ Kết nối tri thức: 6 chủ đề, 17 bài.
- OCR cục bộ 106 trang nội dung bằng Tesseract tiếng Việt/Anh.
- Tạo 197 chunk có nguồn, trang sách, bài, chủ đề, thời gian và thực thể ứng viên.
- Lập manifest SHA-256 và lưu TSV confidence để truy vết OCR.
- Tạo ChromaDB 197 vector bằng embedding đa ngôn ngữ.
- Thêm hybrid retrieval, bộ lọc bài học và RRF.
- Thêm Trust Layer kiểm tra ngày/năm, citation ID, trang và quote nguồn.
- Thêm schema trắc nghiệm/tự luận và API Auto-Exam.
- Khóa bốn cấu hình C0-C3 và tạo 40 yêu cầu đánh giá cân bằng theo bài.
- Thêm rubric giáo viên, công cụ tính điểm và phân tích câu hỏi học sinh.
- Thêm script LoRA/QLoRA, runner thực nghiệm và evaluator retrieval/factuality.
- Tạo workbook duyệt OCR có 55 ảnh trang nguồn, phân loại 61 chunk theo rủi ro kỹ thuật.
- Thêm cổng nhập kết quả duyệt có kiểm tra chữ ký, ngày duyệt, tính toàn vẹn và audit SHA-256.
- Giáo viên đã hoàn tất 61/61 quyết định OCR; corpus đã duyệt gồm 197 chunk và
  ChromaDB đã được lập chỉ mục lại, không còn chunk `review_required`.
- Tạo 600 ứng viên AQG cân bằng 17 bài: 420 trắc nghiệm, 180 tự luận; phân bố độ
  khó 1/2/3 là 240/240/120. Mỗi mẫu có chunk, trang và trích dẫn SGK để đối chiếu.
- Tạo workbook duyệt AQG và trình hoàn tất chỉ xuất dữ liệu khi đạt rubric,
  có mã/ngày người duyệt và trạng thái `teacher_approved`.
- Hoàn tất 600/600 nhãn `teacher_approved` ngày 14-08-2026 và kết xuất tập LoRA
  theo source chunk: 480 train, 60 validation, 60 test; không có chunk rò rỉ.
- Kiểm thử tự động toàn bộ logic cốt lõi.
- Cài môi trường CUDA cục bộ: PyTorch 2.12.0+cu130, Transformers 5.9.0,
  PEFT 0.20.0, Accelerate 1.14.0 và bitsandbytes 0.50.1.
- Hoàn tất QLoRA TinyLlama 1.1B trên 480 mẫu train và 60 mẫu validation,
  3 epoch/180 step, context 1.792 token, seed 42. Adapter cuối khoảng 18 MB,
  `eval_loss` giảm 0,2043 -> 0,1841 -> 0,1795; peak VRAM 3.076 MB.
- Thêm checkpoint mỗi 10 step, tự khôi phục checkpoint mới nhất và script
  kiểm chứng adapter trên tập test chưa huấn luyện.
- Tích hợp suy luận 4-bit, seed, giới hạn ngữ cảnh RAG và số liệu peak VRAM vào
  Auto-Exam Pipeline. Schema chặn phương án trùng/gần trùng; citation sai buộc
  trạng thái `needs_teacher_review`.
- Smoke test C3 chạy đủ RAG + LoRA trên RTX 3050 Ti: 975 prompt token, 965
  completion token, 72,4 giây, peak VRAM 1.106 MB.
- Pilot một yêu cầu chung qua C0-C3 đã chạy xong và ghi cả lỗi. Cả bốn cấu hình
  đều không qua schema ở mẫu đầu tiên; C2 đã sinh JSON nhưng bị loại do phương án
  trùng. C3 context-fit dùng 731 input token, không truncation, nhưng vẫn dùng hết
  1.280 output token và sinh JSON có control character. Đây là lỗi mô hình/dữ liệu,
  không còn là lỗi cửa sổ context.

## Cần con người hoặc phần cứng bên ngoài

- Bộ nhãn huấn luyện do một người duyệt, toàn bộ điểm rubric là 5/5 và không có
  câu nào chỉnh khác bản nháp. Đây là nhãn cho dữ liệu huấn luyện, không được dùng
  thay cho kết quả chấm mù C0-C3 của ba giáo viên.
- Held-out smoke cho thấy adapter chưa đạt quality gate phát hành: một câu trắc
  nghiệm có phương án gần trùng và citation sai; câu tự luận sinh sai schema.
  Pipeline đã chặn/gắn `needs_teacher_review`, nhưng cần vòng dữ liệu và đánh giá
  lỗi trước khi dùng với học sinh.
- Chưa chạy đủ 40 yêu cầu cho từng C0-C3; chưa có tỷ lệ thành công, factuality và
  latency tổng hợp để kết luận tác động riêng của RAG/LoRA.
- Chưa có điểm rubric của ba giáo viên và phản hồi của học sinh; do đó chưa thể
  tính ICC/Krippendorff's Alpha, độ khó và độ phân hóa thực nghiệm.

## Điều kiện để công bố kết quả

1. Thiết kế schema đầu ra gọn hơn (server tự gắn lesson/condition/citation từ RAG),
   kết xuất lại nhãn đã duyệt và huấn luyện adapter v2 trước khi chạy full nếu pilot
   schema/citation/unique-answer chưa đạt ngưỡng định trước.
2. Khi adapter v2 qua pilot, chạy đủ 40 yêu cầu cho mỗi C0-C3 trên cùng phần cứng
   và phân tích cả tỷ lệ lỗi.
3. Ba giáo viên chấm mù các câu qua cổng kỹ thuật và chạy phân tích rubric.
4. Thử nghiệm học sinh chỉ bắt đầu sau khi toàn bộ câu đã được giáo viên duyệt.
