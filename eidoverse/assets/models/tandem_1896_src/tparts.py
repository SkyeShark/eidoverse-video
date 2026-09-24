# tparts.py - the 1890s safety tandem, part by part (bike frame: +X travel, +Y up, +Z right/drive side).
#
# Construction story (what the topology says):
#   drawn tubes           -> open-ended sweeps that stop inside the lugs (no buried caps)
#   cast lugs / brackets  -> one mass each: sockets booleaned into the shell, spear points, filleted
#   forged ends / crown   -> one mass each, the same way
#   pressed plates        -> bevelled extrusions (chainrings, cranks, pedal cages, chain plates)
#   turned parts          -> lathes (hubs, rims, tyres, nipples, cups, bell, nuts)
#   wire                  -> sweeps (spokes with J-bend heads, springs, rails, brake rod)
import math
import bpy, bmesh
from mathutils import Vector
from tgeo import (B, V, TAU, sstep, MB, sweep, lathe, plate, merge_into, line_pts, bezier3_pts, bezier2_pts,
                  catmull_pts, helix_pts, resample, boolean_union, bevel_mod, shade, apply_mods)

DEG = math.pi / 180


# ─────────────────────────────────────────────────────────────────────────────
def layout():
    L = {}
    L['R'] = 0.330; L['hubY'] = 0.328; L['tyreSec'] = 0.0205
    L['rearHub'] = (-0.87, L['hubY']); L['frontHub'] = (0.87, L['hubY'])
    L['bbY'] = 0.280; L['rearBB'] = (-0.41, L['bbY']); L['frontBB'] = (0.27, L['bbY'])
    L['crank'] = 0.150
    h = 68 * DEG
    L['headAngle'] = h; L['rake'] = 0.065
    L['axis'] = (-math.cos(h), math.sin(h)); L['axisN'] = (math.sin(h), math.cos(h))
    L['Q'] = (L['frontHub'][0] - L['rake'] * L['axisN'][0], L['frontHub'][1] - L['rake'] * L['axisN'][1])
    L['sCrown'] = 0.360; L['sHeadBot'] = 0.374; L['sHeadTop'] = 0.522; L['sQuill'] = 0.598
    L['topTubeHeadY'] = 0.721; L['fscY'] = 0.678
    L['sTop'] = (L['topTubeHeadY'] - L['Q'][1]) / L['axis'][1]
    L['sDown'] = 0.392
    sa = 70 * DEG
    L['seatAngle'] = sa; L['seatDir'] = (-math.cos(sa), math.sin(sa))
    L['headTT'] = on_axis(L, L['sTop'])
    L['FSC'] = on_seat(L, L['frontBB'], L['fscY'])
    dx, dy = L['FSC'][0] - L['headTT'][0], L['FSC'][1] - L['headTT'][1]
    sx, sy = L['seatDir']
    ex, ey = L['rearBB'][0] - L['headTT'][0], L['rearBB'][1] - L['headTT'][1]
    den = dx * (-sy) - dy * (-sx)
    m = (ex * (-sy) - ey * (-sx)) / den
    L['RSC'] = (L['headTT'][0] + dx * m, L['headTT'][1] + dy * m)
    L['hipTarget'] = (L['frontBB'][0] - 0.160, L['frontBB'][1] + 0.578)
    L['frontSit'] = (L['hipTarget'][0] - 0.012, L['hipTarget'][1] - 0.095)
    L['rearSit'] = (-0.585, 0.790)
    L['zTiming'] = 0.040; L['zDrive'] = 0.052; L['zCrank'] = 0.066; L['pedalOut'] = 0.060
    L['pitch'] = 0.0254; L['timingTeeth'] = 18; L['driveTeeth'] = 24; L['sprocketTeeth'] = 9
    L['frontSpokes'] = 36; L['rearSpokes'] = 44
    L['pedalTop'] = 0.016
    L['rTube'] = 0.0127; L['rDown'] = 0.0143; L['rHead'] = 0.0165
    return L


def on_axis(L, s):
    return (L['Q'][0] + L['axis'][0] * s, L['Q'][1] + L['axis'][1] * s)


def on_seat(L, bb, y):
    k = (y - bb[1]) / L['seatDir'][1]
    return (bb[0] + L['seatDir'][0] * k, y)


def ringR(pitch, teeth):
    return pitch / (2 * math.sin(math.pi / teeth))


# ─────────────────────────────────────────────────────────────────────────────
class Kit:
    """Holds created objects with tags: pivot (which animated node), mgroup (export material/atlas), smat (source look)."""

    def __init__(self, coll):
        self.coll = coll
        self.objs = []

    def add(self, mb, pivot, mgroup, smat, sharp=40, props=None):
        ob = mb.object(self.coll, sharp_angle=sharp)
        return self.tag(ob, pivot, mgroup, smat, props)

    def tag(self, ob, pivot, mgroup, smat, props=None):
        ob['pivot'] = pivot; ob['mgroup'] = mgroup; ob['smat'] = smat
        for k, v in (props or {}).items():
            ob[k] = v
        self.objs.append(ob)
        return ob


# ─────────────────────────────── helpers ──────────────────────────────────────
def P2(p, z=0.0):
    return V(p[0], p[1], z)


def plug(name, a, d, length, r_lug, r_tube, points=True, back=0.012, n=14, radial=28, pt_len=None, ref=V(0, 0, 1)):
    """Closed lug socket: a solid sleeve from a-d*back to a+d*length, spear points in the frame plane."""
    mb = MB(name)
    d = d.normalized()
    refv = ref - d * ref.dot(d)
    if refv.length < 1e-6:
        refv = V(0, 1, 0) - d * d.y
    N = refv.normalized(); Bv = N.cross(d).normalized()
    pl = pt_len if pt_len is not None else length * 0.55
    start = a - d * back
    rings = []
    for i in range(n + 1):
        t = i / n
        ring = []
        for j in range(radial):
            ang = TAU * j / radial
            spear = max(abs(math.sin(ang)), 0.0) ** 10 if points else 0.0     # points at +-B (in the frame plane)
            ext = (back + length + pl * spear) * t
            taper = 1.0 - sstep(0.55, 1.0, t)
            rr = r_tube + 0.00035 + (r_lug - r_tube - 0.00035) * taper
            ring.append(mb.vert(start + d * ext + N * (math.cos(ang) * rr) + Bv * (math.sin(ang) * rr)))
        rings.append(ring)
    for i in range(n):
        for j in range(radial):
            j1 = (j + 1) % radial
            mb.face([rings[i][j], rings[i + 1][j], rings[i + 1][j1], rings[i][j1]])
    c0 = mb.vert(start)
    c1 = mb.vert(start + d * (back + length))
    for j in range(radial):
        j1 = (j + 1) % radial
        mb.face([c0, rings[0][j], rings[0][j1]], smooth=False)
        mb.face([c1, rings[n][j1], rings[n][j]], smooth=False)
    return mb


def shell_lathe(name, center, axis, r, half, taper=0.0, radial=36, points=False, rp=None):
    """Closed cylindrical shell (BB shell / head sleeve) along axis, optional tapered spear ends."""
    mb = MB(name)
    ax = axis.normalized()
    refv = V(0, 0, 1) - ax * ax.z
    if refv.length < 1e-6:
        refv = V(0, 1, 0) - ax * ax.y
    N = refv.normalized(); Bv = N.cross(ax).normalized()
    n = 12
    rings = []
    for i in range(n + 1):
        t = i / n
        ring = []
        for j in range(radial):
            ang = TAU * j / radial
            end = abs(2 * t - 1)
            spear = (abs(math.sin(ang)) ** 10) if points else 0.0
            h = (2 * t - 1) * (half + (rp or 0.0) * spear)
            rr = r - taper * sstep(0.6, 1.0, end)
            ring.append(mb.vert(center + ax * h + N * (math.cos(ang) * rr) + Bv * (math.sin(ang) * rr)))
        rings.append(ring)
    for i in range(n):
        for j in range(radial):
            j1 = (j + 1) % radial
            mb.face([rings[i][j], rings[i + 1][j], rings[i + 1][j1], rings[i][j1]])
    c0 = mb.vert(center - ax * half); c1 = mb.vert(center + ax * half)
    for j in range(radial):
        j1 = (j + 1) % radial
        mb.face([c0, rings[0][j], rings[0][j1]], smooth=False)
        mb.face([c1, rings[n][j1], rings[n][j]], smooth=False)
    return mb


