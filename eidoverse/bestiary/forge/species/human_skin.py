"""The human's SKIN material pass (HUMAN_PLAN §5.1, H3): the anatomical ZONES with their pigment, roughness, pore and
transmission terms, and the builder of the per-vertex STAND-IN channels on the clay (until the forge's bakes land, the
same channels per texel then: species/human_skin_lut.py holds the optics and the LUTs every channel is read through).

THE PIGMENT MODEL. An identity carries its BASE pigments as uniforms: f_mel0, f_blood0, the inner arm's fractions
(m01_skin_fit: NIST's 100 forearms, f_mel 0.075-0.287 p1-p99 (model units: Jacques's 550 nm melanosome absorption,
slope 2.0), f_blood 0.0005-0.0096, median 0.0018), so the tone space is continuous and reaches past human (Hege's red,
a green alien: the shader's tint uniforms, not the maps). The maps hold only each ZONE's multipliers of those, log2-
encoded (pack R: log2(mel factor) / 12 + 0.5, G: the blood's likewise: 0.5 is x1, 0 is x1/64, 1 is x64; 8-bit
steps of 3.3 %; the lips need x21 blood, the mucosa x14), so twelve crowd identities share one set of maps (HUMAN_PLAN
§7) and differ by their uniforms.

THE ZONES, each multiplier against the inner arm, with its source:
  [X]  Xiao et al. 2017 (Skin Res Technol 23:21-29, CC BY 4.0) Table 2, the four groups' site means inverted through
       the fitted model and n-weighted (m01_skin_fit.json 'zone'): forehead x0.99 / x3.70, cheek x0.87 / x3.46, back of
       hand x1.10 / x1.69;
  [L]  the vermilion against the cheek, n = 202, CM-700d (a Chinese study's abstract, read through a search summary
       only: Lab vermilion 53.25 / 11.19 / 8.77, cheek 61.87 / 7.21 / 12.98): the cheek's colour moved by (-8.62, +3.98,
       -4.21) and inverted through the model (m02 prints the factors it lands on);
  [T]  the technician's zone rules (HUMAN_SYSTEMS §1.5: nose, cheek and ear redness, orbital darkening, the T-zone's
       roughness 0.41, the lips' 0.33, the wet lid margin's 0.24);
  [K]  Korzekwa et al. 2025 (J Clin Med, CC BY 4.0; HUMAN_BODY_PHOTOS §6.1): skin thickness by region, upper eyelid
       0.574 mm .. nasal tip 1.907 mm: the scattering's scale per region;
  [E]  my estimate, each named in the table, with what would check it.

ROUGHNESS is three's GGX roughness (alpha = r^2) of the skin's specular lobes (the shader's dual lobes scale it). The
first engine look (10-30) at the technician's values (T-zone 0.41, face 0.47, body 0.52) read as oily vinyl under a soft
sky; measured faces sit near a Beckmann m of 0.25-0.45 by region (Weyrich et al. 2006, the m = 0.3 average d'Eon &
Luebke 2007 use: read from my memory of those papers, not re-checked this round [E]), alpha ~ m, so r = sqrt(m) ~
0.50-0.67: the table below. The wet zones (lid margin 0.24, conjunctiva, caruncle, mucosa) keep their films.
"""
import numpy as np

