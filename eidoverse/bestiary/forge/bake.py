"""THE BAKE (Warp, GPU): the SDF high (voxel.SparseSDF, the hybrid field) onto the low's UVs, per texel at ss x ss
sub-samples, every pass in one kernel. The robot body's gpu_bake method (the UV layout as a BVH in texel space, the
runtime's own tangent frame, the matched inverse) with an SDF in place of a triangle high:

  1. the low under the sub-sample: its point and THE ENGINE'S TANGENT FRAME there (material.engine_tbn, the one copy:
     three r184's per-fragment TBN from the exported NORMAL and TANGENT, the bitangent cross(N, T) * w per vertex, each
     lerped and normalised);
  2. the search, BOUNDED PER SAMPLE by the field at the low point p (r4: a fixed 6 mm start landed past thin
     membranes and across 1-2 mm folds), along the low's normal (turned continuously toward the low triangle's own
     normal where the low's normal tilts 15 -> 45 degrees off it: at an open edge the welded normal lies in the
     membrane's plane, and a search along it skews the detail millimetres along the membrane). Outside the high: the
     start c = clamp(1.5 |f(p)| + 0.3 mm, 0.3 mm, cage) out, pulled in while it lies inside the high (a neighbouring
     feature), sphere-traced inward at most c + |f(p)| + reach_margin. Inside the high: the first exit along the
     normal, at most exit_max along the welded normal (default the cage) and the cage along a turned search (a march
     inside the solid, which cannot pass a membrane; a bounded start would lie inside every bump taller than
     1.5 |f(p)| + 0.3 mm);
  3. at the hit the field's gradient is the high's normal. A hit reached through air is REJECTED when its normal
     faces away from the search direction or from the low TRIANGLE's own normal (dot < face_min: a membrane's far
     face past an open edge, where the welded normal lies in the membrane's plane; a lumen wall at grazing) or when it
     lies more than far_max beyond the nearest surface (|hit - p| > |f(p)| + far_max: across a fold); an exit (solid
     only: it cannot cross a fold, and a membrane's own face can lie its thickness from p) only when it faces away from
     the triangle, and a deep one (along a membrane to its far rim) yields to a nearer hit along the triangle's
     normal. The search is retried along the triangle's normal, then the field's CLOSEST POINT is taken
     (p -= f grad f, proj_iters times; kept when it converged and does not face away from the triangle), and last,
     where the search had turned toward the triangle's normal, along the WELDED normal, its hit judged against that
     normal (a sheared quad folded along its diagonal: its triangle's normal is the wrong one); else the sub-sample is
     a miss, which the gate sees. The tangent-space normal is the inverse of the shader's
     mat3(T, B, N) applied to the high's normal (material.tbn_encode);
  4. AO: cosine rays sphere-traced in the field (ao_r); CAVITY the same at cav_r. When the field carries OCCLUDER
     values (field.val_occ: a second value array on the same voxel topology), these rays read them instead: parts
     the surface search must not see but whose shade the skin must take (the octopus's geometric suckers: their own
     mesh carries their relief, octopus_suckers.occluder_values);
  5. THICKNESS: rays marched INTO the high until they leave it (the subsurface drive);
  6. CURVATURE: the field's Laplacian at the hit (2 x mean curvature for a distance field);
  7. HEIGHT: the high's offset from the low along the low's normal (+ above);
  8. BASE: the unsculpted block-out's surface point near the (corrected) hit, along the low's normal (the anatomical
     coordinate the sculpt planned its patch sites in, so the material pass's grooves agree with the papillae);
  9. MATERIAL IDS (work/bestiary/patches/material_ids_v2.md): the voxels' ids round each sub-sample's hit voted with
     trilinear weights (voxel.vmat), summed over the texel's hits, the two heaviest packed (voxel.lab_pack: id0 | id1
     << 8 | weight << 16; 0 = all skin). A hit on a growth id more than growth_lift above the low is GROWTH-OCCLUDED
     (the growths mesh covers it), not baked.
Outputs (size x size): normal (rgb tangent, a coverage), ao, cavity, thickness, curvature, height, position (world),
base (world, w = found), region (the low's region id), gate_flags (the FLAG_* bits of the fixes' work per texel),
mat (the packed ids), gocc (growth-occluded sub-samples), hidden (texels under a growth: left out of the miss bar and
the gate); the gate's tables (gate(): 'gate', 'gate_islands', 'gate_clusters').
fix=False runs the bake as it was before r4 (the fixed cage, no rejection, no fallback; the gate still reports).
"""
import numpy as np
import warp as wp

from . import material as MT
from . import sdf as S_
from . import voxel as VX

wp.set_module_options({'enable_backward': False})    # forward-only kernels: no adjoint code to compile
# the GROWTH id range's top (forge/growth.py ID_RANGES['growth'] = 1-63): the growth-occlusion test drops only those
# ids; a cyborg plate's (64-95, forge/cyborg.py) is the skin's own relief, baked at any height
GROWTH_ID_MAX = wp.constant(63)


@wp.func
def frame_inv(t: wp.vec3, b: wp.vec3, n: wp.vec3, v: wp.vec3):
    m = wp.mat33(t[0], b[0], n[0], t[1], b[1], n[1], t[2], b[2], n[2])
    if wp.abs(wp.determinant(m)) < 1.0e-9:
        return wp.vec3(0.0, 0.0, 1.0)
    return wp.inverse(m) @ v


@wp.func
def cos_dir(n: wp.vec3, d: wp.vec2):
    z = wp.sqrt(wp.max(0.0, 1.0 - d[0] * d[0] - d[1] * d[1]))
    a = wp.vec3(0.0, 0.0, 1.0)
    if wp.abs(n[2]) > 0.9:
        a = wp.vec3(1.0, 0.0, 0.0)
    t1 = wp.normalize(wp.cross(n, a))
    t2 = wp.cross(n, t1)
    return wp.normalize(t1 * d[0] + t2 * d[1] + n * z)


