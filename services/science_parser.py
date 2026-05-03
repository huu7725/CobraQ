"""
Science Parser — Bộ thuật toán xử lý công thức & ký hiệu cho các môn Tự Nhiên.
Hỗ trợ: Toán học, Vật lý, Hóa học, Sinh học.

Các thuật toán chính:
1. Phát hiện môn học (subject detection)
2. Normalize công thức hóa học (chemical formula parsing)
3. Xử lý đơn vị vật lý (unit normalization)
4. Chuyển đổi subscript/superscript (ASCII ↔ Unicode)
5. Cải thiện garbled detection cho ký hiệu khoa học
6. Enrich fields chuyên biệt STEM
"""

import re
from typing import Optional, Dict, List, Tuple

# ══════════════════════════════════════════
#  BẢNG ÁNH XẠ SUBSCRIPT / SUPERSCRIPT
# ══════════════════════════════════════════

# Chữ số subscript Unicode
_SUB_DIGIT = str.maketrans("0123456789", "₀₁₂₃₄₅₆₇₈₉")
# Chữ cái subscript Unicode
_SUB_LETTER = str.maketrans("aeioruvxhklmnpstw", "ₐₑᵢₒᵣᵤᵥₓₕₖₗₘₙₚₛₜ𝓌")
# Chữ số superscript Unicode
_SUP_DIGIT = str.maketrans("0123456789", "⁰¹²³⁴⁵⁶⁷⁸⁹")
# Một số superscript chữ cái thường
_SUP_LETTER = str.maketrans("+-=()n", "⁺⁻⁼⁽⁾ⁿ")

# Bảng gốc Latin cho subscript (hóa học): H2O → H₂O
_ASCII_SUB_PATTERN = re.compile(
    r"(?<![a-zA-Z])"  # không theo sau chữ cái
    r"([A-Z])"         # ký tự gốc
    r"(\d+)"            # chữ số subscript
    r"(?![a-zA-Z])"     # không đứng trước chữ cái
)
# Phân số common: 1/2, 3/4 → ½, ¾
_FRAC_MAP = {
    "1/2": "½", "1/3": "⅓", "2/3": "⅔", "1/4": "¼", "3/4": "¾",
    "1/5": "⅕", "2/5": "⅖", "3/5": "⅗", "4/5": "⅘",
    "1/6": "⅙", "5/6": "⅚", "1/7": "⅐", "1/8": "⅛", "3/8": "⅜",
    "5/8": "⅝", "7/8": "⅞", "1/9": "⅑", "1/10": "⅒",
}

# ══════════════════════════════════════════
#  THUẬT TOÁN 1: PHÁT HIỆN MÔN HỌC
# ══════════════════════════════════════════

