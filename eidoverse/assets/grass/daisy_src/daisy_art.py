# daisy_art.py — the createFlora `daisy` trim sheet, MODELLED in Blender and
# rendered orthographically, region by region, as exact emission passes.
#
#   bash run_blender.sh eidoverse/assets/grass/daisy_src/daisy_art.py work/daisy_sheet/renders [region,region]
#
# (always through the repository's isolated runner: a bare --factory-startup run against your real Blender
# config deletes your extensions' packages; see tools-guides/blender.md. README.md here has the whole pipeline.)
#
# Every region of the sheet is a real high-poly model built here in
# millimetres from the botany (Leucanthemum vulgare; reference photos from
# Wikimedia Commons via fetch_refs.py):
#   disc    — ~520 disc florets on a domed receptacle in a Vogel phyllotaxis
#             spiral: closed 5-creased buds inside, a ring of opening stars,
#             3 rows of open lemon florets with styles + anther tubes at the rim
#   petals  — 16 ray-floret variants (8 x 2 cells): notched tips (2-3 teeth),
#             converging vein grooves, V-crease, rolled edges, tubular claw,
#             a few honest blemishes (bite, brown tip, split)
#   basalA/B — spatulate crenate-lobed rosette leaves with winged petioles,
#             sunken midrib, pinnate veins to the lobes, interveinal puckering
#   stemA/B — sessile clasping stem leaves, irregular sharp teeth, lobed base
#   invol   — the involucre seen from below: three imbricate rows of convex
#             bracts with dark scarious margins round the peduncle
#   stalk   — the ribbed stem, half the circumference across u, base→top on v
#
# Passes per region (all emission — exact values, no lighting): col (linear
# albedo, alpha = coverage), dat (R roughness, G translucency), nrm (world
# normal * .5 + .5), ao (Cycles AO node). Saved as float .npy (rows bottom-
# up = v up) for assemble_sheet.py, which builds the four maps + fit json.
import bpy, math, sys, os, time
import numpy as np
from mathutils import Vector, Matrix
from mathutils import noise as bnoise

argv = sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else []
OUT = argv[0]
ONLY = set(argv[1].split(',')) if len(argv) > 1 and argv[1] else None
SS = 2                              # supersample vs the final 1024 sheet
os.makedirs(OUT, exist_ok=True)

# final sheet pixel rects (x0, y0, x1, y1) at 1024, y UP (= v)
LAYOUT = {
    'disc':   (5, 605, 419, 1019),
    'petals': (428, 605, 1020, 1019),
    'basalA': (5, 418, 640, 596),
    'basalB': (5, 236, 640, 414),
    'stemA':  (5, 124, 640, 230),
    'stemB':  (5, 12, 640, 118),
    'invol':  (648, 216, 1016, 584),
    'stalk':  (648, 12, 1016, 108),
}

def lin(c):  # sRGB 0-255 triple -> linear
    c = np.asarray(c, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)

def smoothstep(a, b, x):
    t = np.clip((np.asarray(x, dtype=np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3 - 2 * t)

class RNG:
    def __init__(self, seed): self.r = np.random.default_rng(seed)
    def u(self, a=0.0, b=1.0): return float(self.r.uniform(a, b))
    def n(self, s=1.0): return float(self.r.normal(0, s))

def vnoise(x, y, z=0.0):
    return bnoise.noise(Vector((x, y, z)))

# ── scene / material scaffolding ─────────────────────────────────────────────
bpy.ops.wm.read_factory_settings(use_empty=True)
SC = bpy.context.scene
SC.render.engine = 'CYCLES'
SC.cycles.device = 'CPU'
SC.cycles.samples = 16
SC.cycles.use_denoising = False
SC.cycles.max_bounces = 0
SC.cycles.filter_width = 1.0
SC.render.film_transparent = True
SC.view_settings.view_transform = 'Standard'
SC.render.image_settings.file_format = 'OPEN_EXR'
SC.render.image_settings.color_depth = '32'
SC.render.image_settings.color_mode = 'RGBA'
SC.render.use_persistent_data = False
W0 = bpy.data.worlds.new('W'); SC.world = W0
W0.use_nodes = True
W0.node_tree.nodes['Background'].inputs[1].default_value = 0.0

CAMD = bpy.data.cameras.new('cam'); CAMD.type = 'ORTHO'
CAMD.clip_start = 0.01; CAMD.clip_end = 500
CAM = bpy.data.objects.new('cam', CAMD); SC.collection.objects.link(CAM); SC.camera = CAM
CAM.rotation_euler = (0, 0, 0)

MAT = bpy.data.materials.new('M'); MAT.use_nodes = True
NT = MAT.node_tree; NT.nodes.clear()
N_OUT = NT.nodes.new('ShaderNodeOutputMaterial')
N_EM = NT.nodes.new('ShaderNodeEmission'); N_EM.inputs['Strength'].default_value = 1.0
NT.links.new(N_EM.outputs[0], N_OUT.inputs['Surface'])
N_COL = NT.nodes.new('ShaderNodeAttribute'); N_COL.attribute_name = 'Col'
N_DAT = NT.nodes.new('ShaderNodeAttribute'); N_DAT.attribute_name = 'Dat'
N_GEO = NT.nodes.new('ShaderNodeNewGeometry')
N_BF = NT.nodes.new('ShaderNodeMath'); N_BF.operation = 'MULTIPLY_ADD'
N_BF.inputs[1].default_value = -2.0; N_BF.inputs[2].default_value = 1.0
NT.links.new(N_GEO.outputs['Backfacing'], N_BF.inputs[0])
N_NS = NT.nodes.new('ShaderNodeVectorMath'); N_NS.operation = 'SCALE'
NT.links.new(N_GEO.outputs['Normal'], N_NS.inputs[0])
NT.links.new(N_BF.outputs[0], N_NS.inputs['Scale'])
N_VM = NT.nodes.new('ShaderNodeVectorMath'); N_VM.operation = 'MULTIPLY_ADD'
N_VM.inputs[1].default_value = (0.5, 0.5, 0.5); N_VM.inputs[2].default_value = (0.5, 0.5, 0.5)
NT.links.new(N_NS.outputs['Vector'], N_VM.inputs[0])
N_AO = NT.nodes.new('ShaderNodeAmbientOcclusion'); N_AO.samples = 24
N_AO.inputs['Color'].default_value = (1, 1, 1, 1)

def set_mode(mode, ao_dist=1.0):
    for l in list(N_EM.inputs['Color'].links): NT.links.remove(l)
    src = {'col': N_COL.outputs['Color'], 'dat': N_DAT.outputs['Color'],
           'nrm': N_VM.outputs['Vector'], 'ao': N_AO.outputs['AO']}[mode]
    NT.links.new(src, N_EM.inputs['Color'])
    N_AO.inputs['Distance'].default_value = ao_dist
    SC.cycles.samples = 48 if mode == 'ao' else 16

def make_mesh(name, V, F, col, dat, coll):
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(v) for v in np.asarray(V, dtype=np.float64)], [], [tuple(f) for f in F])
    me.update()
    n = len(me.vertices)
    ca = me.color_attributes.new('Col', 'FLOAT_COLOR', 'POINT')
    ca.data.foreach_set('color', np.asarray(col, dtype=np.float32).reshape(n, 4).ravel())
    da = me.color_attributes.new('Dat', 'FLOAT_COLOR', 'POINT')
    da.data.foreach_set('color', np.asarray(dat, dtype=np.float32).reshape(n, 4).ravel())
    me.polygons.foreach_set('use_smooth', np.ones(len(me.polygons), dtype=bool))
    me.materials.append(MAT)
    ob = bpy.data.objects.new(name, me)
    coll.objects.link(ob)
    return ob