@wp.func
def trace_in(o: wp.vec3, rd: wp.vec3, reach: float, vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int,
             kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
             par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
             node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
             thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """a sphere trace from o along -rd to the high's zero, at most `reach`; a bisection. Returns (hi, status): the
    hit's distance from o; status 1 a hit, 0 no surface within the reach (the search limit), -1 o inside the high"""
    t = float(0.0)
    t_prev = float(0.0)
    f = VX.hybrid(o, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    hit = int(0)
    if f < 0.0:
        return wp.vec2(0.0, -1.0)
    for it in range(128):
        if f < 0.0:
            hit = 1
            break
        step = wp.max(f * 0.8, 2.0e-6)
        t_prev = t
        t = t + step
        if t > reach:
            break
        f = VX.hybrid(o - rd * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                      tri)
    if hit == 0:
        return wp.vec2(0.0, 0.0)
    lo = t_prev
    hi = t
    for it in range(22):
        mid = 0.5 * (lo + hi)
        fm = VX.hybrid(o - rd * mid, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                       thick, tri)
        if fm > 0.0:
            lo = mid
        else:
            hi = mid
    return wp.vec2(hi, 1.0)


@wp.func
def exit_out(p: wp.vec3, d: wp.vec3, air_max: float, tmax: float, vol: wp.uint64, val: wp.array(dtype=wp.float32),
             n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32),
             par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3),
             node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64),
             thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """the first exit along d of the solid at p (p inside the high) or of the solid that begins at most air_max ahead
    of p (the air crossed first): a march inside the solid (|f| bounds the distance to the boundary there, a union's
    field included, so no step crosses it), at most tmax in all; a bisection. Returns (t, status): the exit's
    distance from p; status 1 found, 0 none"""
    t = float(0.0)
    t_prev = float(0.0)
    f = VX.hybrid(p, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    for it in range(32):
        if f <= 0.0:
            break
        t = t + wp.max(f * 0.8, 2.0e-6)
        if t > air_max:
            return wp.vec2(0.0, 0.0)
        f = VX.hybrid(p + d * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                      tri)
    if f > 0.0:
        return wp.vec2(0.0, 0.0)
    t_prev = t
    out = int(0)
    # (a march along a wall at a few degrees closes on it by a few per cent a step: the headroom of 256 steps, and
    # a 10 um least step, far below a voxel, that the bisection refines)
    for it in range(256):
        if f > 0.0:
            out = 1
            break
        t_prev = t
        t = t + wp.max(-f * 0.8, 1.0e-5)
        if t > tmax:
            break
        f = VX.hybrid(p + d * t, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                      tri)
    if out == 0:
        return wp.vec2(0.0, 0.0)
    lo = t_prev
    hi = t
    for it in range(22):
        mid = 0.5 * (lo + hi)
        fm = VX.hybrid(p + d * mid, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                       thick, tri)
        if fm > 0.0:
            hi = mid
        else:
            lo = mid
    return wp.vec2(hi, 1.0)


@wp.func
def attempt(p: wp.vec3, d: wp.vec3, fg: wp.vec3, f0: float, old: int, n_two: int, cage: float, cage_min: float,
            cage_k: float, reach_margin: float, face_min: float, far_max: float, exit_max: float, h_grad: float,
            vol: wp.uint64,
            val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
            kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
            node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
            shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """one sub-sample's search along d from the low point p (f0 = f(p)) for the nearest surface facing d:
      outside the high: the start c out along d, c = clamp(cage_k |f0| + cage_min, cage_min, cage) (bounded by the
        field, so it cannot lie past a membrane or a fold much thinner than the low's own distance to the high),
        pulled in while inside (a neighbouring feature), a trace inward reaching c + |f0| + reach_margin;
      inside the high, or with no valid hit that way: the first exit along d of the solid at p, or of a solid that
        begins within c ahead of p (p a hair outside a face turned away from d: the oral texels at a web's margin,
        whose low point lies on the aboral face), at most exit_max along d (bake_misses: the cage's 6 mm stopped the
        exits from the arm bases' skin through their 16-18 mm suckers, whose tops stand 6.6-8.0 mm over it; k_bake
        passes exit_max only when d is the welded normal, the cage otherwise). A bounded
        start would lie inside every feature taller than cage_k |f0| + cage_min over p (a union's interior field is no
        distance), and an exit crosses solid only.
    A hit through air is valid when its normal faces d and the reference normal fg (the triangle's; the welded
    normal for the last attempt, k_bake) (dot >= face_min) and it lies at most far_max beyond the nearest surface; an
    exit, when its normal does not face away from fg (dot >= 0).
    old = 1: the search before r4 (the start `cage` out, pulled in, a trace reaching c + cage, any hit kept, no exit).
    n_two = 2 (a runtime count: the two phases share one normal evaluation; a forge kernel's code size is its compile
    time). Returns mat33 rows: the hit; its normal; (code, c, hi): code = status + 8 flags (status 1 a hit through
    air, 2 an exit, 0 none; flags the bits of what was rejected (1 facing, 2 far) or met (16: no surface within the
    reach)), c the trace's start out along d and hi the hit's distance from it"""
    af = wp.abs(f0)
    fl = int(0)
    c0 = cage
    if old == 0:
        c0 = wp.clamp(cage_k * af + cage_min, cage_min, cage)
    c = c0
    hi = float(0.0)
    q = p
    hq = d
    found = int(0)
    for phase in range(n_two):
        if found == 0:
            cand = int(0)
            if phase == 0:
                if old == 1 or f0 >= 0.0:
                    for k in range(6):
                        if VX.hybrid(p + d * c, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                     shells, thick, tri) > 0.0:
                            break
                        c = c * 0.5
                    o = p + d * c
                    reach = c + af + reach_margin
                    if old == 1:
                        reach = c + cage
                    tr = trace_in(o, d, reach, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                  shells, thick, tri)
                    if tr[1] > 0.5:
                        hi = tr[0]
                        q = o - d * hi
                        cand = 1
                    elif tr[1] > -0.5:
                        fl = fl | 16
            elif old == 0:
                air = float(0.0)
                if f0 >= 0.0:
                    air = c0
                e = exit_out(p, d, air, exit_max, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                             shells, thick, tri)
                if e[1] > 0.5:
                    q = p + d * e[0]
                    cand = 2
                elif f0 < 0.0:
                    fl = fl | 16
            if cand > 0:
                hq = VX.hnormal(q, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                                thick, tri)
                if old == 1:
                    found = 1
                elif cand == 1:
                    if wp.dot(hq, d) < face_min or wp.dot(hq, fg) < face_min:
                        fl = fl | 1
                    elif wp.length(q - p) > af + far_max:
                        fl = fl | 2
                    else:
                        found = 1
                else:
                    # an exit faces d by construction (a grazing one is a steep flank, as a trace from outside
                    # finds it): it is the wrong surface only when it turns away from the triangle (a far face)
                    if wp.dot(hq, fg) < 0.0:
                        fl = fl | 1
                    else:
                        found = 2
    return wp.mat33(q[0], q[1], q[2], hq[0], hq[1], hq[2], float(found) + 8.0 * float(fl), c, hi)


@wp.func
def base_in(o: wp.vec3, rd: wp.vec3, limit: float, n_prim: int, kind: wp.array(dtype=wp.int32),
            op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
            node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
            node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
            tri: wp.array(dtype=wp.int32)):
    """the unsculpted block-out's surface from o along -rd, at most `limit`: (distance from o, found)"""
    t_bs = float(0.0)
    t_bs_prev = float(0.0)
    f_bs = S_.program(o, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
    hit_bs = int(0)
    if f_bs > 0.0:
        for it in range(160):
            if f_bs < 0.0:
                hit_bs = 1
                break
            t_bs_prev = t_bs
            t_bs = t_bs + wp.max(f_bs * 0.9, 2.0e-6)
            if t_bs > limit:
                break
            f_bs = S_.program(o - rd * t_bs, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                              tri)
    if hit_bs == 0:
        return wp.vec2(0.0, 0.0)
    lo_bs = t_bs_prev
    hi_bs = t_bs
    for it in range(20):
        mid_bs = 0.5 * (lo_bs + hi_bs)
        if S_.program(o - rd * mid_bs, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                      tri) > 0.0:
            lo_bs = mid_bs
        else:
            hi_bs = mid_bs
    return wp.vec2(hi_bs, 1.0)


@wp.func
def project_high(p: wp.vec3, iters: int, h_grad: float, vol: wp.uint64, val: wp.array(dtype=wp.float32),
                 n_prim: int, kind: wp.array(dtype=wp.int32), op: wp.array(dtype=wp.int32),
                 kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32), node_p: wp.array(dtype=wp.vec3),
                 node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4), node_h: wp.array(dtype=wp.vec4),
                 shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32), tri: wp.array(dtype=wp.int32)):
    """the closest point of the high's zero to p: p -= f grad f, `iters` times (a vanishing gradient stops it).
    Returns mat33 rows: the point; the field's normal there; (f there, 0, 0)"""
    q = p
    f = float(0.0)
    g = wp.vec3(0.0)
    for it in range(iters + 1):
        f = VX.hybrid(q, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
        g = VX.hnormal(q, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                       tri)
        if it == iters or wp.length(g) < 0.5:
            break
        q = q - g * f
    return wp.mat33(q[0], q[1], q[2], g[0], g[1], g[2], f, 0.0, 0.0)


@wp.kernel
def k_bake(uv_mesh: wp.uint64, size: int, ss: int, cage: float, ao_r: float, cav_r: float, n_ao: int, n_cav: int,
           n_thk: int, thk_max: float, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
           ltan: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32), seed: int, h_grad: float,
           fix: int, n_two: int, face_min: float, tilt0: float, tilt1: float, cage_min: float, cage_k: float,
           reach_margin: float, far_max: float, exit_max: float, proj_iters: int, proj_tol: float, lim_frac: float,
           lisl: wp.array(dtype=wp.int32),
           o_isl: wp.array(dtype=wp.int32), o_flags: wp.array(dtype=wp.uint8),
           o_normal: wp.array(dtype=wp.vec4), o_ao: wp.array(dtype=wp.float32), o_cav: wp.array(dtype=wp.float32),
           o_thk: wp.array(dtype=wp.float32), o_curv: wp.array(dtype=wp.float32), o_hgt: wp.array(dtype=wp.float32),
           o_pos: wp.array(dtype=wp.vec4), o_reg: wp.array(dtype=wp.int32), o_base: wp.array(dtype=wp.vec4),
           o_miss: wp.array(dtype=wp.int32), o_mat: wp.array(dtype=wp.int32), mat: wp.array(dtype=wp.uint8),
           has_mat: int, lift: float, o_gocc: wp.array(dtype=wp.int32),
           vol: wp.uint64, val: wp.array(dtype=wp.float32), n_prim: int, kind: wp.array(dtype=wp.int32),
           op: wp.array(dtype=wp.int32), kk: wp.array(dtype=wp.float32), par: wp.array(dtype=wp.float32),
           node_p: wp.array(dtype=wp.vec3), node_n: wp.array(dtype=wp.vec3), node_r: wp.array(dtype=wp.vec4),
           node_h: wp.array(dtype=wp.vec4), shells: wp.array(dtype=wp.uint64), thick: wp.array(dtype=wp.float32),
           tri: wp.array(dtype=wp.int32), t0: int, val_occ: wp.array(dtype=wp.float32)):
    tid = wp.tid() + t0
    x = tid % size
    y = tid // size
    down = wp.vec3(0.0, 0.0, -1.0)
    state = wp.rand_init(seed, tid)
    acc_n = wp.vec3(0.0)
    acc_ao = float(0.0)
    acc_cav = float(0.0)
    acc_thk = float(0.0)
    acc_curv = float(0.0)
    acc_h = float(0.0)
    hits = int(0)
    low_hits = int(0)
    flags = int(0)
    first = int(1)
    lab = VX.lab_new()
    gocc = int(0)
    inv = 1.0 / float(ss)
    for i in range(ss):
        for j in range(ss):
            s = wp.mesh_query_ray(uv_mesh, wp.vec3(float(x) + (float(i) + 0.5) * inv, float(y) + (float(j) + 0.5) * inv,
                                                   1.0), down, 2.0)
            if not s.result:
                continue
            low_hits = low_hits + 1
            o_isl[tid] = lisl[s.face]
            c0 = 3 * s.face
            u = s.u
            v = s.v
            w = 1.0 - u - v
            p = lpos[c0] * u + lpos[c0 + 1] * v + lpos[c0 + 2] * w
            # THE ENGINE'S FRAME here (material.engine_tbn: three r184's per-fragment TBN from the glb's NORMAL and
            # TANGENT, the one copy of that math, the look-dev decodes with it); its N is the normal the search follows
            tbn = MT.engine_tbn(lnrm[c0], lnrm[c0 + 1], lnrm[c0 + 2], ltan[c0], ltan[c0 + 1], ltan[c0 + 2], u, v, w)
            nn = wp.vec3(tbn[0, 2], tbn[1, 2], tbn[2, 2])
            ok = int(0)
            hp = p
            hn = nn
            hgt = float(0.0)
            c = cage
            # the low triangle's own normal, turned to the side its corners' normals face (at an open edge the welded
            # normal lies in the membrane's plane: the triangle's normal still tells its face)
            fg = wp.cross(lpos[c0 + 1] - lpos[c0], lpos[c0 + 2] - lpos[c0])
            if wp.length(fg) > 1.0e-20:
                fg = wp.normalize(fg)
                if wp.dot(fg, lnrm[c0] + lnrm[c0 + 1] + lnrm[c0 + 2]) < 0.0:
                    fg = -fg
            else:
                fg = nn
            f0 = float(0.0)
            tw = float(0.0)
            d0 = nn
            n_att = 1
            if fix == 1:
                f0 = VX.hybrid(p, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                               tri)
                # the search direction turns from the low's normal to the triangle's as the low's normal tilts off
                # it from acos(tilt0) to acos(tilt1) (an open edge's welded normal lies in the membrane's plane: a
                # search along it skews the high's detail millimetres along the membrane); continuously, so the hits
                # do not jump
                tw = wp.clamp((tilt0 - wp.dot(nn, fg)) / wp.max(tilt0 - tilt1, 1.0e-6), 0.0, 1.0)
                tw = tw * tw * (3.0 - 2.0 * tw)
                d0 = wp.normalize(nn * (1.0 - tw) + fg * tw)
                n_att = n_two + 2
            af = wp.abs(f0)
            # the search (attempt()); fix = 1: then, where it differs, along the triangle's normal. A hit is rejected
            # when its normal faces away from the search direction or the triangle (FACING: a far face, a wall at
            # grazing) or when, reached through air, it lies far_max beyond the nearest surface (FAR: across a fold).
            # An exit crosses solid only (a membrane's own face can lie its thickness away), but a DEEP one (beyond
            # |f(p)| + far_max: along a membrane, where an open edge's normal runs in its plane, to its far rim)
            # yields to a hit along the triangle's normal that is not deep. Then (att 2) the field's closest point; and
            # last (att 3), where the search had turned toward the triangle's normal (tw > 0) and nothing was kept, along
            # the WELDED normal with it as the facing reference (bake_misses: a sheared quad folded along its diagonal,
            # the v4 crown where an arm's side column and a shallow web's first column run 70-112 mm out of step, has
            # triangles 53-93 deg off their own corners' normals; the turn sends the search along that triangle's
            # normal, parallel to the skin, and the closest point 0.7 mm away faces away from it; the welded normal
            # meets the skin within 0.3-4.5 mm at 89 % of them). One loop, so attempt() is inlined once (a forge
            # kernel's code size is its compile time)
            best = float(1.0e9)
            deep = int(0)
            src = int(0)
            for att in range(n_att):
                if att == 2:
                    if ok == 0:
                        # the field's closest point, kept when it converged and does not face away from the triangle
                        # (a membrane's far face can be the nearer one)
                        m = project_high(p, proj_iters, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n,
                                         node_r, node_h, shells, thick, tri)
                        mf = m[2]
                        if wp.abs(mf[0]) <= proj_tol and wp.dot(m[1], fg) > 0.0:
                            ok = 1
                            hp = m[0]
                            hn = m[1]
                            src = 2
                            flags = flags | 8
                elif (att == 0 or (att == 1 and wp.dot(d0, fg) < 0.999) or (att == 3 and tw > 0.0 and ok == 0)) and (
                        ok == 0 or deep == 1):
                    sd = d0
                    ref = fg
                    if att == 1:
                        sd = fg
                    elif att == 3:
                        sd = nn
                        ref = nn
                    # the exit's own reach (exit_max) only along the welded normal (the search not turned, or the
                    # welded attempt): a height over the skin. Along a turned or a triangle's normal the exit stays
                    # within the cage (a sheared sliver's triangle runs 53-93 deg off the skin's normal: a 6-10 mm exit
                    # along it runs through the solid beside the skin, not up through a tall feature)
                    exm = cage
                    if (att == 0 and tw <= 0.0) or att == 3:
                        exm = exit_max
                    r = attempt(p, sd, ref, f0, 1 - fix, n_two, cage, cage_min, cage_k, reach_margin, face_min,
                                far_max, exm, h_grad, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r,
                                node_h, shells, thick, tri)
                    rc = r[2]
                    code = int(rc[0] + 0.5)
                    fa = code // 8
                    if att >= 1:
                        fa = fa & 3                   # (the search limit is the primary search's)
                    flags = flags | fa
                    st = code % 8
                    if st > 0:
                        hq = r[0]
                        dq = wp.length(hq - p)
                        dp_ = int(0)
                        if st == 2 and dq > af + far_max:
                            dp_ = 1
                            flags = flags | 2
                        # (a deep exit yields only to a hit that is not deep: two deep exits a few degrees apart,
                        # through one tall feature, would flip texel by texel)
                        if ok == 0 or (dp_ == 0 and dq < best):
                            ok = 1
                            best = dq
                            deep = dp_
                            hp = hq
                            hn = r[1]
                            src = att
                            if fix == 0:
                                c = rc[1]
                                hgt = rc[1] - rc[2]
                                if wp.abs(hgt) >= lim_frac * cage:
                                    flags = flags | 16
            if fix == 1:
                if ok == 1 and src == 3:
                    flags = flags | 32                # found along the welded normal, all the rest having failed
                elif ok == 1 and src < 2 and (src == 1 or tw > 0.0):
                    flags = flags | 4                 # the search leaned on the triangle's normal
                hgt = wp.dot(hp - p, nn)
            if ok == 0:
                continue
            # a GROWTH standing over this texel (a leaning crystal's flank, a short one's top, the exit from a buried
            # base) more than `lift` above the low is not the skin's surface: the growths mesh covers it (lift 0: the
            # growths mesh's own bake). Growth ids only (GROWTH_ID_MAX): a cyborg plate standing that high is skin
            # relief, not covered by any growths mesh
            if lift > 0.0 and has_mat == 1 and hgt > lift:
                gid = VX.lab_pack(VX.vmat(vol, mat, hp, VX.lab_new(), 1.0)) & 255
                if gid != 0 and gid <= GROWTH_ID_MAX:
                    gocc = gocc + 1
                    continue
            tn = MT.tbn_encode(tbn, hn)
            acc_n = acc_n + tn
            acc_h = acc_h + hgt
            hits = hits + 1
            if has_mat == 1:
                lab = VX.vmat(vol, mat, hp, lab, 1.0)
            if first == 1:
                o_pos[tid] = wp.vec4(hp[0], hp[1], hp[2], 1.0)
                o_reg[tid] = lreg[s.face]
                # the unsculpted block-out's surface: along the same ray (before r4), or from the corrected hit along
                # the low's normal, its start bounded by the block-out's field there as the high's search is
                ob = p + nn * c
                lim = c + cage + 0.004
                if fix == 1:
                    fb = S_.program(hp, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick, tri)
                    afb = wp.abs(fb)
                    cb = wp.clamp(cage_k * afb + cage_min, cage_min, cage)
                    for k in range(6):
                        if S_.program(hp + nn * cb, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                                      thick, tri) > 0.0:
                            break
                        cb = cb * 0.5
                    ob = hp + nn * cb
                    lim = cb + afb + reach_margin
                bt = base_in(ob, nn, lim, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                             tri)
                if bt[1] > 0.5:
                    p_bs = ob - nn * bt[0]
                    o_base[tid] = wp.vec4(p_bs[0], p_bs[1], p_bs[2], 1.0)
                first = 0
            # AO and cavity: cosine rays sphere-traced in the field (its occluder values: val_occ, = val without them)
            org = hp + hn * 2.0e-4
            occ = int(0)
            for a in range(n_ao):
                d = cos_dir(hn, wp.sample_unit_disk(state))
                tt = float(0.0)
                for it in range(40):
                    fd = VX.hybrid(org + d * tt, vol, val_occ, n_prim, kind, op, kk, par, node_p, node_n, node_r,
                                   node_h, shells, thick, tri)
                    if fd < 1.0e-5:
                        occ = occ + 1
                        break
                    tt = tt + wp.max(fd * 0.9, 1.0e-4)
                    if tt > ao_r:
                        break
            acc_ao = acc_ao + 1.0 - float(occ) / float(wp.max(n_ao, 1))
            occ = int(0)
            for a in range(n_cav):
                d = cos_dir(hn, wp.sample_unit_disk(state))
                tt = float(0.0)
                for it in range(24):
                    fd = VX.hybrid(org + d * tt, vol, val_occ, n_prim, kind, op, kk, par, node_p, node_n, node_r,
                                   node_h, shells, thick, tri)
                    if fd < 1.0e-5:
                        occ = occ + 1
                        break
                    tt = tt + wp.max(fd * 0.9, 5.0e-5)
                    if tt > cav_r:
                        break
            acc_cav = acc_cav + 1.0 - float(occ) / float(wp.max(n_cav, 1))
            # thickness: inward rays (a cone about -hn) marched until they leave the solid
            th = float(0.0)
            for a in range(n_thk):
                dd = wp.sample_unit_disk(state) * 0.5
                d = cos_dir(-hn, dd)
                tt = float(5.0e-4)
                for it in range(64):
                    fd = VX.hybrid(hp + d * tt, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                   shells, thick, tri)
                    if fd > 0.0:
                        break
                    tt = tt + wp.max(-fd * 0.9, 2.0e-4)
                    if tt > thk_max:
                        tt = thk_max
                        break
                th = th + tt
            acc_thk = acc_thk + th / float(wp.max(n_thk, 1))
            # curvature: the field's Laplacian (h = 4 voxels' worth of the gradient step)
            hc = h_grad * 4.0
            f0c = VX.hybrid(hp, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells, thick,
                            tri)
            lap = float(0.0)
            for a in range(3):
                e = wp.vec3(0.0)
                if a == 0:
                    e = wp.vec3(hc, 0.0, 0.0)
                elif a == 1:
                    e = wp.vec3(0.0, hc, 0.0)
                else:
                    e = wp.vec3(0.0, 0.0, hc)
                lap = lap + VX.hybrid(hp + e, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h,
                                      shells, thick, tri) + \
                    VX.hybrid(hp - e, vol, val, n_prim, kind, op, kk, par, node_p, node_n, node_r, node_h, shells,
                              thick, tri) - 2.0 * f0c
            acc_curv = acc_curv + lap / (hc * hc)
    o_miss[tid] = low_hits - hits - gocc
    o_gocc[tid] = gocc
    o_flags[tid] = wp.uint8(flags)
    if hits > 0:
        fh = float(hits)
        mn = acc_n / fh
        cov = fh / float(ss * ss)
        mn = wp.normalize(mn)
        o_normal[tid] = wp.vec4(mn[0], mn[1], mn[2], cov)
        o_ao[tid] = acc_ao / fh
        o_cav[tid] = acc_cav / fh
        o_thk[tid] = acc_thk / fh
        o_curv[tid] = acc_curv / fh
        o_hgt[tid] = acc_h / fh
        o_mat[tid] = VX.lab_pack(lab)


