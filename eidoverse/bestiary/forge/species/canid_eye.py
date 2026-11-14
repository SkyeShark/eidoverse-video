"""The WOLF's EYE (a canid's; W2t, the eye material builder, 10-31): its own part, seated in the head's socket, on
human_eye.py's pattern (the globe, the cornea over the limbus, the iris plane read through the cornea by a refracted view
ray) with octopus_eye.py's painted iris (a Warp kernel in eye space, the maps in the iris plane's projection).

BIOMETRY. No wolf ocular biometry was found (a SciELO preprint on two South American foxes reports smaller globes than
dogs', numbers not legible), so dogs of the wolf's mass stand in:
  * globe axial length 20.29 +- 0.59 mm at 20-35 kg (Kim, Kim, Lee, Yoon 2024, Front Vet Sci 11:1482948: transcorneal
    13 MHz ultrasound, n 12; 17.3 / 18.4 / 19.15 mm at < 5 / 5-10 / 10-20 kg), 22.1 +- 0.8 mm at 15-16 kg (Kovalcuka &
    Murniece 2020, Vet World 13:807-811, A-mode): a 35-45 kg wolf ~21-22 mm;
  * corneal diameter: normal about 16-18 mm horizontally (Whitley & Hamor, Gelatt's Veterinary Ophthalmology 6th ed.,
    ch. 19), 15.5-20 mm, a middle-sized dog's 16-18, "slightly oval" (Kafarnik et al. 2023, Sci Rep, PMC10090133, after
    Gaiddon et al. 1991 and Murphy et al. 1992): a canid's cornea spans ~0.8 of its globe (a human's 0.48);
  * corneal radius 9.19 +- 0.21 mm (Labrador, 29 kg) and 9.28 +- 0.19 (golden retriever, 30 kg), flatter with body weight
    (Spearman 0.72; Kawasaki et al. 2020, Vet Rec 186:e4, a handheld keratometer on the central 3-4 mm); Gaiddon 1991:
    39.94 +- 2.61 D (8.45 mm), the large breeds flatter;
  * anterior chamber depth 3.47 +- 0.29 mm at 20-35 kg (Kim 2024), 3.5 +- 1.0 (Kovalcuka 2020);
  * central corneal thickness 562 um (ultrasonic pachymetry) / 611 um (SD-OCT) (Whitley & Hamor).
WHAT IS USED (and why):
  * THE GLOBE is the head's sphere, its centre, radius and rest gaze read from the head at run time (seat():
    canid_hull.lid_frame, GAZE['rest']; 12 mm today, wolf.py eye.ball_r [E]). A wolf's real globe is ~10 % smaller, but
    the part must fill the socket the lids were fitted to.
  * THE CORNEA IS A VIRTUAL CAP on this head (MODE 'sphere', the default): the GEOMETRY stays the head's sphere, and the
    canid cornea (CORNEA_R 9.3 mm, the large breeds' central radius, over the limbus LIMBUS_R 8.0: a 16 mm cornea,
    its apex 1.5 mm proud of the sphere) is traced in the shading: each view ray that reaches the sphere inside the
    limbus is carried back along itself to where it crossed the cap (cap_entry), refracted there by the cap's normal
    (flattening onto the sphere's own toward the limbus, FLAT0: a real cornea's periphery is flatter than its centre),
    and followed to the iris; the same normal makes the catchlight. The head's lid rig rides a sphere: its margin sits
    at R + 0.59 mm wherever it touches the globe, and at w11's pose the lower margin passes 12 deg from the cornea's axis
    (work/bestiary/wolf/eye_mat/lid_clearance.py): every geometric cap tried pierces some margin (the dog's own
    proportions, apex +1.16 mm on this globe, by 0.34-0.82 mm; even a 0.39 mm cap by 0.14 mm). MODE 'cap' builds the
    anatomical cap (human_eye.py's soft maximum) for the day the lid rig rides the cornea.
  * THE IRIS is a shallow DOME (the canid's large lens pushes the pupil margin forward): its middle CCT + ACD (0.6 +
    3.5 mm: the dogs' central cornea and chamber) behind the virtual cap's apex, its root ROOT_DEPTH (0.5 mm) behind the
    limbus's own plane at the angle (iris_dome); the paint lies on its orthographic projection (x, y). (W2t's first
    cut, before the restart: a flat plane at R - ACD under the sphere's apex.)
  * WHAT SHOWS keeps the head's numbers: the visible iris is the head's (canid_hull GAZE limbus 7.5 mm, the circle the
    lids and the photos' irises were fitted with), so the painted iris's own radius on the plane is the one a frontal ray
    through the cornea sees at 7.5 mm (iris_radii traces it); outside it, under the cornea, the dark iridocorneal angle,
    then the pigmented limbus. The PUPIL is painted at PUPIL_VIS of the visible iris (round; the bright-light photos read
    0.15-0.30) and the runtime opens it (pupil_remap: the stroma compresses toward the root, as a real iris does).
    W2u: the pupil's edge is soft and the stroma darkens into a deep brown cloud toward it along the photos' measured
    ramp (half the plateau at ~0.45 of the iris's radius: work/bestiary/wolf/eye_mat2/pupil_profile.py), so the eye
    reads a soft dark centre, not a crisp disc. THE VISIBLE IRIS SIZE, measured like for like (eye_mat2/iris_size.py:
    the amber disc's 50 % edge on the photos at their own pixels and on the engine stills degraded to them), already
    matches: photos w12 11.3 / 12.5 mm, the engine 11.9 / 12.3, the paint's own edge 12.6; the head's 15 mm limbus
    includes the dark limbal ring, which the photos cannot part from their black conjunctiva.
  * THE IRIS'S PAINT, from the photos (work/bestiary/wolf/eye_mat/photo_iris.py, out/photo_iris.json; w12 R and w11, the
    same wolf, read in sectors the lids leave clean): the ciliary zone olive-amber (photo L* 42-58, a* 3-6, b* 19-28;
    per channel 0.42-0.46 / 0.27-0.32 / 0.14-0.17 of the white fur below the eye), the pupillary zone darker and browner
    to the collarette (~0.35 of the way out), the periphery darkening into a limbal ring (L* 46 -> 20-27 over the last
    15 %), radial fibres and a dense fine fleck (the photos' texture reads granular at 30-47 px of iris), crypts by the
    collarette, contraction furrows; the catchlight is the cornea's (the runtime's specular), never painted.
  * THE CONJUNCTIVA is dark and pigmented, as wolves' is (the W2s fresh eyes: "a dark, wet, pigmented wedge"; the photos'
    surround of the iris L* 1-11), wet (roughness 0.11); the limbus a darker band.

THE MAPS (paint): one set for both eyes, in the iris's projection: u, v = 0.5 + x / (2 UV_HALF), 0.5 + y / (2 UV_HALF)
(mm, the eye's local frame: +Z the gaze, +Y up, +X = Y x Z), inside LIMBUS_R the iris as it lies on its dome (the
runtime reads it at the refracted ray's hit), outside it the globe's surface as it projects (read at the surface point).
The right eye mirrors x (anatomy: +x is lateral in both eyes' paint), and each eye turns the iris by its own angle
(IRIS_ROT) so the two are not copies. Every map is OPAQUE (no alpha: the engine's image path divides PNG colour by a
partial alpha, work/bestiary/patches/ on the staged fix); the conjunctiva is where the eye-space radius passes
LIMBUS_R, which the runtime reads from the position, so it needs no channel.
  albedo     sRGB uint8 RGB
  orm        uint8 RGB: occlusion 1, ROUGHNESS (G: the cornea 0.05 over the iris, the conjunctiva 0.11), metalness 0
  masks      uint8 RGB, linear data: R the iris's stroma (the remix's tint region), G the limbal ring (the iris's
             periphery, the angle, the limbal band), B the pupil (eyeshine / the glow variant: the octopus eye's B)

    seat(spec, side) -> dict(centre (palate mm), R, gaze (palate unit), iris_vis)
    globe_mesh(R, side, mode) -> dict(V (mm, local), F, N, UV)
    iris_hit(P, D, R) -> (q, T): the refracted view ray's hit on the iris (the runtime's optics on the CPU)
    iris_radii(R) -> dict(r_iris, rp0, ...): the iris radii that show at the visible iris's and pupil's
    iris_lookup(P, D, R) -> (uv, in_cornea): the runtime's lookup on the CPU (for ray-traced renders: w02, the coat probe)
    eye_shade(P, D, R, side, maps) -> dict(albedo, rough, masks, n): the maps read there (linear), the shading normal
    paint(size, seed, R) -> dict(albedo, orm, masks) uint8 images in image order (row 0 = +y)
    warp_params(R, side) + the wp.func eye_uv(p, d, k): the same lookup inside a Warp kernel (w02_clay.k_view_eye)
"""
import numpy as np
import warp as wp

from .. import proc

wp.set_module_options({'enable_backward': False})

MODE = 'sphere'          # 'sphere': the cornea in the shading (this head's lids); 'cap': the geometric cap (anatomical)
LIMBUS_R = 8.0           # mm: the cornea's edge on the globe (a 16 mm cornea: dogs 16-18, Gelatt / Kafarnik)
CORNEA_R = 9.3           # mm: the cornea's central radius (Kawasaki 2020: Labrador 9.19, golden 9.28; large = flatter)
FLAT0 = 0.55             # the shading cornea flattens onto the sphere's normal from FLAT0 x LIMBUS_R to the limbus
ACD = 3.5                # mm: the anterior chamber (Kim 2024 3.47 +- 0.29 at 20-35 kg; Kovalcuka 2020 3.5)
CCT = 0.6                # mm: the central cornea (Whitley & Hamor: 562 um ultrasonic, 611 um SD-OCT)
ROOT_DEPTH = 0.5         # mm: the iris's root behind the limbus's own plane, in the iridocorneal angle [E]
IOR = 1.376              # the cornea's (the human's CFEye value; the canine cornea's index is the same within 0.005)
IRIS_VIS = 7.5           # mm: the visible iris's radius, the head's (canid_hull GAZE limbus): read at run time by seat()
PUPIL_VIS = 0.18         # the painted pupil's visible radius over the visible iris's: the reference set's bright snow
#                          light (photo_iris: w12 L 0.11, w11 0.16; the first cut's 0.28 read wide in the engine); the
#                          runtime opens it (pupil_remap / canid_eye.js U.pupil)
UV_HALF = 12.5           # mm: the maps' half width
IRIS_ROT = dict(L=23.0, R=-61.0)   # deg: each eye's turn of the iris paint (the same maps, not the same eye)
CAP_BLEND = 0.25         # mm: MODE 'cap': the cornea's soft maximum into the sphere (human_eye.py)
CAP_R = 10.9             # mm: MODE 'cap': the anatomical cornea scaled to this globe (dog 9.3 on ~10.25 mm x 1.17)
CAP_LIMBUS = 9.95        # mm: MODE 'cap': its limbus (dog 8.5 x 1.17: 56 deg of the globe)