def grid_faces(nr, nc, base=0):
    """quads of an (nr+1) x (nc+1) vertex grid, row-major, CCW seen from +Z
    when rows run +y and columns run +x"""
    F = []
    for i in range(nr):
        for j in range(nc):
            a = base + i * (nc + 1) + j
            F.append((a, a + 1, a + nc + 2, a + nc + 1))
    return F

def render_region(key, coll, framing, ao_dist, modes=('col', 'dat', 'nrm', 'ao')):
    """framing = (cx, cy, width_units, height_units) in model units; the
    region's final pixel size comes from LAYOUT, rendered at SS x."""
    x0, y0, x1, y1 = LAYOUT[key]
    pw, ph = (x1 - x0) * SS, (y1 - y0) * SS
    cx, cy, wu, hu = framing
    SC.render.resolution_x, SC.render.resolution_y = pw, ph
    SC.render.resolution_percentage = 100
    CAMD.ortho_scale = max(wu, hu)
    CAM.location = (cx, cy, 100.0)
    # hide every other region's collection
    for c in bpy.data.collections:
        c.hide_render = (c != coll)
    for mode in modes:
        set_mode(mode, ao_dist)
        path = os.path.join(OUT, f'{key}_{mode}.exr')
        SC.render.filepath = path
        t0 = time.time()
        bpy.ops.render.render(write_still=True)
        img = bpy.data.images.load(path)
        img.colorspace_settings.name = 'Non-Color'
        buf = np.empty(pw * ph * 4, dtype=np.float32)
        img.pixels.foreach_get(buf)
        np.save(os.path.join(OUT, f'{key}_{mode}.npy'), buf.reshape(ph, pw, 4))
        bpy.data.images.remove(img)
        os.remove(path)
        print(f'[art] {key}/{mode} {pw}x{ph} {time.time() - t0:.1f}s', flush=True)

def new_coll(name):
    c = bpy.data.collections.new(name)
    SC.collection.children.link(c)
    return c

def frame_to_z(up):
    """rotation matrix taking +Z to `up` (numpy 3-vector)"""
    return np.array(Vector((0, 0, 1)).rotation_difference(Vector(tuple(up))).to_matrix())

# ═════════════════════════════════════════════════════════════════════════════
# DISC — Vogel phyllotaxis florets on a domed receptacle (mm)
# ═════════════════════════════════════════════════════════════════════════════
RD = 9.0                      # receptacle radius (1.8 cm disc on a ~5 cm head)
RF = RD * 1.06                # framed radius: the rim florets flare past RD
DOME_H = 2.2

def dome_z(rho):
    rho = np.asarray(rho, dtype=np.float64)
    r2 = np.clip(rho, 0, 1.0) ** 2
    z = DOME_H * (1 - r2) ** 0.85 - 0.25 * np.exp(-(rho / 0.12) ** 2)
    return np.where(rho > 1.0, -3.0 * (rho - 1.0), z)