# zone -> mel / blood multipliers (vs the inner arm), roughness, wet (0..1: the tear / mucosa film), pores (the runtime
# micro-normal's strength), freckle (the freckle layer's zone weight), tissue (skin thickness, mm: [K]), source tags
ZONES = {
    'body':      dict(mel=1.00, blood=1.00, rough=0.62, wet=0.0, pores=0.35, freckle=0.0, tissue=1.50, src='X arm; E rough'),
    'limb_out':  dict(mel=1.05, blood=1.20, rough=0.62, wet=0.0, pores=0.35, freckle=0.25, tissue=1.50, src='E: between arm and hand'),
    'shoulder':  dict(mel=1.05, blood=1.10, rough=0.60, wet=0.0, pores=0.40, freckle=0.55, tissue=1.60, src='E: sun-exposed'),
    'hand_back': dict(mel=1.10, blood=1.69, rough=0.60, wet=0.0, pores=0.30, freckle=0.30, tissue=1.20, src='X back of hand'),
    'foot_top':  dict(mel=1.10, blood=1.40, rough=0.62, wet=0.0, pores=0.30, freckle=0.0, tissue=1.30, src='E: as the hand back'),
    'palm':      dict(mel=0.30, blood=2.00, rough=0.66, wet=0.0, pores=0.55, freckle=0.0, tissue=2.50, src='E: palmoplantar melanin low'),
    'sole':      dict(mel=0.30, blood=1.50, rough=0.70, wet=0.0, pores=0.55, freckle=0.0, tissue=3.00, src='E: palmoplantar melanin low'),
    'nail':      dict(mel=0.15, blood=6.00, rough=0.30, wet=0.0, pores=0.0, freckle=0.0, tissue=0.60, src='E: the bed seen through the plate'),
    'joint':     dict(mel=1.20, blood=1.40, rough=0.66, wet=0.0, pores=0.50, freckle=0.0, tissue=1.80, src='E: knees, elbows'),
    'neck':      dict(mel=1.00, blood=2.00, rough=0.58, wet=0.0, pores=0.40, freckle=0.20, tissue=1.30, src='E: between face and trunk'),
    'scalp':     dict(mel=0.85, blood=2.60, rough=0.52, wet=0.0, pores=0.45, freckle=0.0, tissue=1.40, src='E: under hair'),
    'face':      dict(mel=0.87, blood=3.46, rough=0.60, wet=0.0, pores=0.75, freckle=1.0, tissue=1.37, src='X cheek; K buccal'),
    'forehead':  dict(mel=0.99, blood=3.70, rough=0.53, wet=0.0, pores=0.70, freckle=0.6, tissue=1.49, src='X forehead; K'),
    'nose':      dict(mel=0.95, blood=4.20, rough=0.50, wet=0.0, pores=1.00, freckle=1.0, tissue=1.60, src='T redness (E x1.13 forehead); K'),
    'chin':      dict(mel=0.95, blood=3.40, rough=0.56, wet=0.0, pores=0.70, freckle=0.3, tissue=1.61, src='E; K mental'),
    'orbital':   dict(mel=1.20, blood=2.60, rough=0.55, wet=0.0, pores=0.15, freckle=0.5, tissue=0.81, src='T orbital darkening (E x1.2); K lids'),
    'ear':       dict(mel=0.95, blood=4.00, rough=0.58, wet=0.0, pores=0.30, freckle=0.3, tissue=1.10, src='T ear redness (E)'),
    'lips':      dict(mel=None, blood=None, rough=0.42, wet=0.15, pores=0.0, freckle=0.0, tissue=1.00, src='L (calibrated in m02); E rough'),
    'mouth':     dict(mel=0.15, blood=14.0, rough=0.18, wet=1.0, pores=0.0, freckle=0.0, tissue=0.50, src='E: mucosa'),
    'socket':    dict(mel=0.10, blood=9.00, rough=0.14, wet=1.0, pores=0.0, freckle=0.0, tissue=0.30, src='E: conjunctiva'),
    'caruncle':  dict(mel=0.10, blood=12.0, rough=0.12, wet=1.0, pores=0.0, freckle=0.0, tissue=0.40, src='E: wet caruncle'),
    'lid_margin': dict(mel=0.80, blood=5.00, rough=0.24, wet=0.8, pores=0.0, freckle=0.0, tissue=0.57, src='T wet margin 0.24; K upper lid'),
}
# the order the layers paint in (each over the ones before it, by its soft mask)
ORDER = ('body', 'limb_out', 'shoulder', 'hand_back', 'foot_top', 'palm', 'sole', 'joint', 'neck', 'scalp', 'face',
         'forehead', 'chin', 'nose', 'orbital', 'ear', 'lips', 'mouth', 'socket', 'lid_margin', 'caruncle', 'nail')

