"""tests/post_era/test_aero_kuwahara.py: aeropittura's underpainting, ported. Its own anisotropic Kuwahara
(aeropittura.kuwahara_aniso) and the flow field it follows (aeropittura.flow_field), against ref_aero.py (the shader
transcribed into numpy), on THE HOLE frame (test_aeropittura.py's saved source, its display picture as stage A hands it
on with the echoes off), at 960 x 540 and at 1920 x 1080 (that frame doubled, bilinear); Blender's Kuwahara node beside
it (kuwahara='blender'), measured against the same reference; the cost of each, GPU and CPU compositor; a sheet of
crops at 1080p.

Run from the main checkout (a GPU job; on a shared machine queue it with EIDO_GPU_WRAP: blender/tests/_where.py), after
test_aeropittura.py --stage sources:
    bash run_blender.sh <worktree>/blender/tests/post_era/test_aero_kuwahara.py
"""
import json
import os
import sys
import time
import traceback

import bpy
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import scenes as SC                                            # noqa: E402
import ref_aero as REF                                         # noqa: E402

from eidoblend.look import frame_stats as FS                    # noqa: E402

OUT = os.path.join(SC.OUT, 'aero', 'kuwahara')
SRC_PNG = os.path.join(SC.OUT, 'aero', 'src', 'src_plain_0012.png')
FAIL, REPORT = [], {}
os.makedirs(OUT, exist_ok=True)


def check(ok, what):
    print(f"[aero_kw] {'PASS' if ok else 'FAIL'}: {what}", flush=True)
    if not ok:
        FAIL.append(what)


def load_png_linear(path):
    """A PNG through its sRGB transfer: the display picture, display-linear (top-down RGB). (A byte image's pixels
    are its stored sRGB values, measured: 156 in the file reads 156 / 255, so the transfer is undone here.)"""
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, :3]
    is_float = im.is_float
    bpy.data.images.remove(im)
    if not is_float:
        a = np.where(a < 0.04045, a / 12.92, ((a + 0.055) / 1.055) ** 2.4).astype(np.float32)
    return np.ascontiguousarray(a)


def upsample2(a):
    """2x bilinear (texel centres), edges clamped: a 1080p picture from the 540p frame."""
    H, W = a.shape[:2]
    yy, xx = np.mgrid[0:2 * H, 0:2 * W].astype(np.float32)
    return REF.sample(a, (xx + 0.5) / 2.0, (yy + 0.5) / 2.0).astype(np.float32)


def float_image(name, a):
    im = bpy.data.images.new(name, a.shape[1], a.shape[0], alpha=True, float_buffer=True)
    im.colorspace_settings.name = 'Linear Rec.709'
    px = np.ones((a.shape[0], a.shape[1], 4), np.float32)
    px[..., :3] = a
    im.pixels.foreach_set(px[::-1].ravel())
    im.pack()
    return im


def scene_for(name, W, H):
    sc = bpy.data.scenes.new(name)
    if bpy.context.window:
        bpy.context.window.scene = sc
    sc.render.engine = 'BLENDER_EEVEE'
    sc.eevee.taa_render_samples = 1
    sc.render.resolution_x, sc.render.resolution_y, sc.render.resolution_percentage = W, H, 100
    sc.view_settings.view_transform = 'Standard'
    cam = bpy.data.objects.new(name + '_cam', bpy.data.cameras.new(name + '_cam'))
    sc.collection.objects.link(cam)
    sc.camera = cam
    t = bpy.data.node_groups.new(name + '_tree', 'CompositorNodeTree')
    t.interface.new_socket(name='Image', in_out='OUTPUT', socket_type='NodeSocketColor')
    t.nodes.new('NodeGroupOutput')
    sc.compositing_node_group = t
    sc.render.use_compositing = True
    return sc, t