# Keywords cho từng môn — phân theo mức độ đặc trưng
_SUBJECT_KEYWORDS: Dict[str, Dict] = {
    "math": {
        "high": [
            "phương trình", "bất phương trình", "hệ phương trình",
            "tích phân", "đạo hàm", "vi phân", "giới hạn", "lim",
            "ma trận", "định thức", "vec-tơ", "vectơ", "vector",
            "số phức", "đa thức", "tam thức", "logarit", "log",
            "sin", "cos", "tan", "cot", "csc", "sec", "arcsin", "arccos",
            "hàm số", "đồ thị", "parabol", "elip", "hyperbol",
            "chu vi", "diện tích", "thể tích", "bán kính", "đường kính",
            "góc", "tam giác", "tứ giác", "đường tròn", "hình tròn",
            "cấp số", "nhị thức", "hoán vị", "chỉnh hợp", "tổ hợp",
            "xác suất", "kỳ vọng", "phương sai", "trung vị", "trung bình",
            "tọa độ", "phép biến hình", "đối xứng", "đồng dư", "mod",
            "dãy số", "công bịnh", "sqrt", "frac", "sum", "prod",
            "nghiệm", "delta", "biệt thức",
        ],
        "medium": [
            "x²", "x³", "xⁿ", "y²", "√", "∫", "∑", "π", "∞", "≠", "≤", "≥",
            "∈", "∉", "⊂", "⊃", "∪", "∩", "∅", "∀", "∃", "∂", "∇",
            "AB²", "A²+B²", "a²", "b²", "c²", "log₂", "ln", "lg",
        ],
        "symbols": ["√", "∫", "∑", "∏", "π", "∞", "∂", "∇", "∈", "∉", "⊂", "⊃", "⊆", "⊇",
                    "∪", "∩", "∅", "∀", "∃", "≠", "≤", "≥", "≈", "≡", "≡"],
    },
    "physics": {
        "high": [
            "vận tốc", "gia tốc", "quãng đường", "thời gian",
            "lực", "khối lượng", "trọng lượng", "áp suất", "nhiệt độ",
            "công suất", "năng lượng", "cơ năng", "động năng", "thế năng",
            "điện tích", "điện trường", "từ trường", "dòng điện", "hiệu điện thế",
            "điện trở", "tụ điện", "cuộn cảm", "cảm ứng", "từ thông",
            "bước sóng", "tần số", "chu kỳ", "biên độ", "pha",
            "laze", "laser", "photon", "quang điện", "hiệu ứng", "electron",
            "nguyên tử", "proton", "notron", "hạt nhân", "phóng xạ",
            "nhiệt học", "đẳng quá trình", "đẳng nhiệt", "đoạn nhiệt",
            "con lắc", "lò xo", "dao động", "sóng cơ", "sóng điện từ",
            "chiết suất", "giao thoa", "nhiễu xạ", "lưỡng tính", "cực đại",
            "hiệu suất", "ròng rọc", "đòn bẩy", "mặt phẳng nghiêng",
            "momen", "ngẫu lực", "cân bằng", "chuyển động", "quán tính",
            "năng lượng", "bảo toàn", "công", "công cơ học",
            "nhiệt lượng", "nhiệt dung", "nhiệt hóa", "sự bay hơi", "ngưng tụ",
            "mật độ", "khối lượng riêng", "trọng lượng riêng",
            "lực căng", "lực đàn hồi", "lực ma sát", "lực hấp dẫn",
            "định luật", "niuton", "joule", "watt", "pascal", "ohm", "ampere",
            "tesla", "weber", "henry", "farad", "volt", "coulomb",
            "keV", "MeV", "GeV", "eV", "kg", "m/s", "N", "J", "W", "Pa",
        ],
        "medium": [
            "m/s", "kg", "N", "J", "W", "Pa", "Hz", "Ω", "V", "A", "T", "Wb",
            "F", "H", "C", "km/h", "km/s", "cm/s", "mm", "cm", "m", "km",
            "g", "mg", "s", "min", "h", "K", "°C", "°F",
            "λ", "f", "T", "E", "U", "K", "P", "V", "I", "R", "Q", "q",
            "v₀", "v", "a", "s", "t", "F", "m", "W", "P", "Q", "η",
        ],
        "symbols": ["→", "↔", "⟶", "⇌", "↑", "↓", "≈", "≡", "∝", "ω", "φ", "λ", "ν", "c₀"],
    },
    "chemistry": {
        "high": [
            "nguyên tố", "nguyên tử", "phân tử", "ion", "cation", "anion",
            "electron", "proton", "notron", "hạt nhân", "lớp electron", "phân lớp",
            "orbital", "phản ứng", "phương trình phản ứng", "cân bằng",
            "axit", "bazơ", "muối", "oxit", "hidroxit", "axit-bazơ",
            "pH", "nồng độ", "nồng độ mol", "nồng độ đương lượng",
            " dung dịch", "chất tan", "dung môi", "kết tủa", "kết tủa",
            "phản ứng trung hòa", "phản ứng oxi hóa-khử", "trao đổi",
            "cộng hóa trị", "ion chất", "liên kết ion", "liên kết cộng hóa trị",
            "hóa trị", "số oxi hóa", "số oxy hóa",
            "hidro", "oxi", "nitơ", "cacbon", "lưu huỳnh", "photpho",
            "kim loại", "phi kim", "khí hiếm", "nhóm halogen",
            "công thức phân tử", "công thức cấu tạo", "đồng phân", "đồng đẳng",
            "ankyl", "vinyl", "phenyl", "metyl", "etyl", "propyl", "butyl",
            "hiđrocacbon", "ankan", "anken", "ankin", "aren", "benzen", "toluen",
            "rượu", "ancol", "phenol", "andehit", "xeton", "axit", "este",
            "cacboxyl", "amin", "amino", "gluxit", "protein", "lipit", "polime",
            "đipeptit", "tripeptit", "polipeptit", "monome", "polime",
            "enzy", "xúc tác", "chất kích thích", "chất ức chế",
            "tốc độ phản ứng", "cân bằng hóa học", "chiều phản ứng",
            "nhiệt phản ứng", "nhiệt tạo thành", "năng lượng liên kết",
            "chu kỳ", "nhóm", "bảng tuần hoàn", "đồng vị", "iso",
            "Cr", "Mn", "Fe", "Cu", "Zn", "Ag", "Au", "Pb", "Sn", "Na", "K",
            "Ca", "Mg", "Al", "Ba", "Hg", "H₂SO₄", "HCl", "HNO₃", "NaOH",
            "KOH", "Ca(OH)₂", "NaCl", "CuSO₄", "FeCl₃", "NH₄", "SO₄", "NO₃",
            "CO₃", "PO₄", "Cl", "Br", "I",
        ],
        "medium": [
            "H2O", "CO2", "O2", "N2", "H2", "Cl2", "NaCl", "HCl", "H2SO4",
            "NaOH", "KOH", "CaO", "MgO", "Fe2O3", "Al2O3", "CuO", "ZnO",
            "n+", "n-", "e-", "p+", "pH", "pOH", "Ka", "Kb", "Ksp", "Kc", "Kp", "Kn",
        ],
        "symbols": ["→", "⇌", "↑", "↓", "↔", "≡", "⟶", "⊕", "⊖"],
    },
    "biology": {
        "high": [
            "tế bào", "nhân tế bào", "tế bào động vật", "tế bào thực vật",
            "màng sinh chất", "nhân", " ti thể", "lục lạp", "riboxom",
            "ADN", "RNA", "NST", "nhiễm sắc thể", "gen", "ADN",
            "ADN polymerase", "ARN polymerase", "sao chép", "phiên mã", "dịch mã",
            "mã di truyền", "bộ ba mã", "codon", "anticodon",
            "đột biến", "biến dị", "chọn lọc", "tiến hóa", "chọn lọc tự nhiên",
            "quần thể", "quần xã", "hệ sinh thái", "chuỗi thức ăn", "lưới thức ăn",
            "trao đổi chất", "hô hấp", "quang hợp", "hô hấp tế bào",
            "ATP", "ADP", "NADH", "NADPH", "FADH2",
            "men", "enzym", "xúc tác sinh học", "coenzym", "vitamin",
            "protein", "lipit", "glucid", "cacbohydrat", "đường", "chất béo",
            "axit amin", "peptit", "liên kết peptit", "cấu trúc bậc 1", "bậc 2", "bậc 3", "bậc 4",
            "di truyền", " Mendel", "kiểu gen", "kiểu hình", "alen", "lặn", "trội",
            "giao phối", "lai", "lai phân tích", "lai thuần", "phép lai",
            "bệnh di truyền", "hội chứng", "nhiễm sắc", "đảo đoạn", "chuyển đoạn",
            "virus", "vi khuẩn", "vi sinh vật", "nấm", "nguyên sinh",
            "mô", "mô bì", "mô cơ", "mô thần kinh", "mô mạch",
            "hệ thần kinh", "hệ tuần hoàn", "hệ hô hấp", "hệ tiêu hóa",
            "hệ bài tiết", "hệ sinh sản", "hệ nội tiết", "hormone",
            "miễn dịch", "kháng nguyên", "kháng thể", "vaccine", "sốt xuất huyết",
            "sinh sản", "sinh trưởng", "phát triển", "giới tính", "thụ tinh",
            "phôi", "phôi thai", "noãn", "tinh trùng", "hợp tử",
            "quang hợp", "lục lạp", "diệp lục", "carotenoid", "sắc tố",
            "trao đổi khí", "khuếch tán", "thẩm thấu", "vận chuyển chủ động",
        ],
        "medium": [
            "ATP", "ADP", "NAD", "NADP", "FAD", "CoA", "DNA", "RNA", "mRNA", "tRNA", "rRNA",
            "AA", "ATP", "C₆H₁₂O₆", "C₆H₁₂O₆", "CO₂", "H₂O", "O₂", "CO₂",
        ],
        "symbols": ["→", "⇌", "↔", "↑", "↓"],
    },
}


