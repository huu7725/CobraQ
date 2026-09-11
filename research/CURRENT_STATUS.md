# Trạng thái triển khai CobraQ

Cập nhật ngày 11-09-2026.

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
- Chuẩn hóa 600 câu đã duyệt thành AQG schema v2. Target của mô hình chỉ còn
  `question_type`, `stem`, `choices`, `correct_answer` và `explanation`; ID,
  metadata, cấu hình thực nghiệm và citation do máy chủ gắn xác định.
- Hoàn tất QLoRA v2 cho TinyLlama 1.1B trên 480 mẫu train và 60 mẫu validation,
  3 epoch/180 step, context 1.792 token, seed 42. Adapter cuối 17,21 MiB;
  `eval_loss` giảm 0,2580 -> 0,2350 -> 0,2285; peak VRAM 2.947,96 MiB,
  thời gian huấn luyện 47 phút 43 giây và không có mẫu bị cắt.
- Thêm checkpoint mỗi 10 step, tự khôi phục checkpoint mới nhất và script
  kiểm chứng adapter trên tập test chưa huấn luyện.
- Tích hợp suy luận 4-bit, seed, giới hạn ngữ cảnh RAG và số liệu peak VRAM vào
  Auto-Exam Pipeline. Schema chặn phương án trùng/gần trùng; citation sai buộc
  trạng thái `needs_teacher_review`.
- Khóa pilot v2 gồm 10 yêu cầu giống nhau cho mỗi C0-C3, đủ 6 chủ đề, 10 bài,
  7 câu trắc nghiệm và 3 câu tự luận. Cổng GO/NO-GO kiểm tra JSON/schema,
  factuality tự động, phương án nhiễu, citation, truncation, latency và VRAM.
- Chạy đủ 40 lượt pilot trên RTX 3050 Ti. C0 và C1 đạt 0/10 schema; C2 đạt
  8/10; C3 đạt 0/10 dù 9/10 đầu ra parse được JSON. C3 có 9 lỗi schema và
  1 lỗi JSON; C2 có một lỗi dữ kiện thời gian tự động phát hiện.
- Pilot quyết định `NO-GO`; runner đã được kiểm chứng từ chối chạy full 40x4.
  Kết quả thất bại được giữ nguyên trong mẫu số, không hạ ngưỡng sau thực nghiệm.
- Sửa công cụ kiểm chứng adapter để dùng cùng strict schema với runtime. Mẫu
  held-out đầu tiên hiện được báo đúng `valid_schema=false` do phương án trùng.
- Hoàn tất prompt contract v2.1 dùng chung cho train/verify/runtime. TinyLlama
  được serialize bằng native chat template; luật MCQ/tự luận đã tách riêng và
  C0/C2 không còn chuỗi context giả.
- Lưu raw output, latency, token, VRAM và truncation cho cả lượt sai JSON/schema;
  evaluator tổng hợp runtime metrics trên mọi lượt có telemetry.
- Execution contract hash prompt, backend, schema, evaluator, runner, config,
  request và adapter; thay đổi bất kỳ thành phần nào đều vô hiệu báo cáo GO cũ.
- Batch verifier mặc định kiểm tra 10 mẫu held-out bằng một lần nạp model, tách
  JSON/schema failure và không tự cấp nhãn factuality/sư phạm.
- Token-audit prompt v2.1 đã đạt trên đủ 540 mẫu: tổng token trung bình 1.113,70,
  p95 1.497, p99 1.698, tối đa 1.892; `oversized_examples=0` và không cắt mẫu.
- Hoàn tất QLoRA v2.1 cho TinyLlama 1.1B: 480 train, 60 validation, 3 epoch,
  180/180 bước. Run resume an toàn từ checkpoint-80, giữ nguyên hash dữ liệu và
  prompt v2.1; adapter cuối nằm tại `artifacts/adapters/history12_lora_v2_1`.
  `eval_loss` theo epoch là 0,2547 -> 0,2324 -> 0,2268; peak PyTorch VRAM
  3.278,08 MiB; thời gian thực thi 8.574,68 giây; không có mẫu bị cắt.
- Tích hợp giao diện mới trực tiếp vào `CobraQ_v3.html`: dashboard và menu thay
  đổi theo học sinh/giáo viên/quản trị viên, đồng thời giữ upload, nhóm, AI Eval,
  audit, thống kê và bản đồ hiện có.
- Thêm luồng luyện SGK từ 60 câu held-out đã duyệt, tra cứu hybrid, đối chiếu
  citation và mở ảnh trang SGK; responsive mobile đã chuyển sang thanh menu đáy.
- Thêm API practice tách biệt thực nghiệm C0-C3 và Postman Collection cho health,
  auth, luyện tập, RAG, ảnh nguồn và AQG. QA local đã kiểm tra 50 test, JavaScript
  frontend, desktop/mobile và cả ba role.