def cast(kit, name, core_mb, plug_mbs, pivot, mgroup, smat, fillet=0.0012, props=None):
    core = core_mb.object(kit.coll)
    others = [p.object(kit.coll) for p in plug_mbs]
    boolean_union(core, others, solver='EXACT')
    if fillet > 0:
        try:
            bevel_mod(core, width=fillet, segments=2, angle=35)
        except Exception as e:
            print('[tandem] fillet skipped on', name, e)
    import bmesh as _bm
    bm = _bm.new(); bm.from_mesh(core.data)
    _bm.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
    bm.to_mesh(core.data); bm.free()
    shade(core, 45)
    wn = core.modifiers.new('wn', 'WEIGHTED_NORMAL')
    wn.mode = 'FACE_AREA'
    wn.keep_sharp = True
    wn.weight = 60
    apply_mods(core)
    core.name = name
    props = dict(props or {}); props['smartuv'] = 1          # boolean result: no usable UVs
    return kit.tag(core, pivot, mgroup, smat, props)


def tube(kit, name, pts, r, pivot='frame', mgroup='enamel', smat='enamel', radial=24, oval=(1, 1), ref=V(0, 0, 1),
         cap0=False, cap1=False, props=None, spacing=0.02):
    mb = MB(name)
    pts = resample(pts, spacing) if len(pts) > 2 else pts
    sweep(mb, pts, r, radial=radial, oval=oval, ref=ref, cap0=cap0, cap1=cap1)
    length = sum((pts[i] - pts[i - 1]).length for i in range(1, len(pts)))
    rr = r(0.5) if callable(r) else r
    p = dict(props or {})
    p.setdefault('len', length); p.setdefault('rad', rr)
    if not cap0 and not cap1:
        p['keepuv'] = 1
    return kit.add(mb, pivot, mgroup, smat, sharp=60, props=p)


# ─────────────────────────────── the frame ────────────────────────────────────
def build_frame(kit, L):
    ax = lambda s: P2(on_axis(L, s))
    aDir = V(L['axis'][0], L['axis'][1])
    FB, RB = P2(L['frontBB']), P2(L['rearBB'])
    FSC, RSC = P2(L['FSC']), P2(L['RSC'])
    head_tt, head_dn = ax(L['sTop']), ax(L['sDown'])
    sDir = V(L['seatDir'][0], L['seatDir'][1])
    fst_top = P2(on_seat(L, L['frontBB'], L['fscY'] + 0.021))
    rst_top = P2(on_seat(L, L['rearBB'], L['RSC'][1] + 0.021))
    zD = 0.058
    RDs = [V(L['rearHub'][0], L['hubY'], s * zD) for s in (1, -1)]
    rT, rD, rH = L['rTube'], L['rDown'], L['rHead']
    lined = {'lining': 1.0}
    # drawn tubes (stop at the joint centres, inside the lugs)
    tube(kit, 'head_tube', [ax(L['sHeadBot'] + 0.002), ax(L['sHeadTop'])], rH, props={'lining': 1.0, 'wear': 0.35})
    tube(kit, 'top_tube_front', [head_tt, FSC], rT, props={'lining': 1.0, 'wear': 0.35})
    tube(kit, 'top_tube_rear', [FSC, RSC], rT, props={'lining': 1.0, 'wear': 0.30})
    tube(kit, 'down_tube', [head_dn, FB], rD, props={'lining': 1.0, 'wear': 0.30})
    tube(kit, 'seat_tube_front', [FB, fst_top], rT, props={'lining': 1.0, 'wear': 0.25})
    tube(kit, 'diagonal_tube', [FSC, RB], rT, props={'lining': 1.0, 'wear': 0.30})
    tube(kit, 'bottom_tube', [FB, RB], rT, props={'lining': 1.0, 'wear': 0.40})
    tube(kit, 'seat_tube_rear', [RB, rst_top], rT, props={'lining': 1.0, 'wear': 0.25})
    ss_top = lambda s: V(L['RSC'][0] - 0.004, L['RSC'][1] - 0.016, s * 0.021)
    for s, side in ((1, 'R'), (-1, 'L')):
        a, b = ss_top(s), V(L['rearHub'][0] + 0.004, L['hubY'] + 0.012, s * zD)
        tube(kit, 'seat_stay_' + side, [a, b], lambda t: 0.0086 - 0.0012 * t, radial=18, props={'lining': 1.0, 'wear': 0.30})
        ca, cb = V(L['rearBB'][0] - 0.004, L['bbY'], s * 0.026), V(L['rearHub'][0] + 0.010, L['hubY'] - 0.006, s * zD)
        mid = ca.lerp(cb, 0.5) + V(0, 0, s * 0.006)
        tube(kit, 'chain_stay_' + side, bezier2_pts(ca, mid, cb, 14), lambda t: 0.0096 - 0.0016 * t, radial=18, oval=(0.8, 1.0),
             props={'lining': 1.0, 'wear': 0.55 if s > 0 else 0.35})
    # cast lugs --------------------------------------------------------------
    rl = lambda r: r + 0.0024
    # head lugs
    cast(kit, 'lug_head_top', shell_lathe('hl_top', ax(L['sTop'] + 0.005), aDir, rl(rH), 0.027, taper=0.0021, points=True, rp=0.008),
         [plug('hl_tt', head_tt, FSC - head_tt, 0.030, rl(rT), rT)], 'frame', 'enamel', 'enamel', props={'wear': 0.32})
    cast(kit, 'lug_head_bottom', shell_lathe('hl_bot', ax(L['sHeadBot'] + 0.018), aDir, rl(rH), 0.019, taper=0.0021, points=True, rp=0.006),
         [plug('hl_dt', head_dn, FB - head_dn, 0.036, rl(rD), rD)], 'frame', 'enamel', 'enamel', props={'wear': 0.36})
    # seat clusters (with binder ears)
    def cluster(name, bb, sc, plugs):
        c = P2(on_seat(L, bb, sc.y + 0.000))
        core = shell_lathe(name + '_sl', c + sDir * 0.002, sDir, rl(rT), 0.026, taper=0.0021, points=True, rp=0.010)
        ear = MB(name + '_ear')
        back = V(-L['seatDir'][1], L['seatDir'][0]) * -1.0          # behind the seat tube, in plane
        e0 = c + sDir * 0.012 + back * 0.012
        sweep(ear, [e0 + V(0, 0, -0.011), e0 + V(0, 0, 0.011)], 0.0068, radial=16, ref=V(0, 1, 0), cap0=True, cap1=True)
        return cast(kit, name, core, plugs + [ear], 'frame', 'enamel', 'enamel', props={'wear': 0.32})
    cluster('lug_seat_front', L['frontBB'], FSC, [
        plug('sf_tf', FSC, head_tt - FSC, 0.030, rl(rT), rT),
        plug('sf_tr', FSC, RSC - FSC, 0.030, rl(rT), rT),
        plug('sf_dg', FSC, RB - FSC, 0.034, rl(rT), rT)])
    cluster('lug_seat_rear', L['rearBB'], RSC, [
        plug('sr_tt', RSC, FSC - RSC, 0.030, rl(rT), rT),
        plug('sr_ssR', ss_top(1), RDs[0] - ss_top(1), 0.022, 0.0104, 0.0086, back=0.006),
        plug('sr_ssL', ss_top(-1), RDs[1] - ss_top(-1), 0.022, 0.0104, 0.0086, back=0.006)])
    # bottom brackets
    def bracket(name, bb, plugs):
        core = shell_lathe(name + '_sh', bb, V(0, 0, 1), 0.0215, 0.036, taper=0.0, radial=40)
        return cast(kit, name, core, plugs, 'frame', 'enamel', 'enamel', props={'wear': 0.5})
    bracket('bracket_front', FB, [
        plug('bf_dt', FB, head_dn - FB, 0.030, rl(rD), rD, back=0.0),
        plug('bf_st', FB, fst_top - FB, 0.030, rl(rT), rT, back=0.0),
        plug('bf_bt', FB, RB - FB, 0.030, rl(rT), rT, back=0.0)])
    bracket('bracket_rear', RB, [
        plug('br_bt', RB, FB - RB, 0.030, rl(rT), rT, back=0.0),
        plug('br_dg', RB, FSC - RB, 0.030, rl(rT), rT, back=0.0),
        plug('br_st', RB, rst_top - RB, 0.030, rl(rT), rT, back=0.0),
        plug('br_csR', V(L['rearBB'][0] - 0.004, L['bbY'], 0.026), RDs[0] - V(L['rearBB'][0], L['bbY'], 0.026), 0.028, 0.0118, 0.0096, back=0.0),
        plug('br_csL', V(L['rearBB'][0] - 0.004, L['bbY'], -0.026), RDs[1] - V(L['rearBB'][0], L['bbY'], -0.026), 0.028, 0.0118, 0.0096, back=0.0)])
    # rear dropouts (forged ends: plate + two sockets)
    for s, side in ((1, 'R'), (-1, 'L')):
        hub = V(L['rearHub'][0], L['hubY'], s * zD)
        # plate outline in the bike plane (x, y) around the axle, with the open slot facing forward-down
        out = []
        for k in range(28):
            a = TAU * k / 28
            rx, ry = 0.024, 0.017
            out.append((math.cos(a) * rx + 0.012, math.sin(a) * ry + 0.004))
        slot = []
        for k in range(12):
            a = TAU * k / 12
            slot.append((math.cos(a) * 0.0055, math.sin(a) * 0.0055))
        pm = plate('drop_' + side, [out, slot], 0.0055, bevel=0.0009,
                   xf=lambda p, hub=hub: V(hub.x + p.x, hub.y + p.y, hub.z + p.z))
        ss_d = (ss_top(s) - hub).normalized()
        cs_a = V(L['rearBB'][0] - 0.004, L['bbY'], s * 0.026)
        cs_d = (cs_a - hub).normalized()
        cast(kit, 'dropout_' + side, pm, [
            plug('do_ss' + side, hub + ss_d * 0.004, ss_d, 0.030, 0.0100, 0.0082, back=0.004),
            plug('do_cs' + side, hub + cs_d * 0.004, cs_d, 0.030, 0.0104, 0.0082, back=0.004)],
            'frame', 'enamel', 'enamel', fillet=0.0008, props={'wear': 0.6})


