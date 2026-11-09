"""Test stills of the two sets as free assets, from their own cameras (the five each set ships, framed for a figure of
1.6 m on the mark): every camera in the default state, then the states and options (the corridor's doors open and
cracked, a repost typing, a recount, the lights dimmed, the cap carried to a head; the news set's tag half sprayed,
the floods off, the signs on the kick, the chyron in its overlay) and one shot per set with the suggested look on
(apply_post: the aeropittura 'argue'). Every still has the look's bloom, as the WebGPU probes' 'off' frames had.
Writes out/shots/<set>/<shot>.png and a contact sheet per set.

The cap shots need a head: --her stands the claudesona (claude_suit.vrm at 0.87, the scale capFit was measured for)
on the mark for them alone and hides her elsewhere; without it, a bare head bone stands in (the cap's flight, no fit).

    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_corridor_news/render_shots.py [corridor|news] [--samples 16]
        [--size 960x540] [--her] [--only base,states,look] [--dry]
"""
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
from mathutils import Quaternion, Vector  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL, corridor as COR, news as NEWS  # noqa: E402

A = F.args()
WHICH = next((a for a in A if a in ('corridor', 'news', 'both')), 'both')
SAMPLES = int(A[A.index('--samples') + 1]) if '--samples' in A else 16
W, H = (int(v) for v in (A[A.index('--size') + 1] if '--size' in A else '960x540').split('x'))
HER = '--her' in A
ONLY = set(A[A.index('--only') + 1].split(',')) if '--only' in A else {'base', 'states', 'look'}
DRY = '--dry' in A                       # everything but the renders (a check of the script, outside the GPU slot)
OUT = F.OUT / 'shots'
if DRY:
    F.render_still = lambda path, scene=None: print(f'[dry] {Path(path).name}', flush=True) or True


def place_her(scale=0.87):
    """The claudesona on the mark (the origin, facing three's +Z = Blender -Y), her arms lowered from the rest pose."""
    from eidoblend.characters import vrm as V
    h = V.load_vrm('claude_suit', location=(0.0, 0.0, 0.0), rotation=0.0)
    h.arm.scale = (scale, scale, scale)
    h.write_pose({'leftUpperArm': Quaternion((0.0, 0.0, 1.0), -1.2), 'rightUpperArm': Quaternion((0.0, 0.0, 1.0), 1.2),
                  'leftLowerArm': Quaternion((0.0, 1.0, 0.0), 0.15), 'rightLowerArm': Quaternion((0.0, 1.0, 0.0), -0.15)})
    bpy.context.view_layer.update()
    return h


def show(h, on):
    if h is not None:
        for o in h.objects:
            o.hide_render = not on


def look_cam(name, pos, target, fov_deg=30.0):
    cd = bpy.data.cameras.new(name)
    cd.sensor_fit = 'VERTICAL'
    cd.angle_y = math.radians(fov_deg)
    cd.clip_start = 0.02
    ob = bpy.data.objects.new(name, cd)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = Vector(pos)
    ob.rotation_mode = 'QUATERNION'
    ob.rotation_quaternion = (Vector(target) - Vector(pos)).to_track_quat('-Z', 'Y')
    return ob


def render(S, sc, path, cam=None, cam_ob=None):
    ob = cam_ob or S.camera(cam, sc)
    sc.camera = ob
    S.set_u('pix', CL.pix_of(sc, ob))
    return F.render_still(path, sc)


