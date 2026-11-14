"""The COWBOY HAT: a 1950 Stetson, the fifth Bestiary accessory (ROADMAP B5), built at real size on the TOP HAT's
felt method (top_hat.py: the same stages, its felt / grosgrain / leather / satin recipe, its fit contract), measured
on ONE real hat photographed twice (work/bestiary/accessories_b5/cowboy_hat/refs_photos/SOURCES.txt, views A and B;
the measuring: accessories_b5/slice_NOTES.md and cowboy_hat/scripts/m04, m05).

  parts -> block-out SDF:  the felt body as two SHELLs over their mid-surfaces: the CROWN (a tall tapered oval crown,
                           its ridges sloping down from the back to the front pinch, the centre crease between them,
                           the pinch's two side dents: crown_point) and the BRIM (the crown's base oval swept out
                           along its plan normal, dipped front and back, the sides rolled, the edge curled all round:
                           brim_frame, top_hat's terms); the ribbed ribbon BAND and the leather SWEATBAND as thin
                           SHELLs over offsets of the crown's wall; all hard-unioned
  -> the low:              AUTHORED quad rings of K_LOW columns (WORKING_RULES 2; craft guide 05.13, 05.18): from the
                           top's grid cap (its middle line ON the crease, two lines ON the ridges) down the crown, over
                           the band, out the brim's upper face, round the bound edge, back under it, up the sweatband
                           and the lining to the inner top's cap; every ring a fair closed curve OF the high's own
                           surface (the same crown_point / brim_frame, offset by the felt's half-thickness)
  -> UV islands:           the hat is a mirror pair about x = 0 except the bow: every island but the band is the RIGHT
                           half's, the left half stacked on it (07.31; forge/species/red_tailed_hawk_uv.py's way); the
                           band is one unique strip; packed by a raster packer
  -> sculpt plan:          the binding's rolled edge and its puckers, the band's flat bow on the wearer's left
  -> voxel high + bake     (voxel.SparseSDF + bake.bake, as top_hat.forge drives them), symmetric islands baked from
                           the bow-less right half
  -> material pass:        felt (top_hat's fibre tufts, nap and fuzz in this hat's sand colour), the ribbed band with
                           its five cords, the binding, a roan sweatband, a satin lining; the wear a worn western hat
                           shows (research/ACCESSORY_REFERENCE.md §5): the sweat line over the band, the pinch soiled
                           and polished by the fingers, the brim's front edge handled, dust in the brim's nap, the
                           top sun-faded
  -> a static glb carrying its FIT data (top_hat's contract: the head opening, the seat frame, clearance probes; plus
     a validated pose per species under fit.conform, which accessories.js wear() already reads)

Frame: metres, +Y up = the seat axis, the origin at the centre of the head opening on the SEAT PLANE (y = 0: the
opening's lower edge = the brim's underside at the crown), +Z forward (the wearer's face), +X the wearer's left (the
bow's side). phi is the azimuth from +Z toward +X.

NUMBERS and their sources (SPEC; [C] published, [M] measured here on the photos through a [C] scale, [E] estimate):
  * the head opening 570 mm round, a long oval 1.20 : 1 [C: hat size 7 1/8 as the top hat; ACCESSORY_REFERENCE §5];
  * everything tagged [M]: read off views A and B through fitted pinhole cameras with the opening held at that size
    (scripts/m05_fit_photo.py prints "my constant | the photo" for each);
  * felt 1.4 mm, sweatband 45 x 1 mm, band ribbon 0.6 mm, binding 5 mm a face [E: trade figures, as top_hat's].
"""
import numpy as np
import warp as wp

from .. import material as M
from .. import proc

wp.set_module_options({'enable_backward': False, 'max_unroll': 1})   # forward-only; noise neighbour loops left rolled

SPEC = dict(
    head_circ=0.570,        # the head opening's circumference (m): hat size 7 1/8 [C]
    open_ratio=1.17,        # the opening's length / width [M: fitted 1.174; hatters' "regular oval" ~1.2]
    felt_t=0.0014,          # the felt [E]
    sweat_t=0.0010,         # the roan sweatband's thickness and height [E]
    sweat_h=0.045,
    band_t=0.0006,          # the ribbed ribbon band: its thickness [E] and height [M: fitted 17.0 mm, +-2]
    band_h=0.018,
    # ---- the crown (mid-surface; heights above the brim's mid-plane). [M-eye]: set by eye until the model's outline
    # and its ridge / crease lines lay on both photos through the fitted cameras (m05 sheets 0-3)
    crown_h=0.141,          # the ridges' height at the back [M-eye: 150 stood 5-6 mm over the photo's top in view A]
    front_h=0.74,           # the ridges at the front pinch, a share of crown_h [M-eye]
    slope=(-0.50, 0.90),    # where the ridges' descent starts and ends along the top (zeta: -1 the back, +1 the front)
    shoulder_p=3.8,         # the meridian's squircle exponent: 2 a dome, larger a squarer shoulder [M-eye]
    taper_x=0.20,           # the top's outline inside the base oval: in by these shares at the sides, the back and
    taper_b=0.12,           #   the front (the walls lean in; the front wall leans back the most) [M-eye]
    taper_f=0.40,
    top_n=(2.0, 3.2),       # the top's plan outline: a superellipse's exponent on its front half and its back half
    crease_d=0.17,          # the centre crease: its depth at the front (a share of crown_h), where it starts and where
    crease_z=(-0.60, 0.70), #   it is full (zeta), its half-width at its back end and at the front (m), and the height
    crease_w=(0.050, 0.036),  # shares over which its pull fades in up the front wall (the notch) [M-eye]
    crease_lo=(0.50, 0.92),
    pinch_d=0.013,          # the pinch: each side wall pressed in by this much (m) near the front, over the height
    pinch_y=(0.74, 0.30),   #   band (centre, half-extent: shares of the local height), growing along zeta from
    pinch_z=(-0.25, 0.75),  #   pinch_z[0] to [1], on the part of the section beyond pinch_side of its half-width
    pinch_side=(0.25, 0.80),
    # ---- the brim (top_hat.brim_theta's terms)
    brim_w=0.0926,          # along its surface [M: fitted 92.6 mm = 3 5/8 in]
    roll=17.5,              # the side roll: the meridian turns up to `roll` degrees at the side edge [M], growing as
    roll_p=2.4,             #   (rho / W)^roll_p, concentrated at the sides as |sin phi|^roll_q [E: by eye, the sheets]
    roll_q=2.0,
    dip=34.5,               # the front / back dip: the meridian dips by up to `dip` degrees mid-brim (cos^2 phi) [M]
    curl=30.0,              # the all-round edge curl: the bound lip (degrees, over the brim's outer part from
    curl_at=0.80,           #   curl_at) [E: by eye; the photo's curves see the edge only, not how the brim reaches it]
    bind_w=0.005,           # the binding: a 10 mm ribbon folded over the edge, 5 mm a face, 0.35 mm thick [E]
    bind_t=0.00035,
    bead_r=0.0012,          # the binding's rolled edge (sculpt)
    reed_r=0.0005,          # the head opening's edge rounding
    # the band is a CORDED grosgrain: SIX raised gold cords along it, parted by FIVE pale lines (the white warp shown
    # in the grooves; the tails fray to the same white threads). [M: view B's luminance profile across the band at
    # x 930-970 px: the pale lines at these shares of its height, each ~0.9 mm wide; the weft's ribs 1.0 mm apart
    # (60 ribs in 300 px beside a 91 px = 18 mm band)]. CORRECTED 11-10 19:40: the first high had five cords
    # CENTRED on the pale lines (a count on view A's warm close-up, where the lines read as crests)
    band_lines=(0.13, 0.31, 0.49, 0.68, 0.88),
    cord_amp=0.00035,       #   each cord this proud of its grooves [E]
    rho_in=0.0008,          # the brim's felt runs this far inside the crown's mid-surface (under the sweatband)
    bow_phi=90.0,           # the band's bow: degrees from +Z toward +X (the wearer's left) [M: view A]
    knot_w=0.014,           # the WRAPPED KNOT: the same ribbon wound once round the band, its cords upright: its width
    knot_t=0.0022,          #   along the band and how far it stands off the band [M-eye: view A's close-up]
    # the two TAILS over the brim's upper face [M-eye, view A]: each (width, the path's start and end as (degrees
    # from +Z toward +X, rho / brim_w)): the short one runs out from under the knot, a little forward, and lies on the
    # brim; the long one leaves the knot's back edge and runs TAUT, out and back, to just short of the binding (view
    # A: its shadow under it). Both are the low's own strips (tail_strips)
    tails=((0.012, (88.0, 0.03), (79.0, 0.55)), (0.011, (97.0, 0.03), (129.0, 0.90))),
)
# ------------------------------------------------------------------------------------------ THE FELT HATS (11-11)
# This file builds THREE felt hats on one method (as peaked_cap.py also covers the officer's cap): each is SPEC with
# its own numbers, chosen by use(<hat>) BEFORE anything is built (the scripts' `hat=<key>`):
#   'gus'        the 1950 Stetson above, named for what it is (Skye, 11-11: "does not look like a cowboy hat at all
#                ... find out what that actual hat style is"): a GUS crease, "originally known as the Montana Slope"
#                (Resistol's crease guide; slice_NOTES 04:47). Kit option gus_hat.
#   'cattleman'  THE COWBOY HAT people mean: the cattleman crease (a centre crease with a dent each side, the brim
#                curled up at both sides and dipping front and back). Kit option cowboy_hat. Four colours, each a
#                MATERIAL variant of the one bake (VARIANTS).
#   'ranger'     the PARK RANGER (campaign) hat: a stiff flat brim, the four-dent Montana peak, a leather band. Kit
#                option ranger_hat.
# A key that SPEC lacks is new with these hats and read with .get(): the Gus's own numbers and shapes are untouched
# (its low is the same to the bit: scripts/f03_low.py prints the same table).
CATTLEMAN = dict(
    # [C] = published; [M-eye] = set by eye until the clay lay on the three reference photos (accessories_b5/refs/
    # felt_hats: the Calgary white hat, Team USA's 1980 hat from above, F.M. Light & Sons' felt hats at eye level:
    # cowboy_hat/scripts/c01_clay_vs_refs.py); none of those photos comes with a scale, so the sizes are the trade's
    crown_kind='cattleman',
    crown_h=0.1175,         # [C] 4 5/8 in, the cattleman crown of Stetson's 7540 profile (the Lariat 5X's page,
    #                         stetson.com; Resistol's cattleman hats list the same 4 5/8 in)
    brim_w=0.1016,          # [C] 4 in, the same profile's brim (Resistol's: 4 1/4 in)
    # the ridges' height along the top, (zeta, share of crown_h): highest toward the front, a little lower behind
    ridge_pts=((-1.0, 0.930), (-0.30, 0.945), (0.55, 1.000), (1.0, 0.985)),
    # the centre crease's depth under the ridges, (zeta, share of crown_h): deepest toward the front (the Olympic
    # hat's wide V, the Calgary hat's far end), running out to the back; it reaches both ends as a notch
    crease_pts=((-1.0, 0.120), (-0.45, 0.220), (0.30, 0.310), (0.80, 0.250), (1.0, 0.150)),
    crease_w=(0.031, 0.035),  # its half-width (the ridges' crests stand this far from the midline): back, front
    crease_lo=(0.55, 0.96),
    cap_shares=(0.22, 0.78),  # the low's cap: its two lines on each wall of the crease (cap_plan says why)
    # THREE CLAY TRIES beside the photos (tmp/x/clay_cattleman_t1..t3.png): the first (shoulder 2.9, the walls in by
    # 19 / 12 / 13 %, dents 15 mm) was a low dome beside the Calgary hat's tall loaf; the third reads as it does
    shoulder_p=4.2,         # the walls stand nearly straight and roll over into the ridges
    taper_x=0.10, taper_b=0.08, taper_f=0.08,
    top_n=(2.5, 2.6),
    # the two SIDE DENTS: each upper side wall pressed in, CENTRED along the top (dent_z: centre, half-extent in zeta)
    pinch_d=0.020, pinch_y=(0.78, 0.32), dent_z=(0.05, 1.10), pinch_side=(0.30, 0.85),
    roll=75.0, roll_p=2.0, roll_q=2.6,   # the sides curled up: +39 mm at the side edge, the front corners left low
    dip=16.0,               # front and back dipping: the edge 19 mm under the brim's root
    curl=0.0, curl_at=0.85,   # a cut felt edge, no lip
    bind_w=0.0, bind_t=0.0, bead_r=0.0,   # no binding: a raw cut edge (the Olympic hat, the store's felt hats)
    band_h=0.012, band_t=0.0008,          # a narrow band [M-eye: the Calgary hat's, a tenth of the crown's height]
    band_lines=(0.17, 0.33, 0.50, 0.67, 0.83), cord_amp=0.00012,
    knot_w=0.009, knot_t=0.0014,          # its keeper: a small wound loop on the wearer's left
    tails=(),
)
RANGER = dict(
    # THE PARK RANGER HAT, the U.S. National Park Service's "flat hat" (a campaign hat). [C] = the Service's own rules
    # (npshistory.com, "National Park Service Uniforms", section 8): the 1961 handbook's 3 1/4 in brim for an average
    # wearer (Office Order 324, 1936: "Stiff brim 3 to 3 1/2 inches wide, and 4 - 4 5/8 inch crown"); "belly" colour
    # felt (Order 350, 1938); three ventilator holes a side, an equilateral triangle, legs 1 in, its bottom leg 1 1/2 in
    # over the brim (Order 350). [M-eye] = set by eye until the clay lay on the three NPS photos (accessories_b5/refs/
    # felt_hats: the Everglades flat hat from the side, three hats at Agate Fossil Beds, the felt hat worn, cropped)
    crown_kind='montana',
    # [M] 130 mm: on the side view (photo 1) and the front view (photo 2) through the brim's 3 1/4 in, the crown stands
    # 130-150 mm; the 1936 order's 4 5/8 in (117.5) is the old felt hat's, and Stratton's F44 (today's NPS felt hat)
    # has "a taller crown" than its F40 (no published height found)
    crown_h=0.130,
    brim_w=0.0826,          # [C] 3 1/4 in
    # [M-eye] SIX CLAY TRIES beside the three photos (tmp/x/clay_ranger_t1..t6.png): t1 dented the DIAGONALS on a
    # pointed dome (a gnome's hat); read close (tmp/x/ranger_crowns_close.png) the dents are in the FACES, the corners
    # stand high, the walls nearly straight, the top broad; t3 dropped the top's centre with the dents (four bumps
    # round a hollow); t6: the drop fades in toward the axis (the PEAK keeps the full height), the dents wide.
    # (11-11 10:16 restart) t6 BAKED AND SEEN IN THE ENGINE beside the photos read as KNIFE SLOTS: its height map from
    # above was a plateau at full height over most of the top with dents 15-30 mm wide, the cross-section a V with
    # 45-50 degree walls and a 6 mm floor (bends of 35-42 degrees in its middle 8 mm). The real hat is the opposite
    # (the Agate photo from the front: the front dent 60 % of the crown's width at its top, 40 % of its height deep,
    # a smooth U; the NPS felt hat: broad shallow scoops, a rounded top). EIGHTEEN MORE TRIES (tmp/x/clay_ranger_t7 ..
    # t24, compared at the photos' cameras: clay_ranger_t6_t10_compare.png, _t11_t14_, _t15_t18_, _t19_t21_,
    # _t22_t24_compare.png): a cos (q 1) made the dents broad but the corners CREASES meeting in a spike (its low's
    # top folded 75 degrees); t22 kept: cos^2 of |u|^2 across each face (dent_k 2: a flat broad floor, ROUNDED corner
    # ridges, from above an X as the real peak), a rounder original top (shoulder 3.5) so the ridges fall from the
    # peak, shallower (in 0.32, down 0.26 of the crown), the drop fading in over 1.4 of the plan and the pull over
    # 0.6 (a rounded peak, not a nub: pull_core)
    shoulder_p=3.5, taper_x=0.06, taper_b=0.06, taper_f=0.06, top_n=(2.2, 2.2),
    dent_d=0.32, dent_w=0.78, dent_y=(0.42, 1.0), dent_drop=0.26, dent_q=2.0, dent_k=2.0, dent_core=1.4,
    pull_core=0.6,
    ring_space='th',        # the low's crown rings by the meridian's angle (build_low; HATS['ranger'] has them)
    roll=0.0, roll_p=2.0, roll_q=2.0, dip=0.0, curl=0.0, curl_at=0.9,   # a stiff FLAT brim
    bind_w=0.0, bind_t=0.0, bead_r=0.0,              # a raw cut edge (the felt hat's, photo 3)
    band_kind='leather', band_h=0.022, band_t=0.0015,   # the NPS leather hatband [M-eye: a fifth of the crown, photo 3]
    band_lines=(), cord_amp=0.0,
    bow_phi=70.0, knot_w=0.016, knot_t=0.0025,       # the band's lapped end and its keeper on the wearer's left
    tails=(),
    eyelets=dict(n=3, leg=0.0254, low=0.0381, phi=90.0),   # [C] Order 350: per side, centred on the side (phi +-90)
)
HATS = {
    'gus': dict(name='gus_hat', spec={}, title='GUS HAT (the Montana slope crease), a 1950 Stetson'),
    # the ranger's crown rings (RANGER's ring_space 'th'): the cap ring at th 85 deg (the inner 41 % of the top's
    # radius: where the dents meet in the peak), nine wall rings at th 75, 64, 52, 40, 30, 20, 12, 7 and 3 deg
    # (height shares 0.99 .. 0.30: the dents start at 0.42), the lining opposite the upper eight
    # its UVs (f04b_uv_search.py 14 <design> hat=ranger, 11-11 07:55, four designs side by side: 22.5 degree
    # keystones + the wall in two 75.9 %, 30 degree 76.8 %, + the wall in three 73.7 %, 45 degree 75.8 %): three
    # 30 degree keystones a brim face, the wall + band in two, the order below
    # (11-11 10:16 restart, Skye: "make sure they're also optimized as best you can!") THE FLAT BRIM's rings: the first
    # build carried the Gus's six (0.17 .. 0.90 of the brim, where ITS dip and lip turn) on a brim that is a plane:
    # 2 x 672 triangles lying flat on each other (p50 0.00 mm off the high). One ring at the middle keeps its quads'
    # aspect under 4 (83 mm of brim over 11-22 mm columns)
    # (the same restart) THE CAP RING FOR THE ROUNDER TOP: hh_cap 0.99952 was th 85 deg on the first crown (shoulder
    # 5.5: the inner 41 % of the top); on shoulder 3.5 it is th 87.7, the inner 16 % (13 mm): the 12 x 12 cap crammed
    # into the peak's tip (edges 1.3-2.8 mm, 2 x 288 triangles where nothing turns). 0.9913 = th 80 deg on shoulder
    # 3.5, the inner 37 %; the wall's rings keep their shares of the cap's angle
    'ranger': dict(name='ranger_hat', spec=RANGER, title='PARK RANGER HAT (the campaign hat, the NPS "flat hat")',
                   brim_u=(0.5,),
                   hh_cap=0.9913, wall_t=(0.882, 0.751, 0.609, 0.467, 0.349, 0.231, 0.136, 0.077, 0.030), n_lining=8,
                   # its UVs on the second crown and the flat brim's two rings (f04b_uv_search.py 14 <design>
                   # hat=ranger, 11-11 11:12, four designs side by side; the first build's order bisected gave
                   # 65.6 %): 30 degree keystones + the wall in two 75.5 %, + in three 74.7 %, 45 degree 70.0 %;
                   # FOUR 22.5 degree keystones + the wall in two 76.7 % at 6,467 px/m (0.155 mm a texel at the
                   # 2048 master)
                   brim_split=(39, 42, 45), crown_split=(36,), uv_ppm=6466.843579077125,
                   uv_order=('crownband0', 'crownband1', 'brim_under2', 'brim_upper0', 'brim_under3', 'brim_under0',
                             'brim_under1', 'brim_upper2', 'brim_upper3', 'brim_upper1', 'knot', 'inner_wall', 'top',
                             'inner_tip')),
    # the cattleman's UVs (scripts/f04b_uv_search.py <tries> <design> hat=cattleman, 11-11; out/uv_search_cattleman_
    # *.json keep every row): a 4 in brim and no tail strips to fill the holes, so the Gus's design (three 30 degree
    # keystones a brim face, the wall + band one island) packed 66.4 % in its recorded order and 69.1 % at best;
    # the wall + band cut in two 73.7 %, in three 72.7 %; 45 degree keystones 72.5 %; FOUR 22.5 degree keystones
    # + the wall in two: 77.4 % at 6,094 px/m (0.164 mm a texel), the order below
    'cattleman': dict(name='cowboy_hat', spec=CATTLEMAN, title='COWBOY HAT (the cattleman crease)',
                      brim_split=(39, 42, 45), crown_split=(36,), uv_ppm=6093.88283013777,
                      uv_order=('crownband1', 'top', 'brim_upper0', 'brim_under1', 'brim_under3', 'brim_under2',
                                'brim_upper2', 'brim_upper1', 'crownband0', 'brim_upper3', 'brim_under0', 'inner_wall',
                                'knot', 'inner_tip')),
}
NAME = 'cowboy_hat'         # the file stem of the hat in SPEC now (low_<NAME>.npz, T_<NAME>_*.png, <NAME>.glb). Until
#                             use() is called it is the 11-10 name of the Gus's files (out/forge*, kept as they are)
HAT = None                  # the HATS key in use


def use(hat):
    """make `hat` (a HATS key) THE hat this module builds: its numbers into SPEC and MATERIAL IN PLACE (every
    function's `spec=SPEC` default is that one dict: the scripts' own way for a trial), its file stem into NAME, its
    recorded UV placing into UV_ORDER / UV_PPM. Call it once, before anything is built. Returns the HATS row"""
    global NAME, HAT, UV_PPM, UV_ORDER, BRIM_SPLIT, CROWN_SPLIT, HH_CAP, WALL_T, N_LINING, BRIM_U
    h = HATS[hat]
    SPEC.update(h['spec'])
    MATERIAL.update(h.get('material', {}))
    NAME, HAT = h['name'], hat
    # its own island design (where each brim face's quadrant and the wall + band island are cut) and placing order
    UV_PPM, UV_ORDER = h.get('uv_ppm', UV_PPM), h.get('uv_order', UV_ORDER)
    BRIM_SPLIT, CROWN_SPLIT = h.get('brim_split', BRIM_SPLIT), h.get('crown_split', CROWN_SPLIT)
    # (11-11) its own crown rings: the cap ring's height share, the wall's rings and the lining's count
    HH_CAP, WALL_T, N_LINING = h.get('hh_cap', HH_CAP), h.get('wall_t', WALL_T), h.get('n_lining', N_LINING)
    # (11-11, Skye: "make sure they're also optimized as best you can!") its own brim rings: rings go where the form
    # turns; a FLAT brim (the ranger's) turns nowhere between its root and its edge
    BRIM_U = h.get('brim_u', BRIM_U)
    return h


K_LOW = 48                  # the low's columns round the hat (column 0 the front, K / 2 the back): the brim's edge
#                             (R 175-183 mm) then has 23-24 mm chords, sagitta 0.39 mm = 0.9 px at the 0.4 m portrait
RIBBON_ID = 200             # the sculpt's MATERIAL ID for the bow (knot, tails): past the growth and cyborg ranges
#                             (forge/growth.py ID_RANGES), so the bake treats it as plain relief and hands it per texel


# ----------------------------------------------------------------------------------------------------- helpers
def _smoothstep(a, b, x):
    t = np.clip((np.asarray(x, np.float64) - a) / (b - a), 0.0, 1.0)
    return t * t * (3.0 - 2.0 * t)


def _bump(u):
    """cos^2 (pi u / 2) on |u| < 1, else 0: a smooth dent profile (zero slope at its centre and at its ends)"""
    u = np.asarray(u, np.float64)
    return np.where(np.abs(u) < 1.0, np.cos(0.5 * np.pi * np.clip(u, -1.0, 1.0)) ** 2, 0.0)


def _unit(v):
    v = np.asarray(v, np.float64)
    return v / np.maximum(np.linalg.norm(v, axis=-1, keepdims=True), 1e-20)


