"""A film's motion vectors for DLSS 5's temporal path (dlss5nr/, tools-guides/postprocessing.md "DLSS 5 over a finished
film"): EEVEE's Vector pass of a built film, one animation render a shot, as the motion files dlss5nr.py reads.

    bash run_blender.sh blender/tools/render_motion.py --blend <film.blend> --out <dir>
        [--frames 1-240] [--hide haze,dust] [--plan]

--blend is the film's build (`python eido_blender.py build work/<id>/scene.json` saves it beside the film's video, or
any saved scene). Its shots are its camera markers (`ctx.cut`); a film with none is one shot through its scene camera.
Each shot's frames render as ONE animation (the engine syncs the scene once a shot, not once a frame) with only what the
pass needs: EEVEE at 1 sample, motion blur off (the Vector pass needs it off), ray tracing and the sequencer off, and
the compositor replaced by a File Output node that writes the raw pass (Blender saves only Combined in a render's own
EXR). The scene's own resolution is kept, so the vectors are in the film's pixels; the beauty output is a throwaway.
--hide names objects (prefixes) to leave out of the pass, such as a haze volume or dust that moves nothing.

Every frame becomes <out>/<frame:04d>.npz in the motion-file layout (dlss5nr/motion_npz.py: X Y Z W float16, rows
top-down, Blender's pixel units; X Y point to where the pixel's surface was a frame earlier, Y up), and <out>/cuts.txt
lists each shot's first frame. A frame already written is skipped, so a stopped run picks up where it was; --frames
renders a part of the film. --plan prints the shots and writes cuts.txt without rendering. The .blend is only read,
never saved. Then, on the host:

    python dlss5nr/motion_check.py <film.mp4> <dir> --frames <three moving frames> --offset -<frame_start>
    python dlss5nr/dlss5nr.py <film.mp4> <film_dlss5.mp4> --model <weights> --motion <dir> --convention "+X -Y" \
        --offset -<frame_start> --cuts <dir>/cuts.txt

(video frame 0 is the scene's frame_start, so the offset is minus frame_start: -1 for the runner's default films).
"""
import glob
import os
import shutil
import sys
import time

import bpy
import numpy as np
import OpenImageIO as oiio

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, '..', '..'))
sys.path.insert(0, os.path.join(REPO, 'dlss5nr'))
import motion_npz  # noqa: E402

AXES = 'XYZWRGBA'


def log(*a):
    print('[motion]', *a, flush=True)


def parse_args():
    argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []

    def arg(k, d=None):
        return argv[argv.index(k) + 1] if k in argv else d
    if not arg('--blend') or not arg('--out'):
        raise SystemExit(__doc__)
    frames = None
    if arg('--frames'):
        frames = set()
        for part in arg('--frames').split(','):
            a, _, b = part.partition('-')
            frames |= set(range(int(a), int(b or a) + 1))
    hide = tuple(p for p in (arg('--hide') or '').split(',') if p)
    return os.path.abspath(arg('--blend')), os.path.abspath(arg('--out')), frames, hide, '--plan' in argv


def shots(scene):
    """[(first frame, last frame, camera)] over the scene's frame range: a new shot at every camera marker"""
    a, b = scene.frame_start, scene.frame_end
    cuts = sorted((m.frame, m.camera) for m in scene.timeline_markers if m.camera is not None and a < m.frame <= b)
    starts = [(a, None)] + cuts
    out = []
    for i, (f, cam) in enumerate(starts):
        end = starts[i + 1][0] - 1 if i + 1 < len(starts) else b
        if cam is None:      # before the first marker: the camera a marker at or before frame_start set, else the scene's
            early = [m for m in scene.timeline_markers if m.camera is not None and m.frame <= a]
            cam = max(early, key=lambda m: m.frame).camera if early else scene.camera
        if end >= f:
            out.append((f, end, cam))
    return out


def vector_output(scene, tmpdir):
    """the Vector pass on every view layer, out through the compositor: Render Layers -> a File Output node, raw half
    floats, no compression (the EXR only carries the pass to the .npz and is deleted)"""
    for vl in scene.view_layers:
        vl.use_pass_vector = True
    scene.render.use_compositing = True
    tree = bpy.data.node_groups.new('motion_out', 'CompositorNodeTree')
    scene.compositing_node_group = tree
    rl = tree.nodes.new('CompositorNodeRLayers')
    fo = tree.nodes.new('CompositorNodeOutputFile')
    fo.directory = tmpdir
    fo.file_name = '_vec'
    fo.save_as_render = False
    fo.format.media_type = 'MULTI_LAYER_IMAGE'
    fo.format.file_format = 'OPEN_EXR_MULTILAYER'
    fo.format.color_depth = '16'
    fo.format.exr_codec = 'NONE'
    fo.file_output_items.new('VECTOR', 'Vector')
    tree.links.new(rl.outputs['Vector'], fo.inputs['Vector'])


def pass_only(scene, hide):
    """what the Vector pass needs and nothing more"""
    scene.render.engine = 'BLENDER_EEVEE'
    scene.eevee.taa_render_samples = 1
    scene.render.use_motion_blur = False
    for owner, name in ((scene.eevee, 'use_raytracing'), (scene.render, 'use_sequencer')):
        if hasattr(owner, name):
            setattr(owner, name, False)
    hidden = 0
    for ob in bpy.data.objects:
        if hide and ob.name.startswith(hide):
            ob.hide_render = True
            hidden += 1
    return hidden