- Tạo queue kiểm tra độc lập 60 câu từ train/validation, loại trừ test held-out:
  đủ 17 bài, 42 trắc nghiệm, 18 tự luận và độ khó 23/19/18. Queue có cờ ưu tiên
  cho 37 nhóm stem lặp và 18 tự luận còn placeholder; mọi cột chấm của giáo viên
  vẫn để trống. File Excel gồm các sheet `Câu hỏi 60`, `Retrieval Gold` và
  `Hướng dẫn`.
- Tạo retrieval-gold queue 51 truy vấn, 3 truy vấn/bài cho 17 bài. `relevant_chunk_ids`
  chưa được tự gán; cần giáo viên xác nhận và đổi `review_status` thành
  `teacher_approved` trước khi chạy evaluate_retrieval.py.
- Xuất workbook giáo viên riêng tại `outputs/retrieval_gold_review/Retrieval_Gold_Teacher_Review.xlsx`,
  gồm sheet `Retrieval Gold` và `Hướng dẫn`; bản CSV làm việc là
  `research/datasets/retrieval_gold.csv`. Cả 51 dòng vẫn ở trạng thái
  `pending_teacher_review`, chưa được dùng để tính Recall/MRR/nDCG.
- Đã tạo script tái lập `research/build_review_queues.py` và
  `research/build_retrieval_gold_workbook.mjs` để tạo lại hai queue từ hash dữ
  liệu đã khóa. Workbook retrieval gold đã được render/inspect; không có công
  thức hoặc dữ liệu giáo viên nào được tự động điền.
- Token-audit v2.1 được lưu tại `research/results/PROMPT_TOKEN_AUDIT_V2_1.json`;
  540 mẫu có tổng token tối đa 1.892/2.048, `oversized=0`, `truncated=0`.

## Yêu cầu cần làm

- Bộ nhãn huấn luyện do một người duyệt, toàn bộ điểm rubric là 5/5 và không có
  câu nào chỉnh khác bản nháp. Đây là nhãn cho dữ liệu huấn luyện, không được dùng
  thay cho kết quả chấm mù C0-C3 của ba giáo viên.
- Adapter v2 chưa đạt quality gate. C0/C1 sinh văn bản lặp thay vì JSON; C3 chủ
  yếu trùng phương án hoặc sinh `multiple_choice` khi được yêu cầu tự luận.
- Adapter v2.1 đã có adapter cuối nhưng chưa lưu báo cáo batch verifier trong
  workspace hiện tại; cần kiểm tra 10 mẫu held-out bằng adapter cuối trước pilot.
  Không được dùng adapter v2 để đánh giá prompt contract mới.
- Retrieval chưa có gold label do giáo viên xác nhận; một số top chunk mới chỉ là
  tiêu đề hoặc mục tiêu bài học, chưa đủ làm bằng chứng sinh câu hỏi.
- Chỉ số `auto_verified` hiện có dương tính giả về ngữ nghĩa. Citation do server
  gắn chỉ chứng minh provenance đúng, không chứng minh nội dung được nguồn hỗ trợ.
- Server local đã dừng sau QA; có thể khởi động lại bằng Uvicorn trên port 8000.
- Queue review độc lập và retrieval gold hiện đang chờ giáo viên; chưa được dùng
  làm nhãn huấn luyện hoặc kết quả đánh giá cuối.
- Các file làm việc: `outputs/cobraq_teacher_review_60/CobraQ_Independent_Review_60.xlsx`
  và `research/datasets/retrieval_gold.csv`.
- Chưa được chạy full 40x4 do pilot `NO-GO`; chưa có điểm rubric của ba giáo viên
  và phản hồi học sinh để tính độ tin cậy, độ khó và độ phân hóa thực nghiệm.

## Điều kiện để công bố kết quả

1. Chạy batch verifier 10 mẫu held-out trên adapter cuối và lưu báo cáo JSON. Chỉ
   kiểm tra JSON/schema, latency, VRAM và truncation; không tự phê duyệt factuality.
2. Giáo viên hoàn tất queue review độc lập 60 câu, sau đó giữ nguyên bản gốc và
   lưu bản có revision riêng nếu có chỉnh sửa.
3. Giáo viên điền retrieval gold 51 truy vấn, lọc chunk tiêu đề/mục tiêu và chạy
   `evaluate_retrieval.py` ở các mode keyword/dense/hybrid.
4. Đăng ký một pilot mới độc lập. Không dùng lại 10 prompt đã dùng để sửa mô hình
   làm tập xác nhận chính thức và không hạ các ngưỡng GO/NO-GO.
5. Chỉ khi pilot mới đạt GO, chạy đủ 40 yêu cầu mới cho mỗi C0-C3 trên cùng phần
   cứng, sau đó để ba giáo viên chấm mù và phân tích rubric.
6. Thử nghiệm học sinh chỉ bắt đầu sau khi toàn bộ câu đã được giáo viên duyệt.