def dome_normal(rho, th):
    e = 1e-3
    dzdr = (dome_z(rho + e) - dome_z(max(rho - e, 0))) / ((rho + e - max(rho - e, 0)) * RD)
    n = np.array([-dzdr * math.cos(th), -dzdr * math.sin(th), 1.0])
    return n / np.linalg.norm(n)

def revolve(profile, seg, crease=None):
    """profile [(r, z)] bottom->top, last point r=0 apex. Returns V, F (tris+quads as quads w/ dup)."""
    V, F = [], []
    rings = []
    for (r, z) in profile:
        if r < 1e-6:
            rings.append([len(V)]); V.append((0.0, 0.0, z)); continue
        ring = []
        for j in range(seg):
            a = 2 * math.pi * j / seg
            rr = r * (crease(a, z) if crease else 1.0)
            ring.append(len(V)); V.append((rr * math.cos(a), rr * math.sin(a), z))
        rings.append(ring)
    for i in range(len(rings) - 1):
        A, B = rings[i], rings[i + 1]
        if len(B) == 1:
            for j in range(seg): F.append((A[j], A[(j + 1) % seg], B[0]))
        elif len(A) == 1:
            for j in range(seg): F.append((A[0], B[(j + 1) % seg], B[j]))
        else:
            for j in range(seg): F.append((A[j], A[(j + 1) % seg], B[(j + 1) % seg], B[j]))
    # bottom cap (closed)
    ring0 = rings[0]
    if len(ring0) > 1:
        c = len(V); V.append((0.0, 0.0, profile[0][1]))
        for j in range(seg): F.append((ring0[(j + 1) % seg], ring0[j], c))
    return np.array(V), F

def bud_template():
    prof = [(0.70, -0.25), (0.93, 0.10), (1.0, 0.40), (0.97, 0.66), (0.86, 0.86),
            (0.64, 1.02), (0.36, 1.12), (0.0, 1.16)]
    crease = lambda a, z: 1.0 - 0.075 * (0.5 + 0.5 * math.cos(5 * a)) * float(smoothstep(0.55, 1.05, z))
    V, F = revolve(prof, 15, crease)
    # per-vertex crease amount (for the albedo) and apex factor
    a = np.arctan2(V[:, 1], V[:, 0])
    cz = smoothstep(0.55, 1.05, V[:, 2])
    groove = (0.5 + 0.5 * np.cos(5 * a)) * cz
    apex = smoothstep(0.7, 1.16, V[:, 2])
    return V, F, groove, apex

def open_template(open_deg):
    """corolla tube + 5 spreading lobes + anther tube + bifid style (unit = rb)"""
    V, F, part = [], [], []
    def add(vs, fs, p):
        b = len(V); V.extend(vs); part.extend([p] * len(vs))
        F.extend([tuple(b + i for i in f) for f in fs])
    tv, tf = revolve([(0.60, -0.25), (0.62, 0.45), (0.66, 0.85)], 10)
    add(list(map(tuple, tv)), tf, 0)                        # tube
    oa = math.radians(open_deg)
    for k in range(5):
        a0 = 2 * math.pi * k / 5
        vs, fs = [], []
        NA, NR = 3, 3
        for i in range(NR + 1):                             # along the lobe
            t = i / NR
            hw = 0.50 * (1 - t) ** 0.8 + 0.05
            for j in range(NA + 1):
                s = j / NA * 2 - 1
                ang = a0 + s * hw
                rr = 0.66 + 0.78 * t * math.sin(oa)
                zz = 0.85 + 0.78 * t * math.cos(oa) - 0.10 * t * t
                cup = 0.06 * (1 - s * s) * t                 # lobe slightly cupped
                vs.append((rr * math.cos(ang), rr * math.sin(ang), zz + cup))
        for i in range(NR):
            for j in range(NA):
                a = i * (NA + 1) + j
                fs.append((a, a + NA + 1, a + NA + 2, a + 1))
        add(vs, fs, 1)                                      # lobes
    av, af = revolve([(0.24, 0.3), (0.25, 1.05), (0.20, 1.18), (0.0, 1.22)], 8)
    add(list(map(tuple, av)), af, 2)                        # anther tube
    for sgn in (-1, 1):                                     # the two style arms
        sv, sf = revolve([(0.07, 0.0), (0.06, 0.25), (0.0, 0.34)], 6)
        R = np.array(Matrix.Rotation(sgn * 0.62, 3, 'X'))
        sv = (sv @ R.T) + np.array([0, 0, 1.12])
        add(list(map(tuple, sv)), sf, 3)
    return np.array(V), F, np.array(part)