# THE PAINT'S COLOURS (linear), from the photos (module docstring); the absolute level set by the engine's check against
# the photos' iris / white-fur ratio (work/bestiary/wolf/eye_mat/NOTES.md)
CILIARY = (0.242, 0.166, 0.070)    # the ciliary zone's ground: olive-amber (Lab ~49 / 4 / 24; the engine's snow light
#                                    puts its share of the clay at the photos' in R and G, w12 R and w11: out/engine_iris)
OLIVE = (0.180, 0.135, 0.052)      # its darker, greener drift (G/R 0.75 against the ground's 0.69: w12's olive)
AMBER = (0.300, 0.180, 0.070)      # its warmer drift
FLECK = (0.420, 0.300, 0.105)      # the yellow flecks
PUPILLARY = (0.016, 0.0095, 0.0050)  # W2u: THE DARK CENTRE's deep brown, ~0.06 of the plateau's luminance, which the
#                                    stroma darkens into toward the pupil (k_eye: the photos' measured ramp, eye_mat2/
#                                    pupil_profile.py; W2t's (0.105, 0.066, 0.030) mixed at 0.72 reached only ~0.57 of the
#                                    plateau at the pupil's edge, the engine's crisp small disc)
RUFF = (0.009, 0.006, 0.0045)      # the pupillary ruff: the pigment epithelium's rim at the pupil (W2u: between the
#                                    dark centre's cloud and the pupil; W2t's (0.032, 0.021, 0.014), lighter than the new
#                                    cloud, drew a pale halo round the pupil in the maps' 4 mm view)
PERIPHERY = (0.020, 0.0125, 0.006)  # the iris's root. W2u: the photos' ring beyond ~6.8 mm reads 0.08-0.10 of the
#                                    plateau WITH their small corneal veil (eye_mat2/iris_profiles.png), ~0.07-0.09 without;
#                                    W2t's (0.040, 0.025, 0.012) = 0.156 (photo_iris's 0.24-0.32 was read on the slope,
#                                    rho 0.85-1.0 of a circle at the amber edge)
ANGLE = (0.0075, 0.0060, 0.0052)   # the iridocorneal angle under the cornea's edge
PUPIL = (0.0045, 0.0030, 0.0022)   # the pupil: the dark eye behind it. W2u v6: a WARM near-black, the ruff's hue (W2t's
#                                    (0.0035, 0.0038, 0.0045) was bluish: under the snow sky's neutral corneal veil the
#                                    pupil and the brown cloud reach the same luminance and the hue step drew a grey-blue
#                                    disc inside the cloud, eye_mat2/NOTES.md; the photos' dark centre is one warm smudge)
LIMBAL = (0.0085, 0.0068, 0.0062)  # the pigmented limbus on the globe
CONJ = (0.016, 0.013, 0.012)       # the pigmented conjunctiva (photos: the opening outside the iris at 0.01-0.02 of
#                                    the fur below, Y; the first cut's 0.022 read ~0.05 of the clay)
ROUGH_CORNEA = 0.05
ROUGH_CONJ = 0.11


# ----------------------------------------------------------------------------------------------------- the seat
def seat(spec, side='L'):
    """the globe's seat and rest gaze as the head has them NOW (read at run time: the head builder moves the seat):
    dict(centre (palate mm: d back from the nose, q up, x the creature's left), R (mm), gaze (palate unit), iris_vis
    (the head's visible iris radius, mm))"""
    from ..heads import canid_hull as CH
    lf = CH.lid_frame(spec, side)
    g = np.asarray(CH.GAZE['rest'], np.float64)
    g = g / np.linalg.norm(g)
    if side == 'R':
        g = g * np.array([1.0, 1.0, -1.0])
    return dict(centre=np.asarray(lf['centre'], np.float64), R=float(lf['R']), gaze=g,
                iris_vis=float(CH.GAZE.get('limbus', IRIS_VIS)))


def local_frame(gaze_world, up=(0.0, 1.0, 0.0)):
    """3 x 3 whose columns are the eye's local X, Y, Z in the world: Z the gaze, Y up made normal to it, X = Y x Z"""
    z = np.asarray(gaze_world, np.float64)
    z = z / np.linalg.norm(z)
    y = np.asarray(up, np.float64) - (np.dot(up, z)) * z
    y /= np.linalg.norm(y)
    return np.stack([np.cross(y, z), y, z], 1)


# ----------------------------------------------------------------------------------------------------- the cornea
def cornea_centre(R, rl=LIMBUS_R, Rc=CORNEA_R):
    """the cornea sphere's centre on the axis (z, mm) and the limbus's plane z"""
    zl = float(np.sqrt(R * R - rl * rl))
    return zl - float(np.sqrt(Rc * Rc - rl * rl)), zl


def shade_normal(P, R, rl=LIMBUS_R, Rc=CORNEA_R, flat0=FLAT0):
    """the shading normal at points P (n, 3; local mm, on the sphere): the cornea's inside the limbus, flattening onto
    the sphere's own toward the limbus, the sphere's outside it (the runtime's, staged in the patch doc)"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    zc, _ = cornea_centre(R, rl, Rc)
    ns = P / np.linalg.norm(P, axis=1, keepdims=True)
    nc = P - np.array([0.0, 0.0, zc])
    nc /= np.linalg.norm(nc, axis=1, keepdims=True)
    rho = np.hypot(P[:, 0], P[:, 1])
    t = np.clip((rho - flat0 * rl) / ((1.0 - flat0) * rl), 0.0, 1.0)
    w = np.where(P[:, 2] > 0.0, t * t * (3.0 - 2.0 * t), 1.0)
    n = nc * (1.0 - w[:, None]) + ns * w[:, None]
    return n / np.linalg.norm(n, axis=1, keepdims=True)


def refract(D, N, eta):
    """GLSL refract: D the incident unit direction, N the unit normal against it, eta = n1 / n2"""
    D = np.atleast_2d(D)
    N = np.atleast_2d(N)
    c = -np.sum(D * N, axis=1, keepdims=True)
    k = 1.0 - eta * eta * (1.0 - c * c)
    T = eta * D + (eta * c - np.sqrt(np.maximum(k, 0.0))) * N
    return np.where(k >= 0.0, T, 0.0)


def iris_dome(R, rl=LIMBUS_R, Rc=CORNEA_R):
    """the iris's dome (module docstring): (its sphere's centre z, its radius, the middle's z, the root's z), local mm"""
    zc, zl = cornea_centre(R, rl, Rc)
    z_mid = zc + Rc - CCT - ACD                    # the pupil margin: CCT + ACD behind the virtual cap's apex
    z_root = zl - ROOT_DEPTH                       # the root in the angle
    r_root = rl - 0.1
    if z_mid <= z_root + 1e-6:                     # (a flat iris when the cap is too shallow for a dome)
        return -1.0e6, 1.0e6 + z_root, z_root, z_root
    cd = (r_root * r_root + z_root * z_root - z_mid * z_mid) / (2.0 * (z_root - z_mid))
    return float(cd), float(z_mid - cd), float(z_mid), float(z_root)


def iris_z(R):
    """the iris's middle (the pupil margin's plane), local mm"""
    return iris_dome(R)[2]


def cap_entry(P, D, R, rl=LIMBUS_R, Rc=CORNEA_R):
    """where each view ray that reaches the sphere at P (inside the limbus) crossed the VIRTUAL CAP before it: P carried
    back along -D to the cap's sphere (centre (0, 0, zc), radius Rc); outside the cap's sphere, P itself"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    D = np.atleast_2d(np.asarray(D, np.float64))
    zc, _ = cornea_centre(R, rl, Rc)
    m = P - np.array([0.0, 0.0, zc])
    b = np.sum(m * D, axis=1)
    c = np.sum(m * m, axis=1) - Rc * Rc
    s = np.where(c < 0.0, b + np.sqrt(np.maximum(b * b - c, 0.0)), 0.0)
    return P - D * s[:, None]


def iris_hit(P, D, R, rl=LIMBUS_R, Rc=CORNEA_R):
    """THE OPTICS: the view ray reaching the sphere at P (local mm) along D (unit, into the eye), entering the virtual cap
    (cap_entry), refracted there by the shading normal, and followed to the iris's dome (iris_dome; a ray that misses
    the dome's sphere stops on the root's plane). Returns (q (n, 3) the hit, mm; T the refracted directions)"""
    D = np.atleast_2d(np.asarray(D, np.float64))
    Pe = cap_entry(P, D, R, rl, Rc)
    T = refract(D, shade_normal(Pe, R, rl, Rc), 1.0 / IOR)
    cd, rd, z_mid, z_root = iris_dome(R, rl, Rc)
    m = Pe - np.array([0.0, 0.0, cd])
    b = np.sum(m * T, axis=1)
    c = np.sum(m * m, axis=1) - rd * rd
    disc = b * b - c
    t_dome = -b - np.sqrt(np.maximum(disc, 0.0))
    t_root = (z_root - Pe[:, 2]) / np.minimum(T[:, 2], -1e-3)
    t = np.where((disc >= 0.0) & (t_dome > 0.0), t_dome, t_root)
    return Pe + T * t[:, None], T


