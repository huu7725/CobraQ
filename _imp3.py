import sys
sys.path.insert(0, "d:/CobraQ/backend")
try:
    from app.api.router import api_router, USERS_DIR, user_dir
    print("IMPORT OK")
    print(f"USERS_DIR: {USERS_DIR}")
    uid = "admin@test.com"
    d = user_dir(uid)
    print(f"user_dir for {uid}: {d}")
    print(f"Exists: {d.exists()}")
except Exception as e:
    import traceback; traceback.print_exc()
