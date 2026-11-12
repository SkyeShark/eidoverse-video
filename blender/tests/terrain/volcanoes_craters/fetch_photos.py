"""Reference photographs of package 9's places from Wikimedia Commons, for the photo-matched renders (judging in 3D:
a hillshade hides wall heights, benches and skylines; a photograph from the ground or an aircraft shows them).

    python blender/tests/terrain/volcanoes_craters/fetch_photos.py [--place mount_fuji] [--list]

For each place, Commons searches (QUERIES) are run through the public API; a candidate is kept only when it is a
photograph (JPEG), carries a camera location (the {{Location}} template: Commons stores it as the file's primary
coordinates), and is under a free licence (CC0, public domain, CC BY, CC BY-SA). The ones picked by hand after
looking (PICKS: title, and what the view shows) are downloaded at 1600 px wide into
blender/tests/terrain/out/volcanoes_craters/photos/<place>/ with sources.json beside them: per photo the
title, page URL, author, licence and its URL, credit line, camera latitude / longitude (and heading when the
file gives one), the EXIF focal length and 35 mm equivalent, the image size, and the view kind. Data only: images
and JSON, nothing executable. --list prints the candidates of each query (title, licence, camera, focal) to pick
from.
"""
import argparse
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
OUT = os.path.join(TN, 'out', 'volcanoes_craters', 'photos')
API = 'https://commons.wikimedia.org/w/api.php'
UA = 'eidoverse-terrain-reference/1.0 (open-source film toolkit; terrain judging against photographs)'
FREE = ('cc0', 'public domain', 'pd', 'cc by', 'cc-by', 'cc by-sa', 'cc-by-sa')

QUERIES = {
    'mount_fuji': ['Mount Fuji from Lake Kawaguchi', 'Mount Fuji aerial', 'Mount Fuji from Gotemba',
                   'Mount Fuji from Fujinomiya', 'Mount Fuji Hoei crater', 'Mount Fuji from airplane'],
    'crater_lake': ['Crater Lake Wizard Island from rim', 'Crater Lake aerial', 'Crater Lake Watchman',
                    'Crater Lake caldera wall', 'Crater Lake from Garfield Peak'],
    'meteor_crater': ['Meteor Crater rim', 'Meteor Crater aerial', 'Barringer Crater', 'Meteor Crater Arizona'],
    'sp_crater': ['SP Crater', 'SP Crater lava flow', 'S P Crater Arizona', 'San Francisco volcanic field cinder cone'],
}

