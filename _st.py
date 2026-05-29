import requests, json

BASE = "http://127.0.0.1:8000"
r = requests.post(f"{BASE}/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
token = r.json()["access_token"]
h = {"Authorization": f"Bearer {token}"}

r = requests.get(f"{BASE}/api/stats", headers=h)
print("Status:", r.status_code)
print("Response:", json.dumps(r.json(), ensure_ascii=False, indent=2))
