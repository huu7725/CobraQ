import os, json

base = "d:/CobraQ/backend/data/users"
print("Backend user dirs:")
for d in os.listdir(base):
    fp = os.path.join(base, d)
    if os.path.isdir(fp):
        files = os.listdir(fp)
        print(f"  {d}/: {files}")
        for fn in files:
            fpath = os.path.join(fp, fn)
            if fn.endswith('.json') and fn != 'history.json':
                with open(fpath, encoding="utf-8") as f:
                    data = json.load(f)
                if isinstance(data, list):
                    print(f"    {fn}: {len(data)} questions")
                elif isinstance(data, dict):
                    wa = sum(1 for q in data.get("questions", []) if q.get("answer") in "ABCD")
                    print(f"    {fn}: {len(data.get('questions', []))} questions, {wa} with answer")
