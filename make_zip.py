import zipfile
from pathlib import Path

root = Path('/root/forschung')
exclude_dirs = {'.venv', '__pycache__', '.git', 'node_modules', 'cache', '.ipynb_checkpoints'}
exclude_exts = {'.pyc', '.png', '.jpg', '.jpeg', '.gif', '.mp4', '.db', '.parquet', '.log'}

out = root / 'vibe-trading.zip'
count = 0
with zipfile.ZipFile(out, 'w', zipfile.ZIP_DEFLATED) as z:
    for p in root.rglob('*'):
        if any(part in exclude_dirs for part in p.parts):
            continue
        if p.suffix.lower() in exclude_exts:
            continue
        if p.name == 'vibe-trading.zip':
            continue
        if p.is_file():
            try:
                z.write(p, p.relative_to(root))
                count += 1
            except Exception:
                pass

print(f'ZIP erstellt: {out}')
print(f'Dateien enthalten: {count}')
print(f'Größe: {out.stat().st_size / 1024:.0f} KB')
