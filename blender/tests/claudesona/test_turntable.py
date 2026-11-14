"""blender/tools/vrm_turntable.py (the repo-root vrm_turntable.py + eidoverse/vrm_turntable_scene.js, ported) run four
ways in one Blender process, its outputs measured and looked at:

    A  the claudesona wardrobe: a preset variant (--presets, a taller tilted boater), a preset without its fold
       (cyclist_1892:nofold), raw face weights per outfit row (--faces), head framing, two yaws, laid out 2x3 (--tile),
       the keyed scene saved (--save) and REOPENED: a tile rendered from the saved .blend alone must match the sheet's
    B  aletheia with no wardrobe ('-'): a clip sheet (--anim idle,cheer), chest framing, three yaws, MToon
    C  aletheia again in the PBR look (--look pbr), the idle row of B beside it
    D  a spin reel (--spin --video): the TuTa, one eased turn, H.264
Checks: every tile and sheet written at its size; the sheet's grid; the reel's frame count; the saved .blend's tile
within 1 % of the sheet's (mean absolute difference: the keys alone rebuild the frame).

    bash run_blender.sh blender/tests/claudesona/test_turntable.py
    # a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)
"""

import json
import os
import subprocess
import sys
import traceback

sys.dont_write_bytecode = True
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'blender', 'tools'))
sys.path.insert(0, HERE)
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

import vrm_turntable as VT  # noqa: E402

OUT = 'blender/tests/claudesona/out/turntable'
PRESETS = {'cyclist_tall': {'base': 'cyclist_1892', 'hat': {'seat': 'auto', 'sink': 0.004, 'tilt': -9, 'scale': 1.25}}}
FACES = [{'Smile': 1.0, 'MouthSmileLeft': 1.0, 'MouthSmileRight': 1.0}, {}, {'EyeClosedLeft': 0.8, 'EyeClosedRight': 0.8}]


def png(p):
    im = bpy.data.images.load(p, check_existing=False)
    w, h = im.size
    a = np.array(im.pixels[:], dtype=np.float32).reshape(h, w, 4)
    bpy.data.images.remove(im)
    return a


def tiles(sheet):
    return sorted(os.path.join(os.path.splitext(sheet)[0] + '_tiles', f)
                  for f in os.listdir(os.path.splitext(sheet)[0] + '_tiles') if f.endswith('.png'))


