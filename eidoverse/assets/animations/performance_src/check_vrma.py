"""check_vrma.py — measure a .vrma the way the film will play it: forward kinematics on the clip's own rest
skeleton (the claudesona's, for clips exported by build_vrma.py), no engine needed.

    python eidoverse/assets/animations/performance_src/check_vrma.py eidoverse/assets/animations/<clip>.vrma ... [--json out.json]

Per clip it reports:
  seam       loops: the largest rotation difference between the first and last sample (deg) + hips drift (mm)
  feet       horizontal travel of the toe joints (the planted contact: under ~1 mm) and of the ankles (a
             peeling heel moves its ankle a few mm by design) over the clip, and the lowest ankle height
  elbows     flexion range (deg); negative = hyperextended
  knees      flexion range (deg)
  wrists     max bend between forearm and hand (deg)
  speed      the fastest bone (deg/s) — a pop shows up as a spike far above the rest
  flower     hand points (wrist, palm, index/middle/little fingertips) tested against the flower, in the frames
             that carry it: the head flower is a disc (centre (0, 1.535, 0.035), radius ~0.46, facing +z) and the
             four lower petals are a sheet over the chest. 'in petals' = a hand point inside the head-flower slab
             (|depth| < 0.09 m, radius < 0.47 m) or tucked under the chest petals; 'over face' = in front of the
             face disc. Numbers in metres of the 2.00 m rig (film scale x0.87).
The flower model is an approximation of the rest-pose mesh (springs move the real petals): treat a flag as
"look at this frame", and a clean report as necessary, not sufficient. Frames are what decide.
"""
import argparse, glob, json, math, struct, sys

import numpy as np


def qmul(a, b):
    ax, ay, az, aw = a[..., 0], a[..., 1], a[..., 2], a[..., 3]
    bx, by, bz, bw = b[..., 0], b[..., 1], b[..., 2], b[..., 3]
    return np.stack([aw * bx + ax * bw + ay * bz - az * by,
                     aw * by - ax * bz + ay * bw + az * bx,
                     aw * bz + ax * by - ay * bx + az * bw,
                     aw * bw - ax * bx - ay * by - az * bz], -1)


def qrot(q, v):
    u = q[..., :3]
    w = q[..., 3:4]
    t = 2 * np.cross(u, v)
    return v + w * t + np.cross(u, t)


def qinv(q):
    return q * np.array([-1, -1, -1, 1.0])


def qangle(a, b):
    """Angle between rotations (deg). atan2 form: arccos near 1 turns float32 norm error into ~0.05 deg noise."""
    a = a / np.linalg.norm(a, axis=-1, keepdims=True)
    b = b / np.linalg.norm(b, axis=-1, keepdims=True)
    r = qmul(qinv(a), b)
    return np.degrees(2 * np.arctan2(np.linalg.norm(r[..., :3], axis=-1), np.abs(r[..., 3])))


def load(path):
    b = open(path, 'rb').read()
    n = struct.unpack('<I', b[12:16])[0]
    j = json.loads(b[20:20 + n])
    off = 20 + n
    bn = struct.unpack('<I', b[off:off + 4])[0]
    binc = b[off + 8: off + 8 + bn]

    def acc(i):
        a = j['accessors'][i]
        bv = j['bufferViews'][a['bufferView']]
        comps = {'SCALAR': 1, 'VEC3': 3, 'VEC4': 4}[a['type']]
        start = bv.get('byteOffset', 0) + a.get('byteOffset', 0)
        arr = np.frombuffer(binc, dtype='<f4', count=a['count'] * comps, offset=start)
        return arr.reshape(a['count'], comps).astype(np.float64)

    nodes = j['nodes']
    hb = {k: v['node'] for k, v in j['extensions']['VRMC_vrm_animation']['humanoid']['humanBones'].items()}
    anim = j['animations'][0]
    times = None
    rot, tra = {}, {}
    for ch in anim['channels']:
        s = anim['samplers'][ch['sampler']]
        t = acc(s['input'])[:, 0]
        times = t if times is None or len(t) > len(times) else times
        (rot if ch['target']['path'] == 'rotation' else tra)[ch['target']['node']] = acc(s['output'])
    return nodes, hb, times, rot, tra