def plane_hit(P, D, R, rl=LIMBUS_R, Rc=CORNEA_R):
    """(the first cut's name) = iris_hit"""
    return iris_hit(P, D, R, rl, Rc)


def iris_radii(R, iris_vis=IRIS_VIS, pupil_vis=PUPIL_VIS, rl=LIMBUS_R, Rc=CORNEA_R, n=4001):
    """frontal rays (along -Z) through the virtual cap: the iris radius each visible radius sees, and the two the paint
    needs: r_iris (what shows at the visible iris's edge) and rp0 (at the visible pupil's), plus the radius the cornea's
    own edge sees (r_seen) and the root's plane's meeting with the globe's wall (r_wall)"""
    rs = np.linspace(0.0, rl, n)
    P = np.column_stack([rs, np.zeros(n), np.sqrt(np.maximum(R * R - rs * rs, 0.0))])
    q, _ = iris_hit(P, np.tile([0.0, 0.0, -1.0], (n, 1)), R, rl, Rc)
    rp = np.hypot(q[:, 0], q[:, 1])
    f = lambda v: float(np.interp(v, rs, rp))
    cd, rd, z_mid, z_root = iris_dome(R, rl, Rc)
    return dict(r_iris=f(iris_vis), rp0=f(pupil_vis * iris_vis), r_seen=f(rl),
                r_wall=float(np.sqrt(max(R * R - z_root * z_root, 0.0))), mag=float(iris_vis / f(iris_vis)),
                mag_pupil=float(pupil_vis * iris_vis / f(pupil_vis * iris_vis)), iris_z=z_mid, iris_root_z=z_root,
                dome_cz=cd, dome_r=rd, iris_vis=iris_vis, pupil_vis=pupil_vis * iris_vis)


def pupil_remap(q, rp, rp0, r_iris):
    """the runtime's pupil: the plane points q (n, 2+) for a pupil of radius rp (mm, plane), the paint having rp0: the
    stroma between the pupil and the root squeezed or stretched (the root fixed); inside rp the paint's pupil"""
    q = np.atleast_2d(np.asarray(q, np.float64))
    rho = np.hypot(q[:, 0], q[:, 1])
    rho0 = np.where(rho < rp, rho * rp0 / max(rp, 1e-6),
                    np.where(rho < r_iris, rp0 + (rho - rp) * (r_iris - rp0) / max(r_iris - rp, 1e-6), rho))
    s = rho0 / np.maximum(rho, 1e-9)
    out = q.copy()
    out[:, 0] *= s
    out[:, 1] *= s
    return out


def to_uv(xy, side='L'):
    """local mm (x, y) -> the maps' uv (forge convention, v up): the right eye mirrored, each eye turned by IRIS_ROT"""
    xy = np.atleast_2d(np.asarray(xy, np.float64))[:, :2]
    x = xy[:, 0] * (-1.0 if side == 'R' else 1.0)
    a = np.radians(IRIS_ROT[side])
    xr, yr = np.cos(a) * x - np.sin(a) * xy[:, 1], np.sin(a) * x + np.cos(a) * xy[:, 1]
    return np.column_stack([0.5 + xr / (2 * UV_HALF), 0.5 + yr / (2 * UV_HALF)])


def iris_lookup(P, D, R, side='L', rp=None, rl=LIMBUS_R, Rc=CORNEA_R):
    """THE RUNTIME'S LOOKUP ON THE CPU, for ray-traced renders of the eye (w02_clay.render_eye, the coat probe's look.py):
    P the hit points on the globe (local mm), D the view rays into the eye (unit, local). Inside the limbus the refracted
    ray's hit on the iris (iris_hit; its radius clamped short of the limbus: past the iris lies the dark angle, and the
    maps' ring outside LIMBUS_R is the surface's), outside it the surface point itself. rp: a runtime pupil (iris mm;
    None = the paint's). Returns (uv (n, 2) forge convention, in_cornea (n,) bool)"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    rho_s = np.hypot(P[:, 0], P[:, 1])
    inside = (rho_s < rl) & (P[:, 2] > 0.0)
    xy = P[:, :2].copy()
    if inside.any():
        Di = np.atleast_2d(D)[inside] if np.ndim(D) > 1 and len(np.atleast_2d(D)) == len(P) else \
            np.tile(np.ravel(D)[:3], (int(inside.sum()), 1))
        q, _ = iris_hit(P[inside], Di, R, rl, Rc)
        rq = np.hypot(q[:, 0], q[:, 1])
        lim = rl - 0.05
        s = np.where(rq > lim, lim / np.maximum(rq, 1e-9), 1.0)
        q = q[:, :2] * s[:, None]
        if rp is not None:
            ir = iris_radii(R)
            q = pupil_remap(q, rp, ir['rp0'], ir['r_iris'])
        xy[inside] = q
    return to_uv(xy, side), inside


def sample(img, uv):
    """bilinear read of a map (h, w, c) in image order (row 0 = v 1) at forge uvs (n, 2) (v up), clamped to the edge"""
    img = np.asarray(img)
    h, w = img.shape[:2]
    x = np.clip(uv[:, 0] * w - 0.5, 0.0, w - 1.0001)
    y = np.clip((1.0 - uv[:, 1]) * h - 0.5, 0.0, h - 1.0001)
    x0, y0 = np.floor(x).astype(np.int64), np.floor(y).astype(np.int64)
    fx, fy = (x - x0), (y - y0)
    if img.ndim == 3:
        fx, fy = fx[:, None], fy[:, None]
    a = img.astype(np.float64)
    return ((a[y0, x0] * (1 - fx) + a[y0, x0 + 1] * fx) * (1 - fy)
            + (a[y0 + 1, x0] * (1 - fx) + a[y0 + 1, x0 + 1] * fx) * fy)


def load_maps(folder):
    """the painted maps (T_EYE_albedo / orm / masks.png in a folder) as linear float images, for eye_shade"""
    import os
    from PIL import Image
    from .. import material as M
    rd = lambda k: np.asarray(Image.open(os.path.join(folder, f'T_EYE_{k}.png')).convert('RGB'), np.float64) / 255.0
    return dict(albedo=M.srgb_eotf(rd('albedo')), orm=rd('orm'), masks=rd('masks'))


def eye_shade(P, D, R, side='L', maps=None, rp=None):
    """THE RUNTIME'S MATERIAL ON THE CPU (ray-traced renders): at the globe's hit points P (local mm) seen along D (unit,
    into the eye), the albedo (linear) and masks read at the refracted lookup, the roughness at the surface point, and
    the shading normal (the virtual cap's where the ray enters it, flattening to the sphere's; the sphere's outside the
    limbus): dict(albedo (n, 3), rough (n,), masks (n, 3), n (n, 3) local, inside (n,))"""
    P = np.atleast_2d(np.asarray(P, np.float64))
    D = np.atleast_2d(np.asarray(D, np.float64))
    if len(D) != len(P):
        D = np.tile(D[0], (len(P), 1))
    uv, inside = iris_lookup(P, D, R, side, rp)
    uv_s = to_uv(P[:, :2], side)
    nrm = P / np.linalg.norm(P, axis=1, keepdims=True)
    if inside.any():
        nrm[inside] = shade_normal(cap_entry(P[inside], D[inside], R), R)
    return dict(albedo=sample(maps['albedo'], uv), rough=sample(maps['orm'], uv_s)[:, 1], masks=sample(maps['masks'], uv),
                n=nrm, inside=inside)


# ----------------------------------------------------------------------------------------------------- the globe
def globe_mesh(R, side='L', mode=MODE, n_front=30, n_back=30, n_phi=96):
    """the globe (local mm: centre at the origin, +Z the gaze, +Y up): rings in polar angle from the front pole (dense
    over the cornea), a vertex at each pole; MODE 'sphere' the head's sphere, 'cap' the anatomical cornea blended in.
    UV: to_uv of (x, y) (the back half repeats the front's projection, hidden)"""
    th_l = np.arcsin(min((CAP_LIMBUS if mode == 'cap' else LIMBUS_R) / R, 0.999))
    th = np.concatenate([np.linspace(0.0, th_l * 1.2, n_front + 1)[1:],
                         np.linspace(th_l * 1.2, np.pi, n_back + 1)[1:-1]])
    ph = np.linspace(0.0, 2 * np.pi, n_phi, endpoint=False)
    T, Pp = np.meshgrid(th, ph, indexing='ij')
    d = np.stack([np.sin(T) * np.cos(Pp), np.sin(T) * np.sin(Pp), np.cos(T)], -1)

    def radius(t):
        t = np.asarray(t, np.float64)
        if mode != 'cap':
            return np.full(t.shape, R)
        zc, _ = cornea_centre(R, CAP_LIMBUS, CAP_R)
        s = np.sin(t)
        disc = CAP_R ** 2 - (zc * s) ** 2
        rc = np.where((disc > 0) & (np.cos(t) > 0), zc * np.cos(t) + np.sqrt(np.maximum(disc, 0.0)), 0.0)
        return 0.5 * (R + rc + np.sqrt((R - rc) ** 2 + CAP_BLEND ** 2)) - 0.5 * CAP_BLEND
    r = radius(T)
    P = d * r[..., None]
    V = np.concatenate([[[0.0, 0.0, float(radius(np.array(0.0)))]], P.reshape(-1, 3), [[0.0, 0.0, -R]]])
    nr, nphi = T.shape
    idx = (np.arange(nr * nphi) + 1).reshape(nr, nphi)
    F = []
    for j in range(nphi):
        F.append([0, idx[0, j], idx[0, (j + 1) % nphi]])
    for i in range(nr - 1):
        for j in range(nphi):
            a, b = idx[i, j], idx[i, (j + 1) % nphi]
            c, e = idx[i + 1, j], idx[i + 1, (j + 1) % nphi]
            F.append([a, c, b])
            F.append([b, c, e])
    last = len(V) - 1
    for j in range(nphi):
        F.append([idx[-1, j], last, idx[-1, (j + 1) % nphi]])
    F = np.asarray(F, np.int64)
    fn = np.cross(V[F[0, 1]] - V[F[0, 0]], V[F[0, 2]] - V[F[0, 0]])
    if fn[2] < 0:
        F = F[:, [0, 2, 1]]
    fnorm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fnorm)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    return dict(V=V, F=F, N=N, UV=to_uv(V[:, :2], side))