def read_vectors(path):
    """the (4, H, W) float16 X Y Z W of a File Output EXR's Vector channels, rows top-down (W zero if it holds three)"""
    buf = oiio.ImageBuf(path)
    spec = buf.spec()
    names = list(spec.channelnames)
    vec = [c for c in names if 'Vector' in c.split('.')]
    if len(vec) not in (3, 4):
        raise SystemExit(f'[motion] {path}: no Vector channels in {names}')
    px = buf.get_pixels(oiio.FLOAT)                         # (H, W, C), top row first
    order = [names.index(c) for c in sorted(vec, key=lambda c: AXES.index(c.split('.')[-1].upper()) % 4)]
    raw = np.zeros((4, spec.height, spec.width), np.float16)
    raw[:len(order)] = np.moveaxis(px[..., order], -1, 0)
    return raw


def main():
    blend, out, only, hide, plan_only = parse_args()
    if not os.path.isfile(blend):
        raise SystemExit(f'[motion] no film at {blend}')
    os.makedirs(out, exist_ok=True)
    bpy.ops.wm.open_mainfile(filepath=blend, load_ui=False)
    scene = bpy.context.scene
    plan = shots(scene)
    if not plan or plan[0][2] is None:
        raise SystemExit(f'[motion] {blend}: no camera')
    with open(os.path.join(out, 'cuts.txt'), 'w', encoding='utf-8') as f:
        f.write(','.join(str(a) for a, _, _ in plan) + '\n')
    for a, b, cam in plan:
        log(f'shot {a}-{b}: camera {cam.name}')
    if plan_only:
        log(f'{len(plan)} shot(s); cuts {out}/cuts.txt; nothing rendered (--plan)')
        return
    w = scene.render.resolution_x * scene.render.resolution_percentage // 100
    h = scene.render.resolution_y * scene.render.resolution_percentage // 100
    hidden = pass_only(scene, hide)
    tmpdir = os.path.join(out, '_tmp')
    os.makedirs(tmpdir, exist_ok=True)
    vector_output(scene, tmpdir)
    log(f'{os.path.basename(blend)}: {w}x{h}, frames {scene.frame_start}-{scene.frame_end}, {len(plan)} shot(s)'
        + (f', {hidden} object(s) hidden' if hidden else ''))
    written = 0
    t_all = time.time()
    for a, b, cam in plan:
        need = [f for f in range(a, b + 1) if (only is None or f in only)
                and not os.path.exists(os.path.join(out, f'{f:04d}.npz'))]
        if not need:
            continue
        for old in glob.glob(os.path.join(tmpdir, '_*')):
            os.remove(old)
        scene.frame_start, scene.frame_end = need[0], need[-1]
        scene.render.filepath = os.path.join(tmpdir, '_beauty_')       # the main output: a small throwaway JPEG
        scene.render.image_settings.file_format = 'JPEG'
        scene.render.image_settings.quality = 10
        t0 = time.time()
        bpy.ops.render.render(animation=True)
        t1 = time.time()
        span = range(need[0], need[-1] + 1)
        for f in span:
            dst = os.path.join(out, f'{f:04d}.npz')
            files = glob.glob(os.path.join(tmpdir, f'_vec*{f:04d}.exr'))
            if len(files) != 1:
                raise SystemExit(f'[motion] frame {f}: the File Output node wrote {files} (of '
                                 f'{sorted(os.listdir(tmpdir))[:6]})')
            raw = read_vectors(files[0])
            if raw.shape[1:] != (h, w):
                raise SystemExit(f'[motion] frame {f}: the pass is {raw.shape[2]}x{raw.shape[1]}, the film {w}x{h}')
            if not os.path.exists(dst):
                motion_npz.save(dst, raw)
                written += 1
            os.remove(files[0])
        log(f'shot {a}-{b}: frames {need[0]}-{need[-1]}: render {(t1 - t0) / len(span):.2f} s a frame, files '
            f'{(time.time() - t1) / len(span):.2f} s a frame')
    shutil.rmtree(tmpdir, ignore_errors=True)
    start = plan[0][0]                                     # the film's frame_start: its video's frame 0
    log(f'wrote {written} frame(s) to {out} in {time.time() - t_all:.1f} s; cuts {",".join(str(p[0]) for p in plan)}')
    log(f'next: python dlss5nr/motion_check.py <film.mp4> {out} --frames <moving frames> --offset {-start}; then '
        f'python dlss5nr/dlss5nr.py <film.mp4> <out.mp4> --model <weights> --motion {out} --convention "+X -Y" '
        f'--offset {-start} --cuts {os.path.join(out, "cuts.txt")}')


try:                     # (Blender exits 0 after a script's error: a failure here exits 1, so callers can trust the code)
    main()
except SystemExit as e:
    if e.code not in (None, 0):
        print(e.code if isinstance(e.code, str) else f'[motion] exit {e.code}', flush=True)
        os._exit(1)
    raise
except Exception:
    import traceback
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    os._exit(1)
