"""check_vrma.py — measure a .vrma the way the film will play it: forward kinematics on the clip's own rest
skeleton, no engine needed. UNKNOWN FORCE edition of eidoverse/assets/animations/performance_src/check_vrma.py (the
same report, plus the mesh). From the repository root:

    python eidoverse/assets/animations/performance_uf_src/check_vrma.py eidoverse/assets/animations/turn_it_down*.vrma [--trails DIR] [--json out.json]

Per clip:
  seam       loops: the largest rotation difference between the first and last sample (deg) + hips drift (mm)
  feet       horizontal travel of the toe joints (the planted contact: under ~1 mm) and the ankles (a peeling heel
             moves its ankle a few mm by design), the lowest ankle height
  elbows / knees / wrists, the fastest bone (deg/s; a pop shows as a spike)
  flower     DAISY's disc model of the petal ring (flags: 'in petals', 'over face', 'under chest petals')
  MESH       (rig/rig_points.npz, from rig/dump_rig.py) the real rest meshes skinned by the clip's own FK every
             sample (linear blend; the petal springs are not simulated):
               petals  the closest any hand point (wrist, palm, knuckles, finger and thumb tips) comes to a petal
                       vertex, per hand; FLAG 'petal touch' under 3.5 cm. 'forearm' = the closest the middle of
                       the forearm comes (springs push petals off forearms by design: information, not a flag).
               body    the closest a hand point comes to the body surface (tuta, skin, face; the hand's own arm
                       excluded), signed by the nearest vertex normal; FLAG 'body touch' under 1.5 cm or inside.
  gaze       where the face points: elevation (+ = up) and azimuth (+ = toward her left), range over the clip
  drift      loops: how far each palm travels over the loop (mm) — a hold that should be still shows it here
Numbers are metres/degrees of the 2.00 m rig (the film shows it at 0.87). A flag means "look at this frame";
a clean report is necessary, not sufficient. Frames are what decide.
Junctions: every <x> with an <x>_hold beside it gets its hand-over measured (last sample vs first sample).
"""
import argparse, glob, json, math, os, struct, sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
RIG = os.path.join(HERE, 'rig', 'rig_points.npz')
BODY_MESHES = ('tuta', 'BodyActual', 'face')     # not uf_straps: a thin band's inner faces point inward (false 'inside')
PETAL_TOUCH, BODY_TOUCH = 0.035, 0.015


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


def qmat(q):
    x, y, z, w = q[..., 0], q[..., 1], q[..., 2], q[..., 3]
    return np.stack([np.stack([1 - 2 * (y * y + z * z), 2 * (x * y - z * w), 2 * (x * z + y * w)], -1),
                     np.stack([2 * (x * y + z * w), 1 - 2 * (x * x + z * z), 2 * (y * z - x * w)], -1),
                     np.stack([2 * (x * z - y * w), 2 * (y * z + x * w), 1 - 2 * (x * x + y * y)], -1)], -2)


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
            P[i] = lt
            Q[i] = lr
    return P, Q


def rest_fk(nodes):
    P, Q = fk(nodes, np.zeros(1), {}, {})
    return {k: v[0] for k, v in P.items()}, {k: v[0] for k, v in Q.items()}