# picked by hand after looking at the candidates: (title, view kind, what it shows, camera). camera: None takes the
# file's recorded camera location; a dict (lat, lon) replaces it, marked camera_estimated (an aircraft's or an
# unlocated photo's position judged from the image: what is in view, from where, how far below)
PICKS = {
    'mount_fuji': [
        ('File:A view of Mount Fuji from Asagiri Food Park 20241022.jpg', 'ground_west',
         'from the Asagiri plateau 13.7 km west-north-west of the crater, 70 mm: the cone in profile above the '
         'forest, its broad summit, the radial gullies of the west face (Osawa-kuzure the deepest)', None),
        ('File:Fuji Mountain from Kawaguchi Lake Lookout, Japan - panoramio.jpg', 'ground_north',
         'from the north shore of Lake Kawaguchi, 17 km north-north-east: the cone over the lake and the Misaka '
         'foothills', None),
        ('File:Mount Fuji 20120909.jpg', 'ground_southwest',
         'from the hills above Fujinomiya, 20 km south-south-west: the cone over the city and its long lower apron',
         None),
        ('File:Mount Fuji - aerial view - 1394.JPG', 'aerial_north',
         'from an aircraft north-north-east of the summit, looking down the snow-filled radial gullies to the '
         'summit crater', None),
    ],
    'crater_lake': [
        ('File:Crater Lake National Park, OR - Rim Drive View (4).jpg', 'rim_east',
         'from the east rim across the lake: Wizard Island in profile under the west walls, 48 mm', None),
        ('File:Wizard Island, Crater Lake NP,OR 9-06 (14592936418).jpg', 'rim_down',
         'from the rim high above Wizard Island: the cinder cone and its crater on its lava platform, the lake, the '
         'caldera walls behind', dict(lat=42.9462, lon=-122.1694)),
        ('File:Crater Lake from plane 2015 - Oregon.jpg', 'aerial_far',
         'from an airliner about 28 km west-south-west: the caldera and its lake in the eroded edifice', None),
    ],
    'meteor_crater': [
        ('File:Meteor crater site in Arizona 2019.jpg', 'rim_north',
         'from the north rim across the bowl: cliff-banded upper walls, talus and fans, the flat floor, the far '
         'rim, 28 mm', None),
        ('File:Meteor Crater in Arizona viewed from road.jpg', 'plain_north',
         'from the road 4.4 km north: the rim a low ridge on the plain, 69 mm', None),
        ('File:Flying over Meteor Crater, Arizona - panoramio.jpg', 'aerial_southeast',
         'a low aerial from the south-south-east across the crater to the plain', None),
    ],
    # (estimated from the images relative to the cone, whose crater is at 35.5824 N, 111.6320 W: the SP Crater.jpg
    # file's geotag, and the crater floor in the 3DEP tile; the tile itself is centred 1.4 km south of it)
    'sp_crater': [
        ('File:SP Crater.jpg', 'aerial_south',
         'USGS oblique aerial from the south: the cone and its crater, its flow running north across the plateau',
         dict(lat=35.56854, lon=-111.6338)),
        ('File:SP Crater (San Francisco Volcanic Field).jpg', 'ground_southeast',
         'the cone from the plateau, its flanks streaked with gullies under snow, other cones on the horizon',
         dict(lat=35.56554, lon=-111.6188)),
        ('File:Unnamed volcano southeast of SP Crater (San Francisco Volcanic Field, Arizona, USA) 1 '
         '(49135204406).jpg', 'ground_old_cone',
         'an older, lower and rounder cone of the field south-east of SP Crater', dict(lat=35.55654, lon=-111.6018)),
    ],
}


def api(params):
    q = dict(params, format='json', formatversion='2')
    url = API + '?' + urllib.parse.urlencode(q)
    for attempt in range(5):
        try:
            req = urllib.request.Request(url, headers={'User-Agent': UA})
            with urllib.request.urlopen(req, timeout=60) as r:
                return json.loads(r.read().decode('utf-8'))
        except urllib.error.HTTPError as e:                     # 429: Commons asks for a slower pace
            if e.code != 429 or attempt == 4:
                raise
            time.sleep(15.0 * (attempt + 1))


def strip_html(s):
    return re.sub(r'<[^>]+>', '', s or '').strip()


def _meta(page):
    ii = (page.get('imageinfo') or [{}])[0]
    em = ii.get('extmetadata') or {}
    md = {m['name']: m['value'] for m in (ii.get('metadata') or []) if isinstance(m, dict) and 'name' in m}
    coords = page.get('coordinates') or []
    prim = [c for c in coords if c.get('primary')] or coords[:1]
    cam = prim[0] if prim else None
    focal = md.get('FocalLength')
    f35 = md.get('FocalLengthIn35mmFilm')

    def num(v):
        try:
            if isinstance(v, str) and '/' in v:
                a, b = v.split('/')
                return float(a) / float(b)
            return float(v)
        except (TypeError, ValueError, ZeroDivisionError):
            return None
    return dict(
        title=page['title'], page_url=ii.get('descriptionurl'), url=ii.get('url'), thumb_url=ii.get('thumburl'),
        width=ii.get('width'), height=ii.get('height'), mime=ii.get('mime'),
        author=strip_html(em.get('Artist', {}).get('value')), credit=strip_html(em.get('Credit', {}).get('value')),
        licence=strip_html(em.get('LicenseShortName', {}).get('value')),
        licence_url=em.get('LicenseUrl', {}).get('value'),
        description=strip_html(em.get('ImageDescription', {}).get('value'))[:300],
        date=strip_html(em.get('DateTimeOriginal', {}).get('value')),
        camera_lat=cam.get('lat') if cam else None, camera_lon=cam.get('lon') if cam else None,
        camera_heading=num(cam.get('heading')) if cam and cam.get('heading') is not None else None,
        camera_is_primary=bool(cam.get('primary')) if cam else False,
        focal_mm=num(focal), focal_35mm=num(f35), model=md.get('Model'))


