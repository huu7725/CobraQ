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

print("=" * 55)
print("FLOW: Gan de (5 cau / 15 ph) -> HS lam -> GV sua (10 cau / 0 ph) -> GV xem")
print("=" * 55)

# 1. Assign
r = requests.post(f"{BASE}/api/groups/{code}/files", json={"file_id": file_id, "num_questions": 5, "time_limit": 15}, headers=h)
print(f"\n1. Gan de: {r.status_code} -> {r.json().get('message')}")

# 2. HS starts quiz
r = requests.get(f"{BASE}/api/quiz/start?file_id={file_id}&group_code={code}")
d = r.json()
print(f"2. HS lam bai: {d.get('total')} cau, {d.get('time_limit')}s ({d.get('time_limit',0)//60} ph)")

# 3. Submit
r = requests.post(f"{BASE}/api/quiz/submit", headers={"Content-Type": "application/json"},
    json={"session_id": d["session_id"], "answers": {str(q["id"]): q["choices"][0]["label"] for q in d["questions"]}, "time_taken": 60, "file_id": file_id, "group_code": code})
res = r.json()
print(f"3. HS nop: {res.get('score')}/{res.get('total')} ({res.get('percent')}%)")

# 4. GV xem diem
r = requests.get(f"{BASE}/api/groups/{code}/files/{file_id}/scores", headers=h)
scores = r.json().get("scores", [])
print(f"4. GV xem: {len(scores)} HS da lam")

# 5. GV sua settings
r = requests.put(f"{BASE}/api/groups/{code}/files/{file_id}", json={"num_questions": 10, "time_limit": 0}, headers=h)
print(f"5. GV sua: {r.status_code} -> num={r.json().get('num_questions')}, time={r.json().get('time_limit')} ph")

# 6. Verify
r = requests.get(f"{BASE}/api/groups/{code}/files", headers=h)
for f in r.json().get("files", []):
    if f["file_id"] == file_id:
        print(f"6. Verify: num={f.get('num_questions')}, time={f.get('time_limit')} ph")

print("\n" + "=" * 55)
print("ALL PASSED")
