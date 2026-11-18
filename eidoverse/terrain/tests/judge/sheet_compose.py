"""The compare sheet of the port's renders (PORT_PLAN.md 6.3): the Blender judge's own sheet, judge/sheet.py
compose() as it is, with the reference's row (its three renders and numbers) above each row of renders, every row's
numbers from its verdict JSON (the Blender judge's verdict, made with Blender's Python by tests/judge/judge.mjs).
It lays out pictures and computes no number, so it runs in a Python that has Pillow (the Blender judge's sheet module
needs it; Blender's bundled Python has none): tests/judge/sheets.mjs runs it.

    python eidoverse/terrain/tests/judge/sheet_compose.py --reference <name> --row <label>=<verdicts.json> [...]
        --render-dir <dir> --out <png> [--title T]
                 the renders of a row are <render-dir>/<label>_top_hillshade.png, _aerial_45deg.png, _eye_1p7m.png
                 (tests/judge/views.mjs names them so); a missing one is drawn as 'not rendered'
    python eidoverse/terrain/tests/judge/sheet_compose.py --stack <out png> <sheet png> [<sheet png> ...]
                 several sheets one above the other
"""
from __future__ import annotations

import argparse
import json
import os
import site
import sys

sys.dont_write_bytecode = True                              # no __pycache__ beside the tools or in the Blender edition
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.normpath(os.path.join(HERE, '..', 'parity')))
sys.path.append(site.getusersitepackages())                  # Pillow, where it lives in the user's site
import _blender as B  # noqa: E402


def verdict(d, label):
    """A judging.Verdict from its to_dict() form, with the attributes sheet.compose reads (rows, notes, label,
    pixel, extent; passed, judged and failures are the class's own properties over the rows)."""
    from judge.judging import Verdict
    v = Verdict.__new__(Verdict)
    v.reference, v.family, v.label = d['reference'], d.get('family'), label
    v.pixel, v.extent = float(d['pixel_m']), float(d['extent_m'])
    v.notes = list(d.get('notes') or [])
    v.rows = d['rows']
    v.numbers = d.get('numbers') or {}
    return v


def compose(reference, rows, render_dir, out, title=None):
    B.bare_terrain_package()
    from judge import refs, sheet
    ref = refs.load(reference)
    vs = []
    for label, path in rows:
        with open(path, encoding='utf-8') as f:
            d = json.load(f)
        vs.append(verdict(d['verdicts'][0] if 'verdicts' in d else d, label))
    png = sheet.compose(out, ref, vs, render_dir, title=title)
    print(f'[sheet] {reference}: {png or out}', flush=True)
    return out


def stack(out, sheets):
    from PIL import Image
    ims = [Image.open(p).convert('RGB') for p in sheets if os.path.exists(p)]
    if not ims:
        sys.exit('[sheet] nothing to stack')
    w = max(i.width for i in ims)
    canvas = Image.new('RGB', (w, sum(i.height for i in ims)), (24, 25, 27))
    y = 0
    for i in ims:
        canvas.paste(i, (0, y))
        y += i.height
    os.makedirs(os.path.dirname(os.path.abspath(out)) or '.', exist_ok=True)
    canvas.save(out)
    print(f'[sheet] {len(ims)} sheets -> {out}', flush=True)
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    ap.add_argument('--reference')
    ap.add_argument('--row', action='append', default=[], help='<label>=<verdicts.json>')
    ap.add_argument('--render-dir')
    ap.add_argument('--out')
    ap.add_argument('--title')
    ap.add_argument('--stack', nargs='+')
    a = ap.parse_args()
    if a.stack:
        stack(a.stack[0], a.stack[1:])
        return
    if not (a.reference and a.row and a.render_dir and a.out):
        ap.error('give --reference, --row, --render-dir and --out (or --stack)')
    rows = [tuple(r.split('=', 1)) for r in a.row]
    compose(a.reference, rows, a.render_dir, a.out, a.title)


if __name__ == '__main__':
    main()
