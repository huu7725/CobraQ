import re

with open("d:/CobraQ/CobraQ_v3.html", "r", encoding="utf-8") as f:
    html = f.read()

# Extract all script blocks
scripts = re.findall(r'<script>(.*?)</script>', html, re.DOTALL)
print(f"Found {len(scripts)} script blocks")

for i, script in enumerate(scripts):
    lines = script.split('\n')
    for j, line in enumerate(lines):
        # Check for common syntax issues
        stripped = line.strip()
        # Check for unclosed template literals (has ${ but no closing backtick nearby)
        if stripped.startswith('img[src=') or ('${' in stripped and stripped.count('`') % 2 != 0):
            print(f"Script {i}, Line {j+1}: Potential template literal issue")
            print(f"  {stripped[:200]}")
        # Check for line with only closing braces that shouldn't be standalone
        if stripped in ['}', '};', '}}}', '}}};']:
            print(f"Script {i}, Line {j+1}: Orphaned closing brace: {stripped}")
