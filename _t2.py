import requests, json

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]

r2 = requests.get(f"{BASE}/api/stats", headers={"x-user-id": "admin@test.com"})
print("Status:", r2.status_code)
print("Body:", repr(r2.text[:300]))
