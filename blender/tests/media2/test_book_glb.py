"""Probe: makeBook(gltf), the measured-GLB book path, in Blender 5.2 EEVEE (eidoblend.media.book).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/media2/test_book_glb.py
    (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py)

The janus book GLB (Simulacra and Simulators, crimson bookcloth, its own wrap, normal and ORM maps):
1. parity: the engine's own makeBook (eidoverse/book.js in Deno, book_glb_parity.mjs) measures the GLB; the
   Blender measure (measure_book_glb, on the glTF importer's objects) must give the same eight numbers.
2. the closed rig against the asset itself: the case's bounds at frame 1 against the hidden source pieces' bounds,
   and a still of each (out/book_glb_source_f001.png, out/book_glb_rig_f001.png).
3. a film: closed -> open (f1..24) on the janus spreads, a leaf turned (f32..50), then the back cover closed over
   the block (side 'back', f56..72) so it lies front-cover-down -> stills at 1, 24, 41, 54, 64, 72.
Prints PASS/FAIL lines.
"""
import json
import subprocess
import sys
from pathlib import Path

import bpy
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / 'media'))
import _stage as S  # noqa: E402
from eidoblend.media import book  # noqa: E402
from eidoblend.media.canvas_scenes import deno_exe  # noqa: E402

OUT = HERE / 'out'
RENDER = '--no-render' not in sys.argv              # --no-render: the checks only (no GPU slot needed)
GLB = S.ASSETS / 'models' / 'simulacra_and_simulators_book_janus_repligate_crimson_bookcloth_hardcover_readable_pages.glb'
FAILS = []


def check(ok, what):
    print(f"{'PASS' if ok else 'FAIL'} {what}", flush=True)
    if not ok:
        FAILS.append(what)


def engine_measure():
    r = subprocess.run([deno_exe(), 'run', '-A', '--no-config', '--node-modules-dir=none', '--cached-only',
                        str(HERE / 'book_glb_parity.mjs'), str(GLB)], capture_output=True, text=True,
                       encoding='utf-8', cwd=str(S.WORKTREE))
    if r.returncode != 0:
        raise RuntimeError(r.stderr[-2000:])
    print('[parity] engine:', r.stdout.strip().splitlines()[0])
    return json.loads(r.stdout.strip().splitlines()[-1])


def world_bounds(objs, frame=None):
    dg = bpy.context.evaluated_depsgraph_get()
    pts = []
    for o in objs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        co = np.empty(len(me.vertices) * 3)
        me.vertices.foreach_get('co', co)
        m = np.array(ev.matrix_world)
        pts.append(co.reshape(-1, 3) @ m[:3, :3].T + m[:3, 3])
        ev.to_mesh_clear()
    p = np.concatenate(pts)
    return p.min(axis=0), p.max(axis=0)


sc = S.fresh_scene(frames=(1, 72))
sc.eevee.shadow_ray_count = 4
sc.eevee.shadow_step_count = 12

# ---- 1. parity of the measure
eng = engine_measure()
m = eng['metrics']
root = book.import_book_glb(GLB)
mine = book.measure_book_glb(root)
pairs = [('halfT', m['HALF_T']), ('halfH', m['HALF_H']), ('boardLen', m['BOARD_LEN']), ('jointX', m['JOINT_X']),
         ('lip', m['LIP']), ('round', m['SPINE_D']), ('uJoint', m['U_JOINT'])]
for k, want in pairs:
    check(abs(mine[k] - want) < 2e-6, f'measure {k}: Blender {mine[k]:.7f} vs engine {want:.7f}')
check(abs(mine['foreX'] - (m['BOARD_LEN'] - m['JOINT_X'])) < 2e-6, f'measure foreX {mine["foreX"]:.7f}')

# ---- 2. + 3. the book, its film
plan = book.schedule((1, 72), open=[(1, 0.0), (24, 1.0), (56, 1.0), (72, 0.0)], turns=[(32, 50)],
                     side=[(1, 'front'), (56, 'back')])
spreads = sorted((S.ASSETS / 'book_spreads').glob('*.jpg'))
b = book.make_book(OUT / 'book_glb_work', plan, gltf=root, spreads=spreads, name='janus')
print('[book] rig spec', {k: (round(v, 5) if isinstance(v, float) else v) for k, v in b.info['rig'].items()})
check(b.gltf_root is root and set(b.source) >= {'board_front', 'board_back', 'spine'},
      f'source pieces kept and hidden: {sorted(b.source)}')
check(all(o.hide_render for o in b.source.values()), 'source pieces hidden from the render')
case_mats = [s.material.name for s in b.parts['case'].material_slots]
check(case_mats == ['janus_cloth', 'janus_lining', 'janus_trim', 'janus_inlay'],
      f'the case wears copies of the asset\'s own materials: {case_mats}')
