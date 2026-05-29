import requests

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

# Try without auth header
r2 = requests.get(f"{BASE}/api/stats")
print("Without auth:", r2.status_code, r2.text[:200])

# Try with auth
r3 = requests.get(f"{BASE}/api/stats", headers=h)
print("With auth:", r3.status_code, r3.text[:200])

# Try quiz start
r4 = requests.get(f"{BASE}/api/quiz/start?num=5", headers=h)
print("Quiz start:", r4.status_code, r4.text[:200])
