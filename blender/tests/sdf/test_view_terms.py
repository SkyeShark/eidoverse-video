"""view_terms: a hand-written SDF's view-dependent shade() terms (fresnel rims) evaluated per pixel over the baked
channels, the part of the engine's per-pixel shade() a bake cannot hold.

Checks (always, no render):
    the hook's value lands in its Principled input, built from the shading point's direction to the viewer and the
        atlas's normal map (the field's gradient, the engine's n); the baked channel it reads stays under it
    the vertex carrier and an animated bake's played material take the hook too
    Layer Weight's fresnel reaches a Principled input; a wrong input name and a non-dict answer raise clearly
Render (unless --no-render), the stage black and unlit so the frame is the emission alone (view 'Standard'):
    a sphere whose shade() is ONLY a pow(1 - N.V, 3) lavender rim (shade_as='emission': the bake holds it head-on,
    where it is zero), the rim added back by view_terms, against the engine's own march of that shade() from the same
    camera: per pixel inside the silhouette, the error against the rim's peak
    stills: out/view_terms_sheet.png (EEVEE | march | the stylized blob lit, with its sheen | with the engine's unlit
    rim per pixel instead)

    cd <main checkout> && bash run_blender.sh <worktree>/blender/tests/sdf/test_view_terms.py [--no-render]
    (a GPU job: 4 GB VRAM, 8 GB RAM cap; on a shared machine queue it with EIDO_GPU_WRAP, blender/tests/_where.py)
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import _common as C  # noqa: E402

import bpy  # noqa: E402
import numpy as np  # noqa: E402

from eidoblend.sdf import EXAMPLES, create_sdf_object  # noqa: E402

RENDER = '--no-render' not in sys.argv
OUT = os.path.join(C.OUT, 'view_terms')
CACHE = os.path.join(OUT, 'cache')
os.makedirs(OUT, exist_ok=True)

MAP = 'vec2 map(vec3 p) { return vec2(sdSphere(p, 0.8), 1.0); }'
MAP_T = 'vec2 map(vec3 p) { return vec2(sdSphere(p, 0.6 + 0.1 * sin(uTime)), 1.0); }'
RIM_GLSL = """
vec3 shade(vec3 p, vec3 n, float mat) {
    float f = pow(1.0 - max(0.0, dot(n, normalize(cameraPosition - p))), 3.0);
    return vec3(0.9, 0.8, 1.0) * 0.3 * f;
}
"""
BOUNDS = {'min': [-1, -1, -1], 'max': [1, 1, 1]}


def rim(b, s):
    """shade()'s rim, per pixel: pow(1 - N.V, 3) x (0.9, 0.8, 1.0) x 0.3, added to the baked emission"""
    k = b.pow(1.0 - s.n_dot_v, 3.0) * 0.3
    return {'Emission Color': s.emission + b.combine(0.9 * k, 0.8 * k, 1.0 * k)}


def upstream(mat, sock):
    seen, todo = {}, [lk.from_node for lk in sock.links]
    while todo:
        n = todo.pop()
        if n.name in seen:
            continue
        seen[n.name] = n
        for s in n.inputs:
            todo += [lk.from_node for lk in s.links]
    return list(seen.values())


