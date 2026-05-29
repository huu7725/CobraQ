import requests

r = requests.post("http://127.0.0.1:8000/api/auth/login", json={"email": "admin@test.com", "password": "admin123"})
print("Login:", r.status_code, r.json().get("user", {}).get("role"))
token = r.json()["access_token"]

r2 = requests.get("http://127.0.0.1:8000/api/users/", headers={"Authorization": "Bearer " + token})
print("Users:", r2.status_code)
print(r2.text[:1000])

r3 = requests.get("http://127.0.0.1:8000/api/admin/stats", headers={"Authorization": "Bearer " + token})
print("Admin Stats:", r3.status_code)
print(r3.text[:500])