def build_disc():
    coll = new_coll('disc')
    rng = RNG(11)
    COL_BUD = lin((240, 138, 8)); COL_APEX = lin((250, 176, 36)); COL_CTR = lin((214, 160, 30))
    COL_LOBE = lin((252, 212, 40)); COL_TUBE = lin((242, 190, 34)); COL_ANTH = lin((236, 164, 26))
    COL_STYLE = lin((248, 220, 70)); COL_REC = lin((88, 70, 16))
    Vs, Fs, Cs, Ds = [], [], [], []
    nv = 0
    def push(V, F, C, D):
        nonlocal nv
        Vs.append(V); Fs.extend([tuple(nv + i for i in f) for f in F]); Cs.append(C); Ds.append(D)
        nv += len(V)
    # receptacle (visible only in the crevices)
    NRr, NTr = 44, 120
    rv, rf, rc = [], [], []
    for i in range(NRr + 1):
        rho = 1.05 * i / NRr
        for j in range(NTr):
            th = 2 * math.pi * j / NTr
            rv.append((rho * RD * math.cos(th), rho * RD * math.sin(th), float(dome_z(rho)) - 0.05))
    for i in range(NRr):
        for j in range(NTr):
            a = i * NTr + j; b = i * NTr + (j + 1) % NTr
            rf.append((a, a + NTr, b + NTr, b))
    rv = np.array(rv)
    rho_v = np.hypot(rv[:, 0], rv[:, 1]) / RD
    kr = smoothstep(0.7, 0.95, rho_v)[:, None]
    rcol = COL_REC[None, :] * (1 - kr) + lin((204, 160, 22))[None, :] * kr     # pollen-dusted rim
    push(rv, rf, np.c_[rcol, np.ones(len(rv))], np.tile([0.85, 0.08, 0, 1], (len(rv), 1)))

    BV, BF, BG, BA = bud_template()
    N = 540
    GA = math.pi * (3 - math.sqrt(5))
    PEXP = 0.56                    # > 0.5: florets crowd (and shrink) toward the centre
    templates = {}
    for i in range(N):
        x0, x1 = (i + 0.5) / N, (i + 1.5) / N
        rho = x0 ** PEXP
        th = i * GA
        # local hexagonal spacing from the area this floret owns on the spiral
        area = math.pi * RD * RD * (x1 ** (2 * PEXP) - x0 ** (2 * PEXP))
        spacing = math.sqrt(2 * area / math.sqrt(3))
        jitter_open = 0.022 * vnoise(math.cos(th) * 2.3, math.sin(th) * 2.3, 0.7)
        base_r = 0.57 * spacing * (1 + rng.n(0.03))
        p = np.array([rho * RD * math.cos(th), rho * RD * math.sin(th), float(dome_z(rho))])
        n = dome_normal(rho, th)
        Rm = frame_to_z(n) @ np.array(Matrix.Rotation(rng.u(0, 2 * math.pi), 3, 'Z'))
        shade = 1 + rng.n(0.05)
        if rho < 0.745 + jitter_open:
            V = BV * np.array([base_r, base_r, base_r * 1.25])
            V = V @ Rm.T + p
            ctr = float(smoothstep(0.24, 0.05, rho))
            body = COL_BUD * (1 - ctr) + COL_CTR * ctr
            C = body[None, :] * (1 - 0.30 * BG[:, None]) * shade
            C = C * (1 - BA[:, None] * 0.55) + (COL_APEX * shade)[None, :] * BA[:, None] * 0.55
            D = np.stack([0.52 + 0.1 * BG, 0.10 + 0 * BG, 0 * BG, 1 + 0 * BG], 1)
            push(V, BF, np.c_[C, np.ones(len(V))], D)
        else:
            opening = rho < 0.80 + jitter_open
            key = 'half' if opening else 'open'
            if key not in templates:
                templates[key] = open_template(28 if opening else 66)
            OV, OF, OP = templates[key]
            sc = base_r * (1.0 if opening else 1.24)
            V = OV * np.array([sc, sc, sc * 1.05])
            # rim florets lean outward a touch (the rim's star frill)
            lean = float(smoothstep(0.86, 1.0, rho)) * 0.35
            Rl = np.array(Matrix.Rotation(lean, 3, Vector((-math.sin(th), math.cos(th), 0))))
            V = V @ (Rl @ Rm).T + p
            C = np.zeros((len(V), 3))
            C[OP == 0] = COL_TUBE; C[OP == 1] = COL_LOBE; C[OP == 2] = COL_ANTH; C[OP == 3] = COL_STYLE
            if opening:
                C[OP == 1] = 0.5 * COL_LOBE + 0.5 * COL_BUD
            C = C * shade
            rough = np.where(OP == 1, 0.62, 0.5)
            D = np.stack([rough, 0.14 + 0 * rough, 0 * rough, 1 + 0 * rough], 1)
            push(V, OF, np.c_[C, np.ones(len(V))], D)
    V = np.concatenate(Vs); C = np.concatenate(Cs); D = np.concatenate(Ds)
    make_mesh('disc_hp', V, Fs, C, D, coll)
    print(f'[art] disc: {N} florets, {len(V)} verts, {len(Fs)} faces', flush=True)
    render_region('disc', coll, (0.0, 0.0, 2 * RF, 2 * RF), ao_dist=0.55)

# ═════════════════════════════════════════════════════════════════════════════
# PETALS — 16 ray florets, 8 cols x 2 rows (mm; cell = 6.66 x 18.63 mm)
# ═════════════════════════════════════════════════════════════════════════════
PX_MM = 200.0 / 18.0                   # petal texel density at 1024 (px per mm)
CELL_W, CELL_H = 74 / PX_MM, 207 / PX_MM
PETAL_L = 18.0

def petal_params(k):
    r = RNG(100 + k)
    p = dict(
        W=r.u(4.4, 5.5), belly=r.u(0.03, 0.10), bow=r.n(0.16),
        tipRound=r.u(0.05, 0.10), notchD=r.u(0.011, 0.022), notchW=r.u(0.08, 0.12),
        nV=int(r.u(5, 7.99)), crease=r.u(0.14, 0.22), clawW=r.u(0.44, 0.56),
        asym=r.n(0.08), seed=k,
    )
    kind = r.u()
    if kind < 0.6:
        p['notches'] = [-0.34 + r.n(0.04), 0.34 + r.n(0.04)]          # three teeth
    elif kind < 0.85:
        p['notches'] = [r.n(0.06)]                                     # two teeth
    else:
        p['notches'] = [-0.45 + r.n(0.05), 0.05 + r.n(0.05), 0.5 + r.n(0.04)]  # ragged four
    p['blemish'] = {5: 'bite', 11: 'brown', 14: 'split'}.get(k)
    return p