def build_graph(t, im, rad, S):
    """Image -> (own Kuwahara, flow, Blender's node); returns their output sockets."""
    from eidoblend.look.post import aeropittura as AP
    from eidoblend.look.post._graph import fn
    src = t.nodes.new('CompositorNodeImage')
    src.image = im

    def body(g, a):
        img = a['Image']
        co = g.coords(img)
        flow = AP.flow_field(g, img, co, 1.05)
        kw = AP.kuwahara_aniso(g, img, flow, rad)
        return {'Kw': g.rgba(kw, 1.0), 'Flow': flow}
    grp = fn(f'test_kuwa_own_r{rad}', [('Image', 'C', (0, 0, 0, 1))], [('Kw', 'C'), ('Flow', 'C')], body, rebuild=True)
    gn = t.nodes.new('CompositorNodeGroup')
    gn.node_tree = grp
    t.links.new(src.outputs['Image'], gn.inputs['Image'])
    bk = t.nodes.new('CompositorNodeKuwahara')
    bk.inputs['Type'].default_value = 'Anisotropic'
    bk.inputs['Size'].default_value = float(rad)
    bk.inputs['Uniformity'].default_value = max(1, int(round(4 * S)))
    bk.inputs['Sharpness'].default_value = 0.5
    bk.inputs['Eccentricity'].default_value = 1.0
    t.links.new(src.outputs['Image'], bk.inputs['Image'])
    sep = t.nodes.new('CompositorNodeSetAlpha')               # the flow's alpha is its energy: keep it out of the EXR
    sep.inputs['Alpha'].default_value = 1.0
    try:
        sep.inputs['Type'].default_value = 'Replace Alpha'
    except (KeyError, TypeError):
        pass
    t.links.new(gn.outputs['Flow'], sep.inputs['Image'])
    return {'own': gn.outputs['Kw'], 'flow': sep.outputs['Image'], 'blender': bk.outputs['Image'],
            'input': src.outputs['Image']}, len(grp.nodes)


def composite(sc, t, sock, path):
    out = next(n for n in t.nodes if n.bl_idname == 'NodeGroupOutput')
    for lk in list(out.inputs[0].links):
        t.links.remove(lk)
    t.links.new(sock, out.inputs[0])
    sc.frame_set(1)
    t0 = time.perf_counter()
    with bpy.context.temp_override(scene=sc):
        bpy.ops.render.render(write_still=False, scene=sc.name)
    dt = time.perf_counter() - t0
    s = sc.render.image_settings
    s.media_type, s.file_format, s.color_depth, s.exr_codec = 'IMAGE', 'OPEN_EXR', '32', 'ZIP'
    bpy.data.images['Render Result'].save_render(path, scene=sc)
    im = bpy.data.images.load(path, check_existing=False)
    a = np.array(im.pixels[:], np.float32).reshape(im.size[1], im.size[0], 4)[::-1, :, :3]
    bpy.data.images.remove(im)
    return np.ascontiguousarray(a), dt


def timed(sc, t, sock, n=4):
    out = next(nd for nd in t.nodes if nd.bl_idname == 'NodeGroupOutput')
    for lk in list(out.inputs[0].links):
        t.links.remove(lk)
    t.links.new(sock, out.inputs[0])
    ts = []
    for _ in range(n):
        t0 = time.perf_counter()
        with bpy.context.temp_override(scene=sc):
            bpy.ops.render.render(write_still=False, scene=sc.name)
        ts.append(time.perf_counter() - t0)
    return round(ts[0], 3), round(float(np.median(ts[1:])), 3)


def encode(a):
    a = np.clip(a, 0, 1)
    return np.where(a <= 0.0031308, a * 12.92, 1.055 * np.power(a, 1 / 2.4) - 0.055)


