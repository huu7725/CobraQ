"""Build the CobraQ product report using the supplied eight-page PDF structure."""
from pathlib import Path
from html import escape
import json

from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.colors import HexColor, white
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import Paragraph, Table, TableStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont


ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "output/pdf/CobraQ_Bao_cao_san_pham.pdf"
LOGO = Path(r"C:\Users\TUF\Desktop\download.png")
manifest = json.loads((ROOT / "artifacts/adapters/history12_lora_v2_1/training_manifest.json").read_text(encoding="utf-8"))
audit = json.loads((ROOT / "research/results/PROMPT_TOKEN_AUDIT_V2_1.json").read_text(encoding="utf-8"))

for name, file in [("TimesVN", "times.ttf"), ("TimesVN-Bold", "timesbd.ttf"),
                   ("TimesVN-Italic", "timesi.ttf"), ("TimesVN-BoldItalic", "timesbi.ttf")]:
    pdfmetrics.registerFont(TTFont(name, str(Path("C:/Windows/Fonts") / file)))
pdfmetrics.registerFontFamily("TimesVN", normal="TimesVN", bold="TimesVN-Bold",
                            italic="TimesVN-Italic", boldItalic="TimesVN-BoldItalic")

W, H = A4
LEFT, RIGHT, BOTTOM = 72, 57, 58
WIDTH = W - LEFT - RIGHT
BLUE = HexColor("#285887")
INK = HexColor("#161b22")
PALE = HexColor("#f0f4f9")
PURPLE = HexColor("#5b21b6")
styles = {
    "body": ParagraphStyle("body", fontName="TimesVN", fontSize=13, leading=18.2,
                           textColor=INK, alignment=TA_JUSTIFY, firstLineIndent=16),
    "plain": ParagraphStyle("plain", fontName="TimesVN", fontSize=13, leading=18.2,
                            textColor=INK, alignment=TA_LEFT),
    "h1": ParagraphStyle("h1", fontName="TimesVN-Bold", fontSize=13.5, leading=19,
                         textColor=BLUE),
    "h2": ParagraphStyle("h2", fontName="TimesVN-Bold", fontSize=13, leading=18,
                         textColor=INK),
    "small": ParagraphStyle("small", fontName="TimesVN", fontSize=10.8, leading=14.2,
                            textColor=INK),
    "caption": ParagraphStyle("caption", fontName="TimesVN-Italic", fontSize=11.2,
                              leading=14.7, alignment=TA_CENTER, textColor=BLUE),
    "box": ParagraphStyle("box", fontName="TimesVN", fontSize=12, leading=16.2,
                          textColor=INK),
    "cell": ParagraphStyle("cell", fontName="TimesVN", fontSize=11.8, leading=15.3,
                           textColor=INK),
    "node": ParagraphStyle("node", fontName="TimesVN", fontSize=12, leading=15.5,
                           textColor=INK, alignment=TA_CENTER),
}


def normalize(text):
    return text.replace("–", "-").replace("—", "-").replace("‑", "-")


