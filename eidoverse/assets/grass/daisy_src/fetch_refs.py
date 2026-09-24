# fetch_refs.py — reference photos for the createFlora `daisy` species.
# Wikimedia Commons (throttled, UA header), 1600 px thumbnails, licence
# metadata recorded in sources.json beside the images, in work/refs/daisy/ (not committed).
#   python eidoverse/assets/grass/daisy_src/fetch_refs.py [key ...]
import json, time, urllib.request, urllib.parse, os, sys

UA = 'EidoverseRefBot/1.0 (https://github.com/anima-research/eidoverse-video; daisy species lookdev)'
ROOT = os.path.dirname(os.path.abspath(__file__))
while ROOT != os.path.dirname(ROOT) and not os.path.exists(os.path.join(ROOT, 'eido.py')):
    ROOT = os.path.dirname(ROOT)
HERE = os.path.join(ROOT, 'work', 'refs', 'daisy')
os.makedirs(HERE, exist_ok=True)
FILES = {
    # head, front / macro
    'head_front_01': 'Leucanthemum vulgare 17.jpg',
    'head_front_02': 'Leucanthemum vulgare qtl1.jpg',
    'head_front_03': 'Marguerite Leucanthemum vulgare-06-2012.jpg',
    'head_front_04': 'Margarita (Leucanthemum vulgare), centro de Tallinn, Estonia, 2012-08-05, DD 01.JPG',
    'head_group_05': '20220519 Leucanthemum vulgare.jpg',
    'head_group_06': 'Leucanthemum vulgare hp01.jpg',
    'head_side_07': '20210612 Leucanthemum vulgare.jpg',
    'head_side_08': 'Leucanthemum vulgare 18.jpg',
    # leaves
    'leaf_basal_01': 'Leucanthemum vulgare leaf5 (14446324630).jpg',
    'leaf_basal_02': 'Leucanthemum vulgare leaf7 (14446354459).jpg',
    'leaf_stem_01': 'Leucanthemum vulgare stem leaf1 (14630838824).jpg',
    'leaf_stem_02': 'Leucanthemum vulgare stem leaf2 (14632966775).jpg',
    # buds
    'bud_01': '20170512Leucanthemum vulgare1.jpg',
    'bud_02': 'Leucanthemum vulgare 2021-06-05 7810.jpg',
    # habitat / meadow
    'meadow_01': 'Margeritenwiese - panoramio.jpg',
    'meadow_02': 'Margeritenwiese am Radweg nach Speyer - panoramio.jpg',
    # colour variants
    'orange_01': 'Dimorphotheca sinuata 1DS-II 7819.jpg',
    'orange_02': 'Dimorphotheca sinuata - par Mickael Schauli.jpg',
    'pink_01': 'Tanacetum coccineum 2016-05-17 0703.jpg',
    'pink_02': 'Tanacetum coccineum.jpg',
}

def api(params):
    q = urllib.parse.urlencode({**params, 'format': 'json'})
    req = urllib.request.Request('https://commons.wikimedia.org/w/api.php?' + q, headers={'User-Agent': UA})
    for attempt in range(6):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:
            print('[refs] api retry', e); time.sleep(15 + attempt * 10)
    raise RuntimeError('commons api unavailable')

def main(only=None):
    srcp = os.path.join(HERE, 'sources.json')
    sources = json.load(open(srcp)) if os.path.exists(srcp) else {}
    for key, title in FILES.items():
        if only and key not in only:
            continue
        out = os.path.join(HERE, key + '.jpg')
        if os.path.exists(out) and key in sources:
            continue
        d = api({'action': 'query', 'titles': 'File:' + title, 'prop': 'imageinfo',
                 'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1600})
        page = next(iter(d['query']['pages'].values()))
        if 'imageinfo' not in page:
            print('[refs] MISSING', title); continue
        ii = page['imageinfo'][0]
        url = ii.get('thumburl') or ii['url']
        meta = ii.get('extmetadata', {})
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(req, timeout=120).read(); break
            except Exception as e:
                print('[refs] retry', key, e); time.sleep(8)
        else:
            continue
        open(out, 'wb').write(data)
        sources[key] = {
            'title': title, 'page': ii.get('descriptionurl'), 'url': url,
            'artist': meta.get('Artist', {}).get('value', ''),
            'license': meta.get('LicenseShortName', {}).get('value', ''),
        }
        print('[refs]', key, len(data) // 1024, 'KB', sources[key]['license'])
        json.dump(sources, open(srcp, 'w'), indent=1)
        time.sleep(9)

if __name__ == '__main__':
    main(sys.argv[1:] or None)
