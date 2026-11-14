"""THE OUTFIT: every garment built, draped, constructed, unwrapped, baked, skinned and written onto the human, in layer
order (the shoes; the trousers over the body and on the shoes; the top over the body and the trousers), each layer
cached by (the body's pheno hash, the garment, the layers under it, the forge's version).

    G = forge_garment(B, fr, name, under, cache_dir)   ->  dict of the garment (T rest mesh, weights, UVs, maps, records)
    write_outfit(B, garments, out_glb)
"""
import hashlib
import json
import os
import time

import numpy as np
from scipy import ndimage
from PIL import Image

from . import pattern, drape, skin, construct, shoes, maps, weave, meshops as mo
from .body import vertex_normals, texel_density

VERSION = 'b2b-outfit-3'      # (B2b) darts, the legs' hang, the strips' UV width, the collar, the culls, the tie;
#                               3: the envelope blurred down the body, the strips' tangent directions (re-drape)
A_DEG = 45.0
# (B2b) B2_SIZE_SCALE (env, default 1): a dry run's maps at a fraction of the size (the code's paths at a test's memory;
# never cached beside the real ones: d04 takes its cache dir from B2_CACHE then)
_SCALE = float(os.environ.get('B2_SIZE_SCALE', '1'))
SIZE = {k: int(v * _SCALE) for k, v in {'tee': 4096, 'shirt_ss': 4096, 'shirt_ls': 4096, 'trousers': 4096,
                                         'shoes': 2048}.items()}
SLEEVE_SPLIT = pattern.SLEEVE_SPLIT      # the armscye (B2b: the panel borders are pattern.seam_fields' edge chains)


def _key(B, name, under):
    h = hashlib.sha1(f'{VERSION}|{B.pheno_hash()}|{name}|{",".join(under)}'.encode()).hexdigest()[:10]
    return f'{B.sex}_{name}_{h}'


def _body_A(B):
    Vw, Fw, wid, rep = B.welded()
    J4w, W4w = B.J4[rep], B.W4[rep]
    return (lambda t: B.lbs(B.apose(A_DEG * t), V=Vw, J4=J4w, W4=W4w)), Fw


# ------------------------------------------------------------------------------------------------ panels
def panels_top(fr, Vp, F):
    c = Vp[F].mean(1)
    s = fr.arm_s(c)
    th, _ = fr.torso_cyl(c)
    # the body's halves share their texels (the body is mirrored, the drape symmetric): front / back each split at the
    # centre line (a UV cut only: a tee has no centre seam), the right half the twin of the left
    lab = np.where(np.abs(th) < np.pi / 2, 0, 1) + np.where(c[:, 0] < 0, 6, 0)
    sl = s > SLEEVE_SPLIT
    # a sleeve is a tube: two islands (upper / under), split along the arm's top and its underarm (a UV cut only)
    _, ar = fr.arm_cyl(c)
    up = (c[:, 1] - fr.arm_axis[0]) > 0
    lab = np.where(sl & (c[:, 0] > 0), np.where(up, 2, 4), lab)
    lab = np.where(sl & (c[:, 0] < 0), np.where(up, 3, 5), lab)
    names = {0: 'front_L', 1: 'back_L', 2: 'sleeve_top_L', 3: 'sleeve_top_R', 4: 'sleeve_under_L', 5: 'sleeve_under_R',
             6: 'front_R', 7: 'back_R'}
    cuts = {(2, 4), (3, 5), (0, 6), (1, 7)}
    return lab, names, cuts, {3: 2, 5: 4, 6: 0, 7: 1}


def panels_bottom(fr, Vp, F):
    c = Vp[F].mean(1)
    zax = pattern.leg_zax(fr, c[:, 1])
    front = c[:, 2] > zax
    lab = np.where(c[:, 0] > 0, np.where(front, 0, 1), np.where(front, 2, 3))
    names = {0: 'front_L', 1: 'back_L', 2: 'front_R', 3: 'back_R'}
    return lab, names, set(), {2: 0, 3: 1}


# ------------------------------------------------------------------------------------------------ the forge
def forge_garment(B, fr, name, under=(), cache_dir=None, log=print, frames=150):
    """one garment on this body (T rest out), its layers under it given as forged garments"""
    key = _key(B, name, [u['key'] for u in under])
    if cache_dir:
        p = os.path.join(cache_dir, key, 'garment.npz')
        if os.path.exists(p):
            d = dict(np.load(p, allow_pickle=True))
            d['rec'] = json.loads(str(d['rec']))
            d['key'] = key
            for k in ('albedo', 'normal', 'orm', 'masks'):
                d[k] = np.asarray(Image.open(os.path.join(cache_dir, key, f'T_{k}.png')))
            log(f'[outfit] {key}: from the cache')
            return d
    t0 = time.time()
    body_at, Fw = _body_A(B)
    if name == 'shoes':
        d = _forge_shoes(B, fr, log)
    else:
        d = _forge_cloth(B, fr, name, under, body_at, Fw, log, frames,
                         stage_dir=os.path.join(cache_dir, key) if cache_dir else None)
    d['key'] = key
    d['rec']['seconds'] = round(time.time() - t0, 1)
    if cache_dir:
        os.makedirs(os.path.join(cache_dir, key), exist_ok=True)
        for k in ('albedo', 'normal', 'orm', 'masks'):
            Image.fromarray(d[k]).save(os.path.join(cache_dir, key, f'T_{k}.png'))
        np.savez(os.path.join(cache_dir, key, 'garment.npz'),
                 **{k: v for k, v in d.items() if k not in ('albedo', 'normal', 'orm', 'masks', 'rec', 'key')},
                 rec=json.dumps(d['rec']))
    log(f'[outfit] {key}: forged in {time.time() - t0:.0f} s')
    return d


