# 🚀 Hướng dẫn Deploy CobraQ lên Render.com (Free Tier)

## ✅ Tại sao chọn Render?

| | Render Free | HuggingFace Free |
|---|---|---|
| **Docker SDK** | ✅ Đầy đủ | ⚠️ Chỉ một số tài khoản |
| **HTTPS** | ✅ Tự động | ✅ Tự động |
| **Custom domain** | ✅ Free | ✅ Free |
| **Memory** | 512 MB | 16 GB |
| **CPU** | 0.1 (chia sẻ) | 2 vCPU |
| **Disk persistent** | ❌ (cần $7/mo) | ❌ (cần paid) |
| **Sleep** | Sau 15 phút idle | Sau 48h idle |
| **Build** | Auto từ GitHub | Auto từ Git |

→ Render tốt nhất cho CobraQ vì:
- Docker SDK luôn có
- Sleep sớm hơn → ít tốn tài nguyên
- Custom domain dễ (quan trọng nếu muốn branding)

## 📋 Checklist trước khi bắt đầu

- [ ] Tài khoản GitHub (để push code)
- [ ] Tài khoản Render.com (đăng ký miễn phí qua GitHub)
- [ ] Anthropic API key: https://console.anthropic.com/
- [ ] Đã có `Dockerfile`, `requirements.txt`, `render.yaml` ở root repo

## Bước 1 — Push code lên GitHub

```bash
cd "C:\Users\TUF\Desktop\CobraQ"
git add .
git commit -m "Add Render deployment files"
git push origin main
```

Nếu chưa có remote GitHub:
1. Tạo repo mới trên https://github.com/new (đặt tên `cobraq`, **KHÔNG tick** "Add README")
2. Push:
```bash
git remote add origin https://github.com/<username>/cobraq.git
git branch -M main
git push -u origin main
```

⚠️ **Quan trọng**: file `.env`, `backend/data/`, `__pycache__/` **phải có trong `.gitignore`** để không commit data local. Tôi đã thêm `.dockerignore`, nhưng bạn cũng nên check `.gitignore`.

## Bước 2 — Tạo Web Service trên Render

1. Vào https://dashboard.render.com/
2. Click **New +** → **Blueprint** (tự động đọc `render.yaml`)
3. Connect GitHub repo `cobraq` của bạn
4. Render sẽ tự động detect `render.yaml` và tạo service `cobraq`
5. Click **Apply** để deploy

**Cách 2 (thủ công nếu không dùng Blueprint):**
1. **New +** → **Web Service**
2. Connect GitHub repo
3. Điền:
   - **Name**: `cobraq`
   - **Region**: `Singapore` (gần VN) hoặc `Oregon`
   - **Branch**: `main`
   - **Runtime**: **Docker**
   - **Plan**: **Free**
4. Click **Create Web Service**

## Bước 3 — Set Environment Variables (BẮT BUỘC)

Vào tab **Environment** của service vừa tạo:

| Key | Value |
|---|---|
| `ANTHROPIC_API_KEY` | `sk-ant-...` (lấy từ console.anthropic.com) |
| `SECRET_KEY` | random 64 chars (chạy `[guid]::NewGuid().ToString()+"x64"` trong PowerShell nhiều lần, nối lại) |
| `DATA_DIR` | `/app/data` (đã set sẵn trong `render.yaml`) |
| `PORT` | `10000` (Render tự set, nhưng có thể add thủ công) |

Click **Save Changes** → Render tự động rebuild + redeploy.

## Bước 4 — Đợi Deploy

Vào tab **Logs**, đợi build xong (~5-10 phút lần đầu vì phải cài packages + poppler).

Khi thấy:
```
INFO:     Uvicorn running on http://0.0.0.0:10000
INFO:     Application startup complete.
```

→ Service live tại `https://cobraq.onrender.com` (URL có thể khác nếu đặt tên khác).

## Bước 5 — Test

- **Web app**: https://cobraq.onrender.com → giao diện CobraQ
- **API docs**: https://cobraq.onrender.com/docs → Swagger UI
- **Health**: https://cobraq.onrender.com/health → `{"status":"ok"}`

