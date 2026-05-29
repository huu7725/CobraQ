import requests, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = requests.get(f"{BASE}/api/groups/my", headers=h)
groups = r.json()["groups"]
code = groups[0]["code"]
r = requests.get(f"{BASE}/api/stats", headers=h)
file_id = r.json()["files"][0]["id"]

# Assign
r = requests.post(f"{BASE}/api/groups/{code}/files", json={"file_id": file_id, "num_questions": 5, "time_limit": 15}, headers=h)
print(f"Assign: {r.status_code} -> {r.text[:100]}")

# PUT update
r = requests.put(f"{BASE}/api/groups/{code}/files/{file_id}", json={"num_questions": 10, "time_limit": 0}, headers=h)
print(f"PUT: {r.status_code}")
print(f"Response: '{r.text[:200]}'")

# Verify
r = requests.get(f"{BASE}/api/groups/{code}/files", headers=h)
gf = r.json()["files"]
for f in gf:
    if f["file_id"] == file_id:
        print(f"Verified: num={f.get('num_questions')}, time={f.get('time_limit')}")
