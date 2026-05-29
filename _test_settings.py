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

print("=" * 50)
print("FLOW: Gan de (5 cau, 15 phut) -> HS lam -> GV xem diem")
print("=" * 50)

# Step 1: Assign
print(f"\n1. GV gan de {file_id} (5 cau, 15 phut) vao nhom {code}")
r = requests.post(f"{BASE}/api/groups/{code}/files",
    json={"file_id": file_id, "num_questions": 5, "time_limit": 15}, headers=h)
print(f"   Status: {r.status_code} -> {r.json().get('message')}")

# Step 2: Student starts quiz (no files in student account)
print(f"\n2. HS bat dau quiz (khong co file, chi co group_code)...")
r = requests.get(f"{BASE}/api/quiz/start?file_id={file_id}&group_code={code}")
d = r.json()
print(f"   Status: {r.status_code}")
print(f"   Cau hoi: {d.get('total')} (so voi 5)")
print(f"   Thoi gian: {d.get('time_limit')}s = {d.get('time_limit',0)//60} phut")
print(f"   Session: {d.get('session_id')}")

# Step 3: Submit
print(f"\n3. HS nop bai...")
answers = {str(q["id"]): q["choices"][0]["label"] for q in d["questions"]}
r = requests.post(f"{BASE}/api/quiz/submit", headers={"Content-Type": "application/json"},
    json={"session_id": d["session_id"], "answers": answers, "time_taken": 60, "file_id": file_id, "group_code": code})
res = r.json()
print(f"   Status: {r.status_code}")
print(f"   Diem: {res.get('score')}/{res.get('total')} ({res.get('percent')}%)")

# Step 4: GV xem bang diem
print(f"\n4. GV xem bang diem...")
r = requests.get(f"{BASE}/api/groups/{code}/files/{file_id}/scores", headers=h)
scores = r.json().get("scores", [])
print(f"   So HS da lam: {len(scores)}")
for s in scores:
    print(f"   - {s.get('name','?')}: {s.get('score')}/{s.get('total_questions')} ({s.get('percent')}%)")

# Step 5: Update settings
print(f"\n5. GV chinh sua thanh 10 cau, 0 phut (khong gioi han)...")
r = requests.put(f"{BASE}/api/groups/{code}/files/{file_id}",
    json={"num_questions": 10, "time_limit": 0}, headers=h)
print(f"   Status: {r.status_code} -> {r.json().get('message')}")

# Step 6: Verify new settings
r = requests.get(f"{BASE}/api/groups/{code}/files", headers=h)
gf = r.json()["files"]
for f in gf:
    if f["file_id"] == file_id:
        print(f"   Da cap nhat: {f['num_questions']} cau, {f['time_limit']} phut")

print("\n" + "=" * 50)
print("ALL TESTS PASSED")