def detect_subject(text: str) -> Tuple[str, float, Dict]:
    """
    Thuật toán phát hiện môn học từ nội dung câu hỏi.

    Args:
        text: Nội dung câu hỏi (question + choices gộp)

    Returns:
        Tuple[str, float, Dict]: (môn_học, confidence, chi_tiết)
    """
    t = (text or "").strip()
    if not t:
        return "unknown", 0.0, {}

    t_lower = t.lower()

    scores: Dict[str, float] = {
        "math": 0.0,
        "physics": 0.0,
        "chemistry": 0.0,
        "biology": 0.0,
    }

    details: Dict[str, Dict] = {
        "math": {"high_hits": 0, "medium_hits": 0, "symbol_hits": 0},
        "physics": {"high_hits": 0, "medium_hits": 0, "symbol_hits": 0},
        "chemistry": {"high_hits": 0, "medium_hits": 0, "symbol_hits": 0},
        "biology": {"high_hits": 0, "medium_hits": 0, "symbol_hits": 0},
    }

    for subj, kw_data in _SUBJECT_KEYWORDS.items():
        for kw in kw_data.get("high", []):
            # đếm số lần xuất hiện (không phân biệt hoa thường)
            count = t_lower.count(kw.lower())
            if count > 0:
                scores[subj] += count * 3.0  # high weight
                details[subj]["high_hits"] += count

        for kw in kw_data.get("medium", []):
            count = t.count(kw)
            if count > 0:
                scores[subj] += count * 1.5  # medium weight
                details[subj]["medium_hits"] += count

        for sym in kw_data.get("symbols", []):
            if sym in t:
                scores[subj] += 0.5  # symbol weight
                details[subj]["symbol_hits"] += 1

    # Tìm môn có điểm cao nhất
    if not scores or max(scores.values()) == 0:
        return "unknown", 0.0, details

    best_subject = max(scores, key=lambda k: scores[k])
    max_score = scores[best_subject]

    # Tính confidence: normalize theo tổng tất cả các môn
    total = sum(scores.values())
    if total > 0:
        confidence = round(scores[best_subject] / total, 3)
    else:
        confidence = 0.0

    # Nếu điểm quá thấp → unknown
    if max_score < 1.5:
        return "unknown", 0.0, details

    return best_subject, confidence, details[best_subject]


# ══════════════════════════════════════════
#  THUẬT TOÁN 2: NORMALIZE CÔNG THỨC HÓA HỌC
# ══════════════════════════════════════════

# Ký hiệu nguyên tố hóa học (bảng tuần hoàn đầy đủ)
_ELEMENT_PATTERN = re.compile(
    r"(?<![A-Za-z])"  # không theo sau nguyên tố khác
    r"(H|He|Li|Be|B|C|N|O|F|Ne|Na|Mg|Al|Si|P|S|Cl|Ar|K|Ca|Sc|Ti|V|Cr|Mn|Fe|Co|Ni|Cu|Zn|Ga|Ge|As|Se|Br|Kr|Rb|Sr|Y|Zr|Nb|Mo|Tc|Ru|Rh|Pd|Ag|Cd|In|Sn|Sb|Te|I|Xe|Cs|Ba|La|Ce|Pr|Nd|Pm|Sm|Eu|Gd|Tb|Dy|Ho|Er|Tm|Yb|Lu|Hf|Ta|W|Re|Os|Ir|Pt|Au|Hg|Tl|Pb|Bi|Po|At|Rn|Fr|Ra|Ac|Th|Pa|U|Np|Pu|Am|Cm|Bk|Cf|Es|Fm|Md|No|Lr)"
    r"("
    r"(?:[1-9]|1[0-9]|20)?"    # số nguyên tử (tùy chọn, mặc định 1)
    r"(?:[₁₁]|[₂₂]|[₃₃]|[₄₄]|[₅₅]|[₆₆]|[₇₇]|[₈₈]|[₉₉]|[₀₀])?"  # subscript unicode (tùy chọn)
    r")?"
    r"(?![a-z])",
    re.IGNORECASE
)

# Phân số ASCII: 1/2, 3/4
_FRAC_ASCII_PATTERN = re.compile(
    r"(?<!\w)(1/2|1/3|2/3|1/4|3/4|1/5|2/5|3/5|4/5|1/6|5/6|1/7|1/8|3/8|5/8|7/8|1/9|1/10)(?!\w)"
)

# Arrow patterns cho hóa học
_ARROW_CHEMISTRY = [
    (re.compile(r"-->"), "→"),      # phản ứng 1 chiều
    (re.compile(r"<-->"), "⇌"),     # cân bằng
    (re.compile(r"<->"), "↔"),      # cộng hưởng
    (re.compile(r"=>"), "⟶"),       # phản ứng thuận
    (re.compile(r"<=>"), "⇌"),      # cân bằng
    (re.compile(r"<==>"), "⇌"),    # cân bằng
    (re.compile(r"↑"), "↑"),        # khí
    (re.compile(r"↓"), "↓"),        # kết tủa
    (re.compile(r" \+ "), " + "),  # dương
    (re.compile(r" \+"), "+"),      # dương
]