def _forge_cloth(B, fr, name, under, body_at, Fw, log, frames, stage_dir=None):
    spec = pattern.SPECS[name]
    r = pattern.build(fr, name)
    Vp, F, Vr = r['V_skin'], r['F'], r['V_rest']        # Vp: the pattern's coordinates (on the skin / the extension)
    if len(Vp) < len(Vr):
        Vp = np.concatenate([Vp, Vr[len(Vp):]])
    cols = [(body_at, Fw)]
    for u in under:
        cols.append((u['X_A'], u['F_all']))
    pins = None
    if spec['kind'] == 'bottom':
        pins = max(mo.boundary_loops(F), key=lambda l: Vr[l, 1].mean())
    body_A = body_at(1.0)
    Vr2, F2, _ = mo.subdivide(Vr, F)
    dp = os.path.join(stage_dir, 'drape.npz') if stage_dir else None
    if dp and os.path.exists(dp):
        z = np.load(dp, allow_pickle=True)
        X, X2, rep, rep2 = z['X'], z['X2'], json.loads(str(z['rep'])), json.loads(str(z['rep2']))
        log(f'[outfit] {name}: the drape from the stage cache')
    else:
        X, rep = drape.drape(Vr, F, spec['fabric'], cols, frames=frames, ramp=(0.1, 1.2), pins=pins, log=log)
        # THE HIGH: one level finer, draped again from the low's shape on the body at the A-pose (its own fine folds)
        X2s, _, _ = mo.subdivide(X, F)
        cols2 = [(body_A, Fw)] + [(u['X_A'], u['F_all']) for u in under]
        pins2 = None
        if pins is not None:
            loops2 = mo.boundary_loops(F2)
            pins2 = max(loops2, key=lambda l: Vr2[l, 1].mean())
        X2, rep2 = drape.drape(Vr2, F2, spec['fabric'], cols2, frames=40, settle=40, ramp=(0.0, 0.0), pins=pins2,
                               X_start=X2s, pin_target=X2s, log=log, tether=0.004)
        if dp:
            os.makedirs(stage_dir, exist_ok=True)
            np.savez(dp, X=X, X2=X2, rep=json.dumps(rep), rep2=json.dumps(rep2))
    # THE HIGH = the low's own surface (subdivided) + only the FINE part of the high drape's displacement: its slow drift
    # off the low (a few mm sideways over a panel) baked as a tilt of every texel (5 deg on average), which the mirrored
    # twin half then turned the other way: a tone step down the centre line in the engine (look/e02). High-passed here.
    X2s, _, _ = mo.subdivide(X, F)
    D = X2 - X2s
    L2 = mo.laplacian(X2s, F2)
    Ds = D.copy()
    for _ in range(60):
        Ds = Ds + 0.5 * (L2 @ Ds)
    X2 = X2s + (D - Ds) * drape.FABRIC[spec['fabric']].get('high_detail', 1.0)
    # ------------------------------------------------------------------ construction on the low (A-pose)
    loops = mo.boundary_loops(F)
    kinds = _opening_kinds(fr, spec, Vp, loops)
    rimsV, rimsF, rimsShare = [], [], []
    nV = len(X)
    for lp, kd in zip(loops, kinds):
        w = {'hem': spec['hem_w'], 'sleeve': spec.get('sleeve_hem_w', spec['hem_w']), 'neck': 0.012,
             'waist': 0.020, 'leg': spec['hem_w']}[kd]
        NV, NF, share = construct.rim(X, F, lp, min(w, 0.02), drape.FABRIC[spec['fabric']]['thick'] + 0.0006)
        rimsV.append(NV)
        rimsF.append(NF + 0)
        rimsShare.append(share)
    # the faces of the rims index the low + all rims' vertices in order
    allV = [X]
    allF = [F]
    share_src = [np.arange(nV)]
    off = nV
    for NV, NF, share in zip(rimsV, rimsF, rimsShare):
        NF = np.where(NF >= nV, NF - nV + off, NF)
        allV.append(NV)
        allF.append(NF)
        share_src.append(share)
        off += len(NV)
    extra_parts = []
    ctag = None
    if spec['neck'] == 'collar' if spec['kind'] == 'top' else False:
        nl = loops[kinds.index('neck')]
        nl = _order_loop_ccw(X, nl)
        neck_c = fr.neck.mean(0)
        # (B2b) the stand and fall on the neck's own axis, the stand's gap read off the neck's skin (skin_HEAD above
        # the neck ring, skin_BODY below; neither moves in the A-pose)
        HV, HF, _, _ = _head(B)
        skinV = np.concatenate([body_A, HV])
        skinF = np.concatenate([Fw, HF + len(body_A)])
        up = B.joint_pos('head') - B.joint_pos('neck_01')
        CV, CF, ctag = construct.collar2(X[nl], neck_c, up, (skinV, skinF), (X, F),
                                         construct.COLLAR['F' if B.sex == 'F' else 'M'])
        extra_parts.append(('collar', CV, CF))
        # buttons: the placket's 7, the collar band's, the cuffs'
        BV, BF = _buttons(fr, spec, X, F, Vp, ctag['front'])
        extra_parts.append(('buttons', BV, BF))
    # ------------------------------------------------------------------ panels, UVs (the low panels + extras)
    if spec['kind'] == 'top':
        lab, pnames, cuts, twins_p = panels_top(fr, Vp, F)
    else:
        lab, pnames, cuts, twins_p = panels_bottom(fr, Vp, F)
    mir, md = maps.mirror_map(Vp, tol=0.006)
    twins = {p: (m, mir) for p, m in twins_p.items()}
    size = SIZE[name]
    dens_t = maps.TARGET_PX_PER_M * _SCALE
    U = maps.unwrap(X, F, lab, twins=twins, size=size, extra=[(v, f) for _, v, f in extra_parts], density=dens_t)
    # a long-legged phenotype's trousers overflow the sheet at 3,600 px/m: the density steps down toward the body's
    # 3,430 (never under it) before the sheet is called too small
    while U['used'] > 1.0 and dens_t > 3430.0 * _SCALE:
        dens_t = max(3430.0 * _SCALE, dens_t * 0.98)
        U = maps.unwrap(X, F, lab, twins=twins, size=size, extra=[(v, f) for _, v, f in extra_parts], density=dens_t)
        log(f'[outfit] {name}: the density stepped to {dens_t:.0f} px/m: {U["used"] * 100:.0f} % of the sheet')
    log(f'[outfit] {name}: islands packed, {U["used"] * 100:.0f} % of the sheet height; mirror matches '
        f'{(mir >= 0).mean() * 100:.1f} % (d p99 {np.percentile(md, 99) * 1000:.1f} mm)')
    if U['used'] > 1.0:
        raise RuntimeError(f'{name}: the islands overflow the {size} sheet ({U["used"]:.2f})')
    # ------------------------------------------------------------------ the bake (masters only: twins share the texels)
    Fs, src = U['Fs'], U['src']
    Xs = X[src]
    N, TAN = maps.frames(Xs, Fs, U['UV'])
    master = ~np.isin(lab, list(twins_p.keys()))
    low = dict(V=Xs, F=Fs[master], UV=U['UV'], N=N, TAN=TAN, piece=np.zeros(int(master.sum()), np.int32))
    # (B2b) the AO's occluders: the body WITHOUT its arms (an arm is wherever the clip puts it: the A-pose's arm baked a
    # dark patch into the sleeve's underside and the torso's flanks, round 1's blotches; the engine's AO draws the
    # arm's), the layers under; out to 2.5 cm (the folds' and the seams' scale)
    fpart = _part(fr, fr.Vw[Fw].mean(1))
    occ = [(body_A, Fw[fpart == 0])] + [(u['X_A'], u['F_all']) for u in under]
    from .. import bake_mesh
    bk = bake_mesh.bake(low, [dict(V=X2, F=F2)], size, occluders=occ, ss=2, cage=0.012, ao_r=0.025, cav_r=0.003,
                        n_ao=32, log=log)
    for k in ('position', 'low_point', 'base', 'thickness', 'region', 'cavity'):
        bk.pop(k, None)                       # 4096^2 vec4 buffers: the compose's memory
    # the extras (collar, buttons) baked on themselves (their own high: the low; AO against the body and the cloth)
    ex_uv = U['extra_uv']
    exV, exF, exUV = [], [], []
    for (nm, v, f), uv in zip(extra_parts, ex_uv):
        exV.append(v)
        exF.append(f)
        exUV.append(uv)
    # ------------------------------------------------------------------ the maps
    out = _compose_cloth(fr, spec, name, size, U, X, F, Vp, lab, pnames, cuts, twins_p, loops, kinds, bk, extra_parts,
                         body_A, Fw, under)
    # ------------------------------------------------------------------ the full game mesh (A), then T by unposing
    meshV = [Xs]
    meshF = [Fs]
    meshUV = [U['UV']]
    meshSrc = [src]                         # for weights: the low vertex each mesh vertex follows
    off = len(Xs)
    # rims (B2b): each strip in its edge's own panel, its UVs WITH WIDTH: the fold row on the edge's texels, the inside
    # row on the texels of the outer surface right above it (the hem's inside is the same cloth turned back; round 1
    # gave the whole strip its edge's UV, so 6.5 % of the tee's area had ~0 px/m: the check's finding)
    rV, rF, rUV, rS = _rims_uv(X, F, lab, U, loops, rimsV, rimsF, rimsShare, nV, off)
    for v_, f_, uv_, s_ in zip(rV, rF, rUV, rS):
        meshV.append(v_)
        meshF.append(f_)
        meshUV.append(uv_)
        meshSrc.append(s_)
        off += len(v_)
    # extras: their own UVs; weights from the nearest low vertex
    from scipy.spatial import cKDTree
    tree = cKDTree(X)
    collar = None
    for (nm, v, f), uv in zip(extra_parts, ex_uv):
        if nm == 'collar':
            collar = (off, off + len(v), ctag)
        meshV.append(v)
        meshF.append(f + off)
        meshUV.append(uv)
        meshSrc.append(tree.query(v)[1])
        off += len(v)
    MV = np.concatenate(meshV)
    MF = np.concatenate(meshF)
    MUV = np.concatenate(meshUV)
    MS = np.concatenate(meshSrc)
    return _finish(B, fr, name, spec, X, F, MV, MF, MUV, MS, out, rep, rep2, U, size, bk, extra_parts, Vp, under,
                   collar=collar)


_HEADS = {}


def _head(B):
    """skin_HEAD (T rest = the A-pose: the head and neck do not move in it): V, F, its dense weights, a KD tree"""
    if B.path not in _HEADS:
        from .body import Body
        H = Body(B.path, mesh='skin_HEAD')
        D = np.zeros((len(H.V), len(B.jnames)))
        np.add.at(D, (np.repeat(np.arange(len(H.V)), 4), H.J4.ravel()), H.W4.ravel())
        _HEADS[B.path] = (H.V, H.F, D, H)
    return _HEADS[B.path]


def _finish(B, fr, name, spec, X, F, MV, MF, MUV, MS, out, rep, rep2, U, size, bk, extra_parts, Vp, under=(),
            collar=None):
    # weights: transferred from the body in the A-pose (the draped cloth's own place), then the same field for every
    # construction vertex through the low vertex it follows; T by unposing with the A-pose's matrices
    mats_A = B.skin_mats(B.apose(A_DEG))
    # THE WEIGHTS: the skin's at the cloth's closest point WHERE IT HANGS (the drape slides cloth: a pattern point's
    # weights put a vertex that slid 5 cm on the wrong bone, g01 second run), but only among the skin of the cloth's OWN
    # PART (its pattern point's: an arm or the rest): a free nearest point gave the sleeve's underside the torso's weights
    # and the swinging arm went out through it (57 mm, g01 first run)
    Vw, Fw, wid, rep_ = B.welded()
    body_A = B.lbs(B.apose(A_DEG), V=Vw, J4=B.J4[rep_], W4=B.W4[rep_])
    J4, W4, sd = _transfer_A(B, fr, X, F, Vp, body_A, Fw, rep_, under)
    MJ, MW = J4[MS], W4[MS]
    stand = None
    if collar is not None:
        # (B2b) THE COLLAR MOVES PARTLY WITH THE NECK: the stand's top and the roll take half the neck skin's weights
        # (its closest point), easing to the shirt's at the seam and at the fall's edge (it lies on the shirt): a stand
        # on the shoulders' weights alone let the turning neck through it (the check: neck_01 points up to 14 mm)
        c0, c1, tg = collar
        HV, HF, HD, _ = _head(B)
        a = np.where(tg['part'] == 0, 0.5 * tg['t'], 0.5 * (1.0 - tg['t']) ** 2)
        Dsh = np.zeros((c1 - c0, len(B.jnames)))
        np.add.at(Dsh, (np.repeat(np.arange(c1 - c0), 4), MJ[c0:c1].ravel()), MW[c0:c1].ravel())
        q, t, bc, _ = mo.closest_on_mesh(HV, HF, MV[c0:c1])
        Dhd = np.einsum('nk,nkj->nj', bc, HD[HF[t]])
        MJ[c0:c1], MW[c0:c1] = skin.top4(Dsh * (1 - a[:, None]) + Dhd * a[:, None])
        stand = dict(range=(c0, c1), part=tg['part'], top_drop=tg['top_drop'])
    MT = B.unlbs(MV, MJ, MW, mats_A)
    XT = B.unlbs(X, J4, W4, mats_A)
    N, TAN = maps.frames(MT, MF, MUV)
    # (B2b) the density over EVERY face drawn (panels, the turn-back strips, the collar, the buttons): round 1 counted
    # the panels only and missed the strips' collapse
    dens = texel_density(MT, MF, MUV, size)
    dens_p = texel_density(MT, MF[:len(U['Fs'])], MUV, size)
    rec = dict(garment=name, kind=spec['kind'], fabric=spec['fabric'], sex=B.sex, triangles=int(len(MF)),
               vertices=int(len(MV)), drape=rep, drape_high=rep2, density_px_per_m=dens,
               density_panels_px_per_m=dens_p, size=size,
               sheet_height=float(U['used']), bake_gate=bk['gate'], bake_ok=bool(bk['gate_ok']),
               weave_tile_mm=weave.TILE_MM[spec['fabric']], zones=out['zones'])
    d = dict(V=MT, F=MF, UV=MUV, N=N, TAN=TAN, J4=MJ, W4=MW, X_A=X, F_low=F, XT_low=XT, J4_low=J4, W4_low=W4,
             F_all=F, albedo=out['albedo'], normal=out['normal'], orm=out['orm'], masks=out['masks'], rec=rec)
    if stand is not None:
        # the collar's own vertices in the mesh and which are the stand's (the neck's cull reads them)
        d['collar_range'] = np.array(stand['range'], np.int64)
        d['collar_part'] = stand['part'].astype(np.int8)
        d['collar_top_drop'] = stand['top_drop'].astype(np.float32)
    return d


