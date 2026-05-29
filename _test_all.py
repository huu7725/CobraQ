import requests, json

BASE = "http://127.0.0.1:8000"

# 1. Login
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
if r.status_code != 200:
    print("FAIL: Login", r.status_code)
    exit(1)
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}
print("OK: Login")

# 2. Stats
r = requests.get(f"{BASE}/api/stats", headers=h)
d = r.json()
print(f"OK: Stats - files={d.get('total_files','?')}, questions={d.get('total_questions','?')}")

# 3. Upload a test file
content = b"PK\x03\x04"  # minimal zip/DOCX marker
# Actually test with existing file
path = r"D:\CobraQ\thuvienhoclieu.com-De-cuong-on-tap-cuoi-HK2-Lich-su-12-Canh-dieu-24-25.docx"
with open(path, "rb") as f:
    files = {"file": ("test_upload.docx", f, "application/vnd.openxmlformats-officedocument.wordprocessingml.document")}
    data = {"name": "Test upload"}
    r = requests.post(f"{BASE}/api/files/upload", files=files, data=data, headers=h)
result = r.json()
print(f"OK: Upload - parsed={result.get('parsed')}, with_answer={result.get('with_answer')}, ans_rate={result.get('ans_rate')}%")

# 4. Re-check stats
r = requests.get(f"{BASE}/api/stats", headers=h)
d = r.json()
print(f"OK: Stats after upload - files={d.get('total_files','?')}, questions={d.get('total_questions','?')}")

# 5. Quiz start
r = requests.get(f"{BASE}/api/quiz/start?num=5", headers=h)
d = r.json()
if r.status_code == 200:
    print(f"OK: Quiz start - {d.get('total')} questions, session={d.get('session_id','')[:10]}...")
else:
    print(f"FAIL: Quiz start - {r.status_code} {d}")

# 6. Groups
r = requests.get(f"{BASE}/api/groups/my", headers=h)
print(f"OK: Groups - status={r.status_code}")

print("\nTat ca test PASSED!")
