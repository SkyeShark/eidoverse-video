"""The human's EYE (HUMAN_PLAN §5.2, H3): its own part, seated where the clay's lids expect it.

THE GLOBE (local frame: the centre at the origin, +Z the optical axis, +Y up, millimetres; the export scales to metres):
  * the sclera: a sphere of GLOBE_D = 24.156 mm (Bekerman et al. 2014: the transverse diameter's mean; H2b's lid rule
    puts the lid margins on a sphere of GLOBE_D / 2 + 1 mm about this centre, so a lid rests 1 mm off the globe);
  * the CORNEA: a spherical cap of radius CORNEA_R = 7.8 mm (LIFE-Adult's anterior radii 7.81 / 7.66 flat / steep)
    over the limbus of LIMBUS_D = 11.71 mm (Rufer et al. 2005: white-to-white 11.71 +- 0.42), blended into the sphere
    by a soft maximum over ~0.25 mm: its apex stands 1.13 mm proud of the sphere, 0.13 mm past the lid sphere (only at
    the opening's middle, where no lid lies);
  * the IRIS lies on the plane z = IRIS_Z = 10.2 mm, about 3.0 mm behind the corneal apex (LIFE-Adult: central
    corneal thickness 0.558 mm + aqueous depth 2.61 mm at 50 to the lens, on which the pupil margin rests), 0.35 mm
    behind the limbus's own plane: the runtime reads it through the cornea by a refracted view ray (ior 1.376, the
    technician's CFEye: HUMAN_SYSTEMS §1.6), a real-time stand-in for the refracting chamber;
  * UVs: the orthographic projection onto the iris plane (u, v = 0.5 + x / 25 mm, 0.5 + y / 25 mm), so an EYES-set
    paint lands in eye space (octopus_eye.py's convention); the hidden back half repeats it.

    eye_globe() -> dict(V (mm), F, N, UV);  axis_frame(axis) -> 3x3 rotation whose +Z column is the gaze axis

(H3c, the H4 round's close-up builder, 11-01; landed by the H4 integrator from its copy, sha1 543ade02) THE GLOBE AT BUDGET
(HUMAN_PLAN §8: the eyes 2.6 k triangles, both, parts included; H3's globe was 8,496 a side): eye_globe_budget() lays its
rings where the shape and the views need them, not evenly: five over the cornea, two hugging the limbus's soft maximum, the
visible sclera to ~60 deg, then sparse to an OPEN edge at 122 deg (the back half is never seen, even at the controller's
gaze extremes, ~35 deg); every vertex ON the analytic surface (radius(): the sphere and the cornea's soft maximum, the same
function eye_globe() samples), every normal the analytic surface's own (not averaged from the facets), the UVs
eye_globe()'s orthographic projection. 28 segments x 12 bands + the front fan = 700 triangles (the facets' sag off the
surface: under 0.04 mm where the opening shows the ball). The shape's detail lives in the analytic normals and the EYES set
(h4/close/c09_eyetex.py: the iris from a photo, the sclera), not in the facets. radial_table() gives the parts' builder the
same surface.
"""
import numpy as np

GLOBE_D = 24.156
CORNEA_R = 7.8
LIMBUS_D = 11.71
IRIS_Z = 10.2
UV_HALF = 12.5                   # mm: the UV square's half width
BLEND = 0.25                     # mm: the cornea's soft maximum into the sphere


def cornea_geom():
    """(the cornea sphere's centre z, the limbus's polar angle, the apex z)"""
    R = GLOBE_D / 2.0
    rl = LIMBUS_D / 2.0
    zl = np.sqrt(R * R - rl * rl)
    zc = zl - np.sqrt(CORNEA_R ** 2 - rl * rl)
    return zc, float(np.arcsin(rl / R)), zc + CORNEA_R