def dims(spec=SPEC):
    """the head opening's semi-axes (an ellipse of the stated circumference and ratio: Ramanujan's perimeter), the
    crown's MID-SURFACE base oval (the opening + the sweatband + half the felt) on the brim's mid-plane, and the TOP's
    oval (the base oval taken in by the tapers, its centre moved back by the front's larger lean)"""
    k = spec['open_ratio']
    per = np.pi * (3.0 * (k + 1.0) - np.sqrt((3.0 * k + 1.0) * (k + 3.0)))      # perimeter of semi-axes (1, k)
    rx = spec['head_circ'] / per
    rz = k * rx
    off = spec['sweat_t'] + 0.5 * spec['felt_t']
    Bx, Bz = rx + off, rz + off
    return dict(rx_o=rx, rz_o=rz, Bx=Bx, Bz=Bz, y_mid=0.5 * spec['felt_t'], y0=spec['felt_t'],
                Tx=Bx * (1.0 - spec['taper_x']), Tz=Bz * (1.0 - 0.5 * (spec['taper_f'] + spec['taper_b'])),
                zt=0.5 * Bz * (spec['taper_b'] - spec['taper_f']))


def oval_r(phi, ax, az):
    """the polar radius of the ellipse of semi-axes ax (along X) and az (along Z) at azimuth phi (from +Z to +X)"""
    phi = np.asarray(phi, np.float64)
    return 1.0 / np.sqrt((np.sin(phi) / ax) ** 2 + (np.cos(phi) / az) ** 2)


def oval_normal(phi, ax, az):
    """the ellipse's outward unit normal in plan (x, z) at azimuth phi"""
    r = oval_r(phi, ax, az)
    x, z = r * np.sin(phi), r * np.cos(phi)
    n = np.stack([x / ax ** 2, z / az ** 2], -1)
    return n / np.linalg.norm(n, axis=-1, keepdims=True)


# ------------------------------------------------------------------------------------------------- the crown
def top_r(phi, spec=SPEC):
    """the polar radius of the TOP's plan outline at azimuth phi: a superellipse of semi-axes (Tx, Tz), its exponent
    top_n[0] on the front half and top_n[1] on the back half (2 an ellipse; larger a blunter, squarer end: this
    hat's top is broad across the back and narrows to the pinch). The halves meet at the sides with one tangent"""
    d = dims(spec)
    phi = np.asarray(phi, np.float64)
    c, s = np.cos(phi), np.sin(phi)
    n = np.where(c > 0.0, spec['top_n'][0], spec['top_n'][1])
    return (np.abs(s / d['Tx']) ** n + np.abs(c / d['Tz']) ** n) ** (-1.0 / n)


def _meridian_shares(th, p):
    """the crown's squircle meridian at angle th (0 the foot, pi / 2 the top's centre): (plan share, height share)"""
    th = np.clip(np.asarray(th, np.float64), 0.0, 0.5 * np.pi)
    return np.cos(th) ** (2.0 / p), np.sin(th) ** (2.0 / p)


def crown_plan(phi, th, spec=SPEC):
    """the crown's PLAN before the pinch, at azimuth phi and meridian angle th: x0, z0, the height share hh and zeta
    (the place along the top's oval: -1 its back, +1 its front). The wall runs straight from the base oval to the
    top's oval (the taper), then the squircle's shoulder rounds onto the top"""
    d = dims(spec)
    phi, th = np.broadcast_arrays(np.asarray(phi, np.float64), np.asarray(th, np.float64))
    rho, hh = _meridian_shares(th, spec['shoulder_p'])
    rad = oval_r(phi, d['Bx'], d['Bz']) * (1.0 - hh) + top_r(phi, spec) * hh
    x0 = rho * rad * np.sin(phi)
    z0 = d['zt'] * hh + rho * rad * np.cos(phi)
    return x0, z0, hh, (z0 - d['zt']) / d['Tz']


def _pw(pts, x):
    """a curve through the knots pts = ((x0, v0), (x1, v1), ...): a smoothstep between each pair (level at every
    knot, so its slope is continuous), the end values held outside"""
    x = np.asarray(x, np.float64)
    out = np.full(x.shape, float(pts[0][1]))
    for (xa, va), (xb, vb) in zip(pts[:-1], pts[1:]):
        out = np.where(x >= xa, va + (vb - va) * _smoothstep(xa, xb, x), out)
    return out


def ridge_share(zeta, spec=SPEC):
    """the ridges' height along the top, a share of crown_h. The Gus: 1 at the back, front_h at the front pinch. A
    hat with `ridge_pts` (the cattleman): the curve through those (zeta, share) knots"""
    if 'ridge_pts' in spec:
        return _pw(spec['ridge_pts'], zeta)
    return 1.0 - (1.0 - spec['front_h']) * _smoothstep(spec['slope'][0], spec['slope'][1], zeta)


def crease_depth(zeta, spec=SPEC):
    """the centre crease's depth under the ridges along the top (a share of crown_h); with `crease_pts` the curve
    through those (zeta, share) knots (the cattleman's crease runs the whole top and is deepest toward the front)"""
    if 'crease_pts' in spec:
        return _pw(spec['crease_pts'], zeta)
    return spec['crease_d'] * _smoothstep(spec['crease_z'][0], spec['crease_z'][1], zeta)


def dent_along(zeta, spec=SPEC):
    """how far the side walls' dent is in, along the top (0..1). The Gus's PINCH grows toward the front (pinch_z); a
    hat with `dent_z` = (centre, half-extent) has its two side dents CENTRED there (the cattleman)"""
    if 'dent_z' in spec:
        return _bump((np.asarray(zeta, np.float64) - spec['dent_z'][0]) / spec['dent_z'][1])
    return _smoothstep(spec['pinch_z'][0], spec['pinch_z'][1], zeta)


def crease_halfwidth(zeta, spec=SPEC):
    """the crease's half-width (m): the ridges stand this far from the midline"""
    wb, wf = spec['crease_w']
    return wb + (wf - wb) * _smoothstep(spec['crease_z'][0], 1.0, zeta)


def montana_point(phi, th, spec=SPEC):
    """(11-11) THE CAMPAIGN HAT'S CROWN, the park ranger's "flat hat" (Skye, 11-11: "should be maybe made into a park
    ranger hat or something?"): crown_plan's nearly straight wall and a square shoulder (a broad top), no crease and
    no ridge line along a top, and FOUR DENTS pressed into the top of its four FACES (front, back and the two sides:
    read close on the NPS photos, tmp/x/ranger_crowns_close.png: from the front the top shows the front dent's deep
    hollow between two high corners; from the side the side dent's): each takes the wall in toward the crown's axis
    by dent_d of its own plan radius (so the four meet at the top's centre and never cross it) and DOWN by dent_drop
    of the crown's height, across dent_w radians of azimuth (a cos^2 bump), growing from dent_y[0] of the height share
    to its fullest at dent_y[1]. The four CORNERS between them stand up as ridges into the peak: the "Montana" peak
    (npshistory.com, "National Park Service Uniforms" section 8: four dents, blocked at the factory since 1959)"""
    d = dims(spec)
    x0, z0, hh, _ = crown_plan(phi, th, spec)
    rho = _meridian_shares(th, spec['shoulder_p'])[0]     # the plan share (1 on the wall, 0 at the top's centre)
    cz = d['zt'] * hh                                     # the crown's axis at this height (the top's centre)
    a = np.mod(np.arctan2(x0, z0 - cz) + 0.25 * np.pi, 0.5 * np.pi) - 0.25 * np.pi   # the bearing to the nearest face
    # (11-11, the 10:16 restart) the dent ACROSS its face: cos^q of the bearing (q 2 = _bump, the first build). Seen
    # in the engine beside the NPS photos the first build's four dents were knife slots between broad flat corner
    # lobes (its height map from above: a plateau at full height over most of the top, the dents 15-30 mm wide);
    # the real Montana peak is the opposite: BROAD dents (the front one 60 % of the crown's width at its top, 40 %
    # of its height deep: the Agate photo) between NARROW corner ridges that fall from the peak. A smaller q keeps
    # the dent near full depth across most of its face and turns it up only near the corner (q 1: a cos), but leaves
    # the corner a CREASE (its slope does not reach 0 there) and the peak a spike where four creases meet; `dent_k`
    # > 1 flattens the dent's floor and keeps q 2's zero slope at the corner: broad dents between ROUNDED ridges, as
    # the photos show them (cos^q (pi / 2 |u|^k))
    u = np.clip(np.abs(a) / spec['dent_w'], 0.0, 1.0) ** spec.get('dent_k', 1.0)
    across = np.where(np.abs(a) < spec['dent_w'], np.cos(0.5 * np.pi * u) ** spec.get('dent_q', 2.0), 0.0)
    prof = across * _smoothstep(spec['dent_y'][0], spec['dent_y'][1], hh)
    dent = spec['dent_d'] * prof
    if spec.get('pull_core', 0.0) > 0.0:
        # (11-11 10:16 restart) the PULL fades in toward the axis too: pulled in at full strength right up to the peak,
        # the four faces narrowed the dome's apex into a nub between the ridges (the clay tries t15-t21)
        dent = dent * _smoothstep(0.0, spec['pull_core'], rho)
    # (the drop fades in toward the axis: the four dents meet in the PEAK, which keeps the crown's full height; the
    # first try dropped the centre with them and the top read as four corner bumps round a hollow)
    # (11-11 10:16 restart: `dent_core`, the plan share over which the drop fades in, 0.7 in the first build: its four
    # floors rose 21 mm over the last 17 mm to the axis, a spike at the peak; a wider core rounds the peak)
    y = d['y_mid'] + spec['crown_h'] * (hh - spec.get('dent_drop', 0.0) * prof
                                        * _smoothstep(0.0, spec.get('dent_core', 0.7), rho))
    return np.stack([x0 * (1.0 - dent), y, cz + (z0 - cz) * (1.0 - dent)], -1)


def crown_point(phi, th, spec=SPEC):
    """the creased crown's MID-SURFACE at (phi, th), (..., 3): the plan (crown_plan), its height under the top's
    field (the ridges' slope, the centre crease between them, the crease's pull fading out down the front wall), and
    the PINCH: the upper side walls pressed in toward the midplane near the front. (11-11: a `crown_kind` 'montana'
    hat, the ranger's, is montana_point's)"""
    if spec.get('crown_kind') == 'montana':
        return montana_point(phi, th, spec)
    d = dims(spec)
    x0, z0, hh, zeta = crown_plan(phi, th, spec)
    lo = _smoothstep(spec['crease_lo'][0], spec['crease_lo'][1], hh)
    H = spec['crown_h'] * (ridge_share(zeta, spec)
                           - crease_depth(zeta, spec) * _bump(x0 / crease_halfwidth(zeta, spec)) * lo)
    half = d['Bx'] * (1.0 - hh) + d['Tx'] * hh                       # the section's half-width at this height
    side = _smoothstep(spec['pinch_side'][0], spec['pinch_side'][1], np.abs(x0) / half)
    along = dent_along(zeta, spec)
    yc, yh = spec['pinch_y']
    dx = -np.sign(x0) * spec['pinch_d'] * along * _bump((hh - yc) / yh) * side
    return np.stack([x0 + dx, d['y_mid'] + H * hh, z0], -1)


def crown_frame(phi, th, spec=SPEC, e=1.0e-5):
    """the mid-surface's points P and outward unit normals N at (phi, th) (finite differences; at the top's centre
    the normal is taken a hair off the pole). The (phi, th) cross is outward on the wall and up on the top"""
    phi, th = np.broadcast_arrays(np.asarray(phi, np.float64), np.asarray(th, np.float64))
    th_c = np.clip(th, 2.0 * e, 0.5 * np.pi - 2.0 * e)
    P = crown_point(phi, th, spec)
    Pp = (crown_point(phi + e, th_c, spec) - crown_point(phi - e, th_c, spec)) / (2.0 * e)
    Pt = (crown_point(phi, th_c + e, spec) - crown_point(phi, th_c - e, spec)) / (2.0 * e)
    return P, _unit(np.cross(Pp, Pt))


def th_at_height(phi, y, spec=SPEC, n_iter=44):
    """the meridian angle at which the crown's WALL stands at height y, per azimuth (bisection: the height rises
    with th on the wall; y under the lowest shoulder)"""
    phi = np.asarray(phi, np.float64)
    y = np.broadcast_to(np.asarray(y, np.float64), phi.shape)
    lo, hi = np.zeros(phi.shape), np.full(phi.shape, 0.30 * np.pi)
    for _ in range(n_iter):
        mid = 0.5 * (lo + hi)
        up = crown_point(phi, mid, spec)[..., 1] < y
        lo = np.where(up, mid, lo)
        hi = np.where(up, hi, mid)
    return 0.5 * (lo + hi)


def plan_to_th(x0, z0, spec=SPEC, n_iter=44):
    """the (phi, th) whose PRE-PINCH plan point (crown_plan) lies at (x0, z0), for points on the top and the shoulder
    (bisection along th from the top's centre outward at the point's own bearing, two rounds: the top's centre moves
    with the height share)"""
    d = dims(spec)
    x0, z0 = np.broadcast_arrays(np.asarray(x0, np.float64), np.asarray(z0, np.float64))
    phi = np.arctan2(x0, z0 - d['zt'])
    th = np.full(x0.shape, 0.45 * np.pi)
    for _ in range(3):
        # at this bearing (about the centre at the current height share) the plan radius falls as th rises
        _, hh = _meridian_shares(th, spec['shoulder_p'])
        cz = d['zt'] * hh
        phi = np.arctan2(x0, z0 - cz)
        q = np.hypot(x0, z0 - cz)
        lo, hi = np.zeros(x0.shape), np.full(x0.shape, 0.5 * np.pi)
        for _ in range(n_iter):
            mid = 0.5 * (lo + hi)
            rho, h2 = _meridian_shares(mid, spec['shoulder_p'])
            r = rho * (oval_r(phi, d['Bx'], d['Bz']) * (1.0 - h2) + top_r(phi, spec) * h2)
            big = r > q
            lo = np.where(big, mid, lo)
            hi = np.where(big, hi, mid)
        th = 0.5 * (lo + hi)
    return phi, th


def crown_patch(spec=SPEC, n_phi=1440, step=0.00035, th0=0.0):
    """the crown's mid-surface as a triangle patch for the SHELL: n_phi columns, the meridian resampled to ~step of
    arc length (on the back's meridian, the longest), from th0 (the foot, buried in the brim) to a fan at the top's
    centre. Returns V (n, 3), F (m, 3)"""
    th = np.linspace(th0, 0.5 * np.pi, 20001)
    Pm = crown_point(np.full_like(th, np.pi), th, spec)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Pm, axis=0), axis=1))])
    n_s = int(np.ceil(1.15 * s[-1] / step)) + 1
    ths = np.interp(np.linspace(0.0, s[-1], n_s), s, th)[:-1]        # the pole itself is the fan's apex
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    PH, TH = np.meshgrid(phi, ths, indexing='ij')
    V = crown_point(PH, TH, spec).reshape(-1, 3)
    V = np.vstack([V, crown_point(0.0, 0.5 * np.pi, spec).reshape(1, 3)])
    ns = len(ths)
    i = np.arange(n_phi)[:, None]
    j = np.arange(ns - 1)[None, :]
    a = i * ns + j
    b = ((i + 1) % n_phi) * ns + j
    F = [np.stack([a, b, b + 1], -1).reshape(-1, 3), np.stack([a, b + 1, a + 1], -1).reshape(-1, 3)]
    top = np.arange(n_phi) * ns + (ns - 1)
    F.append(np.stack([top, np.roll(top, -1), np.full(n_phi, len(V) - 1)], -1))
    return V, np.concatenate(F)


# --------------------------------------------------------------------------------------------------- the brim
def brim_theta(phi, rho, spec=SPEC):
    """the brim meridian's angle above the horizontal (radians) at azimuth phi and arc length rho: the side roll, the
    front / back dip, the all-round edge curl (top_hat.brim_theta's terms, this hat's numbers)"""
    W = spec['brim_w']
    u = np.clip(np.asarray(rho, np.float64) / W, 0.0, 1.0)
    phi = np.asarray(phi, np.float64)
    S = np.abs(np.sin(phi)) ** spec['roll_q']
    C = np.cos(phi) ** 2
    return (S * np.radians(spec['roll']) * u ** spec['roll_p'] - C * np.radians(spec['dip']) * 4.0 * u * (1.0 - u)
            + np.radians(spec['curl']) * _smoothstep(spec['curl_at'], 1.0, u))


def _meridian(phi, rho, spec, n=1024):
    """the brim meridian at azimuths phi (M,): its horizontal offset X (along the base oval's plan normal) and rise Y,
    and its angle, at the arc lengths rho (N,) (negative rho: straight inward, inside the crown wall), each (M, N)"""
    W = spec['brim_w']
    g = np.linspace(0.0, W, n + 1)
    th = brim_theta(phi[:, None], g[None, :], spec)
    dx = 0.5 * (np.cos(th[:, 1:]) + np.cos(th[:, :-1])) * (W / n)
    dy = 0.5 * (np.sin(th[:, 1:]) + np.sin(th[:, :-1])) * (W / n)
    xg = np.concatenate([np.zeros((len(phi), 1)), np.cumsum(dx, 1)], 1)
    yg = np.concatenate([np.zeros((len(phi), 1)), np.cumsum(dy, 1)], 1)
    rc = np.clip(rho, 0.0, W)
    f = rc / (W / n)
    i0 = np.clip(np.floor(f).astype(np.int64), 0, n - 1)
    w = (f - i0)[None, :]
    X = xg[:, i0] * (1.0 - w) + xg[:, i0 + 1] * w
    Y = yg[:, i0] * (1.0 - w) + yg[:, i0 + 1] * w
    TH = brim_theta(phi[:, None], rc[None, :], spec)
    neg = rho < 0.0
    X[:, neg] = rho[neg][None, :]
    Y[:, neg] = 0.0
    TH[:, neg] = 0.0
    return X, Y, TH


def brim_frame(phi, rho, spec=SPEC, n_mer=1024):
    """the brim's MID-SURFACE at azimuths phi (M,) and arc lengths rho (N,) from the crown's mid-surface base oval:
    positions P, unit normals N (the upper face's side) and meridian tangents T, each (M, N, 3); n_mer: the
    meridian's integration steps"""
    phi = np.atleast_1d(np.asarray(phi, np.float64))
    rho = np.atleast_1d(np.asarray(rho, np.float64))
    d = dims(spec)

    def pos(ph):
        X, Y, TH = _meridian(ph, rho, spec, n_mer)
        r = oval_r(ph, d['Bx'], d['Bz'])
        n = oval_normal(ph, d['Bx'], d['Bz'])
        bx, bz = r * np.sin(ph), r * np.cos(ph)
        P = np.stack([bx[:, None] + X * n[:, None, 0], d['y_mid'] + Y, bz[:, None] + X * n[:, None, 1]], -1)
        return P, TH, n
    P, TH, n = pos(phi)
    T = np.stack([np.cos(TH) * n[:, None, 0], np.sin(TH), np.cos(TH) * n[:, None, 1]], -1)
    e = 1.0e-4
    Pphi = (pos(phi + e)[0] - pos(phi - e)[0]) / (2.0 * e)
    N = _unit(np.cross(T, Pphi))
    return P, N, T


def half_thickness(rho, spec=SPEC):
    """the brim's half-thickness: the felt, plus the binding's ribbon on both faces over its last bind_w (a 0.6 mm
    ramp: a ribbon's edge is not a knife; top_hat.half_thickness)"""
    e = spec['brim_w'] - spec['bind_w']
    return 0.5 * spec['felt_t'] + spec['bind_t'] * _smoothstep(e - 0.0003, e + 0.0003, rho)


def brim_patch(spec=SPEC, n_phi=1440, d_rho=0.0003):
    """the brim's mid-surface as a closed ring of triangles for the SHELL (top_hat.brim_patch: ~0.3 mm across, its
    inner edge buried spec['rho_in'] inside the crown's wall: its rounded end then stops 0.2 mm short of the head
    opening's face, behind the sweatband). Returns V, F and the per-vertex half-thickness"""
    W, rho_in = spec['brim_w'], spec['rho_in']
    rho = np.linspace(-rho_in, W, int(np.ceil((W + rho_in) / d_rho)) + 1)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    P, N, T = brim_frame(phi, rho, spec)
    nr = len(rho)
    i = np.arange(n_phi)[:, None]
    j = np.arange(nr - 1)[None, :]
    a = i * nr + j
    b = ((i + 1) % n_phi) * nr + j
    F = np.concatenate([np.stack([a, b, b + 1], -1).reshape(-1, 3), np.stack([a, b + 1, a + 1], -1).reshape(-1, 3)])
    return P.reshape(-1, 3), F, np.tile(half_thickness(rho, spec), n_phi)


# ---------------------------------------------------------------------------------- the band and the sweatband
def foot_slope(phi, spec=SPEC):
    """the crown wall's direction per unit of height at its foot (the meridian is straight there: the lean), (n, 3)
    with y = 1: how the wall is carried on below its foot (the sweatband's lower edge, the knot's overhang)"""
    phi = np.asarray(phi, np.float64)
    th_a = np.arcsin(0.04 ** (0.5 * spec['shoulder_p']))             # the meridian angle at the height share 0.04
    D = crown_point(phi, np.full(phi.shape, th_a), spec) - crown_point(phi, np.zeros(phi.shape), spec)
    return D / D[..., 1:2]


def wall_ring(phi, y, offset, spec=SPEC):
    """the points `offset` off the crown's mid-surface (+ outward, - inward, along its normal) where its wall stands
    at height y (below the wall's foot: the wall carried on along its own slope): the band's and the sweatband's
    edges, the low's wall rings. (n, 3) and the normals"""
    d = dims(spec)
    phi = np.asarray(phi, np.float64)
    y = np.broadcast_to(np.asarray(y, np.float64), phi.shape)
    ya = np.maximum(y, d['y_mid'] + 2.0e-4)
    P, N = crown_frame(phi, th_at_height(phi, ya, spec), spec)
    if (y < ya).any():
        P = P + (y - ya)[..., None] * foot_slope(phi, spec)
    off = np.broadcast_to(np.asarray(offset, np.float64), phi.shape)
    return P + off[..., None] * N, N


def strip_patch(y_lo, y_hi, offset, spec=SPEC, n_phi=1440, step=0.0003):
    """a strip over the crown's wall between the heights y_lo and y_hi, offset along the crown's normal (+ out, - in):
    the band (outside) and the sweatband (inside), as a triangle patch for a SHELL. Returns V, F and the rows'
    heights (a vertex's row is its index modulo their count)"""
    n_y = int(np.ceil((y_hi - y_lo) / step)) + 1
    ys = np.linspace(y_lo, y_hi, n_y)
    phi = np.linspace(0.0, 2.0 * np.pi, n_phi, endpoint=False)
    V = np.stack([wall_ring(phi, y, offset, spec)[0] for y in ys], 1).reshape(-1, 3)
    i = np.arange(n_phi)[:, None]
    j = np.arange(n_y - 1)[None, :]
    a = i * n_y + j
    b = ((i + 1) % n_phi) * n_y + j
    F = np.concatenate([np.stack([a, b, b + 1], -1).reshape(-1, 3), np.stack([a, b + 1, a + 1], -1).reshape(-1, 3)])
    return V, F, ys


def band_offset(spec=SPEC):
    """the band's MID-surface offset from the crown's (outward): over the felt's outer face"""
    return 0.5 * spec['felt_t'] + 0.5 * spec['band_t']


def sweat_offset(spec=SPEC):
    """the sweatband's MID-surface offset from the crown's (inward)"""
    return -(0.5 * spec['felt_t'] + 0.5 * spec['sweat_t'])


def cord_profile(v, spec=SPEC):
    """the corded ribbon's relief across its width (v: 0 one selvedge, 1 the other), 0..1: a rounded cord between
    each pair of neighbouring grooves (the selvedges and spec['band_lines']), 0 in the grooves"""
    v = np.clip(np.asarray(v, np.float64), 0.0, 1.0)
    e = np.array((0.0,) + tuple(spec['band_lines']) + (1.0,))
    i = np.clip(np.searchsorted(e, v, side='right') - 1, 0, len(e) - 2)
    return np.sin(np.pi * (v - e[i]) / (e[i + 1] - e[i])) ** 0.6


