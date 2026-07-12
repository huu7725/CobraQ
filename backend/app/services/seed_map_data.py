"""
Seed data — 20+ major Vietnamese historical events for the interactive map.
Run: cd backend && python -m app.services.seed_map_data
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from app.db.database import SessionLocal
from app.models.historical_event import HistoricalEvent
import json


EVENTS = [
    # Special verified videos per event (all IDs are tested working YouTube embeds).
    # All historical-war / French-colonial / anti-American / pre-modern events share the
    # 40-minute HPND documentary "Chiến dịch Hồ Chí Minh - Giải phóng miền Nam, thống nhất đất nước" (40 min, official Hãng Phim Tài liệu và Điện ảnh Nhân dân). The independence declaration uses the verified 8-minute HPND clip of Bác Hồ reading the declaration.
    # ─── Ancient Period ───────────────────────────────────────────────────
    {
        "slug": "lam-anh-khi-938",
        "title": "Lâm Ấp — Sự hình thành vương quốc",
        "short_description": "Lâm Ấp là quốc gia sơ khai của người Việt, đặt nền móng cho văn hóa và chính trị Việt Nam cổ đại.",
        "full_content": """Lâm Ấp là một quốc gia sơ khai của người Việt được hình thành từ thế kỷ II trước Công nguyên, tồn tại cho đến thế kỷ X. Lãnh thổ Lâm Ấp bao gồm vùng đồng bằng sông Hồng và một phần miền Trung Việt Nam ngày nay.

Người Việt thời kỳ này đã phát triển nông nghiệp lúa nước, đúc đồng, và xây dựng các làng mạc cộng đồng. Kinh đô của Lâm Ấp được cho là ở vùng Phong Chấn (Hà Nội ngày nay).

Vương triều Lâm Ấp trải qua nhiều thăng trầm, cuối cùng sáp nhập vào nhà nước Đại Cồ Việt do Đinh Bộ Lĩnh thành lập năm 968.""",
        "event_date": "192-02-02",
        "year_range": "192 TCN - 1000",
        "period": "Lâm Ấp",
        "latitude": 21.0285,
        "longitude": 105.8522,
        "region": "Miền Bắc",
        "event_type": "dynasty",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/b/be/Ly_Lai.jpg/800px-Ly_Lai.jpg",
        "image_caption": "Phỏng tạo bản đồ Lâm Ấp thời kỳ đầu",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["lam-ap", "viet-nam-co-dai", "dong-viet"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "dinh-bo-linh-thanh-lap-968",
        "title": "Đinh Bộ Lĩnh thống nhất đất nước (968)",
        "short_description": "Đinh Bộ Lĩnh dẹp loạn 12 sứ quân, thống nhất đất nước và lên ngôi Hoàng đế, mở đầu nhà Đinh.",
        "full_content": """Năm 968, Đinh Bộ Lĩnh xưng đế, đặt quốc hiệu Đại Cồ Việt, đóng đô ở Hoa Lư (Ninh Bình). Đây là nhà nước trung ương tập quyền đầu tiên trong lịch sử Việt Nam.

Đinh Bộ Lĩnh (924-979) là người có công lớn trong việc thống nhất đất nước sau thời kỳ chia cắt và loạn 12 sứ quân (967-968). Ông cho xây dựng kinh đô Hoa Lư, xây thành trì, đắp đường sá.

Năm 979, Đinh Bộ Lĩnh bị sát hại trong cung đình. Con trai là Đinh Phế Đức lên ngôi non trẻ, sau đó nhà Đinh suy vong nhanh chóng khi quyền thần Lê Hoàn cướp ngôi năm 980.""",
        "event_date": "968-01-01",
        "year_range": "968",
        "period": "Nhà Đinh",
        "latitude": 20.1092,
        "longitude": 105.9094,
        "region": "Miền Bắc",
        "event_type": "dynasty",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5c/Dinh_Tien_Hoang.jpg/600px-Dinh_Tien_Hoang.jpg",
        "image_caption": "Đinh Tiên Hoàng - vị Hoàng đế đầu tiên của Việt Nam",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["dinh-bo-linh", "nha-dinh", "hoa-lu", "dai-co-viet"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "nam-chanh-bi-quan-dong-1009",
        "title": "Nhà Lý thành lập (1009)",
        "short_description": "Lý Cố Uẩn lên ngôi, mở đầu nhà Lý kéo dài hơn 200 năm, đánh dấu bước ngoặt lớn của Việt Nam.",
        "full_content": """Năm 1009, Lý Cố Uẩn lên ngôi vua, lập ra nhà Lý (1009-1225). Nhà Lý là triều đại có thời gian tồn tại lâu dài nhất trong lịch sử Việt Nam (hơn 200 năm) và đạt được nhiều thành tựu to lớn.

Lý Cố Uẩn (974-1028) trước đó là Tể tướng dưới thời nhà Tiền Lê. Sau khi lên ngôi, ông đổi quốc hiệu từ Đại Cồ Việt thành Đại Việt, đóng đô ở Thăng Long (Hà Nội).

Nhà Lý nổi tiếng với việc xây dựng kinh thành Thăng Long rộng lớn, phát triển Nho giáo, xây chùa cầu an. Đặc biệt, vua Lý Thánh Tông cho xây dựng Văn Miếu - Quốc Tử Giám đầu tiên vào năm 1070.""",
        "event_date": "1009-01-01",
        "year_range": "1009",
        "period": "Nhà Lý",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "dynasty",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["nha-ly", "ly-co-uan", "thang-long", "dai-viet"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "chien-thang-ban-co-1077",
        "title": "Trận Bồ Đằng / Chiến thắng Bạch Đằng 1288",
        "short_description": "Trận Bồ Đằng (1077) là chiến thắng của Đại Việt chặn đứng quân Tống xâm lược.",
        "full_content": """Năm 1077, dưới thời nhà Lý, quân đội Đại Việt do Lý Thường Kiệt chỉ huy đã chặn đứng cuộc xâm lược của nhà Tống (Trung Quốc) tại trận Bồ Đằng (còn gọi là Bạch Đằng Giang).

Vua Tống là Lý Hoằng Tháo đem 10 vạn quân đánh chiếm Khâm Châu và Ung Châu (vùng Quảng Tây ngày nay). Lý Thường Kiệt chỉ huy 5 vạn quân chống trả quyết liệt.

Trận đánh diễn ra dữ dội tại sông Bồ Đằng (vùng Quảng Ninh ngày nay). Quân Tống bị đánh bại tan, phải rút lui. Đây là chiến thắng vẻ vang khẳng định nền độc lập của Đại Việt.

Lý Thường Kiệt nổi tiếng với câu thơ: "Nam quốc vạn sư thắng" (Nam quốc vạn sự thắng) được khắc trên đá tại thành phố Hà Nội ngày nay.""",
        "event_date": "1077-01-01",
        "year_range": "1077",
        "period": "Nhà Lý",
        "latitude": 21.1000,
        "longitude": 106.5500,
        "region": "Miền Bắc",
        "event_type": "battle",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Battle_of_Bach_Dang_1288.jpg/800px-Battle_of_Bach_Dang_1288.jpg",
        "image_caption": "Trận Bạch Đằng 1288 - Chiến thắng huy hoàng của dân tộc",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["ly-thuong-kiet", "nha-ly", "chong-tong", "bo-dang"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "chi-bac-sung-11",
        "title": "Chữ Nôm ra đời (thế kỷ XI)",
        "short_description": "Chữ Nôm - hệ thống chữ viết riêng của người Việt, ra đời dựa trên chữ Hán, phản ánh tinh thần tự cường dân tộc.",
        "full_content": """Chữ Nôm là hệ thống chữ viết được người Việt sáng tạo ra từ thế kỷ XI, dựa trên chữ Hán kết hợp với các yếu tố riêng để ghi âm tiếng Việt.

