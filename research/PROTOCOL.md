# Giao thức nghiên cứu CobraQ - Lịch sử 12

## Phạm vi đóng băng

- Nguồn tri thức: SGK Lịch sử 12, bộ Kết nối tri thức với cuộc sống, bản mẫu
  tháng 10-2023.
- Phạm vi: 6 chủ đề, 17 bài và hai phụ lục thuật ngữ/phiên âm.
- Đầu ra chính: câu hỏi trắc nghiệm bốn lựa chọn và câu tự luận ngắn.
- Câu hỏi chỉ được đưa vào ngân hàng sau khi giáo viên phê duyệt.

## Câu hỏi nghiên cứu

- RQ1: RAG có giảm tỷ lệ sai dữ kiện so với SLM không truy xuất hay không?
- RQ2: LoRA có cải thiện chất lượng AQG so với mô hình nền hay không?
- RQ3: Cấu hình RAG + LoRA có đạt chất lượng sư phạm chấp nhận được với chi phí
  triển khai thấp hay không?

## Thiết kế ablation

| Điều kiện | RAG | LoRA | Vai trò |
|---|:---:|:---:|---|
| C0 | Không | Không | Base SLM |
| C1 | Có | Không | Đo tác động RAG |
| C2 | Không | Có | Đo tác động LoRA |
| C3 | Có | Có | CobraQ hoàn chỉnh |

Mọi điều kiện dùng cùng base checkpoint, seed, yêu cầu sinh, giới hạn token và
tham số decoding. C0/C2 chỉ nhận tên bài và yêu cầu; C1/C3 nhận thêm các chunk
do cùng một retriever trả về. Không thay prompt giữa các cấu hình ngoài phần ngữ
liệu RAG và mã điều kiện.

## Dữ liệu

- Corpus RAG được chia theo trang và đơn vị ngữ nghĩa; mỗi chunk luôn giữ
  `pdf_page`, `book_page`, `topic_id`, `lesson_id` và văn bản OCR gốc.
- Tập AQG dùng cho LoRA phải được giáo viên duyệt. Chia train/validation/test theo
  bài học hoặc cụm nội dung, không chia ngẫu nhiên từng câu.
- Tập retrieval gold gồm truy vấn và danh sách `chunk_id` liên quan do người chấm
  xác nhận. Log vận hành không được dùng thay cho retrieval gold.
- Tập test cuối không được dùng để chọn checkpoint, prompt hoặc threshold.

## Chỉ số

### Retrieval

`Recall@1/3/5`, `Precision@1/3/5`, MRR và nDCG@5 trên tập retrieval gold.

### Factuality và AQG

- Tỷ lệ câu có dữ kiện thời gian không được nguồn hỗ trợ.
- Tỷ lệ citation hợp lệ và quote xuất hiện trong chunk nguồn.
- Tỷ lệ đáp án đúng duy nhất, phương án trùng và lỗi JSON schema.
- BLEU, ROUGE-L và BERTScore chỉ là chỉ số phụ.

### Con người và học sinh

- Điểm rubric có trọng số, tỷ lệ chấp nhận, tỷ lệ cần sửa và phút chỉnh sửa.
- Với thử nghiệm học sinh: độ khó `p`, point-biserial và Cronbach's Alpha.
- Nếu mẫu học sinh dưới 100, chỉ báo cáo phân tích câu hỏi cổ điển mang tính thăm dò,
  không kết luận mô hình IRT.

### Tài nguyên

Đo latency p50/p95, token/giây, peak RAM/VRAM, thời gian huấn luyện, kích thước
adapter và kích thước mô hình triển khai. Phải ghi rõ CPU/GPU, phiên bản thư viện,
seed và hash của dữ liệu/checkpoint.

## Tiêu chí hoàn thành phiên bản nghiên cứu

- 100% câu C1/C3 có citation hợp lệ.
- Không tự động phê duyệt câu có dữ kiện thời gian không nằm trong nguồn.
- Ít nhất ba giáo viên tham gia chấm mù.
- Báo cáo đầy đủ cả chất lượng và chi phí cho C0-C3.
- Tất cả câu được sử dụng với học sinh đều có trạng thái `teacher_approved`.
