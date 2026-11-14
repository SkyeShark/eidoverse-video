"""look/probe_cli.py: probe stills from a saved .blend, from the command line (eido.py render --at for Blender).

    bash run_blender.sh blender/eidoblend/look/probe_cli.py --blend film.blend --at 1.5 --at 4 [--out DIR] [--name N]
        [--preroll 1 | --replay] [--preset probe|film|preview|keep] [--samples 16] [--res 960x540] [--exposure +0.5]
        [--compare 4.0] [--false-color] [--sheet]
  (a GPU job: every probe is a render)

  --at T        a time in seconds from frame_start (repeatable; also --at 1.5,4); --frame F for frame numbers
  --preroll S   evaluate S seconds of frames before each probe (unbaked sims, spring bones, stateful handlers)
  --replay      evaluate every frame from frame_start (the slow, sure way)
  --preset      the look to render with: 'probe' (default: 960x540, 16 samples), 'film', 'preview', or 'keep' the blend's
  --compare T   render frame T twice, jumped to and after the frame before it, and report how much they differ: EEVEE
                keeps no history between final renders, so they must match (the max difference is noise-level)
  --false-color also save each still through AgX's False Color view (exposure zones)
  --sheet       a contact sheet of the stills (<name>_sheet.jpg)

Writes <out>/<name>_probe_at<sec>s.png (<sec>: the still's frame time to two decimals, as the WebGPU harness names its
captures; default <out> is <blend dir>/probes) through .part files, and <name>_probes.json; measures each still's
highlights.
The blend is never saved. Exit code 1 when a still is missing or the script fails (Blender's own exit code is 0 even
when a script raises, so this one exits itself).
"""
import json
import os
import sys
import traceback

import bpy

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)), '..', '..')))
from eidoblend.look import frame_stats as fs          # noqa: E402
from eidoblend.look import probe as P                  # noqa: E402
from eidoblend.look import render_settings as RS       # noqa: E402
from eidoblend.look import exposure as EX              # noqa: E402
from eidoblend.look import camera as C                 # noqa: E402


def parse(argv):
    o = {'at': [], 'frames': [], 'out': None, 'name': None, 'mode': 'jump', 'preroll': 1.0, 'preset': 'probe',
         'samples': None, 'res': None, 'exposure': None, 'compare': None, 'false_color': False, 'sheet': False}
    i = 0
    while i < len(argv):
        k = argv[i]
        v = argv[i + 1] if i + 1 < len(argv) else None
        if k == '--blend':
            o['blend'] = v
        elif k == '--at':
            o['at'] += [float(x) for x in v.split(',')]
        elif k == '--frame':
            o['frames'] += [int(x) for x in v.split(',')]
        elif k == '--out':
            o['out'] = v
        elif k == '--name':
            o['name'] = v
        elif k == '--preroll':
            o['mode'], o['preroll'] = 'preroll', float(v)
        elif k == '--replay':
            o['mode'] = 'replay'
            i += 1
            continue
        elif k == '--preset':
            o['preset'] = v
        elif k == '--samples':
            o['samples'] = int(v)
        elif k == '--res':
            o['res'] = tuple(int(x) for x in v.lower().split('x'))
        elif k == '--exposure':
            o['exposure'] = float(v)
        elif k == '--compare':
            o['compare'] = float(v)
        elif k in ('--false-color', '--sheet'):
            o[k[2:].replace('-', '_')] = True
            i += 1
            continue
        else:
            raise SystemExit(f'probe_cli: unknown argument {k}')
        i += 2
    if not o.get('blend'):
        raise SystemExit('probe_cli: --blend is required')
    o['out'] = os.path.abspath(o['out'] or os.path.join(os.path.dirname(o['blend']), 'probes'))
    o['name'] = o['name'] or os.path.splitext(os.path.basename(o['blend']))[0]
    return o


def compare(scene, t, out, name):
    """Render frame t jumped to, then again after rendering the frame before it; report the difference."""
    f = C.frame_at(scene, t)
    a = os.path.join(out, f'{name}_compare_jump.png')
    b = os.path.join(out, f'{name}_compare_after.png')
    pre = os.path.join(out, f'{name}_compare_prev.png')
    P.render_still(scene, a, f, 'jump')
    P.render_still(scene, pre, f - 1, 'jump')
    P.render_still(scene, b, f, 'jump')
    import numpy as np
    ia, ib = fs.read_rgb(a).astype(np.int16), fs.read_rgb(b).astype(np.int16)
    d = np.abs(ia - ib)
    res = {'frame': f, 'max_diff': int(d.max()), 'mean_diff': float(d.mean()),
           'pixels_over_8': float((d.max(axis=2) > 8).mean())}
    print(f"[probe] compare frame {f}: alone vs after frame {f - 1}: max diff {res['max_diff']}/255, mean "
          f"{res['mean_diff']:.3f}, {res['pixels_over_8'] * 100:.3f} % of pixels over 8 levels", flush=True)
    os.remove(pre)
    return res


def main():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
    o = parse(argv)
    bpy.ops.wm.open_mainfile(filepath=o['blend'], load_ui=False)
    sc = bpy.context.scene
    if o['preset'] != 'keep':
        RS.apply_auto_enhance(sc, o['preset'], resolution=o['res'], samples=o['samples'], keep_sequencer=False)
    elif o['res'] or o['samples']:
        RS.apply_auto_enhance(sc, 'probe', resolution=o['res'], samples=o['samples'])
    if o['exposure'] is not None:
        sc.view_settings.exposure += o['exposure']
    print('[probe] look:', RS.summary(sc), flush=True)
    os.makedirs(o['out'], exist_ok=True)
    rows = P.render_stills(sc, at=o['at'], frames=o['frames'], out_dir=o['out'], name=o['name'], mode=o['mode'],
                           preroll_s=o['preroll'])
    missing = [r['path'] for r in rows if not os.path.exists(r['path'])]
    if o['false_color']:
        for r in rows:
            P.evaluate_to(sc, r['frame'])
            bpy.ops.render.render()
            keep = sc.view_settings.view_transform, sc.view_settings.look
            sc.view_settings.view_transform = 'False Color'
            try:
                EX.save_display(sc, r['path'].replace('.png', '_falsecolor.png'))
            finally:
                sc.view_settings.view_transform, sc.view_settings.look = keep
    report = {'stills': rows}
    if o['compare'] is not None:
        report['compare'] = compare(sc, o['compare'], o['out'], o['name'])
    if o['sheet'] and rows:
        fs.sheet([r['path'] for r in rows], os.path.join(o['out'], f"{o['name']}_sheet.jpg"),
                 labels=[f"t={r['t']}s f{r['frame']} {r['camera']}" for r in rows])
    with open(os.path.join(o['out'], f"{o['name']}_probes.json"), 'w', encoding='utf-8') as fh:
        json.dump(report, fh, indent=1, default=str)
    if missing:
        print(f'[probe] MISSING: {missing}', flush=True)
        return 1
    bad = [r for r in rows if not r.get('highlights_ok', True)]
    print(f"[probe] {len(rows)} still(s) in {o['out']}; highlights {'OK' if not bad else f'CLIP in {len(bad)}'}", flush=True)
    return 0


if __name__ == '__main__':
    try:
        code = main()
    except SystemExit as e:
        print(e, flush=True)
        code = 2
    except Exception:
        traceback.print_exc()
        code = 1
    sys.stdout.flush()
    os._exit(code)          # Blender returns 0 after a script raises; this exit code is the script's own