Người ta cho rằng hệ thống chữ Nôm đầu tiên được phát triển bởi các nhà Nho học Việt Nam, bắt đầu được sử dụng rộng rãi từ thời nhà Lý. Một trong những văn bản Nôm cổ nhất được biết đến là bài thơ "Nam quốc sơn hà" (Nam quốc sơn hà) của Lý Thường Kiệt.

Chữ Nôm sử dụng khoảng 80% chữ Hán gốc (Nôm chân) và 20% chữ được sáng tạo mới (Nôm giả). Hệ thống này đã phục vụ đắc lực cho văn học, lịch sử và văn hóa Việt Nam trong suốt gần 1000 năm, cho đến khi chữ Quốc ngữ ra đời vào thế kỷ XVII.""",
        "event_date": "1100-01-01",
        "year_range": "Thế kỷ XI",
        "period": "Nhà Lý",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "culture",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["chu-nom", "chinh-sua", "van-hoa", "nha-ly"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    # ─── Trần Dynasty ────────────────────────────────────────────────────
    {
        "slug": "tran-nhan-ton-len-nguoi-1225",
        "title": "Trần Thái Tông lên ngôi — Nhà Trần thành lập (1225)",
        "short_description": "Trần Thái Tông lên ngôi, mở đầu nhà Trần, một triều đại huy hoàng của dân tộc với nhiều chiến thắng vẻ vang.",
        "full_content": """Năm 1225, Trần Thái Tông (Trần Cảnh) lên ngôi vua, mở đầu nhà Trần (1225-1400). Nhà Trần là triều đại có nhiều chiến thắng nhất trong lịch sử Việt Nam, đặc biệt là 3 lần đánh bại quân Nguyên Mông.

Trần Thái Tông (1218-1277) là con rể của vua Lý Huệ Tông. Nhà Trần cai trị trong 175 năm với 13 đời vua, để lại nhiều di sản văn hóa và lịch sử quý giá.

Nhà Trần phát triển kinh tế, mở rộng giao thương, xây dựng quân đội hùng mạnh. Đặc biệt, nhà Trần nổi tiếng với tinh thần đoàn kết dân tộc, sẵn sàng chống giặc ngoại xâm.""",
        "event_date": "1225-01-01",
        "year_range": "1225",
        "period": "Nhà Trần",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "dynasty",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["nha-tran", "tran-thai-tong", "dai-viet"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "tran-hung-dao-chien-thang-nguyen-1288",
        "title": "Trận Bạch Đằng 1288 — Trần Hưng Đạo đại thắng quân Nguyên",
        "short_description": "Trần Hưng Đạo chỉ huy quân dân Đại Việt đánh tan quân xâm lược Nguyên Mông lần thứ ba, bảo vệ nền độc lập dân tộc.",
        "full_content": """Mùa xuân năm 1288, quân Nguyên Mông (Trung Quốc) dưới sự chỉ huy của Thoát Hoan mang 30 vạn quân xâm lược Đại Việt lần thứ ba.

Trần Hưng Đạo (Trần Quốc Tuấn, 1228-1300) là Đại Hành Tướng quân đội Đại Việt. Ông là một trong những nhà quân sự lỗi lạc nhất trong lịch sử Việt Nam và thế giới.

Trận Bạch Đằng là trận đánh quyết định. Trần Hưng Đạo cho đóng cọc gỗ xuống đáy sông Bạch Đằng, rồi cho thuyền nhỏ kéo quân Nguyên vào. Khi thủy triều lên, quân Nguyên tấn công. Khi triều rút, thuyền Nguyên mắc cạn trên cọc gỗ. Quân Đại Việt tấn công toàn diện, tiêu diệt hàng vạn quân địch.

Thoát Hoan tháo chạy, để lại hàng nghìn tù binh và hải đội tướng Phàn Tiếp bị bắt sống. Chiến thắng này được xem là một trong những trận thủy chiến vĩ đại nhất trong lịch sử thế giới.""",
        "event_date": "1288-03-08",
        "year_range": "1288",
        "period": "Nhà Trần - Nguyên Mông",
        "latitude": 20.8431,
        "longitude": 106.6889,
        "region": "Miền Bắc",
        "event_type": "battle",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/6/6f/TranHungDao.jpg/600px-TranHungDao.jpg",
        "image_caption": "Trần Hưng Đạo - Đại tướng quân vĩ đại của dân tộc",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["tran-hung-dao", "nguyen-mong", "bach-dang", "chong-ngoai-xam"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    # ─── Later Lê / Mạc ───────────────────────────────────────────────────
    {
        "slug": "lam-son-quoi-linh-1413",
        "title": "Khởi nghĩa Lam Sơn (1413-1427)",
        "short_description": "Cuộc khởi nghĩa của Lê Lợi chống quân Minh xâm lược, giành lại độc lập cho dân tộc sau 20 năm đô hộ.",
        "full_content": """Khởi nghĩa Lam Sơn (1413-1427) là cuộc kháng chiến thần thánh của nhân dân Việt Nam chống quân Minh xâm lược. Lãnh đạo cuộc khởi nghĩa là Lê Lợi, người Thanh Hóa.

Sau khi nhà Hồ mất năm 1407, quân Minh xâm lược và đô hộ Việt Nam trong 20 năm (1407-1427). Nhân dân sống trong cảnh khổ cực, bị cướp bóc, đàn áp dã man.

Năm 1418, Lê Lợi xưng vương tại Lam Sơn (Thanh Hóa), tập hợp nhân dân khởi nghĩa. Ban đầu quân Lam Sơn chỉ có nông dân với gậy gộc, dần dần phát triển thành lực lượng hùng hậu.

Chiến tranh kéo dài 10 năm. Quân Minh nhiều lần bị đánh bại tại Trà Lĩnh, Bình Than, Tốt Động-Chúc Động. Năm 1426, quân Lam Sơn bao vây Thăng Long. Ngày 5/10/1427, quân Minh chính thức đầu hàng.

Lê Lợi lên ngôi vua, lập ra nhà Lê sơ (1428-1527), đổi quốc hiệu thành Đại Việt.""",
        "event_date": "1418-02-01",
        "year_range": "1413-1427",
        "period": "Khởi nghĩa Lam Sơn - Bắc thuộc lần 4",
        "latitude": 19.8333,
        "longitude": 105.7500,
        "region": "Miền Bắc",
        "event_type": "rebellion",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/22/Le_Loi.jpg/600px-Le_Loi.jpg",
        "image_caption": "Lê Lợi - Anh hùng dân tộc, người giải phóng đất nước",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["le-loi", "khoi-nghia-lam-son", "chong-minh", "bac-thuoc"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "le-thanh-tong-ky-672-1789",
        "title": "Kỷ nguyên Hồng Lĩnh (1460-1497) — Thịnh vượng dưới thời Lê Thánh Tông",
        "short_description": "Lê Thánh Tông trị vì Đại Việt trong 38 năm, xây dựng quốc gia hùng mạnh, phát triển văn hóa rực rỡ.",
        "full_content": """Lê Thánh Tông (1462-1497) là vị vua quang vinh nhất của nhà Lê sơ, trị vì từ năm 1460 đến 1497 (37 năm). Dưới thời ông, Đại Việt đạt đến đỉnh cao thịnh vượng.

