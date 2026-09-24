"""Download AmbientCG PBR sets (CC0) into tex/<ID>/ at the given resolution. Usage: acg_get.py 2K ID ID ..."""
import requests, sys, os, io, zipfile
from concurrent.futures import ThreadPoolExecutor
res = sys.argv[1].upper(); ids = sys.argv[2:]
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'tex')
def get(aid):
    d = os.path.join(OUT, aid)
    if os.path.isdir(d) and any(f.endswith('_Color.jpg') for f in os.listdir(d)):
        return aid, 'cached'
    r = requests.get("https://ambientcg.com/api/v2/full_json", params={"id": aid, "include": "downloadData"}, timeout=30).json()
    a = r['foundAssets'][0]
    link = None
    for folder in (a.get('downloadFolders') or {}).values():
        for cat in (folder.get('downloadFiletypeCategories') or {}).values():
            for dl in (cat.get('downloads') or []):
                if dl.get('attribute') == f'{res}-JPG':
                    link = dl.get('downloadLink') or dl.get('rawLink')
    if not link:
        return aid, 'NO LINK'
    if not link.startswith('http'): link = 'https://ambientcg.com' + link
    z = zipfile.ZipFile(io.BytesIO(requests.get(link, timeout=300).content))
    os.makedirs(d, exist_ok=True)
    n = 0
    for m in z.namelist():
        if m.lower().endswith(('.jpg', '.png')) and 'NormalDX' not in m and '_PREVIEW' not in m.upper():
            open(os.path.join(d, os.path.basename(m)), 'wb').write(z.read(m)); n += 1
    return aid, f'{n} maps'
with ThreadPoolExecutor(6) as ex:
    for aid, st in ex.map(get, ids): print(aid, st, flush=True)