def _rims_uv(X, F, lab, U, loops, rimsV, rimsF, rimsShare, nV, off0):
    """(B2b) the turn-back strips as mesh pieces with their own UV width. Each loop edge's strip (construct.rim: four
    faces per edge, in loop order) belongs to the panel of the low face on that edge: its outer corners are that face's
    split vertices, its fold row r1 takes the edge's UVs, its inside row r2 the UV of the outer surface at r2's closest
    point on that panel (the texel right above it). Strip vertices are split only where the panel changes along the
    loop. Returns per strip (V, F into the mesh, UV, the low vertex each follows)."""
    Fs, UVs = U['Fs'], U['UV']
    ef = {}
    for t, tri in enumerate(F):
        for c in range(3):
            ef[(int(tri[c]), int(tri[(c + 1) % 3]))] = t
    outV, outF, outUV, outS = [], [], [], []
    off = off0
    for lp, NV, NF, share in zip(loops, rimsV, rimsF, rimsShare):
        k = len(lp)
        NF4 = np.asarray(NF).reshape(k, 4, 3)
        key, V_, S_, UV_, need = {}, [], [], [], []
        faces = []
        for i in range(k):
            a, b = int(lp[i]), int(lp[(i + 1) % k])
            t = ef.get((a, b), ef.get((b, a)))
            p = int(lab[t])
            ft = list(F[t])
            sa, sb = int(Fs[t][ft.index(a)]), int(Fs[t][ft.index(b)])
            for f3 in NF4[i]:
                tri = []
                for v in f3:
                    v = int(v)
                    if v < nV:
                        tri.append(sa if v == a else sb)
                        continue
                    j = v - nV
                    if (j, p) not in key:
                        key[(j, p)] = len(V_)
                        V_.append(NV[j])
                        S_.append(int(share[j]))
                        if j < k:
                            UV_.append(UVs[sa] if j == i else UVs[sb])
                            need.append(None)
                        else:
                            UV_.append(np.zeros(2))
                            need.append(p)
                    tri.append(off + key[(j, p)])
                faces.append(tri)
        V_ = np.asarray(V_)
        UV_ = np.asarray(UV_, float)
        need = np.array([-1 if q is None else q for q in need])
        for p in np.unique(need[need >= 0]):
            ids = np.nonzero(need == p)[0]
            fp = np.nonzero(lab == p)[0]
            q, tt, bc, _ = mo.closest_on_mesh(X[U['src']], Fs[fp], V_[ids])
            UV_[ids] = np.einsum('nk,nkj->nj', bc, UVs[Fs[fp][tt]])
        # the FOLD row its own sliver too: its UV moved off the edge, away from the inside row's, by the fold's depth
        # (the island's dilated padding carries the border's texels there; on the edge's UV the fold had 0 px/m)
        UV0 = UV_.copy()
        for (j, p), li in key.items():
            if j < k and (j + k, p) in key:
                l2 = key[(j + k, p)]
                t = np.linalg.norm(V_[li] - X[lp[j]]) / max(np.linalg.norm(V_[l2] - V_[li]), 1e-6)
                UV_[li] = UV0[li] + (UV0[li] - UV0[l2]) * min(t, 0.5)
        outV.append(V_)
        outF.append(np.asarray(faces, np.int64))
        outUV.append(UV_)
        outS.append(np.asarray(S_, np.int64))
        off += len(V_)
    return outV, outF, outUV, outS


def _part(fr, P):
    """0 the rest, 1 the left arm, 2 the right arm (on the T rest). (B2b: over the WAIST, a landmark, not y 1.0 m: the
    rebuilt base (hb1) and every phenotype re-drape by their own landmarks)"""
    arm = (np.abs(P[:, 0]) > fr.x_sh + 0.025) & (P[:, 1] > fr.waist_y)
    return np.where(arm, np.where(P[:, 0] > 0, 1, 2), 0)


def _transfer_A(B, fr, X, F, Vp, body_A, Fw, rep_, under=()):
    D = skin.body_weights_dense(B)[rep_]
    fpart = _part(fr, fr.Vw[Fw].mean(1))
    vpart = _part(fr, Vp)
    W = np.zeros((len(X), D.shape[1]))
    sd = np.zeros(len(X))
    for k in range(3):
        m = vpart == k
        fk = np.nonzero(fpart == k)[0]
        if not m.any() or not len(fk):
            continue
        q, t, bc, s = mo.closest_on_mesh(body_A, Fw[fk], X[m])
        W[m] = np.einsum('nk,nkj->nj', bc, D[Fw[fk][t]])
        sd[m] = s
    # (B2b) THE UNDERARM: within 8 cm of the armscye, on the sleeve's lower half, the cloth takes the weights of the
    # skin it lies on whichever part that is (the armpit's blend of the torso and the arm): the part rule alone gave
    # the sleeve's underarm the arm's weights over an armpit that keeps the torso's, and the lowered arms' armpits
    # went through the short sleeves in 368 of 390 frames (the dry run's g02)
    sa = fr.arm_s(Vp)
    ua = np.clip(1.0 - np.abs(sa - SLEEVE_SPLIT) / 0.08, 0.0, 1.0) * (Vp[:, 1] < fr.arm_axis[0]) * \
        (Vp[:, 1] > fr.waist_y + 0.05)                   # a top's armpit only (never a trouser's hip by the hand)
    if ua.any():
        m = ua > 0
        q, t, bc, s = mo.closest_on_mesh(body_A, Fw, X[m])
        Wall = np.einsum('nk,nkj->nj', bc, D[Fw[t]])
        W[m] = W[m] * (1 - ua[m, None]) + Wall * ua[m, None]
    # A LAYER moves with the layer under it: where the cloth lies within 4 cm of an inner garment (a top's hem over the
    # trousers) it takes that garment's weights at its closest point (the trousers' waist came out through the tee's hem
    # in the crouch: 399 points, g01)
    for u in under:
        if u['rec']['garment'] == 'shoes':
            continue
        Du = np.zeros((len(u['X_A']), D.shape[1]))
        np.add.at(Du, (np.repeat(np.arange(len(Du)), 4), u['J4_low'].ravel()), u['W4_low'].ravel())
        q, t, bc, s = mo.closest_on_mesh(u['X_A'], u['F_low'], X)
        Wu = np.einsum('nk,nkj->nj', bc, Du[u['F_low'][t]])
        # (B2b) THE POINT IT COVERS, not the nearest: a ray from the cloth inward along its normal meets the layer
        # under it, and the cloth takes the weights THERE (each covered point then stays behind its own cloth vertex
        # in every pose: the gap is carried, the hem never lifts off what it covers). The nearest point gave the tee's
        # plumb front a thigh's weights over the fly: it swung away in the walk and back into the belly in the crouch
        Nx = vertex_normals(X, F)
        hit, hp, fc_, bc_ = _ray_hits(u['X_A'], u['F_low'], X - Nx * 0.0005, -Nx, 0.08, full=True)
        if hit.any():
            Wr = np.einsum('nk,nkj->nj', bc_[hit], Du[u['F_low'][fc_[hit]]])
            Wu[hit] = Wr
            s = np.where(hit, np.linalg.norm(hp - X, axis=1), s)
        # (B2b) under the waist the top hangs plumb, 2-5 cm in front of the fly and the seat: its hem follows the layer
        # under it over a longer reach there (6.5 cm), or a forward-swinging thigh pushes the trousers through it
        # (the dry run: 87 trousers points through the tee's front hem in the walk)
        reach = np.where(Vp[:, 1] < fr.waist_y - 0.03, 0.065, 0.04)
        a = np.clip((reach - np.abs(s)) / 0.025, 0.0, 1.0) * (vpart == 0)
        # and the whole PLUMB band under the waist moves exactly as the layer under it, whatever the gap (same weights:
        # the gap is carried, never closed): a hem on the belly's weights let the swinging thigh's trousers through it
        # in the walk, on the thigh's only by distance it swung back into the belly in the crouch (the dry runs' g02)
        band = np.clip((fr.waist_y - Vp[:, 1]) / 0.06, 0.0, 1.0) * (vpart == 0)
        a = np.maximum(a, band)
        W = W * (1 - a[:, None]) + Wu * a[:, None]
        sd = np.where(a > 0, np.minimum(np.abs(sd), 0.01), sd)
    far = np.clip((np.abs(sd) - 0.02) / 0.02, 0.0, 1.0)
    L = mo.laplacian(X, F)
    for _ in range(12):
        W = W + 0.5 * far[:, None] * (L @ W)
    J4, W4 = skin.top4(W)
    return J4, W4, sd