# ----------------------------------------------------------------------------------------------------- the paint
@wp.func
def sstep(a: float, b: float, x: float):
    return proc.smoothstep(a, b, x)


@wp.func
def mix3(a: wp.vec3, b: wp.vec3, t: float):
    return a + (b - a) * t


@wp.func
def collarette_t(phi: float, seed: int):
    """the collarette's place (share of the way from the pupil's edge to the root) round the iris: a wandering ring with
    fine scallops (the canid's zigzag collarette)"""
    c = wp.cos(phi)
    s = wp.sin(phi)
    wander = proc.noise3(wp.vec3(c * 2.2, s * 2.2, 1.7), seed + 41)
    scallop = proc.noise3(wp.vec3(c * 9.0, s * 9.0, 4.3), seed + 43)
    # (W2t restart, v4: the wander 0.040 -> 0.075, the scallops 0.018 -> 0.030: in the engine at a 40 mm crop the v3 zone
    # boundary read as a drawn ring, the photos' pupillary cloud is an irregular smudge)
    return 0.34 + 0.075 * wander + 0.030 * scallop


@wp.kernel
def k_eye(size: int, seed: int, half_mm: float, R: float, rl: float, r_iris: float, rp0: float,
          c_cil: wp.vec3, c_olive: wp.vec3, c_amber: wp.vec3, c_fleck: wp.vec3, c_pup: wp.vec3, c_ruff: wp.vec3,
          c_peri: wp.vec3, c_angle: wp.vec3, c_pupil: wp.vec3, c_limbal: wp.vec3, c_conj: wp.vec3,
          r_cornea: float, r_conj: float,
          alb: wp.array(dtype=wp.vec3), rough: wp.array(dtype=wp.float32), msk: wp.array(dtype=wp.vec4)):
    tid = wp.tid()
    px = tid % size
    py = tid // size
    # the texel's local mm (x right, y up; rows bottom-up here, flipped to image order on the host)
    x = ((float(px) + 0.5) / float(size) * 2.0 - 1.0) * half_mm
    y = ((float(py) + 0.5) / float(size) * 2.0 - 1.0) * half_mm
    px_mm = 2.0 * half_mm / float(size)
    r = wp.sqrt(x * x + y * y)
    phi = wp.atan2(y, x)
    cph = wp.cos(phi)
    sph = wp.sin(phi)
    col = c_conj
    rg = r_conj
    m_iris = float(0.0)
    m_limb = float(0.0)
    m_pupil = float(0.0)
    m_conj = float(0.0)
    if r < rl:
        # ---------------------------------------------------------------- inside the limbus: the iris plane
        t = (r - rp0) / (r_iris - rp0)                        # 0 the pupil's edge, 1 the iris's root
        tc = collarette_t(phi, seed)
        # the stroma's ground: the ciliary zone's olive-amber with slow drifts (patches ~1.5 mm, olive vs amber) and broad
        # pigment sectors
        q = wp.vec3(x, y, 0.0)
        drift = proc.fbm3(q * 0.65 + wp.vec3(3.1, 7.7, 0.0), 3, 2.0, 0.5, seed + 3)
        base = mix3(c_cil, c_olive, 0.8 * sstep(0.10, 0.65, drift))
        base = mix3(base, c_amber, sstep(0.05, 0.6, -drift) * 0.85)
        sector = proc.noise3(wp.vec3(cph * 1.6, sph * 1.6, 2.9), seed + 7)
        base = base * (1.0 + 0.10 * sector)
        # (W2t restart) the MOTTLE: darker brown blotches ~0.8 mm and paler gold patches between them, the iris's texture at
        # the distance a game sees it (r01, a gwdc wolf at ~115 px of iris: soft brown blotches over amber; the head
        # shots' irises read granular)
        # (v4: blotches ~1 mm and stronger, 0.30 -> 0.42 / 0.16 -> 0.20: v3's read as a smooth print in the engine)
        mot = proc.fbm3(q * 1.0 + wp.vec3(5.3, 1.9, 0.0), 3, 2.0, 0.5, seed + 5)
        base = mix3(base, c_amber * 0.55, 0.42 * sstep(0.05, 0.60, mot))
        base = mix3(base, c_fleck * 0.80, 0.20 * sstep(0.15, 0.70, -mot))
        # the pupillary zone: darker and browner from the collarette in to the pupil, the photos' soft dark CLOUD round the
        # pupil (w12 R, w11, w12 L at 8-14x, out/refs/: L* ~25-30 against the band's ~45 next to the pupil, gone by ~0.4 r).
        # (W2t restart: v2 lightened it to 0.40 on photo_iris.json's 'pupillary' zone, which starts at that tool's pupil
        # edge, 0.41 r in w12 R: past the cloud. Looked at, the cloud is there)
        # (v4: the cloud's edge wanders with its own noise, so it fades out as a smudge, not along one ring)
        tn = t + 0.07 * proc.noise3(wp.vec3(x, y, 0.0) * 1.6 + wp.vec3(0.0, 0.0, 6.6), seed + 9)
        zp = sstep(tc + 0.10, 0.0, tn)
        # (W2u) THE DARK CENTRE as the photos measure it from the pupil's own centre (eye_mat2/pupil_profile.py: w12 L / R
        # and w11 L reach half the plateau at 0.40-0.47 of the iris's radius on ONE continuous ramp from ~1 to ~4 mm, no
        # step; W2t's paint reached it at 0.22-0.27 behind a crisp disc): the stroma darkens into the deep brown cloud
        # along s^1.25 of a smoothstep from just inside the pupil's edge to 0.45 of the way to the root, scaled with the
        # wandering collarette (tc 0.34 on average), so the median over the azimuth follows the photos' profile
        sc = sstep(-0.02, 0.45 * tc / 0.34, tn)
        col = mix3(c_pup, base, sc * wp.sqrt(wp.sqrt(sc)))
        # the RADIAL FIBRES: angle-stretched noise (about 240 round the mid-iris, long along the radius), wavy, gathered in
        # bundles (~20 round: the stroma's trabeculae), stronger in the pupillary zone and the ciliary zone's inner half
        wav = 0.35 * proc.noise3(wp.vec3(cph * 3.0, sph * 3.0, r * 0.9), seed + 11)
        a1 = phi + wav * 0.12
        f1 = proc.noise3(wp.vec3(wp.cos(a1) * 38.0, wp.sin(a1) * 38.0, r * 0.55), seed + 13)
        f2 = proc.noise3(wp.vec3(wp.cos(a1) * 96.0, wp.sin(a1) * 96.0, r * 1.4), seed + 17)
        bund = proc.noise3(wp.vec3(wp.cos(a1) * 3.4, wp.sin(a1) * 3.4, r * 0.25), seed + 19)
        fib = (f1 + 0.55 * f2) * (0.75 + 0.5 * sstep(-0.3, 0.4, bund)) + 0.35 * bund
        # (v4: the fibres' contrast varies round the iris, bold bundles and quiet sectors (a second, broader bundle
        # noise), and the finest fibres darken more than they lighten: dark radial furrows, as macro irises show)
        bund2 = proc.noise3(wp.vec3(wp.cos(a1) * 6.5, wp.sin(a1) * 6.5, r * 0.35), seed + 21)
        kf = (0.11 + 0.07 * zp) * (0.55 + 0.95 * sstep(-0.25, 0.45, bund2))
        col = col * (1.0 + kf * fib)
        col = col * (1.0 - 0.16 * sstep(0.35, 0.75, f2) * sstep(-0.1, 0.5, bund2))
        # the GRAIN: the stroma's fine granular texture (0.03-0.12 mm), what the photos' irises read as at 30-47 px
        gr = proc.fbm3(wp.vec3(x, y, 0.0) * 14.0 + wp.vec3(0.0, 0.0, 3.7), 3, 2.1, 0.55, seed + 23)
        col = col * (1.0 + 0.16 * gr)
        # the COLLARETTE: a lighter, yellower scalloped ridge between the zones, a fine dark crease on its inner side
        ridge = wp.exp(-((t - tc) / 0.020) * ((t - tc) / 0.020))
        crease = wp.exp(-((t - tc + 0.035) / 0.012) * ((t - tc + 0.035) / 0.012))
        col = mix3(col, c_fleck * 0.85, 0.12 * ridge) * (1.0 - 0.06 * crease)
        # CRYPTS: lens-shaped lacunae, long along the radius, gathered by the collarette (jittered lattice, 0.55 mm)
        cell = 0.55
        gx = x / cell
        gy = y / cell
        i0 = int(wp.floor(gx))
        j0 = int(wp.floor(gy))
        dark = float(0.0)
        fl = float(0.0)
        for k in range(9):
            i = i0 + k % 3 - 1
            j = j0 + k // 3 - 1
            h = proc.hash3i(i, j, 5, seed + 101)
            rr = proc.rnd3(h)
            sx = (float(i) + 0.5 + (rr[0] - 0.5) * 0.85) * cell
            sy = (float(j) + 0.5 + (rr[1] - 0.5) * 0.85) * cell
            sr = wp.sqrt(sx * sx + sy * sy)
            st = (sr - rp0) / (r_iris - rp0)
            stc = collarette_t(wp.atan2(sy, sx), seed)
            near = wp.exp(-((st - stc - 0.08) / 0.14) * ((st - stc - 0.08) / 0.14))
            if rr[2] < 0.38 * near and st > 0.05 and st < 0.75:
                ur = wp.vec2(sx, sy) / wp.max(sr, 1.0e-4)
                dx = x - sx
                dy = y - sy
                dr = dx * ur[0] + dy * ur[1]
                dt = -dx * ur[1] + dy * ur[0]
                ar = 0.10 + 0.12 * proc.u01(proc.lowbias32(h ^ wp.uint32(0x3C6EF372)))
                at = 0.045 + 0.05 * proc.u01(proc.lowbias32(h ^ wp.uint32(0x1F83D9AB)))
                e = (dr / ar) * (dr / ar) + (dt / at) * (dt / at)
                # (an irregular rim: the lacuna's edge wanders by its own noise)
                e = e * (1.0 + 0.45 * proc.noise3(wp.vec3(x, y, float(k)) * 9.0, seed + 31))
                dark = wp.max(dark, sstep(1.2, 0.2, e) * (0.5 + 0.5 * rr[0]))
        col = col * (1.0 - 0.30 * dark)
        # the FLECKS: fine yellow granules (0.035-0.08 mm, up to ~30 / mm2 in the ciliary zone, fewer inward), gathered in
        # patches (a slow noise sets each cell's chance), each its own shade
        fcell = 0.16
        hx = x / fcell
        hy = y / fcell
        k0 = int(wp.floor(hx))
        l0 = int(wp.floor(hy))
        ftint = float(0.0)
        for k in range(9):
            i = k0 + k % 3 - 1
            j = l0 + k // 3 - 1
            h = proc.hash3i(i, j, 9, seed + 211)
            rr = proc.rnd3(h)
            sx = (float(i) + 0.5 + (rr[0] - 0.5) * 0.95) * fcell
            sy = (float(j) + 0.5 + (rr[1] - 0.5) * 0.95) * fcell
            st = (wp.sqrt(sx * sx + sy * sy) - rp0) / (r_iris - rp0)
            patch = sstep(-0.35, 0.45, proc.noise3(wp.vec3(sx, sy, 0.0) * 1.3 + wp.vec3(0.0, 0.0, 8.1), seed + 37))
            pz = 0.80 * patch * sstep(0.10, 0.45, st) * (1.0 - sstep(0.80, 0.97, st))
            if rr[2] < pz:
                rad = 0.018 + 0.022 * proc.u01(proc.lowbias32(h ^ wp.uint32(0x68E31DA4)))
                d = wp.sqrt((x - sx) * (x - sx) + (y - sy) * (y - sy))
                c = wp.clamp((rad - d) / wp.max(1.5 * px_mm, 0.012) + 0.5, 0.0, 1.0)
                if c > fl:
                    fl = c
                    ftint = proc.u01(proc.lowbias32(h ^ wp.uint32(0xB5297A4D)))
        fcol = c_fleck * (0.80 + 0.40 * ftint)
        col = mix3(col, fcol, (0.25 + 0.25 * ftint) * fl * (1.0 - 0.6 * dark))
        # CONTRACTION FURROWS: three faint broken rings in the ciliary zone's outer half
        furrow = float(0.0)
        for k in range(3):
            tk = 0.60 + 0.12 * float(k) + 0.012 * proc.noise3(wp.vec3(cph * 4.0, sph * 4.0, float(k) * 3.3), seed + 51)
            brk = sstep(-0.1, 0.4, proc.noise3(wp.vec3(cph * 7.0, sph * 7.0, float(k) * 5.1 + 2.0), seed + 53))
            furrow = wp.max(furrow, wp.exp(-((t - tk) / 0.010) * ((t - tk) / 0.010)) * brk)
        col = col * (1.0 - 0.14 * furrow)
        # the PERIPHERY darkens into the limbal ring (photos: from ~0.82 of the way out)
        # (W2t restart: the photos' rim, rho 0.85-1.0, is 0.24-0.32 of the plateau (w12 R, w11); the first cut's 0.45; and
        # it is WIDE, a soft band from ~0.75 r (the crops at 8-14x): v2's ramp from t 0.72 read as a thin line in the engine)
        zl = sstep(0.55, 0.95, t)
        col = mix3(col, c_peri, 0.95 * zl)
        # the RUFF at the pupil's edge, and the pupil itself (one texel's antialiasing)
        # (the ruff ~0.12 mm wide, the pigment epithelium's rim: the first cut's was 0.04 mm, under a pixel in a crop)
        ruff = sstep(0.12, 0.0, r - rp0)
        col = mix3(col, c_ruff, 0.85 * ruff)
        # (W2u) a SOFT pupil edge: the photos show no hard disc at 8-14x (refs/w12_irisL / R); 0.3 mm from the pupil into
        # the cloud (W2t: one texel); v6 0.45 mm (with the pupil's warm hue the cloud runs into it without a rim)
        pup = sstep(rp0 + 0.18, rp0 - 0.27, r)
        col = mix3(col, c_pupil, pup)
        # past the iris's root: the dark angle under the cornea's edge
        ang = wp.clamp((r - r_iris) / (2.0 * px_mm) + 0.5, 0.0, 1.0)
        col = mix3(col, c_angle * (1.0 + 0.25 * proc.noise3(q * 4.0, seed + 61)), ang)
        rg = r_cornea
        m_pupil = pup
        m_iris = (1.0 - pup) * (1.0 - ang)
        m_limb = wp.max(zl, ang)
    else:
        # ---------------------------------------------------------------- outside the limbus: the globe's surface
        sr = wp.min(r / R, 0.9999)
        th = wp.asin(sr)
        s = R * (th - wp.asin(wp.min(rl / R, 0.9999)))            # mm along the surface from the limbus
        p3 = wp.vec3(x, y, wp.sqrt(wp.max(R * R - r * r, 0.0)))  # the surface point: the paint's coordinate
        mot = proc.fbm3(p3 * 0.6 + wp.vec3(11.0, 2.0, 5.0), 3, 2.0, 0.5, seed + 71)
        fine = proc.noise3(p3 * 2.2, seed + 73)
        conj = c_conj * (1.0 + 0.30 * mot + 0.10 * fine)
        band = sstep(0.0, 0.9, s)
        col = mix3(c_limbal * (1.0 + 0.15 * fine), conj, band)
        rg = r_cornea + (r_conj - r_cornea) * sstep(0.0, 1.2, s) + 0.012 * fine
        m_limb = 1.0 - band
        m_conj = 1.0
    alb[tid] = col
    rough[tid] = rg
    msk[tid] = wp.vec4(m_iris, m_limb, m_pupil, m_conj)