@wp.kernel
def k_low_point(uv_mesh: wp.uint64, xs: wp.array(dtype=wp.int32), ys: wp.array(dtype=wp.int32),
                lpos: wp.array(dtype=wp.vec3), out: wp.array(dtype=wp.vec4)):
    """the low's point under each listed texel (kernel rows: y = v * size): its centre, else the first quarter point
    the low covers (an island's border texel); w = 0 where none is"""
    i = wp.tid()
    for k in range(5):
        ox = float(0.5)
        oy = float(0.5)
        if k == 1:
            ox = 0.25
            oy = 0.25
        elif k == 2:
            ox = 0.75
            oy = 0.25
        elif k == 3:
            ox = 0.25
            oy = 0.75
        elif k == 4:
            ox = 0.75
            oy = 0.75
        s = wp.mesh_query_ray(uv_mesh, wp.vec3(float(xs[i]) + ox, float(ys[i]) + oy, 1.0), wp.vec3(0.0, 0.0, -1.0),
                              2.0)
        if s.result:
            c0 = 3 * s.face
            p = lpos[c0] * s.u + lpos[c0 + 1] * s.v + lpos[c0 + 2] * (1.0 - s.u - s.v)
            out[i] = wp.vec4(p[0], p[1], p[2], 1.0)
            return