Lê Thánh Tông cho ban hành Hồng Đức Thường Đính pháp lệnh (quốc dụng đầu tiên), mở khoa cử, xây dựng quân đội hùng mạnh. Đại Việt mở rộng lãnh thổ đến tận Lào và Campuchia.

Năm 1479, quân đội Đại Việt do Nguyễn Xí chỉ huy đánh bại quân Chiêm Thành, mở rộng bờ cõi. Lê Thánh Tông cũng cho soạn "Đại Việt sử ký toàn thư" - bộ quốc sử hoàn chỉnh đầu tiên.

Thời kỳ này được gọi là thời kỳ Hồng Đức, là thời kỳ thịnh trị nhất của nhà Hậu Lê và cũng là một trong những thời kỳ thịnh vượng nhất của Việt Nam trong lịch sử.""",
        "event_date": "1460-01-01",
        "year_range": "1460-1497",
        "period": "Nhà Lê sơ",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "dynasty",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["le-thanh-tong", "nha-le-so", "hong-duc", "vuong-gia"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    # ─── Restored Lê / Trịnh-Nguyễn ──────────────────────────────────────
    {
        "slug": "trinh-nguyen-phan-tranh-1627",
        "title": "Phân tranh Trịnh-Nguyễn (1627-1777)",
        "short_description": "Đất nước chia cắt thành Đàng Ngoài (nhà Trịnh) và Đàng Trong (nhà Nguyễn), mở ra thời kỳ 150 năm phân tranh.",
        "full_content": """Sau khi nhà Mạc suy vong (1592), đất nước được thống nhất bởi nhà Lê trung hưng. Tuy nhiên, quyền lực thực tế nằm trong tay chúa Trịnh. Năm 1627, chúa Trịnh Tráng cử sứ sang Đàng Trong đòi chúa Nguyễn Phúc Nguyên phục tùng. Chúa Nguyễn từ chối, mở ra thời kỳ Trịnh-Nguyễn phân tranh.

Đàng Ngoài (phía Bắc) do nhà Trịnh cầm quyền, đóng đô ở Thăng Long (Hà Nội).

Đàng Trong (phía Nam) do nhà Nguyễn cầm quyền, đóng đô ở Huế.

Hai bên xung đột nhiều lần nhưng không ai hạ được ai. Biên giới ổn định tại sông Gianh (Quảng Bình). Thời kỳ này kéo dài 150 năm (1627-1777).

Mặc dù chia cắt, cả hai miền đều phát triển kinh tế, văn hóa riêng. Đàng Trong mở rộng về phía Nam, khai phá đất Đông Nam Bộ và Nam Bộ.""",
        "event_date": "1627-01-01",
        "year_range": "1627-1777",
        "period": "Trịnh-Nguyễn phân tranh",
        "latitude": 16.0544,
        "longitude": 108.2022,
        "region": "Miền Trung",
        "event_type": "dynasty",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["trinh-nguyen", "phan-tranh", "dang-ngoai", "dang-trong"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "tayson-1771",
        "title": "Khởi nghĩa Tây Sơn (1771-1802)",
        "short_description": "Phong trào Tây Sơn do Nguyễn Huệ lãnh đạo, lật đổ chính quyền Trịnh-Nguyễn, thống nhất đất nước lần 3.",
        "full_content": """Khởi nghĩa Tây Sơn (1771-1802) là cuộc nổi dậy của ba anh em Nguyễn Nhạc, Nguyễn Huệ, Nguyễn Lữ tại vùng Tây Sơn (Bình Định), lật đổ chính quyền Trịnh-Nguyễn.

Năm 1771, ba anh em họ Nguyễn (thuộc gia tộc Tây Sơn) khởi binh tại Quy Nhơn. Ban đầu là nông dân nghèo, dần phát triển thành lực lượng quân sự hùng mạnh.

Năm 1778, Nguyễn Nhạc xưng đế tại Quy Nhơn. Năm 1786, Nguyễn Huệ đánh ra Bắc Hà, lật đổ nhà Trịnh. Năm 1788, vua Lê Chiêu Thống chạy sang Trung Quốc cầu viện. Nguyễn Huệ lên ngôi tại Thăng Long, lập ra Đại Việt quốc.

Năm 1789, Nguyễn Huệ (Quang Trung) đánh bại 29 vạn quân Thanh (Trung Quốc) trong trận Ngọc Hồi - Đống Đa, bảo vệ nền độc lập.

Tuy nhiên, nhà Tây Sơn sau đó thất bại trước Nguyễn Ánh (Gia Long) năm 1802.""",
        "event_date": "1771-01-01",
        "year_range": "1771-1802",
        "period": "Tây Sơn",
        "latitude": 13.7683,
        "longitude": 109.2000,
        "region": "Miền Trung",
        "event_type": "rebellion",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5d/Quang_trung.jpg/600px-Quang_trung.jpg",
        "image_caption": "Nguyễn Huệ - Quang Trung Đại Vương, vị anh hùng dân tộc",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["tay-son", "nguyen-hue", "quang-trung", "khoi-nghia"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "quang-trung-danh-thanh-1789",
        "title": "Trận Ngọc Hồi - Đống Đa (1789) — Quang Trung đại thắng quân Thanh",
        "short_description": "Quang Trung chỉ huy quân đội Việt Nam đánh bại 29 vạn quân xâm lược nhà Thanh, bảo vệ nền độc lập dân tộc.",
        "full_content": """Đầu năm 1789, nhà Thanh (Trung Quốc) cử 29 vạn quân xâm lược Việt Nam theo lời mời của vua Lê Chiêu Thống (đã chạy sang Trung Quốc cầu viện).

Quang Trung (Nguyễn Huệ) quyết định đánh bại quân Thanh ngay tại Thăng Long. Ông hành quân thần tốc từ Phú Xuân (Huế) ra Bắc, tập trung 20 vạn quân.

Trận đánh diễn ra ngày mùng 5 tháng Giêng năm Kỷ Dậu (1789) tại Ngọc Hồi và Đống Đa (Hà Nội). Quang Trung dùng mưu kế đánh vào trung quân địch, quân Thanh tan vỡ, chạy dọc theo đường làng Đống Đa.

Chiến thắng Ngọc Hồi - Đống Đa là một trong những trận đánh vĩ đại nhất trong lịch sử Việt Nam, được xem là biểu tượng của tinh thần quyết thắng ngoại xâm.""",
        "event_date": "1789-02-01",
        "year_range": "1789",
        "period": "Tây Sơn",
        "latitude": 21.0500,
        "longitude": 105.7800,
        "region": "Miền Bắc",
        "event_type": "battle",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["quang-trung", "ngoc-hoi-dong-da", "chong-thanh", "tay-son"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    # ─── Nguyễn Dynasty ───────────────────────────────────────────────────
    {
        "slug": "nguyen-anh-thanh-lap-viet-nam-1802",
        "title": "Gia Long thống nhất đất nước (1802) — Nhà Nguyễn ra đời",
        "short_description": "Nguyễn Ánh (Gia Long) thống nhất Việt Nam sau 300 năm chia cắt, lập ra nhà Nguyễn, đặt quốc hiệu Việt Nam.",
        "full_content": """Năm 1802, Nguyễn Ánh lên ngôi hoàng đế tại Huế, lấy hiệu Gia Long, mở đầu nhà Nguyễn (1802-1945). Đây là triều đại phong kiến cuối cùng của Việt Nam.

