"""Reference photographs of the layered-rock places from Wikimedia Commons, taken from the ground and from oblique
angles (a hillshade from above hides wall heights, benches and skylines), for the photo-beside-render sheets.
After eidoverse/assets/grass/daisy_src/fetch_refs.py: the Commons API (a User-Agent header, throttled, retried),
1600 px thumbnails, each photo's licence, author and source page in sources.json beside the images, and its camera
position when the photo carries GPS metadata (render_views.py stands the camera there). Images only: data, nothing
executable.

    python blender/tests/terrain/layered_rock/fetch_photos.py --search "Toroweap overlook" [--limit 30]
    python blender/tests/terrain/layered_rock/fetch_photos.py                 # every photo in PHOTOS
    python blender/tests/terrain/layered_rock/fetch_photos.py toroweap_01 ... # only these

Writes blender/tests/terrain/out/layered_rock/photos/<key>.jpg and sources.json.
"""
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request

UA = 'EidoverseRefBot/1.0 (https://github.com/SkyeShark/eidoverse-video; terrain landform lookdev)'
HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.normpath(os.path.join(HERE, '..', 'out', 'layered_rock', 'photos'))

# key: (Commons file title, the place, what the photo shows and from where)
PHOTOS = {
    'tw_01': ('Toroweap overlook - Grand Canyon - Flickr - brewbooks.jpg', 'grand_canyon_toroweap',
              'the inner gorge from the west side of Toroweap Overlook, on the Esplanade rim'),
    'tw_02': ('Toroweap Overlook, Grand Canyon National Park, Arizona (67209218).jpg', 'grand_canyon_toroweap',
              'from Toroweap Overlook'),
    'tw_03': ('Toroweap Overlook (50533998363).jpg', 'grand_canyon_toroweap', 'view from Toroweap Overlook (NPS)'),
    'tw_04': ('Approaching Toroweap Overlook, Grand Canyon National Park, Arizona (92980193).jpg',
              'grand_canyon_toroweap', 'on the Esplanade approaching the overlook, 2.7 km west of it'),
    'tw_05': ('Lone Tree - Toroweap - Flickr - brewbooks.jpg', 'grand_canyon_toroweap',
              'from the east side of the Toroweap overlook area'),
    'tw_06': ('Toroweap Overlook, Grand Canyon National Park, Arizona (66044185).jpg', 'grand_canyon_toroweap',
              'from Toroweap Overlook'),
    'tw_07': ('Grand Canyon Toroweap (2).jpg', 'grand_canyon_toroweap', 'from the west side of the Toroweap area'),
    'tw_08': ('Toroweap Overlook, Arizona.jpg', 'grand_canyon_toroweap', 'sunrise over Toroweap Overlook'),
    'gn_01': ('Goosenecks State Park, March 2019.jpg', 'goosenecks', 'the meander loop below the state park overlook'),
    'gn_02': ('San juan river entrenched meanders.jpg', 'goosenecks', 'from Goosenecks State Park'),
    'gn_03': ('Goosenecks San Juan River Utah 2020.jpg', 'goosenecks', 'the incised meanders looking about southeast'),
    'gn_04': ('San Juan River (Goosenecks State Park, Utah, USA) 1 (21263340971).jpg', 'goosenecks',
              "from 37 10' 27.44\" N 109 55' 38.70\" W"),
    'gn_05': ('Goosenecks State Park, San Juan River, Utah, USA.jpg', 'goosenecks', 'panorama from the state park'),
    'gn_06': ('Honaker Trail Formation over Paradox Formation (Pennsylvanian; Goosenecks of the San Juan River, '
              'Utah, USA) 1 (49103741287).jpg', 'goosenecks', 'the stepped canyon wall: ledges and slopes'),
    'mv_01': ('2013-09-22 14 14 43 View east-northeast from Lookout Point towards the Mittens and Merrick Butte in '
              'Monument Valley Navajo Tribal Park.JPG', 'monument_valley',
              'east-northeast from Lookout Point toward the Mittens and Merrick Butte'),
    'mv_02': ('West Mitten Butte - Monument Valley Luca Galuzzi 2007.jpg', 'monument_valley',
              'West Mitten Butte, view about due east'),
    'mv_03': ('West Mitten Butte, East Mitten Butte, and Merrick Butte 2.jpg', 'monument_valley',
              'the Mittens and Merrick Butte from the visitor centre area'),
    'mv_04': ('Monument Valley, Arizona, US - The Mittens and Merrick Butte - panoramio.jpg', 'monument_valley',
              'the Mittens and Merrick Butte'),
    'mv_05': ('East Mitten, Merrick Butte, and West Mitten Over Monument Valley, Navajo Nation.jpg',
              'monument_valley', 'the buttes from the east'),
    'mv_06': ('Monument Valley USA Mittens and Merrick Butte 2009.jpg', 'monument_valley',
              'the Mittens and Merrick Butte'),
    'bl_01': ('Pinnacles from Notch and Door Trails, Badlands National Park, Wall, SD.jpg', 'badlands_sd',
              'pinnacles from the Notch and Door trails'),
    'bl_02': ('Canyon from Notch and Door Trails, Badlands National Park, Wall, SD.jpg', 'badlands_sd',
              'a gully canyon from the Notch and Door trails'),
    'bl_03': ('Badlands National Park - End of Door Trail at dusk.jpg', 'badlands_sd',
              'a badlands canyon at the end of the Door Trail'),
    'bl_04': ('Cedar pass wall (31071050105).jpg', 'badlands_sd', 'the Badlands Wall from Cedar Pass campground'),
    'bl_05': ('Panoramic view of badland formations from Cedar Pass Lodge, Badlands National Park, 2009.jpg',
              'badlands_sd', 'the wall from Cedar Pass Lodge'),
    'bl_06': ('Pinnacles from Notch and Door Trails, Badlands National Park, Wall, SD 2.jpg', 'badlands_sd',
              'pinnacles from the Notch and Door trails'),
    'bl_07': ('Prairie from Notch and Door Trails, Badlands National Park, Wall, SD.jpg', 'badlands_sd',
              'the prairie below the wall from the trails'),
}