def low_frames(V, F, UV, N=None):
    """per-corner-vertex normals (area-weighted over the WELDED positions when N is None) and MikkT-style tangents
    (UV-derivative tangents accumulated per vertex, Gram-Schmidt against the normal, handedness in w)"""
    V = np.asarray(V, np.float64)
    if N is None:
        fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
        N = np.zeros_like(V)
        for k in range(3):
            np.add.at(N, F[:, k], fn)
        N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-20)
    p0, p1, p2 = V[F[:, 0]], V[F[:, 1]], V[F[:, 2]]
    t0, t1, t2 = UV[F[:, 0]], UV[F[:, 1]], UV[F[:, 2]]
    e1, e2 = p1 - p0, p2 - p0
    d1, d2 = t1 - t0, t2 - t0
    r = d1[:, 0] * d2[:, 1] - d2[:, 0] * d1[:, 1]
    r = np.where(np.abs(r) < 1e-14, 1e-14, r)
    T = (e1 * d2[:, 1:2] - e2 * d1[:, 1:2]) / r[:, None]
    Bt = (e2 * d1[:, 0:1] - e1 * d2[:, 0:1]) / r[:, None]
    Ta = np.zeros_like(V)
    Ba = np.zeros_like(V)
    for k in range(3):
        np.add.at(Ta, F[:, k], T)
        np.add.at(Ba, F[:, k], Bt)
    Tg = Ta - (Ta * N).sum(1, keepdims=True) * N
    Tg /= np.maximum(np.linalg.norm(Tg, axis=1, keepdims=True), 1e-20)
    w = np.where((np.cross(N, Tg) * Ba).sum(1) < 0, -1.0, 1.0)
    return N, np.column_stack([Tg, w])