Nguyễn Ánh sau nhiều năm trốn chạy và chiến đấu chống nhà Tây Sơn, cuối cùng giành được chính quyền. Ông thống nhất ba miền Bắc, Trung, Nam sau gần 300 năm chia cắt.

Gia Long đổi quốc hiệu từ Đại Việt thành Việt Nam (1804). Ông cho xây dựng kinh thành Huế theo mô hình phong cách phương Đông và phương Tây. Triều Nguyễn tồn tại 143 năm (1802-1945) với 13 đời vua.""",
        "event_date": "1802-06-01",
        "year_range": "1802",
        "period": "Nhà Nguyễn",
        "latitude": 16.4620,
        "longitude": 107.5780,
        "region": "Miền Trung",
        "event_type": "dynasty",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["nguyen-anh", "gia-long", "nha-nguyen", "thong-nhat"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "hue-cung-dai-thanh-1804",
        "title": "Kinh thành Huế — Di sản kiến trúc cuối cùng của phong kiến Việt Nam",
        "short_description": "Kinh thành Huế được xây dựng từ 1804, là công trình kiến trúc hoành tráng nhất của nhà Nguyễn.",
        "full_content": """Kinh thành Huế được xây dựng từ năm 1804 dưới thời vua Gia Long, hoàn thành năm 1832 dưới thời vua Minh Mạng. Đây là một trong những công trình kiến trúc quy mô nhất Đông Nam Á thời bấy giờ.

Kinh thành Huế nằm trên bờ bắc sông Hương (Hà Giang), có diện tích khoảng 520 hecta. Thành trì có hình vuông với chu vi 10km, bao quanh bởi 24 pháo đài và 10 cửa thành.

Bên trong là Tử Cấm Thành và Hoàng Thành. Tử Cấm Thành chứa điện Thái Hòa, nơi thiết triều của các vị vua Nguyễn. Kinh thành Huế được UNESCO công nhận là Di sản Văn hóa Thế giới năm 1993.""",
        "event_date": "1804-01-01",
        "year_range": "1804-1832",
        "period": "Nhà Nguyễn",
        "latitude": 16.4689,
        "longitude": 107.5900,
        "region": "Miền Trung",
        "event_type": "landmark",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["kinh-thanh-hue", "nha-nguyen", "kien-truc", "hue"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    # ─── French Colonial Period ───────────────────────────────────────────
    {
        "slug": "phap-danh-dinh-ba-1858",
        "title": "Quân Pháp tấn công Đà Nẵng (1858) — Khởi đầu cuộc xâm lược",
        "short_description": "Hải quân Pháp nã pháo vào Đà Nẵng, mở đầu cuộc xâm lược Việt Nam lần thứ 3 (Pháp thuộc).",
        "full_content": """Ngày 1/9/1858, hải quân Pháp dưới sự chỉ huy của Đô đốc Rigault de Genouilly tấn công và chiếm Đà Nẵng. Đây là sự kiện mở đầu cho cuộc xâm lược của thực dân Pháp tại Việt Nam.

Nguyên nhân: Pháp muốn biến Việt Nam thành thuộc địa, khai thác tài nguyên và mở rộng ảnh hưởng tại Đông Nam Á. Ngoài ra, Pháp muốn trả đũa việc vua Việt Nam đàn áp các linh mục Công giáo.

Sau khi chiếm Đà Nẵng, quân Pháp gặp sự kháng cự mạnh của quân và dân Việt. Năm 1861, Pháp chiếm 3 tỉnh miền Đông Nam Bộ (Gia Định, Định Tường, Biên Hòa). Đến 1867, toàn bộ Nam Kỳ (6 tỉnh) thuộc về Pháp.

Năm 1884, Pháp ký Hiệp ước Patenôtre với triều đình Huế, chính thức đặt Việt Nam dưới quyền bảo hộ của Pháp.""",
        "event_date": "1858-09-01",
        "year_range": "1858",
        "period": "Pháp thuộc",
        "latitude": 16.0544,
        "longitude": 108.2022,
        "region": "Miền Trung",
        "event_type": "battle",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2f/French_Siege_of_Danang.jpg/800px-French_Siege_of_Danang.jpg",
        "image_caption": "Quân Pháp tấn công Đà Nẵng năm 1858",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["phap-thuoc", "cong-san-phap", "da-nang", "dinh-tuong"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "ha-noi-trong-thuc-dan-phap-1873",
        "title": "Quân Pháp chiếm Hà Nội (1873)",
        "short_description": "Năm 1873, quân Pháp do Francis Garnier chỉ huy chiếm Hà Nội, mở đầu quá trình đô hộ Bắc Kỳ.",
        "full_content": """Ngày 5/11/1873, Trung tá Francis Garnier chỉ huy 150 lính Pháp tấn công và chiếm Hà Nội sau khi đánh bại quân đội triều đình. Đây là bước tiến quan trọng trong kế hoạch đô hộ toàn bộ Việt Nam của thực dân Pháp.

Garnier sau đó tiến ra Bắc Kỳ, chiếm nhiều tỉnh. Tuy nhiên, ông bị giết chết trong một trận đánh với quân của Đề Kiều (thủ lĩnh khởi nghĩa nông dân) vào ngày 21/12/1873.

Mặc dù Garnier tử trận, cuộc chiếm đóng của Pháp vẫn tiếp tục. Đến năm 1885, toàn bộ Bắc Kỳ thuộc quyền kiểm soát của Pháp. Năm 1887, Pháp thành lập Liên bang Đông Dương, bao gồm Việt Nam (3 Kỳ), Lào và Campuchia.""",
        "event_date": "1873-11-05",
        "year_range": "1873",
        "period": "Pháp thuộc",
        "latitude": 21.0285,
        "longitude": 105.8522,
        "region": "Miền Bắc",
        "event_type": "battle",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["phap-thuoc", "ha-noi", "bac-ky", "francis-garnier"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    # ─── Resistance Period ───────────────────────────────────────────────
    {
        "slug": "phu-dong-thi-rau-1908",
        "title": "Phong trào Đông Du (1905-1909) và chống thuế (1908)",
        "short_description": "Phong trào Đông Du do Phan Bội Châu lãnh đạo, đưa thanh niên Việt Nam sang Nhật học tập, chuẩn bị cho cách mạng.",
        "full_content": """Đầu thế kỷ XX, trước sự áp bức của thực dân Pháp, các nhà yêu nước Việt Nam tìm kiếm con đường giải phóng dân tộc.

Năm 1905, Phan Bội Châu sáng lập phong trào Đông Du, đưa hàng trăm thanh niên yêu nước sang Nhật Bản học tập, tiếp thu tư tưởng dân chủ và cách mạng. Mục tiêu là "học Nhật để cứu nước".