def fk(nodes, times, rot, tra):
    """World positions / rotations of every node at every sample. Returns (P[node], Q[node]) arrays (T, 3/4)."""
    T = len(times)
    parent = {}
    for i, nd in enumerate(nodes):
        for c in nd.get('children', []):
            parent[c] = i
    P, Q = {}, {}
    order = []
    stack = [i for i in range(len(nodes)) if i not in parent]
    while stack:
        i = stack.pop(0)
        order.append(i)
        stack += nodes[i].get('children', [])
    for i in order:
        nd = nodes[i]
        lt = tra.get(i, np.tile(np.array(nd.get('translation', [0, 0, 0]), float), (T, 1)))
        lr = rot.get(i, np.tile(np.array(nd.get('rotation', [0, 0, 0, 1]), float), (T, 1)))
        if len(lt) != T:
            lt = np.resize(lt, (T, 3))
        if len(lr) != T:
            lr = np.resize(lr, (T, 4))
        if i in parent:
            p = parent[i]
            P[i] = P[p] + qrot(Q[p], lt)
            Q[i] = qmul(Q[p], lr)
        else:
            s = np.array(nd.get('scale', [1, 1, 1]), float)
            P[i] = lt
            Q[i] = lr
    return P, Q


def rest_fk(nodes):
    T = 1
    P, Q = fk(nodes, np.zeros(1), {}, {})
    return {k: v[0] for k, v in P.items()}, {k: v[0] for k, v in Q.items()}


def check(path):
    nodes, hb, times, rot, tra = load(path)
    P, Q = fk(nodes, times, rot, tra)
    P0, Q0 = rest_fk(nodes)
    n = {k: hb[k] for k in hb}
    T = len(times)
    dur = float(times[-1])
    out = {'file': path, 'seconds': round(dur, 4), 'samples': T}
    # seam
    seam = max(float(qangle(rot[i][0], rot[i][-1])) for i in rot)
    hips_drift = float(np.linalg.norm(tra[n['hips']][0] - tra[n['hips']][-1]) * 1000) if n['hips'] in tra else 0.0
    out['seam_deg'] = round(seam, 3)
    out['seam_hips_mm'] = round(hips_drift, 2)
    # feet
    feet = {}
    for side in ('left', 'right'):
        for j in ('Foot', 'Toes'):
            p = P[n[side + j]]
            travel = float(np.max(np.linalg.norm(p[:, [0, 2]] - p[0, [0, 2]], axis=1)) * 1000)
            feet[side + j] = dict(travel_mm=round(travel, 2), min_y=round(float(p[:, 1].min()), 4),
                                  max_y=round(float(p[:, 1].max()), 4))
    out['feet'] = feet

    def bend(a, b, c):
        u = P[n[b]] - P[n[a]]
        v = P[n[c]] - P[n[b]]
        cos = np.sum(u * v, 1) / (np.linalg.norm(u, axis=1) * np.linalg.norm(v, axis=1))
        return np.degrees(np.arccos(cos.clip(-1, 1)))

    joints = {}
    for side in ('left', 'right'):
        e = bend(side + 'UpperArm', side + 'LowerArm', side + 'Hand')
        # elbow direction sanity: the hand must be on the flexion side (forearm swings toward the palm side of rest)
        k = bend(side + 'UpperLeg', side + 'LowerLeg', side + 'Foot')
        wr = bend(side + 'LowerArm', side + 'Hand', side + 'MiddleProximal')
        joints[side] = dict(elbow=(round(float(e.min()), 1), round(float(e.max()), 1)),
                            knee=(round(float(k.min()), 1), round(float(k.max()), 1)),
                            wrist_max=round(float(wr.max()), 1))
    out['joints'] = joints
    # speed (deg/s), wrap-around for loops handled by including first-last pair
    dt = np.diff(times)
    speeds = {}
    for name, i in n.items():
        if i not in rot:
            continue
        r = rot[i]
        a = qangle(r[1:], r[:-1]) / dt
        speeds[name] = float(a.max())
    top = sorted(speeds.items(), key=lambda kv: -kv[1])[:3]
    out['fastest'] = [(k, round(v)) for k, v in top]
    # flower tests
    head, chest = n['head'], n['chest']
    dh = qmul(Q[head], qinv(np.tile(Q0[head], (T, 1))))
    dc = qmul(Q[chest], qinv(np.tile(Q0[chest], (T, 1))))
    flags = []
    worst = {}
    for side in ('left', 'right'):
        pts = {
            'wrist': P[n[side + 'Hand']],
            'palm': 0.5 * (P[n[side + 'Hand']] + P[n[side + 'MiddleProximal']]),
            'index_tip': P[n[side + 'IndexDistal']] + 1.0 * (P[n[side + 'IndexDistal']] - P[n[side + 'IndexIntermediate']]) * 0.5,
            'middle_tip': P[n[side + 'MiddleDistal']] + (P[n[side + 'MiddleDistal']] - P[n[side + 'MiddleIntermediate']]) * 0.5,
            'little_tip': P[n[side + 'LittleDistal']] + (P[n[side + 'LittleDistal']] - P[n[side + 'LittleIntermediate']]) * 0.5,
        }
        for pn, p in pts.items():
            # head-flower frame
            pr = P0[head] + qrot(qinv(dh), p - P[head])
            depth = pr[:, 2] - 0.035
            rad = np.hypot(pr[:, 0], pr[:, 1] - 1.535)
            in_petals = (np.abs(depth) < 0.09) & (rad < 0.47) & (pr[:, 1] > 1.33)
            over_face = (depth > 0.0) & (np.hypot(pr[:, 0], pr[:, 1] - 1.53) < 0.17)
            # chest-petal sheet (chest frame): root line y 1.31 z 0.10 -> tips y 1.17 z 0.23, |x| < 0.30
            pc = P0[chest] + qrot(qinv(dc), p - P[chest])
            zs = 0.10 + np.clip((1.31 - pc[:, 1]) / 0.14, 0, 1) * 0.13
            under = (np.abs(pc[:, 0]) < 0.30) & (pc[:, 1] > 1.16) & (pc[:, 1] < 1.37) & (pc[:, 2] < zs - 0.01) & (pc[:, 2] > 0.02)
            for label, mask in (('in petals', in_petals), ('over face', over_face), ('under chest petals', under)):
                if mask.any():
                    idx = np.nonzero(mask)[0]
                    key = f'{side} {pn} {label}'
                    worst[key] = (round(float(times[idx[0]]), 3), round(float(times[idx[-1]]), 3), int(mask.sum()))
    out['flower_flags'] = worst
    out['hand_clearance'] = {}
    for side in ('left', 'right'):
        p = 0.5 * (P[n[side + 'Hand']] + P[n[side + 'MiddleProximal']])
        pr = P0[head] + qrot(qinv(dh), p - P[head])
        out['hand_clearance'][side] = dict(min_radius=round(float(np.hypot(pr[:, 0], pr[:, 1] - 1.535).min()), 3),
                                           depth_at_min=round(float((pr[:, 2] - 0.035)[np.argmin(np.hypot(pr[:, 0], pr[:, 1] - 1.535))]), 3))
    return out


