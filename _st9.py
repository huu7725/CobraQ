import os, json

base = "d:/CobraQ/data/users"
for d in os.listdir(base):
    fp = os.path.join(base, d)
    if os.path.isdir(fp):
        files = os.listdir(fp)
        print(f"{d}/: {files}")
        for fn in files:
            if fn.endswith('.json') and fn != 'history.json':
                with open(os.path.join(fp, fn), encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"  {fn}: {len(data)} questions")
                elif isinstance(data, dict):
                    print(f"  {fn}: keys={list(data.keys())[:5]}")