# ─────────────────────────────── fork & steering ──────────────────────────────
def build_steering(kit, L):
    ax = lambda s: P2(on_axis(L, s))
    aDir = V(L['axis'][0], L['axis'][1])
    FH = V(L['frontHub'][0], L['hubY'])
    crown = ax(L['sCrown'])
    # cast crown (nickel): oblong body + steerer socket + two blade sockets
    body = MB('crown_body')
    fwd = V(L['axisN'][0], L['axisN'][1])
    pts = [crown + V(0, 0, -0.056), crown + V(0, 0, 0.056)]
    sweep(body, pts, lambda t: 0.0142 * (1 - 0.18 * (abs(2 * t - 1) ** 6)), radial=28, oval=(1.0, 0.72),
          ref=V(0, 1, 0), cap0=True, cap1=True)
    blade_tops = []
    socks = [plug('cr_st', crown, aDir, 0.022, 0.0152, 0.0124, back=0.0, points=False)]
    for s in (1, -1):
        top = crown + V(0, 0, s * 0.043) - aDir * 0.006
        blade_tops.append(top)
        socks.append(plug('cr_bl%d' % s, top, -aDir, 0.024, 0.0138, 0.0116, back=0.0, pt_len=0.010, ref=V(0, 0, 1)))
    cast(kit, 'fork_crown', body, socks, 'steer', 'metal', 'nickel', fillet=0.0015, props={'wear': 0.4})
    # blades: oval, tapered, raked (period hockey-stick curve)
    for s, side in ((1, 'R'), (-1, 'L')):
        p0 = blade_tops[0 if s > 0 else 1] - aDir * 0.012
        p1 = ax(0.20) + V(0, 0, s * 0.046)
        p2 = V(FH.x - 0.012, FH.y + 0.12, s * 0.049)
        p3 = V(FH.x, FH.y + 0.006, s * 0.050)
        tube(kit, 'fork_blade_' + side, bezier3_pts(p0, p1, p2, p3, 40), lambda t: 0.0116 - 0.0040 * t, pivot='steer',
             radial=20, oval=(0.72, 1.0), props={'lining': 1.0, 'wear': 0.3}, spacing=0.012)
        # forged fork end
        hub = V(FH.x, FH.y, s * 0.050)
        out = [(math.cos(TAU * k / 24) * 0.015 + 0.002, math.sin(TAU * k / 24) * 0.013 + 0.006) for k in range(24)]
        hole = [(math.cos(TAU * k / 10) * 0.0048, math.sin(TAU * k / 10) * 0.0048) for k in range(10)]
        pm = plate('fe_' + side, [out, hole], 0.0050, bevel=0.0008, xf=lambda p, hub=hub: V(hub.x + p.x, hub.y + p.y, hub.z + p.z))
        bd = (p2 - p3).normalized()
        cast(kit, 'fork_end_' + side, pm, [plug('fe_s' + side, hub + bd * 0.004, bd, 0.022, 0.0090, 0.0077, back=0.002)],
             'steer', 'enamel', 'enamel', fillet=0.0007, props={'wear': 0.6})
    # steerer stub (visible between crown and lower cup), lower race, locknut, quill, stem, clamp
    tube(kit, 'steerer', [ax(L['sCrown'] + 0.010), ax(L['sHeadBot'] + 0.004)], 0.0125, pivot='steer', mgroup='metal', smat='nickel', cap0=False)
    mb = MB('locknut')
    sweep(mb, [ax(L['sHeadTop'] + 0.009), ax(L['sHeadTop'] + 0.019)], 0.0178, radial=6, ref=V(0, 0, 1), cap0=True, cap1=True, smooth=False)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=30)
    tube(kit, 'quill', [ax(L['sHeadTop'] + 0.012), ax(L['sQuill'])], 0.0112, pivot='steer', mgroup='metal', smat='nickel', radial=20)
    qtop = ax(L['sQuill'])
    K = qtop + V(0.046, 0.004)
    tube(kit, 'stem_ext', catmull_pts([ax(L['sQuill'] - 0.030), qtop + V(0.004, 0.006), K + V(-0.012, 0.001), K], 6),
         0.0108, pivot='steer', mgroup='metal', smat='nickel', radial=20, cap0=True, spacing=0.006)
    mb = MB('quill_bolt')
    lathe(mb, [(0.0, 0.0), (0.0068, 0.0), (0.0068, 0.004), (0.0060, 0.0065), (0.0, 0.0070)], 6, center=qtop + aDir * 0.001, axis=aDir, smooth=False)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=30)
    mb = MB('bar_clamp')
    sweep(mb, [K + V(0, 0, -0.019), K + V(0, 0, 0.019)], 0.0145, radial=24, ref=V(0, 1, 0), cap0=True, cap1=True)
    sweep(mb, [K + V(0.006, -0.018, -0.006), K + V(0.006, -0.018, 0.006)], 0.0046, radial=6, ref=V(0, 1, 0), cap0=True, cap1=True, smooth=False)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=40)
    # handlebar: raised, swept-back roadster bar
    inR = K + V(0.004, 0.018, 0.186); outR = K + V(-0.078, 0.021, 0.272)
    mir = lambda p: V(p.x, p.y, -p.z)
    ctrl = [mir(outR), mir(inR), K + V(0.013, 0.012, -0.13), K + V(0.012, 0.004, -0.07), K,
            K + V(0.012, 0.004, 0.07), K + V(0.013, 0.012, 0.13), inR, outR]
    tube(kit, 'handlebar', catmull_pts(ctrl, 10), 0.0111, pivot='steer', mgroup='metal', smat='nickel', radial=20, spacing=0.008)
    grips = {}
    for s, side in ((1, 'R'), (-1, 'L')):
        a = inR if s > 0 else mir(inR); b = outR if s > 0 else mir(outR)
        grips[side] = grip(kit, 'grip_front_' + side, a, b, 'steer')
    # bell ("Daisy Bell"): pressed dome on a post clamp, thumb lever
    bp = K + V(0.012, 0.006, 0.098)
    mb = MB('bell')
    lathe(mb, [(0.0, 0.0215), (0.0045, 0.0212), (0.010, 0.0200), (0.0165, 0.0175), (0.0215, 0.0135), (0.0252, 0.0082), (0.0276, 0.0030),
               (0.0284, 0.0006), (0.0282, -0.0004), (0.0268, 0.0000), (0.0256, 0.0040), (0.0200, 0.0110), (0.0100, 0.0150), (0.0, 0.0158)],
          48, center=bp + V(0, 0.012, 0), axis='y')
    sweep(mb, [bp + V(0, -0.004, 0), bp + V(0, 0.030, 0)], 0.0034, radial=10, ref=V(0, 0, 1), cap1=True)
    lathe(mb, [(0.0, -0.001), (0.0085, -0.001), (0.0085, 0.0045), (0.0, 0.0045)], 20, center=bp + V(0, 0.030, 0), axis='y')
    sweep(mb, catmull_pts([bp + V(0, 0.020, 0), bp + V(-0.022, 0.024, 0.010), bp + V(-0.036, 0.020, 0.024)], 8), 0.0022, radial=8, ref=V(0, 1, 0), cap1=True)
    lathe(mb, [(0.0, -0.002), (0.0055, -0.0015), (0.0060, 0.0005), (0.0045, 0.0022), (0.0, 0.0026)], 16, center=bp + V(-0.036, 0.020, 0.024), axis='y')
    # clamp band around the bar
    sweep(mb, [bp + V(-0.0, -0.006, -0.008), bp + V(0, -0.006, 0.008)], 0.0132, radial=18, ref=V(0, 1, 0), cap0=True, cap1=True)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=35)
    # spoon brake: shoe on the tyre crown, rod down the head with return spring, lever under the right grip
    dirS = V(-0.33, 0.944).normalized()
    a0 = math.atan2(dirS.y, dirS.x)
    arc = [V(FH.x + math.cos(a0 + (i / 11 - 0.5) * 0.26) * (L['R'] + 0.0045), FH.y + math.sin(a0 + (i / 11 - 0.5) * 0.26) * (L['R'] + 0.0045), 0)
           for i in range(12)]
    mb = MB('spoon')
    sweep(mb, arc, 0.017, radial=12, oval=(1.0, 0.14), ref=V(0, 0, 1), cap0=True, cap1=True)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=35)
    shoeC = FH + dirS * (L['R'] + 0.0045)
    rod0 = shoeC + dirS * 0.006
    rod1 = rod0 + aDir * ((K.y - 0.012 - rod0.y) / aDir.y)
    mb = MB('brake_rod')
    sweep(mb, [rod0, rod1], 0.0031, radial=10, cap0=True, cap1=True)
    sweep(mb, helix_pts(rod0 + aDir * 0.075, 0.0068, 0.07, 9, axis=aDir, n=200), 0.0012, radial=6)
    for k in (0.040, 0.110):                     # spring seats (collars on the rod)
        sweep(mb, [rod0 + aDir * (k - 0.003), rod0 + aDir * (k + 0.003)], 0.0058, radial=12, cap0=True, cap1=True)
    eye = rod0 + aDir * 0.028                     # guide eye bolted to the crown's front
    cf = ax(L['sCrown']) + V(L['axisN'][0], L['axisN'][1]) * 0.012
    sweep(mb, [cf, eye], 0.0030, radial=8, cap0=True)
    lathe(mb, [(0.0040, -0.0035), (0.0062, -0.0035), (0.0062, 0.0035), (0.0040, 0.0035)], 16, center=eye, axis=aDir, closed=True)
    lever = catmull_pts([rod1, rod1 + V(-0.004, 0.006, 0.05), inR + V(0.018, -0.022, 0.0), inR.lerp(outR, 0.55) + V(0.014, -0.025, 0.004)], 8)
    sweep(mb, lever, 0.0036, radial=10, oval=(0.6, 1.0), cap1=True)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=35)
    # front axle nuts + axle ends
    mb = MB('front_axle_nuts')
    for s in (1, -1):
        sweep(mb, [V(FH.x, FH.y, s * 0.054), V(FH.x, FH.y, s * 0.062)], 0.0084, radial=6, ref=V(0, 1, 0), cap0=True, cap1=True, smooth=False)
        sweep(mb, [V(FH.x, FH.y, s * 0.046), V(FH.x, FH.y, s * 0.068)], 0.0042, radial=10, ref=V(0, 1, 0), cap1=True)
    kit.add(mb, 'steer', 'metal', 'nickel', sharp=30)
    return {'K': K, 'grips': grips, 'crown': crown}