# Mũi tên vật lý: →
_PHYSICS_ARROW = re.compile(r"(?<![→↔⟶⇌])(→|→|->)(?![→↔⟶⇌])")


def normalize_chemical_formula(text: str) -> str:
    """
    Thuật toán normalize công thức hóa học.
    - Chuyển H2O → H₂O (subscript)
    - Chuyển 1/2 → ½ (phân số thường)
    - Chuyển --> → → (mũi tên)
    - Giữ nguyên ký hiệu unicode hóa học
    """
    if not text:
        return text

    t = text

    # 1. Chuyển phân số ASCII → unicode
    def replace_frac(m):
        frac = m.group(1)
        return _FRAC_MAP.get(frac, frac)

    t = _FRAC_ASCII_PATTERN.sub(replace_frac, t)

    # 2. Chuyển H2, O2, H2O... → H₂, O₂, H₂O...
    def replace_ascii_sub(m):
        elem = m.group(1)
        num = m.group(2)
        if num:
            # chuyển số thường thành subscript unicode
            sub_num = str(num).translate(_SUB_DIGIT)
            return f"{elem}{sub_num}"
        return elem

    t = _ASCII_SUB_PATTERN.sub(replace_ascii_sub, t)

    # 3. Arrow hóa học
    for pattern, replacement in _ARROW_CHEMISTRY:
        t = pattern.sub(replacement, t)

    # 4. Chuyển arrow vật lý ASCII → unicode
    t = _PHYSICS_ARROW.sub("→", t)

    return t


# ══════════════════════════════════════════
#  THUẬT TOÁN 3: XỬ LÝ ĐƠN VỊ VẬT LÝ
# ══════════════════════════════════════════

# Đơn vị vật lý phổ biến + chuẩn hóa
_UNIT_NORM: Dict[str, str] = {
    # Độ dài
    "km": "km", "m": "m", "cm": "cm", "mm": "mm", "µm": "µm", "nm": "nm",
    "km/h": "km/h", "km/s": "km/s", "m/s": "m/s", "cm/s": "cm/s",
    # Khối lượng
    "kg": "kg", "g": "g", "mg": "mg", "µg": "µg", "tấn": "tấn", "t": "tấn",
    # Thời gian
    "s": "s", "ms": "ms", "µs": "µs", "ns": "ns",
    "phút": "min", "min": "min", "giờ": "h", "h": "h", "ngày": "ngày",
    # Năng lượng / Công
    "J": "J", "kJ": "kJ", "cal": "cal", "kcal": "kcal",
    "eV": "eV", "keV": "keV", "MeV": "MeV", "GeV": "GeV",
    "kWh": "kWh",
    # Công suất
    "W": "W", "kW": "kW", "MW": "MW", "GW": "GW", "mW": "mW",
    # Điện
    "A": "A", "mA": "mA", "kA": "kA",
    "V": "V", "mV": "mV", "kV": "kV",
    "Ω": "Ω", "kΩ": "kΩ", "MΩ": "MΩ", "mΩ": "mΩ",
    "F": "F", "mF": "mF", "µF": "µF", "nF": "nF", "pF": "pF",
    "H": "H", "mH": "mH", "µH": "µH",
    "C": "C", "mC": "mC", "µC": "µC",
    # Từ trường
    "T": "T", "mT": "mT", "µT": "µT", "G": "G", "mG": "mG",
    "Wb": "Wb", "mWb": "mWb", "Mx": "Mx",
    # Nhiệt độ
    "K": "K", "°C": "°C", "°F": "°F",
    # Áp suất
    "Pa": "Pa", "kPa": "kPa", "atm": "atm", "mmHg": "mmHg", "bar": "bar",
    # Quang
    "cd": "cd", "lm": "lm", "lx": "lx", "nm": "nm",
    # Tần số
    "Hz": "Hz", "kHz": "kHz", "MHz": "MHz", "GHz": "GHz",
    "rpm": "rpm", "vòng/phút": "rpm",
    # Góc
    "rad": "rad", "mrad": "mrad", "°": "°",
    # Lực
    "N": "N", "kN": "kN", "mN": "mN", "dyn": "dyn",
    "kgf": "kgf", "lbf": "lbf",
    # Áp suất
    "N/m²": "N/m²", "N/m": "N/m",
    # Nồng độ
    "mol/l": "mol/L", "mol/L": "mol/L", "M": "M", "mM": "mM", "µM": "µM",
    "mol": "mol", "mmol": "mmol", "kmol": "kmol",
}

# Pattern nhận diện đơn vị: số + đơn vị
_UNIT_VALUE_PATTERN = re.compile(
    r"(?<![a-zA-Z°µ])"  # không theo sau chữ cái
    r"(\d+(?:[.,]\d+)?(?:[eE][+-]?\d+)?)"  # số (hỗ trợ scientific notation)
    r"\s*"
    r"("
    + "|".join(re.escape(u) for u in sorted(_UNIT_NORM.keys(), key=len, reverse=True))
    + r"|"
    + r"[a-zA-Zµµ²³/Ω°]+"  # đơn vị tự do
    + r")"
    r"(?!\s*[a-zA-Z])",  # không đứng trước chữ cái
    re.IGNORECASE
)


