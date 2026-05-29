import os, json

base = "d:/CobraQ/data/users"
print("Directories:")
for d in os.listdir(base):
    fp = os.path.join(base, d)
    if os.path.isdir(fp):
        files = os.listdir(fp)
        print(f"  {d}/ ({files})")