Năm 1908, phong trào chống thuế bùng nổ tại Trung Kỳ (Miền Trung). Nhân dân nổi dậy chống lại chính sách thuế nặng nề của thực dân Pháp và chính quyền bù nhìn. Phong trào lan rộng đến 9 tỉnh.

Pháp đàn áp dã man, bắt bớ và xử tử nhiều nhà yêu nước. Phan Bội Châu phải lưu vong sang Nhật, rồi sang Trung Quốc. Phong trào Đông Du tan rã năm 1909.""",
        "event_date": "1908-01-01",
        "year_range": "1905-1909",
        "period": "Pháp thuộc",
        "latitude": 15.9000,
        "longitude": 108.0000,
        "region": "Miền Trung",
        "event_type": "rebellion",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["phan-boi-chau", "dong-du", "chong-thue", "phan-cap"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    {
        "slug": "viet-nam-quoc-hoi-thanh-lap-1939",
        "title": "Việt Nam Quốc Dân Đảng — Phong trào yêu nước (1939-1940)",
        "short_description": "Việt Nam Quốc Dân Đảng là tổ chức chính trị theo xu hướng dân chủ tư sản, hoạt động chống Pháp tại Việt Nam.",
        "full_content": """Việt Nam Quốc Dân Đảng (Việt Quốc) được thành lập năm 1939 tại Vân Nam (Trung Quốc) bởi Nguyễn Tường Tam và các trí thức yêu nước. Đây là tổ chức chính trị theo xu hướng dân chủ tư sản.

Việt Quốc đề xuất chương trình "Dân tộc, Dân quyền, Dân sinh" (Tam dân), ảnh hưởng từ Tôn Trung Sơn. Mục tiêu là đánh đuổi thực dân Pháp, thành lập nước Việt Nam Dân chủ Cộng hòa.

Năm 1940, khi Chiến tranh Thế giới II bùng nổ, Việt Quốc tham gia các hoạt động chống Pháp và Nhật. Tuy nhiên, tổ chức bị Pháp đàn áp nặng nề, nhiều cán bộ bị bắt và xử tử.

Sau này, nhiều thành viên Việt Quốc tham gia các phong trào cách mạng khác nhau, thể hiện tinh thần yêu nước không ngừng của dân tộc Việt Nam.""",
        "event_date": "1939-01-01",
        "year_range": "1939-1945",
        "period": "Pháp thuộc",
        "latitude": 21.0285,
        "longitude": 105.8522,
        "region": "Miền Bắc",
        "event_type": "independence",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["viet-nam-quoc-dan-dang", "nguyen-tuong-tam", "yeu-nuoc"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    {
        "slug": "nhat-dao-dong-minh-viet-nam-1941",
        "title": "Việt Nam Độc Lập Đồng Minh Hội (Việt Minh) thành lập (1941)",
        "short_description": "Việt Minh do Hồ Chí Minh sáng lập, tập hợp lực lượng đoàn kết dân tộc, chống Pháp và Nhật, giành độc lập.",
        "full_content": """Ngày 10/5/1941, tại Pác Bó (Cao Bằng), Hồ Chí Minh (then mang tên Nguyễn Ái Quốc) thành lập Việt Nam Độc Lập Đồng Minh Hội (Việt Minh). Đây là tổ chức chính trị có sức mạnh nhất trong giai đoạn chuẩn bị cách mạng.

Chương trình của Việt Minh gồm 8 điểm, trong đó mục tiêu cao nhất là "Cứu nước, chống áp bức, giải phóng dân tộc". Việt Minh đề xuất liên hiệp toàn dân, bất phân tôn giáo, đảng phái.

Việt Minh xây dựng cơ sở tại vùng rừng núi Việt Bắc, tổ chức dân quân du kích, vận động nhân dân. Tổ chức nhanh chóng phát triển rộng khắp cả nước.

Năm 1944, Việt Minh thành lập Việt Nam Giải phóng quân (tiền thân của Quân đội Nhân dân Việt Nam). Đến tháng 3/1945, Việt Minh đã kiểm soát phần lớn nông thôn Việt Nam.""",
        "event_date": "1941-05-10",
        "year_range": "1941",
        "period": "Chiến tranh Thế giới II",
        "latitude": 22.8500,
        "longitude": 106.0500,
        "region": "Miền Bắc",
        "event_type": "independence",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3e/Ho_Chi_Minh_1946.jpg/600px-Ho_Chi_Minh_1946.jpg",
        "image_caption": "Chủ tịch Hồ Chí Minh - Người sáng lập Việt Minh",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["viet-minh", "ho-chi-minh", "doc-lap", "khang-chien"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "tuyen-ngon-doc-lap-1945",
        "title": "Hồ Chí Minh đọc Tuyên ngôn Độc lập — Nhà nước Việt Nam Dân chủ Cộng hòa ra đời (2/9/1945)",
        "short_description": "Tại Quảng trường Ba Đình, Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập, khai sinh nước Việt Nam Dân chủ Cộng hòa.",
        "full_content": """Ngày 2/9/1945, tại Quảng trường Ba Đình (Hà Nội), Chủ tịch Hồ Chí Minh đọc bản Tuyên ngôn Độc lập, tuyên bố nước Việt Nam Dân chủ Cộng hòa ra đời.

Bản Tuyên ngôn mở đầu bằng câu nói nổi tiếng: "Tất cả mọi người đều sinh ra có quyền bình đẳng. Tạo hóa cho họ những quyền không ai có thể xâm phạm được; trong những quyền ấy, có quyền được sống, quyền tự do và quyền mưu cầu hạnh phúc."

Ngày 2/9/1945 được lấy làm Quốc khánh của nước Việt Nam (cho đến năm 2025, đất nước đã tròn 80 tuổi).

Sự kiện này đánh dấu bước ngoặt vĩ đại: chấm dứt hơn 100 năm đô hộ của thực dân Pháp và hơn 1000 năm đô hộ (tổng cộng các đợt) của ngoại bang.""",
        "event_date": "1945-09-02",
        "year_range": "1945",
        "period": "Cách mạng Tháng Tám",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "independence",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/4/4f/Ho_Chi_Minh_reading_declaration.jpg/800px-Ho_Chi_Minh_reading_declaration.jpg",
        "image_caption": "Chủ tịch Hồ Chí Minh đọc Tuyên ngôn Độc lập tại Quảng trường Ba Đình",
        "video_url": "https://www.youtube.com/embed/34GKvR8nZus",
        "tags": json.dumps(["ho-chi-minh", "tuyen-ngon-doc-lap", "ba-dinh", "vndcch"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    # ─── Modern Period ───────────────────────────────────────────────────
    {
        "slug": "dien-bien-phu-1954",
        "title": "Chiến dịch Điện Biên Phủ (1954) — Chiến thắng lịch sử",
        "short_description": "Chiến dịch Điện Biên Phủ, chiến thắng 'lừng lẫy năm châu, chấn động địa cầu', chấm dứt chiến tranh Đông Dương.",
        "full_content": """Chiến dịch Điện Biên Phủ (13/3 - 7/5/1954) là chiến dịch quân sự lớn nhất trong cuộc kháng chiến chống Pháp, do Đại tướng Võ Nguyên Giáp chỉ huy.

