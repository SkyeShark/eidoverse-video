"""Quality gates for the forge's meshes (printed every run; the robot body's habit: flags answered by construction).

quad_quality: per quad, its normal against the shape's own normal (the SDF gradient at its centre projected onto the
surface): a FOLD where they oppose (dot < 0) and a TILT where they disagree > 60 deg; the smallest corner angle; the
aspect (longest over shortest edge). Summarised per region with the worst places listed.
"""
import numpy as np


def quad_quality(mesh, prog=None, region_names=None, worst=6):
    V, Q = mesh.V, mesh.Q
    c = V[Q].mean(1)
    n = np.cross(V[Q[:, 2]] - V[Q[:, 0]], V[Q[:, 3]] - V[Q[:, 1]])
    nl = np.linalg.norm(n, axis=1)
    n = n / np.maximum(nl, 1e-20)[:, None]
    e = [V[Q[:, (k + 1) % 4]] - V[Q[:, k]] for k in range(4)]
    el = np.stack([np.linalg.norm(x, axis=1) for x in e], 1)
    ang = []
    for k in range(4):
        a, b = -e[(k - 1) % 4], e[k]
        cs = (a * b).sum(1) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-20)
        ang.append(np.degrees(np.arccos(np.clip(cs, -1, 1))))
    ang = np.stack(ang, 1)
    out = dict(min_angle=ang.min(1), aspect=el.max(1) / np.maximum(el.min(1), 1e-12), area=0.5 * nl)
    if prog is not None:
        # the shape's normal at the quad centre PROJECTED along the quad's normal: a centre just under a thin sheet
        # reads the sheet's far side (t04d: all 16 crown-top "folds" were centres 0.67 mm under the web margin,
        # dot -0.82 there, +0.89..+0.96 at their projections). A truly folded quad's normal points in, its projection
        # finds no crossing, and it is judged at its centre as before
        p, st = prog.project(c + n * 0.004, n, maxd=0.02)
        g = prog.normals(np.where((st == 0)[:, None], p, c))
        out['dot'] = (n * g).sum(1)
    reg = mesh.attrs['part'][Q].mean(1).argmax(1) if 'part' in mesh.attrs else np.zeros(len(Q), int)
    out['region'] = reg
    if 'fixed' in mesh.attrs and 'dot' in out:
        # designed off the shape (a lid's tuck, a lumen facing inward): the shape's normal does not judge them
        fq = mesh.attrs['fixed'][Q][:, :, 0].max(1) > 0.5
        out['dot'] = np.where(fq, 1.0, out['dot'])
    names = region_names or {}
    lines = []
    for r in np.unique(reg):
        m = reg == r
        s = f'  {names.get(int(r), str(r)):>10s}: {m.sum():6d} quads  min angle p1 {np.percentile(out["min_angle"][m], 1):5.1f}' \
            f'  aspect p99 {np.percentile(out["aspect"][m], 99):5.1f}'
        if 'dot' in out:
            s += f'  FOLDS {int((out["dot"][m] < 0).sum()):4d}  tilts>60 {int((out["dot"][m] < 0.5).sum()):4d}'
        lines.append(s)
    if 'dot' in out:
        for r in np.unique(reg):
            m = np.nonzero((reg == r) & (out['dot'] < 0.5))[0]
            if not len(m):
                continue
            bad = m[np.argsort(out['dot'][m])[:worst]]
            lines.append(f'  worst {names.get(int(r), r)}: ' + '; '.join(
                f'dot {out["dot"][q]:+.2f} asp {out["aspect"][q]:.0f} at {np.round(c[q], 3).tolist()}' for q in bad))
    return out, '\n'.join(lines)