def normalize_physics_units(text: str) -> str:
    """
    Thuật toán chuẩn hóa đơn vị vật lý trong text.
    - Chuẩn hóa cách viết: km/h, m/s, kg.m/s² → N
    - Giữ nguyên giá trị số, chỉ chuẩn hóa đơn vị
    """
    if not text:
        return text

    t = text

    # Chuẩn hóa đơn vị đã biết
    def replace_unit(m):
        value = m.group(1)
        unit = m.group(2)
        unit_lower = unit.lower().strip()
        # Thay thế bằng dạng chuẩn
        normalized = _UNIT_NORM.get(unit_lower, _UNIT_NORM.get(unit, unit))
        return f"{value} {normalized}"

    t = _UNIT_VALUE_PATTERN.sub(replace_unit, t)

    # Chuẩn hóa dạng vector: (x, y, z) → (x; y; z)
    t = re.sub(r"\(\s*([^)]+?)\s*\)", lambda m: f"({m.group(1).replace(',', '; ')})", t)

    # Chuẩn hóa phân số vật lý: m/2 → m/2 (giữ nguyên, chỉ đảm bảo khoảng trắng)
    t = re.sub(r"(\d+)\s*/\s*(\d+)", r"\1/\2", t)

    # Chuẩn hóa số mũ: m^2 → m², kg.m/s^2 → kg·m/s²
    t = re.sub(r"\^(\d+)", lambda m: str(m.group(1)).translate(_SUP_DIGIT), t)

    # Chuẩn hóa dấu nhân: kg.m → kg·m, N.m → N·m
    t = re.sub(r"([A-Za-z0-9²³⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻])\.([A-Za-z0-9²³⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻])", r"\1·\2", t)

    return t


# ══════════════════════════════════════════
#  THUẬT TOÁN 4: SUBSCRIPT / SUPERSCRIPT
# ══════════════════════════════════════════

_ASCII_SUP_PATTERN = re.compile(r"(?<![a-zA-Z0-9])(\d+)\^(\d+)")
_ASCII_SUP_N_PATTERN = re.compile(r"(?<![a-zA-Z0-9])x\^(\d+)")
_MIXED_SUB_PATTERN = re.compile(r"([A-Za-z])([₁-₉₀]+)")


def ascii_to_subscript(text: str) -> str:
    """Chuyển ASCII subscript → Unicode subscript: H2 → H₂"""
    if not text:
        return text

    t = text

    # H2 → H₂ (khi theo sau nguyên tố hóa học)
    t = _ASCII_SUB_PATTERN.sub(lambda m: m.group(1) + str(m.group(2)).translate(_SUB_DIGIT), t)

    # 2_x → ₂ₓ (số trước chữ)
    t = re.sub(r"(\d+)([a-z])", lambda m: str(m.group(1)).translate(_SUB_DIGIT) + m.group(2), t)

    return t


def ascii_to_superscript(text: str) -> str:
    """Chuyển ASCII superscript → Unicode: x^2 → x²"""
    if not text:
        return text

    t = text

    # x^2 → x²
    t = re.sub(r"x\^(\d+)", lambda m: "x" + str(m.group(1)).translate(_SUP_DIGIT), t)

    # y^2 → y²
    t = re.sub(r"y\^(\d+)", lambda m: "y" + str(m.group(1)).translate(_SUP_DIGIT), t)

    # n^2 → n²
    t = re.sub(r"n\^(\d+)", lambda m: "n" + str(m.group(1)).translate(_SUP_DIGIT), t)

    # generic: a^b → aᵇ
    t = _ASCII_SUP_PATTERN.sub(
        lambda m: m.group(1) + str(m.group(2)).translate(_SUP_DIGIT), t
    )

    return t


def subscript_to_ascii(text: str) -> str:
    """Chuyển Unicode subscript → ASCII: H₂ → H2 (dùng cho garbled detection)"""
    if not text:
        return text

    # Bảng đảo ngược subscript
    _UNSUB = str.maketrans("₀₁₂₃₄₅₆₇₈₉ₐₑᵢₒᵣᵤᵥₓₕₖₗₘₙₚₛₜ𝓌", "0123456789aeioruvxhklmnpstw")
    return text.translate(_UNSUB)


def superscript_to_ascii(text: str) -> str:
    """Chuyển Unicode superscript → ASCII: x² → x^2"""
    if not text:
        return text

    _UNSUP = str.maketrans("⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ", "0123456789+-=()n")
    return text.translate(_UNSUP)


# ══════════════════════════════════════════
#  THUẬT TOÁN 5: GARBLED DETECTION CẢI TIẾN
# ══════════════════════════════════════════

# Các ký hiệu khoa học HỢP LỆ — KHÔNG phải garbled
_SCIENTIFIC_VALID: List[re.Pattern] = [
    # Toán
    re.compile(r"[√∫∑∏π∞∂∇∈∉⊂⊃⊆⊇∪∩∅∀∃≠≤≥≈≡≡≠±÷×]"),
    # Hy Lạp
    re.compile(r"[αβγδεζηθικλμνξορστυφχψωΓΔΘΛΞΠΣΦΨΩ]"),
    # Hóa
    re.compile(r"[→⇌↑↓⟶⟻⟼⇌↔⊕⊖]"),
    # Vật lý / Khoa học
    re.compile(r"[°Å℉ΩμÅ]"),
    # Subscript/superscript
    re.compile(r"[₀₁₂₃₄₅₆₷₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾]"),
    # Đơn vị
    re.compile(r"(?<![a-zA-Z])(kg|m|s|J|W|Pa|Hz|Ω|V|A|T|Wb|F|H|C|K|°C|eV|keV|MeV|N|nm|mm|cm|km|ml|L|mol|mol/L|rpm)(?![a-zA-Z])", re.I),
]

# Patterns báo hiệu text garbled / lỗi font
_GARBLED_PATTERNS: List[re.Pattern] = [
    re.compile(r"[%#@\^~]{2,}"),                    # %%##@@
    re.compile(r"[A-Za-z0-9][%#@][A-Za-z0-9]"),     # K%
    re.compile(r"K%|Ã|Â|ð|�"),                      # lỗi Vietnamese encoding
    re.compile(r"[\x00-\x08\x0e-\x1f]"),            # control characters
    re.compile(r"[\ufffd]{2,}"),                    # replacement char liên tiếp
    re.compile(r"[A-Za-z]{1,3}[%#@][A-Za-z]{1,3}"), # pattern dạng var%name
    re.compile(r"\s{5,}"),                         # khoảng trắng liên tiếp quá nhiều
]