def bake(field, V, F, UV, N, TAN, region, size=2048, ss=2, cage=0.006, ao_r=0.025, cav_r=0.0025, n_ao=24,
         n_cav=12, n_thk=6, thk_max=0.05, seed=7, band_rows=128, log=print, fix=True, face_min=0.2,
         tilt=(15.0, 45.0), cage_min=0.0003, cage_k=1.5, reach_margin=0.001, far_max=0.002, exit_max=None,
         proj_iters=3, proj_tol=1.0e-4, lim_frac=0.95, island_pct=1.0, cluster_len=20.0, region_names=None,
         exclude=None, growth_lift=0.0015):
    """V, F: the low (triangles; per-vertex UV, N, TAN (x,y,z,w)); region: per-triangle int. Returns a dict of
    (size, size, k) arrays, rows top-down (image order, v = 0 at the bottom flipped), with 'gate_flags' (uint8 per
    texel, FLAG_* bits over its sub-samples) and the gate's tables ('gate', 'gate_islands', 'gate_clusters').
    GROWTHS (material_ids_v2.md; inert on a field without material ids): 'mat' the packed ids per texel; exclude(points
    (n, 3)) -> bool flags texels whose low point lies under a growth (growth.inside_any: the growths mesh covers them),
    'hidden' and kept out of the miss bar and the gate; growth_lift: a sub-sample whose hit lands on a growth id more
    than this above the low is growth-occluded ('gocc'), not baked (a texel occluded in every sub-sample is hidden too);
    0 bakes growth hits at any height (the growths mesh's own bake).
    The r4 fixes (fix=False: off, the bake as it was): outside the high the cage start clamp(cage_k |f(p)| + cage_min,
    cage_min, cage) and the reach c + |f(p)| + reach_margin, inside it the first exit along the normal (at most
    exit_max along the welded normal, default the cage; a larger reach lets an exit along the welded normal reach a
    tall solid feature's top, as the sculpted 16-18 mm suckers needed before they became geometry; along a turned
    search or the triangle's normal at most the cage, as a sliver's triangle normal runs beside the skin); a hit facing
    away (dot with the search direction or the triangle's normal < face_min) or, reached through air, more than
    far_max beyond the nearest surface is rejected and the search retried along the triangle's normal (which also
    replaces an exit deeper than that when it finds a nearer hit); the search direction itself turns from the low's
    normal to the triangle's as the low's normal tilts tilt[0] -> tilt[1] degrees off it (an open edge); then the
    field's closest point (proj_iters steps, kept when |f| <= proj_tol and not facing away from the triangle); last,
    where that turn had been made and nothing was kept, the search along the welded normal itself, judged against it
    (a folded sliver, whose triangle's normal is the wrong one: FLAG_WELDED). The
    gate (gate()): island_pct, cluster_len its bars, lim_frac the share of the cage at which a hit counts at the
    search limit (fix=False); region_names {id: name} names the islands in the log."""
    import time
    t0 = time.time()
    F = np.asarray(F, np.int32)
    corner = F.ravel()
    luv = np.asarray(UV, np.float64)[corner] * size
    uv_mesh = wp.Mesh(points=wp.array(np.column_stack([luv, np.zeros(len(luv))]).astype(np.float32), dtype=wp.vec3),
                      indices=wp.array(np.arange(len(luv), dtype=np.int32), dtype=wp.int32))
    lpos = wp.array(np.asarray(V, np.float32)[corner], dtype=wp.vec3)
    lnrm = wp.array(np.asarray(N, np.float32)[corner], dtype=wp.vec3)
    ltan = wp.array(np.asarray(TAN, np.float32)[corner], dtype=wp.vec4)
    lreg = wp.array(np.asarray(region, np.int32), dtype=wp.int32)
    isl = islands(F, UV)                             # per triangle: its UV island
    lisl = wp.array(isl.astype(np.int32), dtype=wp.int32)
    n = size * size
    outs = dict(normal=wp.zeros(n, dtype=wp.vec4), ao=wp.zeros(n, dtype=wp.float32),
                cavity=wp.zeros(n, dtype=wp.float32), thickness=wp.zeros(n, dtype=wp.float32),
                curvature=wp.zeros(n, dtype=wp.float32), height=wp.zeros(n, dtype=wp.float32),
                position=wp.zeros(n, dtype=wp.vec4), region=wp.full(n, -1, dtype=wp.int32),
                base=wp.zeros(n, dtype=wp.vec4), miss=wp.zeros(n, dtype=wp.int32), mat=wp.zeros(n, dtype=wp.int32),
                gocc=wp.zeros(n, dtype=wp.int32))
    # the gate's per-texel inputs: the island under the texel (-1: none; the gate's, not returned) and the flags
    outs.update(island=wp.full(n, -1, dtype=wp.int32), gate_flags=wp.zeros(n, dtype=wp.uint8))
    # the field's material ids (a field without them, a SparseSDF before material ids or a dummy grid: none read)
    fmat = getattr(field, 'mat', None)
    has_mat = int(fmat is not None)
    if fmat is None:
        fmat = wp.zeros(1, dtype=wp.uint8)
    exit_max = cage if exit_max is None else exit_max
    # (the gradient over ~a voxel: a sub-voxel step shades the trilinear cells, t09). Launched in bands of rows so no
    # single launch runs long on the display GPU
    args = [uv_mesh.id, size, ss, float(cage), float(ao_r), float(cav_r), n_ao, n_cav, n_thk, float(thk_max), lpos,
            lnrm, ltan, lreg, seed, float(field.vs * 0.9), int(bool(fix)), 2, float(face_min),
            float(np.cos(np.radians(tilt[0]))), float(np.cos(np.radians(tilt[1]))), float(cage_min),
            float(cage_k), float(reach_margin), float(far_max), float(exit_max), int(proj_iters), float(proj_tol),
            float(lim_frac),
            lisl, outs['island'], outs['gate_flags'], outs['normal'], outs['ao'], outs['cavity'], outs['thickness'],
            outs['curvature'], outs['height'], outs['position'], outs['region'], outs['base'],
            outs['miss'], outs['mat'], fmat, has_mat, float(growth_lift), outs['gocc']] + field._args()
    rows = max(1, min(size, band_rows))
    val_occ = getattr(field, 'val_occ', None)        # the AO / cavity rays' occluders (none: the field itself)
    val_occ = field.val if val_occ is None else val_occ
    for r0 in range(0, size, rows):
        nr = min(rows, size - r0)
        wp.launch(k_bake, dim=nr * size, inputs=args + [r0 * size, val_occ])
        wp.synchronize()
        if r0 == 0:
            log(f'[bake] first band of {nr} rows: {time.time()-t0:.1f}s (incl. compile)')
    res = {}
    for k, a in outs.items():
        arr = a.numpy()
        arr = arr.reshape(size, size, -1) if arr.ndim > 1 else arr.reshape(size, size)
        res[k] = arr[::-1].copy()            # rows top-down: image row 0 is v = 1
    # texels under a growth (the growths mesh covers them): their search starts inside the crystal or beside a short or
    # leaning one and lands on it (a growth id) or misses; the candidates are those, then exclude() decides. They stay
    # out of the miss bar here and out of the gate (gate() leaves res['hidden'] out)
    hidden = np.zeros((size, size), bool)
    if exclude is not None:
        ys, xs = np.nonzero((res['miss'] > 0) | (res['mat'] != 0))
        if len(ys):
            lp = wp.zeros(len(ys), dtype=wp.vec4)
            wp.launch(k_low_point, dim=len(ys), inputs=[uv_mesh.id, wp.array(xs.astype(np.int32), dtype=wp.int32),
                                                        wp.array((size - 1 - ys).astype(np.int32), dtype=wp.int32),
                                                        lpos, lp])
            lp = lp.numpy()
            on = lp[:, 3] > 0.5
            hid = np.zeros(len(ys), bool)
            hid[on] = np.asarray(exclude(lp[on, :3]), bool)
            hidden[ys[hid], xs[hid]] = True
    hidden |= (res['gocc'] > 0) & (res['normal'][..., 3] <= 0)       # growth-occluded in every sub-sample
    res['hidden'] = hidden
    cov = res['normal'][..., 3] > 0
    inside = (cov | (res['miss'] > 0)) & ~hidden     # texels the low covers (a sub-sample's UV ray hit it)
    full_miss = (res['miss'] > 0) & ~cov & ~hidden
    part_miss = (res['miss'] > 0) & cov & ~hidden
    hgt = np.abs(res['height'][cov & ~hidden])
    grown_txt = ''
    if has_mat or exclude is not None:
        lead = res['mat'] & 255
        grown_id = cov & (lead != 0) & (lead <= GROWTH_ID_MAX)
        grown_txt = (f'; a growth id leads on {grown_id.sum()/max(cov.sum(), 1)*100:.2f} % of covered texels, '
                     f'{int(hidden.sum())} texels under growths left out of the bar ({int((res["gocc"] > 0).sum())} '
                     f'with growth-occluded sub-samples)')
        cyb_id = cov & (lead > GROWTH_ID_MAX)
        if cyb_id.any():                     # (a cyborg plate's ids, forge/cyborg.py: none on a plain creature)
            grown_txt += f'; a cyborg id leads on {cyb_id.sum()/max(cov.sum(), 1)*100:.2f} %'
    log(f'[bake] {size}^2 x ss {ss}: {time.time()-t0:.1f}s, coverage {cov.mean()*100:.1f} %; '
        f'missed within the cage: {full_miss.sum()/max(inside.sum(), 1)*100:.3f} % of texels whole, '
        f'{part_miss.sum()/max(inside.sum(), 1)*100:.2f} % partly (bar 0.5 %); low-to-high |d| p95 '
        f'{np.percentile(hgt, 95)*1000:.2f} mm, max {hgt.max()*1000:.2f} mm (bar p95 3 mm)' + grown_txt)
    gate(res, res.pop('island'), V, F, UV, isl, size, region, cage, fix=fix, lim_frac=lim_frac,
         island_pct=island_pct, cluster_len=cluster_len, region_names=region_names, log=log)
    return res