def contact_sheet(folder, names, out, cols=3, tw=480):
    from PIL import Image, ImageDraw
    ims = [(n, Image.open(folder / f'{n}.png').convert('RGB')) for n in names if (folder / f'{n}.png').is_file()]
    if not ims:
        return
    th = int(tw * ims[0][1].height / ims[0][1].width)
    rows = (len(ims) + cols - 1) // cols
    sheet = Image.new('RGB', (cols * tw, rows * (th + 18)), (12, 12, 14))
    d = ImageDraw.Draw(sheet)
    for i, (n, im) in enumerate(ims):
        x, y = (i % cols) * tw, (i // cols) * (th + 18)
        sheet.paste(im.resize((tw, th), Image.Resampling.LANCZOS), (x, y + 18))
        d.text((x + 4, y + 3), n, fill=(230, 230, 230))
    sheet.save(out)


def setup():
    sc = F.clean_scene()
    if sc.compositing_node_group is not None:          # the previous set's look pass: off before the next set
        from eidoblend.look.post import chain
        for _slot, name, _n in list(chain.stages(sc)):
            chain.remove_stage(sc, name)
        sc.compositing_node_group = None
    F.render_settings(W, H, SAMPLES)
    sc.frame_start, sc.frame_end = 1, 1
    return sc


# ================================================================================================== corridor ===
def corridor():
    out = OUT / 'corridor'
    out.mkdir(parents=True, exist_ok=True)
    sc = setup()
    clock = F.timer()
    C = COR.build(sc, {'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM'})
    C.apply_look(sc)
    C.apply_post(sc, aeropittura=False)        # the look's bloom on every still, as the WebGPU probes had it
    print(f'[shots] corridor built in {clock():.1f}s', flush=True)
    names = []

    def shot(name, cam, st, t=0.0, cam_ob=None):
        C.update(t, st)
        render(C, sc, out / f'{name}.png', cam, cam_ob)
        names.append(name)
    if 'base' in ONLY:
        for cam in COR.CAMS:
            shot(f'{cam}', cam, {'post': 1.0})
    if 'states' in ONLY:
        shot('corridorWide_doors_open', 'corridorWide', {'post': 1.0, 'open': 1.0}, t=2.0)
        shot('door_doors_crack', 'door', {'post': 1.0, 'open': 0.14}, t=2.0)
        shot('postWall_repost_typing_half', 'postWall', {'postText': 'A NEW POST FROM THE MINISTRY, IN CAPITAL LETTERS',
                                                         'post': 0.5}, t=3.0)
        shot('poll_recount_no_stamp', 'poll', {'post': 1.0, 'tally': [512000, 418000, 341000]}, t=3.0)
        shot('corridorWide_lights_dimmed', 'corridorWide', {'post': 1.0, 'lights': 0.3, 'screen': 0.4}, t=3.0)
        her = place_her() if HER else None
        if her is not None:
            head = (her.arm, her.humanoid['head'])
            hw = her.arm.matrix_world @ her.arm.pose.bones[her.humanoid['head']].head
        else:
            hb = bpy.data.objects.new('stand_in_head', None)      # a bare head bone where hers would be
            sc.collection.objects.link(hb)
            hb.location = (0.0, 0.0, 1.45)
            head, hw = hb, Vector((0.0, 0.0, 1.45))
        show(her, True)
        shot('door_cap_on_head', 'door', {'post': 1.0, 'capOn': 1.0, 'capHead': head}, t=4.0)
        c = hw + Vector((0.0, 0.0, 0.12))
        front = look_cam('cap_fit_front', c + Vector((0.0, -0.75, 0.04)), c, 28)
        side = look_cam('cap_fit_side', c + Vector((0.75, 0.0, 0.04)), c, 28)
        shot('cap_fit_front', None, {'post': 1.0, 'capOn': 1.0, 'capHead': head}, t=4.0, cam_ob=front)
        shot('cap_fit_side', None, {'post': 1.0, 'capOn': 1.0, 'capHead': head}, t=4.0, cam_ob=side)
        shot('door_cap_midflight', 'door', {'post': 1.0, 'capOn': 0.5, 'capHead': head}, t=4.0)
        show(her, False)
    if 'look' in ONLY:
        C.update(0.0, {'post': 1.0, 'postText': 'AMERICANISM, NOT EFFECTIVE ALTRUISM', 'capOn': 0.0, 'open': 0.0})
        sc.camera = C.camera('door', sc)
        from eidoblend.look.post import history
        history.set_history_dir(sc, str(OUT / 'post_history'))   # the aeropittura's frame history: in out/, not in temp
        C.apply_post(sc)
        shot('door_look_argue', 'door', {'post': 1.0})
    contact_sheet(out, names, OUT / 'corridor_contact_sheet.png')
    C.dispose()


# ====================================================================================================== news ===
def news():
    out = OUT / 'news'
    out.mkdir(parents=True, exist_ok=True)
    sc = setup()
    clock = F.timer()
    N = NEWS.build(sc)
    N.apply_look(sc)
    N.apply_post(sc, aeropittura=False)        # the look's bloom on every still, as the WebGPU probes had it
    print(f'[shots] news built in {clock():.1f}s', flush=True)
    names = []

    def shot(name, cam, st, t=0.0, cam_ob=None):
        N.update(t, st)
        render(N, sc, out / f'{name}.png', cam, cam_ob)
        names.append(name)

    def chyron_over(name, cam, t):
        from PIL import Image
        from eidoblend.media import overlay
        if DRY:
            return
        ov = overlay.make_overlay_layer(sc, camera=N.camera(cam, sc))
        N.parts['chyron'].place(ov, fov=N.cams[cam]['fov'], aspect=W / H)
        N.parts['chyron'].update(t)
        ov.scene.render.resolution_x, ov.scene.render.resolution_y = W, H
        ov.scene.render.filepath = str(out / f'{name}_overlay.png')
        ov.scene.render.image_settings.color_mode = 'RGBA'
        bpy.ops.render.render(write_still=True, scene=ov.scene.name)
        base = Image.open(out / f'{name}.png').convert('RGBA')
        top = Image.open(out / f'{name}_overlay.png').convert('RGBA')
        Image.alpha_composite(base, top).convert('RGB').save(out / f'{name}_with_chyron.png')
        names.append(f'{name}_with_chyron')
        N.parts['chyron']['mesh'].hide_render = True
    if 'base' in ONLY:
        for cam in NEWS.CAMS:
            shot(cam, cam, {'spray': 1.0, 'chant': 1.0}, t=0.3)
    if 'states' in ONLY:
        shot('wall_spray_half', 'wall', {'spray': 0.5}, t=1.25)
        shot('fence_floods_off', 'fence', {'floods': 0.0}, t=2.0)
        shot('crowd_signs_on_the_kick', 'crowd', {'pulse': 1.0, 'chant': 1.0}, t=0.26)
        chyron_over('crowd_signs_on_the_kick', 'crowd', 0.26)
    if 'look' in ONLY:
        sc.camera = N.camera('crowd', sc)
        N.update(0.3, {'spray': 1.0})
        from eidoblend.look.post import history
        history.set_history_dir(sc, str(OUT / 'post_history'))
        N.apply_post(sc)
        shot('crowd_look_argue', 'crowd', {'spray': 1.0}, t=0.3)
    contact_sheet(out, names, OUT / 'news_contact_sheet.png')
    N.dispose()


if __name__ == '__main__':                    # (verify_probes.py imports the helpers above)
    t0 = time.time()
    if WHICH in ('corridor', 'both'):
        corridor()
    if WHICH in ('news', 'both'):
        news()
    print(f'[shots] done in {time.time() - t0:.0f}s', flush=True)