def _opening_kinds(fr, spec, Vp, loops):
    out = []
    for lp in loops:
        c = Vp[lp].mean(0)
        if spec['kind'] == 'top':
            if fr.arm_s(c[None])[0] > 0.1:
                out.append('sleeve')
            elif c[1] > fr.bust_y:
                out.append('neck')
            else:
                out.append('hem')
        else:
            out.append('waist' if c[1] > fr.crotch_y else 'leg')
    return out


def _order_loop_ccw(X, lp):
    c = X[lp].mean(0)
    a = np.arctan2(X[lp, 0] - c[0], X[lp, 2] - c[2])
    return lp[np.argsort(a)]


def _buttons(fr, spec, X, F, Vp, band_front):
    """the placket's buttons (7), the collar band's (1), each cuff's (1)"""
    q_pts = []
    nrm = vertex_normals(X, F)
    front = (np.abs(Vp[:, 0]) < 0.006) & (Vp[:, 2] > fr.zc(Vp[:, 1]))
    yt = fr.B.socket('socket_chest')[1, 3] - 0.005
    ys = yt - 0.095 * np.arange(7)
    for y in ys:
        m = front & (np.abs(Vp[:, 1] - y) < 0.02)
        if m.any() and y > Vp[:, 1].min() + 0.06:
            i = np.nonzero(m)[0][np.argmin(np.abs(Vp[m, 1] - y))]
            q_pts.append((X[i], nrm[i], np.array([1.0, 0, 0])))
    # the collar band's: the stand's front, half way up (collar2's 'front')
    q_pts.append((band_front + np.array([0, 0.0, 0.001]), np.array([0, 0.1, 1.0]), np.array([1.0, 0, 0])))
    if 'cuff' in spec:
        s = fr.arm_s(Vp)
        for sg in (1, -1):
            m = (np.sign(Vp[:, 0]) == sg) & (np.abs(s - (spec['sleeve_s'] - 0.4 * spec['cuff'] / fr.arm_len)) < 0.01)
            if m.any():
                cand = np.nonzero(m)[0]
                i = cand[np.argmax(Vp[cand, 2])]
                q_pts.append((X[i], nrm[i], np.array([0, 1.0, 0])))
    BV, BF, off = [], [], 0
    for c, n, t in q_pts:
        v, f = construct.button(c + n * 0.0008, n, t)
        BV.append(v)
        BF.append(f + off)
        off += len(v)
    return np.concatenate(BV), np.concatenate(BF)


# ------------------------------------------------------------------------------------------------ the maps
def _compose_cloth(fr, spec, name, size, U, X, F, Vp, lab, pnames, cuts, twins_p, loops, kinds, bk, extra_parts,
                   body_A, Fw, under):
    Fs, src, UV = U['Fs'], U['src'], U['UV']
    px_mm = 1000.0 / (maps.TARGET_PX_PER_M * _SCALE)
    cov = bk['normal'][..., 3] > 0
    # the extras' coverage (collar / buttons): rasterised flat
    exF, exUV, off = [], [], 0
    for (nm, v, f), uv in zip(extra_parts, U['extra_uv']):
        exF.append(f + off)
        exUV.append(uv)
        off += len(v)
    ex_cov = np.zeros_like(cov)
    ex_kind = np.zeros(cov.shape, np.int32)
    if exF:
        EUV = np.concatenate(exUV)
        EF = np.concatenate(exF)
        kid = np.concatenate([np.full(len(v), k + 1.0) for k, (_, v, _) in enumerate(extra_parts)])
        a, fce = maps.raster(EUV, EF, kid, size)
        ex_cov = fce >= 0
        ex_kind = np.rint(a[..., 0]).astype(np.int32) * ex_cov
    # pattern coordinates per texel (the low's panels)
    attr = np.column_stack([Vp[src], U['lab']])
    A, fce = maps.raster(UV, Fs[~np.isin(lab, list(twins_p.keys()))], attr, size)
    P = A[..., :3]
    isl = np.where(fce >= 0, np.rint(A[..., 3]).astype(int), -1)
    # borders: openings (the low's boundary edges), seams (panel borders that are not UV-only cuts)
    E_open, E_seam = [], []
    bnd = set()
    for lp in loops:
        for i in range(len(lp)):
            a_, b_ = int(lp[i]), int(lp[(i + 1) % len(lp)])
            bnd.add((min(a_, b_), max(a_, b_)))
    Es = np.concatenate([Fs[:, [0, 1]], Fs[:, [1, 2]], Fs[:, [2, 0]]])
    key = np.sort(Es, axis=1)
    u_, inv, cnt = np.unique(key, axis=0, return_inverse=True, return_counts=True)
    bd = key[cnt[inv.ravel()] == 1]
    open_kind = {}
    for lp, kd in zip(loops, kinds):
        for i in range(len(lp)):
            a_, b_ = int(lp[i]), int(lp[(i + 1) % len(lp)])
            open_kind[(min(a_, b_), max(a_, b_))] = kd
    # each original edge's panels (the faces either side)
    edge_lab = {}
    for tri, l in zip(F, lab):
        for c in range(3):
            a_, b_ = int(tri[c]), int(tri[(c + 1) % 3])
            edge_lab.setdefault((min(a_, b_), max(a_, b_)), set()).add(int(l))
    seg_kind = {}
    for a_, b_ in bd:
        o = (min(src[a_], src[b_]), max(src[a_], src[b_]))
        if o in open_kind:
            seg_kind.setdefault(open_kind[o], []).append((a_, b_))
        else:
            ls = edge_lab.get(o, set())
            # a UV-only cut (a sleeve's tube opened along its top / underarm) draws nothing
            is_cut = len(ls) == 2 and tuple(sorted(ls)) in {tuple(sorted(c)) for c in cuts}
            seg_kind.setdefault('cut' if is_cut else 'seam', []).append((a_, b_))
    zone_main = cov.astype(np.float32)
    zone_trim = np.zeros(cov.shape, np.float32)
    H = np.zeros(cov.shape, np.float32)
    big = 1e6
    isl_d = ndimage.grey_dilation(isl, size=5)

    def dist_to(kind):
        segs = seg_kind.get(kind, [])
        if not segs:
            return np.full(cov.shape, big, np.float32), None
        m = maps.draw_lines(UV, segs, size, width_px=1)
        d, ind = ndimage.distance_transform_edt(~m, return_indices=True)
        same = isl_d[ind[0], ind[1]] == isl
        d = np.where(same, d, big)
        phase = (ind[0] + ind[1]) * px_mm * 0.7071
        return d.astype(np.float32), phase
    ds, ph_s = dist_to('seam')
    if ph_s is None:
        ph_s = np.zeros(cov.shape)
    Hc = np.zeros(cov.shape, np.float32)
    trim = np.zeros(cov.shape, np.float32)
    for kd in ('hem', 'sleeve', 'neck', 'waist', 'leg'):
        d, ph = dist_to(kd)
        if ph is None:
            continue
        w = {'hem': spec['hem_w'], 'sleeve': spec.get('sleeve_hem_w', spec['hem_w']), 'neck': 0.018 if spec.get(
            'neck') == 'crew' else 0.008, 'waist': spec.get('waistband', 0.02), 'leg': spec['hem_w']}[kd] * 1000
        Hc += maps.construction_height(cov, np.full(cov.shape, big), d, px_mm, w, ph_s, ph) - 0.0
        if kd == 'neck' and spec.get('neck') == 'crew':
            rib = (d * px_mm < w) & cov
            trim += rib
            # the rib's wales across the band (1 x 1 rib, 1.2 mm)
            Hc += rib * 0.18 * np.cos(2 * np.pi * ph / 1.2)
    Hc += maps.construction_height(cov, ds, np.full(cov.shape, big), px_mm, 0.0, ph_s, ph_s)
    # the garment's own lines from the pattern coordinates
    Hc += _pattern_lines(fr, spec, name, P, isl, pnames, cov, px_mm)
    # the extras: the collar's edge stitch, the buttons' four holes
    if exF:
        exd, exind = ndimage.distance_transform_edt(ex_cov, return_indices=True)
        phase = (exind[0] + exind[1]) * px_mm * 0.7071
        coll = ex_kind == 1
        Hc += coll * (maps.stitch(exd * px_mm, 5.0, phase) + 0.3 * np.clip(1 - exd * px_mm / 1.2, 0, 1))
        btn = ex_kind == 2
        trim += btn
    Nd = maps.height_to_normal(Hc, px_mm, strength=1.0)
    nb = bk['normal'][..., :3].astype(np.float64)
    nb = np.where(cov[..., None], nb, np.array([0, 0, 1.0]))
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True) + 1e-12
    Nf = maps.combine_normals(nb, Nd)
    allcov = cov | ex_cov
    nrm8 = maps.to_u8(maps.dilate(Nf * 0.5 + 0.5, allcov))
    ao = np.where(cov, bk['ao'], 1.0)
    ao = np.where(ex_cov, 0.85, ao)
    curv = np.where(cov, bk['curvature'], 0.0)
    # albedo: the undyed cloth (luminance), the thread a little lighter, the seams' shadow is the AO's, mottling
    rng = np.random.default_rng(11)
    mott = ndimage.gaussian_filter(rng.standard_normal(cov.shape).astype(np.float32), 24) * 6.0
    alb = 0.86 + 0.03 * mott - 0.05 * np.clip(-Hc, 0, 1)
    alb = np.clip(alb, 0, 1)
    wear = np.clip(np.abs(curv) * 4.0, 0, 1) * 0.35
    for kd in ('hem', 'sleeve', 'neck', 'leg'):
        d, _ = dist_to(kd)
        wear = np.maximum(wear, 0.4 * np.clip(1 - d * px_mm / 3.0, 0, 1))
    rough = {'jersey': 0.88, 'poplin': 0.78, 'twill': 0.86}[spec['fabric']] + 0.05 * mott * 0.2 - 0.06 * wear
    zone_trim = np.clip(trim + np.clip(np.abs(Hc) - 0.12, 0, 1) * 0.0, 0, 1)
    main = np.clip(allcov.astype(np.float32) - zone_trim, 0, 1)
    third = np.zeros(cov.shape, np.float32)
    albedo = maps.to_u8(maps.dilate(np.repeat(alb[..., None], 3, -1), allcov))
    orm = maps.to_u8(maps.dilate(np.stack([ao, np.clip(rough, 0, 1), np.zeros_like(ao)], -1), allcov))
    masks = maps.to_u8(maps.dilate(np.stack([main, zone_trim, third, np.clip(wear, 0, 1)], -1), allcov))
    zones = dict(R='dye: the garment colour (outfit.%s)' % ('shirt' if spec['kind'] == 'top' else 'pants'),
                 G='trim: rib / buttons / thread (a second colour; default the dye darkened or the thread white)',
                 B='none', A='wear')
    return dict(albedo=albedo, normal=nrm8, orm=orm, masks=masks, zones=zones)


