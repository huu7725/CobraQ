import requests, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = requests.get(f"{BASE}/api/groups/my", headers=h)
code = r.json()["groups"][0]["code"]
r = requests.get(f"{BASE}/api/stats", headers=h)
file_id = r.json()["files"][0]["id"]

# Set time_limit to 15 minutes
r = requests.put(f"{BASE}/api/groups/{code}/files/{file_id}", json={"num_questions": 5, "time_limit": 15}, headers=h)
print(f"Set: {r.json()}")

# Check
r = requests.get(f"{BASE}/api/groups/{code}/files", headers=h)
for f in r.json().get("files", []):
    if f["file_id"] == file_id:
        print(f"DB: num={f.get('num_questions')}, time={f.get('time_limit')} (minutes)")

# Start quiz
r = requests.get(f"{BASE}/api/quiz/start?file_id={file_id}&group_code={code}")
d = r.json()
print(f"API: time_limit={d.get('time_limit')} (seconds)")
print(f"Frontend use: {d.get('time_limit')}s / 60 = {d.get('time_limit',0)//60} phut")
