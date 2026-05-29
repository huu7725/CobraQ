import requests, json, os

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]

# Check what user_dir resolves to
uid = "admin@test.com"
import re
sanitized = re.sub(r"[^\w]", "_", uid)
print(f"Sanitized: {sanitized}")

# Check files exist
import os
base = f"d:/CobraQ/data/users/{sanitized}"
print(f"Base dir: {base}")
print(f"Exists: {os.path.exists(base)}")
if os.path.exists(base):
    print(f"Contents: {os.listdir(base)}")
    fi = os.path.join(base, "files_index.json")
    if os.path.exists(fi):
        with open(fi, encoding="utf-8") as f:
            data = json.load(f)
        print(f"Files index: {json.dumps(data, ensure_ascii=False, indent=2)[:500]}")
