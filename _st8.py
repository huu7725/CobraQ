import json

with open("d:/CobraQ/backend/data/users_store.json", encoding="utf-8") as f:
    users = json.load(f)
print("Users:")
for email, data in users.items():
    print(f"  {email}")
