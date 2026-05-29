import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from app.core.security import hash_password
from app.db.user_store import user_store
from app.core.audit import audit_log, EventType

email = "admin@test.com"
password = "admin123"
name = "Admin"
role = "admin"

if not user_store.user_exists(email):
    pw_hash = hash_password(password)
    user_store.create_user(email, name, pw_hash, role)
    audit_log.log(EventType.AUTH_REGISTER, user_id=email, role=role)
    print(f"Created admin: {email}")
else:
    # Update role to admin
    user = user_store.get_user(email)
    user["role"] = "admin"
    user_store.save()
    print(f"Updated {email} to admin role")

print(f"Login: {email} / {password}")
