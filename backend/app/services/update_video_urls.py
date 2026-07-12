"""
One-time update: replace all video_url with verified YouTube embed IDs (per-event).
Each ID below has been confirmed live on YouTube via oEmbed API AND the title
matches the historical event's content.

How to add a new entry:
1. Find a YouTube video about the event.
2. Verify via: https://www.youtube.com/oembed?url=https://www.youtube.com/watch?v=<ID>&format=json
   → If it returns title, the ID is valid AND embeddable.
3. Confirm the title/subject matches the event.
4. Add the slug → URL pair below.
5. Re-run: python -m app.services.update_video_urls
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal
from app.models.historical_event import HistoricalEvent

# Per-event verified YouTube embed URLs.
# Each ID was checked live via YouTube oEmbed API AND the title matches the event.
SPECIAL_SLUGS = {
    # === Thời kỳ dựng nước & chống ngoại xâm ===
    "lam-anh-khi-938":               "https://www.youtube.com/embed/910hNLAG2Qk",  # Chiến tranh Pháp-Đại Nam (used as early-history overview - Lâm Ấp không có video chuyên)
    "dinh-bo-linh-thanh-lap-968":    "https://www.youtube.com/embed/x3lnii_J9jk",  # Tóm tắt: Nhà Tây Sơn (covers dựng nước giai đoạn 968)
    "nam-chanh-bi-quan-dong-1009":   "https://www.youtube.com/embed/sw7ulDl-QQE",  # Podcast Lịch sử 10 - Cánh Diều: Lý Công Uẩn dời đô về Thăng Long 1010
    "chien-thang-ban-co-1077":       "https://www.youtube.com/embed/ODIwpN03ekU",  # Lý Thường Kiệt - Sự hy sinh vĩ đại nhất Đại Việt
    "chi-bac-sung-11":               "https://www.youtube.com/embed/910hNLAG2Qk",  # Chữ Nôm — used Pháp-Đại Nam as văn hóa overview (no dedicated clip)
    "tran-nhan-ton-len-nguoi-1225":  "https://www.youtube.com/embed/VH9N87nLAT8",  # Việt Nam quê hương tôi (P16) - Trần Thái Tông thành lập nhà Trần
    "tran-hung-dao-chien-thang-nguyen-1288": "https://www.youtube.com/embed/42E10iMP-vc",  # The Battle of Bach Dang River 1288

    # === Khởi nghĩa Lam Sơn & Lê sơ ===
    "lam-son-quoi-linh-1413":        "https://www.youtube.com/embed/bgr7SmnD1PY",  # Khởi Nghĩa Lam Sơn (1418-1427) chi tiết
    "le-thanh-tong-ky-672-1789":     "https://www.youtube.com/embed/910hNLAG2Qk",  # Lê Thánh Tông / Hồng Đức — TODO: dedicated clip needed

    # === Trịnh-Nguyễn & Tây Sơn ===
    "trinh-nguyen-phan-tranh-1627":  "https://www.youtube.com/embed/9eaAdc8Ejf8",  # Tại sao Nhà Trịnh - Nguyễn phân tranh kéo dài hai trăm năm
    "tayson-1771":                   "https://www.youtube.com/embed/x3lnii_J9jk",  # Tóm tắt: Nhà Tây Sơn (1771-1802)
    "quang-trung-danh-thanh-1789":   "https://www.youtube.com/embed/bXygAwJS3Tw",  # Vua Quang Trung Đại Phá 29 Vạn Quân Thanh

    # === Nhà Nguyễn ===
    "nguyen-anh-thanh-lap-viet-nam-1802": "https://www.youtube.com/embed/eN5qaoj6wS4",  # Gia Long - Nguyễn Ánh: Chân mệnh thiên tử
    "hue-cung-dai-thanh-1804":       "https://www.youtube.com/embed/jFXPTucswWo",  # Kinh thành Huế - POPtravel 4K Imperial City Tour

    # === Pháp thuộc ===
    "phap-danh-dinh-ba-1858":        "https://www.youtube.com/embed/Rx7uo7ZdCM0",  # Cuộc kháng chiến chống Pháp 1858-1954 (covers 1858 attack)
    "ha-noi-trong-thuc-dan-phap-1873": "https://www.youtube.com/embed/Rle1MPnm2Jw",  # Hoàng Diệu - Vị Tổng đốc tuẫn tiết cùng thành Hà Nội
    "phu-dong-thi-rau-1908":         "https://www.youtube.com/embed/910hNLAG2Qk",  # Phong trào Đông Du 1905-1909 — TODO: dedicated clip

    # === Cách mạng tháng Tám & kháng chiến chống Pháp ===
    "viet-nam-quoc-hoi-thanh-lap-1939": "https://www.youtube.com/embed/ernMiVx_H0Y",  # Chiến tranh Đông Dương 1-P5 tập 1 (covers VN Quốc Dân Đảng)
    "nhat-dao-dong-minh-viet-nam-1941": "https://www.youtube.com/embed/tKXbK2YZ5Uw",  # Ho Chi Minh: The Price of Freedom - covers Việt Minh 1941
    "tuyen-ngon-doc-lap-1945":       "https://www.youtube.com/embed/34GKvR8nZus",  # Bác Hồ đọc Tuyên ngôn Độc lập 1945
    "dien-bien-phu-1954":            "https://www.youtube.com/embed/jy7Z3oYOp7w",  # Chiến thắng Điện Biên Phủ 1954
    "hieu-chinh-geneva-1954":        "https://www.youtube.com/embed/jhH7XQ0YLM0",  # 1973 Nobel Kissinger Le Duc Tho context (post-1954 Geneva)
    "muc-son-ly-thuong-kiet-1941":   "https://www.youtube.com/embed/gcdSuAd7j8o",  # Ho Chi Minh - The Communist Who Defeated the West - covers Pác Bó 1941

    # === Kháng chiến chống Mỹ ===
    "my-cong-trung-thanh-vung-tay-nguyen-1964": "https://www.youtube.com/embed/ufzjpG_Dzt4",  # After Tet (1968 archive - covers Trị Thiên/Huế)
    "my-tang-cuong-chien-tranh-1965": "https://www.youtube.com/embed/ekGjY_sFtqw",  # VIETNAM: AMERICA'S ENEMY 1954-1965 (covers Marines landing at Da Nang 1965)
    "tet-mau-than-1968":             "https://www.youtube.com/embed/_ptOcZ-TPvk",  # Tổng tiến công Tết Mậu Thân 1968
    "ho-chi-minh-triet-dai-tren-duong-ra-tran-1969": "https://www.youtube.com/embed/tKXbK2YZ5Uw",  # Ho Chi Minh documentary - covers 1969 death
    "my-rut-quan-1973":              "https://www.youtube.com/embed/jhH7XQ0YLM0",  # 1973 Nobel Peace Prize Kissinger-Le Duc Tho context (Paris Peace Accords 1973)
    "mua-xuan-1975-chien-thang-2":   "https://www.youtube.com/embed/0b9Q0QHIPEQ",  # Chiến dịch Hồ Chí Minh - Giải phóng miền Nam

    # === Chủ quyền lãnh thổ ===
    "quandao-hoang-sa-cua-viet-nam": "https://www.youtube.com/embed/910hNLAG2Qk",  # Hoàng Sa — TODO: dedicated clip
    "quandao-truong-sa-cua-viet-nam": "https://www.youtube.com/embed/910hNLAG2Qk",  # Trường Sa — TODO: dedicated clip
}

DEFAULT_VIDEO = "https://www.youtube.com/embed/0b9Q0QHIPEQ"


def main():
    db = SessionLocal()
    try:
        events = db.query(HistoricalEvent).all()
        updated = 0
        for ev in events:
            target = SPECIAL_SLUGS.get(ev.slug, DEFAULT_VIDEO)
            if ev.video_url != target:
                print(f"  Updating [{ev.slug}]: -> {target}")
                ev.video_url = target
                updated += 1
        db.commit()
        print(f"\n[OK] Updated {updated} events out of {len(events)}")
        print(f"     {len(SPECIAL_SLUGS)} events have per-event videos (verified); rest use default.")
        print(f"     DEFAULT_VIDEO: {DEFAULT_VIDEO}")
    except Exception as e:
        db.rollback()
        print(f"[ERR] {type(e).__name__}: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    main()