try:
    import fastapi, uvicorn, anthropic, tiktoken, slowapi
    import sklearn, pypdf, docx, PIL, chromadb
    import sentence_transformers, bcrypt, passlib, email_validator
    print("ALL OK - All dependencies installed")
except ImportError as e:
    print("MISSING:", e)