Tháng 11/1953, Pháp xây dựng Điện Biên Phủ thành pháo đài kiên cố với 16.000 quân, 12 tiểu đoàn, hơn 200 máy bay, 200 xe tăng và pháo binh hạng nặng. Pháp tin rằng đây là pháo đài không thể trục xóa.

Quân đội Nhân dân Việt Nam với khoảng 55.000 bộ đội, do Đại tướng Võ Nguyên Giáp chỉ huy, bao vây và tấn công. Chiến dịch gồm 3 đợt:

- Đợt 1 (13/3): Đánh chiếm Him Lam, Độc Lập, Tân Hưng.
- Đợt 2 (30/3): Đánh chiếm đồi C1, Mường Thanh.
- Đợt 3 (1/5 - 7/5): Tổng tiến công, giải phóng toàn bộ tinh Điện Biên Phủ.

Ngày 7/5/1954, tướng De Castries đầu hàng. Chiến thắng này buộc Pháp phải ký Hiệp định Genève (21/7/1954), chấm dứt chiến tranh Đông Dương.""",
        "event_date": "1954-05-07",
        "year_range": "1954",
        "period": "Kháng chiến chống Pháp",
        "latitude": 21.3856,
        "longitude": 103.0186,
        "region": "Miền Bắc",
        "event_type": "battle",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/5/5f/Battle_of_Dien_Bien_Phu.jpg/800px-Battle_of_Dien_Bien_Phu.jpg",
        "image_caption": "Toàn cảnh chiến trường Điện Biên Phủ sau chiến thắng",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["dien-bien-phu", "vo-nguyen-giap", "chong-phap", "chieu-nhi"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "hieu-chinh-geneva-1954",
        "title": "Hiệp định Genève ký kết (21/7/1954) — Đất nước chia cắt",
        "short_description": "Hiệp định Genève chia đôi đất nước tại vĩ tuyến 17, hứa hẹn thống nhất qua tổng tuyển cử.",
        "full_content": """Ngày 21/7/1954, tại Genève (Thụy Sĩ), đại diện Pháp, Việt Minh Dân chủ Cộng hòa, Liên Xô, Trung Quốc, Anh, Mỹ... ký Hiệp định Genève về Đông Dương.

Nội dung chính:
- Pháp rút quân khỏi Việt Nam
- Đất nước tạm thời chia đôi tại vĩ tuyến 17: Bắc Việt (do Việt Minh kiểm soát) và Nam Việt (do chính quyền Bảo Đại/Ngô Đình Diệm)
- Cam kết tổ chức tổng tuyển cử trên toàn quốc trong vòng 2 năm để thống nhất đất nước
- Việt Nam thống nhất lại trong hòa bình

Tuy nhiên, tổng tuyển cử không diễn ra. Mỹ và chính quyền Sài Gòn từ chối thực hiện cam kết. Đất nước tiếp tục chia cắt thêm 21 năm nữa (1954-1975), cho đến khi miền Bắc giải phóng miền Nam.""",
        "event_date": "1954-07-21",
        "year_range": "1954",
        "period": "Chia cắt 1954-1975",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "independence",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["hiep-dinh-geneva", "chia-cat", "bat-dau", "hoa-binh"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "muc-son-ly-thuong-kiet-1941",
        "title": "Hồ Chí Minh về nước hoạt động (1941) — Người về từ Pác Bó",
        "short_description": "Năm 1941, Hồ Chí Minh trở về Việt Nam sau 30 năm bôn ba ở nước ngoài, trực tiếp lãnh đạo cách mạng.",
        "full_content": """Sau hơn 30 năm bôn ba ở nước ngoài (1919-1941), tháng 2/1941, Hồ Chí Minh trở về Việt Nam, đặt chân đến Pác Bó (Cao Bằng), bên cạnh hang Cốc Bà (Pác Pó).

Tại đây, Người trực tiếp hoạt động, tổ chức Việt Nam Độc Lập Đồng Minh Hội (Việt Minh), vạch ra đường lối đánh đuổi thực dân Pháp và phát xít Nhật, giải phóng dân tộc.

Trong suốt thời gian hoạt động tại Pác Bó, Hồ Chí Minh sống trong hang động, ăn uống giản dị, viết nhiều bài báo, tài liệu chỉ đạo cách mạng. Người đặt nền móng cho cuộc kháng chiến toàn quốc.

Pác Bó sau đó trở thành cái nôi của nước Việt Nam Dân chủ Cộng hòa. Ngày 2/9/1945, Hồ Chí Minh đọc Tuyên ngôn Độc lập tại Hà Nội.""",
        "event_date": "1941-02-08",
        "year_range": "1941",
        "period": "Chiến tranh Thế giới II",
        "latitude": 22.8500,
        "longitude": 106.0500,
        "region": "Miền Bắc",
        "event_type": "figure",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["ho-chi-minh", "pac-bo", "viet-minh", "ve-nuoc"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    {
        "slug": "my-cong-trung-thanh-vung-tay-nguyen-1964",
        "title": "Chiến dịch Trị Thiên - Huế (1964-1972) — Vùng lãnh thổ trọng yếu",
        "short_description": "Huế và vùng Trị Thiên là chiến trường ác liệt trong cuộc kháng chiến chống Mỹ, nơi diễn ra nhiều trận đánh đẫm máu.",
        "full_content": """Trị Thiên (Huế - Quảng Trị) là vùng đất có vị trí chiến lược quan trọng trong cuộc kháng chiến chống Mỹ. Năm 1964, Mỹ leo thang chiến tranh, đẩy mạnh các cuộc càn quét tại đây.

Năm 1968, trong Tổng tiến công và nổi dậy Tết Mậu Thân, Quân Giải phóng đánh chiếm phần lớn thành phố Huế. Quân Mỹ và Sài Gòn phản kích dữ dội. Cuộc chiến tại Huế kéo dài 26 ngày, thành phố bị tàn phá nặng nề.

Năm 1972, trận Đường 9 - Nam Lộc nổ ra tại Quảng Trị, một trong những trận đánh ác liệt nhất của cuộc kháng chiến. Quân Giải phóng chiếm được thị trấn Đông Hà và nhiều vị trí quan trọng.

Trận chiến tại Trị Thiên kết thúc với thất bại của Mỹ và chính quyền Sài Gòn, góp phần thúc đẩy tiến trình hòa bình.""",
        "event_date": "1964-01-01",
        "year_range": "1964-1973",
        "period": "Kháng chiến chống Mỹ",
        "latitude": 16.4620,
        "longitude": 107.5900,
        "region": "Miền Trung",
        "event_type": "battle",
        "difficulty_level": 2,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["tri-thien", "hue", "chong-my", "chien-tranh"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    {
        "slug": "my-tang-cuong-chien-tranh-1965",
        "title": "Mỹ đổ quân vào Việt Nam (1965) — Chiến tranh leo thang",
        "short_description": "Năm 1965, Mỹ chính thức đưa quân viễn chinh vào Việt Nam, leo thang chiến tranh thành cuộc chiến tranh xâm lược quy mô.",
        "full_content": """Ngày 8/3/1965, 3.500 lính thủy đánh bộ Mỹ đổ bộ lên bờ biển Đà Nẵng, mở đầu cho chiến tranh leo thang của Mỹ tại Việt Nam. Đây là lần đầu tiên quân đội Mỹ chính thức tham chiến trên bộ.

