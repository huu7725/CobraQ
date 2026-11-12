# Bản đồ nhiệm vụ Lịch sử 12

Phiên bản đầu nối trực tiếp vào `CobraQ_v3.html`, mục **Bản đồ nhiệm vụ 12**.
Chạy trên ứng dụng local cổng 8000, không dùng dữ liệu seed lịch sử chung của
trang `/map`. Trang bản đồ cũ được giữ nguyên để các chức năng trước tiếp tục hoạt động.

Mở thẳng `http://127.0.0.1:8000/mission-map` để trải nghiệm. Trang chủ và màn hình
đăng nhập đều có link vào nhiệm vụ; mobile có nút **Nhiệm vụ 12** ở thanh dưới.
Nút **Xem thử nhiệm vụ** hoạt động khi chưa đăng nhập: mở bản đồ, xếp mốc, đọc nguồn,
chọn chứng cứ và xem phản hồi tự động. Bài thử không tạo lượt học sinh, không mở duyệt
nội dung và không gửi phần viết tới giáo viên. Nút lưu của bài thử chỉ lưu trong
sessionStorage của phiên trình duyệt, theo thao tác chủ động của người dùng.

## Hai nhiệm vụ đã xây dựng

| Nhiệm vụ | Phạm vi | Kỹ năng |
| --- | --- | --- |
| Bước chuyển trên chiến trường Bắc Bộ | Bài 7; các mốc 1946, 1947 và 1950 | Trình tự; phân biệt ý nghĩa phản công/tiến công; chọn chứng cứ |
| Năm 1954: chiến trường và bàn đàm phán | Bài 7 và 13; Điện Biên Phủ và Giơ-ne-vơ | Trình tự; đối chiếu hai nguồn; phân biệt quan hệ lịch sử với việc chỉ xảy ra trước/sau |

Có sáu mốc, bảy trích đoạn SGK. Danh mục bộ lọc đủ 17 bài nhưng hiện chỉ hai nhiệm
vụ trên đã được biên soạn. Những bài chưa có nhiệm vụ hiển thị rõ trạng thái này.

## Cách sử dụng

**Giáo viên** đăng nhập và chọn **Bản đồ nhiệm vụ 12**:

1. Chọn **Xem và kiểm tra** để làm thử một lượt. Lượt này mang nhãn xem trước,
   không được tính vào số nhiệm vụ học sinh hoàn thành hay kết quả nghiên cứu.
2. Chọn **Mở phần kiểm tra** để đối chiếu trình tự tham chiếu, tọa độ đại diện,
   nguồn SGK và hình trang gốc. Phần này có mã hash của đúng nội dung đang duyệt.
3. Xác nhận đã đối chiếu rồi chọn **Mở cho học sinh**. Có thể giữ/tạm dừng về bản nháp.
4. Vào **Bài giải thích cần nhận xét** để chấm phần tự luận và gửi phản hồi.

**Học sinh** chỉ bắt đầu được nhiệm vụ đã mở:

1. Dùng thanh thời gian để lọc các mốc; chọn lớp quân sự, ngoại giao hoặc chính trị.
   Điểm cùng địa điểm được nhóm. Danh sách mốc cung cấp thao tác tương đương bằng
   bàn phím, không yêu cầu kéo thả hoặc bấm đúng vị trí nhỏ trên bản đồ.
2. Dùng nút **Lên / Xuống** để sắp xếp các thẻ sự kiện từ sớm đến muộn.
3. Mở và đọc các nguồn, chọn đúng hai chứng cứ phù hợp với câu hỏi điều tra.
4. Chọn nhận định rồi viết giải thích. Lưu tạm để tiếp tục sau hoặc nộp nhiệm vụ.
5. Xem phản hồi từng loại lỗi. Học lại nhiệm vụ nếu cần; một lượt luyện lại tốt
   sẽ xóa gợi ý lỗi cũ của cùng nhiệm vụ khỏi phần khuyến nghị.

Nhật ký giữ các lượt chưa nộp và đã nộp; có nút tiếp tục/xem lại phản hồi. Thoát khi
có thay đổi chưa lưu sẽ có xác nhận. Kết quả lưu theo tài khoản và vẫn còn sau khi
khởi động lại server. Mỗi lượt có revision để tránh ghi đè dữ liệu đã thay đổi.

## Chấm và phản hồi

- Trình tự: 0–2 điểm; tính từ các cặp mốc liên tiếp đúng thứ tự trong tham chiếu.
- Chứng cứ: 0 hoặc 2 điểm; phải chọn đủ và đúng hai nguồn theo yêu cầu.
- Quan hệ: 0 hoặc 2 điểm; lựa chọn nhận định phù hợp với chứng cứ.
- Giải thích: giáo viên chấm riêng 0–2 điểm về lập luận/chính xác và 0–2 điểm về
  sử dụng nguồn, kèm nhận xét bằng chữ. Tổng điểm chỉ có sau bước này.

