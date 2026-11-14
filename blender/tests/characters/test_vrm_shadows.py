"""test_vrm_shadows.py: load_vrm sets up a VRM's MToon materials for EEVEE's shadows and light probes
(characters/vrm.py mtoon_shadows): Aletheia (MToon) and the robot (glTF PBR) both cast sun shadows, and both stand in a
planar mirror.

    bash run_blender.sh blender/tests/characters/test_vrm_shadows.py
    bash run_blender.sh blender/tests/characters/test_vrm_shadows.py -- --render
    # --render: a GPU job; on a shared machine queue it with EIDO_GPU_WRAP (blender/tests/_where.py)

Checks (no render): every MToon material takes the shadow flag its alpha mode needs (OPAQUE: Transparent Shadows off;
MASK and BLEND: on); the add-on's MToon output group lets shadow rays see the material's opacity (its Is Camera Ray
read as max(Is Camera Ray, Is Shadow Ray x (1 - Is Outline))) and glossy rays, with which EEVEE captures its planar
and sphere probes, too (that maximum read again as max(it, Is Glossy Ray)); a group that has the shadow gate alone (a
file set up before the glossy step) gets the glossy step from mtoon_shadows, once; the robot's own materials are left
as the file has them; the change survives a save and a reopen. --render: the two side by side on a floor under a
sun, from the reopened file, rendered with their shadows and with their meshes kept out of the shadow pass; the floor
darkens where each one's shadow falls (out/vrm_shadows_cast.png, _none.png, _sheet.jpg). Then the floor polished dark
under a planar light probe, seen from low, rendered with the two in the probe's capture and kept out of it
(hide_probe_plane): where each one's mirror image falls (their meshes reflected in the floor, projected) the floor
shows them, and their own pixels do not change (out/vrm_mirror_in.png, _out.png, _sheet.jpg).
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


GLOSSY = 'camera, glossy or shadow ray'


def group_reads_glossy_rays(g):
    """Each 'camera or shadow ray' maximum feeds one 'camera, glossy or shadow ray' maximum alone, whose other input
    is Is Glossy Ray and whose output feeds what the camera ray fed."""
    gates = [n for n in g.nodes if n.bl_idname == 'ShaderNodeMath' and n.label == 'camera or shadow ray']
    ok = bool(gates) and bool(g.get('eido_glossy_rays'))
    for n in gates:
        outs = list(n.outputs[0].links)
        m = outs[0].to_node if len(outs) == 1 else None
        if m is None or m.bl_idname != 'ShaderNodeMath' or m.operation != 'MAXIMUM' or m.label != GLOSSY \
                or not m.inputs[1].is_linked or not m.outputs[0].links:
            ok = False
            continue
        src = m.inputs[1].links[0]
        ok = ok and src.from_node.bl_idname == 'ShaderNodeLightPath' and src.from_socket.name == 'Is Glossy Ray'
    return ok, len(gates)


def strip_glossy(g):
    """the group as a file set up before the glossy step holds it: the shadow gate feeding the opacity directly"""
    for n in [n for n in g.nodes if n.bl_idname == 'ShaderNodeMath' and n.label == GLOSSY]:
        src = n.inputs[0].links[0].from_socket
        for lk in list(n.outputs[0].links):
            g.links.new(src, lk.to_socket)
        g.nodes.remove(n)
    if 'eido_glossy_rays' in g:
        del g['eido_glossy_rays']


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
    glossy = [group_reads_glossy_rays(g) for g in gs]
    check("glossy rays (EEVEE's planar and sphere probe captures) see the surface too: max(that, Is Glossy Ray)",
          gs and all(ok for ok, _n in glossy), f'{[g.name for g in gs]}: {glossy}')
    for g in gs:
        strip_glossy(g)
    stripped = [group_reads_glossy_rays(g)[0] for g in gs]
    first = V.mtoon_shadows(her.meshes)['groups']
    again = V.mtoon_shadows(her.meshes)['groups']
    glossy = [group_reads_glossy_rays(g) for g in gs]
    shadow = [group_reads_shadow_rays(g)[0] for g in gs]
    check('a group with the shadow gate alone (a file set up before the glossy step) gets the glossy step from '
          'mtoon_shadows, once', not any(stripped) and sorted(first) == sorted(g.name for g in gs) and not again
          and all(ok for ok, _n in glossy) and all(shadow),
          f'stripped reads glossy {stripped}; first call changed {first}, the second {again}; glossy {glossy}')
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
    glossy = [group_reads_glossy_rays(g) for g in gs]
    flags = [(m.name, m.use_transparent_shadow) for m in bpy.data.materials if m.vrm_addon_extension.mtoon1.enabled
             and (m.vrm_addon_extension.mtoon1.alpha_mode == 'OPAQUE') == m.use_transparent_shadow]
    check('saved and reopened, the output group and the flags are as set', gs and all(ok for ok, _n in reads)
          and all(ok for ok, _n in glossy) and not flags, f'{len(gs)} groups; wrong flags {flags[:4]}')

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
    save_sheet((a, b), os.path.join(S.OUT, 'vrm_shadows_sheet.jpg'))
    for o in figures:
        o.visible_shadow = True
    mirror(sc)


def save_sheet(pair, path):
    """the two images and their difference x 4, side by side at half size"""
    from PIL import Image
    a, b = pair
    vis = np.clip(np.abs(a - b) * 4.0, 0, 1)
    h, w = a.shape[:2]
    sheet = Image.new('RGB', (w * 3 // 2, h // 2))
    for i, im in enumerate((a, b, vis)):
        sheet.paste(Image.fromarray((im * 255).astype(np.uint8)).resize((w // 2, h // 2), Image.LANCZOS), (i * w // 2, 0))
    sheet.save(path, quality=90)


def casts():
    """{character: its meshes} in the reopened file (load_vrm puts each character's objects in its own collection)"""
    out = {}
    for c in bpy.data.collections:
        if any(o.type == 'ARMATURE' for o in c.objects):
            out[c.name] = [o for o in c.objects if o.type == 'MESH' and not o.hide_render]
    return out


def projected(sc, cam, meshes, mirrored=False):
    """the pixels the meshes (evaluated: the outline shells too) cover through the camera; mirrored: their image
    reflected in the floor's plane (z = 0)"""
    from PIL import Image, ImageDraw
    from mathutils import Matrix, Vector
    w, h = sc.render.resolution_x, sc.render.resolution_y
    dg = bpy.context.evaluated_depsgraph_get()
    proj = np.array(cam.calc_matrix_camera(dg, x=w, y=h) @ cam.matrix_world.inverted())
    flip = np.array(Matrix.Scale(-1.0, 4, Vector((0.0, 0.0, 1.0))))
    m = Image.new('L', (w, h), 0)
    draw = ImageDraw.Draw(m)
    for ob in meshes:
        ev = ob.evaluated_get(dg)
        me = ev.to_mesh()
        me.calc_loop_triangles()
        co = np.empty(len(me.vertices) * 3, np.float64)
        me.vertices.foreach_get('co', co)
        tris = np.empty(len(me.loop_triangles) * 3, np.int64)
        me.loop_triangles.foreach_get('vertices', tris)
        mw = np.array(ev.matrix_world)
        hom = np.c_[co.reshape(-1, 3), np.ones(len(co) // 3)] @ (proj @ (flip @ mw if mirrored else mw)).T
        ev.to_mesh_clear()
        front = hom[:, 3] > 1e-6
        px = np.stack([(hom[:, 0] / np.where(front, hom[:, 3], 1.0) * 0.5 + 0.5) * w,
                       (0.5 - hom[:, 1] / np.where(front, hom[:, 3], 1.0) * 0.5) * h], 1)
        for t in tris.reshape(-1, 3):
            if front[t].all():
                draw.polygon([tuple(px[i]) for i in t], fill=255)
    return np.asarray(m) > 0


def mirror(sc):
    """The floor polished dark under a planar light probe (EEVEE traces it with its Screen-Trace method, which
    probe_render sets), the two seen from low: rendered with them in the probe's capture and kept out of it."""
    floor = bpy.data.objects['floor']
    bsdf = floor.active_material.node_tree.nodes['Principled BSDF']
    bsdf.inputs['Base Color'].default_value = (0.012, 0.012, 0.014, 1.0)
    bsdf.inputs['Roughness'].default_value = 0.04
    floor.hide_probe_plane = True                     # it lies on the probe's own plane
    probe = bpy.data.objects.new('mirror', bpy.data.lightprobes.new('mirror', 'PLANE'))
    sc.collection.objects.link(probe)
    probe.scale = (8.0, 8.0, 1.0)
    cam = S.camera('cam_low', 35.0)
    S.aim(cam, (0.3, -4.4, 0.4), (0.3, 0.6, 0.8))
    cs = casts()
    p_in = os.path.join(S.OUT, 'vrm_mirror_in.png')
    p_out = os.path.join(S.OUT, 'vrm_mirror_out.png')
    check('render with the two in the planar probe\'s capture', S.still(sc, cam, 1, p_in), p_in)
    for ms in cs.values():
        for o in ms:
            o.hide_probe_plane = True
    check('render with them kept out of it (hide_probe_plane)', S.still(sc, cam, 1, p_out), p_out)
    for ms in cs.values():
        for o in ms:
            o.hide_probe_plane = False
    _l, a = luma(p_in)
    _l, b = luma(p_out)
    d = np.abs(a - b).max(2)
    own = {n: projected(sc, cam, ms) for n, ms in cs.items()}
    anyone = np.logical_or.reduce(list(own.values()))
    for n, ms in cs.items():
        img = projected(sc, cam, ms, mirrored=True) & ~anyone
        mtoon = any(s.material is not None and s.material.vrm_addon_extension.mtoon1.enabled
                    for o in ms for s in o.material_slots)
        check(f"{n} ({'MToon' if mtoon else 'glTF PBR'}) stands in the planar mirror: the floor changes where its "
              f"mirror image falls", img.sum() > 500 and d[img].mean() > 0.02,
              f'{img.sum()} px, mean change {d[img].mean() * 255:.1f}/255, '
              f'{(d[img] > 8 / 255).mean() * 100:.0f} % of them by more than 8/255')
    check('their own pixels do not change', anyone.sum() > 500 and d[anyone].mean() < 2 / 255,
          f'{anyone.sum()} px, mean change {d[anyone].mean() * 255:.2f}/255')
    save_sheet((a, b), os.path.join(S.OUT, 'vrm_mirror_sheet.jpg'))


if __name__ == '__main__':
    rc = main()
    sys.stdout.flush()
    if rc:
        sys.exit(1)
