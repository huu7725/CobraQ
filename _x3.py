import requests

r = requests.post("http://127.0.0.1:8000/api/auth/login",
    json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Delete old history file
r2 = requests.delete("http://127.0.0.1:8000/api/files/history", headers=h)
print("Delete:", r2.status_code)

# Re-upload
import json
path = r"D:\CobraQ\thuvienhoclieu.com-De-cuong-on-tap-cuoi-HK2-Lich-su-12-Canh-dieu-24-25.docx"
with open(path, "rb") as f:
    files = {"file": ("history.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Lich su 12"}
    r3 = requests.post("http://127.0.0.1:8000/api/files/upload", files=files, data=data, headers=h)

with open("d:/CobraQ/_r3.json", "w", encoding="utf-8") as f:
    f.write(json.dumps({"status": r3.status_code, "body": r3.text}, ensure_ascii=False))
print("Upload:", r3.status_code)
