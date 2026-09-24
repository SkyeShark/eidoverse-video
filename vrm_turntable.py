"""Turntable contact sheets (or reels) of a VRM: outfits x framings x yaws, rendered through the engine.

    python vrm_turntable.py [--vrm eidoverse/assets/vrms/claude_suit_wardrobe.vrm] [--scale 0.87]
        [--outfits lab_coat_1961,mourning] [--frames face,head,chest,body] [--views 0,35,90,150,180]
        [--hold 12] [--size 400x520] [--anim idle] [--light 0.7] [--presets JSON] [--faces JSON]
        [--tile 8x2] [--out work/turntable/sheet.png]
    python vrm_turntable.py ... --spin --video work/turntable/reel.mp4        # one slow turn per outfit, a video

A sheet has one row per (outfit, clip, framing) and one column per yaw; --tile CxR lays the same tiles out in reading
order on a C-by-R grid instead (a grid of outfits). Each tile is the LAST frame of a --hold block (frame 0 of any
render is the VRM's load pose, and spring bones settle over the block). --outfits takes claudesona_wardrobe WARDROBE
keys (the wardrobe VRM) or "-" for any VRM without a wardrobe. --anim takes one VRMA slot or a comma list (a clip
sheet: one row per clip). --presets adds variants
({"name": {"base": "cyclist_1892", "fold": {...}}}); "key:nofold" drops a preset's petal fold. --faces takes one dict
of raw morph weights per outfit row, for expression sheets. Framing follows the character's head height, so any rig
and scale frames the same. --light scales the studio (0.7 keeps white MToon cloth under the bloom threshold).
Guide: AGENTS.md ("Turntable sheets").
"""
import argparse
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    ap.add_argument('--vrm', default='eidoverse/assets/vrms/claude_suit_wardrobe.vrm')
    ap.add_argument('--scale', type=float, default=None, help='VRM scale (default 0.87 for claude_suit*, else 1)')
    ap.add_argument('--outfits', default=None, help='WARDROBE keys, comma-separated; "-" for none')
    ap.add_argument('--views', default='0,35,90,150,180')
    ap.add_argument('--frames', default='head,body', help='any of face, head, chest, body')
    ap.add_argument('--hold', type=int, default=12)
    ap.add_argument('--size', default='400x520')
    ap.add_argument('--anim', default='idle', help='VRMA default slot(s) to play, comma-separated')
    ap.add_argument('--light', type=float, default=0.7, help='studio light level')
    ap.add_argument('--presets', default='{}')
    ap.add_argument('--faces', default='[]')
    ap.add_argument('--spin', action='store_true')
    ap.add_argument('--tile', default=None, help='CxR: lay the tiles out in reading order on this grid')
    ap.add_argument('--out', default='work/turntable/sheet.png')
    ap.add_argument('--video', default='work/turntable/turntable.mp4')
    a = ap.parse_args()
    wardrobe_vrm = 'claude_suit_wardrobe' in os.path.basename(a.vrm)
    outfits = a.outfits if a.outfits is not None else ('suit' if wardrobe_vrm else '-')
    scale = a.scale if a.scale is not None else (0.87 if 'claude_suit' in os.path.basename(a.vrm) else 1.0)
    w, h = map(int, a.size.split('x'))
    views, frames, olist = a.views.split(','), a.frames.split(','), outfits.split(',')
    anims = a.anim.split(',')
    blocks = len(olist) * len(anims) * len(views) * len(frames)
    os.makedirs(os.path.join(ROOT, os.path.dirname(a.video)), exist_ok=True)
    cfg = {'width': w, 'height': h, 'fps': 30, 'duration': blocks * a.hold / 30.0,
           'script': 'eidoverse/vrm_turntable_scene.js', 'outputVideo': a.video, 'assets': {'vrm': a.vrm}}
    cfg_path = os.path.join(ROOT, os.path.dirname(a.video), 'turntable.json')
    json.dump(cfg, open(cfg_path, 'w', encoding='utf-8'), indent=2)
    env = dict(os.environ, VT_OUTFITS=outfits, VT_VIEWS=a.views, VT_FRAMES=a.frames, VT_HOLD=str(a.hold),
               VT_SPIN='1' if a.spin else '', VT_ANIM=a.anim, VT_SCALE=str(scale), VT_LIGHT=str(a.light),
               VT_PRESETS=a.presets, VT_FACES=a.faces)
    rel = os.path.relpath(cfg_path, ROOT).replace('\\', '/')
    r = subprocess.run([sys.executable, 'eido.py', 'render', rel], cwd=ROOT, env=env)
    if r.returncode:
        sys.exit(f'render failed ({r.returncode})')
    if a.spin:
        print(f'reel: {a.video}')
        return
    os.makedirs(os.path.join(ROOT, os.path.dirname(a.out)), exist_ok=True)
    tile = a.tile or f'{len(views)}x{len(olist) * len(anims) * len(frames)}'
    sel = f"select='eq(mod(n+1\\,{a.hold})\\,0)',tile={tile}"
    subprocess.run(['ffmpeg', '-v', 'error', '-y', '-i', os.path.join(ROOT, a.video), '-vf', sel, '-frames:v', '1',
                    os.path.join(ROOT, a.out)], check=True)
    print(f'sheet: {a.out}  ({blocks} tiles on {tile})')


if __name__ == '__main__':
    main()