# ---------------------------------------------------------------------------- the mesh (rest geometry + skinning)
class Mesh:
    def __init__(self, path=RIG):
        d = np.load(path)
        self.names = [str(s) for s in d['human_names']]
        self.parts = {}
        for key in [k[:-5] for k in d.files if k.endswith('__pos')]:
            self.parts[key] = dict(pos=d[key + '__pos'].astype(np.float64), nor=d[key + '__nor'].astype(np.float64),
                                   wi=d[key + '__wi'].astype(np.int64), ww=d[key + '__ww'].astype(np.float64))

    def select(self, meshes, exclude_prefixes=(), min_y=-1.0):
        ex = [i for i, nm in enumerate(self.names) if any(nm.startswith(b) for b in exclude_prefixes)]
        pos, nor, wi, ww = [], [], [], []
        for m in meshes:
            p = self.parts[m]
            keep = ~np.isin(p['wi'][:, 0], ex) if ex else np.ones(len(p['pos']), bool)
            keep &= p['pos'][:, 1] > min_y
            pos.append(p['pos'][keep]); nor.append(p['nor'][keep]); wi.append(p['wi'][keep]); ww.append(p['ww'][keep])
        return dict(pos=np.concatenate(pos), nor=np.concatenate(nor), wi=np.concatenate(wi), ww=np.concatenate(ww))

    def skin(self, sel, Rb, tb):
        """Linear-blend skin a selection with per-bone (3x3, 3) transforms (indexed like self.names)."""
        v, n = sel['pos'], sel['nor']
        out_p = np.zeros_like(v)
        out_n = np.zeros_like(n)
        for k in range(4):
            w = sel['ww'][:, k:k + 1]
            R = Rb[sel['wi'][:, k]]
            out_p += w * (np.einsum('nij,nj->ni', R, v) + tb[sel['wi'][:, k]])
            out_n += w * np.einsum('nij,nj->ni', R, n)
        out_n /= np.linalg.norm(out_n, axis=1, keepdims=True) + 1e-12
        return out_p, out_n


ARM_CHAIN = ('Shoulder', 'UpperArm', 'LowerArm', 'Hand', 'Thumb', 'Index', 'Middle', 'Ring', 'Little')


def hand_points(P, n, side):
    def tip(a, b):
        return P[n[side + a]] + (P[n[side + a]] - P[n[side + b]]) * 0.6
    return {
        'wrist': P[n[side + 'Hand']],
        'palm': 0.5 * (P[n[side + 'Hand']] + P[n[side + 'MiddleProximal']]),
        'knuckle_i': P[n[side + 'IndexProximal']], 'knuckle_m': P[n[side + 'MiddleProximal']],
        'knuckle_l': P[n[side + 'LittleProximal']],
        'index_tip': tip('IndexDistal', 'IndexIntermediate'), 'middle_tip': tip('MiddleDistal', 'MiddleIntermediate'),
        'little_tip': tip('LittleDistal', 'LittleIntermediate'), 'thumb_tip': tip('ThumbDistal', 'ThumbProximal'),
    }


def mesh_checks(mesh, nodes, hb, times, P, Q, P0, Q0):
    from scipy.spatial import cKDTree
    T = len(times)
    B = len(mesh.names)
    Rb = np.tile(np.eye(3), (T, B, 1, 1))
    tb = np.zeros((T, B, 3))
    for bi, name in enumerate(mesh.names):
        if name not in hb:
            continue
        i = hb[name]
        dq = qmul(Q[i], qinv(np.tile(Q0[i], (T, 1))))
        R = qmat(dq)
        Rb[:, bi] = R
        tb[:, bi] = P[i] - np.einsum('tij,j->ti', R, P0[i])
    flower = mesh.select(('flower',))
    # the hands never go below the knee: the body test keeps everything above 0.40 m (rest)
    bodies = {side: mesh.select(BODY_MESHES, exclude_prefixes=[side + c for c in ARM_CHAIN], min_y=0.40) for side in ('left', 'right')}
    res = {}
    for side in ('left', 'right'):
        pts = hand_points(P, hb, side)
        fore = 0.5 * (P[hb[side + 'LowerArm']] + P[hb[side + 'Hand']])
        best_pet = (9.0, None, None)
        best_fore = (9.0, None)
        best_body = (9.0, None, None, 9.0)
        pet_hits, body_hits = [], []
        for f in range(0, T, 2):                 # every other sample (31 Hz)
            fp, _ = mesh.skin(flower, Rb[f], tb[f])
            tree = cKDTree(fp)
            q = np.array([p[f] for p in pts.values()])
            d, _ = tree.query(q)
            k = int(np.argmin(d))
            if d[k] < best_pet[0]:
                best_pet = (float(d[k]), float(times[f]), list(pts)[k])
            if d[k] < PETAL_TOUCH:
                pet_hits.append(float(times[f]))
            df, _ = tree.query(fore[f])
            if df < best_fore[0]:
                best_fore = (float(df), float(times[f]))
            bp, bn = mesh.skin(bodies[side], Rb[f], tb[f])
            tb_tree = cKDTree(bp)
            d2, j2 = tb_tree.query(q)
            sgn = np.einsum('ij,ij->i', q - bp[j2], bn[j2])
            k2 = int(np.argmin(d2))
            if d2[k2] < best_body[0]:
                best_body = (float(d2[k2]), float(times[f]), list(pts)[k2], float(sgn[k2]))
            if (d2 < BODY_TOUCH).any() or ((sgn < 0) & (d2 < 0.06)).any():
                body_hits.append(float(times[f]))
        res[side] = dict(petal=best_pet, forearm=best_fore, body=best_body, petal_hits=pet_hits, body_hits=body_hits)
    return res