def is_scientific_valid(text: str) -> bool:
    """Kiểm tra text có chứa ký hiệu khoa học hợp lệ."""
    if not text:
        return False
    return any(pat.search(text) for pat in _SCIENTIFIC_VALID)


def looks_garbled_improved(text: str) -> bool:
    """
    Thuật toán cải tiến: phát hiện text garbled / lỗi font.
    Đã loại trừ các ký hiệu khoa học hợp lệ.
    """
    t = (text or "").strip()
    if not t:
        return False

    # Nếu có ký hiệu khoa học → giả định hợp lệ
    if is_scientific_valid(t):
        return False

    # Kiểm tra các pattern garbled
    for pat in _GARBLED_PATTERNS:
        if pat.search(t):
            return True

    # Tính tỷ lệ ký tự lạ
    # Cho phép: alphanumeric, khoảng trắng, dấu câu phổ biến, tiếng Việt cơ bản, toán học
    allowed = set(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"
        "0123456789"
        " \t.,;:!?()[]{}<>-_+*/=≤≥≠≈≡±…—–'\""
        "ÀÁÂÃÈÉÊÌÍÒÓÔÕÙÚÝàáâãèéêìíòóôõùúý"
        "ĂăĐđĨĩŨũƠơƯư"
        "ẠạẬậẦầẤấẨẩẪẫẬậẸẹỀềỂểỄễỆệỈỉỊịỌọỜờỞởỠỡỢợ"
        "ỤụỪừỬửỰựỲỳỴỵỶỷỸỹ"
        # Toán
        "√∫∑∏π∞∂∇∈∉⊂⊃⊆⊇∪∩∅∀∃≠≤≥≈≡±÷×∝→←↔↑↓"
        "αβγδεζηθικλμνξορστυφχψωΓΔΘΛΞΠΣΦΨΩ"
        # Đơn vị & subscript/superscript
        "°ÅΩμ℉₀₁₂₃₄₅₆₇₈₉⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿ"
        # Hóa arrows
        "⇌⟶⟻⟼⊕⊖"
    )
    weird_chars = [c for c in t if c not in allowed]
    if len(weird_chars) >= 3:
        return True

    # Quá nhiều ký tự không ascii liên tiếp
    if re.search(r"[\u0080-\u00FF]{8,}", t):
        return True

    return False


# ══════════════════════════════════════════
#  THUẬT TOÁN 6: ENRICH FIELDS STEM
# ══════════════════════════════════════════

# Regex cho các dạng công thức toán học phổ biến
_MATH_FRACTION_PAT = re.compile(
    r"(?<![\w²³⁰¹⁴⁵⁶⁷⁸⁹])"
    r"("
    r"(?:\\frac\s*\{[^}]+\}\s*\{[^}]+\})"  # \frac{num}{den}
    r"|(?:(?:[A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])\s*/\s*(?:[A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻]))"  # a/b
    r"|(?:[0-9]+\s*/\s*[0-9]+)"  # 1/2
    r")"
    r"(?![\w²³⁰¹⁴⁵⁶⁷⁸⁹])"
)

_MATH_SQRT_PAT = re.compile(
    r"(?<![\w²³⁰¹⁴⁵⁶⁷⁸⁹])"
    r"("
    r"(?:\\sqrt\s*(?:\[[^\]]+\])?\s*\{[^}]+\})"  # \sqrt{...}
    r"|(?:√\s*(?:(?:\[[^\]]+\])|(?:\([^\)]+\)))?\s*(?:[A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻\(\)]+]))"  # √(...)
    r"|(?:[Aa]p?proximat?ely\s+)?(?:[0-9.]+)\s*[~≈]\s*[0-9.]+"  # ~3.14
    r")"
)

_MATH_EXP_PAT = re.compile(
    r"(?<![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
    r"([A-Za-z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])\s*\^\s*([0-9⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻nN]|\([^)]+\)|\[[^\]]+\]|\{[^}]+\})"
    r"(?![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
)

_MATH_SUM_PAT = re.compile(
    r"(?<![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
    r"(Σ|∑|Sum|sum|SUM)\s*"
    r"(?:[_]\s*\{[^}]*\}|\b\w+\b)"
    r"(?:[^;]{0,30})?"
    r"(?:to|→)\s*"
    r"(?:[^;]{0,30})?"
    r"(?:n|∞|\d+)"
    r"(?![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])",
    re.IGNORECASE
)

_MATH_INT_PAT = re.compile(
    r"(?<![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
    r"(∫|∬|∮|Integral|integral|INT)\s*"
    r"(?:[_]\s*\{[^}]*\}|\b\w+\b)?"
    r"(?:[^;]*?dx|d[A-Za-z])",
    re.IGNORECASE
)

_MATH_LIM_PAT = re.compile(
    r"(?<![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
    r"(lim|lim_{x→|lim\s*\(?)\s*"
    r"(?:[A-Za-z]\s*→\s*"
    r"(?:[A-Za-z0-9∞⁺⁻ⁿ]|\([^)]+\))"
    r"|[A-Za-z]\s*[=≈]\s*(?:0|∞|1|2|\\infty))"
    r"(?![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])",
    re.IGNORECASE
)

_PHYSICS_VECTOR_PAT = re.compile(
    r"(?<![a-zA-Z])"
    r"(?:→|vect?o?\s*|vec\s*)"
    r"([A-Z][a-z]?)"
    r"(?![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])"
)

