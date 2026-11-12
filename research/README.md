# Công cụ nghiên cứu Lịch sử 12

Chạy từ thư mục CobraQ bằng Python trong `.venv`. Luồng nghiên cứu tách riêng
ngân hàng đề do người dùng tải lên. Xem `../CURRENT_STATUS.md` để biết tài nguyên
thực sự còn thiếu; các script không tự tạo nhãn giáo viên hoặc kết quả thực nghiệm.

## Giao diện và API

`start.bat` phục vụ ứng dụng tại `http://127.0.0.1:8000`.
Đăng nhập giáo viên/quản trị viên rồi vào **Duyệt học liệu**. Duyệt nguồn trước,
câu hỏi và gold sau. Khi cần sửa, lưu thành revision riêng; không sửa trực tiếp
các tệp corpus/dataset gốc sau khi đã có revision.

API có tiền tố `/api/research`: `status`, `lessons`, `search`,
`source-pages/{book_page}`, `reviews/{chunks|questions|gold}`,
`practice`, `practice/{id}/answer`, `auto-exam`. Tất cả yêu cầu đăng nhập;
các API review và auto-exam yêu cầu role teacher/admin. OpenAPI ở `/docs`.
Ứng dụng cục bộ dùng một worker để tuần tự hóa revision.

## Kiểm tra nhanh

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s research/tests -v
```

## Truy xuất

```powershell
.\.venv\Scripts\python.exe -m research.evaluate_retrieval --modes keyword dense hybrid --output research/results/retrieval_run_01.json
```

Lệnh từ chối chạy khi còn gold chưa duyệt hoặc nguồn đã thay đổi. Bộ dense/hybrid
yêu cầu model `sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2` đã
được cấp sẵn cục bộ, hoặc đặt `COBRAQ_EMBEDDING_MODEL` tới thư mục model.
Không có cơ chế tự tải hoặc thay thế bằng embedding giả.

## Kiểm chứng adapter

Thư viện suy luận tùy chọn: `pip install -r research/requirements.txt`. Các gói
CUDA cần tương thích với phần cứng thực tế. Không cần cài các gói này chỉ để duyệt
dữ liệu và luyện câu đã duyệt.

Đặt `COBRAQ_MODEL_DIR` tới model nền và `COBRAQ_ADAPTER_DIR` tới adapter cuối.
Mặc định tìm trong `models/TinyLlama-1.1B-Chat-v1.0` và
`artifacts/adapters/history12_lora_v2_1`. Mặc định 4-bit cần CUDA;
`COBRAQ_LOAD_IN_4BIT=0` cho phép chạy không lượng tử hóa. Không trộn phần cứng
hoặc lượng tử hóa giữa các cấu hình so sánh.

```powershell
.\.venv\Scripts\python.exe -m research.verify_adapter --train path/to/train.jsonl --validation path/to/validation.jsonl --test path/to/test.jsonl --count 10 --output research/results/verifier_run_01.json
```

Các bản ghi cần `id`, `chunk_ids`, `lesson_id`, `question` theo strict schema.
Test cần `split="test"`, `review_status="teacher_approved"` từ dữ liệu gốc,
source chunk không trùng train/validation. Không thay bằng queue 60 câu độc lập.
Verifier dùng C2 để kiểm tra adapter trên model nền; không tự cấp GO hay factuality.
Prompt khôi phục đã đổi contract; phải khôi phục prompt gốc hoặc kiểm chứng lại.

## Chất lượng văn bản và thực thể

```powershell
.\.venv\Scripts\python.exe -m research.evaluate_quality path/to/quality.jsonl --output research/results/quality_run_01.json
```

Mỗi dòng: `id`, `prediction`, `reference`, `predicted_entities`, `gold_entities`.
Entity có dạng `{"type":"YEAR","text":"1945"}`; đây là đối chiếu chính xác theo
loại và chuỗi chuẩn hóa, không phải chấm span/token NER. BLEU-4 dùng một tham chiếu,
không smoothing, thang 0-1, token hóa NFKC/casefold và từ; ROUGE-L là trung bình F1
LCS từng cặp. Câu dưới bốn token có BLEU-4 bằng 0 theo quy ước này.

Nhãn `historical_factuality` là `correct`, `incorrect` hoặc `unreviewed`; hai nhãn
đầu cần `reviewer_id`, `reviewed_at` ISO. Khi chưa chấm, hallucination rate là null.
Báo cáo ghi riêng tỷ lệ trên mẫu đã chấm và độ đầy đủ; không dùng overlap để chấm
ngữ nghĩa và không dùng điểm tập con làm kết quả toàn bộ thực nghiệm.

## Pre-test / Post-test

```powershell
.\.venv\Scripts\python.exe -m research.analyze_study path/to/study.csv --output research/results/study_run_01.json
```

CSV có `participant_id,group,pre_test,post_test`. Dùng mã ẩn danh, mỗi học sinh một
cặp điểm đầy đủ trên thang 0-10; `group` là `experimental` hoặc `control`.
Script không tự loại dòng thiếu hoặc gán điểm. Kết quả gồm mức tăng điểm từng nhóm,
Welch t-test hai phía cho gain và chênh lệch baseline; không tự suy ra quan hệ nhân quả.
Trường hợp hai nhóm đều có phương sai bằng 0 trả kết quả chưa xác định.

Các lệnh xuất báo cáo yêu cầu đường dẫn mới để giữ nguyên kết quả những lần chạy trước.
