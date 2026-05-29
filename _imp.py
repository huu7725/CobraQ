import sys
sys.path.insert(0, "d:/CobraQ/backend")
try:
    from app.api.router import api_router
    print("IMPORT OK")
except Exception as e:
    print(f"IMPORT ERROR: {e}")
    import traceback; traceback.print_exc()
