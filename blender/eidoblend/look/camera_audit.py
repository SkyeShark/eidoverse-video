"""look/camera_audit.py: the camera audits, per shot. Bounce (a camera lurching back and forth), framing (a subject
that ends up a speck) and focus (a subject outside the depth of field, or a picture with nothing sharp in it). Each
returns plain dict records for the audit ledger (look/audit.py), and prints one line each.

    from eidoblend.look import camera_audit as CA
    CA.camera_motion_audit(scene)                         # every shot from the markers bound to cameras
    CA.framing_audit(scene, subject=arm)                  # the subject's projected bounds, middle and last frame
    CA.focus_audit(scene, subject=C.bone_target(arm, 'head'), allow_soft={'pan': (121, 150)})   # a rack's start

The bounce rule is the WebGPU one (render_scene.mjs), its gates restated in seconds so 24 and 30 fps films are judged
alike: more than 5 direction reversals a second, with a swing above 0.6 m/s (position), 9 deg/s (fov) or 9 deg/s
(aim: the WebGPU audit did not watch rotation; a tracking camera aimed at a bobbing bone nods). Reversals are counted
within a shot, so a cut is not a reversal.
"""
import math

import bpy
from bpy_extras.object_utils import world_to_camera_view
from mathutils import Vector

from . import camera as C

POS_GATE, POS_SWING = 0.3, 0.6        # m/s: a reversal counts above the gate; the shot fails above the swing
FOV_GATE, FOV_SWING = 1.5, 9.0        # deg/s
AIM_GATE, AIM_SWING = 1.5, 9.0        # deg/s
RATE = 5.0                            # reversals per second
MIN_COVERAGE = 0.06                   # framing: the subject's share of the frame


def _record(check, outcome, message, cls='CORRECTNESS', **metrics):
    return {'check': check, 'outcome': outcome, 'class': cls, 'metrics': metrics, 'message': message}


def _shots(scene, cam, span):
    if cam is not None:
        fa, fb = span if span else (scene.frame_start, scene.frame_end)
        return {cam.name: (fa, fb, cam)}
    spans = C.shot_spans(scene)
    if not spans:
        fa, fb = span if span else (scene.frame_start, scene.frame_end)
        return {scene.camera.name: (fa, fb, scene.camera)}
    return spans


def camera_motion_audit(scene, cam=None, span=None, log=True):
    """Count direction reversals of each shot's camera position, fov and aim. Returns one record per shot."""
    fps = C.fps_of(scene)
    keep = scene.frame_current
    out = []
    for name, (fa, fb, c) in _shots(scene, cam, span).items():
        tr = []
        for f in range(fa, fb + 1):
            scene.frame_set(f)
            m = c.matrix_world
            fwd = -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
            tr.append((m.translation.copy(), C.fov_of(c, scene)[1], fwd))
        n = len(tr)
        dur = max(0.1, n / fps)
        pos_rev = fov_rev = aim_rev = 0
        pos_sw = fov_sw = aim_sw = 0.0
        pv = pf = pa = None
        for k in range(1, n):
            v = (tr[k][0] - tr[k - 1][0]) * fps                      # m/s
            if pv is not None and v.dot(pv) < 0 and v.length > POS_GATE and pv.length > POS_GATE:
                pos_rev += 1
                pos_sw = max(pos_sw, min(v.length, pv.length))
            pv = v
            fd = (tr[k][1] - tr[k - 1][1]) * fps                     # deg/s
            if pf is not None and fd * pf < 0 and abs(fd) > FOV_GATE and abs(pf) > FOV_GATE:
                fov_rev += 1
                fov_sw = max(fov_sw, min(abs(fd), abs(pf)))
            pf = fd
            ax = tr[k - 1][2].cross(tr[k][2])                         # the aim's angular velocity (axis x rad/frame)
            w = ax * (math.degrees(math.asin(min(1.0, ax.length))) * fps / max(ax.length, 1e-12))
            if pa is not None and w.dot(pa) < 0 and w.length > AIM_GATE and pa.length > AIM_GATE:
                aim_rev += 1
                aim_sw = max(aim_sw, min(w.length, pa.length))
            pa = w
        rates = (pos_rev / dur, fov_rev / dur, aim_rev / dur)
        bad = []
        if rates[0] > RATE and pos_sw > POS_SWING:
            bad.append(f'{pos_rev} position reversals ({rates[0]:.1f}/s, swing {pos_sw:.2f} m/s)')
        if rates[1] > RATE and fov_sw > FOV_SWING:
            bad.append(f'{fov_rev} fov reversals ({rates[1]:.1f}/s, swing {fov_sw:.1f} deg/s)')
        if rates[2] > RATE and aim_sw > AIM_SWING:
            bad.append(f'{aim_rev} aim reversals ({rates[2]:.1f}/s, swing {aim_sw:.1f} deg/s)')
        met = dict(shot=name, camera=c.name, frames=[fa, fb], pos_reversals=pos_rev, fov_reversals=fov_rev,
                   aim_reversals=aim_rev, pos_swing=round(pos_sw, 3), fov_swing=round(fov_sw, 2), aim_swing=round(aim_sw, 2))
        if bad:
            msg = (f"[camera] RE-RENDER: shot {name} ({c.name}, {fa}-{fb}) BOUNCES: {'; '.join(bad)}. One eased move per "
                   f"shot; no high-frequency sin() on the dolly or the lens; smooth the target the camera follows "
                   f"(track/pan smooth_s); cut between shots rather than bounce within one.")
            out.append(_record('camera.motion', 'WARN', msg, **met))
        else:
            msg = (f'[camera] OK: shot {name} ({c.name}, {fa}-{fb}) moves smoothly ({rates[0]:.1f} position, '
                   f'{rates[2]:.1f} aim reversals/s)')
            out.append(_record('camera.motion', 'PASS', msg, cls='REVIEW', **met))
        if log:
            print(msg, flush=True)
    scene.frame_set(keep)
    return out


