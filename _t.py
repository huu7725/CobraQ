import requests, json

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]

# Test stats
r2 = requests.get(f"{BASE}/api/stats", headers={"x-user-id": "admin@test.com"})
print("Stats:", r2.status_code, json.dumps(r2.json(), ensure_ascii=False)[:300])