def api(params):
    q = urllib.parse.urlencode({**params, 'format': 'json'})
    req = urllib.request.Request('https://commons.wikimedia.org/w/api.php?' + q, headers={'User-Agent': UA})
    for attempt in range(6):
        try:
            return json.loads(urllib.request.urlopen(req, timeout=60).read())
        except Exception as e:                                          # noqa: BLE001 - retried
            print('[photos] api retry', e, flush=True)
            time.sleep(10 + attempt * 10)
    raise RuntimeError('commons api unavailable')


def strip(html):
    return re.sub(r'<[^>]+>', '', html or '').strip()


def info(titles):
    """imageinfo (url, size, extmetadata) for File: titles."""
    d = api({'action': 'query', 'titles': '|'.join('File:' + t for t in titles), 'prop': 'imageinfo',
             'iiprop': 'url|size|extmetadata', 'iiurlwidth': 1600})
    out = {}
    for page in d['query']['pages'].values():
        if 'imageinfo' in page:
            out[page['title'][5:]] = page['imageinfo'][0]
    return out


def search(query, limit=30):
    d = api({'action': 'query', 'list': 'search', 'srsearch': query, 'srnamespace': 6, 'srlimit': limit})
    titles = [r['title'][5:] for r in d['query']['search']]
    for k in range(0, len(titles), 20):
        got = info(titles[k:k + 20])
        for t in titles[k:k + 20]:
            ii = got.get(t)
            if not ii:
                continue
            m = ii.get('extmetadata', {})
            gps = (m.get('GPSLatitude', {}).get('value'), m.get('GPSLongitude', {}).get('value'))
            print(f"{t}\n    {ii.get('width')}x{ii.get('height')}  {strip(m.get('LicenseShortName', {}).get('value'))}"
                  f"  by {strip(m.get('Artist', {}).get('value'))[:40]}  gps {gps}\n"
                  f"    {strip(m.get('ImageDescription', {}).get('value'))[:160]}", flush=True)
        time.sleep(1.0)


def fetch(only=None):
    os.makedirs(OUT, exist_ok=True)
    srcp = os.path.join(OUT, 'sources.json')
    sources = json.load(open(srcp, encoding='utf-8')) if os.path.exists(srcp) else {}
    for key, (title, place, what) in PHOTOS.items():
        if only and key not in only:
            continue
        out = os.path.join(OUT, key + '.jpg')
        if os.path.exists(out) and key in sources:
            continue
        ii = info([title]).get(title)
        if ii is None:
            print('[photos] MISSING', title, flush=True)
            continue
        url = ii.get('thumburl') or ii['url']
        req = urllib.request.Request(url, headers={'User-Agent': UA})
        data = None
        for attempt in range(4):
            try:
                data = urllib.request.urlopen(req, timeout=120).read()
                break
            except Exception as e:                                      # noqa: BLE001 - retried
                print('[photos] retry', key, e, flush=True)
                time.sleep(8)
        if data is None:
            continue
        with open(out, 'wb') as f:
            f.write(data)
        m = ii.get('extmetadata', {})

        def mv(k):
            return strip(m.get(k, {}).get('value', ''))
        lat, lon = mv('GPSLatitude'), mv('GPSLongitude')
        sources[key] = {
            'title': title, 'place': place, 'what': what, 'page': ii.get('descriptionurl'), 'url': url,
            'artist': mv('Artist'), 'credit': mv('Credit'), 'license': mv('LicenseShortName'),
            'license_url': mv('LicenseUrl'), 'attribution_required': mv('AttributionRequired'),
            'description': mv('ImageDescription')[:400], 'date': mv('DateTimeOriginal'),
            'camera_lat': float(lat) if lat else None, 'camera_lon': float(lon) if lon else None,
            'size': [ii.get('thumbwidth') or ii.get('width'), ii.get('thumbheight') or ii.get('height')],
        }
        with open(srcp, 'w', encoding='utf-8') as f:
            json.dump(sources, f, indent=1, ensure_ascii=False)
        print('[photos]', key, sources[key]['license'], sources[key]['artist'][:40], flush=True)
        time.sleep(2.0)


if __name__ == '__main__':
    a = sys.argv[1:]
    if a and a[0] == '--search':
        lim = int(a[a.index('--limit') + 1]) if '--limit' in a else 30
        search(a[1], lim)
    else:
        fetch(set(a) or None)