def run():
    s540 = load_png_linear(SRC_PNG)
    cases = [('540', s540), ('1080', upsample2(s540))]
    crops = {}
    for tag, s1 in cases:
        H, W = s1.shape[:2]
        S = H / 1080.0
        rad = max(3, int(round(8 * S)))
        im = float_image(f'kw_src_{tag}', s1)
        sc, t = scene_for(f'kw_{tag}', W, H)
        sc.render.compositor_device = 'GPU'
        t0 = time.perf_counter()
        socks, n_nodes = build_graph(t, im, rad, S)
        build_s = time.perf_counter() - t0
        got_own, _ = composite(sc, t, socks['own'], os.path.join(OUT, f'_own_{tag}.exr'))
        got_flow, _ = composite(sc, t, socks['flow'], os.path.join(OUT, f'_flow_{tag}.exr'))
        got_bk, _ = composite(sc, t, socks['blender'], os.path.join(OUT, f'_blender_{tag}.exr'))
        # the reference on a crop with a margin (the tensor reaches 7 S px, the Kuwahara rad px; edges clamp): her
        # face and the screens' words behind her (numpy takes some 40 s on the 1080p crop's 289 taps)
        fr_ = (0.18, 0.62, 0.28, 0.72) if tag == '540' else (0.24, 0.52, 0.36, 0.64)
        cy0, cy1, cx0, cx1 = (int(fr_[0] * H), int(fr_[1] * H), int(fr_[2] * W), int(fr_[3] * W))
        mg = rad + int(np.ceil(7 * S)) + 4
        sub = s1[cy0 - mg:cy1 + mg, cx0 - mg:cx1 + mg]
        t1 = time.perf_counter()
        flow_ref = REF.flow_field(sub, S=S)                # the reference on the crop, at the frame's S
        kw_ref = REF.kuwahara(sub, flow_ref, tap_px=1.0, S=S)
        ref_s = time.perf_counter() - t1
        inner = (slice(mg, -mg), slice(mg, -mg))
        fr, kr = flow_ref[inner], kw_ref[inner]
        fo, ko, kb = (got_flow[cy0:cy1, cx0:cx1], got_own[cy0:cy1, cx0:cx1], got_bk[cy0:cy1, cx0:cx1])
        e_flow = np.abs(fo - fr)
        e_own = np.abs(ko - kr)
        e_bk = np.abs(kb - kr)
        ident = np.abs(s1[cy0:cy1, cx0:cx1] - kr)
        lv = lambda x: float(np.abs(encode(x[0]) - encode(x[1])).mean() * 255)          # noqa: E731
        rec = {'build_s': round(build_s, 2), 'nodes_test_group': n_nodes, 'ref_s': round(ref_s, 1), 'rad': rad,
               'flow_mean': round(float(e_flow.mean()), 6), 'flow_p999': round(float(np.percentile(e_flow, 99.9)), 4),
               'own_mean': round(float(e_own.mean()), 7), 'own_max': round(float(e_own.max()), 5),
               'own_over_0.01': round(float((e_own.max(-1) > 0.01).mean()), 6),
               'own_levels': round(lv((ko, kr)), 3), 'blender_levels': round(lv((kb, kr)), 3),
               'identity_levels': round(lv((s1[cy0:cy1, cx0:cx1], kr)), 3),
               'blender_mean': round(float(e_bk.mean()), 5), 'identity_mean': round(float(ident.mean()), 5)}
        REPORT[tag] = rec
        print(f'[aero_kw] {tag}: {rec}', flush=True)
        check(rec['flow_mean'] < 2e-3, f'{tag}: the flow field (t.x, t.y, A) matches the shader in numpy (mean '
                                       f'|blender - numpy| {rec["flow_mean"]:.1e})')
        check(rec['own_mean'] < 2e-4 and rec['own_over_0.01'] < 1e-3,
              f'{tag}: the underpainting matches the shader in numpy (mean {rec["own_mean"]:.1e}, '
              f'{rec["own_over_0.01"] * 100:.3f}% of pixels off by > 0.01; {rec["own_levels"]:.3f} sRGB levels '
              f'against Blender\'s node {rec["blender_levels"]:.2f} and no filter {rec["identity_levels"]:.2f})')
        # cost: the own filter and Blender's node alone, GPU (and the CPU compositor at 540p)
        cost = {'GPU_own': timed(sc, t, socks['own']), 'GPU_blender': timed(sc, t, socks['blender']),
                'GPU_none': timed(sc, t, socks['input'])}
        if tag == '540':
            sc.render.compositor_device = 'CPU'
            cost['CPU_own'] = timed(sc, t, socks['own'], n=2)
            cost['CPU_blender'] = timed(sc, t, socks['blender'], n=2)
            sc.render.compositor_device = 'GPU'
        REPORT[tag]['cost_first_median_s'] = cost
        print(f'[aero_kw] {tag} cost (first, median s): {cost}', flush=True)
        crops[tag] = [s1[cy0:cy1, cx0:cx1], kr, ko, kb]
    # a sheet of the 1080p crops: the input, the shader in numpy, the port, Blender's node
    names = ['input (the display picture)', 'the WebGPU shader in numpy (ref_aero.py)', 'the port (kuwahara_aniso)',
             "Blender's Kuwahara node (kuwahara='blender')"]
    paths = []
    for i, a in enumerate(crops['1080']):
        p = os.path.join(OUT, f'kuwahara_1080_crop_{i}.png')
        FS.write_rgb(p, np.round(encode(a) * 255.0).astype(np.uint8))   # sRGB-encoded as it is: no second transfer
        paths.append(p)
    FS.sheet(paths, os.path.join(OUT, 'kuwahara_1080_sheet.jpg'), cols=2, tile=700, labels=names)


if not SC.already_done(OUT, 'all', os.path.abspath(__file__)):
    try:
        run()
    except Exception:
        traceback.print_exc()
        FAIL.append('exception: ' + traceback.format_exc().splitlines()[-1])
    REPORT['fail'] = FAIL
    with open(os.path.join(OUT, 'report.json'), 'w') as f:
        json.dump(REPORT, f, indent=1, default=str)
    SC.mark_done(OUT, 'all')
    print(f"[aero_kw] {'FAIL ' + str(len(FAIL)) if FAIL else 'PASS'}", flush=True)