def band_face(spec=SPEC):
    """the band's outer face over the crown's mid-surface: the ribbon's ground, and its cords' crests"""
    g = 0.5 * spec['felt_t'] + spec['band_t']
    return g, g + spec['cord_amp']


def band_patch(spec=SPEC, n_phi=1440, step=0.0003):
    """the corded band for its SHELL: the strip over the wall from the brim's upper face up band_h, its half-thickness
    the ribbon's plus the cords' relief (a SHELL thickens both ways: the inner half lies in the felt). Returns V, F
    and the per-vertex half-thickness"""
    d = dims(spec)
    V, F, ys = strip_patch(d['y0'], d['y0'] + spec['band_h'], band_offset(spec), spec, n_phi, step)
    h = 0.5 * spec['band_t'] + spec['cord_amp'] * cord_profile((ys - ys[0]) / (ys[-1] - ys[0]), spec)
    return V, F, np.tile(h, n_phi)


def band_point(phi, y, lift, spec=SPEC):
    """a point `lift` off the band's cord crests at azimuth phi and height y, and the wall's outward normal there
    (top_hat.band_point's role on a crown that is no surface of revolution)"""
    phi, y, lift = np.broadcast_arrays(np.asarray(phi, np.float64), np.asarray(y, np.float64),
                                       np.asarray(lift, np.float64))
    P, N = wall_ring(phi, y, 0.0, spec)
    return P + (band_face(spec)[1] + lift)[..., None] * N, N


def brim_point(phi, rho, side=1.0, lift=0.0, spec=SPEC, chunk=256):
    """PAIRED points on the brim: at (phi[i], rho[i]), `lift` off its upper (side +1) or under (-1) face. Returns the
    points, the face's outward normals, the meridian tangents T and the tangents along phi (unit), each (n, 3)"""
    phi = np.atleast_1d(np.asarray(phi, np.float64))
    rho = np.atleast_1d(np.asarray(rho, np.float64))
    out = [[], [], [], []]
    for s in range(0, len(phi), chunk):
        ph, rh = phi[s:s + chunk], rho[s:s + chunk]
        i = np.arange(len(ph))
        P, N, T = brim_frame(ph, rh, spec)
        P2 = brim_frame(ph + 1.0e-4, rh, spec)[0]
        P, N, T, A = P[i, i], N[i, i], T[i, i], _unit(P2[i, i] - P[i, i])
        h = half_thickness(rh, spec) + lift
        for o, a in zip(out, (P + side * h[:, None] * N, side * N, T, A)):
            o.append(a)
    return tuple(np.concatenate(o) for o in out)


# ----------------------------------------------------------------------------------------------------- block-out
def build_sdf(spec=SPEC):
    """the block-out: four SHELLs hard-unioned (k = 0: they overlap inside one another's felt, a smooth union would
    bulge the joins): the CROWN and the BRIM over their mid-surfaces, the corded BAND over the wall's outer face, the
    SWEATBAND inside it from the seat plane up sweat_h (its rounded lower edge is the head opening's edge)"""
    from .. import sdf
    prog = sdf.Program()
    Vc, Fc = crown_patch(spec)
    prog.shell(Vc, Fc, 0.5 * spec['felt_t'], k=0.0, maxd=0.02, name='crown')
    Vb, Fb, Hb = brim_patch(spec)
    prog.shell(Vb, Fb, Hb, k=0.0, maxd=0.02, name='brim')
    Vn, Fn, Hn = band_patch(spec)
    prog.shell(Vn, Fn, Hn, k=0.0, maxd=0.02, name='band')
    Vs, Fs, _ = strip_patch(0.5 * spec['sweat_t'], spec['sweat_h'], sweat_offset(spec), spec)
    prog.shell(Vs, Fs, 0.5 * spec['sweat_t'], k=0.0, maxd=0.02, name='sweatband')
    prog.hat = dict(spec=spec, dims=dims(spec))
    return prog


def extents(spec=SPEC):
    """the hat's own box (m): the brim's dip, roll and edge, the crown's top"""
    phi = np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False)
    P, N, T = brim_frame(phi, np.linspace(0.0, spec['brim_w'], 24), spec, n_mer=256)
    h = float(half_thickness(spec['brim_w'], spec)) + spec['bead_r']
    lo, hi = P.reshape(-1, 3).min(0) - h, P.reshape(-1, 3).max(0) + h
    hi[1] = dims(spec)['y_mid'] + spec['crown_h'] + 0.5 * spec['felt_t']
    return lo, hi


def bounds(spec=SPEC, pad=0.006):
    """the voxel grid's box (the hat's extents plus pad)"""
    lo, hi = extents(spec)
    return lo - pad, hi + pad


# ----------------------------------------------------------------------------------------------------------- low
REGIONS = ('top', 'crown', 'band', 'brim_upper', 'brim_under', 'inner_wall', 'inner_tip', 'tails')
TAIL_LIFT = 0.0013          # the tails' strips stand this far over the brim's upper face: clear of the brim's own low
#                             faces there (they stand up to 0.95 mm off the high: audit_low), 3 px at the 0.4 m portrait
TAIL_START = 0.008          # where the tails leave the band's foot (rho / W): 0.75 mm out from the crown's mid-surface,
#                             inside the band's face (1.5 mm out): they come out of the band under the knot, no gap
TAIL_LONG_U = (0.23, 0.45)  # the taut tail's stations over the brim's valley (rho / W), between its start and the brim's
#                             own rings from 0.66 W out, where it has landed and its faces follow the brim's (an even
#                             five stations left its last quad 0.17 mm over the brim's low faces across the curl)
HH_CAP = 0.86               # the cap ring's height share: the top | crown seam, on the shoulder outside the ridges
WALL_T = (0.886, 0.771, 0.629, 0.457, 0.229)    # the wall's rings between the band's top (0) and the cap ring (1), as
#                             shares of each column's own height share between them: denser through the pinch's
#                             dents (height shares 0.44-0.86) than down the straight lean under them
BRIM_U = (0.17, 0.34, 0.50, 0.66, 0.80, 0.90)   # the brim's rings between the band's foot and the edge (rho / W): the
#                             dip's S turns 34.5 deg by mid-brim and back by 0.8, the lip curls 30 deg over the rest
N_LINING = 4                # the lining's rings stand OPPOSITE the wall's first N_LINING (the same stations, the felt's
#                             inner face): with one ring of its own the lining's chords crossed the wall's at the dents
#                             (2.8 mm off the high; the felt is 1.4), and a shadow pass draws back faces
CAP_RELAX = 40              # the cap grid's fairing passes in plan (each inner vertex to its four neighbours' mean,
#                             the centre line and the ridge lines kept on theirs): a Coons patch alone left its
#                             corner quads slivers (min corner angle 10 deg)
PX_MM = 0.43                # a pixel at the closest view the budget is derived from (a 0.4 m portrait at 1080 lines:
#                             HIGH_TO_LOW "The order" 6), in mm


def _th_of_hh(hh, spec=SPEC):
    """the meridian angle at a height share"""
    return np.arcsin(np.clip(np.asarray(hh, np.float64), 0.0, 1.0) ** (0.5 * spec['shoulder_p']))


def _hh_of_th(th, spec=SPEC):
    return np.sin(np.asarray(th, np.float64)) ** (2.0 / spec['shoulder_p'])


def crest_x(z0, x_max, spec=SPEC, n=241):
    """where the top's transverse section stands highest: per (pre-pinch) plan station z0, the x0 in (0, x_max) of
    the surface's greatest height (the RIDGE's crest; 0 where the top is a plain dome: the back, before the crease
    starts). The cap's ridge lines are drawn on it"""
    z0 = np.atleast_1d(np.asarray(z0, np.float64))
    x_max = np.broadcast_to(np.asarray(x_max, np.float64), z0.shape)
    u = np.linspace(0.0, 1.0, n)
    X = u[None, :] * x_max[:, None]
    ph, th = plan_to_th(X, np.repeat(z0[:, None], n, 1), spec)
    y = crown_point(ph, th, spec)[..., 1]
    return X[np.arange(len(z0)), y.argmax(1)]


def cap_plan(spec=SPEC, K=K_LOW, log=None):
    """the cap's (K / 4 + 1)^2 grid in the crown's PRE-PINCH plan (x0, z0): G[a, j], a across (a = n / 2 the centre
    line, a > n / 2 the wearer's left), j from the back (0) to the front (n). Its boundary is the cap ring's K
    vertices (column k at G[n / 2 + k, n] across the front, and on round: cap_ring_index); the inside a Coons patch
    over that ring, then each cross line stretched about the centre so the lines a = n / 2 +- n / 4 lie ON the
    ridges' crests (crest_x), kept within +-25 % of where the Coons patch had them (at the back the top is a plain
    dome with no crest: the lines stay fair)"""
    n = K // 4
    th_c = float(_th_of_hh(HH_CAP, spec))
    phi = 2.0 * np.pi * np.arange(K) / K
    x0, z0, _, _ = crown_plan(phi, np.full(K, th_c), spec)
    ring = np.column_stack([x0, z0])
    idx = cap_ring_index(K)
    G = np.zeros((n + 1, n + 1, 2))
    for (a, j), k in idx.items():
        G[a, j] = ring[k]
    u = np.arange(n + 1) / n
    for a in range(1, n):
        for j in range(1, n):
            G[a, j] = ((1 - u[j]) * G[a, 0] + u[j] * G[a, n] + (1 - u[a]) * G[0, j] + u[a] * G[n, j]
                       - (1 - u[a]) * (1 - u[j]) * G[0, 0] - u[a] * (1 - u[j]) * G[n, 0]
                       - (1 - u[a]) * u[j] * G[0, n] - u[a] * u[j] * G[n, n])
    h, q = n // 2, n // 4
    if spec.get('crown_kind') == 'montana':
        # (11-11) THE CAMPAIGN HAT'S TOP: its dents' middle lines run along the grid's two centre lines (x0 = 0 and the
        # cross line through the top's centre) and its four corner ridges along the grid's DIAGONALS (they pass through
        # grid vertices): the Coons patch, faired, with its centre line held on x0 = 0 and its own mirror, no ridge
        # stretching (crest_x finds a crease's ridges; this top has none)
        for _ in range(CAP_RELAX):
            M = 0.25 * (G[:-2, 1:-1] + G[2:, 1:-1] + G[1:-1, :-2] + G[1:-1, 2:])
            M[h - 1, :, 0] = 0.0
            G[1:-1, 1:-1] = M
        G[1:-1, 1:-1, 0] = 0.5 * (G[1:-1, 1:-1, 0] - G[-2:0:-1, 1:-1, 0])
        G[1:-1, 1:-1, 1] = 0.5 * (G[1:-1, 1:-1, 1] + G[-2:0:-1, 1:-1, 1])
        if log:
            log('[cowboy_hat] cap: the campaign hat\'s top, a faired Coons grid (the dents on its centre lines, the '
                'corners on its diagonals)')
        return G
    rows = []
    for j in range(1, n):
        xs, xr = G[n, j, 0], G[h + q, j, 0]                           # the side boundary's and the ridge line's x
        xc = float(crest_x(G[h + q, j, 1], xs, spec)[0])
        xt = float(np.clip(xc, 0.75 * xr, 1.25 * xr))
        rows.append((j, G[h + q, j, 1], xr, xc, xt))
    xt = np.array([r[4] for r in rows])
    xt[1:-1] = 0.25 * xt[:-2] + 0.5 * xt[1:-1] + 0.25 * xt[2:]        # one fairing pass along the line
    # `cap_shares` (a hat with a DEEP crease: the cattleman): where the lines between the centre line and a ridge
    # line stand, as shares of the crest's distance (q - 1 numbers). Even thirds left the crease's bottom cells
    # 1.54 mm off the high (a cos^2 valley 36 mm deep turns hardest at its bottom and at its crest, and not at all
    # half way up its wall): lines at 0.22 and 0.78 put the loops where it turns
    shares = spec.get('cap_shares')
    for (j, _, xr, _, _), x_new in zip(rows, xt):
        xs = G[n, j, 0]
        for a in range(h + 1, n):
            x = G[a, j, 0]
            G[a, j, 0] = x * x_new / xr if x <= xr else x_new + (x - xr) * (xs - x_new) / (xs - xr)
            if shares and a < h + q:
                G[a, j, 0] = shares[a - h - 1] * x_new
            G[n - a, j, 0] = -G[a, j, 0]
    for _ in range(CAP_RELAX):
        M = 0.25 * (G[:-2, 1:-1] + G[2:, 1:-1] + G[1:-1, :-2] + G[1:-1, 2:])
        M[h - 1, :, 0] = 0.0                                          # the centre line stays on the crease
        M[h + q - 1, :, 0] = xt                                       # the ridge lines stay on the crests
        M[h - q - 1, :, 0] = -xt
        for i, sh in enumerate(shares or ()):                         # and the crease's own lines on its walls
            M[h + i, :, 0] = sh * xt
            M[h - 2 - i, :, 0] = -sh * xt
        G[1:-1, 1:-1] = M
    G[1:-1, 1:-1, 0] = 0.5 * (G[1:-1, 1:-1, 0] - G[-2:0:-1, 1:-1, 0])  # (its own mirror to the bit)
    G[1:-1, 1:-1, 1] = 0.5 * (G[1:-1, 1:-1, 1] + G[-2:0:-1, 1:-1, 1])
    if log:
        log('[cowboy_hat] cap: the ridge lines (a = n/2 +- n/4) per cross line, mm: z0 | the Coons x | the crest | '
            'drawn: ' + '; '.join(f'{z * 1e3:+.0f} | {xr * 1e3:.1f} | {xc * 1e3:.1f} | {xn * 1e3:.1f}'
                                  for (_, z, xr, xc, _), xn in zip(rows, xt)))
    return G


def cap_ring_index(K=K_LOW):
    """{(a, j): k}: the cap grid's boundary cells and the ring column each one is (column 0 at the middle of the
    front side, the columns counter-clockwise seen from above: +X (the wearer's left) at K / 4)"""
    n = K // 4
    h = n // 2
    idx = {}
    for m in range(-h, h + 1):
        idx[(h + m, n)] = m % K                                       # the front side
    for j in range(n, -1, -1):
        idx[(n, j)] = (h + (n - j)) % K                               # the left side, front to back
    for a in range(n, -1, -1):
        idx[(a, 0)] = (h + n + (n - a)) % K                           # the back side, left to right
    for j in range(0, n + 1):
        idx[(0, j)] = (h + 2 * n + j) % K                             # the right side, back to front
    return idx


def stations(spec=SPEC):
    """the low's rings in order, from the cap ring down the outside, round the brim's bound edge, back under it and
    up the inside to the lining's cap ring: (name, kind, value). Kinds: 'wall' (the share of the column's height
    share between the band's top and the cap ring; the felt's outer face), 'band' (a height; the ribbon's face),
    'brim' (rho / W, side), 'edge' (the apex), 'open' (a height; the sweatband's face), 'lining' (a wall ring's own
    share: the felt's inner face opposite it)"""
    d = dims(spec)
    S = [('tc', 'wall', 1.0)]
    S += [(f'w{i}', 'wall', t) for i, t in enumerate(WALL_T)]
    S += [('bt', 'band', d['y0'] + spec['band_h']), ('b0', 'band', d['y0'])]
    S += [(f'u{i}', 'brim', (u, +1)) for i, u in enumerate(BRIM_U)]
    S += [('eu', 'brim', (1.0, +1)), ('e0', 'edge', 0.0), ('ed', 'brim', (1.0, -1))]
    S += [(f'd{i}', 'brim', (u, -1)) for i, u in reversed(list(enumerate(BRIM_U)))]
    S += [('oc', 'open', 0.0), ('st', 'open', spec['sweat_h'])]
    S += [(f'i{i}', 'lining', WALL_T[i]) for i in reversed(range(N_LINING))]
    S += [('ic', 'lining', 1.0)]
    return S


def opposite_names():
    """{ring: the ring on the felt's other face}: wall | lining, the brim's upper | under"""
    o = {'tc': 'ic', 'eu': 'ed'}
    o.update({f'w{i}': f'i{i}' for i in range(N_LINING)})
    o.update({f'u{i}': f'd{i}' for i in range(len(BRIM_U))})
    return o


def tail_strips(spec=SPEC):
    """the bow's two TAILS as AUTHORED STRIPS (WORKING_RULES 2: a flat panel carries only its outline), not as relief
    on the brim: the brim then keeps its four-fold symmetry (one quadrant's texels, island_keys), and the photo's long
    tail does not lie on the brim at all (view A: taut from the knot to the edge, its shadow under it).
      * the SHORT tail lies on the brim, TAIL_LIFT over its upper face; its stations stand ON the brim's own rings
        (BRIM_U), so its faces run parallel to the brim's low faces under it;
      * the LONG tail is TAUT: a straight line from the knot to its end near the binding, resting on the brim only
        where the brim rises to it.
    A ribbon does not bend sideways: each centre line is STRAIGHT IN PLAN between its two ends (the first strips ran
    straight in (phi, rho) and unrolled with 20-30 degree kinks at their stations). Both leave the band's foot
    (TAIL_START) cut ALONG the band (a square cut on a tail that leaves at 41 degrees put one corner 3.9 mm through
    the wall). Per tail: dict(name, P (n, 2, 3) the stations' two edge points, S (n, 2) each point's distance along
    the tail from its start (m), N (n, 3) the brim's normal under the station, w)"""
    from scipy.spatial import cKDTree
    W = spec['brim_w']
    out = []
    for k, (w, (p0, u0), (p1, u1)) in enumerate(spec['tails']):
        taut = k == 1
        # the brim's upper face, TAIL_LIFT over it, on a fine (phi, rho) grid round the tail (0.25 mm): its height
        # and normal under any plan point
        gp = np.radians(np.linspace(min(p0, p1) - 8.0, max(p0, p1) + 8.0, 361))
        gr = np.linspace(0.0, W, 371)
        Pg, Ng, _ = brim_frame(gp, gr, spec)
        Pg = (Pg + (half_thickness(gr, spec) + TAIL_LIFT)[None, :, None] * Ng).reshape(-1, 3)
        Ng, Ug = Ng.reshape(-1, 3), np.tile(gr / W, len(gp))
        tree = cKDTree(Pg[:, [0, 2]])
        ends = brim_frame(np.radians([p0, p1]), np.array([TAIL_START, u1]) * W, spec)
        A, B = (ends[0][j, j] + (float(half_thickness(u * W, spec)) + TAIL_LIFT) * ends[1][j, j]
                for j, u in ((0, TAIL_START), (1, u1)))
        sd = np.linspace(0.0, 1.0, 801)
        line = A[None] + sd[:, None] * (B - A)[None]
        near = tree.query(line[:, [0, 2]])[1]
        y = np.maximum(line[:, 1], Pg[near, 1]) if taut else Pg[near, 1]
        ud = Ug[near]
        # the stations: the two ends, the brim's rings the tail crosses where it lies on the brim, and two more over
        # the valley the taut tail bridges
        marks = [u for u in BRIM_U if (0.60 if taut else TAIL_START) < u < u1] + (list(TAIL_LONG_U) if taut else [])
        si = sorted({0, len(sd) - 1} | {int(np.argmin(np.abs(ud - u))) for u in marks})
        C = np.column_stack([line[si, 0], y[si], line[si, 2]])
        N = Ng[near[si]]
        t = _unit(np.gradient(C, axis=0))
        b = _unit(np.cross(N, t))
        E = np.stack([C - 0.5 * w * b, C + 0.5 * w * b], 1)
        s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(C, axis=0), axis=1))])
        S2 = np.repeat(s[:, None], 2, 1)
        # the start: each side slid along the tail until it stands on the band's foot line again
        Tr = ends[2][0, 0]
        sl = 0.5 * w * float(b[0] @ Tr) / float(t[0] @ Tr)
        for j, sg in enumerate((-1.0, 1.0)):
            E[0, j] -= sg * sl * t[0]
            S2[0, j] -= sg * sl
        out.append(dict(name=('the short tail (lying on the brim)', 'the long tail (taut over the brim)')[k], P=E,
                        S=S2 - S2.min(), N=N, w=w))
    return out


SEAM_RINGS = ('tc', 'bt', 'b0', 'e0', 'oc', 'ic')         # the rings between regions, in station order
HARD_RINGS = ('b0', 'oc')                                  # of those, the two real corners (the band's foot on the
#                                                            brim, the head opening's edge): split normals