def _pattern_lines(fr, spec, name, P, isl, pnames, cov, px_mm):
    """the shirt's placket / yoke / cuff seam; the trousers' waistband seam, fly, crease, belt loops, back pockets"""
    H = np.zeros(cov.shape, np.float32)
    x, y, z = P[..., 0], P[..., 1], P[..., 2]
    ph = (x + y + z) * 1000.0
    if spec['kind'] == 'top' and spec['neck'] == 'collar':
        front = (isl == 0) & cov
        top = fr.B.socket('socket_chest')[1, 3] + 0.01
        ax = np.abs(x) * 1000
        on = front & (y < top)
        H += on * (maps.stitch(ax, 17.5 - 4, y * 1000) + maps.stitch(ax, 17.5 + 4.0, y * 1000) * 0)
        H += on * 0.6 * np.clip((17.5 - ax) / 1.5, 0, 1)                  # the placket's double layer
        # buttonholes: 15 mm vertical slots at the buttons' heights
        yb = fr.B.socket('socket_chest')[1, 3] - 0.005 - 0.095 * np.arange(7)
        for yy in yb:
            slot = (ax < 1.2) & (np.abs(y - yy) * 1000 < 7.5)
            H -= on * slot * 0.35
        back = (isl == 1) & cov
        yy = fr.neck[:, 1].min() - 0.10
        dy = np.abs(y - yy) * 1000
        H += back * (maps.stitch(dy, 3.0, x * 1000) - 0.25 * np.clip(1 - dy / 0.9, 0, 1) + 0.25 * np.clip(1 - dy / 6, 0, 1))
        if 'cuff' in spec:
            s = fr.arm_s(P.reshape(-1, 3)).reshape(cov.shape)
            sc = spec['sleeve_s'] - spec['cuff'] / fr.arm_len
            dd = np.abs(s - sc) * fr.arm_len * 1000
            sl = (isl >= 2) & cov
            H += sl * (-0.3 * np.clip(1 - dd / 0.9, 0, 1) + maps.stitch(dd, 2.5, ph) + 0.4 * (s > sc))
            # the sleeve gathers into the cuff: two pleats' crests just above it
    if spec['kind'] == 'top' and spec.get('dart_lines'):
        # (B2b) THE SEWN DARTS (pattern.rest_shape takes their intake): a dart shows outside as its sewn line, the
        # folded intake pressed toward the centre under the cloth a soft ridge as wide as the intake (widest at the
        # waist), both fading out at the dart's point. The front's under the bust point (a woman's shirt), the back's
        # under the blades (double-ended: they close again over the seat)
        (yf_pt, yb_pt), (yf_end, yb_end) = pattern.dart_span(fr, np.array([True, False]))
        darts = [(1, fr.blade_pt[0], float(yb_pt), float(yb_end), 7.0)]
        if fr.B.sex == 'F':
            darts.append((0, fr.bust_pt[0], float(yf_pt), float(yf_end), 9.0))
        for isl_k, dxp, ytop, ybot, wmax in darts:
            on = (isl == isl_k) & cov & (y < ytop)
            if ybot is not None:
                on &= y > ybot
            # the intake's profile: 0 at the point(s), 1 at the waist
            up = np.clip((ytop - y) / max(1e-3, ytop - fr.waist_y), 0, 1)
            lo = np.clip((y - ybot) / max(1e-3, fr.waist_y - ybot), 0, 1) if ybot is not None else np.ones_like(y)
            prof = np.where(y > fr.waist_y, up, lo) ** 0.8
            d = (x - dxp) * 1000.0                          # + toward the side seam, - toward the centre
            w = wmax * prof
            H += on * (-0.30 * np.clip(1 - np.abs(d) / 0.7, 0, 1) * np.clip(prof * 4, 0, 1)
                       + 0.35 * prof * np.clip(-d / np.maximum(w, 0.5), 0, 1) ** 0.5 * (d < 0) * np.clip(1 + d / np.maximum(w, 0.5), 0, 1))
    if spec['kind'] == 'bottom':
        top = fr.waist_y - spec['rise']
        dy = np.abs(y - (top - spec['waistband'])) * 1000
        H += cov * (-0.3 * np.clip(1 - dy / 0.9, 0, 1) + maps.stitch(dy, 2.0, ph))
        # the fly (the wearer's left front): a J of stitches 35 mm from the centre, 180 mm down
        fl = (isl == 0) & cov
        yb = top - 0.19
        jx = np.where(y > yb, np.abs(x * 1000 - 35.0), np.hypot(x * 1000 - 0.0, (y - yb) * 1000) - 35.0)
        jx = np.abs(jx)
        H += fl * (y > yb - 0.035) * (y < top - spec['waistband']) * (x > 0) * maps.stitch(jx, 0.0, ph)
        # the front crease: pressed down the leg's front from the hip to the hem
        front = ((isl == 0) | (isl == 2)) & cov
        dc = np.abs(np.abs(x) - fr.leg_axis[0]) * 1000
        H += front * (y < fr.crotch_y + 0.05) * 0.35 * np.clip(1 - dc / 2.5, 0, 1)
        # belt loops: 5, 10 x 45 mm, over the waistband
        back = ((isl == 1) | (isl == 3)) & cov
        for bx in (0.0, 0.07, 0.13):
            dxl = np.abs(np.abs(x) - bx) * 1000
            m = (dxl < 5.0) & (y > top - 0.048) & (y < top + 0.002)
            if bx == 0.0:
                m &= back
            H += cov * m * (1.4 + maps.stitch(np.abs(y - top + 0.008) * 1000, 0, x * 1000) * 0)
        # back welt pockets: 140 mm wide, 75 mm under the waistband's top
        py = top - 0.075
        for sx in (1, -1):
            wx = np.abs(x - sx * 0.08) * 1000
            m = back & (wx < 70) & (np.abs(y - py) * 1000 < 6)
            H += m * (0.3 - 0.6 * (np.abs(y - py) * 1000 < 0.8))
    return H