def grip(kit, name, a, b, pivot):
    """Cork handle on the bar end (a inner -> b outer) with a vulcanite tip and a nickel ferrule."""
    d = (b - a).normalized()
    mb = MB(name + '_cork')
    n = 16
    prof = []
    for i in range(n + 1):
        t = i / n
        prof.append(a.lerp(b, t))
    r = lambda t: 0.0150 + 0.0012 * math.sin(math.pi * t) - 0.0007 * sstep(0.0, 0.08, 0.08 - t)
    sweep(mb, prof, r, radial=24, cap0=True)
    kit.add(mb, pivot, 'grips', 'cork', sharp=70, props={'len': (b - a).length})
    mb = MB(name + '_tip')
    tip = [b - d * 0.001 + d * (0.014 * i / 8) for i in range(9)]
    sweep(mb, tip, lambda t: 0.0156 * math.sqrt(max(0.02, 1 - (max(0.0, t - 0.35) / 0.65) ** 2)), radial=24, cap1=True)
    kit.add(mb, pivot, 'grips', 'vulcanite', sharp=70)
    mb = MB(name + '_ferrule')
    sweep(mb, [a - d * 0.004, a + d * 0.004], 0.0157, radial=24, cap0=True)
    kit.add(mb, pivot, 'metal', 'nickel', sharp=70)
    return {'center': a.lerp(b, 0.5), 'axis': d, 'inner': a, 'outer': b}


# ─────────────────────────────── wheels ───────────────────────────────────────
RIM_PROFILE = [(0.2770, -0.0100), (0.2790, -0.0128), (0.2950, -0.0131), (0.2992, -0.0122), (0.2987, -0.0090), (0.2928, -0.0072),
               (0.2917, 0.0), (0.2928, 0.0072), (0.2987, 0.0090), (0.2992, 0.0122), (0.2950, 0.0131), (0.2790, 0.0128),
               (0.2770, 0.0100), (0.2765, 0.0), (0.2770, -0.0100)]


def tyre_profile(L):
    """Gum pneumatic, 1 5/8": round section with a finely ribbed crown (ribs are geometry, a period moulding)."""
    tc = L['R'] - L['tyreSec']
    out = []
    n = 72
    for i in range(n + 1):
        a = math.pi + TAU * i / n                     # start at the rim (innermost), go round via the -z side
        r = L['tyreSec']
        crown = math.cos(a - 2 * math.pi)             # 1 at the outermost point
        if crown > 0.62:
            rib = 0.00045 * (0.5 + 0.5 * math.cos((a - 2 * math.pi) * 16 * 2))
            r += rib * sstep(0.62, 0.72, crown)
        out.append((tc + math.cos(a) * r, math.sin(a) * r * 1.04))
    return out


