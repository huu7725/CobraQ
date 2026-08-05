# Trạng thái triển khai CobraQ

Cập nhật ngày 02-08-2026.

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
- Kiểm thử tự động toàn bộ logic cốt lõi.

## Cần con người hoặc phần cứng bên ngoài

- 61/197 chunk đang ở hàng đợi kiểm duyệt OCR. Câu dùng các chunk này luôn nhận
  trạng thái `needs_teacher_review`.
- Chưa có 600-1.000 câu hỏi `teacher_approved` để huấn luyện LoRA.
- Máy hiện tại dùng bản PyTorch CPU-only, không phù hợp để huấn luyện adapter cuối.
- Chưa thể chạy kết quả C2/C3 trước khi có adapter LoRA.
- Chưa có điểm rubric của ba giáo viên và phản hồi của học sinh; do đó chưa thể
  tính ICC/Krippendorff's Alpha, độ khó và độ phân hóa thực nghiệm.

## Điều kiện để công bố kết quả

1. Giáo viên duyệt/correct 61 chunk OCR hoặc đánh dấu loại bỏ.
2. Hoàn thành tập AQG có trạng thái `teacher_approved` và chia theo bài học.
3. Huấn luyện LoRA trên GPU, lưu manifest checkpoint và seed.
4. Chạy đủ 40 yêu cầu cho mỗi C0-C3 trên cùng phần cứng.
5. Ba giáo viên chấm mù 160 câu và chạy phân tích rubric.
6. Thử nghiệm học sinh chỉ bắt đầu sau khi toàn bộ câu đã được giáo viên duyệt.
