"""AVIAN flight feathers (HAWK_PLAN.md §5.2): the per-feather generator (outline, rachis bow, vane asymmetry,
emargination, tip shape), the card mesh (two-sided by material: 13 x 4 vertices, 12 rows x 3 quad columns = 72
triangles per card, plan §5.2), the layer order and its minimum separation.

A feather lives in its own 2D frame: s along the rachis from the insertion (0) to the tip (L), w across it, + toward the
OUTER vane (the leading-edge side on the wing; on the tail the side away from the centre). The outline is the two vane
margins w_out(s) >= 0 and w_in(s) <= 0 around the rachis line r(s) (a bow of BOW x L at mid-length toward the inner
vane; the primaries whose tips lie on the leading edge get their own bow from fit_le_bow, so the hand's leading edge
follows the measured outline: D1.4).

Feather classes (plan §5.2, measured by eye on B015440 and c049 [E]; the D1.4 gate fits them to the Beaty outline):
  primary    width WIDTH['primary'] x L, outer:inner 1:3; P6-P10 emarginated (the outer vane steps in at EMARG_S of
             the length, the inner vane notched on P7-P10), the distal part narrow: the slotted hand of c049
  secondary  symmetric-ish (1:1.6), square-tipped (a blunt round of radius 0.5 w)
  tertial    broad, soft, rounded
  alula      short, stiff, asymmetric
  rectrix    broad, rounded, 1:1.3 (the central pair symmetric)
THE LAYER ORDER (dorsal to ventral, plan §5.2): the alula over everything at the hand; the tertials over the
secondaries; each secondary over its OUTER neighbour (S2 over S1 ...); the secondaries over the primaries; each primary
UNDER its inner neighbour (P1 on top of the primaries, P10 lowest). layer_rank() gives each card its rank and
MIN_SEP (0.6 mm [E]) the offset per rank along the wing's normal.
"""
import numpy as np

ROWS, COLS = 13, 4                    # card vertices along and across (COLS: outer margin, rachis x2 (keel), inner)
MIN_SEP = 0.6                         # mm per layer rank along the normal [E: plan §5.2]
WIDTH = dict(primary=0.165, secondary=0.27, tertial=0.24, alula=0.24, rectrix=0.27)   # max total width / L [E]
ASYM = dict(primary=0.25, secondary=0.38, tertial=0.45, alula=0.22, rectrix=0.43)    # outer share of the width [E]
BOW = dict(primary=0.025, secondary=0.010, tertial=0.0, alula=0.03, rectrix=0.008)   # rachis bow / L [E]
EMARG_S = 0.62                        # [E] where the emargination steps the vane in (fraction of L from the base)
EMARG_S_AT = {10: 0.72}               # [M-d0, D1b] per primary: on B015440 (d1_work/look/B015440_hand.png) the
#                                       outermost slot (P10/P9) is the shortest of the four; at 0.62 P10's notch
#                                       opened a 10 mm hole behind it and pulled its outer margin off the LE
EMARG_KEEP = dict(outer=0.25, inner=0.25)   # [E] the vane's width kept beyond the step (D1.4: open slots, c049;
#                                             D1b: inner 0.32 -> 0.25, the finger 0.041 L = 11.6 mm at P8 against
#                                             B015440's 10-12 mm once the tips are blunt)
OUTER_AT = {10: 1.15}                 # [D-d13] per primary: its outer vane's width scale. P10's outer vane IS the hand's
#                                       leading edge past the coverts; fitted with avian.P_INS_FWD (hawk_p10fit.py, a grid
#                                       of bow x scale x insertion): 1.15 + the insertion on the LE took the margin from
#                                       4.4 mm aft to <= 2.8 over x 380-490