def build_wheel(kit, L, name, spokes, rear, pivot, sprocket_rot=0.0):
    coll = kit.coll
    # rim (laminated wood)
    mb = MB(name + '_rim')
    lathe(mb, RIM_PROFILE, 192, axis='z')
    kit.add(mb, pivot, 'wood', 'wood', sharp=50)
    # tyre
    mb = MB(name + '_tyre')
    lathe(mb, tyre_profile(L), 192, axis='z')
    kit.add(mb, pivot, 'rubber', 'gum', sharp=80)
    # hub: turned barrel, flanges, cones, locknuts
    flZ = 0.031 if rear else 0.029
    hl = 0.056 if rear else 0.050
    prof = [(0.0001, -hl), (0.0046, -hl), (0.0046, -hl + 0.004), (0.0091, -hl + 0.0045), (0.0091, -hl + 0.0105), (0.0079, -hl + 0.0125),
            (0.0110, -flZ - 0.012), (0.0133, -flZ - 0.004), (0.0270, -flZ - 0.0022), (0.0273, -flZ + 0.0000), (0.0270, -flZ + 0.0020),
            (0.0140, -flZ + 0.0035), (0.0124, -0.013), (0.0117, 0.0), (0.0124, 0.013), (0.0140, flZ - 0.0035), (0.0270, flZ - 0.0020),
            (0.0273, flZ), (0.0270, flZ + 0.0022), (0.0133, flZ + 0.004), (0.0110, flZ + 0.012), (0.0079, hl - 0.0125),
            (0.0091, hl - 0.0105), (0.0091, hl - 0.0045), (0.0046, hl - 0.004), (0.0046, hl), (0.0001, hl)]
    mb = MB(name + '_hub')
    lathe(mb, prof, 48, axis='z')
    # oil cap on the barrel
    sweep(mb, [V(0, 0.0112, 0), V(0, 0.0182, 0)], 0.0029, radial=12, ref=V(0, 0, 1), cap1=True)
    lathe(mb, [(0.0, 0.0), (0.0040, 0.0), (0.0040, 0.0020), (0.0, 0.0028)], 12, center=V(0, 0.0182, 0), axis='y')
    # valve (stem + knurled cap) at wheel angle 0
    sweep(mb, [V(0.2768, 0, 0), V(0.2635, 0, 0)], 0.0030, radial=12, ref=V(0, 0, 1))
    lathe(mb, [(0.0, 0.0), (0.0041, 0.0), (0.0041, 0.0085), (0.0034, 0.0098), (0.0, 0.0100)], 14, center=V(0.2640, 0, 0), axis=V(-1, 0, 0))
    if rear:
        # 9T fixed sprocket + lockring on the drive side
        loop = ring_outline(L['sprocketTeeth'], L['pitch'])
        bore = [(math.cos(TAU * k / 16) * 0.0125, math.sin(TAU * k / 16) * 0.0125) for k in range(16)]
        cr, sr = math.cos(sprocket_rot), math.sin(sprocket_rot)
        pm = plate(name + '_sprocket', [loop, bore], 0.0034, bevel=0.0005,
                   xf=lambda p: V(p.x * cr - p.y * sr, p.x * sr + p.y * cr, p.z + L['zDrive']))
        merge_into(mb, pm)
        sweep(mb, [V(0, 0, 0.034), V(0, 0, L['zDrive'] - 0.001)], 0.0128, radial=24, ref=V(0, 1, 0))
        lathe(mb, [(0.0126, L['zDrive'] + 0.0018), (0.0165, L['zDrive'] + 0.0018), (0.0165, L['zDrive'] + 0.0052), (0.0126, L['zDrive'] + 0.0052)], 8,
              axis='z', smooth=False, closed=True)
    kit.add(mb, pivot, 'metal', 'nickel', sharp=35)
    # spokes: tangent-laced, cross three, J-bend heads through the flanges; nipples at the rim
    hubR, rimR, cross = 0.0215, 0.2785, 3
    smb = MB(name + '_spokes')
    nmb = MB(name + '_nipples')
    trail = []
    zAx = V(0, 0, 1)
    for i in range(spokes):
        side = i % 2
        k = i // 2
        hubA = (2 * k + side) * TAU / spokes
        dirn = 1 if k % 2 == 0 else -1
        rimA = hubA + dirn * cross * 2 * TAU / spokes
        zs = flZ if side == 0 else -flZ
        a = V(hubR * math.cos(hubA), hubR * math.sin(hubA), zs)
        b = V(rimR * math.cos(rimA), rimR * math.sin(rimA), 0.0015 if side == 0 else -0.0015)
        d = (b - a).normalized()
        # the head sits on the far face of the flange, the elbow bends through the hole
        inward = V(0, 0, -1 if side == 0 else 1)
        head = a + inward * 0.0045 * -1.0
        elbow = a + d * 0.004
        pts = [a + V(0, 0, 0.0035 if side == 0 else -0.0035), a, elbow] + [elbow.lerp(b, t / 6) for t in range(1, 7)]
        verts0 = len(smb.bm.verts)
        sweep(smb, pts, 0.00100, radial=6, ref=zAx, cap0=False, cap1=False)
        # trail flag per vertex: which side of the spoke trails a forward (clockwise) roll
        vel = V(d.y, -d.x, 0)          # velocity dir at the spoke for rotation.z = -theta (clockwise from +Z)
        bm = smb.bm
        bm.verts.ensure_lookup_table()
        for vi in range(verts0, len(bm.verts)):
            v = bm.verts[vi]
            pb = Vector((v.co.x, v.co.z, -v.co.y))     # back to the bike frame
            # nearest point on the spoke line
            t = (pb - a).dot(d)
            c = a + d * max(0.0, t)
            off = pb - c
            trail.append(1.0 if off.dot(vel) < 0 else 0.0)
        # head (dome) on the flange face
        lathe(smb, [(0.0, 0.0), (0.0019, 0.0), (0.0017, 0.0012), (0.0, 0.0016)], 8,
              center=a + V(0, 0, 0.0036 if side == 0 else -0.0036), axis=V(0, 0, 1 if side == 0 else -1))
        while len(trail) < len(smb.bm.verts):
            trail.append(0.0)
        # nipple: turned hex-ish body seated on the rim bed
        lathe(nmb, [(0.0, 0.0), (0.0022, 0.0), (0.0022, 0.0055), (0.0028, 0.0060), (0.0028, 0.0105), (0.0, 0.0108)], 8,
              center=b - d * 0.0118, axis=d, smooth=False)
    ob = kit.add(smb, pivot, 'spokes', 'spoke', sharp=80)
    attr = ob.data.attributes.new('_TRAIL', 'FLOAT', 'POINT')
    for vi, val in enumerate(trail[:len(ob.data.vertices)]):
        attr.data[vi].value = val
    kit.add(nmb, pivot, 'metal', 'nickel', sharp=35)


def ring_outline(teeth, pitch, tip=0.0058, root=0.0068):
    r = ringR(pitch, teeth)
    rTip, rRoot = r + tip, r - root
    M = teeth * 18
    pts = []
    for i in range(M):
        a = TAU * i / M
        f = ((a * teeth / TAU) % 1 + 1) % 1
        d = min(f, 1 - f)
        h = 1 - sstep(0.13, 0.34, d)
        gap = 1 - min(1.0, (0.5 - d) / 0.16) ** 2
        rr = rRoot + (rTip - rRoot) * h - 0.0012 * max(0.0, gap) * (1 - h)
        pts.append((rr * math.cos(a), rr * math.sin(a)))
    return pts


def daisy_holes(teeth, pitch, petals, rIn, band=0.013, root=0.0068):
    rRoot = ringR(pitch, teeth) - root
    rOut = rRoot - band
    rMid = (rIn + rOut) / 2
    W = 0.36 * (TAU * rMid / petals)
    holes = []
    for k in range(petals):
        a0 = TAU * (k + 0.5) / petals
        ca, sa = math.cos(a0), math.sin(a0)
        side = []
        n = 18
        for i in range(n + 1):
            u = i / n
            rad = rIn + u * (rOut - rIn)
            hw = W * (math.sin(math.pi * min(1.0, u * 1.04)) ** 0.75) * (0.55 + 0.45 * u)
            side.append((rad, hw))
        outline = side + [(rad, -hw) for rad, hw in reversed(side[1:-1])]
        holes.append([(rad * ca - lat * sa, rad * sa + lat * ca) for rad, lat in outline])
    return holes