def gaze(P, Q, P0, Q0, hb):
    h = hb['head']
    T = len(Q[h])
    dq = qmul(Q[h], qinv(np.tile(Q0[h], (T, 1))))
    fwd = qrot(dq, np.tile(np.array([0.0, 0.0, 1.0]), (T, 1)))
    el = np.degrees(np.arcsin(np.clip(fwd[:, 1], -1, 1)))
    az = np.degrees(np.arctan2(fwd[:, 0], fwd[:, 2]))
    return el, az


def check(path, mesh=None):
    nodes, hb, times, rot, tra = load(path)
    P, Q = fk(nodes, times, rot, tra)
    P0, Q0 = rest_fk(nodes)
    n = hb
    T = len(times)
    out = {'file': path, 'seconds': round(float(times[-1]), 5), 'samples': T}
    out['seam_deg'] = round(max(float(qangle(rot[i][0], rot[i][-1])) for i in rot), 3)
    out['seam_hips_mm'] = round(float(np.linalg.norm(tra[n['hips']][0] - tra[n['hips']][-1]) * 1000), 2) if n['hips'] in tra else 0.0
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
        k = bend(side + 'UpperLeg', side + 'LowerLeg', side + 'Foot')
        wr = bend(side + 'LowerArm', side + 'Hand', side + 'MiddleProximal')
        joints[side] = dict(elbow=(round(float(e.min()), 1), round(float(e.max()), 1)),
                            knee=(round(float(k.min()), 1), round(float(k.max()), 1)),
                            wrist_max=round(float(wr.max()), 1))
    out['joints'] = joints
    dt = np.diff(times)
    speeds = {}
    for name, i in n.items():
        if i in rot:
            speeds[name] = float((qangle(rot[i][1:], rot[i][:-1]) / dt).max())
    out['fastest'] = [(k, round(v)) for k, v in sorted(speeds.items(), key=lambda kv: -kv[1])[:3]]
    # DAISY's disc model of the flower
    head, chest = n['head'], n['chest']
    dh = qmul(Q[head], qinv(np.tile(Q0[head], (T, 1))))
    dc = qmul(Q[chest], qinv(np.tile(Q0[chest], (T, 1))))
    worst = {}
    for side in ('left', 'right'):
        for pn, p in hand_points(P, n, side).items():
            pr = P0[head] + qrot(qinv(dh), p - P[head])
            depth = pr[:, 2] - 0.035
            rad = np.hypot(pr[:, 0], pr[:, 1] - 1.535)
            in_petals = (np.abs(depth) < 0.09) & (rad < 0.47) & (pr[:, 1] > 1.33)
            over_face = (depth > 0.0) & (np.hypot(pr[:, 0], pr[:, 1] - 1.53) < 0.17)
            pc = P0[chest] + qrot(qinv(dc), p - P[chest])
            zs = 0.10 + np.clip((1.31 - pc[:, 1]) / 0.14, 0, 1) * 0.13
            under = (np.abs(pc[:, 0]) < 0.30) & (pc[:, 1] > 1.16) & (pc[:, 1] < 1.37) & (pc[:, 2] < zs - 0.01) & (pc[:, 2] > 0.02)
            for label, mask in (('in petals', in_petals), ('over face', over_face), ('under chest petals', under)):
                if mask.any():
                    idx = np.nonzero(mask)[0]
                    worst[f'{side} {pn} {label}'] = (round(float(times[idx[0]]), 3), round(float(times[idx[-1]]), 3), int(mask.sum()))
    out['flower_flags'] = worst
    el, az = gaze(P, Q, P0, Q0, n)
    out['gaze'] = dict(el=(round(float(el.min()), 1), round(float(el.max()), 1)), az=(round(float(az.min()), 1), round(float(az.max()), 1)),
                       end=(round(float(el[-1]), 1), round(float(az[-1]), 1)))
    out['palm_drift_mm'] = {}
    out['palm_end'] = {}
    for side in ('left', 'right'):
        p = 0.5 * (P[n[side + 'Hand']] + P[n[side + 'MiddleProximal']])
        out['palm_drift_mm'][side] = round(float(np.max(np.linalg.norm(p - p[0], axis=1)) * 1000), 1)
        out['palm_end'][side] = [round(float(v), 4) for v in p[-1]]
    if mesh is not None:
        out['mesh'] = mesh_checks(mesh, nodes, hb, times, P, Q, P0, Q0)
    out['_first'] = {i: rot[i][0] for i in rot}
    out['_last'] = {i: rot[i][-1] for i in rot}
    out['_hips'] = (tra[n['hips']][0], tra[n['hips']][-1]) if n['hips'] in tra else None
    out['_names'] = {v: k for k, v in n.items()}
    return out