cloth = b.parts['case'].material_slots[0].material
nmap = [n for n in cloth.node_tree.nodes if n.bl_idname == 'ShaderNodeNormalMap']
bsdf = next(n for n in cloth.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
check(nmap and nmap[0].inputs['Color'].is_linked and bsdf.inputs['Roughness'].is_linked
      and bsdf.inputs['Base Color'].is_linked, 'cloth: wrap base colour, normal map and ORM roughness wired')
uvs = {n.uv_map for n in cloth.node_tree.nodes if n.bl_idname in ('ShaderNodeUVMap', 'ShaderNodeNormalMap')}
check(uvs == {book.GLTF_UV} and book.GLTF_UV in b.parts['case'].data.uv_layers,
      f'the asset\'s images and tangents read the v-flipped layer {book.GLTF_UV}')
check(gpart_ok := all(s.material.name.startswith(('case_', 'page_')) for o in b.source.values()
                      for s in o.material_slots), 'the source pieces keep the importer\'s originals')
check(b.max_page == min(len(spreads) - 1, 26 - 2), f'max page {b.max_page} with {len(spreads)} spreads on 26 leaves')
sides = {fr['f']: fr['side'] for fr in b.states}
check(sides[50] == 'front' and sides[60] == 'back', 'cover side switches front -> back at 56')
check(b.open_amount(1) == 0.0 and abs(b.open_amount(24) - 1.0) < 1e-6 and b.page_at(1) == 0 and b.page_at(54) == 1,
      f'open_amount / page_at (the facade\'s openAmount / page): f1 {b.open_amount(1)}, f24 {b.open_amount(24)}, '
      f'pages {b.page_at(1)} -> {b.page_at(54)}; open_at=1 is the rig spec\'s openAt {b.info["rig"].get("openAt")}')

# the closed rig against the asset: the case's bounds against the source pieces' (both in the book root's space)
sc.frame_set(1)
for o in b.source.values():
    o.hide_viewport = False
src_lo, src_hi = world_bounds([o for n, o in b.source.items() if n.startswith(('board', 'spine'))])
for o in b.source.values():
    o.hide_viewport = True
rig_lo, rig_hi = world_bounds([b.parts['case']])
d = np.abs(np.concatenate([src_lo - rig_lo, src_hi - rig_hi]))
print('[book] closed case bounds: asset', np.round(src_lo, 4), np.round(src_hi, 4), '| rig', np.round(rig_lo, 4),
      np.round(rig_hi, 4))
check(d.max() < 0.0025, f'closed rig matches the asset to {d.max() * 1000:.2f} mm (bounds)')
lo, hi = b.seat_box()
print('[book] seat_box', np.round(lo, 4), np.round(hi, 4))
check(abs(lo[2]) < 0.0015, f'seat box underside at {lo[2] * 1000:.2f} mm')
under = [round(fr['minZ'] - b.states[0]['minZ'], 5) for fr in b.states]
check(min(under) > -0.0015, f'underside never sinks into the desk (lowest {min(under) * 1000:.2f} mm)')

# rig.frames: caseFrame's origin is the cross-section's start, the back board's fore-edge on the back cover's
# outer face; its Z the turning axis (the spine's length); pageFrame sits at the gutter. Closed, frame 1.
cf, pf = b.frames.get('case_frame'), b.frames.get('page_frame')
check(cf is not None and pf is not None and cf.animation_data and cf.animation_data.action,
      f'frames: {sorted(b.frames)} as keyed empties under the root')
sc.frame_set(1)
o_c, o_p = np.array(cf.matrix_world.translation), np.array(pf.matrix_world.translation)
z_c = np.array(cf.matrix_world.to_3x3().col[2])
x_fore = rig_lo[0] if abs(o_c[0] - rig_lo[0]) < abs(o_c[0] - rig_hi[0]) else rig_hi[0]
print('[book] case_frame origin', np.round(o_c, 4), 'Z', np.round(z_c, 3), '| page_frame origin', np.round(o_p, 4))
check(abs(o_c[2] - rig_lo[2]) < 0.0015 and abs(o_c[0] - x_fore) < 0.003 and abs(abs(z_c[1]) - 1) < 1e-3,
      f'case_frame at the back board\'s fore-edge on the underside ({abs(o_c[0] - x_fore) * 1000:.2f} mm from the '
      f'fore-edge, {abs(o_c[2] - rig_lo[2]) * 1000:.2f} mm from the underside), its Z along the spine')
check(rig_lo[2] < o_p[2] < rig_hi[2] and abs(o_p[0] - x_fore) > 0.05,
      f'page_frame inside the closed block, at the gutter ({abs(o_p[0] - x_fore) * 1000:.0f} mm from the fore-edge)')
sc.frame_set(24)
o_c24 = np.array(cf.matrix_world.translation)
print('[book] case_frame origin at f24 (open)', np.round(o_c24, 4))
sc.frame_set(1)

desk = S.box(sc, 'desk', (1.4, 0.9, 0.04), (0.05, 0.1, -0.02),
             S.pbr_material('desk_wood', S.cached('textures', 'PaintedWood009C_2k'), scale=1.4))
b.root.rotation_euler.z = 0.12
S.area_light(sc, (-0.6, -0.4, 0.75), (0, 0, 0), 30.0, size=0.7, color=(1.0, 0.93, 0.84), name='window')
S.area_light(sc, (0.7, 0.3, 0.6), (0, 0, 0), 6.0, size=0.8, color=(0.8, 0.86, 1.0), name='fill')
S.camera(sc, (0.05, -0.40, 0.38), (0.0, 0.0, 0.0), lens=35)

# the facade's gate: a book made without code=True ignores the call unless book.CODE_SURFACES is set
gated = b.code_surfaces()
check(gated is False and b.parts['case'].material_slots[0].material.name == 'janus_cloth',
      'code_surfaces() is gated: no code=True, no CODE_SURFACES -> False, materials untouched')
twin = book.Book(b.root, b.parts, b.info, b.out, materials=b.materials, code=True)     # make_book(code=True)'s book
check(twin.code_surfaces() is True and b.parts['case'].material_slots[0].material.name != 'janus_cloth',
      'code=True: code_surfaces() codes the surfaces')
twin.code_surfaces(False)
check(b.parts['case'].material_slots[0].material.name == 'janus_cloth', 'code=True book: materials back after (False)')

if not RENDER:
    print(f'[test_book_glb] checks only: {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
    raise SystemExit(0)
# the asset and the rig, closed, side by side in two stills
for o in b.parts.values():
    o.hide_render = True
for n, o in b.source.items():
    o.hide_render = False
S.render_still(sc, 1, OUT / 'book_glb_source_f001.png')
for o in b.parts.values():
    o.hide_render = False
for o in b.source.values():
    o.hide_render = True
stills = [OUT / 'book_glb_source_f001.png']
for fr in (1, 24, 41, 54, 64, 72):
    st = b.frame_state(fr)
    print(f'[book] frame {fr}: page {st["page"]} open {st["open"]:.2f} side {st["side"]} turn {st["turn"]}')
    stills.append(S.render_still(sc, fr, OUT / f'book_glb_f{fr:03d}.png'))

# rig.codeSurfaces(): mid-turn, every surface named by its colour; then the real materials back
check(len(b.page_materials()) == 7 and b.edge_material.name == 'janus_edge',
      f'page_materials(): {[m.name for m in b.page_materials()]}; edge_material {b.edge_material.name}')
book.CODE_SURFACES = True                                  # globalThis.__CODE_SURFACES
check(b.code_surfaces() is True, 'book.CODE_SURFACES opens the gate for every book')
coded = S.render_still(sc, 41, OUT / 'book_glb_coded_f041.png')
coded_shut = S.render_still(sc, 72, OUT / 'book_glb_coded_f072.png')      # closed, back cover up: the cloth
b.code_surfaces(False)
book.CODE_SURFACES = False
check(b.parts['case'].material_slots[0].material.name == 'janus_cloth', 'code_surfaces(False) puts the materials back')
from PIL import Image, ImageDraw, ImageFont  # noqa: E402


def hues(png):
    """Pixels per coded hue (AgX desaturates the primaries, so classify by hue, saturated pixels only)."""
    hsv = np.asarray(Image.open(png).convert('HSV')).astype(float)
    h, s, v = hsv[..., 0] * 360 / 255, hsv[..., 1] / 255, hsv[..., 2] / 255
    ok = (s > 0.3) & (v > 0.2)
    bands = {'red': (h < 15) | (h > 345), 'yellow': (h > 40) & (h < 70), 'green': (h > 85) & (h < 150),
             'cyan': (h > 160) & (h < 200), 'blue': (h > 205) & (h < 250), 'magenta': (h > 275) & (h < 335)}
    return {k: int((m & ok).sum()) for k, m in bands.items()}


open_h, shut_h = hues(coded), hues(coded_shut)
check(min(open_h['green'], open_h['yellow'], open_h['cyan'], open_h['magenta']) > 50 and shut_h['red'] > 5000,
      f'coded surfaces on screen (pixels per hue): mid-turn {open_h}; closed, back up {shut_h}')
stills.append(coded)
labels = ['the asset, f1', 'the rig, closed', 'opened, f24', 'a leaf mid-turn, f41', 'landed, f54',
          'back cover closing, f64', 'front-cover-down, f72', 'code_surfaces(), f41']
tw, th, pad = 480, 270, 6
sheet = Image.new('RGB', (4 * (tw + pad) + pad, 2 * (th + 24 + pad) + pad), (18, 18, 22))
d = ImageDraw.Draw(sheet)
fnt = ImageFont.truetype(str(S.ASSETS / 'fonts' / 'ShareTechMono-Regular.ttf'), 15)
for i, (p, lab) in enumerate(zip(stills, labels)):
    x, y = pad + (i % 4) * (tw + pad), pad + (i // 4) * (th + 24 + pad)
    d.text((x, y + 3), lab, font=fnt, fill=(232, 228, 216))
    sheet.paste(Image.open(p).convert('RGB').resize((tw, th), Image.Resampling.LANCZOS), (x, y + 24))
sheet.save(OUT / 'book_glb_sheet.png')
print(f'[test_book_glb] {"ALL OK" if not FAILS else f"{len(FAILS)} FAILED"}', flush=True)