# ─────────────────────────────── cranksets, pedals, chain ─────────────────────
def crank_outline(len_, r0=0.0178, r1=0.0124):
    pts = []
    for k in range(17):                       # boss arc (bottom half)
        a = math.pi + math.pi * k / 16
        pts.append((math.cos(a) * r0, math.sin(a) * r0))
    for k in range(17):                       # eye arc (top half)
        a = math.pi * k / 16
        pts.append((math.cos(a) * r1, len_ + math.sin(a) * r1))
    return pts


def build_crankset(kit, L, name, pivot, rings):
    # spindle (axle) + cups are turned
    mb = MB(name + '_spindle')
    lathe(mb, [(0.0, -0.074), (0.0086, -0.074), (0.0086, 0.074), (0.0, 0.074)], 20, axis='z')
    kit.add(mb, pivot, 'metal', 'nickel', sharp=40)
    for s, side in ((1, 'R'), (-1, 'L')):
        z = s * L['zCrank']
        pm = plate(name + '_arm_' + side, [crank_outline(L['crank'])], 0.0090, bevel=0.0014, bevel_res=3,
                   xf=lambda p, s=s, z=z: V(p.x * s, p.y * s, p.z + z))
        # cotter pin (through the boss, perpendicular to the arm), nut and washer
        cp = V(0, 0, z)
        sweep(pm, [cp + V(-0.021, 0.0, 0), cp + V(0.024, 0.0, 0)], 0.0034, radial=10, ref=V(0, 1, 0), cap0=True, cap1=True)
        sweep(pm, [cp + V(0.017, 0, 0), cp + V(0.023, 0, 0)], 0.0058, radial=6, ref=V(0, 1, 0), cap0=True, cap1=True, smooth=False)
        # pedal eye boss
        eye = V(0, s * L['crank'], z)
        sweep(pm, [eye + V(0, 0, -s * 0.004), eye + V(0, 0, s * 0.011)], 0.0082, radial=16, ref=V(0, 1, 0), cap1=True)
        kit.add(pm, pivot, 'metal', 'nickel', sharp=40)
    for rg in rings:
        loops = [ring_outline(rg['teeth'], L['pitch'])] + daisy_holes(rg['teeth'], L['pitch'], rg['petals'], rg['rIn'])
        rot = rg['rot']
        pm = plate(name + '_ring_%d' % rg['teeth'], loops, 0.0034, bevel=0.0006,
                   xf=lambda p, rot=rot, z=rg['z']: V(p.x * math.cos(rot) - p.y * math.sin(rot), p.x * math.sin(rot) + p.y * math.cos(rot), p.z + z))
        # hub boss that carries the ring on the spindle
        sweep(pm, [V(0, 0, rg['z'] - 0.004), V(0, 0, L['zCrank'] - 0.005)], 0.0205, radial=28, ref=V(0, 1, 0), cap0=True)
        kit.add(pm, pivot, 'metal', 'nickel', sharp=40)


def build_pedal(kit, name, pivot, side):
    """Rat-trap pedal, pedal-local: X fwd, Y up (serration tips +0.016), Z lateral; side +1 = right (spindle at -Z)."""
    mb = MB(name + '_barrel')
    lathe(mb, [(0.0, -0.050), (0.0098, -0.050), (0.0106, -0.047), (0.0106, 0.047), (0.0098, 0.050), (0.0, 0.050)], 18, axis='z')
    # dust cap (outboard) + spindle stub (inboard) + lock nut
    zc = side * 0.0515
    lathe(mb, [(0.0, 0.0), (0.0094, 0.0), (0.0090, 0.0025), (0.0070, 0.0048), (0.0, 0.0056)], 16, center=V(0, 0, zc), axis=V(0, 0, side))
    sweep(mb, [V(0, 0, -side * 0.049), V(0, 0, -side * 0.064)], 0.0062, radial=12, ref=V(0, 1, 0), cap1=True)
    sweep(mb, [V(0, 0, -side * 0.050), V(0, 0, -side * 0.056)], 0.0082, radial=6, ref=V(0, 1, 0), cap0=True, cap1=True, smooth=False)
    kit.add(mb, pivot, 'metal', 'nickel', sharp=40)
    # serrated cage plates (front/back) and end plates
    zl, hh, tooth, nT = 0.052, 0.0115, 0.0042, 12
    out = [(-zl, -hh)]
    for i in range(nT):
        z0 = -zl + (i / nT) * 2 * zl; z1 = -zl + ((i + 0.5) / nT) * 2 * zl
        out += [(z0, -hh), (z1, -hh - tooth)]
    out += [(zl, -hh), (zl, hh)]
    for i in range(nT - 1, -1, -1):
        z0 = -zl + ((i + 1) / nT) * 2 * zl; z1 = -zl + ((i + 0.5) / nT) * 2 * zl
        out += [(z0, hh), (z1, hh + tooth)]
    out += [(-zl, hh)]
    clean = []
    for p in out:
        if not clean or (abs(p[0] - clean[-1][0]) > 1e-7 or abs(p[1] - clean[-1][1]) > 1e-7):
            clean.append(p)
    if abs(clean[0][0] - clean[-1][0]) < 1e-7 and abs(clean[0][1] - clean[-1][1]) < 1e-7:
        clean.pop()
    for fx in (0.036, -0.036):
        pm = plate(name + '_cage%+d' % int(fx * 1000), [clean], 0.0026, bevel=0.0004,
                   xf=lambda p, fx=fx: V(fx + p.z, p.y, p.x))
        kit.add(pm, pivot, 'metal', 'nickel', sharp=40)
    for ez in (0.050, -0.050):
        o = [(-0.039, -0.0105), (0.039, -0.0105), (0.039, 0.0105), (-0.039, 0.0105)]
        rr = [(math.cos(TAU * k / 12) * 0.0068, math.sin(TAU * k / 12) * 0.0068) for k in range(12)]
        pm = plate(name + '_end%+d' % int(ez * 1000), [o, rr], 0.0032, bevel=0.0006, xf=lambda p, ez=ez: V(p.x, p.y, ez + p.z))
        kit.add(pm, pivot, 'metal', 'nickel', sharp=40)


def build_chain_link(kit, L):
    """One pitch of 1" block chain in link space (x along, y across, z lateral), centred on the block."""
    parts = []
    # block: figure-of-eight profile (two rivet bosses joined by a waisted web)
    blk = []
    rb, cx, hw = 0.0044, 0.0064, 0.0034
    for k in range(13):                                   # right boss, -90..90 deg
        a = -math.pi / 2 + math.pi * k / 12
        blk.append((cx + math.cos(a) * rb, math.sin(a) * rb))
    for k in range(1, 8):                                 # top waist, right -> left
        u = k / 8
        x = cx * (1 - 2 * u)
        blk.append((x, rb - (rb - hw) * math.sin(math.pi * u)))
    for k in range(13):                                   # left boss, 90..270 deg
        a = math.pi / 2 + math.pi * k / 12
        blk.append((-cx + math.cos(a) * rb, math.sin(a) * rb))
    for k in range(1, 8):                                 # bottom waist, left -> right
        u = k / 8
        x = -cx * (1 - 2 * u)
        blk.append((x, -(rb - (rb - hw) * math.sin(math.pi * u))))
    pm = plate('chain_block', [blk], 0.0060, bevel=0.0006, xf=lambda p: V(p.x, p.y, p.z))
    main = pm
    for s in (1, -1):
        st = []
        for k in range(24):
            a = TAU * k / 24
            cx = 0.0190 if math.cos(a) >= 0 else 0.0064
            st.append((cx + math.cos(a) * 0.0046, math.sin(a) * 0.0046))
        p2 = plate('chain_plate', [st], 0.0011, bevel=0.0003, xf=lambda p, s=s: V(p.x, p.y, p.z + s * 0.00395))
        merge_into(main, p2)
        for xr in (0.0064, 0.0190):
            lathe(main, [(0.0, 0.0), (0.0017, 0.0), (0.0015, 0.0007), (0.0, 0.0009)], 10, center=V(xr, 0, s * 0.0045), axis=V(0, 0, s))
    ob = kit.add(main, 'chain', 'chain', 'chainsteel', sharp=45)
    return ob


