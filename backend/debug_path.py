from pathlib import Path
p = Path(__file__).resolve().parent.parent.parent / "CobraQ_v3.html"
print("Path:", p)
print("Exists:", p.exists())
