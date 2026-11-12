"""Your own objects in the evening news take the set's haze (News.fog_objects): the set's FogExp2(0x0b1018, 0.011),
the haze its own materials carry, wrapped round every material of a performer, a crowd or props, a see-through one
keeping its alpha (citykit.fog_material, the city's wrap).

Without a render: what wraps and how (an opaque card, an alpha-cut card, a blended veil, a mix with a Transparent
BSDF, an additive glow, a node group that hides a transparency of its own; the claudesona and Aletheia, whose MToon
materials EEVEE renders through the VRM add-on's output group, wrapped in one copy of it), once only, unfog_material
and dispose() taking it out, a set built without fog wrapping nothing, and the chain link's own haze keeping its
alpha. --render (the GPU slot): the gate, emission cards in the 'wide' camera at 5 / 20 / 45 m view depth read from a
linear EXR: a card of your own matches the set's own fogged card and FogExp2's 0.30 / 4.7 / 21.7 %, an alpha-cut
card's open half and a blended veil show what stands behind them unveiled; the claudesona and Aletheia on the mark
take FogExp2's share at their depth (linear EXR, wrapped against not); then stills of them in the set's look,
wrapped and not (wide and crowd cameras, and 3x crops of the wide).

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sets_uf_corridor_news/test_news_fog_objects.py
    cd <main checkout> && HEAVY_VRAM_GB=4 bash work/claude_body/work/tmp/heavy.sh 12 bash run_blender.sh \
        <worktree>/blender/tests/sets_uf_corridor_news/test_news_fog_objects.py --render
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _fixture as F  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Vector  # noqa: E402

from eidoblend.sets.unknown_force import cn_lib as CL, citykit as KIT, news as NEWS  # noqa: E402

A = F.args()
RENDER = '--render' in A
OUT = F.OUT / 'fog_objects'
OUT.mkdir(parents=True, exist_ok=True)
EMIT, BACK = 0.5, (1.6, 0.9, 0.3)                       # the cards' emission; the backdrops' (warm, bright)


def principled(nt, emit):
    p = nt.nodes.new('ShaderNodeBsdfPrincipled')
    p.inputs['Base Color'].default_value = (0.0, 0.0, 0.0, 1.0)
    p.inputs['Roughness'].default_value = 1.0
    p.inputs['Specular IOR Level'].default_value = 0.0
    p.inputs['Emission Color'].default_value = (emit[0], emit[1], emit[2], 1.0) if isinstance(emit, tuple) else \
        (emit, emit, emit, 1.0)
    p.inputs['Emission Strength'].default_value = 1.0
    return p


def own_mat(name, kind='opaque', emit=EMIT):
    """A material of the filmmaker's own (not the set's): an emission-only Principled card (black base, no specular),
    see-through by kind: 'cut' (alpha 1 on the left half of the uv, 0 on the right: an alpha-cut card, dithered),
    'veil' (alpha 0.5, blended), 'mix' (Mix(uv x < 0.5, Transparent, Principled)), 'add' (Emission + Transparent,
    blended), 'group' (a node group with a Transparent BSDF inside)."""
    m = bpy.data.materials.new(name)
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    p = principled(nt, emit)
    surf = p.outputs[0]

    def left_half():
        tc = nt.nodes.new('ShaderNodeTexCoord')
        sp = nt.nodes.new('ShaderNodeSeparateXYZ')
        nt.links.new(tc.outputs['UV'], sp.inputs[0])
        lt = nt.nodes.new('ShaderNodeMath')
        lt.operation = 'LESS_THAN'
        lt.inputs[1].default_value = 0.5
        nt.links.new(sp.outputs[0], lt.inputs[0])
        return lt.outputs[0]
    if kind == 'cut':
        nt.links.new(left_half(), p.inputs['Alpha'])
    elif kind == 'veil':
        p.inputs['Alpha'].default_value = 0.5
        m.surface_render_method = 'BLENDED'
    elif kind == 'mix':
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        mx = nt.nodes.new('ShaderNodeMixShader')
        nt.links.new(left_half(), mx.inputs[0])
        nt.links.new(tr.outputs[0], mx.inputs[1])
        nt.links.new(surf, mx.inputs[2])
        surf = mx.outputs[0]
    elif kind == 'add':
        e = nt.nodes.new('ShaderNodeEmission')
        e.inputs['Color'].default_value = (emit, emit, emit, 1.0)
        tr = nt.nodes.new('ShaderNodeBsdfTransparent')
        ad = nt.nodes.new('ShaderNodeAddShader')
        nt.links.new(e.outputs[0], ad.inputs[0])
        nt.links.new(tr.outputs[0], ad.inputs[1])
        surf = ad.outputs[0]
        m.surface_render_method = 'BLENDED'
    elif kind == 'group':
        g = bpy.data.node_groups.new(f'{name}_glass', 'ShaderNodeTree')
        g.interface.new_socket('Shader', in_out='OUTPUT', socket_type='NodeSocketShader')
        go = g.nodes.new('NodeGroupOutput')
        tr = g.nodes.new('ShaderNodeBsdfTransparent')
        gp = principled(g, emit)
        mx = g.nodes.new('ShaderNodeMixShader')
        mx.inputs[0].default_value = 0.5
        g.links.new(tr.outputs[0], mx.inputs[1])
        g.links.new(gp.outputs[0], mx.inputs[2])
        g.links.new(mx.outputs[0], go.inputs[0])
        gn = nt.nodes.new('ShaderNodeGroup')
        gn.node_tree = g
        surf = gn.outputs[0]
    nt.links.new(surf, out.inputs['Surface'])
    return m


def card(name, mat, centre, right, up, size):
    """A square card of `size` metres facing the camera (its plane spanned by the camera's right and up), uv 0..1."""
    c, r, u = Vector(centre), Vector(right) * (size / 2), Vector(up) * (size / 2)
    me = bpy.data.meshes.new(name)
    me.from_pydata([c - r - u, c + r - u, c + r + u, c - r + u], [], [(0, 1, 2, 3)])
    uv = me.uv_layers.new(name='UVMap')
    for i, l in enumerate(me.loops):
        uv.data[i].uv = ((0, 0), (1, 0), (1, 1), (0, 1))[l.vertex_index]
    me.materials.append(mat)
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    return ob


def surface_src(m):
    o = next(n for n in m.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
    return o.inputs['Surface'].links[0].from_socket if o.inputs['Surface'].is_linked else None


def wrap_of(m):
    """(the wrap's top Mix Shader, what it mixes toward) when the output carries fog_material's wrap."""
    s = surface_src(m)
    if s is None or s.node.name != 'uf_fog_wrap_mix':
        return None, None
    hz = s.node.inputs[2].links[0].from_node if s.node.inputs[2].is_linked else None
    return s.node, hz


sc = F.clean_scene()
F.render_settings(960, 540, 16)
clock = F.timer()
N = NEWS.build(sc)
N.apply_look(sc)
print(f'[fog] news built in {clock():.1f}s', flush=True)
F.check("the set's fog: FogExp2(0x0b1018, 0.011), as its materials carry it",
        N.fog == {'color': 0x0b1018, 'density': 0.011}, str(N.fog))

# ------------------------------------------------------------------------------- what wraps, and how (no render)
KINDS = ('opaque', 'cut', 'veil', 'mix', 'add', 'group')
mats = {k: own_mat(f'fogtest_{k}', k) for k in KINDS}
src0 = {k: surface_src(m) for k, m in mats.items()}
obs = [card(f'fogtest_card_{k}', m, (0.0, -3.0 - 0.1 * i, 1.0), (1, 0, 0), (0, 0, 1), 0.5)
       for i, (k, m) in enumerate(mats.items())]
done, left = N.fog_objects(obs)
F.check('fog_objects: every card wraps, see-through ones included; the group hiding a transparency is left',
        (done, left) == (5, 1), f'{done} wrapped, {left} left')
g = N.fog_group()
ok, bad = True, []
for k in KINDS[:-1]:
    mx, hz = wrap_of(mats[k])
    fac = mx.inputs[0].links[0].from_node if mx is not None and mx.inputs[0].is_linked else None
    same_src = mx is not None and mx.inputs[1].is_linked and mx.inputs[1].links[0].from_socket == src0[k]
    if not (fac is not None and fac.type == 'GROUP' and fac.node_tree == g and same_src):
        bad.append(k)
F.check("each wrap mixes the material's own surface toward the set's haze group (factor, colour)", not bad, str(bad))
mx, hz = wrap_of(mats['opaque'])
F.check('an opaque card mixes toward the haze colour itself (Emission)', hz is not None and hz.type == 'EMISSION')
for k, want in (('cut', 'linked'), ('mix', 'linked'), ('veil', 0.5), ('add', 0.0)):
    _, hz = wrap_of(mats[k])
    tr = hz is not None and hz.type == 'MIX_SHADER' and hz.inputs[1].is_linked and \
        hz.inputs[1].links[0].from_node.type == 'BSDF_TRANSPARENT'
    a = None if hz is None else ('linked' if hz.inputs[0].is_linked else round(hz.inputs[0].default_value, 6))
    F.check(f"the {k} card keeps its alpha: the haze covers only what it covers (Mix(alpha, Transparent, haze), "
            f"alpha {want})", tr and a == want, f'alpha {a}')
# the cut card's alpha is its own: 1 - (1 - alpha) read back through the wrap's nodes reaches its LESS_THAN
_, hz = wrap_of(mats['cut'])
seen, stack, reach = set(), [hz.inputs[0].links[0].from_node], False
while stack:
    n = stack.pop()
    if n in seen:
        continue
    seen.add(n)
    reach |= n.type == 'MATH' and n.operation == 'LESS_THAN'
    stack += [l.from_node for s in n.inputs for l in s.links]
F.check("the alpha-cut card's coverage is read from its own Alpha link", reach)
n_wrap = sum(1 for m in mats.values() for n in m.node_tree.nodes if n.name.startswith('uf_fog_wrap'))
again = N.fog_objects(obs)
F.check('fog_objects twice: nothing wrapped twice', again == (0, 1), str(again))
n2 = sum(1 for m in mats.values() for n in m.node_tree.nodes if n.name.startswith('uf_fog_wrap'))
F.check('fog_objects twice: no wrap node added', n_wrap == n2, f'{n_wrap} -> {n2}')
KIT.unfog_material(mats['cut'])
F.check('unfog_material: the surface back on the output, no wrap node, no tag',
        surface_src(mats['cut']) == src0['cut'] and not mats['cut'].get(KIT.FOG_TAG)
        and not any(n.name.startswith('uf_fog_wrap') for n in mats['cut'].node_tree.nodes))
N.fog_objects([obs[1]])
cols = [s.default_value for s in next(n for n in g.nodes if n.type == 'COMBXYZ').inputs]
F.check("the haze group's colour is the set's (0x0b1018, linear)",
        np.allclose(cols, CL.hex_linear(0x0b1018), atol=1e-6), str([round(c, 5) for c in cols]))
# the set's own see-through material: the chain link fogs only its wire, its open diamonds stay clear
ch = N.materials['chain']
o = next(n for n in ch.node_tree.nodes if n.type == 'OUTPUT_MATERIAL')
top = o.inputs['Surface'].links[0].from_node
hz = top.inputs[2].links[0].from_node if top.type == 'MIX_SHADER' and top.inputs[2].is_linked else None
F.check("the chain link's own haze keeps its alpha (Mix(f, chain, Mix(alpha, Transparent, haze)))",
        hz is not None and hz.type == 'MIX_SHADER' and hz.inputs[0].is_linked
        and hz.inputs[1].links[0].from_node.type == 'BSDF_TRANSPARENT')

# the cast: the claudesona (opaque MToon) and Aletheia (every material's Alpha linked: cut-outs and blends)
from mathutils import Quaternion  # noqa: E402
from eidoblend.characters import vrm as V  # noqa: E402
cast = {}
for i, nm in enumerate(('claude_suit', 'aletheia')):
    before = set(bpy.data.objects)
    h = V.load_vrm(nm, location=(0.6 * (2 * i - 1), 0.0, 0.0), rotation=0.0)
    if nm == 'claude_suit':
        h.arm.scale = (0.87,) * 3                       # the scale the set's cameras were framed for
    h.write_pose({'leftUpperArm': Quaternion((0.0, 0.0, 1.0), -1.2), 'rightUpperArm': Quaternion((0.0, 0.0, 1.0), 1.2),
                  'leftLowerArm': Quaternion((0.0, 1.0, 0.0), 0.15),
                  'rightLowerArm': Quaternion((0.0, 1.0, 0.0), -0.15)})   # arms lowered (render_shots.place_her)
    cast[nm] = [o_ for o_ in bpy.data.objects if o_ not in before and o_.type == 'MESH']
def mtoon_wrap(m):
    """For a VRM's MToon material: (its output group, the wrap's top Mix Shader at that group's EEVEE output, what it
    mixes toward). EEVEE renders an MToon material through the add-on's output group's own EEVEE output."""
    gn = m.node_tree.nodes.get('Mtoon1Material.Mtoon1Output')
    if gn is None or gn.node_tree is None:
        return None, None, None
    o_ = next((n for n in gn.node_tree.nodes if n.type == 'OUTPUT_MATERIAL' and n.target == 'EEVEE'
               and n.is_active_output), None)
    s = o_.inputs['Surface'].links[0].from_node if o_ is not None and o_.inputs['Surface'].is_linked else None
    if s is None or s.name != 'uf_fog_wrap_mix':
        return gn.node_tree, None, None
    return gn.node_tree, s, (s.inputs[2].links[0].from_node if s.inputs[2].is_linked else None)


orig_out = {nm: {mtoon_wrap(s.material)[0] for o_ in ms for s in o_.material_slots if s.material} for nm, ms in cast.items()}
for nm, meshes in cast.items():
    ms = {s.material for o_ in meshes for s in o_.material_slots if s.material is not None}
    d_, l_ = N.fog_objects(meshes)
    w = [mtoon_wrap(m) for m in ms]
    copies = {t for t, _mx, _hz in w}
    alpha = sum(1 for _t, _mx, hz in w if hz is not None and hz.type == 'MIX_SHADER')
    F.check(f'{nm}: every material takes the haze ({len(ms)} materials)', d_ == len(ms) and l_ == 0,
            f'{d_} wrapped, {l_} left')
    F.check(f"{nm}: wrapped where EEVEE renders MToon, the add-on's output group's own EEVEE output, in one copy of "
            f"that group shared by the {len(ms)} materials (the add-on's group itself untouched)",
            len(copies) == 1 and all(mx is not None for _t, mx, _hz in w) and not (copies & orig_out[nm])
            and not any(n.name.startswith('uf_fog_wrap') for t in orig_out[nm] for n in t.nodes),
            f'{sorted(c.name for c in copies)}; {alpha} keeping the MToon alpha (opacity x camera ray)')
F.check("the contract reads fog_objects as a dict key too", N['fog_objects'] == N.fog_objects)


# ------------------------------------------------------------------------------------- the gate (--render)
def exr_pixels(path):
    im = bpy.data.images.load(str(path), check_existing=False)
    W_, H_ = im.size
    px = np.empty(W_ * H_ * 4, np.float32)
    im.pixels.foreach_get(px)
    bpy.data.images.remove(im)
    return px.reshape(H_, W_, 4)[::-1, :, :3]            # top-down rows


def patch(img, point, cam, half_px):
    """The mean colour of a square of half_px pixels round a world point seen by cam."""
    from bpy_extras.object_utils import world_to_camera_view
    c = world_to_camera_view(sc, cam, Vector(point))
    H_, W_ = img.shape[:2]
    x, y = c.x * W_, (1.0 - c.y) * H_
    x0, x1, y0, y1 = int(x - half_px), int(x + half_px), int(y - half_px), int(y + half_px)
    return img[max(0, y0):y1, max(0, x0):x1].reshape(-1, 3).mean(0)


if RENDER:
    for o_ in obs:
        bpy.data.objects.remove(o_, do_unlink=True)
    for meshes in cast.values():
        for o_ in meshes:
            o_.hide_render = True
    set_obs = [o_ for o_ in N.collection.all_objects if not o_.hide_render]
    for o_ in set_obs:
        o_.hide_render = True                 # the cards alone: the haze is in their materials, nothing occludes them
    cam = N.camera('wide', sc)
    bpy.context.view_layer.update()
    Mw = cam.matrix_world
    fwd, right, up = -(Mw.to_3x3() @ Vector((0, 0, 1))), Mw.to_3x3() @ Vector((1, 0, 0)), Mw.to_3x3() @ Vector((0, 1, 0))
    eye = Mw.translation
    fog_lin = np.array(CL.hex_linear(0x0b1018))
    K = 0.16                                               # a card's size per metre of view depth (93 px wide)
    rows = {5.0: 0.3, 20.0: 0.0, 45.0: -0.3}              # view depth -> the row's height (tangent of its angle)
    cols_ = {'set': -0.62, 'own': -0.31, 'bare': 0.0, 'cut': 0.31, 'veil': 0.62}
    G, CEN = {}, {}
    for d, ty in rows.items():
        size = K * d
        Ms = {'set': N.lib.mat(f'fogtest_set_{d:g}'), 'own': own_mat(f'fogtest_own_{d:g}'),
              'bare': own_mat(f'fogtest_bare_{d:g}'), 'cut': own_mat(f'fogtest_cut_{d:g}', 'cut'),
              'veil': own_mat(f'fogtest_veil_{d:g}', 'veil')}
        Ms['set'] = Ms['set'].standard((0.0, 0.0, 0.0), rough=1.0, emissive=(EMIT, EMIT, EMIT), fog=N.fog)
        next(n for n in Ms['set'].node_tree.nodes if n.type == 'BSDF_PRINCIPLED').inputs['Specular IOR Level'] \
            .default_value = 0.0
        for k, tx in cols_.items():
            c = eye + fwd * d + right * (tx * d) + up * (ty * d)
            CEN[(d, k)] = c
            G[(d, k)] = card(f'fogtest_{k}_{d:g}', Ms[k], c, right, up, size)
            if k in ('cut', 'veil'):                     # a backdrop behind it, bright, without haze
                bd = own_mat(f'fogtest_backdrop_{k}_{d:g}', emit=BACK)
                G[(d, k + '_back')] = card(f'fogtest_back_{k}_{d:g}', bd, c + fwd * (0.02 * d), right, up, size * 1.5)
        N.fog_objects([G[(d, 'own')], G[(d, 'cut')], G[(d, 'veil')]])
    sc.view_settings.view_transform = 'Standard'
    sc.view_settings.look = 'None'
    sc.view_settings.exposure = 0.0
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    exr = OUT / 'gate_wide.exr'
    F.render_still(exr, sc)
    img = exr_pixels(exr)
    half = 0.25 * K / (2 * math.tan(cam.data.angle_y / 2)) * 540 * 0.5       # a quarter of a card's half width, px
    for d in rows:
        f_exp = 1.0 - math.exp(-(0.011 * d) ** 2)
        a = {k: patch(img, CEN[(d, k)], cam, half) for k in ('set', 'own', 'bare')}
        f_meas = float(np.mean((a['bare'] - a['own']) / (a['bare'] - fog_lin)))
        F.check(f'{d:g} m: your own card takes the set\'s haze, {f_exp * 100:.2f} % (FogExp2)',
                abs(f_meas - f_exp) < 0.0015, f'measured {f_meas * 100:.2f} %')
        rel = float(np.max(np.abs(a['own'] - a['set']) / a['set']))
        F.check(f"{d:g} m: your own card matches the set's own fogged card", rel < 0.002, f'max {rel * 100:.3f} %')
        lw = CEN[(d, 'cut')]
        shift = right * (K * d * 0.25)
        solid = patch(img, lw - shift, cam, half * 0.6)
        hole = patch(img, lw + shift, cam, half * 0.6)
        bare_back = patch(img, lw + right * (K * d * 0.62), cam, half * 0.4)
        F.check(f'{d:g} m: the alpha-cut card fogs its solid half as the set does, and its open half shows the '
                f'backdrop unveiled', float(np.max(np.abs(solid - a['own']) / a['own'])) < 0.003 and
                float(np.max(np.abs(hole - np.array(BACK)) / np.array(BACK))) < 0.003,
                f'solid {solid.round(4)} vs {a["own"].round(4)}; open {hole.round(4)} vs backdrop {np.array(BACK)}, '
                f'beside it {bare_back.round(4)}')
        veil = patch(img, CEN[(d, 'veil')], cam, half)
        want = 0.5 * np.array(BACK) + 0.5 * a['own']
        F.check(f'{d:g} m: the blended veil (alpha 0.5): half the backdrop, half its own colour in the haze',
                float(np.max(np.abs(veil - want) / want)) < 0.004, f'{veil.round(4)} vs {want.round(4)}')
    G_ = list(G.values())
    for o_ in G_:
        bpy.data.objects.remove(o_, do_unlink=True)
    # ------------------------------------------------- her and Aletheia on the mark: the haze on them, linear light
    for meshes in cast.values():
        for o_ in meshes:
            o_.hide_render = False
    her_mats = {s.material for ms_ in cast.values() for o_ in ms_ for s in o_.material_slots if s.material}
    # seen from the wide camera's place through a long lens, so the two fill the frame: the haze reads the view
    # depth alone, and at the wide camera's 50 degrees they are 20 pixels tall, mostly anti-aliased edge
    mid = Vector((0.0, 0.0, 0.85))
    tele = bpy.data.objects.new('fogtest_long_lens', bpy.data.cameras.new('fogtest_long_lens'))
    sc.collection.objects.link(tele)
    tele.data.sensor_fit, tele.data.angle_y = 'VERTICAL', math.radians(4.5)
    tele.location = eye
    tele.rotation_mode = 'QUATERNION'
    tele.rotation_quaternion = (mid - eye).to_track_quat('-Z', 'Y')
    sc.camera = tele
    lin = {}
    for tag in ('fogged', 'unfogged'):
        if tag == 'unfogged':
            for m in her_mats:
                KIT.unfog_material(m)
        F.render_still(OUT / f'cast_long_lens_{tag}.exr', sc)
        lin[tag] = exr_pixels(OUT / f'cast_long_lens_{tag}.exr')
    z = (mid - eye).length                                              # her view depth through the long lens
    f_exp = 1.0 - math.exp(-(0.011 * z) ** 2)
    A_, B_ = lin['fogged'], lin['unfogged']
    on = (np.abs(A_ - B_).max(-1) > 1e-5) & ((B_ - fog_lin).max(-1) > 0.02)  # her pixels with light to fog
    inner = on.copy()                                                   # two pixels in from her silhouette
    for dy, dx in ((-2, 0), (2, 0), (0, -2), (0, 2)):
        inner &= np.roll(on, (dy, dx), axis=(0, 1))
    r = ((B_ - A_) / np.maximum(B_ - fog_lin, 1e-6))[inner]
    r_med = float(np.median(r)) if r.size else -1.0
    F.check(f"the claudesona and Aletheia on the mark ({z:.1f} m from the wide camera) take the set's haze, "
            f"{f_exp * 100:.1f} % (FogExp2)", r.size > 2000 and abs(r_med - f_exp) < 0.005,
            f'{int(inner.sum())} pixels inside their silhouettes, median {r_med * 100:.2f} %, '
            f'quartiles {np.percentile(r, 25) * 100:.2f} / {np.percentile(r, 75) * 100:.2f} %')
    bpy.data.objects.remove(tele, do_unlink=True)
    N.fog_objects([o_ for ms_ in cast.values() for o_ in ms_])
    # ------------------------------------------------------------------ the look: her and Aletheia on the mark
    for o_ in set_obs:
        o_.hide_render = False
    sc.render.image_settings.file_format = 'PNG'
    sc.render.image_settings.color_depth = '8'
    sc.view_settings.view_transform = 'AgX'
    N.apply_look(sc)
    N.apply_post(sc, aeropittura=False)
    N.update(0.3, {'spray': 1.0})
    stills = []
    for tag in ('fogged', 'unfogged'):
        if tag == 'unfogged':
            for m in her_mats:
                KIT.unfog_material(m)
        for cname in ('wide', 'crowd'):
            cam = N.camera(cname, sc)
            N.set_u('pix', CL.pix_of(sc, cam))
            p = OUT / f'cast_{cname}_{tag}.png'
            F.render_still(p, sc)
            stills.append(p)
    from PIL import Image
    cam = N.camera('wide', sc)
    from bpy_extras.object_utils import world_to_camera_view
    c = world_to_camera_view(sc, cam, Vector((0.0, 0.0, 0.9)))
    cx, cy = int(c.x * 960), int((1 - c.y) * 540)
    crops = [Image.open(OUT / f'cast_wide_{t}.png').crop((cx - 80, cy - 45, cx + 80, cy + 45)).resize((480, 270),
                                                                                                    Image.NEAREST)
             for t in ('fogged', 'unfogged')]
    sheet = Image.new('RGB', (966, 270))
    sheet.paste(crops[0], (0, 0))
    sheet.paste(crops[1], (486, 0))
    sheet.save(OUT / 'cast_wide_crop_fogged_vs_unfogged.png')
    N.fog_objects([o_ for ms_ in cast.values() for o_ in ms_])        # wrapped again, for dispose() to take out

# ------------------------------------------------------------------------------- dispose, and a set without fog
wrapped = [m for m in bpy.data.materials if m.get(KIT.FOG_TAG)]
N.dispose()
left_copies = [g_.name for g_ in bpy.data.node_groups if g_.get(KIT.FOG_TAG)]
F.check("dispose(): your own materials get their own surfaces back (a VRM its add-on's output group, the fogged "
        "copy removed) before the haze group goes",
        wrapped and not left_copies and not any(
            m.get(KIT.FOG_TAG) or any(n.name.startswith('uf_fog_wrap') for n in m.node_tree.nodes)
            or any(n.type == 'GROUP' and n.node_tree is not None and n.node_tree.get(KIT.FOG_TAG)
                   for n in m.node_tree.nodes)
            for m in wrapped if m.name in bpy.data.materials), f'{len(wrapped)} were wrapped; copies left {left_copies}')
N2 = NEWS.build(sc, {'fog': False, 'crowd': False})
F.check('a set built with fog=False: no fog, and fog_objects wraps nothing',
        N2.fog is None and N2.fog_objects(cast['claude_suit']) == (0, 0))
N2.dispose()
F.summary()