def build_low(spec=SPEC, K=K_LOW, prog=None, log=print):
    """the AUTHORED low (WORKING_RULES 2; craft guide 05.13, 05.18): one ring of K per station (columns at
    phi = 2 pi k / K: 0 the front, K / 4 the wearer's left, K / 2 the back), quads between consecutive rings, and a
    (K / 4)^2 grid cap on the top and on the lining's top (cap_plan: the middle line on the crease, the lines three
    out on the ridges' crests). Every vertex lies ON the block-out by construction (the same crown_point /
    brim_frame, offset by the felt's half-thickness), and the hat is its own mirror in x to the bit.
    attrs['attr'] = (rho / W on the brim (1 on the edge), else -1; +1 upper / -1 under / 0; 0; 0).
    Returns the QuadMesh and info: stations, ring ids (n_rings, K), the caps' grids, per quad its region, strip
    (-1 on a cap) and column (the cap's a index there), per vertex its mirror twin and the vertex OPPOSITE it on the
    felt's other face (-1: none)"""
    from ..mesh import QuadMesh
    d = dims(spec)
    S = stations(spec)
    names = [s[0] for s in S]
    phi = 2.0 * np.pi * np.arange(K) / K
    W, ft = spec['brim_w'], spec['felt_t']
    g0, g1 = band_face(spec)
    g_band = 0.5 * (g0 + g1)
    g_open = -(0.5 * ft + spec['sweat_t'])
    hh_bt = _hh_of_th(th_at_height(phi, d['y0'] + spec['band_h'], spec), spec)
    us = sorted({v[0] for _, kd, v in S if kd == 'brim'})
    Pb, Nb, Tb = brim_frame(phi, np.array(us) * W, spec)
    col = {u: i for i, u in enumerate(us)}
    rings, attr = [], []
    for nm, kd, v in S:
        a = (-1.0, 0.0)
        if kd in ('wall', 'lining'):
            if spec.get('ring_space') == 'th':
                # (11-11) THE CAMPAIGN HAT: its four dents lie mostly on a FLAT top (shoulder_p 5.5: the height share
                # is over 0.96 on three quarters of the top's radius), so its rings are spaced by the meridian's
                # ANGLE th and carry the top as well as the wall (spaced by height share they crowded onto the wall
                # and left the dents to the cap's grid: top folds p90 53 deg, max 85, tmp/f03_low_ranger_flat.png);
                # its columns stand on the dents' troughs (0, 12, 24, 36) and on the corners' ridges (6, 18, ...)
                tb = _th_of_hh(hh_bt, spec)
                th_r = tb + v * (float(_th_of_hh(HH_CAP, spec)) - tb)
            else:
                th_r = _th_of_hh(hh_bt + v * (HH_CAP - hh_bt), spec)
            Pm, Nm = crown_frame(phi, th_r, spec)
            pos = Pm + (0.5 if kd == 'wall' else -0.5) * ft * Nm
        elif kd == 'band':
            pos = wall_ring(phi, v, g_band, spec)[0]
            a = (g_band / W, 1.0) if nm == 'b0' else a
        elif kd == 'open':
            pos = wall_ring(phi, v, g_open, spec)[0]
            a = (0.0, -1.0) if nm == 'oc' else a
        elif kd == 'brim':
            j = col[v[0]]
            pos = Pb[:, j] + v[1] * float(half_thickness(v[0] * W, spec)) * Nb[:, j]
            a = (v[0], float(v[1]))
        else:
            j = col[1.0]
            pos = Pb[:, j] + float(half_thickness(W, spec)) * Tb[:, j]
            a = (1.0, 0.0)
        rings.append(pos)
        attr.append(np.tile([a[0], a[1], 0.0, 0.0], (K, 1)))
    nR = len(S)
    ids = np.arange(nR * K).reshape(nR, K)
    V = np.concatenate(rings)
    A4 = np.concatenate(attr)
    k = np.arange(K)
    k1 = (k + 1) % K
    Q = np.concatenate([np.stack([ids[i, k], ids[i, k1], ids[i + 1, k1], ids[i + 1, k]], -1) for i in range(nR - 1)])
    reg_of_strip, r = [], 1
    for i in range(nR - 1):
        if i > 0 and names[i] in SEAM_RINGS:
            r += 1
        reg_of_strip.append(r)
    quad_region = np.repeat(reg_of_strip, K)
    quad_strip = np.repeat(np.arange(nR - 1), K)
    quad_col = np.tile(k, nR - 1)
    # the winding: the first wall strip's quads face away from the axis
    c = V[Q[:K]].mean(1)
    n0 = np.cross(V[Q[:K, 2]] - V[Q[:K, 0]], V[Q[:K, 3]] - V[Q[:K, 1]])
    if (n0 * (c * [1.0, 0.0, 1.0])).sum() < 0.0:
        Q = Q[:, ::-1].copy()
    # the caps: the outer top on the cap ring (ids[0]), the lining's top on the last ring
    n = K // 4
    Gp = cap_plan(spec, K, log=log)
    ph_c, th_c = plan_to_th(Gp[..., 0], Gp[..., 1], spec)
    Pm, Nm = crown_frame(ph_c, th_c, spec)
    idx = cap_ring_index(K)
    mirror = np.concatenate([ids[:, (K - k) % K].ravel()])
    opp = -np.ones((nR, K), np.int64)
    for a_, b_ in opposite_names().items():
        ia, ib = names.index(a_), names.index(b_)
        opp[ia], opp[ib] = ids[ib], ids[ia]
    opp = opp.ravel()
    grids = []
    for s, ring_ids, up in ((+1.0, ids[0], 1.0), (-1.0, ids[-1], -1.0)):
        G = -np.ones((n + 1, n + 1), np.int64)
        for (a, j), kk in idx.items():
            G[a, j] = ring_ids[kk]
        inner = [(a, j) for a in range(1, n) for j in range(1, n)]
        base = len(V)
        for m, (a, j) in enumerate(inner):
            G[a, j] = base + m
        V = np.vstack([V, np.array([Pm[a, j] + s * 0.5 * ft * Nm[a, j] for a, j in inner])])
        A4 = np.vstack([A4, np.tile([-1.0, 0.0, 0.0, 0.0], (len(inner), 1))])
        mirror = np.concatenate([mirror, [G[n - a, j] for a, j in inner]])
        cq = np.array([[G[a, j], G[a + 1, j], G[a + 1, j + 1], G[a, j + 1]] for a in range(n) for j in range(n)])
        nn = np.cross(V[cq[:, 2]] - V[cq[:, 0]], V[cq[:, 3]] - V[cq[:, 1]])
        if (nn[:, 1] * up).sum() < 0.0:
            cq = cq[:, ::-1].copy()
        Q = np.vstack([Q, cq])
        quad_region = np.concatenate([quad_region, np.full(len(cq), REGIONS.index('top' if s > 0 else 'inner_tip'))])
        quad_strip = np.concatenate([quad_strip, np.full(len(cq), -1)])
        quad_col = np.concatenate([quad_col, np.repeat(np.arange(n), n)])
        grids.append(G)
    n_in = (n - 1) * (n - 1)                                          # the two caps' inner vertices face each other
    base = nR * K
    opp = np.concatenate([opp, base + n_in + np.arange(n_in), base + np.arange(n_in)])
    # its own mirror to the bit: each twin pair takes the mean of one and the other reflected
    Vm = V[mirror] * [-1.0, 1.0, 1.0]
    V = 0.5 * (V + Vm)
    on = mirror == np.arange(len(V))
    V[on, 0] = 0.0
    body = QuadMesh(V, Q, {'attr': A4})
    # the ring vertices' twins front <-> back (z -> -z: column k <-> K / 2 - k): the BRIM's rings are that mirror
    # too (the crown's are not: the pinch); -1 on the caps
    mirror_z = np.concatenate([ids[:, (K // 2 - k) % K].ravel(), -np.ones(len(V) - nR * K, np.int64)])
    chk = body.check()
    log(f'[cowboy_hat] low, the felt body: {len(body.V)} verts, {len(body.Q)} quads ({2 * len(body.Q)} tris), {nR} '
        f'rings x {K} + two {n} x {n} caps; check {chk}; mirror: {int(on.sum())} vertices on the plane, twins apart '
        f'{np.abs(V[mirror] * [-1.0, 1.0, 1.0] - V).max() * 1e6:.3f} um')
    if prog is not None:
        f = prog.eval(body.V)
        log(f'[cowboy_hat] low on the block-out: |sdf| p50 {np.median(np.abs(f)) * 1e6:.1f} um, p99 '
            f'{np.percentile(np.abs(f), 99) * 1e6:.1f} um, max {np.abs(f).max() * 1e6:.1f} um')
    # the bow's two TAILS: their own strips (tail_strips), an upper face and the same face turned over (the same
    # places, the winding reversed: a camera under the taut tail sees ribbon, not through it)
    nb = len(V)
    under = -np.ones(nb, np.int64)
    r_tail = REGIONS.index('tails')
    for kt, tl in enumerate(tail_strips(spec)):
        ns = len(tl['P'])
        top = len(V) + np.arange(2 * ns).reshape(ns, 2)
        bot = top + 2 * ns
        Pt = tl['P'].reshape(-1, 3)
        # attr: (-1: not the brim; 0; the distance from the tail's frayed END (m); the place across it in cord
        # pitches, 0 its middle): the material pass's ribbon coordinates, no search for them at paint time
        At = np.column_stack([-np.ones(2 * ns), np.zeros(2 * ns), (tl['S'].max() - tl['S']).ravel(),
                              np.tile([-0.5, 0.5], ns) * tl['w'] / tail_pitch(tl['w'], spec)])
        V = np.vstack([V, Pt, Pt])
        A4 = np.vstack([A4, At, At])
        qt = np.array([[top[i, 0], top[i, 1], top[i + 1, 1], top[i + 1, 0]] for i in range(ns - 1)])
        nn = np.cross(V[qt[:, 2]] - V[qt[:, 0]], V[qt[:, 3]] - V[qt[:, 1]])
        if (nn * tl['N'][:-1]).sum() < 0.0:
            qt = qt[:, ::-1].copy()
        qb = (qt + 2 * ns)[:, ::-1].copy()
        Q = np.vstack([Q, qt, qb])
        quad_region = np.concatenate([quad_region, np.full(2 * (ns - 1), r_tail)])
        quad_strip = np.concatenate([quad_strip, np.full(2 * (ns - 1), -2)])
        quad_col = np.concatenate([quad_col, np.full(ns - 1, kt), np.full(ns - 1, kt + 2)])
        under = np.concatenate([under, -np.ones(2 * ns, np.int64), top.ravel()])
        if prog is not None:
            mid = 0.5 * (tl['P'][:-1] + tl['P'][1:]).reshape(-1, 3)
            fc = prog.eval(np.vstack([Pt, mid, tl['P'].mean(1), mid.reshape(-1, 2, 3).mean(1)])) * 1e3
            log(f'[cowboy_hat] low, {tl["name"]}: {ns - 1} quads a face, {tl["S"].max() * 1e3:.1f} x '
                f'{tl["w"] * 1e3:.0f} mm; over the block-out {fc.min():.2f} .. {fc.max():.2f} mm (the brim\'s own '
                f'faces stand up to 0.95 mm off it)')
    pad = -np.ones(len(V) - nb, np.int64)
    mirror, mirror_z, opp = (np.concatenate([a, pad]) for a in (mirror, mirror_z, opp))
    mesh = QuadMesh(V, Q, {'attr': A4})
    info = dict(stations=S, names=names, ids=ids, K=K, phi=phi, quad_region=quad_region, quad_strip=quad_strip,
                quad_col=quad_col, G_top=grids[0], G_in=grids[1], mirror=mirror, mirror_z=mirror_z, opp=opp,
                under=under, cap_n=n, n_body=nb, body_check=chk)
    log(f'[cowboy_hat] low: {len(mesh.V)} verts, {len(mesh.Q)} quads ({2 * len(mesh.Q)} tris) with the tails')
    return mesh, info


def audit_low(low, info, prog, n=5, log=print):
    """the budget's measure (WORKING_RULES 2: budgets derived from the closest view): how far the low's flat faces
    stand off the block-out between their vertices, per region: n x n bilinear samples a quad, |sdf| in mm and in
    pixels at the closest view (PX_MM). A rigid prop bends nowhere: the triangles go where the outline turns, and
    this table is where each region's count is read. Returns {region: dict(tris, p50, p95, max (mm))}"""
    V, Q = low.V, low.Q
    u = (np.arange(n) + 0.5) / n
    U, W_ = np.meshgrid(u, u, indexing='ij')
    U, W_ = U.ravel()[None, :, None], W_.ravel()[None, :, None]
    P = ((1 - U) * (1 - W_) * V[Q[:, 0]][:, None] + U * (1 - W_) * V[Q[:, 1]][:, None]
         + U * W_ * V[Q[:, 2]][:, None] + (1 - U) * W_ * V[Q[:, 3]][:, None])
    f = np.abs(prog.eval(P.reshape(-1, 3))).reshape(len(Q), -1) * 1e3
    out = {}
    lines = []
    for r, nm in enumerate(REGIONS):
        m = info['quad_region'] == r
        if not m.any():                              # (a hat without tails: the region is empty)
            continue
        x = f[m].ravel()
        out[nm] = dict(tris=int(2 * m.sum()), p50=float(np.median(x)), p95=float(np.percentile(x, 95)),
                       max=float(x.max()))
        lines.append(f'  {nm:>11s}: {2 * m.sum():5d} tris   off the high p50 {out[nm]["p50"]:.2f}  p95 '
                     f'{out[nm]["p95"]:.2f}  max {out[nm]["max"]:.2f} mm  = {out[nm]["p95"] / PX_MM:.1f} / '
                     f'{out[nm]["max"] / PX_MM:.1f} px at the 0.4 m portrait')
    log('[cowboy_hat] the low\'s faces against the high (a rigid prop: no region bends):\n' + '\n'.join(lines))
    return out, f


def quad_fold(V, Q, d02):
    """the angle (degrees) between each quad's two triangles across the diagonal named (True = corners 0-2): the
    boot round's quad-fold measure (HIGH_TO_LOW, the boot's (5)), reported per region by the low's script"""
    d = np.asarray(d02, bool)[:, None]
    a = np.where(d, Q[:, [0, 1, 2]], Q[:, [0, 1, 3]])
    b = np.where(d, Q[:, [0, 2, 3]], Q[:, [1, 2, 3]])
    na = _unit(np.cross(V[a[:, 1]] - V[a[:, 0]], V[a[:, 2]] - V[a[:, 0]]))
    nb = _unit(np.cross(V[b[:, 1]] - V[b[:, 0]], V[b[:, 2]] - V[b[:, 0]]))
    return np.degrees(np.arccos(np.clip((na * nb).sum(1), -1.0, 1.0)))


def quad_diagonals(low, info, prog=None):
    """per quad: True = split along corners 0-2, False = 1-3. With the block-out: the diagonal that LIES ON THE HIGH
    (the one whose middle is nearer the surface: a twisted quad split the other way stands a ridge or a gutter across
    the form, a row of them reads as sawteeth flat-shaded: the pinch's flanks, the crease's sides); where both lie
    within 20 um, and without a block-out, the shorter one (top_hat.low_arrays' rule). Then two designed agreements
    a per-quad rule cannot give: a face of the felt's INNER side takes the split of the face opposite it (split the
    other way than its twin 1.4 mm away it comes through it), and the LEFT half takes the right half's split
    mirrored (the left half's UVs are the right's: one bake has to fit both)"""
    V, Q = low.V, low.Q
    d02 = np.linalg.norm(V[Q[:, 0]] - V[Q[:, 2]], axis=1) <= np.linalg.norm(V[Q[:, 1]] - V[Q[:, 3]], axis=1)
    if prog is not None:
        f02 = np.abs(prog.eval(0.5 * (V[Q[:, 0]] + V[Q[:, 2]])))
        f13 = np.abs(prog.eval(0.5 * (V[Q[:, 1]] + V[Q[:, 3]])))
        d02 = np.where(np.abs(f02 - f13) > 2.0e-5, f02 < f13, d02)
        # (TRIED AND REFUSED, 11-10: flipping the quads this folds over 15 degrees to their other diagonal (12 wall
        # quads at 20-31 degrees at the pinch's foot, the other diagonal <= 17). The fold number passed and the
        # flat-shaded picture got WORSE: each flipped quad disagreed with its row and stood a gutter across the
        # form, a cluster of teeth at the pinch's foot (tmp/x_low_c_vs_d.png). The diagonal on the high stays;
        # quad_fold is reported, not obeyed)
    key = {frozenset(q.tolist()): i for i, q in enumerate(Q)}
    opp, mir = info['opp'], info['mirror']
    inner = np.isin(info['quad_region'], [REGIONS.index(r) for r in ('brim_under', 'inner_wall', 'inner_tip')])

    def take(i, m):
        j = key.get(frozenset(m[Q[i]].tolist()))
        if j is None or (m[Q[i]] < 0).any():
            return
        pair = {int(Q[j, 0]), int(Q[j, 2])} if d02[j] else {int(Q[j, 1]), int(Q[j, 3])}
        d02[i] = int(m[Q[i, 0]]) in pair
    cx, cz = V[Q][..., 0].mean(1), V[Q][..., 2].mean(1)
    brim = np.isin(info['quad_region'], [REGIONS.index(r) for r in ('brim_upper', 'brim_under')])
    for i in np.nonzero(brim & (cx < 0.0) & (cz < 0.0))[0]:          # the brim's right back takes its right front's
        take(i, np.asarray(info['mirror_z']))                        # (the four quadrants share one quadrant's UVs)
    for i in np.nonzero(inner & (cx < 0.0))[0]:
        take(i, opp)
    for i in np.nonzero(cx > 0.0)[0]:
        take(i, mir)
    for i in np.nonzero((np.asarray(info['under'])[Q] >= 0).all(1))[0]:   # a tail's turned-over face: its upper face's
        take(i, np.asarray(info['under']))
    return d02


def triangles(Q, d02):
    """the quads' two triangles each, along their chosen diagonals: (2 m, 3), quad i's at i and m + i"""
    d = np.asarray(d02, bool)[:, None]
    return np.concatenate([np.where(d, Q[:, [0, 1, 2]], Q[:, [0, 1, 3]]), np.where(d, Q[:, [0, 2, 3]], Q[:, [1, 2, 3]])])


# ----------------------------------------------------------------------------------------------------------- UVs
BRIM_QUAD = (36, 48)        # the brim's PRIMARY quadrant, columns 36 .. 48: the wearer's right front (x < 0, z > 0: the
#                             bow-less side, the face a portrait looks at). The brim is one shape four times (its roll
#                             goes as |sin phi|, its dip as cos^2 phi, on an ellipse): the other three quadrants of each
#                             face are its mirrors and share its texels (WORKING_RULES 3, 07.31)
BRIM_SPLIT = (40, 44)       # columns inside that quadrant where each brim face is cut: three 30 degree KEYSTONES, which
#                             nest head to tail (measured, scripts/f04b_uv_search.py, out/uv_search.json: a whole
#                             quarter ring 69.8 % of the sheet, two 45 degree keystones 70.7 %, three of 30: 75.7 %)
CROWN_SPLIT = ()            # columns of the right half (24 .. 48) where the wall + band island is cut again
KNOT_COLS = (10, 14)        # the UNIQUE patch of the band and of the wall strip over it: the wrapped knot stands at
#                             column 12 (+- 0.6) and 1.5 mm over the band's top edge; the rest of the band is the
#                             right half's mirror
INNER_SHARE = 0.25          # the inside's texel density relative to the outside (top_hat's: hidden when worn)
UV_PAD = 8                  # texels between islands at 2048 (Skye's low-poly notes: >= 8 px)
# the placing order pack_search found for this island design (the body's eleven primaries: scripts/f04b_uv_search.py,
# 'random 8' of 13 orders; the tails' strips appended, into the holes) and its density (px/m at 2048): unwrap places
# once, in seconds, instead of searching (an empty order: search). 77.4 % of the sheet
UV_ORDER = ('crownband', 'brim_under0', 'top', 'brim_upper2', 'brim_upper1', 'brim_under2', 'brim_upper0',
            'brim_under1', 'knot', 'inner_wall', 'inner_tip', 'tail0', 'tail1')
UV_PPM = 6273.432681590033
SMOOTH_GROUPS = ((0, 1, 2), (3, 4), (5, 6), (7,))   # regions shaded as one surface each: the normals split between
#                             them, at the band's foot on the brim and at the head opening's edge (HARD_RINGS), both UV
#                             seams; the tails' strips are their own


def island_keys(info):
    """per quad its island's name, and {name: None for a PRIMARY, else (its primary's name, how)}: how names the
    mirrors that carry a STACKED island onto its primary ('x' left <-> right, 'z' front <-> back, 'xz' both, 'u' a
    tail's turned-over face onto its upper face).
    WORKING_RULES 3 / 07.31, identical and mirrored parts share one set of shells:
      * the hat is its own mirror in x but for the bow: every island is the RIGHT half's (x < 0), the left stacked;
      * each brim face is one quadrant (BRIM_QUAD) four times, cut into keystones (BRIM_SPLIT);
      * unique, because the design differs there: the band's patch under the knot with the wall strip over it
        (KNOT_COLS), and the two tails (their own strips: an upper face each, the turned-over face stacked on it).
    The crown's wall and the band are ONE island (the band is the wall's own cone carried down: one arc, no strip
    of its own to pack); the top's cap and the inside (wall, tip) are the right halves"""
    K, n = info['K'], info['cap_n']
    reg, col, strip = info['quad_region'], info['quad_col'], info['quad_strip']
    s_band = info['names'].index('bt')              # the band's strip (bt -> b0); the wall strip over it is s_band - 1
    names, stacked = [], {}
    for r, c, s in zip(reg, col, strip):
        R, how = REGIONS[r], ''
        if R == 'tails':                            # its column: the tail (0, 1), + 2 on the turned-over face
            nm, how = f'tail{c % 2}', ('u' if c >= 2 else '')
        elif s < 0:                                 # a cap: its column is the grid's a index, a >= n / 2 the left
            nm, how = R, ('x' if c >= n // 2 else '')
        elif R in ('brim_upper', 'brim_under'):
            how = ('x' if c < K // 2 else '') + ('z' if K // 4 <= c < 3 * K // 4 else '')
            cp = {'': c, 'x': K - 1 - c, 'z': (K // 2 - 1 - c) % K, 'xz': c + K // 2}[how]
            assert BRIM_QUAD[0] <= cp < BRIM_QUAD[1], (c, how, cp)
            nm = f'{R}{sum(cp >= x for x in BRIM_SPLIT)}'
        elif R in ('crown', 'band'):
            if s in (s_band - 1, s_band) and KNOT_COLS[0] <= c < KNOT_COLS[1]:
                nm = 'knot'
            else:
                cr = c if c >= K // 2 else K - 1 - c                   # the quad's column on the right half
                nm = 'crownband' + (str(sum(cr >= x for x in CROWN_SPLIT)) if CROWN_SPLIT else '')
                how = 'x' if c < K // 2 else ''
        else:
            nm, how = R, ('x' if c < K // 2 else '')
        full = nm + ('~' + how if how else '')
        names.append(full)
        stacked[full] = (nm, how) if how else None
    return np.array(names), stacked


def _disc(r):
    y, x = np.mgrid[-r:r + 1, -r:r + 1]
    return (x * x + y * y) <= r * r + 0.25


def _raster(T, tri, g):
    """the cells (g texels a side) an island's triangles touch, T in texels: the mask and its first cell
    (red_tailed_hawk_uv._raster's result, drawn by PIL's polygon fill instead of a Python loop of barycentric tests
    per triangle: 100 x faster, and a touched cell counts (never thinner than the island))"""
    from PIL import Image, ImageDraw
    lo = np.floor(T.min(0) / g).astype(int)
    T2 = T / g - lo
    W, H = (np.ceil(T2.max(0)).astype(int) + 1)
    im = Image.new('L', (int(W), int(H)), 0)
    dr = ImageDraw.Draw(im)
    for a, b, c in T2[tri]:
        dr.polygon([(float(a[0]), float(a[1])), (float(b[0]), float(b[1])), (float(c[0]), float(c[1]))], fill=1,
                   outline=1)
    return np.asarray(im, bool), lo


def pack_raster(isls, size, pad=UV_PAD, g=4, turns=8, order=None):
    """a raster packer on the square sheet (forge/species/red_tailed_hawk_uv.py's _pack_raster and its _raster,
    changed four ways, the first three from HIGH_TO_LOW "Why a set plateaus"): the gutter is a DISC's dilation of the
    island being placed against the others' raw masks (the hawk's dilated both by a diamond: twice the gutter on the
    axes, less on the diagonals); an island goes where its outline TOUCHES the most occupied cells or the sheet's
    border (bottom-left placement leaves holes), so a small island takes a hole the larger ones enclose; the sheet
    is the square itself, so a layout that does not fit FAILS (the caller searches the density); and each island is
    tried at `turns` even orientations from its least-area box, not four (a quarter ring sits in the sheet's corner
    at 45 degrees, two keystones nest head to tail at 180). isls: [(T (n, 2) texels, tri (m, 3))]; order: the
    placing order (default: the largest mask first). Returns each island's UVs (0-1) or None when one finds no
    place"""
    from scipy import fft as sfft
    from scipy.ndimage import binary_dilation
    Wc = size // g
    pc = int(np.ceil(pad / g)) + 1                 # the gutter in cells (+1 for the masks' own rasterisation)
    B = pc + 3
    n_ = Wc + 2 * B
    O = np.zeros((n_, n_))
    O[:B], O[-B:], O[:, :B], O[:, -B:] = 1.0, 1.0, 1.0, 1.0           # beyond the sheet counts as taken
    s = sfft.next_fast_len(n_, real=True)
    cand = []
    for T, tri in isls:
        opts = []
        for k in range(turns):
            a = 2.0 * np.pi * k / turns
            Tr = T @ np.array([[np.cos(a), -np.sin(a)], [np.sin(a), np.cos(a)]]).T
            M, lo = _raster(Tr, tri, g)
            Mp = np.pad(M, pc + 2)
            if max(Mp.shape) > n_:
                continue
            fd = np.conj(sfft.rfft2(binary_dilation(Mp, structure=_disc(pc)).astype(np.float64), (s, s)))
            fc = np.conj(sfft.rfft2(binary_dilation(Mp, structure=_disc(pc + 2)).astype(np.float64), (s, s)))
            opts.append((Tr, lo, Mp, fd, fc))
        cand.append(opts)
    if order is None:
        order = sorted(range(len(isls)), key=lambda i: -max([int(o[2].sum()) for o in cand[i]] or [0]))
    out = [None] * len(isls)
    for i in order:
        best = None
        FO = sfft.rfft2(O, (s, s))                 # (valid correlations: no wrap reaches them while s >= n_)
        for Tr, lo, Mp, fd, fc in cand[i]:
            h, w = Mp.shape
            free = sfft.irfft2(FO * fd, (s, s))[:n_ - h + 1, :n_ - w + 1] < 0.5
            if not free.any():
                continue
            touch = np.where(free, sfft.irfft2(FO * fc, (s, s))[:n_ - h + 1, :n_ - w + 1], -1.0)
            ys, xs = np.nonzero(touch >= touch.max() - 0.5)
            k = np.lexsort((xs, ys))[0]
            c = (float(touch.max()), -int(ys[k]), -int(xs[k]), Tr, lo, Mp)
            if best is None or c[:3] > best[:3]:
                best = c
        if best is None:
            return None
        _, y, x, Tr, lo, Mp = best
        y, x = -y, -x
        O[y:y + Mp.shape[0], x:x + Mp.shape[1]] += Mp
        out[i] = (Tr - lo * g + (np.array([x, y]) - B + pc + 2) * g) / size
    return out


def flatten(low, info, d02, arap_iters=8, log=print):
    """the islands (island_keys) cut apart and each PRIMARY one unwrapped on the triangles that ship (LSCM, then the
    ARAP depth with the smallest worst-direction footprint among those that lie flat: top_hat.unwrap's rule), turned
    to its least-area box and scaled to metres (1 UV unit = 1 m of surface). Returns dict(V, Q, orig (the split
    low), names, stacked, keys, lab, isl: {name: vs, split_of, and for a primary Fl, uv, area, share, fp, arap,
    aniso})"""
    from .. import uv as U
    from ..species import red_tailed_hawk_uv as HU
    names, stacked = island_keys(info)
    keys = sorted(set(names))
    lab = np.array([keys.index(nm) for nm in names])
    Vn, Qn, orig = U.split(low.V, low.Q, lab)
    F_all = triangles(Qn, d02)
    fq = np.tile(np.arange(len(Qn)), 2)
    isl = {}
    inner = lambda nm: nm.startswith('inner')
    for i, nm in enumerate(keys):
        F = F_all[lab[fq] == i]
        vs = np.unique(F)
        isl[nm] = dict(vs=vs, split_of={int(orig[v]): int(v) for v in vs})
        if stacked[nm] is not None:
            continue
        loc = -np.ones(len(Vn), np.int64)
        loc[vs] = np.arange(len(vs))
        Fl, Pv = loc[F], Vn[vs]
        uv = U.lscm(Pv, Fl)
        best, cand, done = None, uv, 0
        for it in (0, 2, max(arap_iters // 2, 3), arap_iters):
            if it > done:
                cand, done = U.arap(Pv, Fl, cand, it - done), it
            if U.self_overlap(cand, Fl):
                continue
            fp = U.footprint(Pv, Fl, cand)
            if best is None or fp < best[0]:
                best = (fp, it, cand)
        if best is None:
            log(f'[cowboy_hat] uv island {nm}: every ARAP depth folded it, LSCM kept')
            best = (U.footprint(Pv, Fl, uv), 0, uv)
        uv = best[2]
        d1, d2 = uv[Fl[:, 1]] - uv[Fl[:, 0]], uv[Fl[:, 2]] - uv[Fl[:, 0]]
        if (d1[:, 0] * d2[:, 1] - d1[:, 1] * d2[:, 0]).sum() < 0:
            uv[:, 0] = -uv[:, 0]
        uv = HU._min_box(uv)
        a3 = 0.5 * np.linalg.norm(np.cross(Pv[Fl[:, 1]] - Pv[Fl[:, 0]], Pv[Fl[:, 2]] - Pv[Fl[:, 0]]), axis=1).sum()
        s1, s2, ok = U.stretch(Pv, Fl, uv)
        isl[nm].update(Fl=Fl, uv=uv / U.island_density(Pv, Fl, uv), area=a3, fp=best[0], arap=best[1],
                       share=INNER_SHARE if inner(nm) else 1.0, aniso=float(np.percentile((s1 / s2)[ok], 95)))
    return dict(V=Vn, Q=Qn, orig=orig, names=names, stacked=stacked, keys=keys, lab=lab, isl=isl)


def pack_search(flat, size=2048, pad=UV_PAD, turns=8, g=4, tries=24, seed=3, floor=0.50, log=print):
    """the greatest density at which the primaries pack on the sheet: the placing ORDER is searched (a greedy packer
    is as good as its order: by area, by long side, by box, then `tries` random orders, the areas jittered x
    exp(0.5 N)), each first tried just over the best fill so far (one placement says whether it is worth
    bracketing: HIGH_TO_LOW "Probe before you bracket") and bisected upward only when it fits. Returns (fill,
    [each primary's UVs 0-1], px_per_m, the order's name)"""
    isl, keys, stacked = flat['isl'], flat['keys'], flat['stacked']
    prim = [nm for nm in keys if stacked[nm] is None]
    area = sum(isl[nm]['area'] * isl[nm]['share'] ** 2 for nm in prim)
    ppm = lambda fill: np.sqrt(fill * size * size / area)
    ext = lambda nm: (isl[nm]['uv'].max(0) - isl[nm]['uv'].min(0)) * isl[nm]['share']
    a_of = np.array([isl[nm]['area'] * isl[nm]['share'] ** 2 for nm in prim])
    by = lambda key: sorted(range(len(prim)), key=key)
    orders = [('area', by(lambda i: -a_of[i])), ('long side', by(lambda i: -float(ext(prim[i]).max()))),
              ('box', by(lambda i: -float(np.prod(ext(prim[i])))))]
    rng = np.random.default_rng(seed)
    for t in range(tries):
        orders.append((f'random {t}', [int(i) for i in np.argsort(-a_of * np.exp(0.5 * rng.normal(size=len(prim))))]))
    place = lambda f, order: pack_raster([(isl[nm]['uv'] * ppm(f) * isl[nm]['share'], isl[nm]['Fl']) for nm in prim],
                                         size, pad, g=g, turns=turns, order=order)
    got, seen = None, []
    for onm, order in orders:
        if order in seen:
            continue
        seen.append(order)
        f0 = floor if got is None else got[0] + 0.004
        out = place(f0, order)
        if out is None:
            continue
        lo_f, hi_f, mine = f0, 0.95, (f0, out)
        for _ in range(7):
            f = 0.5 * (lo_f + hi_f)
            out = place(f, order)
            if out is None:
                hi_f = f
            else:
                lo_f, mine = f, (f, out)
        log(f'[cowboy_hat] uv pack, order {onm}: {mine[0] * 100:.1f} %')
        got = (mine[0], mine[1], onm, [prim[i] for i in order])
    assert got is not None, f'the islands do not pack at a {floor * 100:.0f} % fill'
    return got[0], got[1], float(ppm(got[0])), got[2], got[3]


def pack_fixed(flat, order, ppm, size=2048, pad=UV_PAD, turns=8, g=4):
    """ONE placement of the primaries in a known order (island names, a pack_search winner's) at a known density
    (px/m): the same result as the search found, in seconds. A greedy packer places an island by what stands
    already, so islands appended to a known order (the tails, last) leave the others where they were. None when
    it does not fit (the islands changed: search again)"""
    isl, keys, stacked = flat['isl'], flat['keys'], flat['stacked']
    prim = [nm for nm in keys if stacked[nm] is None]
    if sorted(order) != sorted(prim):
        return None
    area = sum(isl[nm]['area'] * isl[nm]['share'] ** 2 for nm in prim)
    out = pack_raster([(isl[nm]['uv'] * ppm * isl[nm]['share'], isl[nm]['Fl']) for nm in prim], size, pad, g=g,
                      turns=turns, order=[prim.index(nm) for nm in order])
    return None if out is None else (float(ppm * ppm * area / size / size), out, float(ppm), 'fixed', list(order))


def pack_order(flat, order, size=2048, pad=UV_PAD, turns=8, g=4, lo=0.62, hi=0.82, steps=7, log=print):
    """the recorded ORDER again on islands that CHANGED SHAPE (a trial of SPEC: the crown's wall and its cap take
    another outline, so the recorded density no longer fits): the density bisected between the fills `lo` and `hi`
    with that ONE order: 8 placements, against pack_search's 27 orders of up to 8 each (measured 11-11 on a full
    machine under memcap: the search's first order alone took 300 s and gave 72.1 %). Returns pack_fixed's tuple at
    the densest fit found, or None when the order's islands are not this set's or `lo` itself does not fit (then:
    pack_search)"""
    isl, keys, stacked = flat['isl'], flat['keys'], flat['stacked']
    prim = [nm for nm in keys if stacked[nm] is None]
    if sorted(order) != sorted(prim):
        return None
    area = sum(isl[nm]['area'] * isl[nm]['share'] ** 2 for nm in prim)
    ppm = lambda fill: float(np.sqrt(fill * size * size / area))
    got = pack_fixed(flat, order, ppm(lo), size, pad, turns, g)
    if got is None:
        return None
    for _ in range(steps):
        f = 0.5 * (lo + hi)
        out = pack_fixed(flat, order, ppm(f), size, pad, turns, g)
        if out is None:
            hi = f
        else:
            lo, got = f, out
    log(f'[cowboy_hat] uv pack: the recorded order, its density bisected: {got[0] * 100:.1f} % at {got[2]:.0f} px/m '
        f'(the recorded {UV_PPM:.0f})')
    return got


def unwrap(low, info, d02, size=2048, pad=UV_PAD, arap_iters=8, turns=8, g=4, tries=24, flat=None, packed=None,
           log=print):
    """flatten -> pack_search -> the split low with its UVs: one texel density for the set (the inside at
    INNER_SHARE); each STACKED island takes its primary's UVs through its mirrors (one mirror: its UV triangles run
    clockwise and the tangent's sign flips, bake.low_frames; two: a half turn, the sign as the primary's). Returns
    the split low (V, Q, orig), UV, per quad its island's name, the primaries' mask, px_per_m and the fill (the
    primaries' UV area: the sheet is 1). flat / packed: a flatten() / pack_search() result kept from before"""
    flat = flat or flatten(low, info, d02, arap_iters, log)
    Vn, Qn, orig, names, stacked, keys, lab, isl = (flat[k] for k in ('V', 'Q', 'orig', 'names', 'stacked', 'keys',
                                                                      'lab', 'isl'))
    prim = [nm for nm in keys if stacked[nm] is None]
    # (a hat without tails or a binding has fewer islands: the recorded order less the ones it lacks)
    order = tuple(nm for nm in UV_ORDER if nm in prim)
    if packed is None and order:
        packed = pack_fixed(flat, order, UV_PPM, size, pad, turns, g)
        log('[cowboy_hat] uv pack: ' + ('the recorded order no longer fits at its density: the same order, the '
                                        'density bisected' if packed is None else
                                        f'the recorded order at {UV_PPM:.0f} px/m'))
        if packed is None:
            packed = pack_order(flat, order, size, pad, turns, g, log=log)
    fill, out, px_per_m, onm = (packed or pack_search(flat, size, pad, turns, g, tries, log=log))[:4]
    UVn = np.zeros((len(Vn), 2))
    for nm, uv in zip(prim, out):
        UVn[isl[nm]['vs']] = uv
    mx, mz = np.asarray(info['mirror']), np.asarray(info['mirror_z'])
    carry = {'x': mx, 'z': mz, 'xz': mz[mx], 'u': np.asarray(info['under'])}
    for nm in keys:
        if stacked[nm] is None:
            continue
        tw, m = isl[stacked[nm][0]]['split_of'], carry[stacked[nm][1]]
        for v in isl[nm]['vs']:
            UVn[v] = UVn[tw[int(m[orig[v]])]]
    rep = ', '.join(f'{nm} (fp {isl[nm]["fp"]:.2f}, aniso p95 {isl[nm]["aniso"]:.2f}, ARAP {isl[nm]["arap"]})'
                    for nm in prim)
    log(f'[cowboy_hat] uv: {len(keys)} islands, {len(prim)} primary and {len(keys) - len(prim)} stacked on their '
        f'mirrors: {rep}; {px_per_m:.0f} px/m at {size} ({1000 / px_per_m:.3f} mm/texel), fill {fill * 100:.1f} %')
    return dict(V=Vn, Q=Qn, orig=orig, UV=UVn, names=names, keys=keys, stacked=stacked, lab=lab,
                quad_primary=np.array([stacked[nm] is None for nm in names]), px_per_m=px_per_m, size=size,
                fill=float(fill), pad=pad)


def low_arrays(low, info, uvs, d02):
    """the export's arrays: the designed triangles (quad_diagonals), normals smooth within each SMOOTH_GROUP of the
    welded low and split between groups, MikkT-style tangents (bake.low_frames: a stacked island's handedness is -1),
    per triangle its region and whether it is a PRIMARY (the bake and the material pass see primaries only: a stacked
    triangle shares its primary's texels), ATTR per split vertex"""
    from .. import bake
    Vn, Qn, UVn, orig = uvs['V'], uvs['Q'], uvs['UV'], uvs['orig']
    F = triangles(Qn, d02)
    fq = np.tile(np.arange(len(Qn)), 2)
    region = info['quad_region'][fq].astype(np.int32)
    grp_of = np.zeros(len(REGIONS), np.int64)
    for g, regs in enumerate(SMOOTH_GROUPS):
        grp_of[list(regs)] = g
    fn = np.cross(Vn[F[:, 1]] - Vn[F[:, 0]], Vn[F[:, 2]] - Vn[F[:, 0]])          # area-weighted
    acc = np.zeros((len(low.V), len(SMOOTH_GROUPS), 3))
    for k in range(3):
        np.add.at(acc, (orig[F[:, k]], grp_of[region]), fn)
    vg = np.zeros(len(Vn), np.int64)
    vg[F.ravel()] = np.repeat(grp_of[region], 3)
    N = _unit(acc[orig, vg])
    N, TAN = bake.low_frames(Vn, F, UVn, N)
    ATTR = np.asarray(low.attrs['attr'], np.float64)[orig]
    return dict(V=Vn, F=F, UV=UVn, N=N, TAN=TAN, region=region, primary=uvs['quad_primary'][fq], ATTR=ATTR,
                orig=orig, px_per_m=uvs['px_per_m'], size=uvs['size'], island=uvs['lab'][fq])


# --------------------------------------------------------------------------------------------------- sculpt plan
def _ribbon_frame(phi, rho, spec=SPEC):
    """along a (phi, rho) path on the brim: the upper face's points and normals, the path's unit tangents, the
    lateral unit vectors b (in the face, to the path's left seen from above) and, per unit of lateral distance, the
    (d phi, d rho) that moves along b (so a ribbon's width is laid ON the curved brim, not in a tangent plane)"""
    P, N, T, A = brim_point(phi, rho, 1.0, 0.0, spec)
    t = np.gradient(P, axis=0)
    t = _unit(t - (t * N).sum(1, keepdims=True) * N)
    b = np.cross(N, t)
    # b = a_phi * (dP / dphi) + a_rho * T in the face: the brim's own parameter lines (dP / dphi from a finite step)
    e = 1.0e-3
    Pe = brim_point(phi + e, rho, 1.0, 0.0, spec)[0]
    Pphi = (Pe - P) / e
    g11, g12, g22 = (Pphi * Pphi).sum(1), (Pphi * T).sum(1), (T * T).sum(1)
    r1, r2 = (b * Pphi).sum(1), (b * T).sum(1)
    det = g11 * g22 - g12 * g12
    return P, N, t, b, (r1 * g22 - r2 * g12) / det, (r2 * g11 - r1 * g12) / det


def knot_pitch(spec=SPEC):
    """the wound knot's cords: their spacing along the band (six cords across the knot's width less its rounded
    ends); the material pass paints the pale lines between them from the same number"""
    return (spec['knot_w'] - 0.003) / max(len(spec['band_lines']), 1)    # (a leather band has no lines: 11-11)


def tail_pitch(w, spec=SPEC):
    """a tail's cords: their spacing across its width w (six cords inside its rounded edges)"""
    return (w - 0.0016) / (len(spec['band_lines']) + 1)


def plan_hat(prog=None, spec=SPEC, rng=None, log=print):
    """the sculpt plan (top_hat.plan_hat's tier: features of ~0.5 mm and up, each stroke placed analytically):
      * the binding's ROLLED EDGE: capsules along the brim's edge (top_hat's, on this brim);
      * the WRAPPED KNOT on the band at the wearer's left: a pad of flat pills standing knot_t off the band, taller
        than the band by 1.5 mm each way, the wound ribbon's six cords upright on it.
    The knot carries RIBBON_ID (the bake hands the id per texel: the material pass paints it as the band's ribbon
    where it lies over the wall above the band). The two TAILS are not sculpted: they are the low's own strips
    (tail_strips), their cords and ribs the material pass's (a 0.35 mm cord is the texture tier's:
    ACCESSORY_REFERENCE 1.5)"""
    from ..species.octopus_sculpt import Plan
    from ..voxel import STROKE_CONE, STROKE_CYL
    rng = rng or np.random.default_rng(7)
    plan = Plan()
    d = dims(spec)
    W = spec['brim_w']
    # 1. the binding's rolled edge (a hat with a raw cut edge has none: bead_r 0)
    Pe = brim_frame(np.linspace(0.0, 2.0 * np.pi, 720, endpoint=False), [W], spec)[0][:, 0]
    per = np.linalg.norm(np.roll(Pe, -1, axis=0) - Pe, axis=1).sum()
    n = int(np.ceil(per / 0.0002))
    phi = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    A = brim_frame(phi, [W - 0.00025], spec)[0][:, 0]
    knots = rng.normal(0.0, 1.0, 40)                                # a gentle unevenness, periodic round the edge
    wob = 1.0 + 0.04 * np.interp(phi, np.linspace(0.0, 2.0 * np.pi, 41), np.append(knots, knots[0]))
    if spec['bead_r'] > 0.0:
        plan.add(STROKE_CONE, A, np.roll(A, -1, axis=0), spec['bead_r'] * wob, spec['bead_r'] * np.roll(wob, -1),
                 'add', 0.0006, 'binding roll')
    # 2. the wrapped knot
    pb = np.radians(spec['bow_phi'])
    Rb = float(np.hypot(*band_point(pb, d['y0'] + 0.5 * spec['band_h'], 0.0, spec)[0][[0, 2]]))
    hk = 0.5 * spec['knot_w'] / Rb
    ylo, yhi = d['y0'] - 0.0010, d['y0'] + spec['band_h'] + 0.0015
    ym, hh = 0.5 * (ylo + yhi), 0.5 * (yhi - ylo)
    ra = 0.0025
    gp = np.arange(pb - hk + ra / Rb, pb + hk - ra / Rb + 1e-9, 0.0008 / Rb)
    gy = np.arange(ylo + ra, yhi - ra + 1e-9, 0.0008)
    GP, GY = np.meshgrid(gp, gy, indexing='ij')
    tk = spec['knot_t'] * (1.0 - 0.30 * ((GP - pb) / hk) ** 2 - 0.12 * ((GY - ym) / hh) ** 2)
    a, _ = band_point(GP.ravel(), GY.ravel(), -0.0006, spec)
    b, _ = band_point(GP.ravel(), GY.ravel(), tk.ravel(), spec)
    plan.add(STROKE_CYL, a, b, ra, 0.0007, 'add', 0.0004, 'knot pad', mat=RIBBON_ID)
    # (11-11) a LEATHER band (the ranger's): the pad is the band's lapped end and its keeper; no ribbon cords
    nc, rc = (0 if spec.get('band_kind') == 'leather' else len(spec['band_lines']) + 1), 0.0012   # the ribbon's cords
    for i in range(nc):                                               # the wound ribbon's cords, upright: the pale
        #                                                               lines lie between them, at (j - 2) knot_pitch
        g = pb + (i - 0.5 * (nc - 1)) * knot_pitch(spec) / Rb
        yy = np.arange(ylo + 0.0012, yhi - 0.0012 + 1e-9, 0.0005)
        lift = spec['knot_t'] * (1.0 - 0.30 * ((g - pb) / hk) ** 2 - 0.12 * ((yy - ym) / hh) ** 2) \
            + spec['cord_amp'] - rc
        p, _ = band_point(np.full(len(yy), g), yy, lift, spec)
        plan.add(STROKE_CONE, p[:-1], p[1:], rc, rc, 'add', 0.0002, 'knot cord', mat=RIBBON_ID)
    log(f'[cowboy_hat] plan: ' + ', '.join(f'{o["tag"]} {len(o["A"])}' for o in plan.ops))
    return plan


# ------------------------------------------------------------------------------- curves for the photo measuring
def feature_curves(spec=SPEC, n=720, ridges=True, n_mer=1024):
    """the hat's measurable curves as closed or open polylines (the photo fit's and the overlays'): the band's lower
    and upper edges on its outer face, the brim's edge apex, the two ridges and the crease's bottom along the top"""
    d = dims(spec)
    phi = np.linspace(0.0, 2.0 * np.pi, n, endpoint=False)
    out_b = 0.5 * spec['felt_t'] + spec['band_t']
    band_lo = wall_ring(phi, d['y0'], out_b, spec)[0]
    band_hi = wall_ring(phi, d['y0'] + spec['band_h'], out_b, spec)[0]
    P, N, T = brim_frame(phi, [spec['brim_w']], spec, n_mer)
    edge = P[:, 0] + float(half_thickness(spec['brim_w'], spec)) * T[:, 0]
    out = dict(band_lo=band_lo, band_hi=band_hi, brim_edge=edge)
    if not ridges:
        return out
    # the ridges and the crease's bottom: along the top's oval at x0 = +-w(zeta) and 0
    zs = np.linspace(-0.98, 0.98, 240)
    z0 = d['zt'] + zs * d['Tz']
    w = crease_halfwidth(zs, spec)
    nn = np.where(zs > 0.0, spec['top_n'][0], spec['top_n'][1])
    half = d['Tx'] * np.maximum(1.0 - np.abs(zs) ** nn, 0.0) ** (1.0 / nn)   # the top's half-width at this station
    for nm, xs in (('ridge_L', w), ('ridge_R', -w), ('crease', np.zeros_like(w))):
        ok = np.abs(xs) <= 0.985 * half + 1e-9
        ph, th = plan_to_th(xs[ok], z0[ok], spec)
        out[nm] = crown_frame(ph, th, spec)[0]
    return out


# ------------------------------------------------------------------------------------------------- material pass
MATERIAL = dict(
    # linear albedos. [E-photo]: by eye and by patch medians on views A (tungsten light) and B (flash), neither with
    # a grey card: the hues from view B, the felt's level set between ACCESSORY_REFERENCE 5's brown (0.10-0.20 L) and
    # silverbelly (0.58): a sand felt, L 0.25
    felt=(0.300, 0.245, 0.170),
    band=(0.470, 0.270, 0.110),           # the band's gold weft (its cords)
    line=(0.700, 0.660, 0.560),           # the five pale lines: the white warp in the grooves
    binding=(0.580, 0.470, 0.350),        # the brim's binding: a pale cream ribbon (view B's edge close-up)
    leather=(0.33, 0.19, 0.095),          # the roan sweatband (top_hat's tan)
    silk=(0.62, 0.56, 0.44),              # the satin lining (top_hat's ivory)
    ink=(0.55, 0.38, 0.12),               # the lining's printed mark
    dust=(0.43, 0.37, 0.28),              # pale dust in the nap
    salt=(0.62, 0.60, 0.55),              # the sweat line's salt bloom
    soil=(0.085, 0.065, 0.045),           # hand soil at the pinch and on the brim's front
    fray=(0.80, 0.77, 0.70),              # the tails' frayed ends: the bare white warp
    # roughness: fur felt 0.80-0.90 (ACCESSORY_REFERENCE 5); the nap's streaks move it +-nap, hands polish it by up
    # to wear; grosgrain crests / valleys, leather and satin as top_hat's
    # (wear_rough: how far a hand's grease lowers the felt's roughness: top_hat's is 0.14; 0.04 here is the value the
    # look was judged at beside the photos on 11-11 (tmp/x/e_B_m6_m7opaque_nowear.png): the soil's colour carries
    # the handled patch)
    felt_rough=0.86, nap_rough=0.06, wear_rough=0.04, rib_rough=(0.50, 0.68), leather_rough=0.55, silk_rough=0.32,
    rib_pitch=0.0010,                     # the band's weft ribs [M: view B, 60 ribs beside an 18 mm band]
    bind_pitch=0.0008,                    # the binding's, finer [E: view B's edge close-up]
    rib_amp=0.00006,                      # the ribs' peak-to-valley relief [E]
    line_w=0.0009,                        # a pale line's width [M: view B's profile, 4-5 px of the band's 91]
    # top_hat's felt (tufts 2.4 / 1.2 / 0.6 mm, nap), its density CLOUD at 0.02 where the top hat has 0.05: beside the
    # photos (the engine from each photo's own camera, 11-10 22:35) the cloud's +-20 % read as blotches on a pale felt
    # (on the top hat's black they do not); fur felt at a metre is even
    # THE FELT'S BUMP: top_hat's tufts stand 50 um; on this pale felt, under a lamp from the side, that read as
    # plaster stipple on the crown's flanks (a 7 degree slope at the 2.4 mm tuft) where the photographed felt is smooth
    # (11-11, the engine from view A's camera, photo | 50 um | 18 um side by side: tmp/x/e_close_A_photo_v1_m2.png)
    felt_amp=0.000018, nap_amp=0.0000025, cloud=0.02,
    # THE FELT'S FIBRE GRAIN, in its COLOUR (11-11 02:25): with the cloud and the bump turned down the felt was a flat
    # colour at a hand's distance. MEASURED on view B at 0.24 mm a pixel (the luminance less its 6 px blur, as a share
    # of the mean): the photographed felt 5.6-6.7 %, uncorrelated beyond 2 px (0.25-0.5 mm: the fibres' own speckle
    # plus the camera's noise); the engine's 0.5-0.9 %. Two octaves of value noise at 0.45 and 1.1 mm in ln L,
    # their amplitude set so the engine's reads about half the photo's (the rest is the camera): cloth_at.
    # (0.20 with the octaves at 0.7 / 0.5 measured 1.4-1.6 % and still read smooth: the texture filter halves a
    # 2.8-texel grain)
    grain=0.40,
    # THE FUZZ MASK (masks R: the runtime's sheen and rim fuzz amount; accessories.js propMaterial makes the sheen's
    # colour from the ALBEDO: (2.5 albedo + 0.16) / 2 x 1.4 mask, at most 0.3). On the top hat's black felt a mask of
    # 0.4 is a sheen of 0.06; on this sand felt the same 0.4 is 0.25, as bright as the albedo itself. 0.12 gives this
    # felt the top hat's absolute sheen (0.07); +- fuzz_var in 3.5 mm tufts. (Judged beside the photos with the masks
    # OPAQUE, 11-11: run_material's note. Every earlier reading of this mask was through the alpha division.)
    fuzz=0.12, fuzz_var=0.04,
    # THE WEAR, each 0 (a new hat) .. 1; what a worn western hat shows (ACCESSORY_REFERENCE 5, its ref 02). HOW THESE
    # NUMBERS WERE REACHED, kept because two steps were wrong turns: (1) the first engine look (11-10 22:35) showed
    # "leopard" blotches, a brim 14 % greyer than the crown and a chalk line: fade 0.55 -> 0.35, dust 0.50 -> 0.40,
    # salt 0.45 -> 0.18, the fuzz mask evened; (2) 11-11, with the light from the photo's side: rings on the brim and
    # pale ovals at the pinch; I lowered fade and dust again (0.20, 0.22, a wide sky ramp, patchy dust) on a GUESS
    # and the rings stayed; (3) FIVE PROBES, each wear term off in turn: only the one without the HANDS lost them;
    # (4) one more, the masks' alpha set to 255: the cause was never the wear but the PARTIAL ALPHA that carried the
    # hands' wear in the masks texture (run_material's note). The blotches of (1) were the same thing. What stays
    # from (1)-(3) because it reads right beside the photos with the alpha fixed: a KEPT hat's light fade and
    # dust, and the hands' mask shaped as the fingers' grip (k_cowboy) instead of a ring round the brim
    w_fade=0.20,                          # the sun: what faces the sky bleaches (lighter, greyer); the under-brim keeps
    #                                       the dye (WORLD SPACE: the baked normal's up component)
    w_dust=0.22,                          # dust in the nap of what faces the sky, more in the hollows (the crease, the
    #                                       band's foot: the bake's AO; a little by its convexity)
    w_sweat=0.45,                         # the sweat line over the band: darker, greasier, a broken salt line at its
    #                                       upper edge and one tide line under it; the sweatband darkened in front
    w_handle=0.55,                        # hands: the pinch and the brim's front grip, soiled; the binding soiled
    #                                       there (view B)
    w_rub=0.25,                           # the nap rubbed pale on the ridges (the bake's convexity). 0.50 drew a
    #                                       chalk line along the crown's crest beside the photo (11-11, view A close)
    pinch_r=0.045,                        # the fingers' patch round each pinch dent (m)
    seed=31,
)
# ------------------------------------------------------------------------------- THE COLOURS: material variants
# Skye, 11-11: "we should have real cowboy hats black and white and grey, and brown". ONE low, ONE set of UVs, ONE
# bake (normal, AO, curvature, cavity: drivers_<NAME>.npz); a colour is a set of MATERIAL overrides run over those
# drivers (run_material: 40 s, no bake): its own felt, its own band, its own WEAR, because wear does not read the
# same on every felt: pale dust shows on black and on chocolate and is lost on white; soil and the sweat stain show
# on white and grey and are lost on black. Per colour: T_<NAME>_<colour>_{albedo,orm,masks}.png (a SKIN); the
# normal map is ONE picture for all four (the felt's relief is the felt's, not its dye's: `felt_amp` and every other
# height term stay MATERIAL's, the 18 um judged beside the photos on 11-11), so a colour changes no geometry and no
# normal: the one glb carries one mesh, one normal map and the four skins (export_glb's `skins`).
# Albedos linear. The fuzz mask follows TECHNIQUES 11 (the runtime makes the sheen from the albedo: (2.5 albedo +
# 0.16) / 2 x 1.4 x mask): each felt's mask is set for the top hat's absolute sheen of about 0.07.
# THE SECOND LOOK (11-11 06:45, the four side by side in the creatures' studio beside F.M. Light & Sons' wall of felt
# hats, tmp/x/store_colour_crops.png): the first numbers read as charcoal, off-white, off-white and taupe: on black
# and chocolate a fade of 0.30 and dust of 0.45-0.55 greyed the whole felt (the store's black hats read black, its
# browns brown), and silverbelly (0.47 / 0.44 / 0.385) read as a second white beside the white (in the store it is a
# pale beige: Skye asked for GREY, so the grey is a grey felt, the store's slate-grey hats' kind, a little lighter).
# Each colour keeps ITS OWN wear, toned so the felt keeps its colour: pale dust shows on black and on brown, soil and
# the sweat stain on white and on grey
# (06:58, one probe: the black with the runtime's sheen and rim fuzz off read 59 sRGB against 74 with them: the rest of
# its charcoal is the dielectric's own specular floor, F0 0.04 against a 0.02 albedo, under the studio's bright sky
# and AgX, which no map changes. So the black takes the darkest dye (0.012) and half the sheen; and the broken SALT
# LINE over the band printed as a white dashed "stitch" on the black and the brown: their sweat is lower)
VARIANTS = {
    'cattleman': {
        'black': dict(
            felt=(0.012, 0.0115, 0.012), band=(0.010, 0.010, 0.011), line=(0.026, 0.026, 0.028),
            dust=(0.40, 0.35, 0.27), soil=(0.060, 0.050, 0.040),
            w_fade=0.10, w_dust=0.22, w_sweat=0.10, w_handle=0.30, w_rub=0.15,
            fuzz=0.18, fuzz_var=0.05, cloud=0.04, grain=0.30),
        'white': dict(
            felt=(0.760, 0.740, 0.690), band=(0.014, 0.014, 0.015), line=(0.034, 0.034, 0.036),
            dust=(0.300, 0.255, 0.190),     # on white what gathers in the nap is SOIL: darker than the felt
            soil=(0.210, 0.160, 0.105),
            w_fade=0.05, w_dust=0.32, w_sweat=0.60, w_handle=0.75, w_rub=0.10,
            fuzz=0.05, fuzz_var=0.015, cloud=0.02, grain=0.40),
        'grey': dict(                       # a grey felt (hatters' granite / mist grey), a black band
            felt=(0.195, 0.200, 0.210), band=(0.016, 0.016, 0.017), line=(0.036, 0.036, 0.038),
            dust=(0.360, 0.320, 0.260), soil=(0.070, 0.060, 0.050),
            w_fade=0.10, w_dust=0.22, w_sweat=0.45, w_handle=0.50, w_rub=0.15,
            fuzz=0.15, fuzz_var=0.045, cloud=0.03, grain=0.36),
        'brown': dict(                      # a chestnut brown felt with a dark tonal band
            felt=(0.095, 0.052, 0.026), band=(0.040, 0.025, 0.016), line=(0.070, 0.045, 0.030),
            dust=(0.42, 0.36, 0.27), soil=(0.035, 0.022, 0.014),
            w_fade=0.10, w_dust=0.25, w_sweat=0.15, w_handle=0.35, w_rub=0.15,
            fuzz=0.25, fuzz_var=0.08, cloud=0.04, grain=0.32),
    },
}
HATS['cattleman']['material'] = VARIANTS['cattleman']['grey']     # the cattleman's maps without a colour named
# (11-11) THE PARK RANGER HAT's material: "belly" colour fur felt (NPS Order 350, 1938; photo 3 of refs/felt_hats, the
# felt hat in daylight: a pale warm grey-beige; a little darker than the silverbelly that read as a second white
# beside the white cowboy hat), the dark tooled leather band, brass eyelets; a kept uniform hat's light wear
HATS['ranger']['material'] = dict(
    felt=(0.420, 0.390, 0.330), band=(0.040, 0.027, 0.020), line=(0.06, 0.05, 0.04),
    dust=(0.36, 0.32, 0.26), soil=(0.10, 0.08, 0.06),
    brass=(0.80, 0.62, 0.32), hole=(0.012, 0.011, 0.010), brass_rough=0.30, band_rough=0.42,
    eye_r=(0.0021, 0.0034), tool_l=0.030,
    w_fade=0.10, w_dust=0.20, w_sweat=0.35, w_handle=0.40, w_rub=0.15,
    fuzz=0.08, fuzz_var=0.025, cloud=0.02, grain=0.40)

(S_TEXEL, S_WB, S_BIND_LO, S_SWEAT_H, S_Y0, S_BAND_H, S_PITCH, S_PITCH_B, S_RIB_AMP, S_FELT_AMP, S_NAP_AMP, S_CLOUD,
 S_KNOT_PITCH, S_BOW_S, S_ZT, S_FADE, S_DUST, S_SWEAT, S_HANDLE, S_RUB, S_PIN_X, S_PIN_Y, S_PIN_Z, S_PIN_R, S_LINE0,
 S_LINE_W, S_CORD_AMP, S_INNER) = (wp.constant(i) for i in (0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16,
                                                             17, 18, 19, 20, 21, 22, 23, 24, 29, 30, 31))
S_FUZZ, S_FUZZ_VAR, S_GRAIN = wp.constant(32), wp.constant(33), wp.constant(34)
# (11-11, the ranger) a LEATHER band with its tooling (1: the band and the keeper are leather), the tooling's motif
# period along the band (m), and the brass EYELETS: the hole's and the flange's radii (m), their count on the
# right side (the left is its mirror: fold) and their centres from S_EYE on (x, y, z each)
S_LEATHER_BAND, S_TOOL_L, S_EYE_R0, S_EYE_R1, S_EYE_N, S_EYE = (wp.constant(i) for i in (35, 36, 37, 38, 39, 40))
S_COUNT = 40 + 3 * 4        # (S_LINE0 .. S_LINE0 + 4 hold the five pale lines' places; up to four eyelets a side)
RIBBON_K = wp.constant(RIBBON_ID)
(C_FELT, C_BAND, C_LINE, C_BIND, C_LEATHER, C_SILK, C_INK, C_DUST, C_SALT, C_SOIL, C_FRAY, C_BRASS, C_HOLE) = (
    wp.constant(i) for i in range(13))


@wp.struct
class Cloth:
    h: float            # the texture tier's height (m)
    mat: int            # 0 felt, 1 ribbon (grosgrain: band, knot, tails, binding), 2 leather, 3 satin
    rib: float          # ribbon: 1 on a weft rib's crest, 0 in its valley; leather: its grain
    line: float         # ribbon: 1 on a pale line (the white warp in the groove between two cords)
    nap: float          # felt: the brushed nap's streak value (about -1..1)
    fuzz: float         # the runtime's fuzz / sheen amount
    cloud: float        # felt: its density cloud (ln L)
    grain: float        # felt: its fibre grain (ln L)
    zone: float         # the palette zone: 0 felt, 1/3 band and bow, 2/3 binding, 1 inside
    fray: float         # a tail's frayed end
    ink: float          # satin: the printed mark


@wp.func
def _tab(t: wp.array(dtype=wp.float32), u: float):
    n = t.shape[0]
    x = wp.clamp(u, 0.0, 1.0) * float(n - 1)
    i = wp.min(int(x), n - 2)
    f = x - float(i)
    return t[i] * (1.0 - f) + t[i + 1] * f


@wp.func
def fold(p: wp.vec3, reg: int):
    """p carried into the part of the hat whose texels it shows (island_keys: the left half shows the right's, the
    brim one quadrant's): every pattern painted from the folded point agrees across the stack's mirror seams"""
    z = p[2]
    if reg == 3 or reg == 4:
        z = wp.abs(z)
    return wp.vec3(-wp.abs(p[0]), p[1], z)


@wp.func
def cloth_at(p: wp.vec3, reg: int, at: wp.vec4, ribbon: int, S: wp.array(dtype=wp.float32),
             edge_s: wp.array(dtype=wp.float32), band_s: wp.array(dtype=wp.float32), seed: int):
    """the cloth at p on the block-out (reg: the low's region; at: its ATTR; ribbon: the bake's RIBBON id leads here:
    the knot): its class, its texture-tier height and the pattern values the paint uses"""
    out = Cloth()
    texel = S[S_TEXEL]
    if reg == 5 or reg == 6:
        texel = texel * S[S_INNER]
    q = fold(p, reg)
    phi = wp.atan2(q[0], q[2])
    r = wp.sqrt(q[0] * q[0] + q[2] * q[2])
    mat = int(0)
    zone = float(0.0)
    if S[S_LEATHER_BAND] > 0.5 and (reg == 2 or ribbon == 1):
        mat = 2                                     # (11-11) the ranger's LEATHER band and its keeper
        zone = 1.0 / 3.0
    elif reg == 2 or reg == 7 or ribbon == 1:
        mat = 1
        zone = 1.0 / 3.0
    elif (reg == 3 or reg == 4) and at[0] > S[S_BIND_LO]:
        mat = 1
        zone = 2.0 / 3.0
    elif reg == 5:
        mat = 3
        zone = 1.0
        if p[1] < S[S_SWEAT_H]:
            mat = 2
    elif reg == 6:
        mat = 3
        zone = 1.0
    h = float(0.0)
    rib = float(0.0)
    line = float(0.0)
    nap = float(0.0)
    fuzz = float(0.0)
    cloud = float(0.0)
    grain = float(0.0)
    fray = float(0.0)
    ink = float(0.0)
    if mat == 0:
        # top_hat's felt: fibre tufts in three octaves 2.4 / 1.2 / 0.6 mm, each faded out under ~3 texels; the
        # brushed nap's streaks (4 mm along the circumference, 0.6 mm across it); the density cloud; the fuzz mask
        lam = float(0.0024)
        amp = float(1.0)
        for k in range(3):
            fo = proc.smoothstep(2.5, 4.0, lam / texel)
            h = h + S[S_FELT_AMP] * amp * fo * proc.noise3(q / lam, seed + 11 + k)
            lam = lam * 0.5
            amp = amp * 0.7
        across = q[1]
        if reg == 0:
            across = r
        if reg == 3 or reg == 4:
            across = at[0] * S[S_WB]
        qq = wp.vec3(across / 0.0006, 0.11 * wp.cos(phi) / 0.004, 0.11 * wp.sin(phi) / 0.004)
        nap = proc.fbm3(qq, 2, 2.0, 0.5, seed + 23)
        h = h + S[S_NAP_AMP] * nap * proc.smoothstep(2.5, 4.0, 0.0006 / texel)
        cloud = S[S_CLOUD] * 4.0 * (0.6 * proc.fbm3(q / 0.02, 3, 2.0, 0.5, seed + 31)
                                    + 0.4 * proc.noise3(q / 0.006, seed + 37))
        # the fibre grain (MATERIAL's note): 0.45 mm (faded out where a texel is too coarse to carry it) and 1.1 mm
        grain = S[S_GRAIN] * (proc.smoothstep(1.2, 2.2, 0.00045 / texel) * proc.noise3(q / 0.00045, seed + 83)
                              + 0.4 * proc.noise3(q / 0.0011, seed + 89))
        # the FUZZ mask (the runtime's sheen and rim fuzz amount: accessories.js propMaterial). top_hat's is 0.33 +
        # 0.9 fbm, the whole 0..1 range in 3.5 mm tufts: on this pale felt the sheen then drew pale BLOTCHES (the
        # "leopard" of the first engine look; proved by one probe, sheen and fuzz off: kit.py
        # probe_cowboy_hat_A_no_sheen, the felt came out even). A fur felt's sheen is even: a narrow band about
        # MATERIAL's fuzz (its level: MATERIAL's comment)
        fuzz = wp.clamp(S[S_FUZZ] + S[S_FUZZ_VAR] * proc.fbm3(q / 0.0035, 3, 2.0, 0.5, seed + 41), 0.0, 1.0)
    elif mat == 1:
        x = float(0.0)                              # the weft ribs' coordinate, in pitches along the ribbon
        pitch = S[S_PITCH]
        cord = float(0.0)                           # a tail's cords: the relief its flat strip lacks
        if reg == 7:
            # a tail: at[2] its distance from the frayed end (m), at[3] the place across it in cord pitches (the
            # pale lines at 0, +-1, +-2, a cord's crest between each pair)
            x = at[2] / pitch
            c = 0.5 + 0.5 * wp.cos(6.283185307 * at[3])
            inside = 1.0 - proc.smoothstep(2.95, 3.05, wp.abs(at[3]))
            line = proc.smoothstep(0.55, 0.85, c) * (1.0 - proc.smoothstep(2.4, 2.6, wp.abs(at[3])))
            cord = S[S_CORD_AMP] * wp.pow(wp.max(1.0 - c, 0.0), 0.6) * inside
            fray = 1.0 - proc.smoothstep(0.0012, 0.0045, at[2])
        elif zone > 0.5:
            pitch = S[S_PITCH_B]                    # the binding: its ribs cross the edge
            x = _tab(edge_s, (phi + 3.141592654) / 6.283185307) / pitch
        elif ribbon == 1:
            # the wound knot: the ribbon runs upright, its lines between the knot's six cords
            x = p[1] / pitch
            s = (_tab(band_s, (wp.atan2(p[0], p[2]) + 3.141592654) / 6.283185307) - S[S_BOW_S]) / S[S_KNOT_PITCH]
            c = 0.5 + 0.5 * wp.cos(6.283185307 * s)
            line = proc.smoothstep(0.55, 0.85, c) * (1.0 - proc.smoothstep(2.4, 2.6, wp.abs(s)))
        else:
            # the band: ribs along it, the five pale lines at their measured heights
            x = _tab(band_s, (phi + 3.141592654) / 6.283185307) / pitch
            v = (p[1] - S[S_Y0]) / S[S_BAND_H]
            for k in range(5):
                line = wp.max(line, 1.0 - proc.smoothstep(0.5 * S[S_LINE_W], S[S_LINE_W], wp.abs(v - S[S_LINE0 + k])))
        rib = wp.pow(0.5 + 0.5 * wp.cos(6.283185307 * x), 0.6)
        h = S[S_RIB_AMP] * (rib - 0.6) * proc.smoothstep(2.5, 4.0, pitch / texel) + cord
        fuzz = 0.15
    elif mat == 2 and zone > 0.1 and zone < 0.5:
        # (11-11) THE RANGER'S TOOLED LEATHER HATBAND (the NPS band: photos 1-3 of refs/felt_hats: a dark leather
        # band tooled with sequoia cones and leaves between two border lines). At the texture tier: the two border
        # grooves, a cone every S_TOOL_L along the band (an oval outline with its scales cross-hatched inside) and a
        # vine winding between the cones; the grooves 0.18 mm deep, ~0.5 mm wide (3 texels); the leather's grain
        cl = proc.cellular3(q / 0.0009, 0.9, seed + 51)
        g = proc.smoothstep(0.0, 0.18, cl.edge)
        hb = S[S_BAND_H]
        v = wp.clamp((p[1] - S[S_Y0]) / hb, 0.0, 1.0)
        s = _tab(band_s, (phi + 3.141592654) / 6.283185307)
        if ribbon == 1:
            v = 0.5                                 # the keeper: plain leather, its own grain
        L = S[S_TOOL_L]
        u = s / L
        fu = (u - wp.floor(u) - 0.5) * L            # (m) from the nearest cone's centre along the band
        dv = (v - 0.5) * hb                         # (m) from the band's middle line
        gw = 0.00026                                # a groove's half-width
        t = float(0.0)
        t = wp.max(t, 1.0 - proc.smoothstep(0.5 * gw, gw, wp.abs((v - 0.13) * hb)))
        t = wp.max(t, 1.0 - proc.smoothstep(0.5 * gw, gw, wp.abs((v - 0.87) * hb)))
        e = wp.sqrt((fu / (0.17 * L)) * (fu / (0.17 * L)) + (dv / (0.27 * hb)) * (dv / (0.27 * hb)))
        t = wp.max(t, 1.0 - proc.smoothstep(0.5 * gw, gw, wp.abs(e - 1.0) * 0.17 * L))
        if e < 0.92:                                # the cone's scales: two diagonal families of grooves
            a1 = (fu + dv) / 0.0022
            a2 = (fu - dv) / 0.0022
            d1 = wp.abs(a1 - wp.floor(a1 + 0.5)) * 0.0022
            d2 = wp.abs(a2 - wp.floor(a2 + 0.5)) * 0.0022
            t = wp.max(t, 0.8 * (1.0 - proc.smoothstep(0.4 * gw, 0.8 * gw, wp.min(d1, d2))))
        vine = 0.5 + 0.26 * wp.sin(6.283185307 * (u + 0.5))
        if e > 1.25 and v > 0.2 and v < 0.8:
            t = wp.max(t, 1.0 - proc.smoothstep(0.5 * gw, gw, wp.abs(v - vine) * hb))
        if ribbon == 1:
            t = 0.0
        h = 0.00002 * (g - 0.5) - 0.00018 * t
        rib = g
        line = t
        fuzz = 0.0
    elif mat == 2:
        cl = proc.cellular3(q / 0.0011, 0.9, seed + 51)
        g = proc.smoothstep(0.0, 0.18, cl.edge)
        h = 0.00002 * (g - 0.5) * proc.smoothstep(2.5, 4.0, 0.0011 / texel)
        # the stitch line 4 mm above the opening's edge, 3 mm stitches
        st = r * phi / 0.003
        st = st - wp.floor(st)
        sl = (1.0 - proc.smoothstep(0.00025, 0.0004, wp.abs(p[1] - 0.004))) * proc.smoothstep(0.15, 0.25, st) * (
            1.0 - proc.smoothstep(0.75, 0.85, st))
        h = h - 0.00005 * sl
        rib = g
        fuzz = 0.05
    else:
        if reg == 6:
            dz = q[2] - S[S_ZT]
            ink = 1.0 - proc.smoothstep(0.00045, 0.00075, wp.abs(wp.sqrt(q[0] * q[0] + dz * dz) - 0.031))
    if mat == 0 and reg == 1 and S[S_EYE_N] > 0.5:
        # (11-11) THE RANGER'S BRASS EYELETS (NPS Order 350, 1938: three ventilator holes a side), at the texture tier:
        # 4 the grommet's rolled flange (metal: "Metal is metal"), 5 the hole through the felt
        for k in range(int(S[S_EYE_N])):
            ec = wp.vec3(S[S_EYE + 3 * k], S[S_EYE + 3 * k + 1], S[S_EYE + 3 * k + 2])
            dd = wp.length(q - ec)
            if dd < S[S_EYE_R1]:
                fuzz = 0.0
                if dd < S[S_EYE_R0]:
                    mat = 5
                    h = -0.0008
                else:
                    mat = 4
                    h = 0.00035 * wp.sin(3.141592654 * (dd - S[S_EYE_R0]) / (S[S_EYE_R1] - S[S_EYE_R0]))
    out.h = h
    out.mat = mat
    out.rib = rib
    out.line = line
    out.nap = nap
    out.fuzz = fuzz
    out.cloud = cloud
    out.grain = grain
    out.zone = zone
    out.fray = fray
    out.ink = ink
    return out


@wp.kernel
def k_cowboy(uv_mesh: wp.uint64, size: int, ss: int, lpos: wp.array(dtype=wp.vec3), lnrm: wp.array(dtype=wp.vec3),
             ltan: wp.array(dtype=wp.vec4), lattr: wp.array(dtype=wp.vec4), lreg: wp.array(dtype=wp.int32),
             d_nrm: wp.array(dtype=wp.vec4), d_ao: wp.array(dtype=wp.float32), d_base: wp.array(dtype=wp.vec4),
             d_aol: wp.array(dtype=wp.float32), d_convm: wp.array(dtype=wp.float32),
             d_mat: wp.array(dtype=wp.int32), edge_s: wp.array(dtype=wp.float32),
             band_s: wp.array(dtype=wp.float32), C: wp.array(dtype=wp.vec3), R: wp.array(dtype=wp.float32),
             S: wp.array(dtype=wp.float32), seed: int, o_alb: wp.array(dtype=wp.vec3),
             o_nrm: wp.array(dtype=wp.vec3), o_orm: wp.array(dtype=wp.vec3), o_mask: wp.array(dtype=wp.vec4),
             o_wear: wp.array(dtype=wp.vec4), o_hit: wp.array(dtype=wp.int32)):
    tid = wp.tid()
    x = tid % size
    y = tid // size
    dn = d_nrm[tid]
    if dn[3] <= 0.0:
        return
    tn_b = wp.normalize(wp.vec3(dn[0], dn[1], dn[2]))
    base = d_base[tid]
    # the bake's two leading material ids here: the sculpt's ribbon (the knot)
    code = d_mat[tid]
    w0 = float((code >> 16) & 255) / 255.0
    rw = float(0.0)
    if (code & 255) == RIBBON_K:
        rw = rw + w0
    if ((code >> 8) & 255) == RIBBON_K:
        rw = rw + 1.0 - w0
    inv = 1.0 / float(ss)
    dlt = 0.5 * inv
    acc_a = wp.vec3(0.0)
    acc_n = wp.vec3(0.0)
    acc_r = float(0.0)
    acc_m = wp.vec4(0.0)
    acc_w = wp.vec4(0.0)
    acc_metal = float(0.0)
    hits = int(0)
    hb = float(0.0)
    have_hb = int(0)
    aol = d_aol[tid]
    convm = d_convm[tid]
    for i in range(ss):
        for j in range(ss):
            fx = float(x) + (float(i) + 0.5) * inv
            fy = float(y) + (float(j) + 0.5) * inv
            lo = M.low_at(uv_mesh, fx, fy, lpos, lnrm, ltan, lattr)
            if lo.ok == 0:
                continue
            if have_hb == 0:
                if base[3] > 0.5:
                    hb = wp.dot(wp.vec3(base[0], base[1], base[2]) - lo.p, lo.n)
                have_hb = 1
            lx = M.low_at(uv_mesh, fx + dlt, fy, lpos, lnrm, ltan, lattr)
            if lx.ok == 0:
                lx = M.low_at(uv_mesh, fx - dlt, fy, lpos, lnrm, ltan, lattr)
            ly = M.low_at(uv_mesh, fx, fy + dlt, lpos, lnrm, ltan, lattr)
            if ly.ok == 0:
                ly = M.low_at(uv_mesh, fx, fy - dlt, lpos, lnrm, ltan, lattr)
            reg = lreg[lo.face]
            ribbon = int(0)
            if rw > 0.5 and (reg == 1 or reg == 2):
                ribbon = 1
            pb0 = lo.p + lo.n * hb
            cl = cloth_at(pb0, reg, lo.attr, ribbon, S, edge_s, band_s, seed)
            g = wp.vec3(0.0)
            if lx.ok == 1 and ly.ok == 1:
                pbx = lx.p + lx.n * hb
                pby = ly.p + ly.n * hb
                hx = cloth_at(pbx, reg, lx.attr, ribbon, S, edge_s, band_s, seed).h
                hy = cloth_at(pby, reg, ly.attr, ribbon, S, edge_s, band_s, seed).h
                g = M.surface_grad(pb0, pbx, pby, cl.h, hx, hy)
            nw = M.to_world(lo, tn_b)
            g = g - nw * wp.dot(g, nw)
            acc_n = acc_n + M.to_tangent(lo, wp.normalize(nw - g))
            q = fold(pb0, reg)
            phi = wp.atan2(q[0], q[2])
            col = wp.vec3(0.0)
            rough = float(0.5)
            metal = float(0.0)
            fz = cl.fuzz
            w_fade = float(0.0)
            w_dust = float(0.0)
            w_sweat = float(0.0)
            w_hand = float(0.0)
            w_rub = float(0.0)
            # WORLD SPACE: how far this texel faces the sky (the prop's +Y is the seat's axis: up when worn). A WIDE
            # ramp: the first one (0.15 .. 0.85) turned the brim's own dip and curl (normals 34 and 30 degrees off
            # the vertical) into concentric pale RINGS on its upper face, plain beside the photo once the sheen no
            # longer veiled them (11-11: tmp/x/e_A_photo_m3_nowear.png); the sky lights a leaning face too
            sky = proc.smoothstep(-0.30, 1.0, nw[1])
            # hands on the brim: the fingers' GRIP at its front edge (and, by the quadrants' stack, its back), above
            # and under: a patch a hand wide (within ~30 degrees of the front, the outer third), its outline eaten by
            # a 14 mm mottle. THE FIRST MASK (the outer 45 % of the brim x cos^2 phi x a 0.6-1.0 mottle) was a clean
            # RING round the whole brim, and with the polish it carried it read PALER than the felt beside it: found
            # by five one-variable probes, each wear term off in turn (11-11: tmp/x/e_A_wear_probes.png; only the
            # probe without the hands lost the ring)
            hbrim = float(0.0)
            if reg == 3 or reg == 4:
                cf = wp.max(wp.cos(phi), 0.0)
                hbrim = proc.smoothstep(0.62, 0.98, lo.attr[0]) * proc.smoothstep(0.86, 0.985, cf) * proc.smoothstep(
                    -0.25, 0.35, proc.fbm3(q / 0.014, 3, 2.0, 0.5, seed + 43))
            if cl.mat == 0:
                # the felt: its density cloud and the local AO in ln L (top_hat's)
                col = C[C_FELT] * wp.exp(cl.cloud + cl.grain + 0.8 * aol + 0.04 * convm)
                rough = R[0] - R[1] * proc.smoothstep(-0.1, 0.5, cl.nap) + 0.5 * R[1] * proc.smoothstep(0.1, -0.5,
                                                                                                   cl.nap)
                hpin = float(0.0)
                w_salt = float(0.0)
                if reg == 0 or reg == 1:
                    dp = wp.length(q - wp.vec3(S[S_PIN_X], S[S_PIN_Y], S[S_PIN_Z]))
                    # (the fingers' patch at each pinch dent, its outline eaten by a 12 mm mottle: the first one, a
                    # round soft disc with a 0.65-1.0 mottle, read as a pale oval drawn on the crown)
                    hpin = (1.0 - proc.smoothstep(0.25 * S[S_PIN_R], S[S_PIN_R], dp)) * proc.smoothstep(
                        -0.30, 0.30, proc.fbm3(q / 0.012, 3, 2.0, 0.5, seed + 47))
                if reg == 1:
                    # the sweat line: its height over the band's top edge, taller in front, its edge wandering
                    hs = pb0[1] - (S[S_Y0] + S[S_BAND_H])
                    front = 0.5 + 0.5 * wp.cos(phi)
                    e = 0.010 + 0.008 * front + 0.005 * proc.fbm3(q / 0.035, 2, 2.0, 0.5, seed + 53)
                    amt = S[S_SWEAT] * (0.45 + 0.55 * front)
                    w_sweat = amt * (1.0 - proc.smoothstep(e - 0.007, e, hs))
                    brk = proc.smoothstep(-0.25, 0.25, proc.noise3(q / 0.005, seed + 59))
                    d1 = (hs - e) / 0.0008
                    d2 = (hs - 0.62 * e) / 0.0006
                    w_salt = amt * (wp.exp(-d1 * d1) * brk + 0.35 * wp.exp(-d2 * d2) * (1.0 - brk))
                w_hand = S[S_HANDLE] * wp.max(hpin, hbrim)
                if reg != 4:
                    w_fade = S[S_FADE] * sky * (0.75 + 0.25 * proc.fbm3(q / 0.05, 2, 2.0, 0.5, seed + 61))
                # (the dust lies in PATCHES, 3-4 cm: with the hollows' share at 0.45 of the broad convexity and a
                # 12 mm mottle it followed the brim's valley as one even ring, a target drawn on the brim)
                hollow = wp.clamp(0.35 + 0.20 * proc.smoothstep(0.2, -1.2, convm)
                                  + 0.45 * proc.smoothstep(0.0, -0.10, aol), 0.0, 1.0)
                w_dust = S[S_DUST] * sky * hollow * (0.40 + 0.60 * proc.smoothstep(
                    -0.25, 0.45, proc.fbm3(q / 0.035, 4, 2.0, 0.5, seed + 67)))
                w_rub = S[S_RUB] * proc.smoothstep(0.8, 2.2, convm)
                # in the order they happen: the sun bleaches the dye; sweat and hands stain; the ridges rub pale;
                # the dust lies on top
                col = M.lsh(col, 1.0 + 0.16 * w_fade, 1.0 - 0.25 * w_fade)
                col = M.lsh(col, 1.0 - 0.30 * w_sweat, 1.0 + 0.20 * w_sweat)
                col = M.mix3(col, C[C_SALT], 0.18 * w_salt)
                col = M.mix3(col, C[C_SOIL], 0.30 * w_hand)
                col = col * (1.0 + 0.10 * w_rub)
                col = M.mix3(col, C[C_DUST], 0.30 * w_dust)
                rough = rough - R[2] * w_hand - 0.10 * w_sweat - 0.05 * w_rub + 0.04 * w_dust
                fz = fz * (1.0 - 0.6 * w_hand) * (1.0 - 0.5 * w_sweat) * (1.0 - 0.4 * w_rub)
                w_sweat = w_sweat + w_salt
            elif cl.mat == 1:
                cb = C[C_BAND]
                if cl.zone > 0.5:
                    cb = C[C_BIND]
                col = cb * (0.78 + 0.22 * cl.rib)
                # a pale line shows the white warp between the weft's ribs: strongest in their valleys
                col = M.mix3(col, C[C_LINE], cl.line * (0.5 + 0.5 * (1.0 - cl.rib)))
                fr = cl.fray * (0.6 + 0.4 * proc.noise3(wp.vec3(lo.attr[3] * 6.0, lo.attr[2] / 0.004, 0.0), seed + 71))
                col = M.mix3(col, C[C_FRAY], wp.clamp(fr, 0.0, 1.0))
                col = col * wp.exp(0.6 * aol)
                rough = R[4] + (R[3] - R[4]) * cl.rib
                w_hand = S[S_HANDLE] * hbrim                 # the binding soiled where the brim is handled
                w_dust = 0.6 * S[S_DUST] * sky * proc.smoothstep(0.0, -0.10, aol)   # dust at the band's foot
                w_fade = 0.5 * S[S_FADE] * sky
                col = M.lsh(col, 1.0 + 0.08 * w_fade, 1.0 - 0.15 * w_fade)
                col = M.mix3(col, C[C_SOIL], 0.45 * w_hand)
                col = M.mix3(col, C[C_DUST], 0.30 * w_dust)
            elif cl.mat == 4:
                # (11-11) a brass eyelet's flange: metal (metallic 1; Metal is metal), its rim polished, a little
                # tarnish in its hollow (the bake's AO)
                col = C[C_BRASS] * wp.exp(0.25 * aol)
                rough = R[7] + 0.10 * proc.smoothstep(0.0, -0.10, aol)
                metal = 1.0
            elif cl.mat == 5:
                col = C[C_HOLE]                              # the hole through the felt: the dark inside
                rough = 0.9
            elif cl.mat == 2 and cl.zone > 0.1 and cl.zone < 0.5:
                # (11-11) the ranger's tooled leather band: the dye pools darker in the tooling's grooves; the flat
                # leather between them polished; dust in the grooves on what faces the sky
                col = C[C_BAND] * (0.86 + 0.14 * cl.rib) * (1.0 - 0.42 * cl.line) * wp.exp(0.6 * aol)
                rough = R[8] + 0.18 * cl.line + 0.06 * (cl.rib - 0.5)
                w_dust = 0.5 * S[S_DUST] * sky * cl.line
                w_fade = 0.4 * S[S_FADE] * sky
                col = M.lsh(col, 1.0 + 0.10 * w_fade, 1.0 - 0.15 * w_fade)
                col = M.mix3(col, C[C_DUST], 0.35 * w_dust)
            elif cl.mat == 2:
                # the sweatband: darkened and polished by the forehead
                front = 0.5 + 0.5 * wp.cos(phi)
                w_sweat = S[S_SWEAT] * (0.35 + 0.65 * front) * (0.7 + 0.3 * proc.fbm3(q / 0.015, 2, 2.0, 0.5,
                                                                                      seed + 73))
                col = C[C_LEATHER] * (0.90 + 0.10 * cl.rib) * wp.exp(1.0 * aol)
                col = M.lsh(col, 1.0 - 0.35 * w_sweat, 1.0 + 0.10 * w_sweat)
                rough = R[5] + 0.06 * (cl.rib - 0.5) - 0.10 * w_sweat
            else:
                col = M.mix3(C[C_SILK], C[C_INK], cl.ink) * wp.exp(0.5 * aol)
                rough = R[6] + (0.45 - R[6]) * cl.ink
            acc_a = acc_a + col
            acc_r = acc_r + wp.clamp(rough, 0.04, 1.0)
            acc_metal = acc_metal + metal
            # (the masks' G is the material id / 3 for the runtime's sheen: the eyelets count as felt there, their
            # fuzz is 0)
            acc_m = acc_m + wp.vec4(fz, float(wp.min(cl.mat, 3)) / 3.0, cl.zone, w_hand)
            acc_w = acc_w + wp.vec4(w_fade, w_dust, w_sweat, w_hand + w_rub)
            hits = hits + 1
    if hits == 0:
        return
    fh = float(hits)
    # Toksvig (craft guide 00.48, 11.44): the averaged normal's lost length widens the highlight
    ln = wp.length(acc_n) / fh
    var = wp.clamp((1.0 - ln) / wp.max(ln, 1.0e-4), 0.0, 1.0)
    rr = acc_r / fh
    a = rr * rr
    rr = wp.sqrt(wp.sqrt(a * a + var))
    o_alb[tid] = acc_a / fh
    o_nrm[tid] = wp.normalize(acc_n)
    o_orm[tid] = wp.vec3(d_ao[tid], wp.clamp(rr, 0.0, 1.0), acc_metal / fh)
    o_mask[tid] = acc_m / fh
    o_wear[tid] = acc_w / fh
    o_hit[tid] = 1


def ring_table(P):
    """the arc length along a closed ring sampled at phi = -pi .. pi (an odd count: the middle sample is the front),
    measured FROM THE FRONT: odd in phi, so a pattern even in it is its own mirror at the front and at the back
    (the UV stack's mirror seams)"""
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    return (s - s[len(s) // 2]).astype(np.float32)


def pinch_centre(spec=SPEC):
    """where the fingers grip: the deepest point of the RIGHT side's pinch dent (x < 0) on the felt's outer face. (11-11)
    The campaign hat is lifted by its peak: the FRONT dent's middle, high on the face"""
    if spec.get('crown_kind') == 'montana':
        P, N = crown_frame(np.array([0.0]), np.array([float(_th_of_hh(0.80, spec))]), spec)
        return P[0] + 0.5 * spec['felt_t'] * N[0]
    d = dims(spec)
    ph, th = np.meshgrid(np.linspace(-np.pi, 0.0, 181), np.linspace(0.05, 0.5 * np.pi - 0.05, 121), indexing='ij')
    x0, z0, hh, zeta = crown_plan(ph, th, spec)
    half = d['Bx'] * (1.0 - hh) + d['Tx'] * hh
    dent = (_smoothstep(spec['pinch_side'][0], spec['pinch_side'][1], np.abs(x0) / half)
            * dent_along(zeta, spec)
            * _bump((hh - spec['pinch_y'][0]) / spec['pinch_y'][1]))
    i = np.unravel_index(int(np.argmax(dent)), dent.shape)
    P, N = crown_frame(ph[i], th[i], spec)
    return P + 0.5 * spec['felt_t'] * N


def material_tables(texel, spec=SPEC, recipe=MATERIAL):
    """the kernel's tables: S (its scalars), C (the colours), R (the roughnesses), the binding's and the band's arc
    lengths from the front"""
    d = dims(spec)
    W = spec['brim_w']
    phi = np.linspace(-np.pi, np.pi, 1025)
    edge_s = ring_table(brim_frame(phi, [W], spec)[0][:, 0])
    band_s = ring_table(band_point(phi, d['y0'] + 0.5 * spec['band_h'], 0.0, spec)[0])
    S = np.zeros(S_COUNT, np.float32)
    pin = pinch_centre(spec)
    for k, v in ((S_TEXEL, texel), (S_WB, W), (S_BIND_LO, 1.0 - spec['bind_w'] / W), (S_SWEAT_H, spec['sweat_h']),
                 (S_Y0, d['y0']), (S_BAND_H, spec['band_h']), (S_PITCH, recipe['rib_pitch']),
                 (S_PITCH_B, recipe['bind_pitch']), (S_RIB_AMP, recipe['rib_amp']), (S_FELT_AMP, recipe['felt_amp']),
                 (S_NAP_AMP, recipe['nap_amp']), (S_CLOUD, recipe['cloud']), (S_KNOT_PITCH, knot_pitch(spec)),
                 (S_BOW_S, float(np.interp(np.radians(spec['bow_phi']), phi, band_s))), (S_ZT, d['zt']),
                 (S_FADE, recipe['w_fade']), (S_DUST, recipe['w_dust']), (S_SWEAT, recipe['w_sweat']),
                 (S_HANDLE, recipe['w_handle']), (S_RUB, recipe['w_rub']), (S_PIN_X, pin[0]), (S_PIN_Y, pin[1]),
                 (S_PIN_Z, pin[2]), (S_PIN_R, recipe['pinch_r']),
                 (S_LINE_W, 0.5 * recipe['line_w'] / spec['band_h']), (S_CORD_AMP, spec['cord_amp']),
                 (S_INNER, 1.0 / INNER_SHARE), (S_FUZZ, recipe['fuzz']), (S_FUZZ_VAR, recipe['fuzz_var']),
                 (S_GRAIN, recipe['grain'])):
        S[int(k)] = v
    S[int(S_LINE0):int(S_LINE0) + len(spec['band_lines'])] = spec['band_lines']
    # (11-11, the ranger) a leather band and its tooling's motif period; the brass eyelets of the RIGHT side (x < 0:
    # the kernel folds the left onto it)
    S[int(S_LEATHER_BAND)] = 1.0 if spec.get('band_kind') == 'leather' else 0.0
    S[int(S_TOOL_L)] = recipe.get('tool_l', 0.030)
    E = eyelet_centres(spec)
    S[int(S_EYE_R0)], S[int(S_EYE_R1)] = recipe.get('eye_r', (0.0021, 0.0034))
    S[int(S_EYE_N)] = len(E)
    for k, e in enumerate(E[:4]):
        S[int(S_EYE) + 3 * k:int(S_EYE) + 3 * k + 3] = e
    C = np.array([recipe[k] for k in ('felt', 'band', 'line', 'binding', 'leather', 'silk', 'ink', 'dust', 'salt',
                                      'soil', 'fray')]
                 + [recipe.get('brass', (0.80, 0.62, 0.32)), recipe.get('hole', (0.012, 0.011, 0.010))], np.float32)
    R = np.array([recipe['felt_rough'], recipe['nap_rough'], recipe['wear_rough'], recipe['rib_rough'][0],
                  recipe['rib_rough'][1], recipe['leather_rough'], recipe['silk_rough'],
                  recipe.get('brass_rough', 0.30), recipe.get('band_rough', 0.45)], np.float32)
    return S, C, R, edge_s, band_s


def eyelet_centres(spec=SPEC):
    """(11-11) the ranger's brass EYELETS on the RIGHT side (x < 0), on the felt's outer face: NPS Office Order 350
    (1938), "three ventilator holes on each side", an equilateral triangle, legs 1 in, its bottom leg 1 1/2 in over
    the brim (`eyelets` = dict(n, leg, low, phi)): the two lower ones leg / 2 each way along the wall from the side's
    middle, the third leg x sqrt(3) / 2 over them. [] for a hat without them"""
    ey = spec.get('eyelets')
    if not ey:
        return []
    d = dims(spec)
    y_b = d['y0'] + ey['low']
    ph_c = -np.radians(ey['phi'])                      # the wearer's RIGHT side
    out = []
    for dy, ds in ((0.0, -0.5 * ey['leg']), (0.0, 0.5 * ey['leg']), (0.5 * np.sqrt(3.0) * ey['leg'], 0.0)):
        y = y_b + dy
        r = float(np.hypot(*crown_point(ph_c, th_at_height(np.array([ph_c]), y, spec), spec)[0][[0, 2]]))
        ph = ph_c + ds / r
        th = th_at_height(np.array([ph]), y, spec)
        P, N = crown_frame(np.array([ph]), th, spec)
        out.append((P[0] + 0.5 * spec['felt_t'] * N[0]).tolist())
    return out[:ey.get('n', 3)]


def tail_drivers(res, L, size):
    """the bake's drivers on the TAILS' texels, set by hand: the tails are not in the high (plan_hat), so the bake
    leaves them out; a flat tangent normal, open AO, no relief, no base point (the material pass adds the cords and
    the ribs as its own height). In place; returns the count of texels set"""
    from PIL import Image, ImageDraw
    sel = L['primary'] & (L['region'] == REGIONS.index('tails'))
    im = Image.new('L', (size, size), 0)
    dr = ImageDraw.Draw(im)
    T = np.column_stack([L['UV'][:, 0], 1.0 - L['UV'][:, 1]]) * size          # image order: row 0 is v = 1
    for f in L['F'][sel]:
        dr.polygon([(float(T[v, 0]), float(T[v, 1])) for v in f], fill=1, outline=1)
    m = np.asarray(im, bool) & ~(res['normal'][..., 3] > 0)
    res['normal'][m] = (0.0, 0.0, 1.0, 1.0)
    for k, v in (('ao', 0.92), ('cavity', 1.0), ('curvature', 0.0), ('height', 0.0), ('thickness', 0.0)):
        if k in res:
            res[k][m] = v
    res['base'][m] = 0.0
    res['mat'][m] = 0
    return int(m.sum())


def run_material(low, drivers, size, texel, spec=SPEC, ss=2, recipe=MATERIAL, log=print):
    """the material pass over the hat's texture set, on the PRIMARY triangles (a stacked island shows its primary's
    texels). low: low_arrays(); drivers: the bake's result with tail_drivers applied (image order). Returns
    image-order uint8 maps: albedo (sRGB), normal (GL), orm (AO, roughness, metalness 0), masks (R fuzz / sheen, G
    material id / 3, B palette zone: RGB, NO ALPHA), wear (R sun fade, G dust, B sweat and salt, A hands and
    rubbed ridges: for the eye, not shipped), and palette_base (the zones' median linear albedo, for the runtime's
    recolour).
    THE MASKS SHIP WITHOUT AN ALPHA CHANNEL (11-11). top_hat's layout keeps the handling wear in A; the engine's image
    decode (Deno's createImageBitmap under three's loader) hands the GPU colour x 255 / alpha wherever 0 < alpha <
    255 (stag_beetle_skin.py's B8 note; the beetle rounds' finding), so wherever a hand had touched this hat its
    fuzz channel arrived divided by a small number, clipped to 1, and the runtime's sheen stood at its ceiling there:
    the pale "leopard" blotches of the first engine look, the pale ring on the brim, the pale ovals at the pinch
    (each drawn exactly by the handling mask). ONE PROBE proved it: the same maps with the masks' alpha set to 255
    (accessories_b5/cowboy_hat/tmp/x/e_B_m6_m7opaque_nowear.png): the pale patches turned into the soil they are.
    The runtime's prop material never reads masks.a"""
    import time

    from .. import calib
    from ..bake import dilate_all
    t0 = time.time()
    pr = np.asarray(low['primary'], bool)
    F = low['F'][pr]
    uvm = M.uv_bvh(F, low['UV'], size)
    lpos, lnrm, ltan, lattr = M.corner_arrays(low['V'], F, low['N'], low['TAN'], low['ATTR'])
    keep = {k: drivers[k] for k in ('normal', 'ao', 'curvature', 'base', 'mat')}
    D = M.driver_arrays({**keep, **calib.relief_drivers(keep, 1.0 / texel)})
    S, C, R, edge_s, band_s = material_tables(texel, spec, recipe)
    n = size * size
    o_alb = wp.zeros(n, dtype=wp.vec3)
    o_nrm = wp.zeros(n, dtype=wp.vec3)
    o_orm = wp.zeros(n, dtype=wp.vec3)
    o_mask = wp.zeros(n, dtype=wp.vec4)
    o_wear = wp.zeros(n, dtype=wp.vec4)
    o_hit = wp.zeros(n, dtype=wp.int32)
    wp.launch(k_cowboy, dim=n, inputs=[uvm.id, size, ss, lpos, lnrm, ltan, lattr,
                                       wp.array(np.asarray(low['region'], np.int32)[pr], dtype=wp.int32),
                                       D['normal'], D['ao'], D['base'], D['ao_local'], D['conv_mid'], D['mat'],
                                       wp.array(edge_s, dtype=wp.float32), wp.array(band_s, dtype=wp.float32),
                                       wp.array(C, dtype=wp.vec3), wp.array(R, dtype=wp.float32),
                                       wp.array(S, dtype=wp.float32), int(recipe['seed']), o_alb, o_nrm, o_orm,
                                       o_mask, o_wear, o_hit])
    wp.synchronize()
    img = lambda a, k: np.asarray(a.numpy()).reshape(size, size, k)[::-1]
    alb, nrm, orm, msk, wear = img(o_alb, 3), img(o_nrm, 3), img(o_orm, 3), img(o_mask, 4), img(o_wear, 4)
    cov = np.asarray(o_hit.numpy()).reshape(size, size)[::-1] > 0
    zone = np.rint(msk[..., 2] * 3.0).astype(int)
    pal = {}
    for zi, nm in enumerate(('felt', 'band', 'binding', 'inside')):
        sel = cov & (zone == zi)
        if sel.sum() > 16:
            pal[nm] = [float(x) for x in np.median(alb[sel], axis=0)]
    dil, grown = dilate_all(dict(normal=np.concatenate([nrm, cov[..., None].astype(np.float32)], -1), alb=alb,
                                 orm=orm, msk=msk, wear=wear), 16)
    alb_s = M.srgb_oetf(np.where(grown[..., None], dil['alb'], 0.05))
    nrm_t = np.where(grown[..., None], dil['normal'][..., :3], [0.0, 0.0, 1.0])
    u8 = lambda a: np.clip(a * 255 + 0.5, 0, 255).astype(np.uint8)
    out = dict(albedo=u8(alb_s), normal=u8(nrm_t * 0.5 + 0.5),
               orm=u8(np.where(grown[..., None], dil['orm'], [1.0, 0.8, 0.0])),
               masks=u8(np.where(grown[..., None], dil['msk'][..., :3], 0.0)),
               wear=u8(np.where(grown[..., None], dil['wear'], 0.0)), palette_base=pal, coverage=cov)
    wm = wear[cov]
    log(f'[cowboy_hat] material {size}^2 x ss {ss}: {time.time() - t0:.1f}s over {int(cov.sum())} texels '
        f'({cov.mean() * 100:.1f} % of the sheet); palette base (linear) '
        + ', '.join(f'{k} {np.round(v, 4).tolist()}' for k, v in pal.items())
        + '; wear, mean / p95 over the covered texels: ' + ', '.join(
            f'{nm} {wm[:, i].mean():.3f} / {np.percentile(wm[:, i], 95):.3f}'
            for i, nm in enumerate(('sun fade', 'dust', 'sweat + salt', 'hands + rub'))))
    return out


# ------------------------------------------------------------------------------------------------------ fit data
def fit_data(spec=SPEC, n_probe=32, conform=None):
    """what forge/fit.py's fit_hat and the runtime's wear() need from the hat (prop space, metres; top_hat.fit_data's
    contract): the seat frame, the head opening (a long oval: its semi-axes on the seat plane), the crown's inner
    ceiling (the felt's inner face at its LOWEST within 45 mm of the seat axis: the crease dips there), the brim's
    extents, clearance probes (the brim's underside at three widths, the opening's rim), and `conform`: {species:
    {pose: {translation, scale, tilt_deg}, ...}}, the pose validated per base (wear() takes it when the seat itself
    carries none for this prop)"""
    d = dims(spec)
    W = spec['brim_w']
    phi = np.linspace(0.0, 2.0 * np.pi, n_probe, endpoint=False)
    rho = np.array([0.25 * W, 0.6 * W, W])
    P, N, _ = brim_frame(phi, rho, spec)
    under = P - half_thickness(rho, spec)[None, :, None] * N
    opening = np.column_stack([d['rx_o'] * np.sin(phi), np.zeros_like(phi), d['rz_o'] * np.cos(phi)])
    Pe, Ne, Te = brim_frame(np.linspace(0.0, 2.0 * np.pi, 360, endpoint=False), [W], spec)
    he = float(half_thickness(W, spec))
    edge = Pe[:, 0] + he * Te[:, 0]
    r_edge = np.hypot(edge[:, 0], edge[:, 2])
    g = np.linspace(-0.045, 0.045, 31)
    X, Z = np.meshgrid(g, g, indexing='ij')
    m = np.hypot(X, Z) <= 0.045
    ph, th = plan_to_th(X[m], Z[m], spec)
    Pm, Nm = crown_frame(ph, th, spec)
    ceiling = float((Pm - 0.5 * spec['felt_t'] * Nm)[:, 1].min())
    rnd = lambda a: np.round(np.asarray(a, np.float64), 5).tolist()
    # the FIT VOLUME (G5, the remix's hat probe, against a WORN hat: PLAN C0 "each worn accessory's fit volume, not a
    # margin"): two upright CYLINDERS about the seat axis that hold the whole hat: the BRIM (its faces and bound edge
    # all round, over their own height range) and the CROWN (from the brim's top to the ridges, the band, knot and
    # tails inside its radius), each 2 mm proud. A back mount's reach envelope must clear them at the pose in use
    # (accessories_b5/cowboy_hat/scripts/f08_g5.py g5_worn: the pure-Python distance). FIRST TRY, refused: one capsule
    # round the axis (radius 187 mm) stood 164-192 mm under the true distance from a person's back sockets (its round
    # ends bulge 187 mm below a hat that is 44 mm deep there)
    pg, tg = np.meshgrid(np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False), np.linspace(0.0, 0.5 * np.pi, 24),
                         indexing='ij')
    Pc, Nc = crown_frame(pg, tg, spec)
    Pc = Pc + 0.5 * spec['felt_t'] * Nc
    # (11-10: the brim in EVERY shape a wearer's pose may use: with its dip taken out (brim_spec) the same felt reached
    # further out front and back. 11-11, THE FIT LAW: a hat is RIGID, its brim has ONE shape on every wearer, so the
    # volume holds that one shape)
    rb = np.linspace(0.05, 1.0, 12) * W
    hb = half_thickness(rb, spec)[None, :, None]
    brim_pts = []
    for share in (0.0,):
        sp = brim_spec(share, spec)
        pb, nb, tb = brim_frame(np.linspace(0.0, 2.0 * np.pi, 72, endpoint=False), rb, sp)
        brim_pts += [pb[:, -1] + he * tb[:, -1], (pb + hb * nb).reshape(-1, 3), (pb - hb * nb).reshape(-1, 3)]
    brim_pts = np.vstack(brim_pts)
    pad = 0.002
    y_b0, y_b1 = float(brim_pts[:, 1].min()) - he - pad, float(brim_pts[:, 1].max()) + he + pad
    r_b = float(np.hypot(brim_pts[:, 0], brim_pts[:, 2]).max()) + he + pad
    r_c = float(np.hypot(Pc[..., 0], Pc[..., 2]).max()) + spec['band_t'] + spec['cord_amp'] + spec['knot_t'] + pad
    y_c1 = float(Pc[..., 1].max()) + pad
    # rigid: THE FIT LAW (accessories_b5/SKYE_ON_THE_ACCESSORIES_1111.md 3): a placement and ONE uniform scale, no
    # morph; the staged wear() (STAGED.md F1) reads it and never scales this prop per axis
    return dict(archetype='hat', prop=NAME, rigid=True,
                volume=dict(kind='cylinders', axis='+Y',
                            parts=[dict(name='brim', y=[round(y_b0, 5), round(y_b1, 5)], radius=round(r_b, 5)),
                                   dict(name='crown', y=[round(y_b0, 5), round(y_c1, 5)], radius=round(r_c, 5))],
                            note='the whole hat inside two upright cylinders about the seat axis (prop space, '
                                 'metres): G5 measures a back mount\'s reach envelope against them at the pose in '
                                 'use'),
                seat=dict(origin=[0.0, 0.0, 0.0], up=[0.0, 1.0, 0.0], forward=[0.0, 0.0, 1.0], left=[1.0, 0.0, 0.0]),
                opening=dict(rx=round(float(d['rx_o']), 5), rz=round(float(d['rz_o']), 5), y=0.0,
                             circumference=spec['head_circ']),
                crown_inner_height=round(ceiling, 5),
                crown_outer=dict(r_base=round(float(0.5 * (d['Bx'] + d['Bz']) + 0.5 * spec['felt_t']), 5),
                                 r_top=round(float(0.5 * (d['Tx'] + d['Tz'])), 5),
                                 height=round(float(d['y_mid'] + spec['crown_h'] + 0.5 * spec['felt_t']), 5)),
                brim=dict(width=W, y_min=round(float((Pe[:, 0, 1] - he).min()), 5),
                          y_max=round(float(edge[:, 1].max() + he), 5), r_front=round(float(r_edge[0]), 5),
                          r_side=round(float(r_edge[90]), 5)),
                bow_side='+X', conform=conform or {},
                probes=dict(brim_under=rnd(under.reshape(-1, 3)), opening=rnd(opening)))


# ----------------------------------------------------------------------------------- the brim shaped for a wearer
def brim_spec(share, spec=SPEC):
    """the hat with its brim's front / back dip taken out by `share` (0: the measured Stetson; 1: the brim level
    front and back; the side roll, the edge curl and the width stay): what a hatter does with steam for a wearer whose
    head does not fall away under the brim. A person's forehead and nape drop 30 mm inside the brim's dip; the
    octopus's mantle crest, the stag beetle's head and the axolotl's skull do not, and the dipped brim enters them at
    every size (accessories_b5/slice_NOTES.md, the fit step). The crown, the band and the inside are untouched"""
    return dict(spec, dip=spec['dip'] * (1.0 - float(share)))


def conform_shape(low, share, spec=SPEC):
    """the export's vertices (low_arrays' split set: low['V'], ['F'], ['UV'], ['region'], ['orig']) with the brim
    shaped by brim_spec(share): the low built again from the changed SPEC (the same stations, columns and tails, so
    the same vertices in the same order), its normals by low_arrays' rule (smooth within each SMOOTH_GROUP).
    Returns (V, N) for a morph target's deltas (peaked_cap's conform morph: accessories.js wear() sets it at exactly
    the pose it was fitted for)"""
    from .. import bake
    low2, _ = build_low(brim_spec(share, spec), log=lambda s: None)
    orig = np.asarray(low['orig'], np.int64)
    assert len(low2.V) == int(orig.max()) + 1, (len(low2.V), int(orig.max()) + 1)
    V2 = np.asarray(low2.V, np.float64)[orig]
    F, region = np.asarray(low['F']), np.asarray(low['region'])
    grp_of = np.zeros(len(REGIONS), np.int64)
    for g, regs in enumerate(SMOOTH_GROUPS):
        grp_of[list(regs)] = g
    fn = np.cross(V2[F[:, 1]] - V2[F[:, 0]], V2[F[:, 2]] - V2[F[:, 0]])
    acc = np.zeros((len(low2.V), len(SMOOTH_GROUPS), 3))
    for k in range(3):
        np.add.at(acc, (orig[F[:, k]], grp_of[region]), fn)
    vg = np.zeros(len(V2), np.int64)
    vg[F.ravel()] = np.repeat(grp_of[region], 3)
    N2, _ = bake.low_frames(V2, F, np.asarray(low['UV']), _unit(acc[orig, vg]))
    return V2, N2


# -------------------------------------------------------------------------------------------------------- export
# (11-11, Skye: "make sure they're also optimized as best you can!") THE DELIVERED SIZE OF THE MAPS (the masters stay
# the bake's 2048 sheet: T_<name>_*.png and the macro glb, `deliver=None`). The runtime decodes every PNG / JPEG to
# RGBA8 + mips (no KTX2): a 2048 map is 21.3 MB on the GPU, a 1024 5.3, a 512 1.3. The felt hats' 2048 sheet is 0.16
# mm a texel against the closest view's 0.43 mm a pixel (2.6 texels a pixel: the GPU samples its mip 1.4 there), so a
# 1024 set (0.33 mm) is what that view reads. MEASURED on the cattleman (accessories_b5/cowboy_hat/scripts/
# o02_maps_detail.py: the 2048 octave over the used texels; the engine A/B at the review views, 0.3-0.4 mm a pixel,
# slice_NOTES 11:0x): ORM + masks at 1024: p99.9 3 levels of 255, 13 pixels over 6; every map at 1024: p99.9 4-6,
# the largest a softer sweatband edge INSIDE the crown (seen from below only). The masks hold nothing above 1024's
# Nyquist (fuzz p99 1.7 steps) and carry classes, not detail: 512. The kit's other builders deliver the same way
# (the hard hat 1024 + masks 512; the masks 1024): ONE filter for the kit, the SOFT builder's
# `soft_common.deliver_maps` (albedo in linear light; normals as vectors, their lost length folded into the roughness;
# the palette zone by majority), used as it stands
DELIVER = dict(maps=1024, masks=512)


def delivered(maps, deliver=DELIVER):
    """the maps as they ship (soft_common.deliver_maps at deliver['maps'], the masks once more at deliver['masks']);
    deliver None: the masters as they are (the macro glb)"""
    if not deliver:
        return maps
    from .soft_common import deliver_maps
    out = deliver_maps(maps, deliver['maps'])
    if deliver.get('masks') and deliver['masks'] < deliver['maps']:
        out['masks'] = deliver_maps(out, deliver['masks'])['masks']
    return out


def maps_alike(a, b, steps_p99=8, steps_max=16):
    """two skins' maps close enough to ship as ONE texture: their p99 / max absolute difference in 8-bit steps over
    every channel. The cattleman's four ORMs: occlusion and metal identical, roughness p95 1-4 / max 13 (the felts'
    own small differences)"""
    d = np.abs(np.asarray(a, np.int16) - np.asarray(b, np.int16))
    return float(np.percentile(d, 99)) <= steps_p99 and int(d.max()) <= steps_max, float(np.percentile(d, 99)), int(d.max())


def export_glb(path, low, maps, spec=SPEC, conform=None, shapes=None, variant=None, skins=None, deliver=DELIVER,
               log=None):
    """a static glb as top_hat.export_glb writes it: one mesh (every triangle: the stacked islands show their
    primaries' texels), one material (base, normal, ORM; the masks in KHR_materials_volume's thickness slot), the fit
    data in the root node's and the file's extras. shapes: {target name: (V, N)} from conform_shape, one MORPH TARGET
    each (the 11-10 fit's shaped brims; THE FIT LAW of 11-11 forbids them: a rigid hat is exported with none).
    variant: the colour's name (VARIANTS), written into the extras; the prop's name stays NAME.
    skins: (11-11) {colour: its maps} in order, the FIRST the default: ONE glb for every colour (Skye: "brown/black/
    white/grey skins" / "as in texture material skin alternatives"): one mesh, ONE normal map (every skin's normal
    must be that picture: checked), the default's albedo / ORM / masks on the material, every other skin's three
    as textures of their own, named in the file's extras `bestiary.skins` = {default: <colour>, <colour>: {base,
    orm, masks: texture index, palette_base}} (the runtime's choice of a skin: accessories_b5/STAGED.md F5).
    deliver: the maps' delivered sizes (DELIVER: 1024, the masks 512; None: the bake's masters, the macro glb). (11-11)
    A skin whose delivered ORM is the default's within maps_alike SHARES the default's texture (one ORM for the
    cattleman's four felts); its own masks (the felt's sheen differs per colour) and albedo stay its own"""
    from .. import gltf
    say = log or (lambda s: None)
    g = gltf.GLB()
    if skins:
        names = list(skins)
        for nm in names[1:]:
            if not np.array_equal(np.asarray(skins[nm]['normal']), np.asarray(skins[names[0]]['normal'])):
                raise ValueError(f'the skin {nm!r} has a normal map of its own: a skin changes colour, never relief')
        master = int(np.asarray(skins[names[0]]['albedo']).shape[0])
        skins = {k: delivered(v, deliver) for k, v in skins.items()}
        maps = skins[names[0]]
        variant = names[0]
    else:
        master = int(np.asarray(maps['albedo']).shape[0])
        maps = delivered(maps, deliver)
    t_base = g.texture(maps['albedo'], fmt='jpeg', quality=94)
    t_nrm = g.texture(maps['normal'], fmt='png')
    t_orm = g.texture(maps['orm'], fmt='jpeg', quality=94)
    t_msk = g.texture(maps['masks'], fmt='png')
    say('[cowboy_hat] delivered maps: ' + ', '.join(f'{k} {np.asarray(maps[k]).shape[1]}' for k in
                                                    ('albedo', 'normal', 'orm', 'masks')) + (
        f'; the normals\' spread folded into the roughness on {maps["delivered"]["spread_texels"]} texels (p99 +'
        f'{maps["delivered"]["roughness_raised_p99"]:.3f})' if 'delivered' in maps else ' (the masters)'))
    extra = dict(variant=variant) if variant else {}
    if deliver:
        extra['delivered'] = dict(deliver, master=master, filter='forge/props/soft_common.deliver_maps')
    if skins:
        sk = {'default': names[0], names[0]: dict(base=t_base, orm=t_orm, masks=t_msk,
                                                   palette_base=maps.get('palette_base', {}))}
        for nm in names[1:]:
            m = skins[nm]
            alike, p99, mx = maps_alike(m['orm'], maps['orm'])
            say(f'[cowboy_hat] skin {nm}: its ORM against {names[0]}\'s: p99 {p99:.0f}, max {mx} steps -> '
                + ('SHARED (one texture)' if alike else 'its own'))
            sk[nm] = dict(base=g.texture(m['albedo'], fmt='jpeg', quality=94),
                          orm=t_orm if alike else g.texture(m['orm'], fmt='jpeg', quality=94),
                          masks=g.texture(m['masks'], fmt='png'), palette_base=m.get('palette_base', {}))
        extra['skins'] = sk
    mat = g.material(NAME, base=t_base, normal=t_nrm, orm=t_orm, volume_tex=t_msk, extras=dict(
        bestiary='prop', prop=NAME, masks=t_msk,
        masks_channels='R fuzz / sheen amount, G material (0 felt, 1/3 grosgrain, 2/3 leather, 1 satin), B palette '
                       'zone (0 felt, 1/3 band and bow, 2/3 binding, 1 inside); RGB, no alpha (the engine divides a '
                       'PNG\'s colour by a partial alpha)',
        palette_base=maps.get('palette_base', {}), **extra))
    mesh = g.mesh(NAME, low['V'], low['N'], low['TAN'], low['UV'], [(low['F'], mat)])
    if shapes:
        names = sorted(shapes)
        g.morph_targets(mesh, [(np.asarray(shapes[k][0], np.float64) - low['V'],
                                np.asarray(shapes[k][1], np.float64) - low['N']) for k in names], names)
    fit = fit_data(spec, conform=conform)
    g.node(NAME, mesh=mesh, root=True, extras=dict(bestiary='prop', fit=fit))
    return g.save(path, extras=dict(bestiary=dict(prop=NAME, archetype='hat', units='m', up='+Y', forward='+Z',
                                                  left='+X', triangles=int(len(low['F'])), fit=fit, **extra)))


# --------------------------------------------------------------------------------------------- the whole forge
def forge(out_dir, size=2048, voxel_size=0.00025, band=0.0015, ss=2, seed=7, spec=SPEC, conform=None, log=print,
          material=True):
    """block-out -> low (+ gates) -> UVs -> plan -> voxel high (GPU) -> bake (GPU) -> material -> glb; returns the
    glb's path (top_hat.forge's stages; ~50 M voxels at 0.25 mm). The bake and the material pass see the PRIMARY
    triangles; the tails (not in the high) take tail_drivers. Writes drivers_cowboy_hat.npz, low_cowboy_hat.npz (the
    export's arrays: export_glb again from them and the T_ maps re-writes the glb without a bake) and the four maps
    + T_cowboy_hat_wear.png.
    material=False: stop when the bake is saved (returns None). The material pass in THIS process hung once after
    the bake (11-10: 0 s of CPU in 20 minutes, the cause not found), while the same pass in a process of its own
    (run_material on the saved drivers) has run 20 times in 20-60 s: an unattended chain bakes with material=False"""
    import json
    import os
    import time

    from PIL import Image

    from .. import bake, gates, voxel
    t0 = time.time()
    os.makedirs(out_dir, exist_ok=True)
    prog = build_sdf(spec)
    low, info = build_low(spec, prog=prog, log=log)
    q, txt = gates.quad_quality(low, prog, region_names=None)
    log('[cowboy_hat] gates:\n' + txt)
    d02 = quad_diagonals(low, info, prog)
    uvs = unwrap(low, info, d02, size=size, log=log)
    L = low_arrays(low, info, uvs, d02)
    np.savez_compressed(os.path.join(out_dir, f'low_{NAME}.npz'),
                        **{k: v for k, v in L.items() if isinstance(v, np.ndarray)}, px_per_m=L['px_per_m'],
                        size=L['size'])
    plan = plan_hat(prog, spec, np.random.default_rng(seed), log=log)
    lo, hi = bounds(spec)
    G = voxel.SparseSDF(prog, lo, hi, voxel=voxel_size, band=band, extra=plan.bounds(prog, band), log=log)
    plan.apply(G, log=log)
    bk = L['primary'] & (L['region'] != REGIONS.index('tails'))
    res = bake.bake(G, L['V'], L['F'][bk], L['UV'], L['N'], L['TAN'], L['region'][bk], size=size, ss=ss, cage=0.006,
                    ao_r=0.02, cav_r=0.002, n_thk=2, thk_max=0.01, seed=seed, log=log,
                    region_names=dict(enumerate(REGIONS)))
    log(f'[cowboy_hat] the tails\' texels set by hand: {tail_drivers(res, L, size)}')
    keep = {k: (v.astype(np.float16) if v.dtype == np.float32 and k != 'base' else v) for k, v in res.items()
            if k != 'position'}
    np.savez_compressed(os.path.join(out_dir, f'drivers_{NAME}.npz'), **keep)
    if not material:
        log(f'[cowboy_hat] the bake is saved (drivers_{NAME}.npz) after {time.time() - t0:.0f}s; the material '
            f'pass and the glb are left to a process of their own')
        return None
    maps = run_material(L, res, size, 1.0 / L['px_per_m'], spec, ss=ss, log=log)
    for k in ('albedo', 'normal', 'orm', 'masks', 'wear'):
        Image.fromarray(maps[k]).save(os.path.join(out_dir, f'T_{NAME}_{k}.png'))
    with open(os.path.join(out_dir, 'palette_base.json'), 'w') as fh:
        json.dump(maps['palette_base'], fh)
    path = os.path.join(out_dir, f'{NAME}.glb')
    n = export_glb(path, L, maps, spec, conform)
    log(f'[cowboy_hat] wrote {path} ({n / 1e6:.1f} MB) in {time.time() - t0:.0f}s')
    return path
