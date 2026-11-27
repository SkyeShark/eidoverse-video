"""test_rooms.py: the four SAME SEED rooms made from a clean checkout and checked (plain Python driving make.py; the
steps run in Blender and the GPU baker):

    python blender/tests/sets_same_seed/test_rooms.py [--rooms sealed_room,kitchen,lab,desk] [--no-render] [--full]

For each room: make.py's whole chain into blender/tests/sets_same_seed/out/<room>/ (high -> lows -> bake -> prints ->
look; the CC0 IDs fetched into the shared library on first use), then check_room.py on the delivered file (the room
through the public API, see its doc), then (unless --no-render) two small stills from the room's own cameras at its
own render settings, 480 x 270, each checked to be a picture (not black, not flat). The kitchen bakes in Blender's
Cycles: here at 1024 with a tenth of the samples (--full: the room's 4096, about 13 minutes on a desktop GPU).
A room whose GPU bake cannot run (no warp-lang) is a SKIP, said so.

EIDO_SAME_SEED_FILM (optional, through _where.external): the film's own set folder (<room>/<ROOM>_film_view_<id>.png);
then each room's wide camera is rendered at 1920 x 1080 too and measured against the film's frame from that lens (mean
luma and mean absolute luma difference; PASS under 0.01). Run inside run_all.py's GPU slot (HEAVY_VRAM_GB set), its
steps do not queue for the slot again.
"""
import argparse
import os
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
import _where  # noqa: E402

sys.path.insert(0, str(_where.REPO / 'blender'))
from eidoblend.sets.same_seed import ROOMS, make as MK  # noqa: E402

# per room: the two small stills' cameras, and the film's wide frame (file prefix, lens id) for the optional measure
STILLS = {'sealed_room': ('wide', 'bench_right'), 'kitchen': ('wide', 'table_homework'), 'lab': ('wide', 'monstera'),
          'desk': ('wide', 'desk_things')}
FILM_WIDE = {'sealed_room': ('SEALED', 'i4'), 'kitchen': ('KITCHEN', 'i2'), 'lab': ('LAB', 'i3'), 'desk': ('DESK', 'i1')}
FAILS = []


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    if not ok:
        FAILS.append(name)


def luma(path):
    """(mean, std) of a picture's luma, 0..1 (Pillow and numpy when there; None without them)"""
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        return None
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0
    y = a[..., 0] * 0.2126 + a[..., 1] * 0.7152 + a[..., 2] * 0.0722
    return float(y.mean()), float(y.std()), y


def run_blender(script, *args):
    p = subprocess.run(_where.blender_cmd(script, *args), cwd=str(_where.REPO), capture_output=True, text=True,
                       encoding='utf-8', errors='replace', creationflags=0x08000000 if os.name == 'nt' else 0)
    lines = [ln for ln in (p.stdout + p.stderr).splitlines() if ln.startswith(('PASS', 'FAIL', '[check_room]', 'Traceback', '  File'))
             or 'Error' in ln]
    return p.returncode, lines


def test_room(room, render, full, film):
    out = HERE / 'out' / room
    kw = {} if (full or room != 'kitchen') else {'size': 1024, 'quick': True}
    rc = MK.make(room, out=str(out), first='high', last='look', log=lambda *a: print(*a, flush=True), **kw)
    if rc == 3:
        print(f'SKIP {room}: the GPU bake cannot run here (pip install warp-lang); nothing else of it is checked', flush=True)
        return
    check(f'{room}: made from nothing (make.py exit {rc})', rc == 0 and (out / f'{room}.blend').is_file())
    if rc != 0:
        return
    code, lines = run_blender(HERE / 'check_room.py', room, out)
    for ln in lines:
        print('   ' + ln if not ln.startswith(('PASS', 'FAIL')) else ln, flush=True)
    check(f'{room}: check_room.py ran', code == 0 and any(ln.startswith('[check_room]') for ln in lines), f'exit {code}')
    if not render:
        return
    cams = STILLS[room]
    rc = MK.make(room, out=str(out), first='stills', last='stills', stills=True, cams=','.join(cams), res='480x270',
                 log=lambda *a: print(*a, flush=True))
    for c in cams:
        p = out / 'stills' / f'{room}_{c}.png'
        m = luma(p) if p.is_file() else None
        ok = p.is_file() and (m is None or (m[0] > 0.02 and m[1] > 0.02))
        check(f'{room}: still {c}', rc == 0 and ok, (f'mean luma {m[0]:.3f}, spread {m[1]:.3f}' if m else ('no Pillow to read it' if p.is_file() else 'not written')))
    if film is not None:
        prefix, lens = FILM_WIDE[room]
        ref = film / room / f'{prefix}_film_view_{lens}.png'
        if not ref.is_file():
            print(f'[skip] {room}: the film frame {ref.name} is not in EIDO_SAME_SEED_FILM', flush=True)
            return
        _film_still(room, out)
        mine = out / 'film' / f'{room}_wide.png'
        a, b = luma(mine), luma(ref)
        if a is None or b is None:
            print(f'[skip] {room}: no Pillow to measure the film frame', flush=True)
            return
        import numpy as np
        mad = float(np.abs(a[2] - b[2]).mean()) if a[2].shape == b[2].shape else 1.0
        check(f'{room}: the wide lens against the film frame {ref.name}', mad < 0.01, f'mean luma {a[0]:.3f} against {b[0]:.3f}; mean abs diff {mad:.4f}')


def _film_still(room, out):
    """the wide camera at 1920 x 1080 from the delivered file, into out/film/"""
    (out / 'film').mkdir(parents=True, exist_ok=True)
    code, _ = run_blender(_where.REPO / 'blender' / 'eidoblend' / 'sets' / 'same_seed' / 'cli.py', room, 'stills', '--dir', out,
                          '--cams', 'wide', '--res', '1920x1080')
    src = out / 'stills' / f'{room}_wide.png'
    if src.is_file():
        os.replace(src, out / 'film' / f'{room}_wide.png')
    return code


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--rooms', default=','.join(ROOMS))
    ap.add_argument('--no-render', action='store_true')
    ap.add_argument('--full', action='store_true', help="the kitchen's bake at its own 4096 and full samples")
    a = ap.parse_args()
    if os.environ.get('HEAVY_VRAM_GB') and os.environ.get('EIDO_GPU_WRAP'):
        os.environ.pop('EIDO_GPU_WRAP')                        # (already in run_all.py's GPU slot: the steps do not queue again)
    film = _where.external('EIDO_SAME_SEED_FILM', "the film's set folder, to measure each room's wide lens against its frame")
    for room in [r for r in a.rooms.split(',') if r]:
        if room not in ROOMS:
            check(f'{room}: a room', False, f'the rooms: {", ".join(ROOMS)}')
            continue
        test_room(room, not a.no_render, a.full, film if not a.no_render else None)
    print(f'[test_rooms] {len(FAILS)} FAIL', flush=True)
    return 1 if FAILS else 0


if __name__ == '__main__':
    sys.exit(main())