def petal_mesh(p, NY=150, NX=34):
    L, W = PETAL_L, p['W']
    ts = np.linspace(0, 1, NY + 1)
    ss = np.linspace(-1, 1, NX + 1)
    S, T = np.meshgrid(ss, ts)                         # rows = t (along), cols = s
    # the tip: rounded corners + notches, by shortening columns
    tip = p['tipRound'] * (1 - np.sqrt(np.clip(1 - S ** 2, 0, 1))) ** 1.0
    for sk in p['notches']:
        tip = tip + p['notchD'] * np.exp(-((S - sk) / p['notchW']) ** 2)
    if p['blemish'] == 'bite':
        tip = tip + 0.07 * np.exp(-((S - 0.55) / 0.22) ** 2)
    if p['blemish'] == 'split':
        tip = tip + 0.16 * np.exp(-((S + 0.05) / 0.035) ** 2)
    tip = tip + p['asym'] * 0.02 * S
    Y = T * (1 - tip) * L
    t = Y / L
    claw = p['clawW'] + (1 - p['clawW']) * smoothstep(0.0, 0.24, t)
    belly = 1 + p['belly'] * np.sin(np.pi * np.clip((t - 0.10) / 0.90, 0, 1))
    hw = 0.5 * W * claw * belly
    bow = p['bow'] * np.sin(np.pi * t) * t
    X = S * hw + bow
    # relief (mm): converging vein grooves, V-crease, trough, rolled edges,
    # tubular claw, fine longitudinal wrinkles
    Z = np.zeros_like(X)
    nV = p['nV']
    conv = 0.30 + 0.70 * smoothstep(0.0, 0.55, t)
    vein = np.zeros_like(X)
    for k in range(nV):
        sk = (-0.78 + 1.56 * k / (nV - 1)) * conv
        vein = np.maximum(vein, np.exp(-((S - sk) / 0.055) ** 2))
    Z -= 0.03 * vein
    Z -= p['crease'] * np.exp(-np.abs(S) / 0.28) * smoothstep(0.05, 0.35, t) * (1 - 0.4 * smoothstep(0.8, 1.0, t))
    Z -= 0.08 * (1 - S ** 2)
    Z -= 0.14 * smoothstep(0.80, 1.0, np.abs(S)) ** 2
    Z += 0.40 * S ** 2 * (1 - smoothstep(0.0, 0.14, t))
    wr = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            wr[i, j] = vnoise(X[i, j] * 2.6 + p['seed'] * 7.1, Y[i, j] * 0.35, 0.3)
    Z += 0.018 * wr
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    # albedo: warm white, cool-grey veins, cream-green claw, faint mottling
    # PBR register: a white ray reflects ~0.78 (photo whites are exposure)
    WHITE = lin((229, 229, 223)); CLAW = lin((200, 200, 146)); TIPC = lin((234, 234, 230))
    base = WHITE[None, None, :] * (1 - smoothstep(0.10, 0.0, t))[..., None] + \
           CLAW[None, None, :] * smoothstep(0.10, 0.0, t)[..., None]
    base = base * (1 - smoothstep(0.75, 1.0, t))[..., None] + TIPC * smoothstep(0.75, 1.0, t)[..., None]
    col = base * (1 - 0.085 * vein)[..., None] * (1 + 0.025 * wr)[..., None]
    col = col * (0.78 + 0.22 * smoothstep(0.04, 0.26, t))[..., None]    # base shaded by the disc rim
    col = col * (1 - 0.03 * np.exp(-np.abs(S) / 0.12))[..., None]           # the crease line
    if p['blemish'] == 'brown':
        spot = 0.55 * np.exp(-(((S - 0.2) / 0.45) ** 2 + ((t - 0.985) / 0.035) ** 2))
        col = col * (1 - spot[..., None]) + lin((176, 150, 104)) * spot[..., None]
    rough = 0.58 + 0.08 * vein
    transl = np.clip(0.88 - 0.18 * vein - 0.40 * smoothstep(0.12, 0.0, t) + 0.08 * smoothstep(0.7, 1.0, np.abs(S)), 0, 1)
    C = np.concatenate([col.reshape(-1, 3), np.ones((V.shape[0], 1))], 1)
    D = np.stack([rough.ravel(), transl.ravel(), np.zeros(V.shape[0]), np.ones(V.shape[0])], 1)
    F = grid_faces(NY, NX)
    return V, F, C, D

def build_petals():
    coll = new_coll('petals')
    for k in range(16):
        c, row = k % 8, k // 8
        p = petal_params(k)
        V, F, C, D = petal_mesh(p)
        V = V + np.array([c * CELL_W + CELL_W / 2, row * CELL_H + 3.5 / PX_MM, 0])
        make_mesh(f'petal{k}', V, F, C, D, coll)
    bw, bh = 8 * CELL_W, 2 * CELL_H
    print(f'[art] petals: block {bw:.2f} x {bh:.2f} mm', flush=True)
    render_region('petals', coll, (bw / 2, bh / 2, bw, bh), ao_dist=0.25)

