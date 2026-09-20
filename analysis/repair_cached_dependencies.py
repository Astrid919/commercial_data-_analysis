"""Restore already downloaded wheels from local pip cache; no network access."""
from pathlib import Path
import zipfile, shutil, json
root=Path(__file__).resolve().parents[2]
cache=Path.home()/'AppData/Local/pip/Cache/http-v2'
dest=root/'.runtime'
wanted={'threadpoolctl','wrapt','statsmodels','tzdata'}
found={}
for p in cache.rglob('*.body'):
    if not zipfile.is_zipfile(p):continue
    try:
        with zipfile.ZipFile(p) as z:
            metas=[n for n in z.namelist() if n.endswith('.dist-info/METADATA')]
            if not metas:continue
            name=next((s[6:] for s in z.read(metas[0]).decode().splitlines() if s.startswith('Name: ')), '').lower().replace('-','_')
            if name not in wanted:continue
            if name in found and p.stat().st_mtime<found[name][0]:continue
            found[name]=(p.stat().st_mtime,str(p))
    except (OSError,zipfile.BadZipFile):continue
for name,(_,path) in found.items():
    with zipfile.ZipFile(path) as z:
        for item in z.infolist():
            target=(dest/item.filename).resolve()
            if not target.is_relative_to(dest.resolve()):raise ValueError(item.filename)
            if '__pycache__' in item.filename or item.is_dir():continue
            target.parent.mkdir(parents=True,exist_ok=True)
            with z.open(item) as src,open(target,'wb') as out:shutil.copyfileobj(src,out)
    print('Restored cached dependency',name,flush=True)
print('Found',list(found),flush=True)
