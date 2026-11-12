"""test_vrm_shadows.py: load_vrm sets up a VRM's MToon materials for EEVEE's shadows (characters/vrm.py mtoon_shadows),
and Aletheia (MToon) and the robot (glTF PBR) both cast sun shadows.

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/characters/test_vrm_shadows.py
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/characters/test_vrm_shadows.py -- --render

Checks (no render): every MToon material takes the shadow flag its alpha mode needs (OPAQUE: Transparent Shadows off;
MASK and BLEND: on); the add-on's MToon output group lets shadow rays see the material's opacity (its Is Camera Ray
read as max(Is Camera Ray, Is Shadow Ray x (1 - Is Outline))); the robot's own materials are left as the file has
them; the change survives a save and a reopen. --render: the two side by side on a floor under a sun, from the
reopened file, rendered with their shadows and with their meshes kept out of the shadow pass; the floor darkens where
each one's shadow falls (out/vrm_shadows_cast.png, _none.png, _sheet.jpg).
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _stage as S  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.characters import vrm as V  # noqa: E402

RESULTS = []
RENDER = '--render' in S.argv()
BLEND = os.path.join(S.OUT, 'vrm_shadows.blend')


def check(name, ok, detail=''):
    print(('PASS ' if ok else 'FAIL ') + name + (f'  ({detail})' if detail else ''), flush=True)
    RESULTS.append(bool(ok))


def mtoon_materials(meshes):
    out = {}
    for o in meshes:
        for s in o.material_slots:
            m = s.material
            if m is not None and m.vrm_addon_extension.mtoon1.enabled:
                out[m.name] = m
    return list(out.values())


def output_groups():
    return [g for g in bpy.data.node_groups if g.name.startswith(V.MTOON_OUTPUT)]


def group_reads_shadow_rays(g):
    """Every Is Camera Ray use in the group goes into a 'camera or shadow ray' maximum whose other input is fed by
    Is Shadow Ray (through the outline gate)."""
    uses = [lk for lk in g.links if lk.from_node.bl_idname == 'ShaderNodeLightPath'
            and lk.from_socket.name == 'Is Camera Ray']
    ok = bool(uses) and bool(g.get('eido_shadow_rays'))
    for lk in uses:
        n = lk.to_node
        if n.bl_idname != 'ShaderNodeMath' or n.operation != 'MAXIMUM' or not n.inputs[1].is_linked:
            ok = False
            continue
        src = n.inputs[1].links[0].from_node
        feeds = [x.from_socket.name for x in (src.inputs[0].links if src.bl_idname == 'ShaderNodeMath' else [])]
        ok = ok and (feeds == ['Is Shadow Ray'] or n.inputs[1].links[0].from_socket.name == 'Is Shadow Ray')
    return ok, len(uses)


def stage():
    sc = S.clean_scene(24)
    S.probe_render(sc)
    sc.render.resolution_x, sc.render.resolution_y = 960, 540
    S.studio_world(sc, 0.35, background=0x121214)
    S.floor_disc(radius=8.0, colour=0x8c8c90, roughness=0.8)
    # the sun from the front left, 51 degrees up: each shadow falls back to the right, on the floor beside its owner
    S.sun('sun', (-2.0, 4.5, 3.0), 0xfff4e8, 4.0, angle_deg=1.0)
    return sc


def main():
    sc = stage()
    her = V.load_vrm('aletheia', location=(-1.0, 0.0, 0.0), rotation=0.0)
    bot = V.load_vrm('claude_robot', location=(1.0, 0.0, 0.0), rotation=0.0)

    # ---------------------------------------------------------------------------------------------- the flags
    mats = mtoon_materials(her.meshes)
    modes = {}
    for m in mats:
        modes.setdefault(m.vrm_addon_extension.mtoon1.alpha_mode, []).append(m)
    wrong = [m.name for m in mats if m.use_transparent_shadow != (m.vrm_addon_extension.mtoon1.alpha_mode != 'OPAQUE')]
    check("Aletheia's MToon materials take their alpha mode's shadow flag (OPAQUE off, MASK and BLEND on)",
          mats and not wrong, f"{ {k: len(v) for k, v in modes.items()} }; wrong {wrong}")
    gs = output_groups()
    reads = [group_reads_shadow_rays(g) for g in gs]
    check("the add-on's MToon output group reads its Is Camera Ray as max(Is Camera Ray, Is Shadow Ray x not outline)",
          gs and all(ok for ok, _n in reads), f'{[g.name for g in gs]}: {reads}')
    robot_mats = {s.material for o in bot.meshes for s in o.material_slots if s.material is not None}
    check("the robot's own materials are left as the file has them (glTF PBR, no MToon, Blender's shadow default)",
          robot_mats and not any(m.vrm_addon_extension.mtoon1.enabled for m in robot_mats)
          and all(m.use_transparent_shadow for m in robot_mats), f'{len(robot_mats)} materials')

    # ---------------------------------------------------------------------------------------------- save, reopen
    bpy.ops.wm.save_as_mainfile(filepath=BLEND)
    bpy.ops.wm.open_mainfile(filepath=BLEND)
    sc = bpy.context.scene
    gs = output_groups()
    reads = [group_reads_shadow_rays(g) for g in gs]
    flags = [(m.name, m.use_transparent_shadow) for m in bpy.data.materials if m.vrm_addon_extension.mtoon1.enabled
             and (m.vrm_addon_extension.mtoon1.alpha_mode == 'OPAQUE') == m.use_transparent_shadow]
    check('saved and reopened, the output group and the flags are as set', gs and all(ok for ok, _n in reads)
          and not flags, f'{len(gs)} groups; wrong flags {flags[:4]}')

    if RENDER:
        render(sc)
    n_fail = RESULTS.count(False)
    print(f'[test_vrm_shadows] {len(RESULTS) - n_fail} passed, {n_fail} failed', flush=True)
    return n_fail


def luma(path):
    from PIL import Image
    a = np.asarray(Image.open(path).convert('RGB'), np.float32) / 255.0
    return a @ np.array([0.2126, 0.7152, 0.0722], np.float32), a


def render(sc):
    cam = S.camera('cam', 35.0)
    S.aim(cam, (0.3, -5.2, 1.55), (0.3, 0.6, 0.55))
    figures = [o for o in bpy.data.objects if o.type == 'MESH' and o.name != 'floor']
    cast = os.path.join(S.OUT, 'vrm_shadows_cast.png')
    none = os.path.join(S.OUT, 'vrm_shadows_none.png')
    check('render with their shadows', S.still(sc, cam, 1, cast), cast)
    for o in figures:
        o.visible_shadow = False
    check('render with their meshes out of the shadow pass', S.still(sc, cam, 1, none), none)
    la, a = luma(cast)
    lb, b = luma(none)
    drop = lb - la
    W = la.shape[1]
    for name, x0, x1 in (('Aletheia', 0, W // 2), ('the robot', W // 2, W)):
        d = drop[:, x0:x1]
        dark = d > 0.04
        check(f'{name} casts a sun shadow: the floor darkens where it falls', dark.mean() > 0.005,
              f'{dark.mean() * 100:.2f}% of the half darker by > 0.04, mean drop there {d[dark].mean() if dark.any() else 0:.3f}')
    from PIL import Image
    vis = np.clip(np.abs(a - b) * 4.0, 0, 1)
    h, w = la.shape
    sheet = Image.new('RGB', (w * 3 // 2, h // 2))
    for i, im in enumerate((a, b, vis)):
        sheet.paste(Image.fromarray((im * 255).astype(np.uint8)).resize((w // 2, h // 2), Image.LANCZOS), (i * w // 2, 0))
    sheet.save(os.path.join(S.OUT, 'vrm_shadows_sheet.jpg'), quality=90)


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(1)