# the vermilion against the cheek ([L]): Lab deltas
LIP_DELTA = (53.25 - 61.87, 11.19 - 7.21, 8.77 - 12.98)


LOG_RANGE = 12.0                 # the packs' log2 span (the TSL node decodes with the same constant)


def encode_log(f):
    """a multiplier into the pack's [0, 1]: log2(f) / 12 + 0.5 (x1/64 .. x64; the lips' blood x21, the mucosa's x14 and
    the caruncle's melanin x0.10 all inside; the first build's x16 range clipped the lips)"""
    return np.clip(np.log2(np.maximum(f, 1e-6)) / LOG_RANGE + 0.5, 0.0, 1.0)


def decode_log(e):
    return 2.0 ** ((np.asarray(e, float) - 0.5) * LOG_RANGE)


def calibrate_lips(SL, cheek_mel, cheek_blood):
    """the vermilion's multipliers vs the inner arm: the cheek's colour (at the given cheek fractions) moved by
    LIP_DELTA, inverted through the model; returns (mel factor vs cheek, blood factor vs cheek, the lip's Lab)"""
    from scipy.optimize import least_squares
    cheek = SL.lab(SL.xyz(SL.LAM, SL.sci(SL.body_reflectance(SL.LAM, cheek_mel, cheek_blood))))
    target = cheek + np.array(LIP_DELTA)

    def res(p):
        m = SL.sci(SL.body_reflectance(SL.LAM, np.exp(p[0]), np.exp(p[1])))
        return SL.lab(SL.xyz(SL.LAM, m)) - target
    s = least_squares(res, (np.log(cheek_mel), np.log(cheek_blood * 2)))
    return float(np.exp(s.x[0]) / cheek_mel), float(np.exp(s.x[1]) / cheek_blood), target, s.fun


# ------------------------------------------------------------------------------------------- the stand-in channels
def vertex_normals(V, F):
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)


def edges_of(F):
    e = np.concatenate([F[:, [0, 1]], F[:, [1, 2]], F[:, [2, 0]]])
    e = np.sort(e, axis=1)
    return np.unique(e, axis=0)


def smooth(vals, E, n, iters):
    """Laplacian smoothing of per-vertex values over the edges (uniform weights), iters passes"""
    v = np.asarray(vals, np.float64).copy()
    deg = np.bincount(E.ravel(), minlength=n).astype(np.float64)[:, None] if v.ndim > 1 else \
        np.bincount(E.ravel(), minlength=n).astype(np.float64)
    for _ in range(iters):
        acc = np.zeros_like(v)
        np.add.at(acc, E[:, 0], v[E[:, 1]])
        np.add.at(acc, E[:, 1], v[E[:, 0]])
        v = 0.5 * v + 0.5 * acc / np.maximum(deg, 1)
    return v


def curvature(V, N, E, n):
    """per-vertex curvature magnitude (1 / mm): the mean over its edges of |n_i - n_j| / |p_i - p_j| (the screen-space
    estimate's length(dN) / length(dP), as Penner's pre-integration reads it), smoothed over ~2 rings"""
    dn = np.linalg.norm(N[E[:, 0]] - N[E[:, 1]], axis=1)
    dp = np.maximum(np.linalg.norm(V[E[:, 0]] - V[E[:, 1]], axis=1), 1e-6)
    k = dn / dp
    acc = np.zeros(n)
    cnt = np.zeros(n)
    for j in range(2):
        np.add.at(acc, E[:, j], k)
        np.add.at(cnt, E[:, j], 1.0)
    return smooth(acc / np.maximum(cnt, 1), E, n, 2)