_PHYSICS_UNIT_IN_TEXT = re.compile(
    r"(?<![a-zA-Z0-9])"
    r"("
    r"[0-9]+(?:[.,][0-9]+)?(?:\s*[×x]\s*[0-9]+(?:\s*[×x]\s*[0-9]+)?)?"
    r")"
    r"\s*"
    r"(?:"
    r"kg(?:\.m/s²|m/s|m³|L|mol|Hz|W)?"
    r"|N(?:\.m|/(?:m²|m³|s))?"
    r"|J(?:\/(?:mol|K|s))?"
    r"|W(?:\.m)?"
    r"|Pa(?:\.s)?"
    r"|Hz"
    r"|T(?:\.m²)?"
    r"|A(?:\.s)?"
    r"|V(?:\.A)?"
    r"|Ω(?:\.m)?"
    r"|F(?:\.m)?"
    r"|H(?:\.m)?"
    r"|C(?:\.mol)?"
    r"|rad(?:\.s)?"
    r"|sr"
    r"|eV|keV|MeV|GeV"
    r"|km/h|km/s|m/s|cm/s|mm/s"
    r"|km|hm|dam|m|dm|cm|mm|nm|µm|Å"
    r"|kg|g|mg|µg|tấn|t"
    r"|s|ms|µs|ns|min|h|ngày"
    r"|K|°C|°F|°"
    r"|mol|mmol|kmol|mM|µM"
    r"|cd|lm|lx"
    r"|rpm|vòng/phút"
    r"|atm|mmHg|bar|kPa|Pa"
    r"|L|ml|µL|m³|cm³"
    r"|N/m|N/m²|N\.m"
    r"|kg\.m²/s²|J/s|Wb|T|mT|Ω\.m"
    r")"
    r"(?![a-zA-Z0-9²³⁰¹⁴⁵⁶⁷⁸⁹⁺⁻])",
    re.IGNORECASE
)

_CHEM_FORMULA_PAT = re.compile(
    r"(?<![a-zA-Z₀-₉])"
    r"("
    r"[A-Z][a-z]?"        # nguyên tố (H, C, Na, Fe...)
    r"(?:[₀-₉0-9]+)?"       # subscript
    r")+"
    r"(?:"
    r"[-+]"               # ion charge
    r"(?:[₀-₉0-9]+)?"     # số charge
    r")?"
    r"(?![a-zA-Z₀-₉])"
)

_CHEM_REACTION_ARROW = re.compile(
    r"(?<!\S)"
    r"("
    r"(?:<==?>|-->?|⇌|→|⟶|⟻|⟼)"
    r"|"
    r"(?:<-+>+|=)"
    r")"
    r"(?!\S)"
)


def classify_math_expression(text: str) -> List[str]:
    """
    Phân loại các dạng biểu thức toán học có trong text.
    Trả về danh sách loại: ["fraction", "sqrt", "exponent", "sum", "integral", "limit", ...]
    """
    if not text:
        return []

    types = []
    if _MATH_FRACTION_PAT.search(text):
        types.append("fraction")
    if _MATH_SQRT_PAT.search(text):
        types.append("sqrt")
    if _MATH_EXP_PAT.search(text):
        types.append("exponent")
    if _MATH_SUM_PAT.search(text):
        types.append("summation")
    if _MATH_INT_PAT.search(text):
        types.append("integral")
    if _MATH_LIM_PAT.search(text):
        types.append("limit")

    return types


def detect_physics_elements(text: str) -> Dict:
    """
    Phát hiện các thành phần vật lý trong text:
    - vector (→v, vectơ v)
    - đơn vị
    - ký hiệu (ω, λ, ν, φ, ...)
    """
    if not text:
        return {}

    result = {
        "has_vector": bool(_PHYSICS_VECTOR_PAT.search(text)),
        "has_units": bool(_PHYSICS_UNIT_IN_TEXT.search(text)),
        "symbols": [],
        "formulas": [],
    }

    # Ký hiệu vật lý phổ biến
    phys_symbols = {
        "ω": "tốc độ góc", "φ": "pha", "λ": "bước sóng", "ν": "tần số",
        "ω": "omega", "ρ": "khối lượng riêng", "σ": "ứng suất", "ε": "chiều dài",
        "η": "hiệu suất", "θ": "góc", "ψ": "hàm sóng", "Γ": "gamma lớn",
        "Ω": "ohm", "μ": "hệ số ma sát", "τ": "momen", "Φ": "từ thông",
        "ℰ": "suất điện động", "𝒜": "ampe", "ℰ₀": "epsilon_0",
        "k": "hằng số Boltzmann", "h": "hằng số Planck", "ℏ": "h-bar",
        "G": "hằng số hấp dẫn", "c": "vận tốc ánh sáng", "ε₀": "điện môi chân không",
        "μ₀": "từ môi chân không", "g": "gia tốc rơi tự do",
        "v₀": "vận tốc ban đầu", "v": "vận tốc", "a": "gia tốc",
    }
    found_syms = []
    for sym, name in phys_symbols.items():
        if sym in text:
            found_syms.append({"symbol": sym, "name": name})
    result["symbols"] = found_syms

    # Công thức vật lý phổ biến
    phys_formulas = [
        "F=ma", "E=mc²", "P=UI", "U=IR", "W=Fd", "P=W/t",
        "v=s/t", "a=Δv/Δt", "p=mv", "E_k=½mv²", "E_p=mgh",
        "Q=mcΔt", "PV=nRT", "F=kq₁q₂/r²", "E=F/q", "V=W/q",
        "T=2π√(l/g)", "T=2π√(m/k)", "f=1/T", "v=λf",
        "n₁sinα=n₂sinβ", "sin i = n.sin r", "1/f = 1/d + 1/d'",
        "E=hv", "λ=h/p", "ΔE=hf", "hc/λ",
    ]
    found_f = []
    t_lower = text.lower()
    for formula in phys_formulas:
        if formula.lower() in t_lower or formula.replace("=", "").lower() in t_lower:
            found_f.append(formula)
    result["formulas"] = found_f

    return result