def outline(group, L, index=0, emarginated=False, n=64, bow=None):
    """the closed feather polygon (s, w) in its frame, counter-clockwise: the outer margin base -> tip, the inner tip ->
    base; plus dict(s, r, w_out, w_in) for the card. bow: the rachis bow / L, + toward the inner vane (default the
    class's BOW; fit_le_bow sets it for the leading-edge primaries)"""
    s = np.linspace(0.0, L, n)
    t = s / L
    Wmax = WIDTH[group] * L
    a = ASYM[group]
    # the vane envelope: a quick rise from the calamus (bare quill, 6 % of L), full by 30 %, then the tip shape
    rise = np.clip((t - 0.06) / 0.24, 0.0, 1.0) ** 0.6
    if group == 'secondary':
        # blunt with a small point at the rachis (D1b, the lead's call): the corners round back over the last 10 %,
        # so the margins recede from the rachis tip instead of standing past the TE as a square end's corners do
        u = np.clip((t - 0.90) / 0.10, 0.0, 1.0)
        tip = np.sqrt(np.clip(1.0 - u ** 2, 0.0, 1.0)) * (1.0 - 0.6 * u)
    elif group in ('tertial', 'rectrix'):
        tip = np.sqrt(np.clip(1.0 - np.clip((t - 0.78) / 0.22, 0.0, 1.0) ** 2, 0.0, 1.0))      # rounded
    else:
        tip = np.sqrt(np.clip(1.0 - np.clip((t - 0.70) / 0.30, 0.0, 1.0) ** 2, 0.0, 1.0))      # tapered
    tip_in = tip
    if emarginated:
        # the slotted fingers end ROUND and blunt (B015440 dorsal, d1_work/look/B015440_hand.png: 10-12 mm wide to
        # near the end, a round over the last few %), not the unslotted primaries' taper. Per vane: a vane that is
        # not notched (P6's inner) keeps the taper, or its full width stands past the TE (D1b: 12 mm at P6)
        tip = np.sqrt(np.clip(1.0 - np.clip((t - 0.93) / 0.07, 0.0, 1.0) ** 2, 0.0, 1.0))
        if index >= 7:
            tip_in = tip
    w_out = a * Wmax * rise * tip
    w_in = -(1.0 - a) * Wmax * rise * tip_in
    if emarginated:
        # the notch narrows the vane GRADUALLY (a smoothstep over EMARG_S -0.06 .. +0.08): B015440's slots open as V's;
        # D1.4's 0.025-wide tanh made a cliff that left a blunt-ended hole between P10's notch and P9 (D1b)
        v = np.clip((t - (EMARG_S_AT.get(index, EMARG_S) - 0.06)) / 0.14, 0.0, 1.0)
        step = v * v * (3.0 - 2.0 * v)
        w_out = w_out * (1.0 - step * (1.0 - EMARG_KEEP['outer']))
        if index >= 7:
            w_in = w_in * (1.0 - step * (1.0 - EMARG_KEEP['inner']))
    if group == 'primary':
        w_out = w_out * OUTER_AT.get(index, 1.0)
    b = BOW[group] if bow is None else bow
    r = b * L * 4.0 * t * (1.0 - t)                                   # + toward the inner vane (- w)
    poly = np.concatenate([np.stack([s, w_out - r], 1), np.stack([s[::-1], (w_in - r)[::-1]], 1)])
    return poly, dict(s=s, r=-r, w_out=w_out - r, w_in=w_in - r)


def card(group, L, index=0, emarginated=False):
    """the card's vertices (ROWS x COLS, (s, w)) and its triangles (one side; the card is two-sided by material):
    columns = the outer margin, the rachis (two, a 0.6 mm keel), the inner margin; rows evenly in s"""
    _, c = outline(group, L, index, emarginated, n=256)
    rs = np.linspace(0.0, L, ROWS)
    cols = [np.interp(rs, c['s'], c['w_out']), np.interp(rs, c['s'], c['r']) + 0.3,
            np.interp(rs, c['s'], c['r']) - 0.3, np.interp(rs, c['s'], c['w_in'])]
    V = np.array([[rs[i], cols[j][i]] for i in range(ROWS) for j in range(COLS)])
    F = []
    for i in range(ROWS - 1):
        for j in range(COLS - 1):
            a, b, c_, d = i * COLS + j, i * COLS + j + 1, (i + 1) * COLS + j + 1, (i + 1) * COLS + j
            F += [[a, b, c_], [a, c_, d]]
    return V, np.array(F)