# ------------------------------------------------------------------------------------------------ the tie
def forge_tie(B, fr, shirt, cache_dir=None, log=print):
    """the necktie on a forged collared shirt (necktie.py, B2b: the four-in-hand knot loft and the draped blade): skinned
    from the shirt's full mesh, its own small set (2048). Returns (the tie, the shirt with its collar's fall laid over
    the knot)"""
    from . import necktie
    key = _key(B, 'tie', [shirt['key']])
    p = os.path.join(cache_dir, key, 'garment.npz') if cache_dir else None
    if p and os.path.exists(p):
        d = dict(np.load(p, allow_pickle=True))
        d['rec'] = json.loads(str(d['rec']))
        d['key'] = key
        for k in ('albedo', 'normal', 'orm', 'masks'):
            d[k] = np.asarray(Image.open(os.path.join(cache_dir, key, f'T_{k}.png')))
        log(f'[outfit] {key}: from the cache')
        return d, necktie.collar_over_knot(shirt, d['V'], d['F'], d['tie_piece'])
    V, F, tag, rec = necktie.build(fr, shirt, B.sex)
    size = int(2048 * _SCALE)
    # a face label per piece and side: the blade's front, back and rolled edges apart (a blade in one island is a sock
    # that LSCM crushes), the knot's front and back
    fn = np.cross(V[F[:, 1]] - V[F[:, 0]], V[F[:, 2]] - V[F[:, 0]])
    fn /= np.linalg.norm(fn, axis=1, keepdims=True) + 1e-20
    cls = np.where(fn[:, 2] > 0.35, 0, np.where(fn[:, 2] < -0.35, 1, 2 + (V[F].mean(1)[:, 0] > 0)))
    lab = mo.components(F, len(V))[F[:, 0]] * 10 + cls
    U = maps.unwrap(V, F, lab, size=size, density=maps.TARGET_PX_PER_M * _SCALE)
    Fs, src = U['Fs'], U['src']
    Xs = V[src]
    N, TAN = maps.frames(Xs, Fs, U['UV'])
    from .. import bake_mesh
    Vw, Fw, wid, rep_ = B.welded()
    low = dict(V=Xs, F=Fs, UV=U['UV'], N=N, TAN=TAN, piece=np.zeros(len(Fs), np.int32))
    Vh, Fh, _ = mo.subdivide(V, F)
    bk = bake_mesh.bake(low, [dict(V=Vh, F=Fh)], size, occluders=[(Vw, Fw), (shirt['V'], shirt['F'])],
                        ss=2, cage=0.004, ao_r=0.015, n_ao=32, log=log)
    px_mm = 1000.0 / (maps.TARGET_PX_PER_M * _SCALE)
    cov = bk['normal'][..., 3] > 0
    # repp silk: diagonal ribs at 45 deg, 1.6 mm pitch, in the blade's own UV frame; the edge's blind stitch
    yy, xx = np.mgrid[0:size, 0:size] * px_mm
    rib = 0.12 * np.sin(2 * np.pi * (xx + yy) / 1.6)
    d, ind = ndimage.distance_transform_edt(cov, return_indices=True)
    Hc = cov * (rib + 0.25 * np.clip(1 - d * px_mm / 1.5, 0, 1))
    # (B2b) the four-in-hand's front: the last wrap's edge (a diagonal fold across the knot's face, its upper side
    # proud 0.5 mm) and the soft creases the wrap pulls toward the knot's bottom
    A, fce = maps.raster(U['UV'], Fs, np.column_stack([tag['u'][src], tag['x'][src], tag['piece'][src]]), size)
    kn = cov & (A[..., 2] < 0.5) & (fce >= 0)
    ku, kx = A[..., 0], A[..., 1]
    dl = (ku - (0.30 + 0.16 * kx)) * rec['knot']['knot_h'] * 1000.0          # mm across the wrap's edge
    Hc += kn * (0.5 * np.clip(-dl / 1.0, 0, 1) * np.clip(1 + dl / 6.0, 0, 1) - 0.35 * np.clip(1 - np.abs(dl) / 0.6, 0, 1))
    Hc += kn * (ku > 0.45) * 0.18 * np.cos(np.pi * kx * 3.0) * (ku - 0.45)
    Nf = maps.combine_normals(np.where(cov[..., None], bk['normal'][..., :3], [0, 0, 1.0]), maps.height_to_normal(Hc, px_mm))
    alb = 0.82 + 0.04 * np.sin(2 * np.pi * (xx + yy) / 1.6)
    out = dict(albedo=maps.to_u8(maps.dilate(np.repeat(alb[..., None], 3, -1), cov)),
               normal=maps.to_u8(maps.dilate(Nf * 0.5 + 0.5, cov)),
               orm=maps.to_u8(maps.dilate(np.stack([np.where(cov, bk['ao'], 1), np.full(cov.shape, 0.38),
                                                    np.zeros(cov.shape)], -1), cov)),
               masks=maps.to_u8(maps.dilate(np.stack([cov * 1.0, np.zeros(cov.shape), np.zeros(cov.shape),
                                                      np.clip(np.abs(np.where(cov, bk['curvature'], 0)) * 3, 0, 1) * 0.3], -1), cov)))
    # weights: the shirt's FULL mesh at the tie's closest point (the knot takes the collar's, with its neck share; the
    # blade the front's)
    Du = np.zeros((len(shirt['V']), len(B.jnames)))
    np.add.at(Du, (np.repeat(np.arange(len(Du)), 4), shirt['J4'].ravel()), shirt['W4'].ravel())
    q, t, bc, s = mo.closest_on_mesh(shirt['V'], shirt['F'], Xs)
    J4, W4 = skin.top4(np.einsum('nk,nkj->nj', bc, Du[shirt['F'][t]]))
    dens = texel_density(Xs, Fs, U['UV'], size)
    rec.pop('drape', None)
    r = dict(garment='tie', kind='prop', fabric='silk', sex=B.sex, triangles=int(len(Fs)), vertices=int(len(Xs)),
             density_px_per_m=dens, size=size, sheet_height=float(U['used']), bake_gate=bk['gate'],
             bake_ok=bool(bk['gate_ok']), weave_tile_mm=weave.TILE_MM['poplin'], seat=rec['seat'], tie=rec,
             zones=dict(R='dye: the tie colour (opts.tie)', G='none', B='none', A='wear'))
    d = dict(V=Xs, F=Fs, UV=U['UV'], N=N, TAN=TAN, J4=J4, W4=W4, X_A=Xs, F_all=Fs, F_low=Fs, XT_low=Xs, J4_low=J4,
             W4_low=W4, tie_piece=tag['piece'][src].astype(np.int8), rec=r, key=key, **out)
    if cache_dir:
        os.makedirs(os.path.join(cache_dir, key), exist_ok=True)
        for k in ('albedo', 'normal', 'orm', 'masks'):
            Image.fromarray(d[k]).save(os.path.join(cache_dir, key, f'T_{k}.png'))
        np.savez(p, **{k: v for k, v in d.items() if k not in ('albedo', 'normal', 'orm', 'masks', 'rec', 'key')},
                 rec=json.dumps(r))
    log(f'[outfit] {key}: the tie, {len(Fs)} tris, density p50 {dens["p50"]:.0f}')
    return d, necktie.collar_over_knot(shirt, Xs, Fs, d['tie_piece'])


# ------------------------------------------------------------------------------------------------ the shoes
def _forge_shoes(B, fr, log):
    parts = {}
    for sd in 'LR':
        s = shoes.build(fr, sd)
        parts[sd] = s
    # one mesh: L upper, L sole, R upper, R sole; the R pair takes the L's UVs by mirror (shared repeats)
    VuL, FuL = parts['L']['upper']
    VsL, FsL = parts['L']['sole']
    VuR, FuR = parts['R']['upper']
    VsR, FsR = parts['R']['sole']
    size = SIZE['shoes']
    UL = maps.unwrap(VuL, FuL, _shoe_panels(VuL, FuL, parts['L']['last']), size=size, density=maps.TARGET_PX_PER_M * _SCALE,
                     extra=[(VsL, FsL)])
    if UL['used'] > 1:
        raise RuntimeError('shoes overflow')
    # the R parts by mirror: nearest mirrored L vertex's UV per split vertex
    from scipy.spatial import cKDTree
    def mirrored(VR, FR, VL, UVsplit, FsplitL, srcL):
        tl = cKDTree(VL[srcL] * [-1, 1, 1])
        d, i = tl.query(VR)
        return UVsplit[i], d
    UVuR, du = mirrored(VuR, FuR, VuL, UL['UV'], UL['Fs'], UL['src'])
    UVsR = UL['extra_uv'][0][cKDTree(VsL * [-1, 1, 1]).query(VsR)[1]]
    # the high: the upper subdivided and smoothed (the leather's soft volume), the sole as is
    from .. import bake_mesh
    Xs = VuL[UL['src']]
    N, TAN = maps.frames(Xs, UL['Fs'], UL['UV'])
    Vh, Fh, _ = mo.subdivide(VuL, FuL)
    Vh, Fh, _ = mo.subdivide(Vh, Fh)
    L = mo.laplacian(Vh, Fh)
    bd = np.zeros(len(Vh), bool)
    for lp in mo.boundary_loops(Fh):
        bd[lp] = True
    for _ in range(6):
        for lam in (0.5, -0.53):
            d = L @ Vh
            d[bd] = 0
            Vh = Vh + lam * d
    Vw, Fw, wid, rep_ = B.welded()
    low = dict(V=Xs, F=UL['Fs'], UV=UL['UV'], N=N, TAN=TAN, piece=np.zeros(len(UL['Fs']), np.int32))
    bk = bake_mesh.bake(low, [dict(V=Vh, F=Fh)], size, occluders=[(Vw, Fw), (VsL, FsL)], ss=2, cage=0.006, ao_r=0.02,
                        n_ao=32, log=log)
    out = _compose_shoes(fr, size, UL, VuL, FuL, parts['L']['last'], bk, VsL, FsL)
    # the mesh, all four parts, T rest = as built (the legs do not move in the A-pose)
    MV = np.concatenate([Xs, VsL, VuR, VsR])
    nL = len(Xs)
    MF = np.concatenate([UL['Fs'], FsL + nL, FuR + nL + len(VsL), FsR + nL + len(VsL) + len(VuR)])
    MUV = np.concatenate([UL['UV'], UL['extra_uv'][0], UVuR, UVsR])
    J4, W4, _ = skin.transfer(B, MV, None, smooth_iters=0)
    N, TAN = maps.frames(MV, MF, MUV)
    nT = int(len(MF))
    dens = texel_density(MV, MF, MUV, size)
    rec = dict(garment='shoes', kind='shoes', fabric='leather', sex=B.sex, triangles=nT, vertices=int(len(MV)),
               density_px_per_m=dens, size=size, sheet_height=float(UL['used']), bake_gate=bk['gate'],
               bake_ok=bool(bk['gate_ok']), weave_tile_mm=weave.TILE_MM['leather'],
               tread_y=min(parts['L']['tread_y'], parts['R']['tread_y']), mirror_d_mm_p99=float(np.percentile(du, 99) * 1000),
               zones=out['zones'])
    F_coll = np.concatenate([FuL, FsL + len(VuL), FuR + len(VuL) + len(VsL), FsR + len(VuL) + len(VsL) + len(VuR)])
    V_coll = np.concatenate([VuL, VsL, VuR, VsR])
    return dict(V=MV, F=MF, UV=MUV, N=N, TAN=TAN, J4=J4, W4=W4, X_A=V_coll, F_all=F_coll, F_low=F_coll, XT_low=V_coll,
                albedo=out['albedo'], normal=out['normal'], orm=out['orm'], masks=out['masks'], rec=rec)


