import requests, json

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
print("Login:", r.status_code, r.text[:100])
token = r.json()["access_token"]

# Try without auth header
r2 = requests.get(f"{BASE}/api/stats", headers={"x-user-id": "admin@test.com"})
print("Stats no auth:", r2.status_code, r2.text[:200])

# Try with auth header (Authorization)
r3 = requests.get(f"{BASE}/api/stats", headers={"x-user-id": "admin@test.com"})
print("Stats with x-user-id:", r3.status_code, r3.text[:200])

# Quiz start
r4 = requests.get(f"{BASE}/api/quiz/start?num=5", headers={"Authorization": f"Bearer {token}"})
print("Quiz start:", r4.status_code, r4.text[:200])