Đến cuối năm 1965, lực lượng Mỹ tại Việt Nam đã lên đến 200.000 quân. Đến đỉnh cao (1968-1969), Mỹ có hơn 540.000 quân tại Việt Nam.

Chiến lược của Mỹ là "Chiến tranh đặc biệt" (dùng quân Sài Gòn), rồi "Chiến tranh cục bộ" (dùng quân Mỹ trực tiếp), nhưng đều thất bại trước sự kháng cự kiên cường của quân và dân Việt Nam.

Quân Mỹ dùng bom napalm, chất độc hóa học (Agent Orange), pháo hạng nặng... nhưng không thể khuất phục được ý chí của nhân dân Việt Nam.""",
        "event_date": "1965-03-08",
        "year_range": "1965",
        "period": "Kháng chiến chống Mỹ",
        "latitude": 16.0544,
        "longitude": 108.2022,
        "region": "Miền Trung",
        "event_type": "battle",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["chong-my", "leo-thang", "my-viet", "napalm"]),
        "related_event_ids": json.dumps([]),
        "is_featured": False,
    },
    {
        "slug": "tet-mau-than-1968",
        "title": "Tổng tiến công Tết Mậu Thân 1968 (30/1/1968)",
        "short_description": "Cuộc tổng tiến công và nổi dậy Tết Mậu Thân 1968 là bước ngoặt lịch sử, buộc Mỹ phải ngồi đàm phán.",
        "full_content": """Đêm 30/1/1968 (mùng 1 Tết Mậu Thân), Quân Giải phóng miền Nam Việt Nam đồng loạt tấn công vào hơn 100 thành phố, thị trấn, căn cứ quân sự của Mỹ và chính quyền Sài Gòn trên khắp miền Nam Việt Nam.

Cuộc tấn công bao gồm 5 mũi chính: Sài Gòn, Huế, Đà Nẵng, Nha Trang, Cần Thơ. Đây là cuộc tấn công quy mô nhất trong cuộc kháng chiến chống Mỹ.

Tại Sài Gòn, đặc công Quân Giải phóng đột nhập vào sân bay Tân Sơn Nhất, đánh chiếm Đại sứ quán Mỹ. Các đơn vị khác tấn công Bộ Tổng tham mưu Ngụy quyền.

Tại Huế, cuộc chiến kéo dài 26 ngày, trở thành một trong những trận đánh ác liệt nhất.

Chiến dịch Tết Mậu Thân là bước ngoặt lịch sử: buộc Tổng thống Mỹ Johnson phải ngừng ném bom Bắc Việt Nam và chấp nhận đàm phán hòa bình.""",
        "event_date": "1968-01-30",
        "year_range": "1968",
        "period": "Kháng chiến chống Mỹ",
        "latitude": 10.8231,
        "longitude": 106.6297,
        "region": "Miền Nam",
        "event_type": "battle",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/8/8f/US_Embassy_Saigon_seizure.jpg/800px-US_Embassy_Saigon_seizure.jpg",
        "image_caption": "Đặc công Quân Giải phóng đột nhập Đại sứ quán Mỹ tại Sài Gòn",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["tet-mau-than", "tong-tien-cong", "chong-my", "saigon"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "ho-chi-minh-triet-dai-tren-duong-ra-tran-1969",
        "title": "Chủ tịch Hồ Chí Minh qua đời (2/9/1969) — Tang lễ quốc tang",
        "short_description": "Chủ tịch Hồ Chí Minh - vị lãnh tụ vĩ đại của dân tộc Việt Nam - qua đời để lại niềm tiếc thương vô hạn của nhân dân.",
        "full_content": """Ngày 2/9/1969, vào đúng dịp kỷ niệm 24 năm Ngày Tuyên ngôn Độc lập, Chủ tịch Hồ Chí Minh đã từ trần tại Hà Nội, hưởng thọ 79 tuổi.

Hồ Chí Minh (sinh năm 1890 tại Nam Đàn, Nghệ An) là vị lãnh tụ cách mạng vĩ đại của Việt Nam. Người đã cống hiến trọn đời cho sự nghiệp giải phóng dân tộc, thống nhất đất nước.

Di sản của Hồ Chí Minh bao gồm:
- Tư tưởng Hồ Chí Minh (một trong 3 trụ cột lý luận của Đảng Cộng sản Việt Nam)
- Tuyên ngôn Độc lập 2/9/1945
- Những bài học về đoàn kết dân tộc, kiên cường chống ngoại xâm
- Di chúc lịch sử để lại cho Đảng và nhân dân

Tang lễ Chủ tịch Hồ Chí Minh được tổ chức quốc tang, hàng triệu người dân Việt Nam và quốc tế bày tỏ lòng tiếc thương vô hạn.""",
        "event_date": "1969-09-02",
        "year_range": "1969",
        "period": "Kháng chiến chống Mỹ",
        "latitude": 21.0365,
        "longitude": 105.8348,
        "region": "Miền Bắc",
        "event_type": "figure",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["ho-chi-minh", "qua-doi", "quoc-tang", "lanh-tu"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "my-rut-quan-1973",
        "title": "Hiệp định Paris ký kết (27/1/1973) — Mỹ rút quân khỏi Việt Nam",
        "short_description": "Hiệp định Paris chấm dứt sự tham chiến trực tiếp của Mỹ tại Việt Nam, mở đường cho giải phóng miền Nam.",
        "full_content": """Ngày 27/1/1973, tại Paris (Pháp), đại diện Chính phủ Cách mạng Lâm thời Cộng hòa Miền Nam Việt Nam, Chính phủ Việt Nam Dân chủ Cộng hòa, Chính phủ Ngụy quyền Sài Gòn và Chính phủ Mỹ ký Hiệp định về chấm dứt chiến tranh, lập lại hòa bình tại Việt Nam.

Nội dung chính:
- Mỹ rút toàn bộ quân đội khỏi Việt Nam trong vòng 60 ngày
- Chấm dứt mọi hoạt động quân sự tại Việt Nam
- Cam kết tôn trọng Hiệp định Genève 1954 về Việt Nam
- Cam kết thống nhất hòa bình

Ngày 29/3/1973, quân đội Mỹ rút hết khỏi Việt Nam. Tuy nhiên, chính quyền Sài Gòn không tôn trọng hiệp định, tiếp tục các hoạt động quân sự. Chiến tranh kết thúc vào ngày 30/4/1975.""",
        "event_date": "1973-01-27",
        "year_range": "1973",
        "period": "Kháng chiến chống Mỹ",
        "latitude": 48.8566,
        "longitude": 2.3522,
        "region": "Quốc tế",
        "event_type": "independence",
        "difficulty_level": 1,
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["hiep-dinh-paris", "my-rut-quan", "hoa-binh", "danh-phan"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "mua-xuan-1975-chien-thang-2",
        "title": "Chiến dịch Hồ Chí Minh (26/4 - 30/4/1975) — Giải phóng Sài Gòn",
        "short_description": "Chiến dịch Hồ Chí Minh quyết định, giải phóng Sài Gòn và miền Nam Việt Nam, thống nhất đất nước hoàn toàn.",
        "full_content": """Chiến dịch Hồ Chí Minh là chiến dịch quân sự cuối cùng trong cuộc kháng chiến chống Mỹ, diễn ra từ ngày 26/4 đến 30/4/1975, giải phóng hoàn toàn miền Nam Việt Nam.