def projected_box(scene, cam, items, depsgraph=None):
    """The subject's evaluated world bounds projected through the camera: dict(box=(x0, y0, x1, y1) normalised with
    the origin TOP left, clipped to the frame; coverage = its share of the frame; cut = it crosses an edge;
    behind = corners behind the lens) or None without geometry. A bounding box: generous for thin diagonal shapes."""
    b = C.world_bounds(items, depsgraph)
    if b is None:
        return None
    lo, hi = b
    xs, ys, behind = [], [], 0
    for cx in (lo.x, hi.x):
        for cy in (lo.y, hi.y):
            for cz in (lo.z, hi.z):
                v = world_to_camera_view(scene, cam, Vector((cx, cy, cz)))
                if v.z <= 0:
                    behind += 1
                    continue
                xs.append(v.x)
                ys.append(1.0 - v.y)
    if len(xs) < 4:
        return {'box': None, 'coverage': 0.0, 'cut': True, 'behind': behind}
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    cx0, cx1, cy0, cy1 = max(0.0, x0), min(1.0, x1), max(0.0, y0), min(1.0, y1)
    cov = max(0.0, cx1 - cx0) * max(0.0, cy1 - cy0)
    return {'box': (cx0, cy0, cx1, cy1), 'coverage': cov, 'cut': x0 < 0 or x1 > 1 or y0 < 0 or y1 > 1,
            'behind': behind, 'unclipped': (x0, y0, x1, y1)}


def _mass_cluster(scene, depsgraph):
    """The WebGPU framing audit's subject when none is named: where the geometric mass concentrates (ground slabs over
    150 m wide and long thin runs left out), converged by three rounds of keeping what lies near the mass centre."""
    cands = []
    for o in scene.objects:
        if o.type not in C.GEOMETRY or o.hide_render:
            continue
        b = C.world_bounds(o, depsgraph, children=False)
        if b is None:
            continue
        lo, hi = b
        s = hi - lo
        span = max(s.x, s.y)
        if span > 150 and s.z < span * 0.05:
            continue
        dims = sorted((s.x, s.y, s.z), reverse=True)
        cands.append({'o': o, 'c': (lo + hi) * 0.5, 'm': max(s.x, .01) * max(s.y, .01) * max(s.z, .01),
                      'run': dims[0] > 12 * max(dims[1], .01)})
    kept = cands
    for _ in range(3):
        if len(kept) < 2:
            break
        M = sum(k['m'] for k in kept)
        if M <= 0:
            break
        Cc = sum((k['c'] * k['m'] for k in kept), Vector()) / M
        var = sum(k['m'] * (k['c'] - Cc).length_squared for k in kept) / M
        keep_r = max(math.sqrt(var) * 1.25, 1e-3)
        nxt = [k for k in kept if (k['c'] - Cc).length <= keep_r]
        if len(nxt) in (0, len(kept)):
            break
        kept = nxt
    objs = [k['o'] for k in kept if not k['run']] or [k['o'] for k in kept]
    return objs