# gate_flags bits (per texel, over its sub-samples): a hit rejected facing away; a hit far beyond the nearest surface
# (through air: rejected; an exit: kept only for want of a nearer one); the hit's search leaning on the triangle's
# normal (an open edge's turn, or the retry); the field's closest point taken; no surface within the search's reach;
# the hit found along the welded normal after the triangle's normal and the closest point found nothing (a sliver)
FLAG_FACING, FLAG_FAR, FLAG_TRI, FLAG_CLOSEST, FLAG_LIMIT, FLAG_WELDED = 1, 2, 4, 8, 16, 32
GATE_COLS = ('ok', 'islands_failed', 'clusters_failed', 'limit_texels', 'rejected_texels', 'far_texels',
             'tri_texels', 'closest_texels', 'full_texels', 'texels', 'welded_texels')
ISLAND_COLS = ('island', 'region', 'tris', 'texels', 'full', 'part', 'full_pct', 'rejected', 'far', 'tri', 'closest',
               'closest_pct', 'limit', 'px_per_m', 'x0', 'y0', 'x1', 'y1', 'ok')
CLUSTER_COLS = ('cluster', 'island', 'texels', 'length', 'x0', 'y0', 'x1', 'y1', 'border', 'ok')


def islands(F, UV, eps=1.0e-7):
    """per triangle: its UV island (triangles joined through shared UV corners, welded at eps), numbered from 0 in
    order of first appearance"""
    from scipy.sparse import coo_matrix
    from scipy.sparse.csgraph import connected_components
    F = np.asarray(F, np.int64).reshape(-1, 3)
    if not len(F):
        return np.zeros(0, np.int64)
    q = np.round(np.asarray(UV, np.float64)[F.ravel()] / eps).astype(np.int64)
    _, key = np.unique(q, axis=0, return_inverse=True)
    key = key.reshape(-1, 3)
    nv = int(key.max()) + 1
    a = key.ravel()
    b = key[:, [1, 2, 0]].ravel()
    _, lab = connected_components(coo_matrix((np.ones(len(a), np.int8), (a, b)), shape=(nv, nv)), directed=False)
    tri = lab[key[:, 0]]
    uniq, first, inv = np.unique(tri, return_index=True, return_inverse=True)
    rank = np.empty(len(uniq), np.int64)
    rank[np.argsort(first)] = np.arange(len(uniq))
    return rank[inv.reshape(-1)]


