"""Photographs of the places whose packages had none yet (the San Gabriel Mountains, the Palouse, the Namib star dunes
near Sossusvlei, Great Sand Dunes, the Li River towers near Guilin), for the recipe review sheets beside the renders.
Only CC0 and public-domain files from Wikimedia Commons, through the volcano package's Commons helpers
(volcanoes_craters/fetch_photos.py: the API with its User-Agent, throttling and retries, and each file's licence,
author and source page):

    python blender/tests/terrain/integration/fetch_photos.py [--place guilin_karst] [--list]

Writes blender/tests/terrain/out/integration/photos/<place>/<place>_<nn>.jpg (1600 px wide) and sources.json beside
them (title, page URL, author, licence and its URL, what the view shows). Images and JSON only. --list prints the
CC0 / public-domain candidates of each query to pick from.
"""
import argparse
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
TN = os.path.normpath(os.path.join(HERE, '..'))
sys.path.insert(0, os.path.join(TN, 'volcanoes_craters'))

import fetch_photos as FP  # noqa: E402  (the volcano package's Commons helpers)

OUT = os.path.join(TN, 'out', 'integration', 'photos')
FREE = ('cc0', 'public domain')

QUERIES = {
    'san_gabriel_mountains': ['San Gabriel Mountains', 'Angeles National Forest mountains', 'Mount Baden-Powell'],
    'palouse_hills': ['Palouse from Steptoe Butte', 'Palouse hills', 'Palouse landscape'],
    'namib_star_dunes': ['Sossusvlei dunes', 'Namib desert dunes', 'Namib Sand Sea'],
    'great_sand_dunes': ['Great Sand Dunes National Park', 'Great Sand Dunes Star Dune'],
    'guilin_karst': ['Li River karst', 'Li River and mountains in Yangshuo County', 'Yangshuo karst'],
}

# picked after looking: (Commons title, what the view shows)
PICKS = {
    'san_gabriel_mountains': [
        ('File:San Gabriel Mountains 4, CA.JPG', 'looking north from Dawson Saddle (2,408 m) across the range'),
        ("File:06 West Baldy Summit Views (2) - 9,407' Mount Baden-Powell.jpg",
         'from the summit of Mount Baden-Powell (2,867 m) over the ridges'),
        ('File:San Gabriel Mountains 2, CA.JPG', 'from route 39 in the San Gabriel River canyon'),
        ('File:SMOG, SAN GABRIEL MOUNTAINS - NARA - 542676.jpg', 'the range front over the basin\'s haze'),
    ],
    'palouse_hills': [
        ('File:PalouseFromSteptoeButteMay2023-1.jpg', 'west across the hills from Steptoe Butte'),
        ('File:04-03-16-steptoe.jpg', 'from Steptoe Butte'),
        ('File:Palouse fields, Washington from Kamiak Butte.jpg', 'the fields from Kamiak Butte, autumn'),
        ('File:NRCSWA84001 - Washington (6775)(NRCS Photo Gallery).jpg', 'rolling loess hills under wheat'),
    ],
    'namib_star_dunes': [
        ('File:Sossusvlei Dunes Namib.jpg', 'the dunes near Sossusvlei'),
        ('File:Dune 45 Sossusvlei.jpg', 'Dune 45: a star dune\'s arm from the interdune floor'),
        ('File:Dune crest Sossusvlei.jpg', 'from a dune crest across the field'),
        ('File:Hiking Through Sand Dunes (Unsplash).jpg', 'walking a crest in the Namib'),
    ],
    'great_sand_dunes': [
        ('File:Grasslands, Star Dune, and Crestone Peaks (50994036138).jpg',
         'the dunefield from near the park entrance, the Sangre de Cristo range behind'),
        ('File:Star Dune (49985859201).jpg', 'Star Dune, about 230 m'),
        ('File:Star Dune from Sangre de Cristo Mountains (49913696873).jpg',
         'the dunefield from above Zapata Falls, 18 km south'),
        ('File:Colorado Great Sand Dunes National Park.jpg', 'into the dunes from the creek, walkers for scale'),
    ],
    'guilin_karst': [
        ('File:Li River and mountains in Yangshuo County, Guilin2.jpg', 'towers along the Li River'),
        ('File:Li River and mountains in Yangshuo County, Guilin10.jpg', 'towers along the Li River'),
        ('File:Li River and mountains in Yangshuo County, Guilin20.jpg', 'towers along the Li River'),
        ('File:Li River and mountains in Yangshuo County, Guilin40.jpg', 'towers along the Li River'),
        ('File:Li River and mountains in Yangshuo County, Guilin46.jpg', 'towers along the Li River'),
        ('File:Li River and mountains in Yangshuo County, Guilin50.jpg', 'towers along the Li River'),
    ],
}


def free(m):
    lic = (m['licence'] or '').lower()
    return m['mime'] == 'image/jpeg' and any(lic.startswith(f) for f in FREE)


def listing(place):
    seen = set()
    for q in QUERIES[place]:
        print(f'== {place}: {q}', flush=True)
        for m in FP.search(q, limit=40):
            if m['title'] in seen or not free(m):
                continue
            seen.add(m['title'])
            print(f"  {m['title']} | {m['licence']} | {m['width']}x{m['height']} | {m['description'][:80]}",
                  flush=True)
        time.sleep(1.0)


def fetch(place):
    d = os.path.join(OUT, place)
    os.makedirs(d, exist_ok=True)
    records = []
    for i, (title, note) in enumerate(PICKS[place]):
        q = FP.api(dict(action='query', titles=title, prop='imageinfo|coordinates',
                        iiprop='url|extmetadata|size|mime|metadata', iiurlwidth=1600, coprimary='all', colimit='max'))
        m = FP._meta(q['query']['pages'][0])
        if not free(m):
            print(f'  skip {title}: {m["licence"]} (CC0 and public domain only)', flush=True)
            continue
        fn = f'{place}_{i + 1:02d}.jpg'
        path = os.path.join(d, fn)
        if not os.path.exists(path):
            for attempt in range(4):
                try:
                    req = urllib.request.Request(m['thumb_url'] or m['url'], headers={'User-Agent': FP.UA})
                    with urllib.request.urlopen(req, timeout=120) as r:
                        data = r.read()
                    with open(path, 'wb') as f:
                        f.write(data)
                    break
                except Exception as e:                                 # noqa: BLE001 - rate limits: back off
                    print(f'  retry {fn}: {e}', flush=True)
                    time.sleep(10.0 * (attempt + 1))
            time.sleep(2.0)
        m.update(file=fn, note=note)
        records.append(m)
        print(f'  {fn}: {title} ({m["licence"]}, {m["author"][:40]})', flush=True)
    with open(os.path.join(d, 'sources.json'), 'w', encoding='utf-8') as f:
        json.dump(dict(place=place, source='Wikimedia Commons (commons.wikimedia.org), fetched ' +
                       time.strftime('%Y-%m-%d'), photos=records), f, indent=1, ensure_ascii=False)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--place', default=None)
    ap.add_argument('--list', action='store_true')
    a = ap.parse_args()
    for place in ([a.place] if a.place else list(PICKS)):
        (listing if a.list else fetch)(place)


if __name__ == '__main__':
    main()