def ray_channels(V, N, F, ao_rays=48, ao_dist=60.0, seed=3, t_rays=24, t_cone=50.0):
    """per vertex, on Warp's CPU device: the THICKNESS (mm) as the SHAPE DIAMETER FUNCTION (Shapira et al. 2008, the
    bakers' thickness map): t_rays rays in a cone of t_cone deg round -N, started 0.05 mm inside, each to the surface's
    other side (capped at 80 mm), their MEDIAN; and the AMBIENT OCCLUSION (cosine-weighted hemisphere, ao_rays rays to
    ao_dist mm: the fraction unoccluded). (The first build's single ray along -N crossed every skin FOLD: the upper
    lid's crease read ~1 mm thin and glowed orange under a back light, where the tissue behind it is the orbit; a cone's
    median reads a fold as the bulk it is, and a cartilage plate, the ear, still as thin)"""
    import warp as wp
    wp.config.quiet = True
    wp.init()
    dev = 'cpu'

    @wp.kernel
    def k_rays(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), Nn: wp.array(dtype=wp.vec3), nrays: int, dist: float,
               seed: int, trays: int, cos_cone: float, tdist: wp.array2d(dtype=float), ao: wp.array(dtype=float)):
        i = wp.tid()
        p = P[i]
        n = Nn[i]
        # a frame round n
        a = wp.vec3(1.0, 0.0, 0.0)
        if wp.abs(n[0]) > 0.9:
            a = wp.vec3(0.0, 1.0, 0.0)
        t = wp.normalize(wp.cross(n, a))
        b = wp.cross(n, t)
        st = wp.rand_init(seed, i)
        # the cone's rays round -n (uniform in solid angle), their distances (the median is taken on the host)
        for k in range(trays):
            cz = 1.0 - wp.randf(st) * (1.0 - cos_cone)
            sz = wp.sqrt(wp.max(1.0 - cz * cz, 0.0))
            ph = 6.2831853 * wp.randf(st)
            d = t * (sz * wp.cos(ph)) + b * (sz * wp.sin(ph)) - n * cz
            q = wp.mesh_query_ray(mesh, p - n * 0.05, d, 80.0)
            if q.result:
                tdist[i, k] = q.t + 0.05
            else:
                tdist[i, k] = 80.0
        free = float(0.0)
        for k in range(nrays):
            u1 = wp.randf(st)
            u2 = wp.randf(st)
            r = wp.sqrt(u1)
            ph = 6.2831853 * u2
            d = t * (r * wp.cos(ph)) + b * (r * wp.sin(ph)) + n * wp.sqrt(wp.max(1.0 - u1, 0.0))
            h = wp.mesh_query_ray(mesh, p + n * 0.05, d, dist)
            if not h.result:
                free = free + 1.0
        ao[i] = free / float(nrays)

    pts = wp.array(V.astype(np.float32), dtype=wp.vec3, device=dev)
    mesh = wp.Mesh(points=pts, indices=wp.array(F.astype(np.int32).ravel(), dtype=wp.int32, device=dev))
    tdist = wp.zeros((len(V), t_rays), dtype=float, device=dev)
    ao = wp.zeros(len(V), dtype=float, device=dev)
    wp.launch(k_rays, dim=len(V), inputs=[mesh.id, pts, wp.array(N.astype(np.float32), dtype=wp.vec3, device=dev),
                                          ao_rays, ao_dist, seed, t_rays, float(np.cos(np.radians(t_cone))), tdist,
                                          ao], device=dev)
    return np.median(tdist.numpy(), axis=1).astype(np.float64), ao.numpy().astype(np.float64)


def compose(masks, n):
    """the zones' layers over each other in ORDER by their soft masks (0..1): per vertex the log2 multipliers of
    melanin and blood, roughness, wet, pores, freckle and tissue thickness"""
    out = dict(lmel=np.zeros(n), lblood=np.zeros(n), rough=np.full(n, ZONES['body']['rough']), wet=np.zeros(n),
               pores=np.full(n, ZONES['body']['pores']), freckle=np.zeros(n), tissue=np.full(n, ZONES['body']['tissue']))
    for z in ORDER:
        if z == 'body' or z not in masks:
            continue
        w = np.clip(masks[z], 0.0, 1.0)
        Z = ZONES[z]
        out['lmel'] += w * (np.log2(Z['mel']) - out['lmel'])
        out['lblood'] += w * (np.log2(Z['blood']) - out['lblood'])
        for k in ('rough', 'wet', 'pores', 'freckle', 'tissue'):
            out[k] += w * (Z[k] - out[k])
    return out