def _shoe_panels(V, F, L):
    """the upper: the vamp (front) and the quarters (L / R of the heel seam): islands split at the heel's back seam and
    across the instep"""
    c = V[F].mean(1)
    t = ((c - L.heel) @ L.axis) / L.length
    side = (c - L.heel) @ L.side_v
    # the vamp split down the toe's middle too: one domed island squeezed the toe's texels to half the density (F p5
    # 1,688 px/m, d04)
    lab = np.where(t > 0.55, np.where(side > 0, 0, 3), np.where(side > 0, 1, 2))
    return lab


def _compose_shoes(fr, size, UL, Vu, Fu, L, bk, Vs, Fs):
    px_mm = 1000.0 / (maps.TARGET_PX_PER_M * _SCALE)
    cov = bk['normal'][..., 3] > 0
    src = UL['src']
    Xs = Vu[src]
    t = ((Xs - L.heel) @ L.axis) / L.length
    side = (Xs - L.heel) @ L.side_v
    attr = np.column_stack([t, side, Xs[:, 1] - L.floor])
    A, fce = maps.raster(UL['UV'], UL['Fs'], attr, size)
    tt, ss, hh = A[..., 0], A[..., 1] * 1000, A[..., 2] * 1000
    # the sole's island
    so = np.zeros(cov.shape, bool)
    sa, sf = maps.raster(UL['extra_uv'][0], Fs, np.ones(len(Vs)), size)
    so = sf >= 0
    Hc = np.zeros(cov.shape, np.float32)
    ph = (tt * L.length * 1000 + hh)
    # the quarters' front edge over the vamp (t ~ 0.52 - 0.6, curving down to the welt): a step + a stitch row
    qe = (0.555 - 0.06 * np.clip(1 - hh / 50, 0, 1)) * L.length * 1000
    dq = tt * L.length * 1000 - qe
    Hc += cov * (0.7 * (dq < 0) * np.clip(-dq / 1.0, 0, 1) + maps.stitch(np.abs(dq), 3.0, hh * 3))
    # the lacing: the facings either side of the instep's top, 5 eyelet pairs, the lace's crossings
    top = hh > np.percentile(hh[cov], 70) if cov.any() else hh > 0
    lace_zone = cov & (tt > 0.40) & (tt < 0.58) & (np.abs(ss) < 22)
    for k in range(5):
        tk = 0.42 + 0.035 * k
        for sg in (1, -1):
            de = np.hypot((tt - tk) * L.length * 1000, ss - sg * 15.0)
            Hc += lace_zone * (-0.6 * np.clip(1 - de / 2.0, 0, 1) + 0.3 * np.clip(1 - np.abs(de - 2.6) / 0.6, 0, 1))
    tl = (tt * L.length * 1000 - 0.42 * L.length * 1000) / (0.035 * L.length * 1000)
    cross = np.minimum(np.abs((tl % 1.0) * 30 - 15 - ss), np.abs((tl % 1.0) * 30 - 15 + ss))
    lace = lace_zone & (np.abs(ss) < 14) & (cross < 2.2) & (tl > -0.2) & (tl < 4.2)
    Hc += lace * (1.6 * np.sqrt(np.clip(1 - (cross / 2.2) ** 2, 0, 1)))
    # the facings' edge (the gap between the quarters over the tongue)
    Hc += lace_zone * (np.abs(ss) < 4) * -0.5
    # the heel's counter seam (the back's vertical line) and the collar's top stitch
    Hc += cov * (np.abs(ss) < 1.0) * (tt < 0.08) * -0.3
    Hc += cov * maps.stitch(np.abs(hh - (fr.B.joint_pos('foot_L')[1] * 0 + 60.0)), 0, ph) * (tt < 0.4)
    # the sole: the welt's stitch row round its ledge, the tread's fine grain
    sd, sind = ndimage.distance_transform_edt(so, return_indices=True)
    Hc += so * maps.stitch(sd * px_mm, 2.0, (sind[0] + sind[1]) * px_mm)
    Nd = maps.height_to_normal(Hc, px_mm)
    nb = bk['normal'][..., :3].astype(np.float64)
    nb = np.where(cov[..., None], nb, np.array([0, 0, 1.0]))
    nb /= np.linalg.norm(nb, axis=-1, keepdims=True) + 1e-12
    Nf = maps.combine_normals(nb, Nd)
    allc = cov | so
    rng = np.random.default_rng(5)
    mott = ndimage.gaussian_filter(rng.standard_normal(cov.shape).astype(np.float32), 12) * 5
    curv = np.where(cov, bk['curvature'], 0)
    wear = np.clip(np.abs(curv) * 3.0, 0, 1) * 0.5 + cov * (tt > 0.8) * 0.25 * np.clip((tt - 0.8) / 0.15, 0, 1)
    alb = np.where(so, 0.55, 0.80 + 0.04 * mott) + 0.1 * wear * cov
    rough = np.where(so, 0.82, 0.42 + 0.06 * mott - 0.15 * wear)
    ao = np.where(cov, bk['ao'], np.where(so, 0.9, 1.0))
    lace_m = lace.astype(np.float32)
    main = cov.astype(np.float32) * (1 - lace_m)
    zones = dict(R='dye: the leather (outfit.shoes)', G='trim: laces and thread', B='the sole (rubber, fixed dark)',
                 A='wear')
    return dict(albedo=maps.to_u8(maps.dilate(np.repeat(np.clip(alb, 0, 1)[..., None], 3, -1), allc)),
                normal=maps.to_u8(maps.dilate(Nf * 0.5 + 0.5, allc)),
                orm=maps.to_u8(maps.dilate(np.stack([ao, np.clip(rough, 0, 1), np.zeros_like(ao)], -1), allc)),
                masks=maps.to_u8(maps.dilate(np.stack([main, lace_m, so.astype(np.float32), np.clip(wear, 0, 1)], -1),
                                             allc)),
                zones=zones)


# ------------------------------------------------------------------------------------------------ hidden faces, write
_REGIONS = {}


def _region_cover(fr, name, P, margin, leg_ok=False, near=0.0008):
    """(B2b) which points P (T rest) lie IN the garment's pattern region (pattern.build_region: the body's own surface
    it was cut from) within `near` of it, and farther than `margin` from its openings (the trousers' ankle loops are
    not openings: the leg goes on past them, unless leg_ok). A rest-shape rule, so a concave place (the crotch, where
    round 1's normal rays missed the cloth and left body faces drawn) is judged like any other"""
    from scipy.spatial import cKDTree
    key = (id(fr), name)
    if key not in _REGIONS:
        spec = pattern.SPECS[name]
        V, F, _ = pattern.build_region(fr, spec)
        loops = mo.boundary_loops(F)
        if spec['kind'] == 'bottom' and not leg_ok:
            loops = [l for l in loops if V[l, 1].mean() > fr.knee_y]
        trees = []
        for lp in loops:
            a, b = V[lp], V[np.roll(lp, -1)]
            n = np.maximum(1, np.ceil(np.linalg.norm(b - a, axis=1) / 0.002).astype(int))
            S = [p + (q - p) * (np.arange(k)[:, None] / k) for p, q, k in zip(a, b, n)]
            # (B2b) each opening its own margin floor: the NECK 40 mm (from behind and above the eye looks down
            # between a neckband and the nape: 15 mm left a dark band of culled skin there, the engine's back view),
            # a SLEEVE 25 mm (up the sleeve from the side); the rest the caller's
            c = V[lp].mean(0)
            floor = 0.040 if c[1] > fr.neck[:, 1].min() - 0.06 else (0.025 if abs(c[0]) > fr.x_sh else 0.0)
            trees.append((cKDTree(np.concatenate(S)), floor))
        _REGIONS[key] = (V, F, trees)
    V, F, trees = _REGIONS[key]
    q, t, bc, sd = mo.closest_on_mesh(V, F, P)
    d_in = np.linalg.norm(P - q, axis=1)
    ok = d_in < near
    for T, floor in trees:
        ok &= T.query(P)[0] > max(margin, floor)
    return ok, d_in