Hệ thống không dùng AI, số phút xem video, việc mở marker hay số lượt xem để
quyết định học sinh hiểu bài. Sáu điểm tự động không phải điểm tổng kết 10 điểm.
Nộp lặp cùng dữ liệu không tạo thêm lượt; không đổi đáp án một lượt sau khi đã nộp.

## Nguồn và trạng thái duyệt

Nội dung lấy từ SGK Lịch sử 12, bộ Kết nối tri thức với cuộc sống, bản mẫu 10/2023:
trang sách 39, 40, 41, 42 và 79 (trang PDF tương ứng +2). Các trích đoạn OCR đã
được so lại với ảnh trang để sửa lỗi chép; vẫn là nội dung biên soạn nháp, không
tự mang nhãn giáo viên phê duyệt. Bản OCR gốc và hash trích đoạn được giữ trong pack.

**Mặc định cả hai nhiệm vụ chưa mở bài có lưu kết quả cho học sinh.** Chế độ trải
nghiệm công khai được ghi rõ là bài thử. Việc thay nguồn, tọa độ, đáp án
tham chiếu hoặc nội dung nhiệm vụ làm quyết định mở cũ mất hiệu lực. Phải đối chiếu
lại đúng mã nội dung; lượt học sinh cũ không được nộp dưới nội dung mới. Kết quả cũ
vẫn xem được từ snapshot nguồn tại lúc bắt đầu.

Các tọa độ chỉ là điểm đại diện thành phố/vùng, có ghi chú rõ. Chúng chưa phải
lược đồ chiến dịch, tuyến tiến quân hay ranh giới lịch sử. Bản đồ nền OpenStreetMap
là bản đồ hiện tại, có attribution hiển thị. Không vẽ các mũi tên hành quân hoặc
ranh giới tự suy đoán. Giáo viên cần kiểm tra vị trí khi duyệt nhiệm vụ.

Leaflet 1.9.4 được lưu cục bộ tại `frontend/vendor/leaflet`, có giấy phép BSD.
Bản đồ nền cần mạng để tải tile; nếu chưa tải được nền, các mốc, tọa độ và nguồn
vẫn được cung cấp qua danh sách sự kiện. Không gửi nội dung bài giải thích vào tile request.

## Cấu hình nguồn PDF

Ảnh trang gốc chỉ được mở khi PDF khớp SHA-256 đã khóa trong pack. Có thể cấp bằng:

```powershell
$env:COBRAQ_HISTORY12_PDF='C:\path\history12_kntt_2023_sample.pdf'
```

Ứng dụng còn tìm trong `research/sources/` hoặc bản gốc đã nhập ở `data/documents`.
Không có PDF thì vẫn đọc được trích đoạn; nút ảnh báo rõ chưa có nguồn khớp.
PDF sách và dữ liệu bài làm không đưa vào Git.

## Cấu trúc triển khai

- `research/mission_maps/history12-v1.json`: pack biên soạn và tham chiếu nguồn.
- `backend/app/services/mission_maps.py`: kiểm tra pack, hash duyệt, lưu lượt làm,
  chấm khách quan, phản hồi và tổng hợp tiến độ.
- `backend/app/api/mission_map.py`: API `/api/mission-map`, có phân quyền JWT.
- `frontend/mission_map.js`, `mission_map.css`: danh mục, bản đồ/thanh thời gian,
  chứng cứ, bài làm và màn hình giáo viên.
- `<data_dir>/mission_maps/`: lượt làm, quyết định mở và lịch sử quyết định duyệt.

Giáo viên/quản trị được xem trước, mở nhiệm vụ và nhận xét; học sinh chỉ xem lượt
của mình và không được đọc khóa chấm trước khi nộp. Đây là lưu trữ JSON cho một
worker local hiện tại. Không chạy nhiều worker ghi chung thư mục này; khi triển
khai nhiều máy cần chuyển lớp lưu trữ sang giao dịch SQL.

## Kiểm tra

```powershell
python -m unittest tests.test_mission_maps -v
python -m unittest discover -s tests
python -m unittest tools.tests.test_extraction research.tests.test_pipeline research.tests.test_evaluation
```

27 kiểm thử mới bao gồm quyền API, giới hạn nháp, tính toàn vẹn nguồn, khóa tham
chiếu, lưu/tiếp tục, điểm theo lỗi, nộp lặp, tạm dừng nhiệm vụ, cập nhật nội dung,
chấm giáo viên và khuyến nghị sau luyện lại. Kiểm tra DOM bằng dữ liệu giả xác
nhận trình tự, lựa chọn nguồn, phản hồi, lọc bài và chống chèn HTML trong bài viết.
Kiểm tra HTTP môi trường chính có lượt xem trước được ghi rõ `[KIỂM TRA KỸ THUẬT]`;
không tạo quyết định duyệt hay điểm tự luận giả dưới tên giáo viên.

Kiểm tra trực quan bằng trình duyệt chưa thực hiện vì quyền mở origin 8000 đã
bị từ chối trong phiên trước. Xác nhận hiện tại dựa trên kiểm thử Python, DOM và API;
không tuyên bố đã kiểm tra hình ảnh desktop/mobile hoặc việc tải tile ngoài thực tế.
