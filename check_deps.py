import ast
import os

reqs = set()
with open('backend/requirements.txt', 'r') as f:
    for line in f:
        line = line.strip().split('==')[0].split('>')[0].split('<')[0].lower().replace('_', '-')
        if line:
            reqs.add(line)

stdlib = set(['os', 'sys', 'math', 'datetime', 'time', 'json', 'logging', 'tempfile', 'pathlib', 'asyncio', 'typing', 're', 'operator', '__future__'])

imports = set()
for root, _, files in os.walk('backend'):
    if 'venv' in root: continue
    for file in files:
        if file.endswith('.py'):
            with open(os.path.join(root, file), 'r') as f:
                try:
                    tree = ast.parse(f.read())
                    for node in ast.walk(tree):
                        if isinstance(node, ast.Import):
                            for alias in node.names:
                                imports.add(alias.name.split('.')[0])
                        elif isinstance(node, ast.ImportFrom):
                            if node.module:
                                imports.add(node.module.split('.')[0])
                except Exception as e:
                    print(f"Error parsing {file}: {e}")

missing = []
for imp in imports:
    if imp in stdlib: continue
    # common mappings
    pkg = imp.lower().replace('_', '-')
    if pkg == 'fitz': pkg = 'pymupdf'
    elif pkg == 'pil': pkg = 'pillow'
    elif pkg == 'dotenv': pkg = 'python-dotenv'
    elif pkg == 'sklearn': pkg = 'scikit-learn'
    
    if pkg not in reqs:
        missing.append((imp, pkg))

print("Missing imports:")
for m in missing:
    print(m)