def search(query, limit=30):
    d = api(dict(action='query', generator='search', gsrsearch=query, gsrnamespace=6, gsrlimit=limit,
                 prop='imageinfo|coordinates', iiprop='url|extmetadata|size|mime|metadata', iiurlwidth=1600,
                 coprop='type|name|dim', coprimary='all', colimit='max'))
    return [_meta(p) for p in (d.get('query') or {}).get('pages', [])]


def usable(m, located=True):
    lic = (m['licence'] or '').lower()
    return (m['mime'] == 'image/jpeg' and any(lic.startswith(f) for f in FREE)
            and (not located or (m['camera_lat'] is not None and m['camera_is_primary'])))


def listing(place):
    seen = set()
    for q in QUERIES[place]:
        print(f'== {place}: {q}', flush=True)
        for m in search(q):
            if m['title'] in seen or not usable(m):
                continue
            seen.add(m['title'])
            print(f"  {m['title']} | {m['licence']} | cam {m['camera_lat']:.5f},{m['camera_lon']:.5f}"
                  f"{' hdg %.0f' % m['camera_heading'] if m['camera_heading'] is not None else ''} | f {m['focal_mm']}"
                  f" ({m['focal_35mm']} eq) {m['width']}x{m['height']} | {m['author'][:40]}", flush=True)
        time.sleep(1.0)


def fetch(place):
    picks = PICKS.get(place) or []
    if not picks:
        print(f'{place}: nothing picked yet (run --list and fill PICKS)')
        return
    d = os.path.join(OUT, place)
    os.makedirs(d, exist_ok=True)
    records = []
    for i, (title, kind, note, cam) in enumerate(picks):
        q = api(dict(action='query', titles=title, prop='imageinfo|coordinates',
                     iiprop='url|extmetadata|size|mime|metadata', iiurlwidth=1600, coprimary='all', colimit='max'))
        m = _meta(q['query']['pages'][0])
        if not usable(m, located=cam is None):
            print(f'  skip {title}: not usable ({m["licence"]}, camera {m["camera_lat"]})')
            continue
        fn = f'{place}_{i + 1:02d}_{kind}.jpg'
        for attempt in range(4):
            try:
                req = urllib.request.Request(m['thumb_url'] or m['url'], headers={'User-Agent': UA})
                with urllib.request.urlopen(req, timeout=120) as r, open(os.path.join(d, fn), 'wb') as f:
                    f.write(r.read())
                break
            except Exception as e:                                     # noqa: BLE001 - rate limits: back off
                print(f'  retry {fn}: {e}', flush=True)
                time.sleep(10.0 * (attempt + 1))
        m.update(file=fn, kind=kind, note=note, camera_estimated=cam is not None)
        if cam is not None:
            m.update(camera_lat_recorded=m['camera_lat'], camera_lon_recorded=m['camera_lon'],
                     camera_lat=cam['lat'], camera_lon=cam['lon'])
        records.append(m)
        print(f'  {fn}: {title} ({m["licence"]}, {m["author"][:40]})', flush=True)
        time.sleep(3.0)
    with open(os.path.join(d, 'sources.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(place=place, source='Wikimedia Commons (commons.wikimedia.org), fetched ' +
                       time.strftime('%Y-%m-%d'), photos=records), f, indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--place', default=None)
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    for place in ([a.place] if a.place else list(QUERIES)):
        (listing if a.list else fetch)(place)


if __name__ == '__main__':
    main()