def island_name(row, region_names=None):
    """an island's name for the logs: its main region's name (or 'region <id>') and its number"""
    r = int(row[1])
    nm = (region_names or {}).get(r, f'region {r}')
    return f'{nm} #{int(row[0])}'


def _extent(ys, xs):
    """a texel cluster's greatest extent: the largest centre-to-centre distance + 1 (one texel: 1, a run of n: n)"""
    if len(ys) == 1:
        return 1.0
    P = np.column_stack([xs, ys]).astype(np.float64)
    if len(P) > 64:
        try:
            from scipy.spatial import ConvexHull
            P = P[ConvexHull(P).vertices]
        except Exception:                            # collinear: its ends are its bounding box's corners
            return float(np.hypot(np.ptp(P[:, 0]), np.ptp(P[:, 1]))) + 1.0
    d = P[:, None, :] - P[None, :, :]
    return float(np.sqrt((d * d).sum(-1).max())) + 1.0


def gate(res, island, V, F, UV, isl, size, region, cage, fix=True, lim_frac=0.95, island_pct=1.0, cluster_len=20.0,
         region_names=None, log=print):
    """the gates the global line cannot be (one percentage over millions of texels: a small island or a lumen missed
    whole stays under its bar, r4). island: per texel (image order) the UV island under it (-1: none); isl: per
    triangle its island (islands()):
      ISLANDS: per UV island, the share of its texels FULLY missed (no sub-sample found the high); more than
        island_pct % fails the island, named in the log. Its texel density at the BAKED size (px/m) rides along;
      CLUSTERS: the fully missed texels' 8-connected clusters; one of more than cluster_len texels, or longer than
        cluster_len texels (its greatest extent), fails, wherever it lies (a compact hole the island's bar cannot see,
        a crack along a feature);
      LIMIT: texels with a sub-sample that found no surface within its reach (or, fix=False, a hit with |d| at
        lim_frac of the cage) are counted and listed per island (not failed);
    with the r4 fixes' work per island (res['gate_flags']): texels with a hit rejected facing away, a hit far beyond
    the nearest surface, the search on the triangle's normal, and on the field's closest point (a high share marks an
    island the low does not follow). Texels res marks 'hidden' are left out. Adds to res, as float64 arrays (the dict
    stays numeric for savez and the material pass; gate_rows() reads them as dicts): 'gate' (GATE_COLS),
    'gate_islands' (a row per island, ISLAND_COLS), 'gate_clusters' (a row per cluster, CLUSTER_COLS, failing first,
    then longest first; x, y in image texels, border = the share of its texels on its island's edge). Logs the block;
    returns ok"""
    from scipy import ndimage
    island = np.asarray(island)
    cov = res['normal'][..., 3] > 0
    keep = island >= 0
    if res.get('hidden') is not None:
        keep &= ~np.asarray(res['hidden'], bool)
    fl = np.asarray(res['gate_flags'], np.int64)
    full = (res['miss'] > 0) & ~cov & keep
    part = (res['miss'] > 0) & cov & keep
    rej, far, tri, prj, lim, wel = ((fl & b > 0) & keep for b in (FLAG_FACING, FLAG_FAR, FLAG_TRI, FLAG_CLOSEST,
                                                                   FLAG_LIMIT, FLAG_WELDED))
    isl = np.asarray(isl, np.int64)
    n_isl = int(isl.max()) + 1 if len(isl) else 0
    ids = np.where(keep, island, n_isl)
    cnt = lambda m: np.bincount(ids[m], minlength=n_isl + 1)[:n_isl]
    texels, n_full, n_part, n_rej, n_far, n_tri, n_prj, n_lim = (cnt(m) for m in (keep, full, part, rej, far, tri,
                                                                                  prj, lim))
    F = np.asarray(F, np.int64)
    V = np.asarray(V, np.float64)
    reg = np.asarray(region, np.int64).reshape(-1)
    main_reg = np.zeros(n_isl, np.int64)
    if len(reg) == len(isl) and n_isl:
        rr = reg - reg.min()
        M = np.zeros((n_isl, int(rr.max()) + 1), np.int64)
        np.add.at(M, (isl, rr), 1)
        main_reg = M.argmax(1) + reg.min()
    UVp = np.asarray(UV, np.float64) * size
    a3 = 0.5 * np.linalg.norm(np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]]), axis=1)
    e1, e2 = UVp[F[:, 1]] - UVp[F[:, 0]], UVp[F[:, 2]] - UVp[F[:, 0]]
    a2 = 0.5 * np.abs(e1[:, 0] * e2[:, 1] - e1[:, 1] * e2[:, 0])
    dens = np.sqrt(np.bincount(isl, a2, n_isl) / np.maximum(np.bincount(isl, a3, n_isl), 1e-30))
    dens_all = float(np.sqrt(a2.sum() / max(a3.sum(), 1e-30)))
    tc = UVp[F]                                      # (n, 3, 2): each triangle's corners in texels
    box = np.zeros((n_isl, 4))
    box[:, :2] = np.inf
    box[:, 2:] = -np.inf
    np.minimum.at(box[:, 0], isl, tc[..., 0].min(1))
    np.minimum.at(box[:, 1], isl, tc[..., 1].min(1))
    np.maximum.at(box[:, 2], isl, tc[..., 0].max(1))
    np.maximum.at(box[:, 3], isl, tc[..., 1].max(1))
    cl = lambda a: np.clip(np.floor(a), 0, size - 1)
    full_pct = 100.0 * n_full / np.maximum(texels, 1)
    proj_pct = 100.0 * n_prj / np.maximum(texels, 1)
    ok_isl = full_pct <= island_pct
    T_isl = np.column_stack([np.arange(n_isl), main_reg, np.bincount(isl, minlength=n_isl), texels, n_full, n_part,
                             full_pct, n_rej, n_far, n_tri, n_prj, proj_pct, n_lim, dens, cl(box[:, 0]),
                             size - 1 - cl(box[:, 3]), cl(box[:, 2]), size - 1 - cl(box[:, 1]),
                             ok_isl]).astype(np.float64).reshape(-1, len(ISLAND_COLS))
    # the clusters of fully missed texels
    lab, n_cl = ndimage.label(full, structure=np.ones((3, 3), bool))
    mx = ndimage.maximum_filter(island, size=3, mode='constant', cval=-1)
    mn = ndimage.minimum_filter(island, size=3, mode='constant', cval=-1)
    edge = (island >= 0) & ((mx != island) | (mn != island))
    rows = []
    for k, sl in enumerate(ndimage.find_objects(lab)):
        if sl is None:
            continue
        ys, xs = np.nonzero(lab[sl] == k + 1)
        ys, xs = ys + sl[0].start, xs + sl[1].start
        L = _extent(ys, xs)
        rows.append([k, np.bincount(island[ys, xs]).argmax(), len(ys), L, xs.min(), ys.min(), xs.max(), ys.max(),
                     edge[ys, xs].mean(), len(ys) <= cluster_len and L <= cluster_len])
    T_cl = np.asarray(rows, np.float64).reshape(-1, len(CLUSTER_COLS))
    T_cl = T_cl[np.lexsort((-T_cl[:, 3], T_cl[:, 9]))]          # the failing first, each group longest first
    nf_isl = int((~ok_isl).sum())
    nf_cl = int((T_cl[:, 9] == 0).sum())
    ok = nf_isl == 0 and nf_cl == 0
    res['gate'] = np.array([ok, nf_isl, nf_cl, lim.sum(), rej.sum(), far.sum(), tri.sum(), prj.sum(), full.sum(),
                            keep.sum(), wel.sum()], np.float64)
    res['gate_islands'] = T_isl
    res['gate_clusters'] = T_cl
    # the block
    lim_txt = 'no surface within the per-sample reach' if fix else \
        f'|d| >= {lim_frac * cage * 1000:.2f} mm or no surface within the cage'
    log(f'[bake] GATE {size}^2: {"PASS" if ok else "FAIL"}; islands over {island_pct:g} % fully missed: {nf_isl} of '
        f'{n_isl}; miss clusters over {cluster_len:g} texels (in size or extent): {nf_cl} of {len(T_cl)}; texels at '
        f'the search limit ({lim_txt}): {int(lim.sum())}; r4 fixes {"on" if fix else "OFF"}: texels with a hit '
        f'rejected facing away {int(rej.sum())}, a hit far beyond the nearest surface {int(far.sum())}, the search on '
        f'the triangle normal {int(tri.sum())}, on the welded normal {int(wel.sum())}, on the closest point '
        f'{int(prj.sum())}')
    if nf_isl:
        log('[bake]   FAILED islands: ' + ', '.join(island_name(r, region_names) for r in T_isl[~ok_isl]))
    log(f'[bake]   density at {size}: {dens_all:.0f} px/m ({1000.0 / max(dens_all, 1e-9):.3f} mm/texel) over the set'
        + (f'; islands {dens.min():.0f}..{dens.max():.0f} px/m ({1000.0 / max(dens.max(), 1e-9):.3f}..'
           f'{1000.0 / max(dens.min(), 1e-9):.3f} mm/texel)' if n_isl else ''))
    log('[bake]   island                   texels    full   full%    part  facing    far    tri  closest   cl%   limit'
        '   px/m  bbox (x0,y0)-(x1,y1)')
    order = np.lexsort((-T_isl[:, 11], -T_isl[:, 6], T_isl[:, 18])) if n_isl else []
    for r in T_isl[order][:24]:
        log(f'[bake]   {island_name(r, region_names)[:22]:22s} {int(r[3]):7d} {int(r[4]):7d} {r[6]:7.3f} '
            f'{int(r[5]):7d} {int(r[7]):7d} {int(r[8]):6d} {int(r[9]):6d} {int(r[10]):8d} {r[11]:5.1f} {int(r[12]):7d} '
            f'{r[13]:6.0f}  ({int(r[14])},{int(r[15])})-({int(r[16])},{int(r[17])})  {"ok" if r[18] else "FAIL"}')
    if n_isl > 24:
        log(f'[bake]   ... {n_isl - 24} more islands' + (', all passing' if nf_isl == int((~ok_isl[order[:24]]).sum())
                                                          else ''))
    sz = T_cl[:, 2]
    log(f'[bake]   miss clusters: {len(T_cl)} (1 texel: {int((sz == 1).sum())}, 2-5: '
        f'{int(((sz > 1) & (sz <= 5)).sum())}, 6-20: {int(((sz > 5) & (sz <= 20)).sum())}, over 20: '
        f'{int((sz > 20).sum())})' + ('; the failing first, then the longest:' if len(T_cl) else ''))
    if len(T_cl):
        log('[bake]   cluster island texels  length  bbox (x0,y0)-(x1,y1)  on edge')
        for r in T_cl[:max(12, min(nf_cl, 40))]:
            log(f'[bake]   {int(r[0]):7d} {int(r[1]):6d} {int(r[2]):6d} {r[3]:7.1f}  ({int(r[4])},{int(r[5])})-'
                f'({int(r[6])},{int(r[7])})  {r[8] * 100:5.1f} %  {"ok" if r[9] else "FAIL"}')
    return ok