def framing_audit(scene, subject=None, cam=None, span=None, frames=None, min_coverage=MIN_COVERAGE, log=True):
    """The subject's share of the frame, per shot at its middle and last frames (or at `frames`). subject: objects /
    a collection / an armature (its meshes); None = the mass cluster. Under min_coverage: 'RE-RENDER' (a speck)."""
    keep = scene.frame_current
    out = []
    for name, (fa, fb, c) in _shots(scene, cam, span).items():
        fs = [f for f in frames if fa <= f <= fb] if frames else sorted({(fa + fb) // 2, fb})
        for f in fs:
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            items = subject if subject is not None else _mass_cluster(scene, dg)
            pb = projected_box(scene, c, items, dg)
            met = dict(shot=name, camera=c.name, frame=f)
            if pb is None or pb['box'] is None:
                msg = f'[framing] shot {name} frame {f}: the subject is not in front of the camera ({c.name})'
                out.append(_record('framing', 'WARN', msg, coverage=0.0, **met))
            elif pb['coverage'] < min_coverage:
                msg = (f"[framing] RE-RENDER REQUIRED: shot {name} frame {f}: the subject covers only "
                       f"{pb['coverage'] * 100:.1f}% of the frame (a speck). Frame the SUBJECT's bounds, not the scene's.")
                out.append(_record('framing', 'WARN', msg, coverage=round(pb['coverage'], 4), **met))
            else:
                msg = (f"[framing] OK: shot {name} frame {f}: the subject covers {pb['coverage'] * 100:.0f}% of the frame"
                       + (' (cut by the frame edge)' if pb['cut'] else ''))
                out.append(_record('framing', 'PASS', msg, cls='REVIEW', coverage=round(pb['coverage'], 4),
                                   cut=pb['cut'], box=[round(v, 3) for v in pb['box']], **met))
            if log:
                print(msg, flush=True)
    scene.frame_set(keep)
    return out


def sharp_share(scene, cam, grid=(32, 18), depsgraph=None, lim=None):
    """The share of the picture that is sharp: a grid of rays through the frame, each first surface's view depth
    against the depth of field at the camera's focus (instances count; a ray that meets nothing is sharp only when
    the far limit is infinite). Returns (share, limits)."""
    dg = depsgraph or bpy.context.evaluated_depsgraph_get()
    lim = lim or C.dof_limits(cam, max(C.focus_depth(cam), 1e-3))
    m = cam.matrix_world
    fwd = -(m.to_3x3() @ Vector((0.0, 0.0, 1.0))).normalized()
    nx, ny = grid
    sharp = 0
    for j in range(ny):
        for i in range(nx):
            o, d = C.frame_ray(scene, cam, ((i + 0.5) / nx, (j + 0.5) / ny))
            o = o + d * (cam.data.clip_start / max(d.dot(fwd), 1e-6))      # what the near clip cuts away is not seen
            ok, loc, _n, _k, _ob, _m = scene.ray_cast(dg, o, d, distance=cam.data.clip_end)
            if ok:
                z = (loc - m.translation).dot(fwd)
                sharp += lim['near'] <= z <= lim['far']
            else:
                sharp += lim['far'] == math.inf
    return sharp / float(nx * ny), lim


def _spans_for(allow, name):
    if not allow:
        return []
    v = allow.get(name, []) if isinstance(allow, dict) else allow
    if v and isinstance(v[0], (int, float)):
        v = [v]
    return [(int(a), int(b)) for a, b in v]


def _frame_runs(frames, every):
    """Sampled frames -> runs [first, last] of frames no more than `every` apart."""
    runs = []
    for f in frames:
        if runs and f - runs[-1][1] <= every:
            runs[-1][1] = f
        else:
            runs.append([f, f])
    return runs


def focus_audit(scene, subject, cam=None, span=None, every=6, allow_soft=None, min_sharp=0.01, grid=(32, 18),
                log=True):
    """Focus, per shot, every `every` frames. Two questions, both in view depth (the depth Blender's depth of field
    measures):
      - camera.focus: is the subject (a target spec: a bone, an object) inside the depth of field at the focus
        distance? Soft frames are reported as RUNS, one record each, so a regression late in a shot is not hidden
        behind the shot's worst frame. allow_soft: frames where a soft subject is intended, [(first, last)] or
        {shot: (first, last)} (a rack's start on something else): recorded as INFO, not as a warning.
      - camera.focus_sharp: is ANYTHING in the picture sharp? sharp_share over a grid of rays; under min_sharp the
        focus sits on something off-screen or in empty air (the audience sees a soft frame and no subject). Checked in
        allowed spans too.
    Returns ledger records."""
    keep = scene.frame_current
    tfn = C.target_fn(subject)
    out = []
    for name, (fa, fb, c) in _shots(scene, cam, span).items():
        if not c.data.dof.use_dof:
            out.append(_record('camera.focus', 'PASS', f'[focus] shot {name}: no depth of field (everything sharp)',
                               cls='INFO', shot=name))
            continue
        allowed = _spans_for(allow_soft, name)
        rows = []
        for f in range(fa, fb + 1, max(1, every)):
            scene.frame_set(f)
            dg = bpy.context.evaluated_depsgraph_get()
            fd = C.focus_depth(c)
            lim = C.dof_limits(c, max(fd, 1e-3))
            sd = C.view_depth(c, tfn())
            margin = min(sd - lim['near'], lim['far'] - sd)          # metres inside the sharp zone (< 0: outside)
            share, _l = sharp_share(scene, c, grid, dg, lim)
            rows.append({'f': f, 'margin': margin, 'sd': sd, 'fd': fd, 'lim': lim, 'share': share,
                         'allowed': any(a <= f <= b for a, b in allowed)})
        e = max(1, every)

        def run_records(sel, check, verdict, cls, text):
            for a, b in _frame_runs([r['f'] for r in rows if sel(r)], e):
                rs = [r for r in rows if a <= r['f'] <= b]
                w = min(rs, key=lambda r: r['margin'] if check == 'camera.focus' else r['share'])
                lim = w['lim']
                met = dict(shot=name, camera=c.name, frames=[a, b], frame=w['f'], subject_m=round(w['sd'], 3),
                           focus_m=round(w['fd'], 3), near_m=round(lim['near'], 3),
                           far_m=round(lim['far'], 3) if lim['far'] != math.inf else None,
                           sharp_share=round(w['share'], 4))
                msg = text(a, b, w, lim)
                out.append(_record(check, verdict, msg, cls=cls, **met))
                if log:
                    print(msg, flush=True)

        soft = lambda r: r['margin'] < 0
        run_records(lambda r: soft(r) and not r['allowed'], 'camera.focus', 'WARN', 'REVIEW',
                    lambda a, b, w, lim: (f"[focus] shot {name}: the subject is SOFT at frames {a}-{b} (worst {w['f']}: "
                                          f"{w['sd']:.2f} m deep, sharp from {lim['near']:.2f} to {lim['far']:.2f} m; "
                                          f"focus {w['fd']:.2f} m, f/{lim['fstop']:g}, {lim['lens']:.0f} mm)"))
        run_records(lambda r: soft(r) and r['allowed'], 'camera.focus', 'PASS', 'INFO',
                    lambda a, b, w, lim: (f"[focus] shot {name}: the subject is soft at frames {a}-{b} by design "
                                          f"(allowed; focus {w['fd']:.2f} m, the subject {w['sd']:.2f} m)"))
        if not any(soft(r) and not r['allowed'] for r in rows):
            ok = [r for r in rows if not soft(r)] or rows
            w = min(ok, key=lambda r: r['margin'])
            lim = w['lim']
            msg = (f"[focus] OK: shot {name}: the subject stays inside the depth of field"
                   + (' outside the allowed soft frames' if allowed else '')
                   + f" (closest call frame {w['f']}: {w['sd']:.2f} m in {lim['near']:.2f}-{lim['far']:.2f} m)")
            out.append(_record('camera.focus', 'PASS', msg, cls='REVIEW', shot=name, camera=c.name, frame=w['f'],
                               subject_m=round(w['sd'], 3), focus_m=round(w['fd'], 3), near_m=round(lim['near'], 3),
                               far_m=round(lim['far'], 3) if lim['far'] != math.inf else None))
            if log:
                print(msg, flush=True)
        run_records(lambda r: r['share'] < min_sharp, 'camera.focus_sharp', 'WARN', 'REVIEW',
                    lambda a, b, w, lim: (f"[focus] shot {name}: NOTHING in the picture is sharp at frames {a}-{b} "
                                          f"(worst {w['f']}: {w['share'] * 100:.1f}% of the frame inside "
                                          f"{lim['near']:.2f}-{lim['far']:.2f} m): the focus ({w['fd']:.2f} m) sits on "
                                          f"something off-screen or in empty air. Rack from a mark in the picture "
                                          f"(camera.point_in_frame)."))
        if all(r['share'] >= min_sharp for r in rows):
            w = min(rows, key=lambda r: r['share'])
            msg = (f"[focus] OK: shot {name}: something in the picture is sharp at every checked frame (least: "
                   f"{w['share'] * 100:.0f}% of the frame at frame {w['f']})")
            out.append(_record('camera.focus_sharp', 'PASS', msg, cls='REVIEW', shot=name, camera=c.name,
                               frame=w['f'], sharp_share=round(w['share'], 4)))
            if log:
                print(msg, flush=True)
    scene.frame_set(keep)
    return out