def eye_globe(n_front=26, n_back=34, n_phi=72):
    """the globe's mesh: rings in polar angle from the front pole (dense over the cornea), a vertex at each pole"""
    R = GLOBE_D / 2.0
    zc, th_l, _ = cornea_geom()
    th = np.concatenate([np.linspace(0.0, th_l * 1.15, n_front + 1)[1:],
                         np.linspace(th_l * 1.15, np.pi, n_back + 1)[1:-1]])
    ph = np.linspace(0.0, 2 * np.pi, n_phi, endpoint=False)
    T, Pp = np.meshgrid(th, ph, indexing='ij')
    d = np.stack([np.sin(T) * np.cos(Pp), np.sin(T) * np.sin(Pp), np.cos(T)], -1)

    def radius(t):
        s = np.sin(t)
        disc = CORNEA_R ** 2 - (zc * s) ** 2
        rc = np.where(disc > 0, zc * np.cos(t) + np.sqrt(np.maximum(disc, 0.0)), 0.0)
        rc = np.where(np.cos(t) > 0, rc, 0.0)
        # soft maximum of the sphere and the cornea
        return 0.5 * (R + rc + np.sqrt((R - rc) ** 2 + BLEND ** 2)) - 0.5 * BLEND
    r = radius(T)
    P = d * r[..., None]
    V = np.concatenate([[[0.0, 0.0, radius(np.array(0.0))]], P.reshape(-1, 3), [[0.0, 0.0, -R]]])
    nr, nphi = T.shape
    idx = (np.arange(nr * nphi) + 1).reshape(nr, nphi)
    F = []
    for j in range(nphi):                                 # the front cap's fan
        F.append([0, idx[0, j], idx[0, (j + 1) % nphi]])
    for i in range(nr - 1):
        for j in range(nphi):
            a, b = idx[i, j], idx[i, (j + 1) % nphi]
            c, e = idx[i + 1, j], idx[i + 1, (j + 1) % nphi]
            F.append([a, c, b])
            F.append([b, c, e])
    last = len(V) - 1
    for j in range(nphi):                                 # the back cap's fan
        F.append([idx[-1, j], last, idx[-1, (j + 1) % nphi]])
    F = np.asarray(F, np.int64)
    # outward winding check: the first fan's normal must point +Z
    fn = np.cross(V[F[0, 1]] - V[F[0, 0]], V[F[0, 2]] - V[F[0, 0]])
    if fn[2] < 0:
        F = F[:, [0, 2, 1]]
    fnorm = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    N = np.zeros_like(V)
    for k in range(3):
        np.add.at(N, F[:, k], fnorm)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    UV = np.column_stack([0.5 + V[:, 0] / (2 * UV_HALF), 0.5 + V[:, 1] / (2 * UV_HALF)])
    return dict(V=V, F=F, N=N, UV=UV)


def axis_frame(axis, up=(0.0, 1.0, 0.0)):
    z = np.asarray(axis, np.float64)
    z /= np.linalg.norm(z)
    x = np.cross(np.asarray(up, np.float64), z)
    x /= np.linalg.norm(x)
    y = np.cross(z, x)
    return np.stack([x, y, z], 1)


# ------------------------------------------------------------------------------------------- (H3c) the globe at budget
BUDGET_RINGS_DEG = (8.0, 16.0, 23.0, 27.5, 30.0, 33.0, 38.0, 46.0, 57.0, 70.0, 86.0, 104.0, 122.0)
BUDGET_SEGMENTS = 28           # 28 x 12 bands + the fan = 700; with the parts' 572 a side 1,272 (both 2,544 of the 2.6 k)


def radius(t):
    """(H3c) the globe's radius at polar angle t (radians, from the front pole): the sphere and the cornea's cap joined by
    eye_globe()'s soft maximum (its own expression, lifted out so the budget globe and the parts read one surface)"""
    R = GLOBE_D / 2.0
    zc, _, _ = cornea_geom()
    t = np.asarray(t, np.float64)
    s = np.sin(t)
    disc = CORNEA_R ** 2 - (zc * s) ** 2
    rc = np.where(disc > 0, zc * np.cos(t) + np.sqrt(np.maximum(disc, 0.0)), 0.0)
    rc = np.where(np.cos(t) > 0, rc, 0.0)
    return 0.5 * (R + rc + np.sqrt((R - rc) ** 2 + BLEND ** 2)) - 0.5 * BLEND


def radial_table(n=1441):
    """(H3c) (angles, radii) over 0..pi: the analytic surface for the parts' builder (p12's eye_radial read it off H3's
    dense mesh; the budget globe's 13 rings would make that a polygon)"""
    g = np.linspace(0.0, np.pi, n)
    return g, radius(g)


def eye_globe_budget(rings_deg=BUDGET_RINGS_DEG, n_phi=BUDGET_SEGMENTS):
    """(H3c) the globe at budget (the module docstring's note): a front fan, then bands between the rings, open after the
    last; positions on radius(), normals the analytic surface's (r e_r - r' e_t, normalised), eye_globe()'s UVs"""
    th = np.radians(np.asarray(rings_deg, np.float64))
    ph = np.linspace(0.0, 2 * np.pi, n_phi, endpoint=False)
    T, Pp = np.meshgrid(th, ph, indexing='ij')
    d = np.stack([np.sin(T) * np.cos(Pp), np.sin(T) * np.sin(Pp), np.cos(T)], -1)
    et = np.stack([np.cos(T) * np.cos(Pp), np.cos(T) * np.sin(Pp), -np.sin(T)], -1)
    r = radius(T)
    dr = (radius(T + 1e-5) - radius(T - 1e-5)) / 2e-5
    P = d * r[..., None]
    Nn = d * r[..., None] - et * dr[..., None]
    Nn /= np.linalg.norm(Nn, axis=-1, keepdims=True)
    V = np.concatenate([[[0.0, 0.0, float(radius(0.0))]], P.reshape(-1, 3)])
    N = np.concatenate([[[0.0, 0.0, 1.0]], Nn.reshape(-1, 3)])
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
    F = np.asarray(F, np.int64)
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    if (fn * N[F].mean(1)).sum(1).mean() < 0:
        F = F[:, [0, 2, 1]]
    UV = np.column_stack([0.5 + V[:, 0] / (2 * UV_HALF), 0.5 + V[:, 1] / (2 * UV_HALF)])
    return dict(V=V, F=F, N=N, UV=UV)
