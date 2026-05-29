import requests, json, io, sys
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = requests.get(f"{BASE}/api/groups/my", headers=h)
groups = r.json()["groups"]
code = groups[0]["code"]
print(f"Testing with group: {code}")

r = requests.get(f"{BASE}/api/stats", headers=h)
files = r.json()["files"]
file_id = files[0]["id"]

# Test 1: Assign with num_questions=5, time_limit=10
print("\n1. Gan de voi 5 cau, 10 phut...")
r = requests.post(f"{BASE}/api/groups/{code}/files",
    json={"file_id": file_id, "num_questions": 5, "time_limit": 10}, headers=h)
print(f"   Status: {r.status_code} -> {r.json().get('message','?')}")

# Verify group files
r = requests.get(f"{BASE}/api/groups/{code}/files", headers=h)
gf = r.json()["files"]
print(f"   Group files: {len(gf)}")
for f in gf:
    print(f"   - {f['name']}: num={f.get('num_questions')}, time={f.get('time_limit')}")

# Test 2: Start quiz as student (no files) - should get 5 questions, 10 min
print("\n2. HS bat dau quiz (khong co file, nhung co group_code)...")
r = requests.get(f"{BASE}/api/quiz/start?file_id={file_id}&group_code={code}")
print(f"   Status: {r.status_code}")
d = r.json()
print(f"   Questions: {d.get('total', 0)}")
print(f"   Time limit: {d.get('time_limit', 'N/A')} seconds")
print(f"   num_questions: {d.get('num_questions', 'N/A')}")

# Cleanup
print("\n3. Cleanup...")
r = requests.delete(f"{BASE}/api/groups/{code}/files/{file_id}", headers=h)
print(f"   Status: {r.status_code}")

print("\nDONE")