def principled(mat):
    return next(n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED')


W, H = 480, 270
sc = C.stage(W, H, 16, world_strength=0.0, floor=False, sun=False)     # black and unlit: the frame is the emission
# ---- the atlas carrier --------------------------------------------------------------------------------------------
obj = create_sdf_object(map=MAP, shade=RIM_GLSL, shade_as='emission', bounds=BOUNDS, quality='fast', name='vt_atlas',
                        cache_dir=CACHE, view_terms=rim)
m = obj.material
bs = principled(m)
up = upstream(m, bs.inputs['Emission Color'])
kinds = {n.type for n in up}
C.check('the hook feeds Emission Color', bs.inputs['Emission Color'].is_linked and m.get('sdf_view_terms') is not None
        and list(m['sdf_view_terms']) == ['Emission Color'], f'{len(up)} nodes')
C.check('it reads the direction to the viewer and the atlas normal map',
        'NEW_GEOMETRY' in kinds and 'NORMAL_MAP' in kinds, ', '.join(sorted(kinds)))
emit_const = [n for n in up if n.type == 'COMBXYZ' and all(not i.is_linked for i in n.inputs)
              and max(abs(i.default_value) for i in n.inputs) < 1e-6]
C.check('the baked emission (zero head-on) stays under the rim', len(emit_const) == 1 or 'TEX_IMAGE' in kinds,
        'constant zero' if emit_const else 'the emit atlas')

# ---- the vertex carrier, Layer Weight, errors ---------------------------------------------------------------------
obj_v = create_sdf_object(map=MAP, shade=RIM_GLSL, shade_as='emission', bounds=BOUNDS, quality='fast',
                          name='vt_vertex', cache_dir=CACHE, carrier='vertex',
                          view_terms=lambda b, s: {'Coat Weight': s.fresnel, 'Emission Color': rim(b, s)['Emission Color']})
bv = principled(obj_v.material)
kv = {n.type for n in upstream(obj_v.material, bv.inputs['Coat Weight'])}
C.check('the vertex carrier takes the hook', bv.inputs['Emission Color'].is_linked, obj_v.material.get('sdf_carrier'))
C.check("Layer Weight's fresnel reaches Coat Weight", 'LAYER_WEIGHT' in kv, ', '.join(sorted(kv)))
for bad, exc, what in ((lambda b, s: {'Rim Colour': 1.0}, ValueError, 'a wrong input name'),
                       (lambda b, s: [('Emission Color', 1.0)], TypeError, 'a non-dict answer')):
    try:
        create_sdf_object(map=MAP, shade=RIM_GLSL, bounds=BOUNDS, quality='fast', name='vt_bad', cache_dir=CACHE,
                          view_terms=bad)
        C.check(f'{what} raises', False, 'no error')
    except exc as e:
        C.check(f'{what} raises', True, str(e)[:120])

# ---- an animated bake's played material ---------------------------------------------------------------------------
obj_a = create_sdf_object(map=MAP_T, shade=RIM_GLSL, shade_as='emission', bounds=BOUNDS, quality='fast',
                          name='vt_anim', cache_dir=CACHE, animated=True, build=False, view_terms=rim)
obj_a.bake(1, 2)
ba = principled(obj_a.material)
C.check("an animated bake's played material takes the hook", ba.inputs['Emission Color'].is_linked and
        obj_a.material.get('sdf_view_terms') is not None, obj_a.material.name)
for o in bpy.data.objects:                        # the rim sphere alone in the render (the error cases left theirs)
    if o.type == 'MESH' and o != obj.object:
        o.hide_render = True

if RENDER:
    import OpenImageIO as oiio
    import engine_march as EM
    sc.view_settings.view_transform = 'Standard'
    sc.eevee.use_fast_gi = True
    cam = C.camera((0.0, -4.2, 0.6), (0.0, 0.0, 0.0), lens=50)
    exr = os.path.join(OUT, 'view_terms_eevee.exr')
    sc.render.image_settings.file_format = 'OPEN_EXR'
    sc.render.image_settings.color_depth = '32'
    C.render(exr)
    ee = np.asarray(oiio.ImageBuf(exr).get_pixels(oiio.FLOAT), np.float64)[::-1, :, :3]      # row 0 at the bottom
    # the march with a tight hit tolerance: at the 'fast' preset's surfEps (0.002 x the 4.2 m distance) the engine
    # stops 8 mm short of the surface, which swells its silhouette by 1.3 px and pushes the whole rim outward with
    # it (measured); the rim, not the march's tolerance, is what this compares
    ref = np.asarray(EM.march(obj, cam, W, H, samples=4, values={'uSurfEps': 1e-5, 'uMaxSteps': 512.0}), np.float64)
    inside = ref[..., 3] > 0.999
    # each pixel's distance in from the silhouette (pixels), by repeated erosion
    depth = np.zeros(inside.shape, np.int32)
    cur = inside.copy()
    for k in range(1, 40):
        depth[cur] = k
        nxt = cur.copy()
        nxt[1:-1, 1:-1] &= cur[:-2, 1:-1] & cur[2:, 1:-1] & cur[1:-1, :-2] & cur[1:-1, 2:]
        nxt[[0, -1], :] = nxt[:, [0, -1]] = False
        cur = nxt
    err = np.abs(ee - ref[..., :3]).max(axis=2)
    core = depth >= 3                       # the film filter and the silhouettes' own sub-pixel offset stay outside
    peak = float(ref[core, :3].max())
    mean_rel, p99_rel = float(err[core].mean()) / peak, float(np.percentile(err[core], 99)) / peak
    rings = ', '.join(f'{k} px {float(err[depth == k].mean()) / peak * 100:.1f} %' for k in (1, 2, 3, 4, 6, 10))
    rim_px = core & (ref[..., 2] > 0.05 * peak)
    C.check('the rim per pixel matches the engine march', mean_rel < 0.02 and p99_rel < 0.08,
            f'{int(core.sum())} pixels 3+ px inside the silhouette, peak {peak:.3f}: mean |error| '
            f'{mean_rel * 100:.2f} %, 99th percentile {p99_rel * 100:.2f} % of the peak; {int(rim_px.sum())} '
            f'carry a visible rim. Mean by distance in from the silhouette: {rings}')
    out = oiio.ImageOutput.create(os.path.join(OUT, 'view_terms_march.exr'))
    out.open(os.path.join(OUT, 'view_terms_march.exr'), oiio.ImageSpec(W, H, 4, 'float'))
    out.write_image(np.ascontiguousarray(ref[::-1], np.float32))
    out.close()
    C.save_linear_png(os.path.join(OUT, 'view_terms_eevee.png'), ee, exposure=1.5, agx=False)
    EM.save_png(os.path.join(OUT, 'view_terms_march.png'), ref, exposure=1.5)
    # the stylized blob lit on a stage: its sheen (the edition's choice), then the engine's unlit rim per pixel
    sc.render.image_settings.file_format = 'PNG'
    obj.object.hide_render = True
    sc2 = C.stage(W, H, 16)
    cam2 = C.camera((0.0, -5.2, 1.3), (0.0, 0.0, 0.75), lens=50)          # the whole blob, a margin round it
    blob = EXAMPLES['stylized_blob'].make(location=(0, 0, 0.75), time=1.0, cache_dir=CACHE, name='vt_blob')
    p_sheen = os.path.join(OUT, 'view_terms_blob_sheen.png')
    C.render(p_sheen)
    bpy.data.objects.remove(blob.object, do_unlink=True)

    def blob_rim(b, s):
        k = b.pow(1.0 - s.n_dot_v, 3.0) * 0.3
        return {'Sheen Weight': 0.0, 'Emission Color': s.emission + b.combine(0.9 * k, 0.8 * k, 1.0 * k)}
    blob2 = EXAMPLES['stylized_blob'].make(location=(0, 0, 0.75), time=1.0, cache_dir=CACHE, name='vt_blob_rim',
                                           view_terms=blob_rim)
    p_rim = os.path.join(OUT, 'view_terms_blob_rim.png')
    C.render(p_rim)
    C.sheet([os.path.join(OUT, 'view_terms_eevee.png'), os.path.join(OUT, 'view_terms_march.png'), p_sheen, p_rim],
            os.path.join(OUT, 'view_terms_sheet.png'), cols=2)
C.summary()