# ═════════════════════════════════════════════════════════════════════════════
# LEAVES — basal (spatulate, crenate-lobed) and stem (sessile, toothed)
# ═════════════════════════════════════════════════════════════════════════════
def leaf_mesh(kind, seed, L, win_h_mm, NT=260, NS=40):
    r = RNG(seed)
    ts = np.linspace(0, 1, NT + 1)
    ss = np.linspace(-1, 1, NS + 1)
    S, T = np.meshgrid(ss, ts)
    side = np.sign(S) + (S == 0)
    if kind == 'basal':
        hwmax = 0.5 * win_h_mm * 0.9
        rise = 0.13 + 0.87 * smoothstep(0.06, 0.70, T) ** 1.25          # winged petiole -> blade
        tipcap = np.sqrt(np.clip(1 - np.clip((T - 0.70) / 0.30, 0, 1) ** 2, 0, 1))
        hw = np.maximum(hwmax * rise * tipcap, 0.2)
        # crenate lobes (oak-like), deepest mid-blade; each side its own phase,
        # irregular lobe widths from a warped phase
        nlob = r.u(5.0, 6.5)
        ph = np.where(side > 0, r.u(0, 1), r.u(0, 1))
        warp = 0.06 * np.sin(T * 17.0 + side * 2.0 + seed)
        lob = np.abs(np.sin(np.pi * (nlob * (T - 0.28 + warp) / 0.72 + ph))) ** 0.40
        depth = 0.36 * smoothstep(0.26, 0.46, T) * (1 - 0.5 * smoothstep(0.78, 1.0, T))
        hw = hw * (1 - depth + depth * lob)
        # small secondary teeth on the lobes
        hw = hw * (1 - 0.05 * smoothstep(0.35, 0.5, T) * np.abs(np.sin(np.pi * 3.0 * nlob * T)) ** 3)
        green = lin((80, 118, 62)); mid = lin((156, 180, 118)); edge = lin((104, 136, 74))
        mid_w = 0.45
    else:
        hwmax = 0.5 * win_h_mm * 0.82
        aur = np.exp(-((T - 0.03) / 0.028) ** 2)            # rounded clasping auricles
        body = hwmax * (0.5 + 0.5 * smoothstep(0.04, 0.32, T)) * (1 - smoothstep(0.60, 1.0, T) ** 1.5)
        hw = np.maximum(body * (1 - 0.45 * np.exp(-((T - 0.075) / 0.03) ** 2)) + hwmax * 0.42 * aur, 0.12)
        nt = r.u(8, 11)
        ph = np.where(side > 0, r.u(0, 1), r.u(0, 1))
        pos = nt * T + ph + 0.18 * np.sin(T * 23.0 + side * 1.3 + seed)   # irregular spacing
        saw = pos % 1.0
        tsize = 0.75 + 0.5 * (0.5 + 0.5 * np.sin(np.floor(pos) * 12.9898 + seed * 7.0))
        tooth = saw ** 2.6                                  # sharp forward teeth
        depth = (0.40 * (1 - smoothstep(0.1, 0.85, T)) + 0.10) * np.minimum(tsize, 1.2)
        depth = depth * smoothstep(0.07, 0.12, T)           # no teeth on the auricle
        hw = hw * (1 - depth + depth * tooth)
        green = lin((82, 124, 56)); mid = lin((140, 170, 98)); edge = lin((104, 140, 70))
        mid_w = 0.3
    # tip closure: the outermost rows pinch to the midrib
    hw = hw * (1 - smoothstep(0.985, 1.0, T))
    X = T * L
    Y = S * hw
    Z = np.zeros_like(X)
    # sunken midrib (upper side), pinnate veins aiming at the lobes / teeth
    Z -= 0.30 * np.exp(-(Y / mid_w) ** 2) * (0.4 + 0.6 * smoothstep(0.0, 0.3, T))
    vein = np.zeros_like(X)
    nveins = 7 if kind == 'basal' else 9
    for k in range(nveins):
        tv = 0.28 + 0.66 * (k + 0.5) / nveins if kind == 'basal' else 0.08 + 0.85 * (k + 0.5) / nveins
        for sgn in (-1, 1):
            # vein line from (tv - d, 0) to (tv, sgn*edge)
            x0, y0 = (tv - 0.10) * L, 0.0
            x1 = tv * L
            y1 = sgn * float(np.interp(tv, ts, hw[:, -1 if sgn > 0 else 0]))
            dx, dy = x1 - x0, y1 - y0
            l2 = dx * dx + dy * dy
            u = np.clip(((X - x0) * dx + (Y - y0) * dy) / l2, 0, 1)
            d = np.hypot(X - (x0 + dx * u), Y - (y0 + dy * u))
            vein = np.maximum(vein, np.exp(-(d / 0.22) ** 2) * (1 - 0.6 * u))
    Z -= 0.10 * vein
    puck = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            puck[i, j] = vnoise(X[i, j] * 0.55 + seed, Y[i, j] * 0.55, 1.7)
    Z += 0.12 * puck * (1 - vein)
    Z -= 0.30 * smoothstep(0.78, 1.0, np.abs(S)) ** 2          # rolled margin
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    mott = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            mott[i, j] = vnoise(X[i, j] * 0.18 + seed * 3.3, Y[i, j] * 0.18, 4.2)
    midm = np.exp(-(Y / (mid_w * 1.3)) ** 2)
    col = green[None, None, :] * (1 + 0.10 * mott)[..., None]
    col = col * (1 - 0.5 * midm)[..., None] + mid * (0.5 * midm)[..., None]
    col = col * (1 - 0.35 * vein)[..., None] + (mid * 0.85) * (0.35 * vein)[..., None]
    em = smoothstep(0.85, 1.0, np.abs(S))
    col = col * (1 - 0.4 * em)[..., None] + edge * (0.4 * em)[..., None]
    if kind == 'basal':
        base_pale = smoothstep(0.18, 0.0, T)
        col = col * (1 - 0.6 * base_pale)[..., None] + lin((170, 186, 128)) * (0.6 * base_pale)[..., None]
        if seed % 2 == 1:                                       # one lobe tip drying
            dry = np.exp(-(((T - 0.93) / 0.05) ** 2 + ((S - 0.85) / 0.3) ** 2))
            col = col * (1 - 0.7 * dry)[..., None] + lin((140, 118, 60)) * (0.7 * dry)[..., None]
    rough = 0.46 + 0.08 * midm + 0.05 * vein
    transl = np.clip(0.55 - 0.30 * midm - 0.15 * vein, 0, 1)
    C = np.concatenate([col.reshape(-1, 3), np.ones((V.shape[0], 1))], 1)
    D = np.stack([rough.ravel(), transl.ravel(), np.zeros(V.shape[0]), np.ones(V.shape[0])], 1)
    return V, [tuple(reversed(f)) for f in grid_faces(NT, NS)], C, D

