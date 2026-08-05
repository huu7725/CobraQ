# Rubric giáo viên đánh giá câu hỏi CobraQ

## Mục đích

Rubric dùng để đánh giá mù câu hỏi của bốn cấu hình C0-C3. Giáo viên không được
biết câu hỏi thuộc cấu hình nào. Thứ tự câu hỏi phải được xáo trộn riêng cho từng
người chấm.

## Thang điểm

- 1: Không đạt, không thể sử dụng.
- 2: Cần sửa lớn.
- 3: Dùng được sau khi chỉnh sửa.
- 4: Tốt, chỉ cần sửa rất ít.
- 5: Có thể đưa vào ngân hàng câu hỏi.

## Tiêu chí và trọng số

| Mã | Tiêu chí | Trọng số | Bắt buộc |
|---|---|---:|:---:|
| R1 | Chính xác dữ kiện lịch sử | 20% | Có |
| R2 | Câu hỏi và đáp án được nguồn trích dẫn hỗ trợ | 15% | Có |
| R3 | Đáp án đúng duy nhất | 15% | Có, với trắc nghiệm |
| R4 | Câu dẫn rõ ràng, không mơ hồ | 10% | Không |
| R5 | Phù hợp SGK và mục tiêu bài học | 10% | Không |
| R6 | Đúng mức độ nhận thức yêu cầu | 10% | Không |
| R7 | Phương án nhiễu hợp lý, không vô tình đúng | 10% | Không |
| R8 | Ngôn ngữ và tính sư phạm | 5% | Không |
| R9 | Độ khó phù hợp với học sinh lớp 12 | 5% | Không |

Điểm tổng được quy đổi về thang 5 theo trọng số. Với câu tự luận, bỏ R3 và R7,
sau đó chuẩn hóa lại tổng trọng số của các tiêu chí còn lại về 100%.

## Quy tắc quyết định

- Chấp nhận: điểm tổng từ 4,2 và mọi tiêu chí bắt buộc đạt ít nhất 4.
- Cần sửa: điểm tổng từ 3,4 đến dưới 4,2 và không có lỗi dữ kiện nghiêm trọng.
- Loại bỏ: điểm dưới 3,4 hoặc bất kỳ tiêu chí bắt buộc nào đạt từ 2 trở xuống.

Ngoài điểm Likert, giáo viên phải chọn `Chấp nhận / Cần sửa / Loại bỏ`, ghi nhận
có lỗi dữ kiện hay không, và ước lượng số phút cần chỉnh sửa. Chỉ số thời gian sửa
phản ánh trực tiếp giá trị hỗ trợ giáo viên của CobraQ.

## Thiết kế chấm mù

- Chọn 160 câu: 40 câu từ mỗi cấu hình C0-C3.
- Cân bằng theo 17 bài, loại câu hỏi và ba mức độ khó.
- Dùng mã ngẫu nhiên thay cho tên mô hình/cấu hình.
- Ba giáo viên chấm độc lập; không trao đổi trong vòng chấm đầu.
- Câu có lỗi factuality phải ghi rõ dữ kiện sai và trang SGK đối chứng.

## Phân tích độ tin cậy

- Dùng ICC cho điểm tổng có trọng số.
- Dùng Krippendorff's Alpha hoặc weighted Kappa cho quyết định ba mức.
- Báo cáo Cronbach's Alpha của các tiêu chí rubric.
- So sánh C0-C3 bằng Friedman test; nếu có khác biệt, thực hiện Wilcoxon cặp đôi
  với hiệu chỉnh Holm và báo cáo Kendall's W.
