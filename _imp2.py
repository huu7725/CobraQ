import sys
sys.path.insert(0, "d:/CobraQ/backend")
try:
    from app.api.router import api_router
    print("IMPORT OK")
    # Try the dependency
    from app.core.security import decode_token
    print("DECODE OK")
except Exception as e:
    print(f"ERROR: {e}")
    import traceback; traceback.print_exc()