def paint(size=2048, seed=7, R=12.0, iris_vis=IRIS_VIS, device=None):
    """the maps (module docstring) as uint8 images in image order (row 0 = +y): dict(albedo (sRGB RGB), orm (RGB: 255,
    roughness, 0), masks (RGBA linear)), and the radii they were painted with"""
    from .. import material as M
    ir = iris_radii(R, iris_vis)
    n = size * size
    dev = device or wp.get_preferred_device()
    alb = wp.zeros(n, dtype=wp.vec3, device=dev)
    rgh = wp.zeros(n, dtype=wp.float32, device=dev)
    msk = wp.zeros(n, dtype=wp.vec4, device=dev)
    v3 = lambda c: wp.vec3(*[float(a) for a in c])
    wp.launch(k_eye, dim=n, device=dev,
              inputs=[size, seed, float(UV_HALF), float(R), float(LIMBUS_R), float(ir['r_iris']), float(ir['rp0']),
                      v3(CILIARY), v3(OLIVE), v3(AMBER), v3(FLECK), v3(PUPILLARY), v3(RUFF), v3(PERIPHERY), v3(ANGLE),
                      v3(PUPIL), v3(LIMBAL), v3(CONJ), float(ROUGH_CORNEA), float(ROUGH_CONJ), alb, rgh, msk])
    A = alb.numpy().reshape(size, size, 3)[::-1]
    G = rgh.numpy().reshape(size, size)[::-1]
    Mk = msk.numpy().reshape(size, size, 4)[::-1]
    albedo = (M.srgb_oetf(np.clip(A, 0.0, 1.0)) * 255 + 0.5).astype(np.uint8)
    orm = np.stack([np.full((size, size), 255, np.uint8), (np.clip(G, 0, 1) * 255 + 0.5).astype(np.uint8),
                    np.zeros((size, size), np.uint8)], -1)
    # (the masks OPAQUE, RGB: the kernel's fourth channel, the conjunctiva, is r > LIMBUS_R, which the runtime reads from
    # the position; an alpha channel would be divided into the colour by the engine's image path)
    masks = (np.clip(Mk[..., :3], 0, 1) * 255 + 0.5).astype(np.uint8)
    return dict(albedo=albedo, orm=orm, masks=masks, linear=A, radii=ir, conj=Mk[..., 3])


def constants(R=12.0, iris_vis=IRIS_VIS):
    """what the runtime reads (the glb's node extras / the patch doc): every length in mm"""
    ir = iris_radii(R, iris_vis)
    zc, zl = cornea_centre(R)
    cd, rd, z_mid, z_root = iris_dome(R)
    return dict(globe_r_mm=R, limbus_r_mm=LIMBUS_R, cornea_r_mm=CORNEA_R, cornea_flat0=FLAT0, cornea_zc_mm=zc,
                limbus_z_mm=zl, iris_z_mm=z_mid, iris_root_z_mm=z_root, iris_dome_cz_mm=cd, iris_dome_r_mm=rd,
                iris_r_mm=ir['r_iris'], pupil_r0_mm=ir['rp0'], ior=IOR, uv_half_mm=UV_HALF,
                iris_rot_deg=dict(IRIS_ROT), iris_vis_mm=iris_vis, mode=MODE, rough_cornea=ROUGH_CORNEA,
                rough_conj=ROUGH_CONJ, conj_rgb=list(CONJ))


# ------------------------------------------------------------------------------------- the lookup inside Warp kernels
def warp_params(R, side='L', iris_vis=IRIS_VIS):
    """the constants eye_uv reads, as a float32 array (wp.array(warp_params(...), dtype=float)): R, rl, zc, Rc, flat0,
    1 / ior, the dome's centre z and radius, the root's z, the clamp radius, UV_HALF, cos / sin of the side's turn, the
    mirror (-1 for the right eye)"""
    zc, _ = cornea_centre(R)
    cd, rd, _, z_root = iris_dome(R)
    a = np.radians(IRIS_ROT[side])
    return np.array([R, LIMBUS_R, zc, CORNEA_R, FLAT0, 1.0 / IOR, cd, rd, z_root, LIMBUS_R - 0.05, UV_HALF, np.cos(a),
                     np.sin(a), -1.0 if side == 'R' else 1.0], np.float32)