def trails(path, out_png, fps=30):
    """Motion trails, the animator's arc check: every joint that matters as one dot per film frame (30 fps),
    so arcs read as curves and spacing reads as dot density (bunched = easing, spread = fast). Front (x-y) and
    side (z-y) projections over the rest stick figure and the flower's outline, colours running early -> late."""
    from PIL import Image, ImageDraw, ImageFont
    nodes, hb, times, rot, tra = load(path)
    P, Q = fk(nodes, times, rot, tra)
    n = hb
    T = times[-1]
    ts = np.arange(0, T + 1e-9, 1.0 / fps)
    idx = np.clip(np.searchsorted(times, ts), 0, len(times) - 1)
    W, H, S = 520, 700, 300.0            # px per panel, px per metre
    img = Image.new('RGB', (W * 2, H + 40), (22, 24, 30))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 18)
    name = path.replace(chr(92), '/').split('/')[-1]
    d.text((10, 8), f'{name}  trails @ {fps} fps   front (her left = right) | side (forward = right)',
           font=font, fill=(235, 235, 235))
    P0, Q0 = rest_fk(nodes)

    def to_px(p, panel):
        x = p[0] if panel == 0 else p[2]          # front: a +z camera sees her left (+x) on screen right
        return (W * panel + W / 2 + x * S, 40 + H - 30 - p[1] * S)

    bones = [('hips', 'spine'), ('spine', 'chest'), ('chest', 'neck'), ('neck', 'head')]
    for s in ('left', 'right'):
        bones += [('chest', s + 'Shoulder'), (s + 'Shoulder', s + 'UpperArm'), (s + 'UpperArm', s + 'LowerArm'),
                  (s + 'LowerArm', s + 'Hand'), (s + 'Hand', s + 'MiddleProximal'), ('hips', s + 'UpperLeg'),
                  (s + 'UpperLeg', s + 'LowerLeg'), (s + 'LowerLeg', s + 'Foot'), (s + 'Foot', s + 'Toes')]
    for panel in (0, 1):
        d.line([(W * panel + 10, 40 + H - 30), (W * panel + W - 10, 40 + H - 30)], fill=(70, 74, 84), width=1)
        for f0, col in ((0, (80, 86, 100)), (len(times) - 1, (120, 110, 90))):
            for a_, b_ in bones:
                if a_ in n and b_ in n:
                    d.line([to_px(P[n[a_]][f0], panel), to_px(P[n[b_]][f0], panel)], fill=col, width=3)
        # flower outline at the first frame: the petal ring (radius ~0.45 round the face) in the head's frame
        hd = n['head']
        for f0, col in ((0, (214, 140, 70)), (len(times) - 1, (150, 100, 60))):
            dq = qmul(Q[hd][f0], qinv(Q0[hd]))
            ring = [P[hd][f0] + qrot(dq, np.array([0.45 * math.cos(a), 1.535 + 0.45 * math.sin(a), 0.035]) - P0[hd])
                    for a in np.linspace(0, 2 * math.pi, 49)]
            d.line([to_px(p, panel) for p in ring], fill=col, width=2)
    tracks = [('leftHand', (120, 200, 255)), ('rightHand', (255, 150, 150)), ('head', (255, 220, 120)),
              ('hips', (170, 255, 170)), ('leftMiddleDistal', (60, 140, 220)), ('rightMiddleDistal', (220, 90, 90))]
    for j, col in tracks:
        if j not in n:
            continue
        pts = P[n[j]][idx]
        for panel in (0, 1):
            for k, p in enumerate(pts):
                u = k / max(1, len(pts) - 1)
                c = tuple(int(col[m] * (0.45 + 0.55 * u)) for m in range(3))
                x, y = to_px(p, panel)
                d.ellipse([x - 2, y - 2, x + 2, y + 2], fill=c)
    img.save(out_png)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('files', nargs='+')
    ap.add_argument('--json')
    ap.add_argument('--trails', help='directory: also draw trails_<clip>.png motion-trail sheets')
    a = ap.parse_args()
    files = []
    for f in a.files:
        files += sorted(glob.glob(f)) or [f]
    import os
    mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'clips.json')
    manifest = json.load(open(mp)) if os.path.exists(mp) else {}
    res = []
    for f in files:
        r = check(f)
        res.append(r)
        feet = r['feet']
        toes = max(feet['leftToes']['travel_mm'], feet['rightToes']['travel_mm'])
        ank = max(feet['leftFoot']['travel_mm'], feet['rightFoot']['travel_mm'])
        name = f.replace(chr(92), '/').split('/')[-1][:-5]
        loop = manifest.get(name, {}).get('loop', True)
        seam = (f"seam {r['seam_deg']:6.3f} deg / hips {r['seam_hips_mm']:5.2f} mm" if loop
                else f"one-shot (start->end {r['seam_deg']:5.1f} deg)")
        print(f"{name:24s} {r['seconds']:7.4f}s  {seam:36s}  toes slide {toes:5.2f} mm  ankles {ank:5.2f} mm"
              f"  ankle y {min(feet['leftFoot']['min_y'], feet['rightFoot']['min_y']):.4f}")
        for side, j in r['joints'].items():
            print(f"      {side:5s} elbow {j['elbow'][0]:6.1f}..{j['elbow'][1]:6.1f}  knee {j['knee'][0]:5.1f}..{j['knee'][1]:5.1f}  wrist max {j['wrist_max']:5.1f}")
        print(f"      fastest {r['fastest']}   hand clearance {r['hand_clearance']}")
        for k, v in r['flower_flags'].items():
            print(f"      FLAG {k}: t {v[0]}..{v[1]} s ({v[2]} samples)")
        if a.trails:
            os.makedirs(a.trails, exist_ok=True)
            trails(f, os.path.join(a.trails, f'trails_{name}.png'))
    if a.json:
        json.dump(res, open(a.json, 'w'), indent=1)


if __name__ == '__main__':
    main()
