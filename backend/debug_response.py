from pathlib import Path
from fastapi.responses import FileResponse

p = Path("D:/CobraQ/CobraQ_v3.html")
print("Path:", p)
print("Exists:", p.exists())
r = FileResponse(p)
print("FileResponse content_type:", r.media_type)
print("FileResponse body[:100]:", r.body[:100])