@wp.func
def eye_uv(p: wp.vec3, d: wp.vec3, k: wp.array(dtype=float)):
    """iris_lookup in a kernel: p the globe's hit (eye-local mm: +Z the gaze, +Y up, X = Y x Z), d the view ray into the
    eye (unit, local), k = warp_params. Returns (u, v, inside): forge uvs (v up) of the maps, inside 1 where the ray read
    the iris through the cornea (the surface point's own uv where 0)"""
    R = k[0]
    rl = k[1]
    zc = k[2]
    rc = k[3]
    x = p[0]
    y = p[1]
    inside = float(0.0)
    if wp.sqrt(p[0] * p[0] + p[1] * p[1]) < rl and p[2] > 0.0:
        # the virtual cap's entry (back along the ray), its flattening normal, the refraction, the dome
        m = p - wp.vec3(0.0, 0.0, zc)
        b = wp.dot(m, d)
        c = wp.dot(m, m) - rc * rc
        s = float(0.0)
        if c < 0.0:
            s = b + wp.sqrt(wp.max(b * b - c, 0.0))
        pe = p - d * s
        nc = wp.normalize(pe - wp.vec3(0.0, 0.0, zc))
        ns = wp.normalize(pe)
        rho = wp.sqrt(pe[0] * pe[0] + pe[1] * pe[1])
        t = wp.clamp((rho - k[4] * rl) / ((1.0 - k[4]) * rl), 0.0, 1.0)
        w = t * t * (3.0 - 2.0 * t)
        n = wp.normalize(nc * (1.0 - w) + ns * w)
        eta = k[5]
        ci = -wp.dot(d, n)
        kk = 1.0 - eta * eta * (1.0 - ci * ci)
        tr = d * eta + n * (eta * ci - wp.sqrt(wp.max(kk, 0.0)))
        m2 = pe - wp.vec3(0.0, 0.0, k[6])
        b2 = wp.dot(m2, tr)
        c2 = wp.dot(m2, m2) - k[7] * k[7]
        disc = b2 * b2 - c2
        th = -b2 - wp.sqrt(wp.max(disc, 0.0))
        if disc < 0.0 or th <= 0.0:
            th = (k[8] - pe[2]) / wp.min(tr[2], -1.0e-3)
        q = pe + tr * th
        rq = wp.sqrt(q[0] * q[0] + q[1] * q[1])
        sc = float(1.0)
        if rq > k[9]:
            sc = k[9] / rq
        x = q[0] * sc
        y = q[1] * sc
        inside = 1.0
    x = x * k[13]
    xr = k[11] * x - k[12] * y
    yr = k[12] * x + k[11] * y
    return wp.vec3(0.5 + xr / (2.0 * k[10]), 0.5 + yr / (2.0 * k[10]), inside)


@wp.func
def eye_normal(p: wp.vec3, d: wp.vec3, k: wp.array(dtype=float)):
    """the shading normal at the globe's hit p (eye-local mm) seen along d (unit, into the eye), k = warp_params: inside
    the limbus the virtual cap's at the ray's entry, flattening onto the sphere's toward the limbus (the catchlight's);
    outside it the sphere's (eye_shade's n)"""
    rl = k[1]
    zc = k[2]
    rc = k[3]
    n = wp.normalize(p)
    if wp.sqrt(p[0] * p[0] + p[1] * p[1]) < rl and p[2] > 0.0:
        m = p - wp.vec3(0.0, 0.0, zc)
        b = wp.dot(m, d)
        c = wp.dot(m, m) - rc * rc
        s = float(0.0)
        if c < 0.0:
            s = b + wp.sqrt(wp.max(b * b - c, 0.0))
        pe = p - d * s
        rho = wp.sqrt(pe[0] * pe[0] + pe[1] * pe[1])
        t = wp.clamp((rho - k[4] * rl) / ((1.0 - k[4]) * rl), 0.0, 1.0)
        w = t * t * (3.0 - 2.0 * t)
        n = wp.normalize(wp.normalize(pe - wp.vec3(0.0, 0.0, zc)) * (1.0 - w) + wp.normalize(pe) * w)
    return n


@wp.func
def sample_rgb(img: wp.array2d(dtype=wp.vec3), u: float, v: float):
    """bilinear read of a (h, w) vec3 map in image order (row 0 = v 1; e.g. load_maps' linear albedo) at a forge uv"""
    h = img.shape[0]
    w_ = img.shape[1]
    x = wp.clamp(u * float(w_) - 0.5, 0.0, float(w_) - 1.0001)
    y = wp.clamp((1.0 - v) * float(h) - 0.5, 0.0, float(h) - 1.0001)
    x0 = int(wp.floor(x))
    y0 = int(wp.floor(y))
    fx = x - float(x0)
    fy = y - float(y0)
    return (img[y0, x0] * (1.0 - fx) + img[y0, x0 + 1] * fx) * (1.0 - fy) + \
        (img[y0 + 1, x0] * (1.0 - fx) + img[y0 + 1, x0 + 1] * fx) * fy


# ----------------------------------------------------------------------------------------------- the occlusion shell
# W2u (the eye builder; the lead's call: "a lid-occlusion shell: the environment light reaches the globe unshadowed by
# the lids, so the flat facets of the inner-corner pocket catch light; build a head-attached occlusion shell as the
# human's H3b eye parts did (the eye-space band the human tried first drifted with the gaze)"). THE SHELL is a
# transparent mesh the runtime draws as a true MULTIPLY over whatever lies behind it (canid_eye.js
# canidEyeShellMaterial), its value per vertex a MEASURED occlusion. The human's (work/bestiary/human/h3b/material/
# e01_eyeparts.py) is a dome about the ball's centre. On this head the margin loop climbs to R + 7.3 mm at the medial
# notch and the lit facets the cameras see in the opening stand in front of the ball (R + 0.05 .. 4.2 mm, up to 6.6:
# work/bestiary/wolf/eye_mat2/scratch/pocket_geo.py), so a dome would pass behind them; and one membrane spanning the
# loop as a height field along the opening's axis (tried first) covered 97-99 % of the globe the photos' cameras see
# but only 32-47 % of the pocket's seen faces: the front cameras look into the medial pocket 25-40 deg off that axis.
# So the shell is TWO PARTS, both head-attached, both the same multiply:
#   THE GLOBE CAP (globe_cap): a cap at SHELL_LIFT over the ball, on meridians from the opening's axis (shell_frame: the
#     margin's mean direction from the globe's centre) through each margin station, its rim SHELL_TUCK beyond the
#     margin under the lids; where a pocket face stands in front of it, the depth test hides it (no double darkening).
#     Its value: the cosine-weighted ambient occlusion of the ball's point under each vertex against the head, relative
#     to the opening's centre (the apex), so the centre multiplies by 1; the eye's own aoNode may take the centre's
#     (ao_ref). The stations ride the margin chain, so a lid pose moves the cap with the lids (the probe's morph targets;
#     a rig's lid weights), while the globe turns under it: a sphere, so its points' occlusion does not depend on gaze.
#     (W2u v5) Each cap vertex also carries ITS DEPTH BELOW THE UPPER LID'S MARGIN (lid_depth, mm: straight down
#     across the opening's axis, along its up direction e2, from the upper lid's margin at the vertex's own place across
#     the opening; 0 under the lid, 99 beyond the canthi), so the runtime can lay THE UPPER LID'S SHADE on the ball
#     (canid_eye.js SHELL.LASH): every w12 crop shades the iris's top under the upper lid (about half its mirror's
#     brightness from the margin down ~2.5 mm, even by ~4.5 mm: eye_mat2/lidshade.py, which reads the same straight-down
#     depth), the lid's shadow cast into the eye through the 4 mm deep anterior chamber plus its lashes and the dark rim's
#     fringe, none of which the bare clay's measured occlusion holds (it darkens ~1 mm at the margin). (A first cut
#     measured the depth along the cap's meridians: at w12's up-gaze the iris rides high in the opening and its sides
#     sat on tilted upper meridians a few mm from the margin, so the band darkened them a quarter; straight down is the
#     shadow's own direction under a sky.) The games' eye-occlusion mesh does the same with a top gradient; [E] until the
#     head's lashes / fringe and an iris lit through the cornea exist.
#   THE POCKET PART (pocket_part): the conjunctival faces standing POCKET_MIN .. POCKET_REACH off the ball (the medial
#     pocket's floor, the roll under the lids, the lateral corner), copied POCKET_LIFT off the skin along its normals,
#     each vertex's value the ambient occlusion of its own skin point (the head and the globe as occluders) relative
#     to the same centre, and its height off the ball (the runtime's pocket floor reads it: canid_eye.js SHELL). It
#     rides the head's own vertices, so it follows every lid pose exactly. A stand-in for the head's baked occlusion
#     over the pocket: once the head's AO bake (W2v) darkens those faces, its gain goes to 0. (Measured on W2t's head,
#     eye_mat2/NOTES.md: the medial pocket's floor is a broad shelf open to the sky, AO-occ ~0.1-0.3, where the photos
#     show a narrow black crease shaded by lashes, the fur fringe and the third eyelid's fold: the head's construction
#     item; the runtime's floor term stands in, marked [E].)
SHELL_STATIONS = 96
SHELL_ROWS = (0.0, 0.035, 0.08, 0.14, 0.22, 0.32, 0.44, 0.58, 0.74, 0.88)   # the share of the way to the axis
SHELL_TUCK = 1.0         # mm along the ball: the cap's rim beyond each margin station's direction, under the lids
SHELL_LIFT = 0.25        # mm: the cap's radius over the ball's
POCKET_MIN = 0.2         # mm: the pocket part takes the conjunctival faces whose centres stand more than this off the
POCKET_REACH = 10.0      #     ball and less than this (nearer the ball the cap covers them; 0.3 left the faces at
#                          R + 0.25-0.3, in front of the cap, uncovered)
POCKET_LIFT = 0.12       # mm: the pocket part off the skin along its normals
SHELL_RAYS = 768         # ambient-occlusion rays per vertex
SHELL_RAY_MM = 45.0      # their reach (mm): the brow, the muzzle and the cheek round the eye
SHELL_GROUND = 0.4      # [E] SKY-WEIGHTED occlusion: a ray below the head's horizon counts this much of one above it
#                          (the ground's light against the sky's; plain cosine AO = 1). With 1 the cap was darkest by
#                          the LOWER lid (down-facing ball points see the lid and the cheek) and darkened the lower iris
#                          in w08's and r03's poses, where the photos shade the iris's TOP under the upper lid, lashes
#                          and brow (eye_mat2/NOTES.md, out/ab_shell_beach.png)
SHELL_RIDE = (0.58, 1.0)  # (W2w v5d) THE CAP RIDES ITS LIDS: on a lid pose each meridian turns about the globe's centre
#                          with its own margin station (the rotation taking the station's rest direction to its posed
#                          one), whole, from the rim in to this share of the way to the axis, eased from there to the
#                          stations' mean turn at the apex (cap_ride). W2u re-spread every row between the posed rim and
#                          the REST axis, so a wide-open lid STRETCHED the cap and carried the rest-measured attribute
#                          (the occlusion, the depth below the upper margin) over the ball: at w12's pose the iris's lower
#                          sector lost 15 % where it loses 4 % at rest (eye_mat3/NOTES.md). Riding whole, a vertex keeps
#                          its place against the lid that shades it, so the rest attribute holds on the pose. A rig does
#                          the same with each cap vertex on its station's lid weights (patches/wolf_eye_w2w.md). None =
#                          W2u's re-spread