def build_leaf(key, kind, seed, L):
    coll = new_coll(key)
    x0, y0, x1, y1 = LAYOUT[key]
    pw, ph = x1 - x0, y1 - y0
    mm_px = L / (pw - 16)                   # leaf spans the window minus 8 px margins
    win_h = ph * mm_px
    V, F, C, D = leaf_mesh(kind, seed, L, win_h)
    make_mesh(key, V, F, C, D, coll)
    print(f'[art] {key}: {kind} L={L}mm window {pw * mm_px:.1f} x {win_h:.1f} mm', flush=True)
    render_region(key, coll, (L / 2, 0.0, pw * mm_px, win_h), ao_dist=0.6)

# ═════════════════════════════════════════════════════════════════════════════
# INVOLUCRE — three imbricate rows of bracts, seen from below (mm)
# ═════════════════════════════════════════════════════════════════════════════
R_INV = 9.4        # framed radius: inner-row bract tips just past the cup rim

def cup_z(r):
    """receptacle underside, upright head frame (disc faces +z): a shallow bowl"""
    return -0.8 - 4.6 * np.clip(1 - (np.asarray(r) / 8.7) ** 2, 0, 1) ** 1.35

def build_invol():
    coll = new_coll('invol')
    rng = RNG(29)
    GREEN = lin((112, 146, 66)); GREEN_D = lin((58, 80, 36)); MARG = lin((104, 54, 50))
    EDGE = lin((196, 186, 150)); STEM = lin((96, 132, 58))
    Vs, Fs, Cs, Ds = [], [], [], []
    nv = 0
    def push(V, F, C, D):
        nonlocal nv
        Vs.append(V); Fs.extend([tuple(nv + i for i in f) for f in F]); Cs.append(C); Ds.append(D); nv += len(V)
    # the bowl itself (under everything)
    NR, NTh = 30, 96
    bv = []
    for i in range(NR + 1):
        r = 1.2 + (8.9 - 1.2) * i / NR
        for j in range(NTh):
            a = 2 * math.pi * j / NTh
            bv.append((r * math.cos(a), r * math.sin(a), float(cup_z(r))))
    bf = []
    for i in range(NR):
        for j in range(NTh):
            a = i * NTh + j; b = i * NTh + (j + 1) % NTh
            bf.append((a, a + NTh, b + NTh, b))
    bv = np.array(bv)
    push(bv, bf, np.tile(np.r_[GREEN_D, 1], (len(bv), 1)), np.tile([0.7, 0.2, 0, 1], (len(bv), 1)))
    # peduncle stub continuing down the axis
    sv, sf = revolve([(1.55, -9.0), (1.55, -5.2), (1.35, -4.6), (0.0, -4.5)], 16)
    push(sv, [tuple(reversed(f)) for f in sf], np.tile(np.r_[STEM, 1], (len(sv), 1)), np.tile([0.6, 0.25, 0, 1], (len(sv), 1)))
    # rows: (count, r0, r1, lift, width) — outer rows short and low, inner long
    rows = [(19, 1.7, 4.8, 0.50, 1.15), (20, 2.7, 6.4, 0.38, 1.25), (21, 3.8, 7.9, 0.26, 1.35),
            (22, 5.0, 9.3, 0.13, 1.4)]
    for ri, (cnt, r0, r1, lift, wid) in enumerate(rows):
        for k in range(cnt):
            a = 2 * math.pi * (k + 0.5 * ri) / cnt + rng.n(0.05)
            rr1 = r1 * (1 + rng.n(0.04)); w = wid * (1 + rng.n(0.08))
            NA, NW = 14, 6
            vs, cs, ds = [], [], []
            bshade = 1 + 0.08 * rng.n(1)
            for i in range(NA + 1):
                t = i / NA
                r = r0 + (rr1 - r0) * t
                # lanceolate outline; rounded-acute tip
                hw = 0.5 * w * (0.75 + 0.25 * math.sin(math.pi * min(1, t * 1.3))) * math.sqrt(max(0.0, 1 - max(0.0, (t - 0.78) / 0.22) ** 2))
                hw = max(hw, 0.02)
                for j in range(NW + 1):
                    s = j / NW * 2 - 1
                    ang = a + s * hw / r
                    z = float(cup_z(r)) - lift - 0.32 * (1 - s * s) * math.sin(math.pi * min(1, t * 1.1))
                    vs.append((r * math.cos(ang), r * math.sin(ang), z))
                    streak = 0.5 + 0.5 * vnoise(k * 3.1 + ri * 17.0, s * 2.2, t * 6.0)
                    mg = float(smoothstep(0.40, 0.78, abs(s)) + smoothstep(0.70, 0.98, t) * 0.9)
                    mg = min(1.0, mg * (0.65 + 0.55 * streak))
                    ed = float(smoothstep(0.86, 1.0, abs(s)) + smoothstep(0.95, 1.0, t))
                    ed = min(1.0, ed)
                    c = GREEN * bshade * (1 - 0.22 * np.exp(-(s / 0.18) ** 2))
                    c = c * (1 - mg) + MARG * mg
                    c = c * (1 - 0.7 * ed) + EDGE * 0.7 * ed
                    cs.append(np.r_[c, 1]); ds.append([0.5 + 0.2 * mg, 0.25 - 0.12 * mg, 0, 1])
            fs = []
            for i in range(NA):
                for j in range(NW):
                    b0 = i * (NW + 1) + j
                    fs.append((b0, b0 + NW + 1, b0 + NW + 2, b0 + 1))
            push(np.array(vs), fs, np.array(cs), np.array(ds))
    V = np.concatenate(Vs); C = np.concatenate(Cs); D = np.concatenate(Ds)
    # seen from below: mirror z so the outer surface faces the +z camera;
    # x = u, y = v stays (the gen's planar projection along the head axis)
    V = V * np.array([1, 1, -1])
    make_mesh('invol_hp', V, Fs, C, D, coll)
    print(f'[art] involucre: {len(V)} verts', flush=True)
    render_region('invol', coll, (0.0, 0.0, 2 * R_INV, 2 * R_INV), ao_dist=0.5)