def gate_rows(res, key='gate_islands'):
    """a gate table of the bake's dict as a list of dicts ('gate', 'gate_islands' or 'gate_clusters')"""
    cols = dict(gate=GATE_COLS, gate_islands=ISLAND_COLS, gate_clusters=CLUSTER_COLS)[key]
    rows = np.asarray(res[key], np.float64).reshape(-1, len(cols))
    return [dict(zip(cols, (float(x) for x in r))) for r in rows]


def dilate_all(res, steps=16):
    """every driver pushed out of the covered texels into the gutters: each gutter texel up to `steps` texels out takes
    its nearest covered texel's value (one distance transform for all channels; neighbouring islands split their
    gutter down the middle). Returns (dilated dict, grown mask)"""
    from scipy import ndimage
    cov = res['normal'][..., 3] > 0
    d, idx = ndimage.distance_transform_edt(~cov, return_indices=True)
    grown = d <= steps
    fill = grown & ~cov
    out = {}
    for k, a in res.items():
        if np.ndim(a) < 2 or np.shape(a)[:2] != cov.shape:
            out[k] = a                               # not a map (the gate's tables): passed through
            continue
        b = a.copy()
        b[fill] = a[idx[0][fill], idx[1][fill]]
        out[k] = b
    return out, grown


def driver_sheet(res, out_png, tile=1024):
    """the drivers side by side for my eyes: normal, AO, cavity, thickness, curvature, height"""
    from PIL import Image, ImageDraw
    cov = res['normal'][..., 3] > 0
    nrm = np.where(cov[..., None], res['normal'][..., :3] * 0.5 + 0.5, [0.5, 0.5, 1.0])
    g = lambda x: np.repeat(np.clip(x, 0, 1)[..., None], 3, -1)
    tiles = [('normal', nrm), ('ao', g(np.where(cov, res['ao'], 0))), ('cavity', g(np.where(cov, res['cavity'], 0))),
             ('thickness 0-50 mm', g(np.where(cov, res['thickness'] / 0.05, 0))),
             ('curvature +-4000/m', g(np.where(cov, 0.5 + res['curvature'] / 8000.0, 0))),
             ('height +-3 mm', g(np.where(cov, 0.5 + res['height'] / 0.006, 0)))]
    sheet = Image.new('RGB', (tile * 3, tile * 2))
    for i, (name, a) in enumerate(tiles):
        im = Image.fromarray((a * 255 + 0.5).astype(np.uint8)).resize((tile, tile), Image.LANCZOS)
        ImageDraw.Draw(im).text((6, 6), name, fill=(255, 64, 64))
        sheet.paste(im, ((i % 3) * tile, (i // 3) * tile))
    sheet.save(out_png)