def trails(path, out_png, mesh=None, fps=30):
    """Motion trails: every joint that matters as one dot per film frame (30 fps): arcs read as curves, spacing as
    dot density. Front (x-y) and side (z-y) over the rest stick figure and the PETALS (skinned, first frame faint
    orange, last frame brighter), colours running early -> late."""
    from PIL import Image, ImageDraw, ImageFont
    nodes, hb, times, rot, tra = load(path)
    P, Q = fk(nodes, times, rot, tra)
    P0, Q0 = rest_fk(nodes)
    n = hb
    T = times[-1]
    ts = np.arange(0, T + 1e-9, 1.0 / fps)
    idx = np.clip(np.searchsorted(times, ts), 0, len(times) - 1)
    W, H, S = 520, 700, 300.0
    img = Image.new('RGB', (W * 2, H + 40), (22, 24, 30))
    d = ImageDraw.Draw(img)
    font = ImageFont.truetype('C:/Windows/Fonts/arialbd.ttf', 18)
    name = path.replace(chr(92), '/').split('/')[-1]
    d.text((10, 8), f'{name}  trails @ {fps} fps   front (her left = right) | side (forward = right)', font=font, fill=(235, 235, 235))

    def to_px(p, panel):
        x = p[0] if panel == 0 else p[2]
        return (W * panel + W / 2 + x * S, 40 + H - 30 - p[1] * S)

    if mesh is not None:
        flower = mesh.select(('flower',))
        Tn = len(times)
        for f0, col in ((0, (110, 70, 40)), (Tn - 1, (200, 120, 60))):
            Rb = np.tile(np.eye(3), (len(mesh.names), 1, 1))
            tb = np.zeros((len(mesh.names), 3))
            for bi, nm in enumerate(mesh.names):
                if nm in hb:
                    i = hb[nm]
                    R = qmat(qmul(Q[i][f0], qinv(Q0[i])))
                    Rb[bi] = R
                    tb[bi] = P[i][f0] - R @ P0[i]
            fp, _ = mesh.skin(flower, Rb, tb)
            for panel in (0, 1):
                for v in fp[::3]:
                    x, y = to_px(v, panel)
                    d.point((x, y), fill=col)
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
    ap.add_argument('--no-mesh', action='store_true')
    a = ap.parse_args()
    files = []
    for f in a.files:
        files += sorted(glob.glob(f)) or [f]
    files = [f for f in files if not os.path.basename(f).startswith('zz_')]
    mp = os.path.join(HERE, 'clips.json')
    manifest = json.load(open(mp, encoding='utf-8')) if os.path.exists(mp) else {}
    mesh = None if a.no_mesh or not os.path.exists(RIG) else Mesh()
    res = {}
    for f in files:
        r = check(f, mesh)
        name = f.replace(chr(92), '/').split('/')[-1][:-5]
        res[name] = r
        feet = r['feet']
        toes = max(feet['leftToes']['travel_mm'], feet['rightToes']['travel_mm'])
        ank = max(feet['leftFoot']['travel_mm'], feet['rightFoot']['travel_mm'])
        loop = manifest.get(name, {}).get('loop', True)
        beats = manifest.get(name, {}).get('beats')
        seam = (f"seam {r['seam_deg']:6.3f} deg / hips {r['seam_hips_mm']:5.2f} mm" if loop
                else f"one-shot (start->end {r['seam_deg']:5.1f} deg)")
        print(f"{name:20s} {r['seconds']:7.5f}s ({beats} beats)  {seam:36s}  toes slide {toes:5.2f} mm  ankles {ank:5.2f} mm"
              f"  ankle y {min(feet['leftFoot']['min_y'], feet['rightFoot']['min_y']):.4f}")
        for side, j in r['joints'].items():
            print(f"      {side:5s} elbow {j['elbow'][0]:6.1f}..{j['elbow'][1]:6.1f}  knee {j['knee'][0]:5.1f}..{j['knee'][1]:5.1f}  wrist max {j['wrist_max']:5.1f}")
        g = r['gaze']
        print(f"      fastest {r['fastest']}   gaze el {g['el'][0]}..{g['el'][1]} az {g['az'][0]}..{g['az'][1]} (end {g['end'][0]}, {g['end'][1]})"
              + (f"   palm drift L {r['palm_drift_mm']['left']} R {r['palm_drift_mm']['right']} mm" if loop else ''))
        for k, v in r['flower_flags'].items():
            print(f"      FLAG(disc) {k}: t {v[0]}..{v[1]} s ({v[2]} samples)")
        if 'mesh' in r:
            for side, m in r['mesh'].items():
                pt, bt = m['petal'], m['body']
                print(f"      mesh {side:5s} petals {pt[0] * 100:5.1f} cm ({pt[2]} @ {pt[1]:.2f}s)  forearm {m['forearm'][0] * 100:5.1f} cm"
                      f"  body {bt[0] * 100:5.1f} cm ({bt[2]} @ {bt[1]:.2f}s, signed {bt[3] * 100:+.1f})")
                if m['petal_hits']:
                    print(f"      FLAG {side} petal touch: t {m['petal_hits'][0]:.2f}..{m['petal_hits'][-1]:.2f} s ({len(m['petal_hits'])} samples)")
                if m['body_hits']:
                    print(f"      FLAG {side} body touch: t {m['body_hits'][0]:.2f}..{m['body_hits'][-1]:.2f} s ({len(m['body_hits'])} samples)")
        if a.trails:
            os.makedirs(a.trails, exist_ok=True)
            trails(f, os.path.join(a.trails, f'trails_{name}.png'), mesh)
    # junctions: one-shot -> its _hold loop
    for name, r in res.items():
        h = res.get(name + '_hold')
        if not h:
            continue
        names = r['_names']
        worst = max((float(qangle(r['_last'][i], h['_first'][i])), names.get(i, i)) for i in r['_last'] if i in h['_first'])
        hips = float(np.linalg.norm(r['_hips'][1] - h['_hips'][0]) * 1000) if r['_hips'] is not None and h['_hips'] is not None else 0.0
        print(f"junction {name} -> {name}_hold: max bone difference {worst[0]:.3f} deg ({worst[1]}), hips {hips:.2f} mm")
    if a.json:
        clean = {k: {kk: vv for kk, vv in v.items() if not kk.startswith('_')} for k, v in res.items()}
        json.dump(clean, open(a.json, 'w'), indent=1, default=float)


if __name__ == '__main__':
    main()