class Report:
    def __init__(self):
        OUT.parent.mkdir(parents=True, exist_ok=True)
        self.c = canvas.Canvas(str(OUT), pagesize=A4, pageCompression=1)
        self.c.setTitle("CobraQ - Báo cáo sản phẩm")
        self.c.setAuthor("Nguyễn Hữu Thuận; Đinh Nhật Nam; Các thành viên Team Cobra")
        self.c.setSubject("AI trong học tập: ôn tập và sinh câu hỏi Lịch sử 12; cập nhật 12/09/2026")
        self.page = 0
        self.y = 0
        self.remaining = []

    def new(self):
        if self.page:
            self.remaining.append((self.page, round(self.y - BOTTOM, 1)))
            self.c.showPage()
        self.page += 1
        self.y = H - 65
        if self.page > 1:
            self.c.setFont("TimesVN", 11.5)
            self.c.setFillColor(INK)
            self.c.drawCentredString(W / 2, H - 33, str(self.page))

    def reserve(self, height):
        if self.y - height < BOTTOM:
            raise ValueError(f"Page {self.page} overflows: need {height:.1f}, available {self.y - BOTTOM:.1f}")

    def p(self, text, style="body", after=9):
        para = Paragraph(normalize(text), styles[style])
        _, height = para.wrap(WIDTH, H)
        self.reserve(height + after)
        para.drawOn(self.c, LEFT, self.y - height)
        self.y -= height + after

    def heading(self, text):
        self.p(text, "h1", 10)

    def sub(self, text):
        self.p(text, "h2", 5)

    def box(self, text, after=9):
        para = Paragraph(normalize(text), styles["box"])
        _, h = para.wrap(WIDTH - 24, H)
        self.reserve(h + 20 + after)
        self.c.setFillColor(PALE)
        self.c.setStrokeColor(HexColor("#cad5e3"))
        self.c.roundRect(LEFT, self.y - h - 20, WIDTH, h + 20, 3, stroke=1, fill=1)
        para.drawOn(self.c, LEFT + 12, self.y - h - 10)
        self.y -= h + 20 + after

    def table(self, rows, widths, after=10):
        cells = [[Paragraph(normalize(str(v)), styles["cell"]) for v in row] for row in rows]
        t = Table(cells, colWidths=widths, hAlign="LEFT")
        t.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), PALE),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("GRID", (0, 0), (-1, -1), 0.45, HexColor("#c8d2df")),
            ("LEFTPADDING", (0, 0), (-1, -1), 8),
            ("RIGHTPADDING", (0, 0), (-1, -1), 8),
            ("TOPPADDING", (0, 0), (-1, -1), 7),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 7),
        ]))
        _, h = t.wrap(WIDTH, H)
        self.reserve(h + after)
        t.drawOn(self.c, LEFT, self.y - h)
        self.y -= h + after

    def centered(self, text, y, size=15, leading=None, bold=False, width=430, color=INK):
        style = ParagraphStyle("cover", fontName="TimesVN-Bold" if bold else "TimesVN",
                               fontSize=size, leading=leading or size * 1.28,
                               alignment=TA_CENTER, textColor=color)
        p = Paragraph(normalize(text), style)
        _, h = p.wrap(width, H)
        p.drawOn(self.c, (W - width) / 2, y - h)

    def diagram(self):
        h, gap = 63, 21
        column = (WIDTH - 24) / 2
        top = self.y
        labels = [
            ("1. SGK Lịch sử 12", "OCR, hiệu đính và chia đoạn"),
            ("2. Kho tri thức có nguồn", "Embedding, ChromaDB, metadata"),
            ("3. Truy xuất RAG", "Lọc bài, tìm hybrid, chọn bằng chứng"),
            ("4. TinyLlama + QLoRA", "Sinh câu hỏi theo schema gọn"),
            ("5. Kiểm tra và giáo viên duyệt", "Cấu trúc, dữ kiện, đáp án, trích dẫn"),
            ("6. Đề và phiên luyện tập", "Trắc nghiệm / tự luận, lời giải"),
        ]
        positions = [(LEFT, top), (LEFT + column + 24, top),
                     (LEFT + column + 24, top - h - gap), (LEFT, top - h - gap),
                     (LEFT, top - 2 * (h + gap)), (LEFT + column + 24, top - 2 * (h + gap))]
        self.reserve(3 * h + 2 * gap + 15)
        c = self.c
        for (title, desc), (x, y) in zip(labels, positions):
            c.setFillColor(PALE)
            c.setStrokeColor(BLUE)
            c.setLineWidth(.7)
            c.roundRect(x, y - h, column, h, 4, stroke=1, fill=1)
            p = Paragraph(f"<b>{title}</b><br/>{desc}", styles["node"])
            _, ph = p.wrap(column - 14, h)
            p.drawOn(c, x + 7, y - (h + ph) / 2)
        def arrow(x1, y1, x2, y2):
            c.setStrokeColor(BLUE)
            c.setLineWidth(1)
            c.line(x1, y1, x2, y2)
            if x2 != x1:
                s = 1 if x2 > x1 else -1
                c.line(x2, y2, x2 - s * 5, y2 + 3)
                c.line(x2, y2, x2 - s * 5, y2 - 3)
            else:
                c.line(x2, y2, x2 - 3, y2 + 5)
                c.line(x2, y2, x2 + 3, y2 + 5)
        arrow(LEFT + column, top - h / 2, LEFT + column + 24, top - h / 2)
        arrow(LEFT + column * 1.5 + 24, top - h, LEFT + column * 1.5 + 24, top - h - gap)
        arrow(LEFT + column + 24, top - h - gap - h / 2, LEFT + column, top - h - gap - h / 2)
        arrow(LEFT + column / 2, top - 2 * h - gap, LEFT + column / 2, top - 2 * (h + gap))
        arrow(LEFT + column, top - 2 * (h + gap) - h / 2, LEFT + column + 24, top - 2 * (h + gap) - h / 2)
        self.y -= 3 * h + 2 * gap + 12

    def save(self):
        self.remaining.append((self.page, round(self.y - BOTTOM, 1)))
        self.c.save()
        print(json.dumps({"output": str(OUT), "pages": self.page, "free_space_pt": self.remaining}, ensure_ascii=False))