# ─────────────────────────────── saddle ───────────────────────────────────────
def spline1D(vals, s):
    n = len(vals) - 1
    f = min(n - 1e-9, max(0.0, s * n)); i = int(f); u = f - i
    p0 = vals[max(0, i - 1)]; p1 = vals[i]; p2 = vals[min(n, i + 1)]; p3 = vals[min(n, i + 2)]
    return 0.5 * ((2 * p1) + (-p0 + p2) * u + (2 * p0 - 5 * p1 + 4 * p2 - p3) * u * u + (-p0 + 3 * p1 - 3 * p2 + p3) * u * u * u)


def build_saddle(kit, L, name, sit, pivot='frame'):
    """Sprung leather saddle (Brooks pattern). Saddle-local: origin at the sit point on top, +X nose."""
    X0, X1 = -0.078, 0.198
    Wd = [0.086, 0.097, 0.094, 0.078, 0.058, 0.042, 0.031, 0.024]
    TOP = [0.010, 0.003, 0.000, -0.002, -0.003, -0.002, 0.001, 0.007]
    CR = [0.010, 0.012, 0.013, 0.015, 0.016, 0.016, 0.014, 0.011]
    SK = [0.034, 0.035, 0.033, 0.028, 0.022, 0.016, 0.011, 0.008]
    TH = 0.0045
    nS, nQ = 40, 36
    s_sit = (0 - X0) / (X1 - X0)
    y0 = spline1D(TOP, s_sit) + spline1D(CR, s_sit)
    at = lambda p: V(sit.x + p.x, sit.y + p.y, sit.z + p.z)

    def section(s, grow=0.0):
        w = spline1D(Wd, s) + grow; top = spline1D(TOP, s); cr = spline1D(CR, s); sk = spline1D(SK, s) + grow
        ctrl = [V(0, top - sk, -w - 0.004), V(0, top - sk * 0.55, -w - 0.0015), V(0, top - 0.004, -w + 0.0008), V(0, top + cr * 0.62, -w * 0.7),
                V(0, top + cr, 0), V(0, top + cr * 0.62, w * 0.7), V(0, top - 0.004, w - 0.0008), V(0, top - sk * 0.55, w + 0.0015), V(0, top - sk, w + 0.004)]
        pts = catmull_pts(ctrl, 8)
        # resample to exactly nQ points
        Ls = [0.0]
        for i in range(1, len(pts)):
            Ls.append(Ls[-1] + (pts[i] - pts[i - 1]).length)
        out = []
        k = 0
        for i in range(nQ):
            tt = Ls[-1] * i / (nQ - 1)
            while k < len(Ls) - 2 and Ls[k + 1] < tt:
                k += 1
            seg = max(1e-9, Ls[k + 1] - Ls[k])
            out.append(pts[k].lerp(pts[k + 1], (tt - Ls[k]) / seg))
        return out, w, top, sk

    mb = MB(name + '_leather')
    rings = []
    lth = []
    for i in range(nS + 1):
        s = i / nS
        x = X0 + s * (X1 - X0)
        pts, w, top, sk = section(s)
        outer, inner = [], []
        for j in range(nQ):
            p = pts[j]
            pa, pb = pts[max(0, j - 1)], pts[min(nQ - 1, j + 1)]
            tz, ty = pb.z - pa.z, pb.y - pa.y
            tl = math.hypot(tz, ty) or 1.0
            nzz, nyy = -ty / tl, tz / tl
            outer.append(V(x, p.y - y0, p.z))
            inner.append(V(x, p.y - y0 - nyy * TH, p.z - nzz * TH))
        loop = outer + list(reversed(inner))
        rings.append([mb.vert(at(p)) for p in loop])
    nL = len(rings[0])
    for i in range(nS):
        for j in range(nL):
            j1 = (j + 1) % nL
            a, b, c, d = rings[i][j], rings[i][j1], rings[i + 1][j1], rings[i + 1][j]
            mb.face([a, b, c, d])
    # close the nose and cantle ends (turned leather edges)
    for idx, flip in ((0, True), (nS, False)):
        ring = rings[idx]
        for j in range(nQ - 1):
            a, b = ring[j], ring[j + 1]
            c, d = ring[nL - 2 - j], ring[nL - 1 - j]
            mb.face([a, b, c, d] if not flip else [d, c, b, a])
    ob = kit.add(mb, pivot, 'leather', 'leather', sharp=75, props={'smartuv': 1})
    # metal: cantle plate, copper rivets, rails, springs, clip, nose bolt
    cp = MB(name + '_cantle')
    pts, w, top, sk = section(0.02, 0.0022)
    band = [at(V(X0 + 0.0065, p.y - y0, p.z)) for p in pts]
    sweep(cp, band, 0.0085, radial=10, oval=(1.0, 0.16), ref=V(1, 0, 0), cap0=True, cap1=True)
    kit.add(cp, pivot, 'metal', 'japanned', sharp=40)
    rv = MB(name + '_rivets')
    for q in (0.14, 0.30, 0.50, 0.70, 0.86):
        k = q * (len(band) - 1); i0 = int(k); u = k - i0
        p = band[i0].lerp(band[min(len(band) - 1, i0 + 1)], u)
        tg = (band[min(len(band) - 1, i0 + 1)] - band[max(0, i0 - 1)]).normalized()
        outn = V(0, -tg.z, tg.y).normalized()
        lathe(rv, [(0.0, 0.0), (0.0044, 0.0), (0.0040, 0.0012), (0.0026, 0.0021), (0.0, 0.0024)], 12, center=p + outn * 0.0012 + V(-0.001, 0, 0), axis=outn)
    for zz in (-0.012, 0.012):
        pn = at(V(X1 - 0.022, spline1D(TOP, 0.92) + spline1D(CR, 0.92) - y0, zz * 0.9))
        lathe(rv, [(0.0, 0.0), (0.0034, 0.0), (0.0030, 0.0010), (0.0, 0.0018)], 10, center=pn, axis=V(0, 1, 0))
    kit.add(rv, pivot, 'metal', 'copper', sharp=40)
    fr = MB(name + '_frame')
    sTop, sBot = -0.026, -0.064
    for s in (1, -1):
        zc = s * 0.052
        sweep(fr, helix_pts(at(V(-0.056, (sTop + sBot) / 2, zc)), 0.0132, sTop - sBot, 4.5, n=150, phase=0 if s > 0 else math.pi),
              0.0022, radial=8, ref=V(0, 1, 0))
        rail = catmull_pts([at(V(0.170, -0.014, s * 0.006)), at(V(0.110, -0.034, s * 0.020)), at(V(0.035, -0.046, s * 0.030)),
                            at(V(-0.030, -0.058, s * 0.044)), at(V(-0.056, sBot - 0.002, s * 0.052)), at(V(-0.070, sBot - 0.003, s * 0.040))], 8)
        sweep(fr, rail, 0.0034, radial=10, cap0=True, cap1=True)
        # spring cups (top plate under the cantle, bottom cup on the rail)
        lathe(fr, [(0.0, 0.0), (0.0158, 0.0), (0.0158, 0.0022), (0.0, 0.0022)], 16, center=at(V(-0.056, sTop, zc)), axis='y')
        lathe(fr, [(0.0, 0.0), (0.0150, 0.0), (0.0150, 0.0026), (0.0, 0.0026)], 16, center=at(V(-0.056, sBot - 0.0026, zc)), axis='y')
    # clip (the seat pin clamps here) with its bolts
    sweep(fr, [at(V(0.030, -0.050, -0.038)), at(V(0.030, -0.050, 0.038))], 0.0095, radial=18, ref=V(0, 1, 0), cap0=True, cap1=True)
    for zz in (-0.012, 0.012):
        sweep(fr, [at(V(0.030, -0.068, zz)), at(V(0.030, -0.032, zz))], 0.0040, radial=10, cap0=True, cap1=True)
        sweep(fr, [at(V(0.030, -0.071, zz)), at(V(0.030, -0.066, zz))], 0.0062, radial=6, cap0=True, cap1=True, smooth=False)
    # nose: tension bolt and cap
    sweep(fr, [at(V(0.168, -0.020, 0)), at(V(0.188, 0.001, 0))], 0.0045, radial=12, cap0=True, cap1=True)
    sweep(fr, [at(V(0.150, -0.016, 0)), at(V(0.172, -0.016, 0))], 0.0060, radial=6, cap0=True, cap1=True, smooth=False)
    kit.add(fr, pivot, 'metal', 'nickel', sharp=40)
    return {'clip': at(V(0.030, -0.050, 0))}