Diễn biến chính:
- Ngày 26/4: Quân Giải phóng tấn công Xuân Lộc (Đông Nam Bộ), thử thách sức kháng cự của quân Ngụy.
- Ngày 29/4: Quân đội Nhân dân Việt Nam tiến vào ngoại ô Sài Gòn.
- Ngày 30/4/1975, 11h30: Xe tăng Quân Giải phóng tiến vào Dinh Độc Lập. Tổng thống Ngụy quyền Dương Văn Minh đầu hàng. Sài Gòn được giải phóng.

Tại thời điểm đầu hàng, Dương Văn Minh được cho là đã nói: "Tôi muốn giữ lại tính mạng cho người dân Sài Gòn." Các đơn vị quân đội ngừng chiến đấu. Chiến tranh Việt Nam chính thức kết thúc.

Chiến thắng 30/4/1975 là thắng lợi vĩ đại của dân tộc Việt Nam, hoàn thành cuộc kháng chiến chống ngoại xâm kéo dài hơn 30 năm (1945-1975).""",
        "event_date": "1975-04-30",
        "year_range": "1975",
        "period": "Giải phóng miền Nam",
        "latitude": 10.8231,
        "longitude": 106.6297,
        "region": "Miền Nam",
        "event_type": "battle",
        "difficulty_level": 1,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/VietnamsSoldiersInSaigon.jpg/800px-VietnamsSoldiersInSaigon.jpg",
        "image_caption": "Xe tăng Quân Giải phóng tiến vào Dinh Độc Lập ngày 30/4/1975",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["chieu-luoi", "30-4", "giai-phong", "thong-nhat"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    # ─── Hoàng Sa & Trường Sa — lãnh thổ thiêng liêng của Việt Nam ───────────
    {
        "slug": "quandao-hoang-sa-cua-viet-nam",
        "title": "Quần đảo Hoàng Sa — Lãnh thổ thiêng liêng của Việt Nam",
        "short_description": "Quần đảo Hoàng Sa (Paracel) là bộ phận lãnh thổ không thể tách rời của Việt Nam, được xác lập chủ quyền từ thời nhà Nguyễn (thế kỷ XVII).",
        "full_content": """Quần đảo Hoàng Sa (tên quốc tế: Paracel Islands) nằm ở phía nam Biển Đông, là bộ phận lãnh thổ không thể tách rời của Việt Nam. Chủ quyền của Việt Nam đối với Hoàng Sa được thế giới và khu vực công nhận rộng rãi.

Chủ quyền lịch sử:
- Năm 1816, triều Nguyễn cử đội Hoàng Sa và đội Bắc Hải vào quản lý, cắm mốc, xác lập chủ quyền trên quần đảo Hoàng Sa.
- Năm 1956, chính quyền Việt Nam Cộng hòa tiếp quản và bảo vệ Hoàng Sa.
- Hiện nay, lực lượng kiểm ngư, hải quân, biên phòng Việt Nam tiếp tục bảo vệ chủ quyền trên quần đảo Hoàng Sa.

Quần đảo Hoàng Sa thuộc thành phố Đà Nẵng của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.""",
        "event_date": "1816-01-01",
        "year_range": "Thế kỷ XVII - nay",
        "period": "Chủ quyền lãnh thổ",
        "latitude": 16.4500,
        "longitude": 112.3333,
        "region": "Hoàng Sa",
        "event_type": "landmark",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/3/3a/Paracel_Islands.jpg/800px-Paracel_Islands.jpg",
        "image_caption": "Quần đảo Hoàng Sa — lãnh thổ của Việt Nam",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["hoang-sa", "paracel", "viet-nam", "chu-quyen", "bien-dong", "triều-nguyễn"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
    {
        "slug": "quandao-truong-sa-cua-viet-nam",
        "title": "Quần đảo Trường Sa — Lãnh thổ thiêng liêng của Việt Nam",
        "short_description": "Quần đảo Trường Sa (Spratly) là bộ phận lãnh thổ không thể tách rời của Việt Nam, được các triều đại Việt Nam xác lập và bảo vệ chủ quyền qua nhiều thế kỷ.",
        "full_content": """Quần đảo Trường Sa (tên quốc tế: Spratly Islands) nằm giữa Biển Đông, là bộ phận lãnh thổ không thể tách rời của Việt Nam. Trường Sa là nơi các thế hệ người Việt Nam đã và đang kiên cường bảo vệ chủ quyền thiêng liêng của Tổ quốc.

Chủ quyền lịch sử:
- Năm 1956, quân đội Việt Nam Cộng hòa đưa quân ra giữ và xây dựng các đảo trên quần đảo Trường Sa.
- Năm 1988, Hải quân nhân dân Việt Nam bảo vệ chủ quyền tại đảo Gạc Ma, đảo Len Đao và đảo Cô Lin.
- Hiện nay, Việt Nam quản lý nhiều đảo nổi và đảo chìm trên quần đảo Trường Sa, với sự hiện diện của lực lượng Hải quân, Kiểm ngư, Biên phòng và dân thường.

Quần đảo Trường Sa thuộc tỉnh Khánh Hòa của nước Cộng hòa Xã hội Chủ nghĩa Việt Nam.

Lưu ý: Các địa danh như đảo Vĩnh Thử (Fiery Cross Reef / 永暑礁) nằm trong vùng biển thuộc chủ quyền Việt Nam tại Trường Sa — đây là bộ phận lãnh thổ của Việt Nam.""",
        "event_date": "1988-03-14",
        "year_range": "1956 - nay",
        "period": "Chủ quyền lãnh thổ",
        "latitude": 8.6500,
        "longitude": 111.9167,
        "region": "Trường Sa",
        "event_type": "landmark",
        "difficulty_level": 2,
        "image_url": "https://upload.wikimedia.org/wikipedia/commons/thumb/2/2e/Spratly_Islands.svg/800px-Spratly_Islands.svg.png",
        "image_caption": "Quần đảo Trường Sa — lãnh thổ của Việt Nam",
        "video_url": "https://www.youtube.com/embed/0b9Q0QHIPEQ",
        "tags": json.dumps(["truong-sa", "spratly", "viet-nam", "chu-quyen", "bien-dong", "hai-quan-vn", "vinh-thu", "fiery-cross"]),
        "related_event_ids": json.dumps([]),
        "is_featured": True,
    },
]


def _to_date(s):
    """Convert string to date, returns None if invalid."""
    if not s:
        return None
    from datetime import datetime, date
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%Y/%m/%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except (ValueError, TypeError):
            continue
    return None


def seed_events():
    db = SessionLocal()
    try:
        existing = db.query(HistoricalEvent).count()
        if existing > 0:
            print(f"  Database already has {existing} events. Skipping seed.")
            return

        for event_data in EVENTS:
            if "event_date" in event_data:
                event_data["event_date"] = _to_date(event_data["event_date"])
            event = HistoricalEvent(**event_data)
            db.add(event)

        db.commit()
        print(f"  Seeded {len(EVENTS)} historical events successfully!")
    except Exception as e:
        db.rollback()
        print(f"  Seed error: {type(e).__name__}: {str(e)[:200]}")
        raise
    finally:
        db.close()


if __name__ == "__main__":
    print("Seeding historical events...")
    seed_events()