def detect_chemistry_elements(text: str) -> Dict:
    """
    Phát hiện các thành phần hóa học trong text.
    """
    if not text:
        return {}

    result = {
        "has_reaction": bool(_CHEM_REACTION_ARROW.search(text)),
        "has_formula": bool(_CHEM_FORMULA_PAT.search(text)),
        "formulas": [],
        "reactions": [],
    }

    # Tìm công thức hóa
    formulas = _CHEM_FORMULA_PAT.findall(text)
    if formulas:
        result["formulas"] = list(set(formulas[:20]))  # unique, giới hạn 20

    # Tìm phản ứng hóa học
    parts = _CHEM_REACTION_ARROW.split(text)
    if len(parts) >= 2:
        for i, part in enumerate(parts):
            if re.match(r"^\s*[A-Z]", part):
                result["reactions"].append(part.strip()[:80])

    return result


def enrich_science_fields(question_data: Dict) -> Dict:
    """
    Thuật toán chính: enrich câu hỏi STEM với metadata chuyên biệt.

    Returns dict bổ sung thêm:
    - subject: môn học phát hiện được
    - subject_confidence: độ chính xác phát hiện môn
    - math_types: các dạng toán phát hiện được
    - physics_elements: dict phần tử vật lý
    - chemistry_elements: dict phần tử hóa học
    - is_stem: bool có phải STEM không
    - formula_count: số công thức phát hiện
    - unit_count: số đơn vị phát hiện
    """
    q = dict(question_data or {})

    # Ghép question + choices để phân tích
    question = str(q.get("question") or "").strip()
    choices = q.get("choices") or []
    choices_text = " ".join(
        str((c or {}).get("text") or "").strip() for c in choices
    )
    full_text = f"{question} {choices_text}"

    # 1. Phát hiện môn học
    subject, subj_conf, subj_details = detect_subject(full_text)
    q["subject"] = subject
    q["subject_confidence"] = subj_conf
    q["subject_details"] = subj_details

    # 2. Phân loại biểu thức toán
    math_types = classify_math_expression(full_text)
    q["math_types"] = math_types
    q["math_formula_count"] = len(math_types)

    # 3. Phần tử vật lý
    physics = detect_physics_elements(full_text)
    q["physics"] = physics
    q["physics_unit_count"] = 1 if physics.get("has_units") else 0
    q["physics_vector_count"] = 1 if physics.get("has_vector") else 0

    # 4. Phần tử hóa học
    chemistry = detect_chemistry_elements(full_text)
    q["chemistry"] = chemistry
    q["chemistry_formula_count"] = len(chemistry.get("formulas", []))
    q["chemistry_has_reaction"] = chemistry.get("has_reaction", False)

    # 5. STEM flag
    q["is_stem"] = (
        subject in ("math", "physics", "chemistry", "biology")
        or bool(math_types)
        or physics.get("has_units")
        or chemistry.get("has_formula")
    )

    # 6. Tổng số công thức / ký hiệu khoa học
    q["formula_count"] = (
        q.get("math_formula_count", 0)
        + q.get("chemistry_formula_count", 0)
        + len(physics.get("formulas", []))
    )

    # 7. Chuẩn hóa công thức hóa & đơn vị vật lý trong text gốc
    if q["is_stem"]:
        q["_normalized_question"] = normalize_chemical_formula(
            normalize_physics_units(question)
        )
        normalized_choices = []
        for c in choices:
            txt = str((c or {}).get("text") or "").strip()
            txt = normalize_chemical_formula(normalize_physics_units(txt))
            lb = (c.get("label") or "").strip().upper()
            normalized_choices.append({"label": lb, "text": txt})
        q["_normalized_choices"] = normalized_choices

    return q


# ══════════════════════════════════════════
#  THUẬT TOÁN 7: EXPORT CHO FRONTEND
# ══════════════════════════════════════════

def build_rich_text_for_display(q: Dict) -> Dict:
    """
    Build text hiển thị đẹp cho frontend (rich text).
    - Normalize hóa học
    - Normalize đơn vị vật lý
    - Chuyển superscript
    - Gắn nhãn subject vào display
    """
    q = enrich_science_fields(q)

    question = str(q.get("question") or "").strip()
    choices = q.get("choices") or []

    # Chuẩn hóa display
    display_question = normalize_chemical_formula(
        normalize_physics_units(
            ascii_to_superscript(question)
        )
    )

    display_choices = []
    for c in choices:
        txt = str((c or {}).get("text") or "").strip()
        lb = (c.get("label") or "").strip().upper()
        txt = normalize_chemical_formula(
            normalize_physics_units(
                ascii_to_superscript(txt)
            )
        )
        display_choices.append({"label": lb, "text": txt})

    # Metadata hiển thị
    display_meta = {
        "subject": q.get("subject", "unknown"),
        "is_stem": q.get("is_stem", False),
        "math_types": q.get("math_types", []),
        "has_physics_units": bool(q.get("physics", {}).get("has_units")),
        "has_chemistry_formula": bool(q.get("chemistry", {}).get("has_formula")),
        "has_vector": bool(q.get("physics", {}).get("has_vector")),
        "subject_confidence": q.get("subject_confidence", 0.0),
    }

    return {
        **q,
        "display_question": display_question,
        "display_choices": display_choices,
        "display_meta": display_meta,
    }


# ══════════════════════════════════════════
#  GIAO DIỆN HÓA VỚI MAIN PARSER
# ══════════════════════════════════════════

def patch_garbled_detection(text: str) -> bool:
    """
    Patch cho hàm _looks_garbled_text trong main_updated.py.
    Sử dụng thuật toán cải tiến thay thế.
    """
    return looks_garbled_improved(text)


def get_science_metadata(question_data: Dict) -> Dict:
    """
    Wrapper: lấy metadata khoa học cho một câu hỏi.
    Dùng để gọi từ các endpoint AI / RAG.
    """
    return enrich_science_fields(question_data)