def margin_chain(V, loop, step=0.1, snap=3.0):
    """the lid margin loop (k, 3) snapped in order onto a mesh's vertices V: their indices round the loop, consecutive
    repeats dropped (the chain a lid pose carries: V_posed[chain])"""
    from scipy.spatial import cKDTree
    L = np.asarray(loop, np.float64)
    dense = []
    for k in range(len(L)):
        a, b = L[k], L[(k + 1) % len(L)]
        m = max(1, int(np.ceil(np.linalg.norm(b - a) / step)))
        dense.append(a[None] + (b - a)[None] * (np.arange(m) / m)[:, None])
    dd, ii = cKDTree(V).query(np.vstack(dense))
    ii = ii[dd < snap]
    ch = [int(ii[0])] + [int(x) for k, x in enumerate(ii[1:]) if x != ii[k]]
    if ch[-1] == ch[0]:
        ch = ch[:-1]
    return np.asarray(ch, np.int64)


def chain_stations(Vr, chain, n=SHELL_STATIONS, Vp=None, smooth=1.0):
    """n stations evenly spaced by the REST chain's arc length (Vr[chain]), and the same material points on a posed copy
    Vp (each station's chain segment and fraction kept), circularly smoothed over `smooth` stations"""
    P = Vr[chain]
    Q = np.vstack([P, P[:1]])
    s = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))]
    t = np.linspace(0.0, s[-1], n, endpoint=False)
    j = np.clip(np.searchsorted(s, t, side='right') - 1, 0, len(P) - 1)
    f = (t - s[j]) / np.maximum(s[j + 1] - s[j], 1e-12)

    def at(W):
        A, B = W[chain][j], W[chain][(j + 1) % len(chain)]
        X = A * (1 - f[:, None]) + B * f[:, None]
        if smooth > 0:
            k = np.minimum(np.arange(n), n - np.arange(n)).astype(np.float64)
            g = np.exp(-0.5 * (k / smooth) ** 2)
            g /= g.sum()
            X = np.real(np.fft.ifft(np.fft.fft(X, axis=0) * np.fft.fft(g)[:, None], axis=0))
        return X
    return at(Vr), (at(Vp) if Vp is not None else None)


def shell_frame(stations, centre):
    """the opening's axis a (the stations' mean direction from the globe's centre) and e1, e2 across it (palate mm:
    d, q, x; e1 = q x a)"""
    D = np.asarray(stations, np.float64) - np.asarray(centre, np.float64)
    a = (D / np.linalg.norm(D, axis=1, keepdims=True)).mean(0)
    a /= np.linalg.norm(a)
    e1 = np.cross(np.array([0.0, 1.0, 0.0]), a)
    e1 /= np.linalg.norm(e1)
    return a, e1, np.cross(a, e1)


def cap_dirs(stations, centre, axis, R, rows=SHELL_ROWS, tuck=SHELL_TUCK):
    """THE GLOBE CAP's directions from the globe's centre: per station a meridian from the axis through the station's
    own direction, its rim `tuck` mm (along the ball) beyond it, rows in toward the axis; returns (stations, rows, 3)
    unit directions and the apex (the axis)"""
    U = np.asarray(stations, np.float64) - np.asarray(centre, np.float64)
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    a = np.asarray(axis, np.float64)
    th = np.arccos(np.clip(U @ a, -1.0, 1.0))
    Wt = U - (U @ a)[:, None] * a[None]
    Wt /= np.maximum(np.linalg.norm(Wt, axis=1, keepdims=True), 1e-12)
    ang = (th + tuck / R)[:, None] * (1.0 - np.asarray(rows, np.float64))[None, :]
    D = np.cos(ang)[..., None] * a[None, None] + np.sin(ang)[..., None] * Wt[:, None, :]
    return D, a.copy()


def rot_between(U, V):
    """the minimal rotations (n, 3, 3) taking unit directions U (n, 3) to V (n, 3) (Rodrigues; the identity where they
    agree)"""
    U = np.atleast_2d(U)
    V = np.atleast_2d(V)
    k = np.cross(U, V)
    s = np.linalg.norm(k, axis=1)
    c = np.clip(np.sum(U * V, axis=1), -1.0, 1.0)
    k = k / np.maximum(s, 1e-12)[:, None]
    K = np.zeros((len(U), 3, 3))
    K[:, 0, 1], K[:, 0, 2], K[:, 1, 2] = -k[:, 2], k[:, 1], -k[:, 0]
    K[:, 1, 0], K[:, 2, 0], K[:, 2, 1] = k[:, 2], -k[:, 1], k[:, 0]
    Rm = np.eye(3)[None] + s[:, None, None] * K + (1.0 - c)[:, None, None] * (K @ K)
    return np.where((s < 1e-12)[:, None, None], np.eye(3)[None], Rm)


def cap_ride(D0, apex0, stations_rest, stations_posed, centre, rows=SHELL_ROWS, ride=SHELL_RIDE):
    """(W2w v5d) THE CAP ON A LID POSE, riding its lids (SHELL_RIDE): the rest cap's directions D0 (stations, rows, 3) and
    apex, each meridian turned about the globe's centre with its own station (rest -> posed direction), whole from the
    rim to ride[0] of the way to the axis, eased by ride[0] -> ride[1] to the stations' mean turn (the posed stations'
    mean direction against the rest's), which the apex takes. Returns (D (stations, rows, 3), apex) unit directions"""
    c = np.asarray(centre, np.float64)
    U = np.asarray(stations_rest, np.float64) - c
    Up = np.asarray(stations_posed, np.float64) - c
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    Up /= np.linalg.norm(Up, axis=1, keepdims=True)
    a, ap = U.mean(0), Up.mean(0)
    a /= np.linalg.norm(a)
    ap /= np.linalg.norm(ap)
    Ri = rot_between(U, Up)                                          # (ns, 3, 3) each station's turn
    Rm = rot_between(a[None], ap[None])[0]                           # the mean turn
    D_ride = np.einsum('sij,srj->sri', Ri, D0)
    D_mean = np.einsum('ij,srj->sri', Rm, D0)
    t = np.clip((np.asarray(rows, np.float64) - ride[0]) / max(ride[1] - ride[0], 1e-9), 0.0, 1.0)
    w = (t * t * (3.0 - 2.0 * t))[None, :, None]
    D = D_ride * (1.0 - w) + D_mean * w
    return D / np.linalg.norm(D, axis=2, keepdims=True), Rm @ np.asarray(apex0, np.float64)


def lid_depth(P, stations, centre, frame, beyond=99.0):
    """(v5) the depth (mm) of points P below the UPPER lid's margin, straight down across the opening's axis: in the
    plane across the axis (frame = (a, e1, e2), e2 up) each point's e2 height against the upper margin's at the point's
    own e1 place (the stations' arc between the canthi, the extremes along e1, that stands higher), clipped at 0 (under
    the lid); `beyond` past the canthi"""
    a, e1, e2 = (np.asarray(v, np.float64) for v in frame)
    S = np.asarray(stations, np.float64) - np.asarray(centre, np.float64)
    su, sv = S @ e1, S @ e2
    i0, i1 = int(np.argmin(su)), int(np.argmax(su))
    n = len(S)
    arc1 = [(i0 + k) % n for k in range((i1 - i0) % n + 1)]
    arc2 = [(i1 + k) % n for k in range((i0 - i1) % n + 1)]
    up = arc1 if sv[arc1].mean() > sv[arc2].mean() else arc2
    o = np.argsort(su[up])
    uu, vv = su[up][o], sv[up][o]
    D = np.asarray(P, np.float64) - np.asarray(centre, np.float64)
    pu, pv = D @ e1, D @ e2
    d = np.maximum(np.interp(pu, uu, vv) - pv, 0.0)
    return np.where((pu < uu[0]) | (pu > uu[-1]), beyond, d)


def vertex_normals(V, F):
    """area-weighted vertex normals of a mesh"""
    N = np.zeros_like(V)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    for k in range(3):
        np.add.at(N, F[:, k], fn)
    return N / np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-30)