def main():
    R, C = {}, S.Checks('turntable')
    ab = lambda p: os.path.join(REPO, p)  # noqa: E731
    try:
        # A: presets, nofold, faces, tile, save + reopen
        a_out, a_blend = f'{OUT}/claudesona_presets.png', f'{OUT}/claudesona_presets.blend'
        VT.main(['--outfits', 'suit,cyclist_1892:nofold,cyclist_tall', '--presets', json.dumps(PRESETS),
                 '--frames', 'head', '--views', '0,90', '--faces', json.dumps(FACES), '--tile', '2x3', '--hold', '10',
                 '--size', '300x360', '--out', a_out, '--save', a_blend])
        ts = tiles(ab(a_out))
        sh = png(ab(a_out))
        C.check('A: six tiles on a 2x3 sheet (3 outfits x 1 framing x 2 yaws), 300x360 each',
                len(ts) == 6 and sh.shape[:2] == (3 * 360, 2 * 300), f'{len(ts)} tiles, sheet {sh.shape[1]}x{sh.shape[0]}')
        R['A'] = {'sheet': ab(a_out), 'tiles': ts}
        # the saved .blend alone: reopen it, render block 4's last frame, compare with its tile
        ref = png(ts[3])
        bpy.ops.wm.open_mainfile(filepath=ab(a_blend))
        sc = bpy.context.scene
        sc.frame_set(1 + 3 * 10 + 9)
        sc.render.filepath = os.path.join(ab(OUT), 'reopened_block4.png')
        sc.render.image_settings.media_type = 'IMAGE'
        sc.render.image_settings.file_format = 'PNG'
        bpy.ops.render.render(write_still=True)
        got = png(sc.render.filepath)
        d = float(np.abs(got[..., :3] - ref[..., :3]).mean())
        R['A']['reopened_mad'] = d
        C.check("A: the saved .blend, reopened, renders block 4's tile on its own (keys only: outfit, face, yaw, camera, "
                "springs)", d < 0.01, f'mean abs diff {d:.5f}')
        os.remove(ab(a_blend))
        # the reopened file replaced every datablock: vrma.load_clip's cache (keyed by armature name) now holds dead
        # actions, which a later build of the same character would read (a CLI run of the tool is a fresh process)
        from eidoblend.characters import vrma
        vrma._CACHE.clear()
        # B: aletheia, any VRM, a clip sheet
        b_out = f'{OUT}/aletheia_clips.png'
        VT.main(['--vrm', 'eidoverse/assets/vrms/aletheia.vrm', '--outfits', '-', '--anim', 'idle,cheer', '--frames', 'chest',
                 '--views', '0,35,90', '--hold', '14', '--size', '300x360', '--out', b_out])
        tb = tiles(ab(b_out))
        sb = png(ab(b_out))
        C.check("B: aletheia ('-': no wardrobe), two clips x three yaws: a 3x2 sheet", len(tb) == 6 and sb.shape[:2] == (2 * 360, 3 * 300),
                f'{len(tb)} tiles, sheet {sb.shape[1]}x{sb.shape[0]}')
        R['B'] = {'sheet': ab(b_out)}
        # C: the PBR look
        c_out = f'{OUT}/aletheia_pbr.png'
        VT.main(['--vrm', 'eidoverse/assets/vrms/aletheia.vrm', '--outfits', '-', '--anim', 'idle', '--frames', 'chest',
                 '--views', '0,35,90', '--hold', '14', '--size', '300x360', '--look', 'pbr', '--out', c_out])
        sc_ = png(ab(c_out))
        mt = sb[360:, :, :3]                                   # B's first row (idle): the image's top row is stored last
        diff = float(np.abs(sc_[..., :3] - mt).mean())
        R['C'] = {'sheet': ab(c_out), 'mtoon_vs_pbr_mad': diff}
        C.check('C: the PBR look renders, and differs from MToon (it is a different shading, not a no-op)',
                sc_.shape[:2] == (360, 900) and diff > 0.005, f'mean abs diff vs MToon {diff:.4f}')
        # D: a spin reel
        d_vid = f'{OUT}/tuta_spin.mp4'
        VT.main(['--outfits', 'tuta', '--frames', 'body', '--views', '0', '--hold', '48', '--size', '360x480', '--spin',
                 '--video', d_vid])
        n = None
        try:
            r = subprocess.run(['ffprobe', '-v', 'error', '-count_frames', '-select_streams', 'v:0', '-show_entries',
                                'stream=nb_read_frames,codec_name', '-of', 'json', ab(d_vid)], capture_output=True, text=True)
            st = json.loads(r.stdout)['streams'][0]
            n, codec = int(st['nb_read_frames']), st['codec_name']
        except Exception as e:  # noqa: BLE001
            codec = f'ffprobe failed: {e}'
        R['D'] = {'video': ab(d_vid), 'frames': n, 'codec': codec}
        C.check('D: the spin reel is an H.264 video of one 48-frame turn', n == 48 and codec == 'h264', f'{n} frames, {codec}')
    except Exception:
        traceback.print_exc()
        R['error'] = traceback.format_exc()
        C.check('ran without an exception', False)
    R['checks'] = C.rows
    R['all_pass'] = C.all_pass and 'error' not in R
    with open(os.path.join(REPO, OUT, 'turntable.json'), 'w', encoding='utf-8') as f:
        json.dump(R, f, indent=1, default=str)
    print('[turntable] ALL PASS' if R['all_pass'] else '[turntable] SOME FAILED', flush=True)


main()