def hidden_tris(B, garments, margin=0.015, fr=None):
    # the margin: 15 mm from an opening (30 mm left skin points in the band between the gate's covered set and the mask
    # visible, and those went through in the crouch, g01); an opening's turned-back rim (up to 20 mm inside) hides the
    # culled skin just inside it
    """skin_BODY's triangles every vertex of which is under a garment and farther than `margin` from its openings:
    (B2b) by the garment's PATTERN REGION (_region_cover) or, as round 1, a ray along the skin's normal meeting it within
    10 cm (the shoes: the ray rule alone). And THE NECK UNDER A COLLAR: skin_BODY's and skin_HEAD's triangles whose
    normal ray meets the collar's stand more than 8 mm below its top. Returns ({garment: body tris}, {garment: head
    tris})"""
    import warp as wp
    wp.init()
    V, F = B.V, B.F
    Nv = vertex_normals(V, F)
    per, per_h = {}, {}
    Vw, Fw, wid, rep = B.welded()
    for g in garments:
        nm = g['rec']['garment']
        GV, GF = g['XT_low'], g['F_low']
        loops = mo.boundary_loops(GF)
        bpts = np.concatenate([GV[l] for l in loops]) if loops else np.zeros((0, 3))
        hit, hp = _ray_hits(GV, GF, V + Nv * 0.0005, Nv, 0.10)
        if len(bpts):
            from scipy.spatial import cKDTree
            dmin = cKDTree(bpts).query(hp)[0]
        else:
            dmin = np.full(len(V), 1.0)
        m = margin if g['rec']['kind'] != 'shoes' else 0.012
        cov = hit & (dmin > m)
        if g['rec']['kind'] != 'shoes' and fr is not None and nm in pattern.SPECS:
            # (B2b) cloth: the PATTERN REGION alone (round 1's normal rays culled the back of the neck above a tee's
            # neckline: a ray up the nape met the tee's back far from its opening, g02's holes test). What the clips
            # then expose (up a short sleeve in the wave) is drawn again by rommask.refine over the same frames
            # (tried and reverted 11-09: leaving the arm under a SHORT sleeve drawn put the armpit through the sleeve
            # in 365 of 390 frames, arms down: the arm's inner side and the chest's flank squeeze together under LBS
            # whatever the cloth's weights; culled, it can show only up the sleeve from below: judged in the engine)
            cw, _ = _region_cover(fr, nm, Vw, m)
            cov = cw[wid]
        per[nm] = cov
        if 'collar_range' in g:
            c0, c1 = (int(x) for x in g['collar_range'])
            st = np.asarray(g['collar_part']) == 0
            CVt = g['V'][c0:c1]
            loc = -np.ones(c1 - c0, np.int64)
            loc[st] = np.arange(st.sum())
            fc = g['F'][(g['F'] >= c0).all(1) & (g['F'] < c1).all(1)] - c0
            fc = fc[st[fc].all(1)]
            SF = loc[fc]
            SV = CVt[st]
            drop = np.asarray(g['collar_top_drop'])[st]
            HV, HF, _, _ = _head(B)
            for which, PV, PF in (('body', V, F), ('head', HV, HF)):
                Nn = vertex_normals(PV, PF)
                h, hp_, face, bcs = _ray_hits(SV, SF, PV + Nn * 0.0005, Nn, 0.03, full=True)
                dd = np.einsum('nk,nk->n', bcs, drop[SF[np.maximum(face, 0)]])
                c = h & (dd > 0.008)
                if which == 'body':
                    per[nm] = per[nm] | c
                else:
                    per_h[nm] = c
    out = {k: np.nonzero(c[F].all(1))[0] for k, c in per.items()}
    HV, HF, _, _ = _head(B) if per_h else (None, None, None, None)
    out_h = {k: np.nonzero(c[HF].all(1))[0] for k, c in per_h.items()}
    return out, out_h


def _ray_hits(GV, GF, O, D, maxd, full=False):
    import warp as wp
    dev = 'cuda:0' if wp.is_cuda_available() else 'cpu'
    m = wp.Mesh(points=wp.array(GV.astype(np.float32), dtype=wp.vec3, device=dev),
                indices=wp.array(GF.astype(np.int32).ravel(), dtype=wp.int32, device=dev))
    hit = wp.zeros(len(O), int, device=dev)
    hp = wp.zeros(len(O), wp.vec3, device=dev)
    face = wp.zeros(len(O), int, device=dev)
    bc = wp.zeros(len(O), wp.vec3, device=dev)
    wp.launch(_k_ray, len(O), [m.id, wp.array(O.astype(np.float32), dtype=wp.vec3, device=dev),
                               wp.array(D.astype(np.float32), dtype=wp.vec3, device=dev), float(maxd), hit, hp, face,
                               bc], device=dev)
    if full:
        return hit.numpy().astype(bool), hp.numpy().astype(np.float64), face.numpy(), bc.numpy().astype(np.float64)
    return hit.numpy().astype(bool), hp.numpy().astype(np.float64)


def _k():
    import warp as wp

    @wp.kernel
    def k(mesh: wp.uint64, o: wp.array(dtype=wp.vec3), d: wp.array(dtype=wp.vec3), maxd: float,
          hit: wp.array(dtype=int), hp: wp.array(dtype=wp.vec3), face: wp.array(dtype=int), bc: wp.array(dtype=wp.vec3)):
        i = wp.tid()
        q = wp.mesh_query_ray(mesh, o[i], d[i], maxd)
        if q.result:
            hit[i] = 1
            hp[i] = o[i] + d[i] * q.t
            face[i] = q.face
            bc[i] = wp.vec3(q.u, q.v, 1.0 - q.u - q.v)
    return k


_k_ray = _k()


def write_outfit(B, garments, out_glb, colours=None, fr=None, layer_margin=0.035):
    from .export import GlbEdit
    E = GlbEdit(B.path)
    fr = fr if fr is not None else pattern.Frame(B)
    hid, hid_h = hidden_tris(B, [g for g in garments if g['rec']['garment'] != 'tie'], fr=fr)
    # THE LAYERS' MASK: an inner garment's faces under an outer one (the trousers' waist under an untucked top) drop as
    # the body's do (a game's layered outfit: what cannot show is not drawn, and cannot poke through in a crouch).
    # (B2b) by the outer garment's PATTERN REGION, `layer_margin` in from its openings (round 1's normal rays from the
    # draped trousers culled a patch at the front crotch under nothing, a hole the walk opened: the check's crotch
    # points) and only faces wholly inside it
    layer_hide = {}
    order = ['shoes', 'trousers', 'tee', 'shirt_ss', 'shirt_ls', 'tie']
    for gi in garments:
        for go in garments:
            ni, no = gi['rec']['garment'], go['rec']['garment']
            if 'shoes' in (ni, no) or 'tie' in (ni, no) or order.index(ni) >= order.index(no):
                continue
            # under the outer garment's region (the coverage), and `layer_margin` from its DRAPED openings (the hem as
            # it hangs: the tee's front falls 5 cm under the pattern's hem line, which left a 9 cm band of trousers
            # drawn under it, and the walk's thighs put that band through the tee)
            cov, _ = _region_cover(fr, no, gi['V'], 0.0, near=0.03)
            from scipy.spatial import cKDTree
            GV = go['XT_low']
            S = []
            for lp in mo.boundary_loops(go['F_low']):
                P, Q = GV[lp], GV[np.roll(lp, -1)]
                for p, q in zip(P, Q):
                    k = max(1, int(np.ceil(np.linalg.norm(q - p) / 0.003)))
                    S.append(p + (q - p) * (np.arange(k)[:, None] / k))
            cov &= cKDTree(np.concatenate(S)).query(gi['V'])[0] > layer_margin
            # and actually UNDER it: a ray out RADIALLY from the trunk's axis meets the draped outer within 10 cm ('3.5 cm
            # from the hem' is true below the hem too, where the tee drapes higher than its pattern line: holes; the
            # inner's own normal turns sideways in a concave seam, the seat's cleft, and never met the tee: drawn there,
            # those points went through it in the walk)
            Pv = gi['V']
            rad = np.column_stack([Pv[:, 0], np.zeros(len(Pv)), Pv[:, 2] - fr.zc(Pv[:, 1])])
            rad /= np.linalg.norm(rad, axis=1, keepdims=True) + 1e-12
            hit_o, _ = _ray_hits(go['XT_low'], go['F_low'], Pv + rad * 0.0005, rad, 0.10)
            cov &= hit_o
            layer_hide.setdefault(ni, []).append(np.nonzero(cov[gi['F']].all(1))[0])
    keep = np.ones(len(B.F), bool)
    HV, HF, _, _ = _head(B)
    keep_h = np.ones(len(HF), bool)
    recs = []
    for g in garments:
        nm = g['rec']['garment']
        full_idx = None
        if nm in layer_hide:
            lh = np.unique(np.concatenate(layer_hide[nm]))
            g = dict(g)
            g['F_full'] = g['F']
            full_idx = E.accessor(np.asarray(g['F'], np.uint32).reshape(-1), 'SCALAR')
            g['F'] = np.delete(g['F'], lh, axis=0)
            g['rec'] = dict(g['rec'], layer_hidden_tris=[int(x) for x in lh])
        tex = [E.texture(g[k]) for k in ('albedo', 'normal', 'orm', 'masks')]
        _, _, wn, _ = weave.tile({'silk': 'poplin'}.get(g['rec']['fabric'], g['rec']['fabric']), 512)
        wtex = E.texture(wn)
        ex = dict(bestiary=f'garment_{nm}', garment=nm, fabric=g['rec']['fabric'], zones=g['rec']['zones'],
                  weave_tile_mm=g['rec']['weave_tile_mm'], weave_texture=wtex, texel_px_per_m=maps.TARGET_PX_PER_M,
                  size=g['rec']['size'],
                  density_px_per_m=g['rec']['density_px_per_m'], masks='emissiveTexture (factor 0): R dye, G trim, '
                  'B third, A wear')
        mi = E.material(f'garment_{nm}', tex[0], tex[1], tex[2], tex[3], ex)
        E.skinned_mesh(f'garment_{nm}', g['V'], g['N'], g['TAN'], g['UV'], g['F'], g['J4'], g['W4'], mi)
        h = hid.get(nm, np.zeros(0, int))
        keep[h] = False
        hh = hid_h.get(nm, np.zeros(0, int))
        keep_h[hh] = False
        r = dict(g['rec'])
        r.pop('drape', None)
        r.pop('drape_high', None)
        r['hidden_tris'] = [int(x) for x in h]
        r['hidden_tris_head'] = [int(x) for x in hh]
        if full_idx is not None:
            r['index_full'] = full_idx           # the garment's whole index (a runtime without the outer layer)
        r['key'] = g['key']
        recs.append(r)
    full = E.body_index('skin_BODY', keep)
    b = E.j.setdefault('extras', {}).setdefault('bestiary', {})
    b['garments'] = recs
    b['body_index_full'] = full
    if not keep_h.all():
        b['head_index_full'] = E.body_index('skin_HEAD', keep_h)
    b['garments_version'] = VERSION
    if colours:
        b['outfit'] = colours
    n = E.save(out_glb)
    return dict(bytes=n, hidden=int((~keep).sum()), per={k: int(len(v)) for k, v in hid.items()},
                hidden_head=int((~keep_h).sum()), layer={k: int(sum(len(x) for x in v)) for k, v in layer_hide.items()})