@wp.kernel
def k_shell_ao(mesh: wp.uint64, P: wp.array(dtype=wp.vec3), Nn: wp.array(dtype=wp.vec3), S: wp.array(dtype=int),
               c: wp.vec3, R: float, nrays: int, dist: float, seed: int, up: wp.vec3, ground: float,
               ao: wp.array(dtype=float)):
    """per point the cosine-weighted share of the hemisphere round its normal reaching `dist` unoccluded by the head's
    mesh or (for a point off the globe) the globe's sphere, each ray weighted by the sky (SHELL_GROUND below the
    head's horizon, eased over +-0.25 of the up axis)"""
    i = wp.tid()
    p = P[i]
    n = Nn[i]
    a = wp.vec3(1.0, 0.0, 0.0)
    if wp.abs(n[0]) > 0.9:
        a = wp.vec3(0.0, 1.0, 0.0)
    t = wp.normalize(wp.cross(n, a))
    b = wp.cross(n, t)
    st = wp.rand_init(seed, i)
    free = float(0.0)
    tot = float(0.0)
    for k in range(nrays):
        u1 = wp.randf(st)
        u2 = wp.randf(st)
        r = wp.sqrt(u1)
        ph = 6.2831853 * u2
        d = t * (r * wp.cos(ph)) + b * (r * wp.sin(ph)) + n * wp.sqrt(wp.max(1.0 - u1, 0.0))
        o = p + n * 0.03
        blocked = int(0)
        h = wp.mesh_query_ray(mesh, o, d, dist)
        if h.result:
            blocked = 1
        if blocked == 0 and S[i] != 0:
            m = o - c
            bb = wp.dot(m, d)
            cc = wp.dot(m, m) - R * R
            disc = bb * bb - cc
            if disc > 0.0:
                if -bb - wp.sqrt(disc) > 0.0:
                    blocked = 1
        sw = ground + (1.0 - ground) * proc.smoothstep(-0.25, 0.25, wp.dot(d, up))
        tot = tot + sw
        if blocked == 0:
            free = free + sw
    ao[i] = free / wp.max(tot, 1.0e-6)


def _wp_mesh(V, F):
    return wp.Mesh(points=wp.array(np.asarray(V, np.float32), dtype=wp.vec3, device='cpu'),
                   indices=wp.array(np.asarray(F, np.int32).ravel(), dtype=wp.int32, device='cpu'))


def shell_faces(ns, nr):
    """the shell's triangles: the closed station ring x open rows, then a fan to the apex (index ns * nr)"""
    F = []
    for i in range(ns):
        i1 = (i + 1) % ns
        for j in range(nr - 1):
            a_, b_, c_, d_ = i * nr + j, i1 * nr + j, i1 * nr + j + 1, i * nr + j + 1
            F += [(a_, b_, c_), (a_, c_, d_)]
    ap = ns * nr
    for i in range(ns):
        F.append((i * nr + nr - 1, ((i + 1) % ns) * nr + nr - 1, ap))
    return np.asarray(F, np.int64)


def surface_ao(mesh, P, N, on_globe, centre, R, rays=SHELL_RAYS, dist=SHELL_RAY_MM, seed=11, up=(0.0, 1.0, 0.0),
               ground=SHELL_GROUND):
    """THE SHELL'S MEASURE (the section's header): the sky-weighted, cosine-weighted ambient occlusion at surface points
    P (n, 3) with normals N against a head mesh (a wp.Mesh) and, for the points off the globe (on_globe False), the
    globe's sphere (k_shell_ao, Warp's CPU device); up the head's up (palate q), ground SHELL_GROUND"""
    n = len(P)
    ao = wp.zeros(n, dtype=float, device='cpu')
    S = np.where(np.broadcast_to(np.asarray(on_globe, bool), (n,)), 0, 1).astype(np.int32)
    wp.launch(k_shell_ao, dim=n, device='cpu',
              inputs=[mesh.id, wp.array(np.asarray(P, np.float32), dtype=wp.vec3, device='cpu'),
                      wp.array(np.asarray(N, np.float32), dtype=wp.vec3, device='cpu'),
                      wp.array(S, dtype=int, device='cpu'),
                      wp.vec3(*np.asarray(centre, np.float32)), float(R), int(rays), float(dist), int(seed),
                      wp.vec3(*np.asarray(up, np.float32)), float(ground), ao])
    return ao.numpy().astype(np.float64)


def occlusion_shell(V, F, loop, centre, R, conj_ids, posed=None, stations=SHELL_STATIONS, rows=SHELL_ROWS,
                    tuck=SHELL_TUCK, lift=SHELL_LIFT, pocket=(POCKET_MIN, POCKET_REACH), pocket_lift=POCKET_LIFT,
                    rays=SHELL_RAYS, dist=SHELL_RAY_MM, ride=SHELL_RIDE):
    """THE OCCLUSION SHELL of one eye (the section's header) over a head mesh (V, F; palate mm), round its lid margin
    loop (k, 3; on the mesh at rest), the globe's centre and radius; conj_ids the head's vertices on the globe's side of
    the margin (the conjunctival skin: the probe's inner_of_margin). posed: {name: V_posed (the same vertex set)}, the
    lid poses (morph targets): the cap on the posed margin chain's stations (v5d: the rest cap riding them, cap_ride;
    ride None = W2u's rows re-spread to the rest axis), the pocket part on the posed vertices, each measured against the
    posed head (the posed occlusion is a check: the attribute stays the rest's). Returns dict(cap=dict(V (n, 3), F, N, occ,
    ao, rim_mm, lid_depth (v5: mm below the upper lid's margin, straight down; 99 beyond the canthi)),
    pocket=dict(V, F, N, occ, ao, src (the head vertices it copies), height (mm off the ball, rest)),
    ao_ref (the opening's centre), frame (axis, e1, e2), chain, stations, rows, posed={name: dict(cap_V, cap_occ,
    pocket_V, pocket_occ, ao_ref, stations (posed), cap_lid_depth (v5d: the posed cap's own depth below the posed upper
    margin)))"""
    wp.init()
    V = np.asarray(V, np.float64)
    F = np.asarray(F, np.int64)
    c = np.asarray(centre, np.float64)
    ch = margin_chain(V, loop)
    st, _ = chain_stations(V, ch, stations)
    fr = shell_frame(st, c)
    ns, nr = int(stations), len(rows)
    Fc = shell_faces(ns, nr)
    inner = np.zeros(len(V), bool)
    inner[np.asarray(conj_ids, np.int64)] = True
    rr = np.linalg.norm(V[F].mean(1) - c, axis=1) - R
    pf = np.nonzero(inner[F].all(1) & (rr > pocket[0]) & (rr < pocket[1]))[0]
    src, inv = np.unique(F[pf].ravel(), return_inverse=True)
    Fp = inv.reshape(-1, 3)

    D_rest, ap_rest = cap_dirs(st, c, fr[0], R, rows, tuck)

    def build(W, rest):
        mesh = _wp_mesh(W, F)
        Nv = vertex_normals(W, F)
        stn = st if rest else chain_stations(V, ch, stations, Vp=W)[1]
        if rest or ride is None:
            D, ap = cap_dirs(stn, c, fr[0], R, rows, tuck)
        else:
            D, ap = cap_ride(D_rest, ap_rest, st, stn, c, rows, ride)     # (v5d) the rest cap riding its lids
        dirs = np.vstack([D.reshape(-1, 3), ap[None]])
        cap_ao = surface_ao(mesh, c[None] + dirs * R, dirs, True, c, R, rays, dist)
        pk_ao = surface_ao(mesh, W[src], Nv[src], False, c, R, rays, dist, seed=13)
        ref = float(cap_ao[-1])
        occ = lambda x: np.clip(1.0 - x / max(ref, 1e-6), 0.0, 1.0)
        return dict(cap_V=c[None] + dirs * (R + lift), dirs=dirs, cap_ao=cap_ao, cap_occ=occ(cap_ao),
                    pocket_V=W[src] + Nv[src] * pocket_lift, pocket_N=Nv[src], pocket_ao=pk_ao, pocket_occ=occ(pk_ao),
                    ao_ref=ref, stations=stn)
    b0 = build(V, True)
    Vc = b0['cap_V']
    fn = np.cross(Vc[Fc[:, 1]] - Vc[Fc[:, 0]], Vc[Fc[:, 2]] - Vc[Fc[:, 0]])
    if (fn * (Vc[Fc].mean(1) - c)).sum(1).mean() < 0:
        Fc = Fc[:, [0, 2, 1]]
    th = np.arccos(np.clip(b0['dirs'] @ fr[0], -1.0, 1.0))
    U = st - c
    U /= np.linalg.norm(U, axis=1, keepdims=True)
    th_rim = np.r_[np.repeat(np.arccos(np.clip(U @ fr[0], -1.0, 1.0)) + tuck / R, nr), 0.0]
    rim_mm = np.maximum(th_rim - th, 0.0) * (R + lift)
    rim_mm[-1] = float(np.mean(th_rim[:-1])) * (R + lift)
    # (v5) each cap vertex's depth below the upper lid's margin (the section's header), at rest
    out = dict(cap=dict(V=Vc, F=Fc, N=b0['dirs'], occ=b0['cap_occ'], ao=b0['cap_ao'], rim_mm=rim_mm,
                        lid_depth=lid_depth(Vc, st, c, fr)),
               pocket=dict(V=b0['pocket_V'], F=Fp, N=b0['pocket_N'], occ=b0['pocket_occ'], ao=b0['pocket_ao'], src=src,
                           height=np.linalg.norm(V[src] - c, axis=1) - R),
               ao_ref=b0['ao_ref'], frame=fr, chain=ch, stations=st, rows=tuple(rows), posed={})
    for name, Vp in (posed or {}).items():
        b = build(np.asarray(Vp, np.float64), False)
        # (v5d) the posed cap's own depth below the posed upper margin, a check against the rest attribute it carries
        out['posed'][name] = dict(cap_V=b['cap_V'], cap_occ=b['cap_occ'], pocket_V=b['pocket_V'],
                                  pocket_occ=b['pocket_occ'], ao_ref=b['ao_ref'], stations=b['stations'],
                                  cap_lid_depth=lid_depth(b['cap_V'], b['stations'], c, shell_frame(b['stations'], c)))
    return out