def build():
    r = Report()
    r.new()
    c = r.c
    c.setStrokeColor(BLUE)
    c.setLineWidth(1.3)
    c.rect(44, 43, W - 88, H - 86)
    c.setStrokeColor(INK)
    c.setLineWidth(.65)
    c.rect(49, 48, W - 98, H - 96)
    # Restrained double-border corner ornament, keeping the reference's formal style.
    for x, y, sx, sy in [(53, 52, 1, 1), (W-53, 52, -1, 1),
                         (53, H-52, 1, -1), (W-53, H-52, -1, -1)]:
        c.line(x, y + 17 * sy, x, y)
        c.line(x, y, x + 17 * sx, y)
        c.setFillColor(BLUE)
        c.circle(x + 5 * sx, y + 5 * sy, 1.5, stroke=0, fill=1)
    r.centered("TRƯỜNG ĐẠI HỌC QUY NHƠN<br/>KHOA CÔNG NGHỆ THÔNG TIN", H-78, 14, bold=True)
    c.drawImage(str(LOGO), (W-112)/2, H-255, 112, 112, mask="auto")
    r.centered('CUỘC THI “GIA LAI YOUTH HACKAITHON 2026”', H-282, 13.3, bold=True, width=466)
    r.centered('“Thanh niên Gia Lai sáng tạo cùng AI -<br/>Chuyển đổi số vì cộng đồng”', H-308, 13.1, width=430)
    r.centered("BÁO CÁO SẢN PHẨM", H-367, 18, bold=True, color=BLUE)
    r.centered("COBRAQ", H-407, 29, bold=True, color=BLUE)
    r.centered("TRỢ LÝ ÔN TẬP VÀ TẠO CÂU HỎI<br/>LỊCH SỬ 12", H-451, 17, bold=True)
    r.centered("Chủ đề: AI trong học tập", H-508, 14, bold=True)
    r.centered("<b>Tác giả:</b><br/>Nguyễn Hữu Thuận<br/>Đinh Nhật Nam<br/>Các thành viên Team Cobra", H-568, 14, 21)
    r.centered("Gia Lai, tháng 9 năm 2026", 98, 14, bold=True)
    r.y = BOTTOM

    r.new()
    r.heading("PHẦN 1. GIỚI THIỆU VẤN ĐỀ")
    r.p("Trong định hướng chuyển đổi số giáo dục, việc khai thác học liệu số cần gắn với chất lượng học tập và khả năng triển khai thực tế. Đối với môn Lịch sử lớp 12, người học phải liên hệ nhiều sự kiện, nhân vật, mốc thời gian và quan hệ nguyên nhân - kết quả. Khi chỉ ghi nhớ các thông tin rời rạc, học sinh dễ nhầm lẫn trình tự sự kiện hoặc chưa giải thích được ý nghĩa lịch sử. Đây là vấn đề thực tiễn được nêu trong bản thuyết minh đề tài của nhóm [1].")
    r.p("Về phía giáo viên, quá trình xây dựng câu hỏi đòi hỏi lựa chọn kiến thức trọng tâm, diễn đạt câu dẫn rõ ràng, thiết kế phương án nhiễu hợp lý và kiểm tra đáp án theo sách giáo khoa. Ngân hàng câu hỏi tĩnh khó đáp ứng linh hoạt mọi mục tiêu ôn tập. Vì vậy, nhu cầu hỗ trợ ra câu hỏi và đối chiếu nguồn là đáng quan tâm; mức tiết kiệm thời gian cụ thể vẫn cần được đo bằng khảo sát và thực nghiệm.")
    r.p("Mô hình ngôn ngữ có thể tạo văn bản tự nhiên nhưng cũng có thể sinh sai niên đại, gán nhầm nhân vật hoặc đưa ra lời giải không được nguồn hỗ trợ. Các mô hình lớn còn đặt ra yêu cầu về bộ nhớ, thời gian suy luận và chi phí vận hành. Với dữ liệu Lịch sử, một câu hỏi trôi chảy nhưng sai dữ kiện có thể dẫn người học đến nhận thức không chính xác.")
    r.heading("PHẦN 2. Ý TƯỞNG GIẢI QUYẾT")
    r.p("CobraQ được đề xuất như một hệ thống hỗ trợ ôn tập và xây dựng câu hỏi, kết hợp mô hình ngôn ngữ nhỏ (SLM), sinh tăng cường truy xuất (RAG) và tinh chỉnh hiệu quả tham số (PEFT). Tri thức được truy xuất từ học liệu đã hiệu đính; mô hình tạo câu hỏi có cấu trúc; giáo viên đối chiếu và quyết định nội dung được sử dụng. Cách tiếp cận này hướng tới giảm rủi ro ảo giác và hạ yêu cầu tài nguyên.")
    r.p("Phạm vi triển khai hiện tại là SGK Lịch sử 12, bộ Kết nối tri thức với cuộc sống, gồm 6 chủ đề và 17 bài. Sản phẩm ưu tiên câu hỏi trắc nghiệm bốn lựa chọn và tự luận. Mục tiêu nghiên cứu là xây dựng kho tri thức có nguồn, hoàn thiện Auto-Exam Pipeline và đánh giá riêng đóng góp của RAG, LoRA đối với chất lượng câu hỏi và tài nguyên sử dụng. Trợ lý hỏi đáp và các dạng bài khác là hướng phát triển trong đề cương [1, 2].")

    r.new()
    r.sub("2.1. Luồng xử lý của hệ thống")
    r.p("Hệ thống tổ chức thành hai giai đoạn: chuẩn bị kho tri thức và khai thác câu hỏi. Mỗi đoạn SGK được giữ thông tin bài, chủ đề, trang và mã nguồn để phục vụ tra cứu, đối chiếu và truy vết.")
    r.diagram()
    r.p("Hình 1. Kiến trúc Auto-Exam Pipeline của CobraQ.", "caption", 12)
    r.p("Đầu ra của mô hình chỉ gồm loại câu, nội dung, phương án, đáp án và lời giải. Máy chủ gắn mã câu hỏi, bài học, cấu hình thực nghiệm và trích dẫn. Kiểm tra cấu trúc giúp phát hiện lỗi JSON, sai loại câu hoặc phương án trùng; kiểm tra ngữ nghĩa vẫn cần người có chuyên môn. Việc gắn đúng nguồn chỉ chứng minh xuất xứ, chưa đủ khẳng định mọi nhận định trong câu hỏi đều được nguồn hỗ trợ.")
    r.sub("2.2. Trải nghiệm theo vai trò")
    r.p("<b>Học sinh:</b> chọn bài và số lượng câu để luyện tập, nộp bài trắc nghiệm, xem đáp án, lời giải và tra cứu SGK. Với tự luận, nội dung tham khảo hỗ trợ tự đối chiếu; quyết định đánh giá chuyên môn thuộc về giáo viên.")
    r.p("<b>Giáo viên:</b> sử dụng các chức năng quản lý đề, học liệu, nhóm học tập và kết quả; đồng thời tham gia quy trình duyệt dữ kiện, câu hỏi và nguồn truy xuất. <b>Quản trị viên:</b> quản lý người dùng, thống kê và nhật ký hệ thống. Giao diện tích hợp trong một sản phẩm và điều chỉnh menu theo vai trò.")

    r.new()
    r.heading("PHẦN 3. CÔNG CỤ AI SỬ DỤNG")
    r.sub("3.1. TinyLlama và tinh chỉnh QLoRA")
    r.p("CobraQ chọn TinyLlama-1.1B-Chat-v1.0 làm mô hình nền cho hướng nghiên cứu SLM. QLoRA kết hợp mô hình nền lượng tử hóa 4-bit với các ma trận LoRA có thể huấn luyện. Với trọng số W được giữ cố định, phần cập nhật được biểu diễn dưới dạng ΔW = (α/r)BA, trong đó r nhỏ hơn kích thước của W. Việc chỉ học các tham số bổ sung giúp giảm bộ nhớ huấn luyện so với cập nhật toàn bộ mô hình.")
    r.p("Adapter v2.1 dùng r = 16, α = 32, dropout = 0,05 và tác động lên các phép chiếu q, k, v, o của attention. Cấu hình này đã huấn luyện trên GPU laptop 4 GB. Mức giảm độ trễ suy luận và chất lượng câu hỏi phải được đo riêng; mô hình nhỏ hoặc loss thấp không tự bảo đảm dữ kiện chính xác [3].")
    r.sub("3.2. Embedding đa ngôn ngữ và RAG")
    r.p("Mô hình intfloat/multilingual-e5-small mã hóa đoạn SGK thành vector và lưu trong ChromaDB. Truy xuất hybrid kết hợp tìm kiếm từ khóa với độ tương đồng ngữ nghĩa, hợp nhất thứ hạng bằng RRF và hỗ trợ lọc bài học. Cơ chế này bổ sung bằng chứng cho mô hình, nhưng hiệu quả còn phụ thuộc chất lượng OCR, cách chia đoạn và mức phù hợp của nguồn được tìm thấy.")
    r.sub("3.3. Công cụ xây dựng và kiểm chứng")
    r.table([
        ["<b>Thành phần</b>", "<b>Vai trò trong sản phẩm</b>"],
        ["Tesseract OCR", "Chuyển ảnh trang SGK thành văn bản, lưu thông tin phục vụ hiệu đính."],
        ["PyTorch, Transformers,<br/>PEFT, bitsandbytes", "Nạp TinyLlama, lượng tử hóa, huấn luyện và lưu adapter có cấu hình truy vết."],
        ["FastAPI và giao diện web", "Cung cấp API, luồng luyện tập, tra cứu và chức năng theo vai trò."],
        ["Trợ lý AI hỗ trợ phát triển", "Hỗ trợ phân tích yêu cầu, soạn mã và tài liệu; kết quả cần được nhóm kiểm tra."],
    ], [156, WIDTH-156])
    r.p("LoRA/QLoRA là phương pháp đã triển khai. IA3 và ReFT được xem xét ở mức hướng so sánh, chưa có kết quả huấn luyện hoặc đối chứng tương ứng trong báo cáo này.", "small")

    r.new()
    r.heading("PHẦN 4. QUY TRÌNH THỰC HIỆN")
    steps = [
        ("Bước 1. Xác định yêu cầu và phạm vi", "Khóa nội dung Lịch sử 12 với 17 bài; xác định các nhóm người dùng và hai loại câu ưu tiên. Tách mục tiêu nghiên cứu sinh câu hỏi khỏi chức năng luyện tập bằng ngân hàng có sẵn."),
        ("Bước 2. Số hóa và hiệu đính học liệu", "OCR 106 trang nội dung; rà soát dữ kiện qua workbook có nguồn đối chiếu. Lưu dấu vết hiệu đính và thông tin kiểm tra tính toàn vẹn của dữ liệu."),
        ("Bước 3. Xây dựng kho truy xuất", "Tạo 197 đoạn có metadata, embedding và chỉ mục ChromaDB. Hỗ trợ lọc bài và tìm kiếm hybrid; ưu tiên đoạn có nội dung đủ làm bằng chứng thay vì chỉ có tiêu đề."),
        ("Bước 4. Chuẩn bị nhãn và chia dữ liệu", "Từ 600 câu đã được duyệt, tách 480 train, 60 validation và 60 test theo nhóm đoạn nguồn. Giữ nội dung chuyên môn; rút gọn cấu trúc đầu ra để mô hình tập trung học tác vụ."),
        ("Bước 5. Thống nhất prompt và huấn luyện", "Dùng prompt builder chung cho train, verify và runtime, áp dụng chat template của TinyLlama. Audit 540 mẫu trước khi huấn luyện v2.1 với context 2.048 token, 3 epoch và seed 42."),
        ("Bước 6. Tích hợp API và giao diện", "Kết nối luồng luyện SGK, tra cứu và các chức năng quản lý vào giao diện hiện có. Tách đáp án khỏi phản hồi khởi tạo bài luyện; trả đáp án và nguồn sau khi nộp."),
        ("Bước 7. Kiểm tra độc lập và nguồn chuẩn", "Chuẩn bị 60 câu để giáo viên thứ hai đối chiếu mà không xem điểm của người trước; đồng thời lập 51 truy vấn retrieval gold. Các trường phê duyệt chờ giáo viên điền."),
        ("Bước 8. Kiểm chứng và chạy pilot", "Kiểm tra adapter cuối trên nhiều mẫu chưa huấn luyện; lưu cả đầu ra lỗi, độ trễ, VRAM và cắt token. Khóa phiên bản prompt, mô hình và evaluator trước khi chạy pilot C0-C3."),
        ("Bước 9. Thực nghiệm có điều kiện", "Chỉ chạy 40 câu/cấu hình khi pilot mới đạt cổng chất lượng. Ba giáo viên chấm mù; dữ liệu học sinh dùng để phân tích độ khó, độ phân hóa và trải nghiệm sử dụng."),
        ("Bước 10. Hoàn thiện và quản lý phiên bản", "Sửa câu hỏi sau xác nhận của giáo viên, lưu phiên bản cùng lịch sử thay đổi. Cập nhật mô hình hoặc prompt phải kiểm chứng lại; không sử dụng báo cáo GO đã lỗi thời."),
    ]
    for title, body in steps:
        r.p(f"<b>{title}.</b> {body}", "plain", 9)

    r.new()
    r.heading("PHẦN 5. PROMPT TIÊU BIỂU")
    r.p("Các mẫu dưới đây diễn đạt mục đích và quy tắc sử dụng prompt của CobraQ; là bản trình bày phục vụ báo cáo, không phải bản ghi nguyên văn của mọi lần chạy. Khi triển khai, nội dung được chuẩn hóa bởi prompt builder và chat template tương ứng.")
    prompts = [
        ("5.1. Tạo câu hỏi trắc nghiệm có nguồn", "Dựa trên đoạn SGK được cung cấp, tạo một câu trắc nghiệm Lịch sử 12. Có đúng bốn phương án khác nhau, một đáp án đúng và lời giải dựa vào dữ kiện trong đoạn. Không bổ sung sự kiện ngoài nguồn."),
        ("5.2. Tách yêu cầu tự luận", "Tạo một câu tự luận phù hợp nội dung bài học. Đưa ra đáp án tham khảo và giải thích đủ ý; không viết lời nhắc yêu cầu giáo viên hoàn thiện đáp án. Tuân thủ schema tự luận, không tạo bốn phương án trắc nghiệm."),
        ("5.3. Kiểm soát cấu trúc đầu ra", "Chỉ trả đối tượng JSON có danh sách questions. Mỗi câu gồm question_type, stem, choices, correct_answer, explanation. Không sinh question_id, thông tin bài học, citation hoặc tên cấu hình; các trường này do hệ thống quản lý."),
        ("5.4. Hỗ trợ truy xuất và đối chiếu", "Với truy vấn về sự kiện, tìm đoạn SGK có thông tin trực tiếp giúp trả lời. Giữ mã đoạn và trang sách. Nếu đoạn chỉ là tiêu đề hoặc mục tiêu bài học, đánh dấu để rà soát thêm thay vì coi đó là bằng chứng đầy đủ."),
        ("5.5. Rà soát chất lượng câu hỏi", "Đối chiếu câu hỏi, đáp án và lời giải với đoạn nguồn. Chỉ rõ nhận định thiếu bằng chứng, phương án trùng hoặc lỗi diễn đạt. Đề xuất nội dung cần giáo viên xem xét, không tự cấp nhãn phê duyệt chuyên môn."),
        ("5.6. Hỗ trợ kiểm thử hệ thống", "Kiểm tra các luồng tạo bài, nộp bài và tra cứu SGK. Báo cáo đầu vào, kết quả thực tế và lỗi có thể tái hiện. Không suy diễn tính đúng lịch sử từ việc API phản hồi thành công hoặc JSON hợp lệ."),
    ]
    for title, body in prompts:
        r.sub(title)
        r.box(body, 10)

    r.new()
    r.heading("PHẦN 6. KẾT QUẢ ĐẠT ĐƯỢC")
    r.p("Tại thời điểm lập báo cáo (12/09/2026), CobraQ đã hình thành nguyên mẫu tích hợp dữ liệu, mô hình và giao diện. Các số liệu sau phản ánh dữ liệu và nhật ký kỹ thuật hiện có; chưa phải kết quả chứng minh hiệu quả sư phạm [2-4].")
    max_token = audit["splits"]["combined"]["total"]["max"]
    last_loss = manifest["eval_history"][-1]["eval_loss"]
    r.table([
        ["<b>Hạng mục</b>", "<b>Kết quả ghi nhận</b>"],
        ["Phạm vi học liệu", "6 chủ đề, 17 bài; 106 trang OCR; 197 đoạn có thông tin nguồn."],
        ["Dữ liệu câu hỏi", "600 nhãn đã duyệt: 420 trắc nghiệm, 180 tự luận; chia 480/60/60 mẫu."],
        ["Audit prompt v2.1", f"540 mẫu; dài nhất {max_token:,}/2.048 token; không vượt giới hạn, không cắt mẫu.".replace("1,892", "1.892")],
        ["Huấn luyện v2.1", f"{manifest['global_step']}/180 bước, 3 epoch; eval_loss cuối {last_loss:.4f}.".replace("0.2268", "0,2268")],
        ["Bộ nhớ huấn luyện", "Peak PyTorch VRAM 3.278,08 MiB trên RTX 3050 Ti Laptop GPU; chưa phải tổng bộ nhớ tiến trình."],
        ["Dùng thử tại máy local", "Trang web và health hoạt động; API tạo/nộp bài 5 câu thành công; tra cứu thử trả 5 đoạn SGK."],
    ], [147, WIDTH-147])
    r.sub("6.1. Kết quả pilot trước và giới hạn diễn giải")
    r.table([
        ["<b>Cấu hình</b>", "<b>Thiết lập</b>", "<b>Đạt schema (pilot v2)</b>"],
        ["C0", "SLM gốc", "0/10"],
        ["C1", "SLM + RAG", "0/10"],
        ["C2", "SLM + LoRA", "8/10"],
        ["C3", "SLM + RAG + LoRA", "0/10"],
    ], [73, 200, WIDTH-273])
    r.p("Pilot v2 ngày 18/08/2026 có kết luận NO-GO. Bảng trên không phải kết quả của v2.1. Adapter v2.1 đã huấn luyện xong nhưng chưa có báo cáo batch/pilot xác nhận trong hồ sơ hiện tại; loss giảm không đồng nghĩa tỷ lệ câu hỏi đúng tăng. Vì vậy, chưa công bố thực nghiệm chính thức 160 câu hoặc khẳng định C3 tốt hơn các cấu hình còn lại.")
    r.p("Hạn chế dữ liệu: 600 nhãn do một người duyệt, cùng điểm 5/5; 60 câu kiểm tra độc lập và 51 truy vấn nguồn chuẩn đang chờ xác nhận. Chưa có đánh giá chấm mù của ba giáo viên hoặc kết quả thực nghiệm học sinh.", "small", 0)

    r.new()
    r.heading("PHẦN 7. KHẢ NĂNG ỨNG DỤNG")
    r.sub("7.1. Hỗ trợ tự học Lịch sử 12")
    r.p("CobraQ cho phép học sinh lựa chọn nội dung luyện tập, nhận phản hồi sau khi làm bài và đối chiếu SGK. Bản dùng thử hiện khai thác 60 câu có sẵn để trình diễn quy trình học tập. Các câu đã được công khai trong ứng dụng không nên tiếp tục được coi là bộ kiểm tra mù của thực nghiệm với chính nhóm người đã tiếp xúc với chúng.")
    r.sub("7.2. Hỗ trợ giáo viên xây dựng học liệu")
    r.p("Kho tri thức có nguồn và quy trình duyệt giúp giáo viên rà soát câu hỏi có hệ thống, phát hiện nhóm lỗi lặp và lưu lịch sử chỉnh sửa. Mục tiêu là giảm thao tác thủ công khi chuẩn bị đề; hiệu quả tiết kiệm thời gian và chất lượng phương án nhiễu cần được xác nhận qua đánh giá độc lập trước khi sử dụng cho kiểm tra chính thức.")
    r.sub("7.3. Triển khai với nguồn lực giới hạn")
    r.p("Kết quả huấn luyện trên GPU laptop 4 GB cho thấy khả năng thực hiện quy trình QLoRA trong điều kiện phần cứng của nhóm. Luồng luyện câu có sẵn và tra cứu có thể dùng để trình diễn mà không chạy sinh câu hỏi mới. Khả năng phục vụ đồng thời, độ trễ khi sinh và tổng chi phí vận hành cần được kiểm thử trước khi triển khai ở quy mô lớp học.")
    r.sub("7.4. Lộ trình hoàn thiện")
    r.p("Ưu tiên tiếp theo là kiểm chứng adapter v2.1, hoàn tất nguồn chuẩn retrieval và duyệt độc lập. Sau pilot đạt yêu cầu, nhóm mới chạy đối chứng C0-C3, tổ chức chấm mù và khảo sát học sinh. Dữ liệu trả lời thực tế sẽ hỗ trợ tính độ khó, độ phân hóa và phân tích phương án nhiễu; đánh giá chuyên gia tập trung vào tính đúng, rõ ràng và phù hợp chương trình.")
    r.p("Về lâu dài, hệ thống có thể mở rộng học liệu, dạng bài và trợ lý hỏi đáp theo RAG như định hướng trong đề cương. Các cải tiến cần duy trì quy trình đối chiếu nguồn, quản lý phiên bản và quyền quyết định chuyên môn của giáo viên; chưa xem sinh câu hỏi tự động là thay thế hoàn toàn hoạt động đánh giá của nhà trường.")
    r.sub("Nguồn nội dung và số liệu")
    r.p("[1] Nhóm đề tài, <i>Thuyết minh đề tài NCKH new (2)</i>, bản PDF do nhóm cung cấp; mục 8-12 về vấn đề, mục tiêu và phương pháp.<br/>[2] Hồ sơ CobraQ: <i>research/CURRENT_STATUS.md</i>, cập nhật 11/09/2026; các bộ dữ liệu và hàng đợi giáo viên duyệt.<br/>[3] <i>artifacts/adapters/history12_lora_v2_1/training_manifest.json</i>; <i>research/results/PROMPT_TOKEN_AUDIT_V2_1.json</i>.<br/>[4] <i>research/results/PILOT_V2_2026-08-18.md</i>; kiểm tra web/API local ngày 12/09/2026.<br/><i>Bố cục bảy phần và phong cách trình bày tham khảo mẫu “Báo cáo sản phẩm - CheatDetect AI”; nội dung được biên soạn cho CobraQ.</i>", "small", 0)
    r.save()


if __name__ == "__main__":
    build()