# ═════════════════════════════════════════════════════════════════════════════
# STALK — ribbed stem band: u = half the circumference (5 ribs), v = base→top
# ═════════════════════════════════════════════════════════════════════════════
def build_stalk():
    coll = new_coll('stalk')
    x0, y0, x1, y1 = LAYOUT['stalk']
    pw, ph = x1 - x0, y1 - y0
    WU, HU = pw / 10.0, ph / 10.0        # model units: 1 unit = 10 px (x ~ 0.1 mm of rib)
    NX, NY = 220, 60
    xs = np.linspace(0, WU, NX + 1); ys = np.linspace(0, HU, NY + 1)
    X, Y = np.meshgrid(xs, ys)
    u = X / WU
    ribs = 5
    ph_ = u * ribs * 2 * np.pi
    Z = 0.55 * (np.abs(np.cos(ph_ / 2)) ** 0.7 - 0.6)         # angular ridges
    streak = np.zeros_like(X)
    for i in range(X.shape[0]):
        for j in range(X.shape[1]):
            streak[i, j] = vnoise(X[i, j] * 1.8, Y[i, j] * 0.08, 9.1)
    Z += 0.12 * streak
    V = np.stack([X, Y, Z], -1).reshape(-1, 3)
    v = Y / HU
    GREEN = lin((104, 146, 62)); RIDGE = lin((134, 170, 86)); BASE = lin((126, 96, 78))
    ridge = smoothstep(0.1, 0.9, np.abs(np.cos(ph_ / 2)))
    col = GREEN * (1 - 0.45 * ridge)[..., None] + RIDGE * (0.45 * ridge)[..., None]
    col = col * (1 + 0.04 * streak)[..., None]
    b = smoothstep(0.28, 0.0, v)                               # purple-brown foot
    col = col * (1 - 0.65 * b)[..., None] + BASE * (0.65 * b)[..., None]
    rough = 0.55 - 0.08 * ridge
    transl = 0.18 + 0.1 * (1 - ridge)
    C = np.concatenate([col.reshape(-1, 3), np.ones((V.shape[0], 1))], 1)
    D = np.stack([rough.ravel(), transl.ravel(), np.zeros(V.shape[0]), np.ones(V.shape[0])], 1)
    make_mesh('stalk', V, grid_faces(NY, NX), C, D, coll)
    render_region('stalk', coll, (WU / 2, HU / 2, WU, HU), ao_dist=0.6)

# ── run ──────────────────────────────────────────────────────────────────────
JOBS = {
    'disc': build_disc,
    'petals': build_petals,
    'basalA': lambda: build_leaf('basalA', 'basal', 3, 64.0),
    'basalB': lambda: build_leaf('basalB', 'basal', 8, 60.0),
    'stemA': lambda: build_leaf('stemA', 'stem', 21, 44.0),
    'stemB': lambda: build_leaf('stemB', 'stem', 34, 40.0),
    'invol': build_invol,
    'stalk': build_stalk,
}
for key, fn in JOBS.items():
    if ONLY and key not in ONLY:
        continue
    t0 = time.time()
    fn()
    print(f'[art] === {key} done in {time.time() - t0:.1f}s', flush=True)
print('[art] ALL DONE', flush=True)
sys.stdout.flush()
os._exit(0)