def build_seat_pin(kit, L, name, bb, sit_clip, lug_y):
    """L-shaped seat pin: rises out of the seat lug along the seat tube, bends forward into the saddle clip."""
    pinY = sit_clip.y
    sd = V(L['seatDir'][0], L['seatDir'][1])
    lugTop = P2(on_seat(L, bb, lug_y + 0.012))
    bend = V(on_seat(L, bb, pinY)[0] + 0.004, pinY)
    pts = catmull_pts([lugTop - sd * 0.030, lugTop, P2(on_seat(L, bb, pinY - 0.012)), bend, sit_clip + V(0.013, 0)], 8)
    tube(kit, name, pts, 0.0102, mgroup='metal', smat='nickel', radial=20, cap1=True, spacing=0.004)


def build_stoker_bar(kit, L):
    """Stoker's bars clamp to the captain's seat pin under the saddle (Swift pattern) and reach back."""
    clampY = 0.701
    c = P2(on_seat(L, L['frontBB'], clampY))
    sd = V(L['seatDir'][0], L['seatDir'][1])
    mb = MB('stoker_clamp')
    sweep(mb, [c - sd * 0.008, c + sd * 0.008], 0.0146, radial=24, cap0=True, cap1=True)
    back = V(-L['seatDir'][1], L['seatDir'][0]) * -1.0
    e0 = c + back * 0.017
    sweep(mb, [e0 + V(0, 0, -0.011), e0 + V(0, 0, 0.011)], 0.0052, radial=12, ref=V(0, 1, 0), cap0=True, cap1=True)
    sweep(mb, [e0 + V(0, 0, -0.016), e0 + V(0, 0, 0.016)], 0.0027, radial=8, ref=V(0, 1, 0), cap0=True, cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=40)
    T0 = V(-0.125, 0.752)
    tube(kit, 'stoker_stem', catmull_pts([c + V(-0.010, 0.0), V(0.030, 0.708), V(-0.060, 0.732), T0], 10), 0.0100, mgroup='metal', smat='nickel',
         radial=18, spacing=0.006)
    inR = V(-0.132, 0.760, 0.165); outR = V(-0.212, 0.764, 0.222)
    mir = lambda p: V(p.x, p.y, -p.z)
    tube(kit, 'stoker_bar', catmull_pts([mir(outR), mir(inR), V(-0.118, 0.756, -0.09), T0, V(-0.118, 0.756, 0.09), inR, outR], 10), 0.0104,
         mgroup='metal', smat='nickel', radial=18, spacing=0.008)
    mb = MB('stoker_tee')
    sweep(mb, [T0 + V(0, 0, -0.022), T0 + V(0, 0, 0.022)], 0.0135, radial=20, ref=V(0, 1, 0), cap0=True, cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=40)
    g = {}
    for s, side in ((1, 'R'), (-1, 'L')):
        a = inR if s > 0 else mir(inR); b = outR if s > 0 else mir(outR)
        g[side] = grip(kit, 'grip_rear_' + side, a, b, 'frame')
    return g


def build_frame_hardware(kit, L):
    ax = lambda s: P2(on_axis(L, s))
    aDir = V(L['axis'][0], L['axis'][1])
    mb = MB('headset_cups')
    sweep(mb, [ax(L['sHeadBot'] - 0.010), ax(L['sHeadBot'] + 0.002)], lambda t: 0.0186 + 0.0012 * (1 - t), radial=28, cap0=True, cap1=True)
    sweep(mb, [ax(L['sHeadTop'] - 0.002), ax(L['sHeadTop'] + 0.009)], lambda t: 0.0186 + 0.0010 * t, radial=28, cap0=True, cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=40)
    mb = MB('bb_cups')
    for bb in (L['frontBB'], L['rearBB']):
        for s in (1, -1):
            z0, z1 = s * 0.0355, s * 0.0435
            lathe(mb, [(0.0, z0), (0.0170, z0), (0.0170, z0 + s * 0.004), (0.0150, z1), (0.0092, z1), (0.0, z1)] if s > 0 else
                  [(0.0, z1), (0.0092, z1), (0.0150, z1), (0.0170, z0 + s * 0.004), (0.0170, z0), (0.0, z0)], 28, center=P2(bb), axis='z')
        # oiler on the shell top
        sweep(mb, [P2(bb) + V(0, 0.0205, 0), P2(bb) + V(0, 0.0275, 0)], 0.0030, radial=10, cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=40)
    mb = MB('binder_bolts')
    for bb, sc in ((L['frontBB'], L['FSC']), (L['rearBB'], L['RSC'])):
        c = P2(on_seat(L, bb, sc[1])) + V(L['seatDir'][0], L['seatDir'][1]) * 0.012 + V(-L['seatDir'][1], L['seatDir'][0]) * -0.012
        sweep(mb, [c + V(0, 0, -0.019), c + V(0, 0, 0.017)], 0.0033, radial=10, ref=V(0, 1, 0), cap0=True, cap1=True)
        sweep(mb, [c + V(0, 0, 0.011), c + V(0, 0, 0.017)], 0.0056, radial=6, ref=V(0, 1, 0), cap0=True, cap1=True, smooth=False)
        sweep(mb, [c + V(0, 0, -0.017), c + V(0, 0, -0.012)], 0.0052, radial=12, ref=V(0, 1, 0), cap0=True, cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=40)
    mb = MB('rear_axle_nuts')
    for s in (1, -1):
        sweep(mb, [V(L['rearHub'][0], L['hubY'], s * 0.061), V(L['rearHub'][0], L['hubY'], s * 0.069)], 0.0086, radial=6, ref=V(0, 1, 0),
              cap0=True, cap1=True, smooth=False)
        sweep(mb, [V(L['rearHub'][0], L['hubY'], s * 0.056), V(L['rearHub'][0], L['hubY'], s * 0.075)], 0.0045, radial=10, ref=V(0, 1, 0), cap1=True)
    kit.add(mb, 'frame', 'metal', 'nickel', sharp=30)


# ─────────────────────────────── belts (for tandem.js) ────────────────────────
def belt(A, rA, Bc, rB, pitch, teethA, teethB):
    dx, dy = Bc[0] - A[0], Bc[1] - A[1]
    D = math.hypot(dx, dy)
    u = (dx / D, dy / D); n = (-u[1], u[0])
    phi = math.asin((rA - rB) / D)
    Ls = D * math.cos(phi)
    arcB = rB * (math.pi - 2 * phi); arcA = rA * (math.pi + 2 * phi)
    Lt = 2 * Ls + arcA + arcB
    N = round(Lt / pitch); pp = Lt / N
    angUp = math.pi / 2 - phi; angLow = -angUp
    base = math.atan2(u[1], u[0])
    sMidB = Ls + arcB / 2
    sOff = sMidB % pp
    gammaB = base + angUp - (arcB / 2) / rB
    sMidA = 2 * Ls + arcB + arcA / 2
    jA = round((sMidA - sOff) / pp); sA = sOff + jA * pp
    gammaA = base + angLow - (sA - (2 * Ls + arcB)) / rA
    return {'A': list(A), 'rA': rA, 'B': list(Bc), 'rB': rB, 'teethA': teethA, 'teethB': teethB, 'N': N, 'pp': pp, 'L': Lt,
            'sOff': sOff, 'rotA': gammaA - math.pi / teethA, 'rotB': gammaB - math.pi / teethB}