COVER_GAP = (1.0, 6.0)                # mm [E, D1b]: under its outer neighbour a LE primary's outer margin lies at most
#                                       6 mm behind the neighbour's inner margin (the planform's 5 mm closing fills
#                                       less than 10 mm); in its distal 20 % at least 1 mm clear (the slot, B015440)


def fit_le_bow(group, L, index, emarginated, ins, tip, le_x, le_y, outer_dir_sign=-1.0, x_from=None, cover=None):
    """the bow (one number per feather) for a primary whose tip lies on the LEADING EDGE (P9, P10 on H1). From 10 % to
    95 % of its length its outer margin must never stand beyond the LE (0.5 mm slack, then x 10); where it FORMS the
    LE (outline x >= x_from; None = everywhere) it must also not fall aft of it. cover = (x, y), the outer
    neighbour's placed inner margin, x rising: where the neighbour covers it (x < x_from) the gap behind that margin
    stays inside COVER_GAP. D1b: fitting P9 to the LE over its whole length, where P10 forms most of it, bowed P9
    forward and opened a 10 mm hole behind P10's notch while its tip crossed P10's. Minimises the worst term, bow in
    [-0.08, 0.06] on a 0.0025 step. Returns (bow, worst mm)"""
    best = None
    for b in np.arange(-0.08, 0.0601, 0.0025):
        _, c = outline(group, L, index, emarginated, n=128, bow=b)
        k = (c['s'] >= 0.10 * L) & (c['s'] <= 0.95 * L)
        pts = place(np.stack([c['s'][k], c['w_out'][k]], 1), ins, tip, outer_dir_sign)
        d = pts[:, 1] - np.interp(pts[:, 0], le_x, le_y)       # + = aft of the LE (inside), - = beyond it
        forms = np.ones(len(d), bool) if x_from is None else pts[:, 0] >= x_from
        worst = float(np.max(np.where(d < 0, 10.0 * np.maximum(-d - 0.5, 0.0), np.where(forms, d, 0.0))))
        if cover is not None:
            under = ~forms & (pts[:, 0] >= cover[0][0]) & (pts[:, 0] <= cover[0][-1])
            g = pts[:, 1] - np.interp(pts[:, 0], cover[0], cover[1])          # + = aft of the neighbour's margin
            slot = c['s'][k] >= 0.80 * L
            pen = np.where(under, np.maximum(g - COVER_GAP[1], 0.0), 0.0)
            pen = np.maximum(pen, np.where(under & slot, 20.0 * np.maximum(COVER_GAP[0] - g, 0.0), 0.0))
            worst = max(worst, float(pen.max()) if len(pen) else 0.0)
        if best is None or worst < best[1]:
            best = (float(b), worst)
    return best


def place(poly_sw, ins, tip, outer_dir_sign):
    """the feather's (s, w) points into the plane: s along ins -> tip, +w toward outer_dir_sign x the left normal"""
    ins, tip = np.asarray(ins, float), np.asarray(tip, float)
    ax = (tip - ins) / np.linalg.norm(tip - ins)
    nrm = np.array([-ax[1], ax[0]]) * outer_dir_sign
    return ins + poly_sw[:, :1] * ax + poly_sw[:, 1:2] * nrm


def layer_rank(feathers):
    """name -> rank (0 = the most ventral), the plan's dorsal-to-ventral order (module docstring)"""
    order = []
    prim = sorted([n for n, f in feathers.items() if f['group'] == 'primary'], key=lambda n: -feathers[n]['index'])
    sec = sorted([n for n, f in feathers.items() if f['group'] == 'secondary'], key=lambda n: feathers[n]['index'])
    ter = sorted([n for n, f in feathers.items() if f['group'] == 'tertial'], key=lambda n: -feathers[n]['index'])
    alu = sorted([n for n, f in feathers.items() if f['group'] == 'alula'], key=lambda n: -feathers[n]['index'])
    order = prim + sec + ter + alu                 # P10 .. P1, S1 .. S13, T3 .. T1, A4 .. A1
    return {n: i for i, n in enumerate(order)}