## 🔄 Update code

Mỗi lần `git push`, Render tự động rebuild & redeploy (~3-5 phút).

```bash
git add .
git commit -m "Update feature X"
git push
```

## 🌐 Custom Domain (Optional)

1. Mua domain (vd `cobraq.vn`) tại Namecheap/Cloudflare/Pavietnam (~10-15$/năm)
2. Trên Render: tab **Settings** → **Custom Domains** → **Add Custom Domain** → nhập `cobraq.vn`
3. Render sẽ cho bạn CNAME record, thêm vào DNS provider
4. HTTPS tự động được cấp bởi Render (Let's Encrypt)

## ⚠️ Hạn chế của Free Tier

### 1. Service sleep sau 15 phút idle
- Lần truy cập đầu sau sleep phải đợi ~30-60s để cold-start.
- **Workaround** (miễn phí): dùng cron-job.org ping mỗi 14 phút.
- Hoặc upgrade plan **Starter** $7/mo (no sleep).

### 2. Data KHÔNG persistent
- Mỗi lần redeploy (do push code) → user/files/câu hỏi **mất hết**.
- **Workaround**:
  - Upgrade plan (có persistent disk)
  - Hoặc migrate sang external DB (Supabase Postgres free)
  - Hoặc accept mất data (chỉ dùng demo)

### 3. Resource limit
- 512 MB RAM, 0.1 CPU → **chậm** cho AI operations.
- AI Fill 1 câu mất ~5-10s (có thể lâu hơn nếu nhiều user cùng lúc).
- Đủ cho demo & test nhỏ.

## 🐛 Troubleshooting

### Build fail: "Could not find a version that satisfies the requirement"

Pin version trong `requirements.txt`:
```txt
anthropic==0.105.2
fastapi==0.115.0
```

### Build fail: "executor failed running [/bin/sh -c ...]"

Check log chi tiết. Thường do:
- `apt-get update` fail → retry
- Memory không đủ → reduce dependencies

### Runtime: "Address already in use"

Render tự set `PORT=10000`. Dockerfile đã đọc từ env. Nếu vẫn lỗi, hardcode `--port 10000` trong Dockerfile CMD.

### AI Fill không hoạt động (response "AI disabled" hoặc 500)

1. Check tab **Environment** → `ANTHROPIC_API_KEY` đã set chưa
2. Test bằng cách gọi `POST /api/files/ai/fill-answer` trong `/docs`
3. Check log Render → có lỗi từ Anthropic SDK không

### CORS issues (frontend không gọi được API)

`main.py` đã set `allow_origins=["*"]` → không lỗi CORS. Nếu vẫn lỗi, hard refresh `Ctrl+Shift+R`.

### Service crash loop

Vào tab **Logs** → xem error cuối. Thường là:
- Thiếu env var → set lại
- `requirements.txt` có package không tương thích → pin version

## 💡 Tips sau khi deploy thành công

1. **Monitor**: tab **Metrics** của Render có CPU/RAM/disk usage real-time
2. **Auto-deploy**: bật sẵn (mặc định ON với Blueprint)
3. **Preview environments**: mỗi PR tạo 1 service tạm (free tier vẫn count vào limit)
4. **Custom domain**: Settings → Custom Domains
5. **Backup data** (nếu dùng persistent disk): Render chưa hỗ trợ auto-backup, phải tự snapshot qua Render CLI

## 🎯 Khi nào nên upgrade?

| Tình huống | Plan |
|---|---|
| Cần persistent data | **Starter** $7/mo + persistent disk $1/GB/mo |
| Cần không sleep (24/7) | **Starter** $7/mo |
| Cần tốc độ AI Fill nhanh | **Standard** $25/mo (2GB RAM) |
| Cần scale cho nhiều user (1000+) | **Pro** $85/mo (auto-scale) |

Đối với demo/test cá nhân → Free tier là đủ. Sau khi có user thật → upgrade khi cần.