"""The RAPTOR head archetype (HAWK_PLAN.md §2.4, §4.1, §4.5): the face built on c018's lateral photo (an adult
red-tail's head in true profile), mapped onto H1's skeleton (families/avian.py rest_chain: the eye centre and the bill
tip). Life MILLIMETRES in the world (the chain's frame: +z forward, +y up, +x the bird's left); the sdf members in
metres.

THE FACE FRAME. c018's pixels (x right = forward, y down) go to the head's sagittal plane by one similarity: the eye
centre onto the skeleton's eye (its y and z), the traced bill tip onto the skeleton's bill tip. The plan's scale rule
(§2.4: the eye centre 46.4 mm from the bill tip, S1's skull plus 2 mm of keratin [E]) is then exact by construction;
the photo's head pitch is replaced by the bind's (one rotation, printed by face_frame).

TRACED BY EYE ON c018 (D1.3, the full-resolution photo under a 50 px grid: scratchpad gridcrop.py; px, x right, y down):
  CULMEN    the upper rhamphotheca's top edge from the cere's front margin over the arch to the hook's tip
  TOMIUM    its lower edge from the cere's front foot forward to the hook's corner, then the hook's inner edge to the tip
  CHIN      the lower rhamphotheca's lower edge from where its keratin starts (D1.3c fix 1: re-read on 4x / 7x grids;
            D1.3's followed the chin's bristles over its base)
  CROWN     the plumage's top silhouette from behind the eye to the cere's top
The plan's landmark bill tip (1630, 915) lies on the hook's front curve, 1.3 mm from the tip traced here (1605, 922);
the scale follows the plan's definition with the traced tip (18.35 px/mm against the plan's 18.76).

MEMBERS (the clay, HAWK_PLAN §4.5; D1.3b restart 2's head):
  skin   the head envelope (elliptical PSWEEP pieces along the head's axis, its sections from CROWN less the plumage
         depth SPEC head.plumage, half widths [E]; the lores one V from the eye's front to the cere's back, flush with
         the cere's flanks), the LIDS (D1.3c fix 1: the lid's sphere raised round each eye, c018's own outline of the
         lids carved through it along the eye's axis, a rounded margin all round) and the eye's cap in the opening (a
         low dome, the EYE set's cornea replaces it; the globe sits avian.EYE_BACK behind c018's eye_c so its iris
         lands on c018's pupil), the brow (the supraorbital SHELF: an eave PSWEEP over the eye, its edge over the lids'
         outermost, its top one convex run into the crown), the CERE (a sleeve over the upper shell's base: the shell's own
         margin section carried back, ending on the shell's margin plane), the gape (the crack's crease and the yellow
         flesh's band along each side's mouth line to the rictus under the eye), the nostril pits
  shells the UPPER rhamphotheca (a PSWEEP: the section an ellipse's upper arc over two tomia, broad at the base (a
         bell head-on) and meeting at the hook's keel (D1.2's HOOK test: PSWEEP holds it to 0.7 um)), the LOWER (a
         PSWEEP of ellipse sections along the CHIN / TOMIUM pair), each its own closed Program sunk into the skin
"""
import numpy as np

from .. import sdf
from ..families.avian_body import pn_kw      # the PSWEEPs' per-node divisor where the installed sdf has it (D1.3c)

MM = 1e-3
PLAN_PX_PER_MM = 18.76                 # plan §2.4 [M-pl from E]: the landmark tip's scale (printed beside ours)
EYE_PX = (865.0, 500.0)                # c018 landmarks.json eye_c
TIP_PX = (1605.0, 922.0)               # traced (module docstring)
CULMEN_PX = np.array([(1502, 502), (1540, 520), (1575, 550), (1602, 580), (1625, 615), (1642, 655), (1655, 700),
                      (1661, 740), (1661, 780), (1655, 825), (1645, 860), (1632, 890), (1615, 915), (1605, 922)],
                     float)
TOMIUM_PX = np.array([(1440, 735), (1460, 740), (1500, 750), (1530, 770), (1570, 795), (1577, 805), (1585, 825),
                      (1592, 860), (1600, 905), (1605, 922)], float)
LOWER_TOP_PX = np.array([(1380, 714), (1400, 718), (1425, 728), (1440, 735), (1460, 740), (1500, 750), (1530, 770),
                         (1565, 792)], float)
CHIN_PX = np.array([(1380, 777), (1400, 781), (1425, 785), (1450, 790), (1475, 795), (1500, 799), (1525, 802),
                    (1550, 804), (1565, 805)], float)
#                                        (D1.3c fix 1: the lower rhamphotheca re-read on c018 under 5 px grids at 4x and
#                                        7x, scratchpad d13c_fix1/grid/c018_lowerbill*.png: its keratin starts at x 1378,
#                                        3.5 mm tall there, behind it the gape's bare yellow skin; D1.3's CHIN followed
#                                        the chin's bristles from x 1395 (the base 1.85 mm tall): the lower bill showed
#                                        1.8-2.4 mm of c018's 2.8-3.5, "a sliver", the D1.3c check)
CROWN_PX = np.array([(200, 255), (300, 170), (400, 135), (500, 115), (600, 107), (700, 105), (800, 107), (900, 112),
                     (1000, 125), (1100, 145), (1200, 180), (1300, 230), (1370, 280), (1410, 340), (1440, 390)], float)
CERE_PX = dict(back_top=(1340.0, 420.0), front_top=(1502.0, 502.0), front_foot=(1460.0, 620.0), nostril=(1435.0, 580.0))
RICTUS_PX = (910.0, 715.0)             # landmarks.json c018 rictus
IRIS_PX = 11.7                         # SPEC head.iris (mm): the visible iris

HALF_W = dict(occiput=17.0, brain=20.0)    # [E] skin half widths (the eyes set the widest; the lores the sleeve)
BEAK_W0, BEAK_W1 = 4.6, 0.45            # [M-pl from E: c044 head-on] the upper bill's half width at the cere, the tip
#                                         (D1.3c fix 1: c044 under a 5 px grid at 8x (scratchpad d13c_fix1/grid/
#                                         c044_bill8.png), at the fitted camera's 5.32 px/mm (its iris 11.3-11.7 mm, as
#                                         SPEC's): the keratin 6.6-8 mm across at the cere's margin, about 10 at the
#                                         gape, the cere's hood 13.2-13.5 mm round it, so 2.5-4 mm of cere beside the
#                                         bill each side. D1.3c's 6.3 (12.6 mm) left the cere a 0.3-0.5 mm skin on the
#                                         bill's flanks: a thin U frame head-on, the D1.3c check. Plan §8.1's 14 x 18
#                                         [E] was wider still)
BEAK_TAPER = 1.6                        # [E: c019 head-on] _bill_width's exponent (D1.3: 0.9, a spike head-on)
LOWER_TOP_N = 4.0                      # the lower section's top half: a superellipse of this exponent (_lower_section)
LOWER_GAP = 0.15                       # mm the lower's top edge stands under the upper's tomium (the shells never
#                                        touch; D1.3c fix 1: 0.3 -> 0.15, c018 shows the lower's side from the edge down)
LOWER_W0, LOWER_W1 = 4.8, 0.8          # [E] the lower's half width at its base, at the tip (D1.3b: 5 -> 6, the rami
#                                         spread under the upper's 7; at 5 the face's front showed beside it. D1.3c fix 1:
#                                         4.8 under the narrower upper's tomia, 5.06 apart at the gape)
ENV_SMOOTH = (3.0, 4.5)                 # stations: the envelope's top / bottom and half width Gaussians (D1.3: 2, 3;
#                                         D1.3b's eye width and front taper took |grad| < 0.6 to 9 % of the head's
#                                         points, 1.5 % at 3, 4.5: scratchpad gradhead3.py)
HEAD_PIECES = 1                        # the head envelope's PSWEEP pieces (head_members). ONE (D1.3c fix 2): six
#                                        overlapping pieces each divide by their OWN divisor (1.26-1.56), so the
#                                        envelope's field jumped 19-24 % across each piece's end plane, and every
#                                        smooth union that reads that field (the lids' skin, the cere, the lips) put a
#                                        3-6 deg crease on the surface along that plane (scratch kw.py on c10: 5.4 deg
#                                        on the cheek 6 mm behind the eye, the same plane at every height). One piece:
#                                        one divisor (the largest, 1.56: |grad| 0.64, over the gates' 0.4), no seam
ENV_N = 192                            # the envelope's ellipse polygon points (D1.3c fix 1: 128 put a 2.8 deg normal
#                                        kink every 1 mm round the head, facet lines in the close views at 25 px / mm)
ENV_DENSE = (6, 0.6)                   # D1.3c fix 2: the envelope's PSWEEP stations per construction node, and the
#                                        Gaussian (in nodes) over the stations' keys. The keys ran straight between the
#                                        48 nodes, 1.29 mm apart: the surface turned 1-8 deg at each (check 2's kink
#                                        walk: 20 spikes along the crown's midline, each within 0.04 mm of a node):
#                                        bands on the cheek, rings round the bill, terraces on the crown, all of which
#                                        would bake into the normal map. Now 283 stations 0.21 mm apart on the smoothed
#                                        profile (fix 1 did the same for the brow's keys)
ENV_FRONT_SINK = (1.4, 5.0)            # mm: the envelope's last stretch (mm, the second number) sinks this far under
#                                        its own section all round, eased to nothing behind it (D1.3c fix 2). The
#                                        envelope ends on a FLAT plane normal to the head's axis 3 mm behind the bill
#                                        base's centre, 0.3-0.8 mm inside the base's skin: the base's smooth union
#                                        with it (CERE_K) swelled the keratin band by 0.15 mm up to that plane and not
#                                        beyond: an S-step with 5 deg kinks along the plane's trace, t = 3 + 0.40 (y -
#                                        1.3) in the margin frame (scratch kw.py: 1.3 mm behind the margin at y -3.5,
#                                        2.1 at y -1.5: the upright crease under the nostril in the 55 px/mm look).
#                                        Sunk 1.4 mm the end lies past the union's reach (k x the divisor: 0.94 mm)
FRONT_TAPER = 4.5                      # [E] mm: the envelope's front end eases inside the cere and the two bills over
#                                         this length (D1.3b: its flat PSWEEP end stood as a wall from the cere to the
#                                         chin, the lower bill poking out of it)
A_TOP = 0.4                             # D1.2's beak section: the ellipse's half height / the height (keel outside it)
TOMIA = (1.10, 0.10, 0.65)              # [E: c019, c044 head-on (D1.3c: 1.15 flared the base past the cere: the
#                                         tomia at the gape about 1.08 x the arch's width on c044); a raptor's upper
#                                         bill is an arch over the lower, its two
#                                         tomia apart at the gape, its flanks flaring to them: a bell head-on (0.95's
#                                         upright flanks made the cere sleeve a box)] the tomia's half separation / the bill's half width:
#                                         TOMIA[0] from the base to u TOMIA[1], easing (smoothstep) to D1.2's single keel
#                                         by u TOMIA[2] (the hook). D1.3's keel the whole length was a thin spike
#                                         head-on (the D1.3 check, 11-08). D1.3c: the keel by 0.65 (0.55 closed the
#                                         tomia at 1.45 mm per mm of the palate: the body piece's divisor 1.76, |grad|
#                                         0.57 along them; 0.65: 1.18 / 1.55)
WT_MIN = 0.03                           # mm: the keel's two tomia points stay 2 x this apart (one section topology)
RHO_K = 20e-6                           # m: the tomium's keel rounding (D1.2)
NE = 120                                # ellipse arc points per key
U_END = 0.985                           # the hook's last 1.5 % (a section under 0.5 mm) is the PSWEEP's flat end
UPPER_TIP = ((0.72, 0.88), (0.84, 1.0))   # the HOOK's pieces on the curved centreline (fractions of its nodes' span,
#                                         overlapping): beak() says why
UPPER_BODY = dict(pitch=24.0, stop=0.78, back=0.5, n_u=2800)
#                                         D1.3c: the bill's BODY, from its sunk base to station `stop` (x U_END), as ONE
#                                         STRAIGHT piece: on the curved centreline the deep base sections' 9-10 mm reach
#                                         against the culmen's ~12.7 mm bend left H 0.28 and divisors 2.9-5.2 over every
#                                         segment (|grad| 0.2-0.3). A raptor's bill is a fan round the hook's inner
#                                         corner: the tomium runs straight to it while the culmen arcs over. The piece's
#                                         line is the base tangent pitched `pitch` deg down (between the palate's line
#                                         and the hook's), its keys the TARGET's cuts by the planes normal to that line
#                                         (_upper_grid: n_u stations, `back` behind the base), its end the plane through
#                                         the farthest target point of its stations; the hook's first piece starts
#                                         behind every target point in front of that plane (asserted in beak()), so each
#                                         target point lies in a piece and the hard union is the target. Scanned
#                                         (scratch billscan.py) for the lowest divisors: the body's nodes 1.21 (p50) to
#                                         1.63 (the tomia where the bell closes to the keel), the hook's 1.2. (The first
#                                         D1.3c build cut four 25 % chord pieces between their end NODES' planes, +-18
#                                         deg off the sections: 2-3 mm wedges of the culmen lay in no piece, notches
#                                         across the bill, and its ARCH / TOMIA split left a crease along the flank;
#                                         eight short chord slabs with whole sections were seamless but cut the level
#                                         tomium at up to 70 deg from the hook's side: divisors 1.6-3.3)
SINK = 2.0                              # mm the shells' bases reach behind the cere / gape collar's front margin
BACK_TAPER = 11.0                       # [E] mm: the envelope's back end radius, inside the neck (avian_body NECK_R 15.5)
CHIN = (8.0, 1.5)                      # [E] mm of jaw / throat skin under the gape line: behind, at the bill's base
#                                         (D1.3c: 3 -> 1.5: the envelope's front end inside the LOWER COLLAR, whose
#                                         margin section is the lower shell's (1.85 mm deep) + its skin)
LOWER_COLLAR = dict(skin=(0.3, 0.6), grow=(1.6, 1.4), length=5.0, k=1.2, n=16)
#                                         [E: c018, c044] the jaw's skin round the lower shell's base, as the cere is
#                                         round the upper's: its margin key + skin[0] at the lower shell's margin plane,
#                                         growing back over `length` mm by grow (half width, depth below) and skin[1];
#                                         smooth union k. D1.3b's CHIN_CUT alone left the chin's end a flat face round
#                                         the lower bill head-on (the bottom of the "U-frame", the wave 5 check)
CHIN_CUT_K = 1.0                        # mm: the chin's cut blended (its own SUBTRACT group; D1.3c fix 1)
CHIN_CUT = (14.0, 8.0, 6.0, 0.2)        # mm: the box SUBTRACTED from the skin in front of the lower bill's margin plane
#                                         and under the mouth line (half extents lateral, vertical, forward; its top's
#                                         clearance over the lower bill's top edge): the chin's skin ends at the lower
#                                         bill's margin (c018: the chin's feathers end there, 2-3 mm behind the cere's
#                                         margin). D1.3b r2: carried to the envelope's end the chin ran 2 mm over the
#                                         lower shell's margin, the cage's lower SOCKET ring sat inside the skin and its
#                                         bridge folded; a rise of the envelope's bottom there instead set its front
#                                         piece's divisor to 3.3 (|grad| p1 0.45 -> 0.32)
EYE_PROUD = 0.5                     # [E] mm the globe's lateral pole stands past the head's skin envelope at the
#                                         eye's height (D1.3: 4.0, then 1.5 at the section's widest point, 2-3 mm more
#                                         at the eye's height: goggles, the D1.3 check; D1.3b 0 with the globe faired in:
#                                         a dome. D1.3c 0.5 with no globe member: the envelope passes about the globe,
#                                         so the lids' rim plane lies where the EYE set's ball crosses the opening's
#                                         circle (3 sank it 3 mm: the ball would have stood out of the clay's lids)
LID_K = 0.3                             # [E] mm: the eye's ball blended into the lids round it
CORNEA = dict(base=12.5, sag=2.8, k=0.3)
#                                         [M-pl: c019] the CORNEA (D1.3c fix 2, the lead's call 2 after check 2): its
#                                         own dome on SPEC's 22.5 mm globe, of smaller radius: a sphere's cap on the
#                                         limbus circle `base` mm across (the iris 11.7 + 0.8) lying on the globe's
#                                         sphere, `sag` mm tall over that circle's plane: radius 8.4 mm, its apex 0.9
#                                         mm past the globe's own pole; blended k into the globe (the limbus'
#                                         furrow). MEASURED on c019 (scratchpad d13c_fix2/ey.py, grid/
#                                         c019_near_eye_4x.png): its camera sees the bird's left eye 78 deg off the
#                                         eye's axis, nearly in profile: the lid margins vanish behind the eye's
#                                         bulge at (1140, 402) and (1158, 507) px and the eye's surface stands 17 px
#                                         = 1.67 mm past the line through them (10.19 px/mm). The clay, the same
#                                         construction at check 2's fitted c019 camera: sag 2.2 -> 0.99 mm, 2.5 ->
#                                         1.22, 2.8 -> 1.65, 3.0 -> 2.19 (the lids 0.45 mm thick); fix 1's flat cap
#                                         0.42. So 2.8 (the first build of this round took 3.0 [E]: 0.5 mm too
#                                         proud). c044 head-on agrees in kind (grid/c044_left_eye_12x.png: a lit
#                                         crescent on the eye's lateral flank past the iris, the iris 9.9 x 12.2 mm
#                                         where a flat disc on the 65 deg axis would show 0.42).
#                                         D1.3c fix 1's cap: one sphere of radius 11.0 whose top lay 1.25 mm INSIDE the
#                                         globe's own sphere, "a flat lens" (check 2); D1.3b's (radius 14) "a
#                                         porthole's glass" (the wave 5 check)
EYE_OPEN_PX = np.array([(740, 480), (760, 440), (800, 420), (880, 411), (950, 418), (1007, 440), (1013, 513),
                        (990, 545), (963, 567), (920, 585), (880, 593), (830, 585), (790, 567), (760, 535)], float)
#                                         [E: c018 under a 20 px grid, the D1.3c check's reading (scratchpad
#                                         d13c_check1/k10_matched.py), checked on the fix's 10 px crop] the LIDS'
#                                         OPENING as c018 shows it, back -> over the top -> front -> under: 14.9 x 9.9 mm,
#                                         the upper lid's margin nearly straight 4.1-4.6 mm over the pupil, the front
#                                         corner blunt, the back corner pointed, the lower lid an arc 5.3 mm under it
LID = dict(thick=0.45, fair=1.5, k=0.35, cut=1.0, n=96, reach=1.2, under=0.8, canthus=(4.0, 3.0, 13.0, 1.0, 2.2))
#                                         [E: c018] mm: the LIDS (D1.3c fix 2, the lead's call 2): the periorbital skin
#                                         and the lids LIE ON THE GLOBE and wrap it: a sphere `thick` over SPEC's globe
#                                         about the eye joint, smooth-unioned `fair` into the head's group (no zone, no
#                                         edge: where the head's skin is already outside it nothing changes), cut by
#                                         the opening (_eye_opening: c018's outline placed on that sphere, n points,
#                                         held `reach` inside the globe's radius in the eye's frame), its margin rounded
#                                         by the carve's blend k; the eye's ball (globe + cornea) fills the opening and
#                                         runs `under` the margin. canthus (radius, blend, length, rise, end radius)
#                                         mm: the LORES' FURROW from the front corner: forward of the eye the lores'
#                                         skin stands 3 mm outside the lid's sphere (the eye looks 65 deg out, so its
#                                         front corner lies on the globe's FRONT face, no farther out than the
#                                         globe's centre, while the face there is still 16 mm wide), and the
#                                         opening's carve left that as an upright wall at the corner (2.96 mm, check
#                                         2; still there in the first look of the lids on the globe, 11-10 21:02). A
#                                         round cone is subtracted with that blend: its first sphere touches the
#                                         lid's sphere from outside at the opening's foremost point, its axis runs
#                                         `length` forward along the head's side and `rise` out along the eye's
#                                         axis, its radius narrowing to the end radius: a furrow that shallows to
#                                         nothing toward the cere's flank, as a hawk's hollow lores do (c044 / c019:
#                                         the face is scooped between each eye and the bill; the bristles fill it).
#                                         The lores' own line runs 0.17 mm IN per mm forward (the face narrowing 0.7
#                                         mm per mm), so `rise` 1 over 13 mm leaves the furrow 3 mm deep at the
#                                         corner and gone 13 mm on. (TRIED: one sphere of radius 5.5: a round dent
#                                         under raking light, 21:13; a cone 7 long rising 3, radius 4 throughout: it
#                                         left the surface after 5 mm: a round CRATER in front of the eye at c019's
#                                         camera, the GPU look of 22:35.)
#                                         D1.3c fix 1 raised the lid sphere (about the flat
#                                         cap's own centre) only in the outline grown 2 mm: "the lid zone a raised
#                                         ring", the skin up to 1.39 mm INSIDE the globe's sphere under and behind the
#                                         opening, the front corner 0.8 mm short on a 2.96 mm upright wall (check 2).
#                                         D1.3b's torus round the rim, then D1.3c's dish with a level-box upper lid and
#                                         a crescent lower lid, each read as a disc in a ring, "round portholes" (the
#                                         wave 5 check, the D1.3c check)
BILL_BASE = dict(
    top=(6.80, 0.315, 0.25), w=(1.76, 1.42, 3.0, 2.5), c1=(0.3, 1.5), tail=(6.0, 0.9), step=(0.08, 6.0, 0.2),
    n=(220, 84, 12),
    skin=(0.40, 0.33, 2.5), cushion=(0.0, 2.9, -0.12, 1.5, 0.6, 2.1),
    front=((0.0, 0.45), (2.2, 1.0), (4.0, 0.89), (5.6, 0.70), (7.2, 0.54), (8.0, 0.59), (9.1, 0.71)),
    low=(1.0, -0.2, -0.72), lip=(0.4, 0.45, 3.3, 6.5, 3.0), edge=(0.35, 3.0, 1.6, 2.0), fade=4.0,
    band=((-1.0, 3.8), (-3.73, 2.95), (-6.8, 3.65)))
#                                         D1.3c fix 2 (the lead's call 1 after check 2): the BILL BASE, the head's own
#                                         surface behind the upper shell's MARGIN plane (the beak's SOCKET ring stays that
#                                         plane, the remix swaps beaks on it): the shell's margin section carried back
#                                         along -Tm, FLUSH with the shell at the plane (station 0 is the shell's own
#                                         margin key), with the CERE a wax skin on it inside c018's stepped edge: so the
#                                         cere is a SADDLE that ends at the nostril's lower rim, and under it the
#                                         keratin's base runs back as the head's own surface, keratin by form (no step
#                                         at the margin plane) and by material (head_members returns the edge). All in
#                                         the MARGIN FRAME: t mm behind the margin plane, y mm along bm = Tm x lateral,
#                                         sg mm round the section from the culmen. c018's readings carried into it:
#                                         scratchpad d13c_fix2/q1.py, q2.py (logs/q1.txt, q2.txt).
#   top    (y0, slope, te): c018's bare cere top is the line y = y0 + slope t (check 2's k45 pixels and the 7x grid
#          reading agree within 0.1 mm over t 0.3..5.9; it meets the crown's skin, CROWN less the plumage, at t 9.5 =
#          SPEC head.cere); the base's top leaves the shell's own slope (+0.017) for it over te mm, the skin on top
#   w      (dW, dWt, tw, pw): the arch's lateral semi-axis and the tomia's half separation grow by dW / dWt mm as
#          1 - exp(-(t / tw) ^ pw): the tomia 10.05 -> 12.9 mm apart (c019 12.8 mm of keratin at the mouth line, c044
#          12.3-12.5; S1's bony bill 12.8 at 14 mm behind its tip), the arch 9.0 -> 12.5 (13.2 with the skin: the cere
#          head-on c044 13.6, c019 12.1). pw 1.5 -> 2.5 (11-11): at 1.5 the flare started as sqrt(t): see c1
#   c1     (d_c, tau_c) mm: CONTINUOUS WITH THE BILL IN SLOPE at the margin plane, not only flush (the lead's call 1:
#          "flush and continuous with the bill"). Measured on the 23:01 build (scratch d13c_fix2/bs.py: the flank's
#          lateral half width across the plane at y -3.5): the shell arrives at +3..7 deg, the base left at +13 deg
#          0.3 mm behind the plane and +20 deg at 1 mm: a tangent break of 24 deg within 0.2 mm, an upright line at
#          the plane and the keratin band a flat panel beside the bill at c019's / c044's cameras ("boxes beside
#          the bill"). Now the base takes the shell's own slope at the plane (the shell cut d_c mm in front of it,
#          along station 0's rays) and turns into its own flare over tau_c mm; with pw 2.5 that flare grows from
#          nothing (a trumpet's bell toward the gape, as c019's left flank shows below the nostril)
#   tail   (mm past the cere's back, scale there): the member runs on inside the face, its top still on c018's line
#          (which the forehead's skin leaves upward at the cere's back), shrinking a little, eased. (3 mm shrinking
#          to 0.6: the cere's back dived under the forehead within 1 mm: a notch across the forehead 3 mm off the
#          midline, 70 deg of turning in 1.5 mm, 15.6 deg in one 0.1 mm step: scratch kw.py on c13; "rings round
#          the bill" head-on, check 2. Now the forehead rises off the cere's own line at a shallow angle)
#   step   (node spacing to `fine` mm behind the plane, fine, spacing behind it); n (arch, flank, palate points)
#   skin   (at the culmen, on the flanks, the Gaussian's width in sg): the wax skin's thickness, mm
#   cushion (mm more, its centre line y = y0 + slope t, its Gaussian width in y, t_in0, t_in1): the cere's flank swells
#          just over the nostril's upper rim (c018: the opening's upper lip overhangs it; c044 / c019: a cushion, not
#          an upright hood), easing in over t_in0 .. t_in1 behind the front edge (full at the edge it stood as a
#          pointed shoulder in the first sections, scratch out/q3_a_sections.png) and out behind the nostril with the
#          lower edge (lip's t0 .. t1). NOW 0 (11-10 22:25): at 0.30 and at 0.18 it stood round the nostril as a
#          puffed ring under raking light (scratch out/c8_c018_rake_cpu.png); the lip's overhang is the nostril's
#          own undercut (NOSTRIL['lean']), the cere's swell is its arch
#          (front's first knots: c018's silhouette shows the cere 0.8 mm farther forward on the midline than 0.65 mm
#          down the flank, (1518, 500) against (1503, 502): kept as a 0.55 mm lobe; at the full 0.9 the sections 1 mm
#          behind the plane read as a cap with two notches)
#   front  (sg, t) knots: c018's cere | keratin edge on the flank, culmen -> the nostril's lower rim (check 2's k45:
#          1518 on the midline, 1503 / 1497 / 1489 / 1480 / 1463 at rows 502 / 527 / 553 / 580 / 610)
#   low    (t_a, y_a, slope): the cere's LOWER edge, y = y_a + slope (t - t_a): along the nostril's lower rim (c018:
#          the yellow ends at row 619; under it the keratin band, 4.4 mm tall, 2.6 mm long at the mouth line)
#   lip    (r_f, r_l, t0, t1, r_l1): the edges' soft ramps, mm: the front edge's; the lower edge's, widening from
#          r_l at t0 to r_l1 at t1 (behind the nostril the edge fades out under the lores' bristles)
#   edge   (a, R, r_c, s_c): how the skin rises behind the FRONT edge. On the flanks only the share `a` of it rises
#          in the edge's own ramp r_f (a fine lip, 0.1-0.2 mm: c018's edge is a thin line the keratin runs out from
#          under), the rest swells slowly over R mm behind it (the cushion); at the culmen (within s_c mm round the
#          section, a Gaussian) the whole skin rises over r_c mm (c018's top outline is straight to 0.1 mm from 0.3
#          mm behind the edge). The cut run's first build rose the whole skin (0.33 + the cushion's 0.30) in 0.6 mm
#          all along: a cliff with a sharp brow down the flank at c018's camera (the first look, 11-10 20:45)
#   fade   mm: station 0's correction onto the shell's own margin key fades out behind the plane (a Gaussian of
#          this width; at 1.5 the flank's 0.2 mm of correction came off within 1 mm: an S-step across the keratin
#          band 1.3 mm behind the margin, a vertical crease under the nostril in the 55 px/mm look of 22:33)
#   band   (y, t) knots: the KERATIN BAND's back end under the nostril, for the material (c018: the grey keratin
#          ends at (1395, 660) and (1360, 706) px = (t 2.95, y -3.73) and (3.65, -6.8); behind it the lores' bristles
#          and the gape's flange): the form runs on unchanged, the feathers cover it
#                                         D1.3c fix 1's SLEEVE (the margin key grown 26 % wider with a 0.3-0.5 mm skin
#                                         all round, its top a straight line 0.7-0.8 mm under c018's) wrapped the bill
#                                         to the tomia: skirts 1.3-1.5 mm thick beside the bill down to the mouth line, a
#                                         crease and a dark gap inside them, the cere | keratin edge one plane cut: "a
#                                         hood, not the photos' saddle" (check 2). D1.3b's 12 % flare and D1.3c's none
#                                         left a thin U frame round the bill head-on (the wave 5 check, the D1.3c check)
CERE_K = 0.6                            # mm: the base's smooth union with the face. The face runs CAP_IN / LORE_IN
#                                         inside the sleeve all along the cere, and a smooth union of two surfaces that
#                                         close swells by k / 4: at k 2 the cere stood 0.5 mm fatter where the face ran
#                                         in it and stepped down where the face's front tapers away: a second and a third
#                                         arch round the bill head-on (D1.3c)
CAP_IN = 0.3                            # mm the envelope's top stays under the sleeve's top line forward of the cere's back
LORE_IN = 0.25                          # mm the envelope's half width stays inside the sleeve's over the cere
#                                         (D1.3c: 0.6 / 0.5 left the sleeve a step proud of the face all round: head-on
#                                         a second arch round the bill, the last of the "U-frame")
LORE_OUT = 0.0                          # [E: c019, c044] mm the lores' half width past the sleeve's at the cere's back
#                                         (D1.3c: 1.0 stood the lores' edge round the cere head-on)
FOREHEAD_RAMP = 3.5                     # [E: c018] mm over which the forehead's skin slopes down onto the cere, from
#                                         the cere's back forward (7 from behind it cut the crown gate's roof 3 mm)
HEAD_WIDEST = dict(above_eye=5.0, behind=14.0, ahead=10.0, max_frac=0.55)
#                                         [E: c044, c019, c022] the head's sections at the eyes are widest at the eye's
#                                         level, `above_eye` mm over its centre (ellipse_psweep's y_w), easing to the
#                                         section's middle `behind` / `ahead` mm along the axis; y_w at most max_frac of
#                                         the half height (D1.3c: the plain ellipse was widest 4.5 mm UNDER the eye's
#                                         centre, a chicken's cheeks; widest 4 mm over it the head read as a ball)
BROW = dict(over=-3.5, stand=0.6, y=7.0, y_root=7.5, yaw=18.0, pitch=3.0, back=12.0, front=18.0,
            ramp=(12.0, 11.0), bury=5.0, top=6.0, n_top=48, n_ch=192, rise=1.2, w_u=3.5, w_in=5.0, edge=2.4, k=1.0, n=137,
            smooth=1.5, key_smooth=4.0, hold_back=0.0, n_arc=73, top_sink=5.0)
#                                         (11-11 11:47 / 12:08: and its ENDS along the line buried `bury` 5.0, was 1.5;
#                                         measured along n_b, the head's side behind the eye turns away from it. With the
#                                         skull's line the front end lies on the forehead 16.5 mm before the eye's centre
#                                         (1.5: 2.0-3.5 deg per 0.1 mm step there; scratch kg.py, a height field over the
#                                         forehead) and the back end 14 mm behind it, 11 mm up: THE CRESCENT at c022
#                                         (scratch loc.py names a look's pixel on the clay; 1.5 / 3.0: folds of 16.9 deg
#                                         over 0.5 mm, 5.0 deg the largest step; 5.0: two steps of 1.7 / 2.2). The shelf
#                                         where it stands is unchanged)
#                                         (D1.3c fix 2, 11-11 11:25, the kink walk over the brow, scratchpad
#                                         d13c_fix2/kw.py: TWO CREASES OF ITS OWN, both since fix 1. (a) The section's
#                                         TOP END lay 1.0 mm under the head (1.5 where the brow fades) and turned in
#                                         there: within the smooth union's reach it creased the crown along the brow,
#                                         10.4 / 12.6 / 8.9 deg in one 0.1 mm step 15-16 mm over the globe's centre (the
#                                         arc on the forehead at c022). The top's last rows now ease down `top_sink` x
#                                         t^4 more (6 mm laterally at the end, whatever the fade: on the crown's slope
#                                         3 mm only halved it): no step over 1.5 deg there. (b) The edge's ROUND was 19
#                                         points (10 deg facets of 0.4 mm; resampling along the hull keeps a polygon's
#                                         corners): steps alternating 1.6 / 5.4 / 2.8 / 6.2 deg over it; `n_arc` 73 and
#                                         `n_ch` 192: an even 2.1-2.8 deg per 0.1 mm, the 2.4 mm round's own turning)
#                                         [M: S1 USNM 553822 dorsal (CC0), the D1.3c fix 2 skull study, Skye's call of
#                                         11-11 06:45 ("eye sockets look very strange from front")] THE BROW IS THE
#                                         SKULL'S: the bony brow (the lacrimal's supraorbital process) reaches 19.5-20.0
#                                         mm off the midline 3.5-9.5 mm before the orbit's middle, over the eye's
#                                         front-top; behind it the orbit's rim is the frontal's edge, 10-17 mm out. So the
#                                         edge stands `over` -3.5 (about 20.8 mm off the midline at the eye's centre
#                                         plane: the bone + about 1 mm of skin), its foot 7 mm over the globe's centre
#                                         (the lacrimal sits over the eye's top), fading over `back` 12 mm behind, no
#                                         hold behind the widest (hold_back 0). Fix 2's first brow (over 0.5, y 4.2, back
#                                         16, ramp 9, top 8, hold 5.5) stood 22.7-25.5 mm out, 2-4 mm past bone + skin
#                                         and 0.5 mm past the lids' widest point: a VISOR over each eye head-on (the
#                                         strange sockets). The photos' shelf over the whole eye and behind it is the
#                                         coat's (D1.6). Scratch d13c_fix2: sk1.py / sk2.py (the skull from above at the
#                                         clay's scale), snap_b1..b3 (b1: the edge inside the lids' bulge, no brow at
#                                         all over the eye and a knob at c022; b2: back 8, a horn at c022; b3 = this).
#                                         The eye's axis stays 65 deg (avian.py; the 11-11 10:4x measure is in the
#                                         round's NOTES: at c044 the axis 55 moves the cornea-seen pupil from 0.30 to
#                                         0.37 of the eye, its aspect 0.64 -> 0.75, and leaves c018's front corner 1.0
#                                         mm beyond the lid sphere)
#                                         (D1.3c fix 2, 11-10 22:40: back 12 -> 16, its ramp 5 -> 9, hold_back 7 ->
#                                         5.5: held level 7 mm behind its widest and then buried within 5 mm, the
#                                         shelf ended as a pointed HORN at the head's side at c019's camera (the GPU
#                                         look of 22:35); c019 / c022: the ridge fades into the head behind the eye)
#                                         D1.3c fix 1: over the eye the edge's widest point stands `over` past the lids'
#                                         outermost point in each node's plane, elsewhere `stand` off the head; its foot
#                                         (the lowest edge a side view sees) `y` mm over the globe's centre, at the lids'
#                                         top (c018: the brow's edge meets the upper lid's margin, 4.1-4.6 mm over the
#                                         globe's centre in the face frame). D1.3c's foot at 5.9 put the brow line 1-2 mm
#                                         over c018's, a band of upper lid lit between (the D1.3c check)
#                                         [E: c018, c044, c022; S1's skull dorsal and lateral (USNM 553822): the LACRIMAL,
#                                         a blade from the forehead's corner behind the cere, swept back and out about 35
#                                         deg over the orbit's front half and sloping about 19 deg down to its root, its
#                                         tip 18.6 mm off the midline (the bone); plan §2.4 / SPEC head.brow_overhang 3.5]
#                                         the supraorbital SHELF (D1.3c) as an EAVE: a PSWEEP on a straight line `y_root`
#                                         mm above the eye's centre and 6 mm inside it, running forward `yaw` deg medial
#                                         and `pitch` deg down in the FACE FRAME (c018's level: the brow's edge is level
#                                         over the eye, then falls toward the cere's back corner) from -back to +front
#                                         mm; each node's section an eave whose EDGE (a round of radius `edge`, its foot
#                                         `y` mm over the globe's centre) stands, over the eye, `over` past the lids'
#                                         outermost point in the node's plane (forward of the eye's widest held on the
#                                         line; elsewhere `stand` off the head), easing over `ramp` (back, front) mm to
#                                         `bury` mm under the head's surface (the probe) at the ends; from the foot over
#                                         the round and up the head's own surface `top` mm (n_top rows) the outline is
#                                         ONE CONVEX chain, the hull of the round and the head's profile (n_ch points),
#                                         so it runs into the crown with no crease, as the feathered brow does; its
#                                         UNDERSIDE rising `rise` mm over `w_u` mm inward (the soffit over the upper
#                                         lid), closed `w_in` mm inside; the per-node depths smoothed over `smooth` mm,
#                                         the keys point by point over `key_smooth` nodes; unioned with k. (D1.3c: the
#                                         edge `out` mm past the rim plane but held within `x_over` of the head's widest
#                                         half width, the top's stand eased by a cubic: a knob with a notch over it in
#                                         every section, nothing over the cap; the D1.3c check.) D1.3b's wedge stood
#                                         its edge 1 mm proud of the rim plane, under the cornea's 2 mm, its underside
#                                         DROPPING: no overhang, no shade ("round portholes with no brow shelf", the wave
#                                         5 check); the first D1.3c eave (level in the WORLD, yaw 8, a flat top 5 mm
#                                         tall) was a bar pasted over the opening from the side and a pointed brim with a
#                                         hollow over it from the front and above
GAPE_PX = np.array([(910, 719), (980, 718), (1040, 712), (1100, 705), (1150, 699), (1180, 698), (1200, 699), (1240, 703),
                    (1290, 707), (1320, 708), (1340, 706), (1370, 712), (1400, 722), (1430, 733), (1440, 735)], float)
#                                         c018, the mouth's crack from the rictus to the tomium's foot (D1.3c fix 2: read
#                                         on 10 px grids at x 6, scratchpad d13c_fix2/grid/c018_gape_back_6x.png,
#                                         c018_gape_front_6x.png; it ends on TOMIUM_PX's first point. D1.3b's seven
#                                         points stood 0.2-0.5 mm off it and ended 0.5 mm over the tomium's foot)
GAPE = dict(upper=((2.7, 0.0, 0.0), (3.8, 0.2, 0.03), (4.9, 0.76, 0.10), (6.0, 1.2, 0.17), (11.0, 1.3, 0.20),
                   (17.5, 1.5, 0.22), (22.0, 1.7, 0.22), (24.0, 1.6, 0.12), (25.5, 1.2, 0.0)),
            lower=((3.5, 0.0, 0.0), (4.9, 0.5, 0.07), (7.0, 1.1, 0.16), (10.0, 1.3, 0.18), (13.5, 1.0, 0.14),
                   (15.8, 0.4, 0.04), (17.0, 0.0, 0.0)),
            k=0.35, n=84, r_max=2.0)
#                                         [E: c018 at x 3 and x 6] the GAPE's FLANGE (D1.3c fix 2): two soft lips with
#                                         the mouth's crack between them, tapering to nothing at the corner under the
#                                         eye. Each lip's knots are (mm along the mouth line from the rictus, the lip's
#                                         height from the crack, how far it stands proud of the face); between them a
#                                         monotone cubic. c018: the UPPER lip 1.2-1.7 mm tall over x 1020-1340 (check 2,
#                                         by colour), fullest toward the bill, where it runs flush into the keratin's
#                                         base at x 1340-1363 (proud 0 there: no lump, no knob); the LOWER lip from the
#                                         corner to x 1230, fullest (1.3 mm) at x 1010-1150. Each lip is a chain of
#                                         round cones whose circle of radius (h^2 / 4 + p^2) / (2 p) is sunk so that it
#                                         stands p proud over a chord h tall (a low wide roll, not a bead), hard-
#                                         unioned in its own group, the group blended k into the head; n points along
#                                         the line. The radius is held under r_max: where a lip thins out (proud -> 0)
#                                         it keeps its roundness and its chord narrows to nothing, and each cone is
#                                         sunk along the SURFACE'S NORMAL. (The cut run's first build let the radius
#                                         grow as h^2 / 8 p: 3.7 -> 10 mm where the upper lip ran flush into the bill's
#                                         base, sunk along x: balls 5 mm across beside the bill at c019 / c044, the
#                                         first look of 11-10 20:45.) The knots' stations are check 2's reading of
#                                         c018 by colour: no flange nearer the corner than 2.7 mm, 0.2 mm tall at 3.8,
#                                         0.76 at 4.9, 1.2-1.7 from 6 to 23.4 (x 1020-1340), the lower lip over x
#                                         1000-1200. How far the lips stand proud is [E: c019, c044: a thin soft
#                                         edge to the mouth, no roll]: 0.2 mm (at 0.30-0.34 the lips were fat rolls,
#                                         a clown's smile, at c044's camera: the quick look of 11-10 21:02).
#                                         D1.3c fix 1's lip: one chain of radius 0.34-0.75 standing 0.15
#                                         proud, 0.6-1.0 mm tall over a 0.4 mm crease, "a thin raised bead", with a
#                                         lump 2.5-3.1 mm tall and a knob at the bill's base (check 2: the old cere's
#                                         skirt); D1.3b's stood 0.35 mm proud as a 2.6 mm round rod: "a thick cord"
GAPE_CREASE = (0.32, 0.28)              # [E] mm: the crack's round cone radius, its depth into the skin (a thin line)
CREASE_END = 0.5                        # mm: the crack's radius eases to nothing over this length behind the lower
#                                         bill's margin plane, where the jaw's skin ends (head_members; D1.3c fix 2.
#                                         At 1.5 the mouth's line stopped 1.5-2 mm short of the bill at c018's camera,
#                                         a healed-over corner: scratch out/c17_c018_gape_cpu.png)
NOSTRIL = dict(at=(3.0, 0.72), axis=3.0, mouth=(4.6, 3.45), lean=(48.0, 35.0), depth=6.5, taper=(0.5, 2.2, 3.4),
               out=3.4, k=0.3, ring=dict(at=(0.0, 0.0), semi=(1.61, 1.21)), pit=dict(at=(-0.2, 0.12), semi=(0.78, 0.59)),
               loop=0.45)
#                                         THE MOUTH'S OVAL LIES ON THE CERE ITSELF (11-11 04:40; head_members carries
#                                         each of its points from the tangent plane onto the cere along the normal
#                                         before the prism is drawn through them). Why: the cere falls away steeply
#                                         behind and above the nostril (1.2 mm under the mouth's tangent plane 2 mm
#                                         over the oval's top, 2.3 mm at its upper back corner), and a prism leaning
#                                         48 deg drawn through the oval ON THE TANGENT PLANE meets that fallen
#                                         surface delta x tan 48 farther back and up: the opening as cut reached 1.1
#                                         mm farther back and 0.8 mm higher than c018's at the build's camera
#                                         (scratch d13c_fix2/nz.py: x 1366..1458, y 542..598 px against the oval's
#                                         1380..1466, 557..618), and two of the face rings' own vertices beside the
#                                         cage's loop stood 0.9-1.0 mm down in it: d1_05's fold 68.2 deg there
#                                         (scratch nq.py's chart, out/c19_nostril_cage_chart.png). And at / mouth
#                                         re-read on c018's outline under the 7x grid (18 points; its box x
#                                         1388.6..1475, y 550.7..617.4 px): (3.2, 0.5) / (5.0, 3.0) -> (3.0, 0.72) /
#                                         (4.6, 3.45): the oval's box at the build's camera x 1387..1469, y 552..618;
#                                         the front end stays 0.7 mm behind the socket plane (the cage's loop needs
#                                         that room); taper from 2.5 -> 3.4 (the oval's deepest point along the axis)
#                                         lean 60 -> 48, depth 8 -> 6.5 (11-11 03:10): THE PASSAGE'S ROOF. Leaning 60
#                                         deg the passage sinks 0.5 mm per mm while it runs 0.87 mm back and up, and
#                                         behind the nostril the cere itself falls away toward the lores about as fast
#                                         (0.6 mm under the mouth's tangent plane 3 mm back, 1.7 mm at 5): the passage
#                                         ran on just UNDER THE SKIN, a roof 0.0-0.3 mm thick, for 4 mm behind the
#                                         lip. When this round's slope fix turned the flank's normal a few degrees
#                                         the roof OPENED over t 6.6-7.2 (y +1.5 .. +2.5): the outer surface there
#                                         1.2-1.7 mm lower than in the 23:01 build, the opening 1.5 mm longer with a
#                                         ragged end (scratch d13c_fix2/kw.py on c18: 73 deg in one step; roof.py).
#                                         At 48 deg it sinks 0.67 per 0.74: the roof is over 0.5 mm thick from 1 mm
#                                         behind the lip's edge and thickens (roof.py's table in the notes)
#                                         [E: c018 under a 10 px grid at x 7 (scratchpad d13c_fix2/grid/
#                                         c018_cere_flank_7x.png)] the nostril (D1.3c fix 2): ONE opening that goes IN:
#                                         a SCOOP, the nasal passage running back and up under the cere's upper lip.
#                                         c018: the mouth an oval x 1386..1472, y 549..618 px: in the upper shell's
#                                         MARGIN frame (BILL_BASE's: t mm behind the margin plane, y mm up) 5.0 mm long
#                                         from t 0.7 to 5.75, 3.0 tall from y -1.0 to +2.0, its long axis `axis` deg off
#                                         the plane's normal (front end up); its lower front a lit floor rising to the
#                                         rim, which meets the keratin's edge at the bottom front; its upper back a
#                                         dark wedge under the overhanging lip, 1.5 mm tall at the back end, nothing at
#                                         t 2.5. c019 / c044: seen from the front the nostrils are dark holes one
#                                         looks INTO: the passage runs back.
#   at     (t, y) mm: the mouth's centre in the margin frame, on the cere's surface (so it lands on c018's at the
#          build's lateral camera); mouth (long, short) mm on the cere
#   lean   (deg off the inward normal, deg from the back (along the long axis) toward the upper side): the passage's
#          axis. ONE oblique oval prism (a PSWEEP on a straight axis, its key the mouth's oval carried along the axis:
#          it cuts the cere's tangent plane in that oval): its lower front wall IS the floor, a trough ramping in at
#          90 - lean[0] deg from the surface (the taper flattens it a little); its upper back wall is undercut by the
#          same angle: the upper lip overhangs, and the floor under it is in its shadow. So the side view sees a lit
#          floor at the lower front going dark toward the upper back, one form, and no view from outside sees the
#          passage's end (`depth` mm ALONG THE AXIS: 8 sin 60 = 6.9 mm sideways against the mouth's 4 mm that way)
#   taper  (s_inf, d, from): the section's scale 1 down to `from` mm along the axis (the mouth's own reach along it,
#          so the oval at the surface is the mouth's), then s_inf + (1 - s_inf) exp(-(depth - from) / d)
#   out    mm the prism runs on OUTSIDE the surface along its axis: past the oval's own reach along the axis (mouth /
#          2 x sin lean = 1.7 mm). The cut run's first single funnel stopped 1.2 mm out with a 1.33 mm reach: its flat
#          end plane sliced the mouth's lower front: "a pipe cut on the skew" (the first look of 11-10 20:45)
#   k      mm: the carve's blend (its own SUBTRACT group: the rim's round; the lip's thin edge)
#   ring / pit  the cage's two nostril rings (avian_cage.head_ports), each an ellipse (semi axes, mm) about `at` (mm
#          along the long axis forward, toward the upper side) from the mouth's centre, cast along the cere's normal
#          from outside: both land on the FLOOR (what that view sees: one tilted plane-like trough), the ring at 0.7
#          of the mouth's oval, the pit ring inside it: the port is a height field deepening to the back and up, the
#          undercut under the lip stays the bake's.
#   loop   mm: the gap by which the cage's own loop round the nostril (the 2 x 2 block's 8 vertices) stands outside
#          the mouth's oval, measured in the passage's own shadow (avian_cage._loop_round_opening carries the grown
#          oval onto the cere along the passage's axis: outside the prism by construction, clear of the rim's 0.3 mm
#          round). The opening as cut in the curved cere (scratch d13c_fix2/no.py on the 23:01 build, in the cere's
#          normal chart): l -3.3 .. +2.5, s -1.45 .. +1.8 mm against the oval's +-2.5 / +-1.5: longer to the back and
#          higher at the upper back, where the leaning prism meets the cere's fall.
#          TRIED IN THIS ROUND, each looked at beside c018 (scratch out/c4..c8): a BOWL (a round cone lying in the
#          mouth, 0.8 deep) with a separate leaning HOLE in its upper back (3.0 x 1.5: an eyelet; 4.0 x 2.0: its edge
#          met the bowl's rim, the cage's ring fell 2 mm into it: a 3.7 deg corner, a 58 deg fold; 3.4 x 1.7 with the
#          ring moved: a 94 deg fold): two features where c018 has one, "a small grey hole in a dish"; and with the
#          cere's 0.18 mm cushion round it, a puffed ring under raking light
#                                         D1.3c fix 1: a 5.4 x 3.6 dish 0.9 deep holding a 3.9 x 2.0 rounded-box slot
#                                         whose flat floor lay 3.15 mm under the cere square to the side view: "a lit
#                                         flat-floored capsule in a dish", a raised pill at c022, a scroll at c044,
#                                         1.0 mm back and 1.2 mm up of c018's (check 2; it sat 1.6 mm back so the dish
#                                         would not open onto the shell's sunk base under the old cere's skin). D1.3c: a
#                                         dish with a ring of cones, "a pipe's end with a washer"; D1.3b: an ellipsoid
#                                         standing 0.55 mm out of the surface, "a tiny pit" (the wave 5 check). SPEC
#                                         head.nostril (3.7, 2.1) is the dark part alone.


def _u(v):
    v = np.asarray(v, np.float64)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def _arc_resample(P, n):
    P = np.asarray(P, float)
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))])
    t = np.linspace(0.0, s[-1], n)
    return np.stack([np.interp(t, s, P[:, k]) for k in range(P.shape[1])], 1)


def face_frame(chain):
    """the map c018 px -> world mm on the sagittal plane (x = 0) and its numbers: dict(px_per_mm, pitch_deg, to_w,
    to_px (its inverse, world mm -> c018 px: the build's own lateral camera), eye (c018's eye_c on the skeleton: the
    anchor), tip). The anchor is P['eye_c_L'], the VISIBLE eye's centre (D1.3c fix 1: the globe, P['eye_L'], sits
    avian.EYE_BACK behind it, so its iris lands on c018's pupil)"""
    P = chain['pos']
    eye_w, tip_w = np.asarray(P.get('eye_c_L', P['eye_L']), float), np.asarray(P['bill_tip'], float)
    # 2D (forward z, up y) on the sagittal plane
    e2, t2 = np.array([eye_w[2], eye_w[1]]), np.array([tip_w[2], tip_w[1]])
    v_px = np.array([TIP_PX[0] - EYE_PX[0], -(TIP_PX[1] - EYE_PX[1])])
    v_w = t2 - e2
    s = np.linalg.norm(v_px) / np.linalg.norm(v_w)                  # px per mm
    ang = np.arctan2(v_w[1], v_w[0]) - np.arctan2(v_px[1], v_px[0])
    c, sn = np.cos(ang), np.sin(ang)
    Rm = np.array([[c, -sn], [sn, c]])

    def to_w(px, x=0.0):
        px = np.asarray(px, float).reshape(-1, 2)
        q = np.stack([px[:, 0] - EYE_PX[0], -(px[:, 1] - EYE_PX[1])], 1) / s
        q = q @ Rm.T + e2
        return np.stack([np.full(len(q), x), q[:, 1], q[:, 0]], 1)

    def to_px(w):
        q = (np.asarray(w, float).reshape(-1, 3)[:, [2, 1]] - e2) @ Rm
        return np.stack([q[:, 0] * s + EYE_PX[0], EYE_PX[1] - q[:, 1] * s], 1)

    return dict(px_per_mm=float(s), pitch_deg=float(np.degrees(ang)), to_w=to_w, to_px=to_px, eye=eye_w, tip=tip_w)


# ----------------------------------------------------------------------------------------- the rhamphothecae
def _pair_curves(top, bot, n, sigma_mm=1.2):
    """two traced edges resampled to n stations each by normalised arc length (they share the tip), each smoothed by a
    Gaussian of sigma_mm along its arc (the trace's corners are clicks, not anatomy: unsmoothed, the centreline's
    curvature spikes past the PSWEEP band's limit)"""
    from scipy.ndimage import gaussian_filter1d
    out = []
    for c in (top, bot):
        r = _arc_resample(c, n)
        L = float(np.linalg.norm(np.diff(r, axis=0), axis=1).sum())
        sg = sigma_mm / (L / (n - 1))
        r2 = gaussian_filter1d(r, sg, axis=0, mode='nearest')
        r2[0], r2[-1] = r[0], r[-1]                               # the ends stay where they were traced
        out.append(_arc_resample(r2, n))
    return out[0], out[1]


def _tomia(u):
    """the tomia's half separation / the bill's half width at u (0 the sunk base, 1 the hook's tip): TOMIA"""
    u = np.asarray(u, float)
    return TOMIA[0] * (1.0 - _smooth((u - TOMIA[1]) / (TOMIA[2] - TOMIA[1])))


def _upper_section(w, h, wt=0.0, n=NE):
    """the upper bill's SHARP section (x lateral, v up) about its centre: an ellipse's upper arc (semi-axes w,
    A_TOP h), the two tomia (-wt, -(1 - A_TOP) h) and (wt, ...) each joined to the arc by its tangent line, the flat
    bottom between them (the palate's line over the lower bill). wt <= WT_MIN is D1.2's keel (the HOOK target): the
    tangent lines meet there. n + 2 points, counter-clockwise from the right tangent point"""
    e, k = A_TOP * h, (1.0 - A_TOP) * h
    wt = max(float(wt), WT_MIN)
    A, B = wt / w, -k / e                                         # the tangent point a: A cos a + B sin a = 1
    tt = np.arctan2(B, A) + np.arccos(1.0 / np.hypot(A, B))
    a = np.linspace(tt, np.pi - tt, n)
    return np.concatenate([np.stack([w * np.cos(a), e * np.sin(a)], 1), [[-wt, -k], [wt, -k]]])


def _smooth(x):
    x = np.clip(np.asarray(x, float), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def _bill_width(u):
    """the upper bill's half width along its length (u 0 at the base, 1 at the hook's tip): broad over the base half,
    narrowing over the hook (c019 head-on: about 0.7 of the base width at mid-length; the base as wide as the bill's
    sink ring). D1.3's near-linear taper (u ** 0.9) read as a thin spike head-on (the D1.3 check, 11-08)"""
    u = np.clip(np.asarray(u, float), 0.0, 1.0)
    return BEAK_W1 + (BEAK_W0 - BEAK_W1) * (1.0 - u ** BEAK_TAPER)


def _offset_polygon(P, t):
    """a convex closed polygon (n, 2) grown by t (n,) mm along each vertex's outward bisector (the cere's wax skin
    over the bill's base section)"""
    P = np.asarray(P, float)
    n = len(P)
    nrm = lambda e: np.stack([e[:, 1], -e[:, 0]], 1) / np.maximum(np.linalg.norm(e, axis=1, keepdims=True), 1e-12)
    area = 0.5 * np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1])
    b = nrm(P - np.roll(P, 1, axis=0)) + nrm(np.roll(P, -1, axis=0) - P)
    b = (1.0 if area > 0 else -1.0) * b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)
    return P + b * np.broadcast_to(np.asarray(t, float), (n,))[:, None]


def _ellipse_section(w, h, n=64):
    a = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    return np.stack([w * np.cos(a), 0.5 * h * np.sin(a)], 1)


def _lower_section(w, h, n=64):
    """the lower bill's section: an ellipse's lower half under a squarer top (a superellipse, LOWER_TOP_N): the
    mandible's two tomia are its top edges, closing flat under the upper's palate (D1.3b r2: the full ellipse made the
    lower SOCKET ring a slit whose tips folded the cage's bridge)"""
    a = np.linspace(0.0, 2 * np.pi, n, endpoint=False)
    c, s = np.cos(a), np.sin(a)
    e = np.where(s > 0, 2.0 / LOWER_TOP_N, 1.0)
    return np.stack([w * np.sign(c) * np.abs(c) ** e, 0.5 * h * np.sign(s) * np.abs(s) ** e], 1)


def _cut_keys(C, T, nrm, surf, M, us, u_max):
    """the target surface cut by each node's plane (D1.2's rule): surf(u, i) -> (n, 3) mm points for perimeter index i
    at stations u in [0, u_max]; us the nodes' own stations; returns keys (N, M, 2) in mm, x along nrm, y along
    t x nrm"""
    N = len(C)
    keys = []
    idx = np.arange(M)
    for j in range(N):
        t = T[j]
        b = np.cross(t, nrm[j])
        uu = np.full(M, us[j])
        for _ in range(12):
            g = (surf(uu, idx) - C[j]) @ t
            ua, ub = np.clip(uu + 1e-4, 0, u_max), np.clip(uu - 1e-4, 0, u_max)
            dg = ((surf(ua, idx) - surf(ub, idx)) @ t) / np.maximum(ua - ub, 1e-12)
            uu = np.clip(uu - g / np.where(np.abs(dg) < 1e-9, 1e-9, dg), 0.0, u_max)
        Q = surf(uu, idx) - C[j]
        keys.append(np.stack([Q @ nrm[j], Q @ b], -1))
    return np.array(keys)


def _upper_axis(chain, n_nodes=None):
    """the upper shell's construction (beak(); D1.3b r2: shared with head_members' cere sleeve): dict(C (the
    PSWEEP's centreline, mm), Tn (its tangents), nrm (lateral), us (the nodes' stations), s (arc length of the traced
    pair's middle), surf (the target surface: surf(u, i) -> point i of the section at u), M (points per section), jm
    (the MARGIN node: SINK mm along from the sunk base, where the keratin leaves the skin), frame_at)"""
    ff = face_frame(chain)
    to_w = ff['to_w']
    # ---- upper: the culmen / tomium pair -> centre = top + A_TOP (bottom - top), section height |top - bottom|
    n = 400
    Tt, Bt = _pair_curves(to_w(CULMEN_PX), to_w(TOMIUM_PX), n)
    # the base: SINK mm back along the bill's axis behind the cere margin (the shell sinks into the collar)
    ax0 = _u(Tt[8] - Tt[0] + Bt[8] - Bt[0])
    Tt = np.vstack([Tt[0] - ax0 * SINK, Tt])
    Bt = np.vstack([Bt[0] - ax0 * SINK, Bt])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(0.5 * (Tt + Bt), axis=0), axis=1))])
    u_all = s / s[-1]
    lat = np.array([1.0, 0.0, 0.0])

    def frame_at(u):
        top = np.stack([np.interp(u, u_all, Tt[:, k]) for k in range(3)], -1)
        bot = np.stack([np.interp(u, u_all, Bt[:, k]) for k in range(3)], -1)
        h = np.linalg.norm(top - bot, axis=-1)
        D = (top - bot) / np.maximum(h, 1e-9)[..., None]
        h = np.maximum(h, 0.6)                                    # the hook's last fraction: no section under 0.6 mm
        c = top - A_TOP * h[..., None] * D
        return c, D, h

    wu = _bill_width
    us = np.linspace(0.0, U_END, n_nodes or int(round(s[-1] * U_END / 0.15)) + 1)
    C, D_, h_ = frame_at(us)
    # the line through the section's MIDDLE (0.5 h, not the target's 0.4 h centre): the hook bends at about 12 mm
    # radius with the keel on the inside; at 0.4 h the inner reach (0.6 h, 8 mm) left the PSWEEP bound's curvature
    # term 0.33 and a divisor of 2.1 (D1.3)
    C = C - (0.5 - A_TOP) * h_[:, None] * D_
    from scipy.ndimage import gaussian_filter1d
    Cs_ = gaussian_filter1d(C, 2.0 / 0.15, axis=0, mode='nearest')   # the PSWEEP's own centreline: any line inside
    Cs_[0] = C[0]                                                     # the target serves (the keys are its cuts)
    # (the hook's end left where the smoothing puts it, D1.3c: re-pinned onto the traced line's last point, which the
    # 0.6 mm section floor bends, the last segment shrank to 0.08 mm and kinked: its section moved 6 mm per mm there,
    # the tip piece's divisor 9.5 and |grad| 0.11 over the whole piece)
    C = Cs_
    Tn = _u(np.gradient(C, axis=0))
    nrm = np.tile(lat, (len(C), 1))
    M = NE + 2

    def surf(u, i):
        c, D, h = frame_at(u)
        w = wu(u)
        wt = _tomia(u) * w
        out_ = np.empty((len(u), 3))
        for k in range(len(u)):
            sec = _upper_section(w[k], h[k], wt[k])
            q = sec[i[k]]
            out_[k] = c[k] + lat * q[0] + D[k] * q[1]
        return out_

    jm = int(np.argmin(np.abs(us * s[-1] - SINK)))
    return dict(C=C, Tn=Tn, nrm=nrm, us=us, s=s, surf=surf, M=M, jm=jm, frame_at=frame_at, lat=lat, ff=ff)


def _upper_grid(ax, ug):
    """the upper bill's TARGET surface on a dense grid of stations ug (beak()'s straight slabs, D1.3c): (n, M, 3) mm,
    point i of the section at each station (_upper_axis's surf); behind the base (u < 0) the base section carried
    back along the base tangent (the sunk end is a prism, so a slab's first planes cut it too)"""
    uc = np.clip(ug, 0.0, None)
    c, D, h = ax['frame_at'](uc)
    w = _bill_width(uc)
    wt = _tomia(uc) * w
    lat = ax['lat']
    S = np.empty((len(ug), ax['M'], 3))
    for k in range(len(ug)):
        sec = _upper_section(w[k], h[k], wt[k])
        S[k] = c[k][None] + sec[:, :1] * lat[None] + sec[:, 1:] * D[k][None]
    back = np.minimum(ug, 0.0) * float(ax['s'][-1])
    return S + back[:, None, None] * ax['Tn'][0][None, None]


def _plane_cuts(Sg, i_a, i_b, t_c, lat, what, step=0.15):
    """a STRAIGHT PSWEEP's nodes and keys over a target surface (D1.3c). Sg (n, M, 3) mm: the target on a grid of
    stations (point i of every station on one perimeter line); the piece's own stations i_a .. i_b; its line along
    t_c through their mean point, its node planes (normal to t_c) every `step` mm from the rearmost target point of
    its stations to the foremost: so the piece holds every target point of its stations. Each key is the target's cut
    by its node plane: per perimeter line, the station where the line crosses the plane, looked up on the line's
    stretch that runs FORWARD along t_c round the piece's own (a line that turns back against t_c, as near a hook,
    ends the stretch). Returns the nodes Pj (n_j, 3) mm, the keys (n_j, M, 2) mm (x along lat, y along t_c x lat),
    every target point's station along t_c (n, M) and the end plane's"""
    b_c = np.cross(t_c, lat)
    pr = Sg @ t_c
    s0, s1 = float(pr[i_a:i_b + 1].min()), float(pr[i_a:i_b + 1].max())
    n_j = int(np.ceil((s1 - s0) / step)) + 1
    sj = np.linspace(s0, s1, n_j)
    m_c = Sg[i_a:i_b + 1].reshape(-1, 3).mean(0)
    Pj = m_c[None] + (sj - float(m_c @ t_c))[:, None] * t_c[None]
    kp = np.empty((n_j, Sg.shape[1], 2))
    for i in range(Sg.shape[1]):
        back_ = np.flatnonzero(np.diff(pr[:, i]) <= 0.0)
        w0 = int(back_[back_ < i_a].max()) + 1 if (back_ < i_a).any() else 0
        w1 = int(back_[back_ >= i_b].min()) + 1 if (back_ >= i_b).any() else len(Sg)
        p_i = pr[w0:w1, i]
        assert w0 <= i_a and w1 > i_b and p_i[0] <= s0 and p_i[-1] >= s1, \
            f'{what}: perimeter line {i} does not cross every node plane (the target\'s grid ends short, or t_c is too steep)'
        f = np.interp(sj, p_i, np.arange(w0, w1, dtype=float))
        k0 = np.clip(np.floor(f).astype(int), w0, w1 - 2)
        fr = (f - k0)[:, None]
        pt = Sg[k0, i] * (1.0 - fr) + Sg[k0 + 1, i] * fr - Pj
        kp[:, i, 0], kp[:, i, 1] = pt @ lat, pt @ b_c
    return Pj, kp, pr, s1


def _lower_axis(chain):
    """the lower shell's construction (beak(); D1.3c: shared with head_members' LOWER COLLAR): the LOWER_TOP / CHIN pair
    0.3 mm below the upper's tomium, its base SINK mm back along the pair's axis; dict(C, Tn, nrm, keys (mm), s, w, h,
    jm (the MARGIN node, SINK mm from the sunk base), us)"""
    to_w = face_frame(chain)['to_w']
    lat = np.array([1.0, 0.0, 0.0])
    Lt, Lb = _pair_curves(to_w(LOWER_TOP_PX), to_w(CHIN_PX), 200)
    Lt = Lt + np.array([0.0, -LOWER_GAP, 0.0])
    ax1 = _u(Lt[8] - Lt[0] + Lb[8] - Lb[0])
    Lt = np.vstack([Lt[0] - ax1 * SINK, Lt])
    Lb = np.vstack([Lb[0] - ax1 * SINK, Lb])
    s2 = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(0.5 * (Lt + Lb), axis=0), axis=1))])
    u2 = s2 / s2[-1]
    us2 = np.linspace(0.0, 0.97, int(round(s2[-1] * 0.97 / 0.15)) + 1)
    top2 = np.stack([np.interp(us2, u2, Lt[:, k]) for k in range(3)], -1)
    bot2 = np.stack([np.interp(us2, u2, Lb[:, k]) for k in range(3)], -1)
    C2 = 0.5 * (top2 + bot2)
    h2 = np.maximum(np.linalg.norm(top2 - bot2, axis=1), 0.6)
    w2 = LOWER_W0 - (LOWER_W0 - LOWER_W1) * us2 ** 0.8
    Tn2 = _u(np.gradient(C2, axis=0))
    keys2 = np.array([_lower_section(w2[j], h2[j]) for j in range(len(C2))])
    jm2 = int(np.argmin(np.abs(us2 * s2[-1] - SINK)))
    return dict(C=C2, Tn=Tn2, nrm=np.tile(lat, (len(C2), 1)), keys=keys2, s=s2, w=w2, h=h2, jm=jm2, us=us2)


def beak(spec, chain, n_nodes=None):
    """the two keratin shells: dict(upper=dict(prog, C (centreline mm), base (the base section's ring points mm),
    frame), lower=...). Each a closed PSWEEP (one Program per shell), its flat base end SINK mm behind the collar's
    margin"""
    ax = _upper_axis(chain, n_nodes)
    ff = ax['ff']
    to_w = ff['to_w']
    out = {}
    C, Tn, nrm, us, s, M, lat = ax['C'], ax['Tn'], ax['nrm'], ax['us'], ax['s'], ax['M'], ax['lat']
    frame_at, wu = ax['frame_at'], _bill_width
    keys = _cut_keys(C, Tn, nrm, ax['surf'], M, us, U_END)
    cores = np.array([sdf.Program.section_core(kk * MM, RHO_K) for kk in keys])
    pu = sdf.Program()
    # in PIECES, each its own PSWEEP, hard-unioned (the min of the pieces' fields over their overlap is the target's):
    # the PSWEEP's divisor takes the WHOLE member's reach (the 13 mm deep base's 8 mm) against the hook's tight
    # curvature, and one member's divisor was 20.5 (|grad f| 0.05: D1.3); split, each piece's reach meets its own turn.
    # The bill's BODY as ONE STRAIGHT piece on the palate's line (UPPER_BODY's note): the target on a dense grid of
    # stations, the piece's ends, then each node plane's cut of the target
    UB = UPPER_BODY
    ug = np.linspace(-UB['back'], U_END, UB['n_u'])
    Sg = _upper_grid(ax, ug)
    th_b = np.radians(UB['pitch'])
    t_c = np.cos(th_b) * Tn[0] - np.sin(th_b) * np.cross(Tn[0], lat)      # the base tangent pitched down
    Pj, kp, pr, s1 = _plane_cuts(Sg, int(np.searchsorted(ug, 0.0)), int(np.searchsorted(ug, UB['stop'] * U_END)), t_c,
                                 lat, 'upper bill body')
    # (so the hard union is the target: every target point in front of the body's end plane lies in front of the
    # hook's first node plane, 0.1 mm to spare; a later hook start left a wedge of the culmen in neither)
    j_h = int(np.nonzero(us >= UPPER_TIP[0][0] * U_END - 1e-9)[0][0])
    assert float(((Sg[pr > s1] - C[j_h]) @ Tn[j_h]).min()) >= 0.1, \
        'upper bill: target points in front of the body\'s end lie behind the hook\'s first plane (UPPER_TIP / UPPER_BODY)'
    pu.psweep(Pj * MM, np.array([sdf.Program.section_core(kk * MM, RHO_K) for kk in kp]), rho=RHO_K,
              key=np.arange(len(Pj), dtype=float), normal=np.tile(lat, (len(Pj), 1)), name='rhamphotheca_upper_body',
              check=False, **pn_kw())
    # ... and the hook on the curved centreline (its sections are small against its bend)
    for a, b in UPPER_TIP:
        sel = np.nonzero((us >= a * U_END - 1e-9) & (us <= b * U_END + 1e-9))[0]
        pu.psweep(C[sel] * MM, cores[sel], rho=RHO_K, key=np.arange(len(sel), dtype=float), normal=nrm[sel],
                  name=f'rhamphotheca_upper_{a:.2f}', check=False, **pn_kw())
    # the sunk BASE stays the plane through the first node normal to the base tangent (D1.2's flat end: SINK mm behind
    # the cere's margin): the body's own first plane leans `pitch` deg off it, so its base ran up to 5 mm farther back
    # along the tomia, under the gape's skin; an exact box behind the base plane cuts that away
    hb = np.array([BEAK_W0 * TOMIA[0] + 4.0, float(frame_at(np.array([0.0]))[2][0]) + 4.0, 0.5 * UB['back'] * float(s[-1])])
    pu.roundbox((C[0] - Tn[0] * hb[2]) * MM, hb * MM, r=0.0, axes=np.column_stack([lat, np.cross(Tn[0], lat), Tn[0]]),
                op=sdf.SUBTRACT, k=0.0, name='rhamphotheca_upper_base_cut')
    # the MARGIN section: where the keratin leaves the cere (SINK mm along from the sunk base): the cage's SOCKET ring
    # lies here, on the shell (D1.3 put it on the sunk base, inside the cere's skin)
    jm = ax['jm']
    out['upper'] = dict(prog=pu, C=C, base=C[0] + keys[0][:, :1] * nrm[0] + keys[0][:, 1:] * np.cross(Tn[0], nrm[0]),
                        T0=Tn[0], h0=float(frame_at(np.array([0.0]))[2][0]), w0=float(wu(0.0)), length=float(s[-1]),
                        margin=C[jm] + keys[jm][:, :1] * nrm[jm] + keys[jm][:, 1:] * np.cross(Tn[jm], nrm[jm]),
                        Tm=Tn[jm])
    # ---- lower: LOWER_TOP / CHIN pair, ellipse sections, 0.3 mm below the upper's tomium (the shells never touch)
    la = _lower_axis(chain)
    C2, Tn2, nrm2, keys2, s2, w2, h2, jm2 = (la[k] for k in ('C', 'Tn', 'nrm', 'keys', 's', 'w', 'h', 'jm'))
    pl = sdf.Program()
    # ONE STRAIGHT piece on the shell's chord (D1.3c), its keys the target's cuts by the planes normal to the chord
    # (the upper body's rule; the target = the sections on the traced pair's middle line, carried on as a prism past
    # both ends for the first and last planes). On the curved middle line (six overlapping pieces, D1.3b) the chin's
    # first turn left H 0.4-0.5 over two pieces, |grad| p1 0.48 with the per-node divisor; the trough is near straight
    stp = float(np.linalg.norm(C2[1] - C2[0]))
    Sl = C2[:, None, :] + keys2[:, :, :1] * nrm2[:, None, :] + keys2[:, :, 1:] * np.cross(Tn2, nrm2)[:, None, :]
    n_b, n_f = 16, 8
    Sl = np.concatenate([Sl[:1] - (np.arange(n_b, 0, -1) * stp)[:, None, None] * Tn2[0][None, None], Sl,
                         Sl[-1:] + (np.arange(1, n_f + 1) * stp)[:, None, None] * Tn2[-1][None, None]])
    Pl, kl, _, _ = _plane_cuts(Sl, n_b, n_b + len(C2) - 1, _u(C2[-1] - C2[0]), lat, 'lower bill')
    pl.psweep(Pl * MM, kl * MM, rho=0.0, key=np.arange(len(Pl), dtype=float), normal=np.tile(lat, (len(Pl), 1)),
              name='rhamphotheca_lower', check=False, **pn_kw())
    # (its sunk base the plane through the first node normal to the base tangent, as the upper's; the box 12 mm deep:
    # at 2.4 its own middle plane lay 1.2 mm behind the base face, inside the gradient gate's 1.5 mm)
    hl = np.array([float(w2[0]) + 4.0, float(h2[0]) + 4.0, 6.0])
    pl.roundbox((C2[0] - Tn2[0] * hl[2]) * MM, hl * MM, r=0.0, axes=np.column_stack([lat, np.cross(Tn2[0], lat), Tn2[0]]),
                op=sdf.SUBTRACT, k=0.0, name='rhamphotheca_lower_base_cut')
    out['lower'] = dict(prog=pl, C=C2, base=C2[0] + keys2[0][:, :1] * nrm2[0] + keys2[0][:, 1:] *
                        np.cross(Tn2[0], nrm2[0]), T0=Tn2[0], h0=float(h2[0]), w0=float(w2[0]), length=float(s2[-1]),
                        margin=C2[jm2] + keys2[jm2][:, :1] * nrm2[jm2] + keys2[jm2][:, 1:] * np.cross(Tn2[jm2],
                                                                                                    nrm2[jm2]),
                        Tm=Tn2[jm2])
    out['frame'] = ff
    return out


def _bell(w, yt, yb, wt, n_arc, n_fl, n_pal):
    """the bill base's section in a node plane (x lateral, y up): an ellipse's upper arc (lateral semi-axis w, its top
    at yt, its vertical semi-axis A_TOP (yt - yb): _upper_section's rule) over two flanks, each the tangent line from
    the arc to a tomium (-+wt, yb), and the palate's line between the tomia. Counter-clockwise from the right tangent
    point, its points at FIXED shares of the arc, of each flank and of the palate: point i of one station is point i of
    the next, so the PSWEEP's blend of two keys moves a point across the surface, not along it. Returns the points
    (n_arc + 2 n_fl + n_pal, 2) and the arc's centre height"""
    h = yt - yb
    e, k = A_TOP * h, (1.0 - A_TOP) * h
    yc = yt - e
    A, B = wt / w, -k / e
    tt = np.arctan2(B, A) + np.arccos(1.0 / np.hypot(A, B))
    a = np.linspace(tt, np.pi - tt, n_arc)
    arc = np.stack([w * np.cos(a), yc + e * np.sin(a)], 1)
    v = (np.arange(n_fl) + 1.0) / n_fl
    fl_l = arc[-1][None] + v[:, None] * (np.array([-wt, yb]) - arc[-1])[None]          # down the left flank to its tomium
    u = (np.arange(n_pal) + 1.0) / (n_pal + 1.0)
    pal = np.stack([-wt + 2.0 * wt * u, np.full(n_pal, yb)], 1)
    fl_r = np.array([wt, yb])[None] + (np.arange(n_fl) / n_fl)[:, None] * (arc[0] - np.array([wt, yb]))[None]
    return np.vstack([arc, fl_l, pal, fl_r]), yc


def _ray_on_polygon(Q, c, P):
    """each point P (n, 2) carried along its ray from c onto the closed polygon Q (m, 2), star-shaped about c"""
    out = np.empty_like(P)
    E0, E1 = Q, np.roll(Q, -1, axis=0)
    dE = E1 - E0
    for i, p in enumerate(P):
        u = p - c
        u = u / np.linalg.norm(u)
        den = dE[:, 0] * u[1] - dE[:, 1] * u[0]
        with np.errstate(divide='ignore', invalid='ignore'):
            s = ((E0[:, 1] - c[1]) * u[0] - (E0[:, 0] - c[0]) * u[1]) / den
            r = (E0[:, 0] - c[0] + s * dE[:, 0]) * u[0] + (E0[:, 1] - c[1] + s * dE[:, 1]) * u[1]
        ok = (s >= -1e-9) & (s <= 1.0 + 1e-9) & (r > 0.0) & np.isfinite(r)
        out[i] = c + u * float(r[ok].min())
    return out


def _normals2(P):
    """the outward unit normals of a counter-clockwise closed polygon's vertices (its edges' normals' bisectors)"""
    e = np.roll(P, -1, axis=0) - P
    n = np.stack([e[:, 1], -e[:, 0]], 1)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    b = n + np.roll(n, 1, axis=0)
    return b / np.maximum(np.linalg.norm(b, axis=1, keepdims=True), 1e-12)


def _bill_base(spec, chain):
    """the BILL BASE with the CERE on it (D1.3c fix 2; BILL_BASE's note): the upper shell's MARGIN key (beak()'s cut
    where the keratin leaves the skin) carried back along -Tm from the margin plane as a bell section (_bell) whose
    top follows c018's outline, whose tomial edges follow the mouth line (GAPE_PX) and whose width grows to the
    face's, over SPEC head.cere, then BILL_BASE['tail'] mm more shrinking inside the face. Station 0 is carried onto
    the shell's own margin key (FLUSH: the PSWEEP's flat end is the shell's margin plane, the keratin runs on behind
    it with no step). The CERE is the wax skin: each point moved out along the section's normal by tau, which is the
    skin's thickness inside c018's edge (behind the front edge, above the lower edge along the nostril's lower rim)
    and nothing outside it, with soft ramps: a saddle. The nodes run from the back to the margin. Returns dict(C
    (nodes, mm), keys (mm, with the skin), base (without), scale, top (world points of its top line over the cere,
    back -> margin), Tm, Cm, bm, lat, t (the nodes' mm behind the plane), tau, edge (the cere's edge on the +x side,
    world mm: the front edge from the culmen down, then the lower edge back; the material's mask), flush (mm:
    station 0 off the shell's margin key))"""
    from scipy.interpolate import PchipInterpolator
    hd, BB = spec['head'], BILL_BASE
    ax = _upper_axis(chain)
    jm = ax['jm']
    Cm, Tm, lat = ax['C'][jm], ax['Tn'][jm], ax['lat']
    bm = np.cross(Tm, lat)
    key_m = _cut_keys(ax['C'][jm:jm + 1], ax['Tn'][jm:jm + 1], ax['nrm'][jm:jm + 1], ax['surf'], ax['M'],
                      ax['us'][jm:jm + 1], U_END)[0]               # (M, 2) mm: x lateral, y along bm
    to_w = ax['ff']['to_w']

    def fr(px):                                                    # c018 px -> (t, y) in the margin frame
        w_ = to_w(np.asarray(px, float).reshape(-1, 2))
        return np.column_stack([(Cm - w_) @ Tm, (w_ - Cm) @ bm])
    n_arc, n_fl, n_pal = BB['n']
    L = hd['cere'] + BB['tail'][0]
    st, fine, st2 = BB['step']
    t = np.concatenate([np.arange(0.0, fine, st), np.arange(fine, L, st2), [L]])
    # the margin section's own numbers: its top, its tomia, the arch's lateral semi-axis (least squares through the
    # arc's points about the centre the section rule gives)
    y0t, y0b, wt0 = float(key_m[:, 1].max()), float(key_m[-1, 1]), float(key_m[-1, 0])
    e0 = A_TOP * (y0t - y0b)
    arc0 = key_m[:-2]
    sy = np.sqrt(np.clip(1.0 - ((arc0[:, 1] - (y0t - e0)) / e0) ** 2, 1e-9, None))
    w0 = float((np.abs(arc0[:, 0]) * sy).sum() / (sy * sy).sum())
    # the shell's own top slope at the margin (its target's top line just in front of the plane)
    um = ax['us'][jm]
    tops = []
    for du in (0.0, 0.02):
        c, D, h = ax['frame_at'](np.array([um + du]))
        tp = c[0] + A_TOP * h[0] * D[0]
        tops.append(((Cm - tp) @ Tm, (tp - Cm) @ bm))
    s0 = float((tops[0][1] - tops[1][1]) / (tops[0][0] - tops[1][0]))
    _, s1, te = BB['top']
    yt = y0t + s0 * t + (s1 - s0) * (t - te * (1.0 - np.exp(-t / te)))
    # the tomial edge: the mouth line behind the plane (the margin key's tomia at it)
    g_ = fr(GAPE_PX)
    g_ = g_[np.argsort(g_[:, 0])]
    g_ = g_[g_[:, 0] > 0.6]
    yb = PchipInterpolator(np.concatenate([[0.0], g_[:, 0]]), np.concatenate([[y0b], g_[:, 1]]))(t)
    dW, dWt, tw, pw = BB['w']
    grow = 1.0 - np.exp(-(t / tw) ** pw)
    w, wt = w0 + dW * grow, wt0 + dWt * grow
    S, yc = [], []
    for j in range(len(t)):
        s_, c_ = _bell(w[j], yt[j], yb[j], wt[j], n_arc, n_fl, n_pal)
        S.append(s_)
        yc.append(c_)
    S, yc = np.array(S), np.array(yc)
    # FLUSH at the plane WITH THE SHELL AS IT IS BUILT (D1.3c fix 2, 11-11): station 0 carried, along its own rays
    # from the arch's centre, onto the upper shell's ZERO SET in the margin plane (bisection on beak()'s program), the
    # difference fading out behind it. (It was carried onto key_m, the TARGET's cut by this plane, whose flank is one
    # straight chord from the arch to the tomium. The shell's body is a straight PSWEEP whose own node planes lean
    # 24 deg off this one (UPPER_BODY): its flank is ruled by chords lying in THOSE planes, and its trace in this
    # plane bows up to 0.055 mm inside key_m's chord: the head's surface stood 51-56 um proud of the shell along the
    # flank and 28 um shy near the tomium, a hairline step at the plane in every close view; scratch d13c_fix2/
    # bs.py and logs/bs_c15.txt)
    from scipy.ndimage import gaussian_filter1d
    c00 = np.array([0.0, yc[0]])
    ray0 = S[0] - c00[None]
    r0_ = np.linalg.norm(ray0, axis=1)
    ray0 /= r0_[:, None]
    shell = beak(spec, chain)['upper']['prog']
    dir0 = ray0[:, :1] * lat[None] + ray0[:, 1:] * bm[None]

    def shell_r(off):
        """the shell's surface along station 0's rays in the plane `off` mm in front of the margin's"""
        o_w = Cm + off * Tm + c00[0] * lat + c00[1] * bm
        lo_, hi_ = np.zeros(len(r0_)), r0_ + 1.5
        for _ in range(44):
            mid = 0.5 * (lo_ + hi_)
            f_ = shell.eval((o_w[None] + mid[:, None] * dir0) * MM)
            lo_, hi_ = np.where(f_ < 0, mid, lo_), np.where(f_ < 0, hi_, mid)
        return 0.5 * (lo_ + hi_)
    r_sh = shell_r(0.0)
    S = S + ((r_sh - r0_)[:, None] * ray0)[None] * np.exp(-(t / BB['fade']) ** 2)[:, None, None]
    # ... and CONTINUOUS IN SLOPE there (BILL_BASE['c1']): the shell's own radial slope along each ray, read off its
    # surface `d_c` mm in FRONT of the plane; the base's own slope read off its second station; the difference added
    # as a term linear in t that dies out over `tau_c` mm
    d_c, tau_c = BB['c1']
    r_on = lambda Q_: np.einsum('ij,ij->i', _ray_on_polygon(Q_, c00, S[0]) - c00[None], ray0)
    mu = gaussian_filter1d((r_sh - shell_r(d_c)) / d_c - (r_on(S[1]) - r_on(S[0])) / (t[1] - t[0]), 2.0, mode='wrap')
    for j in range(1, len(t)):
        ray = S[j] - c00[None]
        ray /= np.linalg.norm(ray, axis=1, keepdims=True)
        S[j] = S[j] + (mu * t[j] * np.exp(-(t[j] / tau_c) ** 2))[:, None] * ray
    base = S.copy()
    # the CERE's wax skin in the chart (t, sg): sg each point's distance round the section from the culmen
    i_top = n_arc // 2
    M = S.shape[1]
    tau = np.zeros(S.shape[:2])
    fr_s, fr_t = np.array(BB['front']).T
    t_a, y_a, sl = BB['low']
    r_f, r_l, t_l0, t_l1, r_l1 = BB['lip']
    e_a, e_R, e_c, e_s = BB['edge']
    is_arc = np.arange(M) < n_arc
    is_pal = (np.arange(M) >= n_arc + n_fl - 1) & (np.arange(M) <= n_arc + n_fl + n_pal)   # the tomia and the palate
    c_a, c_y, c_sl, c_s, c_t0, c_t1 = BB['cushion']
    sg_all = np.zeros(S.shape[:2])
    # (the front edge a smooth curve through its knots, 11-11: straight between them it turned 17 deg at sg 2.2)
    fr_c = PchipInterpolator(fr_s, fr_t)
    fr_of = lambda s_: fr_c(np.clip(s_, fr_s[0], fr_s[-1]))
    for j in range(len(t)):
        P = S[j]
        ds = np.linalg.norm(np.diff(np.vstack([P, P[:1]]), axis=0), axis=1)
        cs = np.concatenate([[0.0], np.cumsum(ds)])[:-1]
        sg = np.abs(cs - cs[i_top])
        sg = np.minimum(sg, cs[-1] + ds[-1] - sg)
        sg_all[j] = sg
        d_f = t[j] - fr_of(sg)                                     # behind the front edge
        h_l = (P[:, 1] - (y_a + sl * (t[j] - t_a))) / np.hypot(1.0, sl)   # over the lower edge
        rl = r_l + (r_l1 - r_l) * _smooth((t[j] - t_l0) / (t_l1 - t_l0))
        full = BB['skin'][1] + (BB['skin'][0] - BB['skin'][1]) * np.exp(-(sg / BB['skin'][2]) ** 2) + \
            c_a * np.exp(-((P[:, 1] - (c_y + c_sl * t[j])) / c_s) ** 2) * _smooth((t[j] - c_t0) / (c_t1 - c_t0)) * \
            (1.0 - _smooth((t[j] - t_l0) / (t_l1 - t_l0)))
        w_cu = np.exp(-(sg / e_s) ** 2)                            # 1 at the culmen: BILL_BASE's `edge`
        rise = w_cu * _smooth(d_f / e_c) + (1.0 - w_cu) * (e_a * _smooth(d_f / r_f) + (1.0 - e_a) * _smooth(d_f / e_R))
        tau[j] = np.where(is_pal, 0.0, full * rise * _smooth(np.where(is_arc, 1e9, h_l) / rl))
        S[j] = P + tau[j][:, None] * _normals2(P)
    # (the tail's shrink eased in and out, D1.3c fix 2: a straight ramp from the cere's back turned the member's own
    # surface about 40 deg there: a hard ring across the forehead at the cere's back, 12-18 deg per 0.1 mm step 6 mm
    # off the midline, in fix 1 and in this round's first builds alike: scratch kw.py)
    sc = 1.0 - (1.0 - BB['tail'][1]) * _smooth((t - hd['cere']) / (L - hd['cere']))
    C = Cm[None] - t[:, None] * Tm[None]
    on = t <= hd['cere'] + 1e-9
    top = C[on] + (S[on, i_top, 1] * sc[on])[:, None] * bm[None]
    # the cere's EDGE on the +x side (the half-way line of the skin's ramps), for the material's mask (D1.6): the
    # +x side's points run from the culmen (i_top) back to index 0, then down the right flank from the last index
    idx = np.concatenate([np.arange(i_top, -1, -1), np.arange(M - 1, n_arc + n_fl + n_pal - 1, -1)])
    edge = []
    t_meet = 0.0                                                    # where the front edge meets the lower edge
    for sg_k in np.linspace(0.0, fr_s[-1], 80):
        t_meet = float(fr_of(sg_k)) + 0.5 * r_f
        # (between the two stations round t_meet, 11-11: at the nearest station the edge stepped +-0.04 mm, a torn
        # line in the 55 px/mm previews)
        j = int(np.clip(np.searchsorted(t, t_meet) - 1, 0, len(t) - 2))
        f_ = (t_meet - t[j]) / (t[j + 1] - t[j])
        q = np.array([(1.0 - f_) * np.interp(sg_k, sg_all[j][idx], S[j][idx, k_]) +
                      f_ * np.interp(sg_k, sg_all[j + 1][idx], S[j + 1][idx, k_]) for k_ in range(2)])
        if q[1] < y_a + sl * (t_meet - t_a):
            break
        edge.append(Cm - t_meet * Tm + q[0] * lat + q[1] * bm)
    n_front = len(edge)                                             # the front edge's points; the lower edge's follow
    fl_i = idx[i_top + 1:]                                          # the +x flank, top -> the tomium
    for j in np.nonzero((t >= t_meet) & on)[0][::3]:
        y_e = y_a + sl * (t[j] - t_a) + 0.5 * (r_l + (r_l1 - r_l) * _smooth((t[j] - t_l0) / (t_l1 - t_l0)))
        yy = S[j][fl_i, 1]
        if y_e < yy.min() or y_e > yy.max():
            continue
        edge.append(C[j] + float(np.interp(-y_e, -yy, S[j][fl_i, 0])) * lat + y_e * bm)
    # station 0 against the SHELL AS BUILT: the shell's own field at its points (mm; 0 = on the shell's surface. It
    # was measured against the margin key, which the shell's surface leaves by up to 0.055 mm: see FLUSH above)
    f0_ = shell.eval((Cm[None] + base[0][:, :1] * lat[None] + base[0][:, 1:] * bm[None]) * MM) / MM
    o_ = np.arange(len(t))[::-1]                                    # the PSWEEP's nodes: the back -> the margin
    return dict(C=C[o_], keys=S[o_], base=base[o_], scale=sc[o_], top=top[::-1], Tm=Tm, Cm=Cm, bm=bm, lat=lat, t=t[o_],
                tau=tau[o_], edge=np.array(edge), n_front=n_front, flush=float(np.abs(f0_).max()), fr=fr)


def _lower_collar(chain):
    """the LOWER COLLAR (D1.3c): the jaw's skin round the lower shell's base, as the cere sleeve is round the upper's:
    the lower shell's MARGIN key + LOWER_COLLAR skin[0] at its margin plane (the flat PSWEEP end: the chin's skin steps
    0.3 mm onto the keratin there), carried back LOWER_COLLAR['length'] mm along -Tm, its half width and its depth
    below growing by `grow` and its skin to skin[1] (the jaw's rami spread behind the bill; c018: the chin's feathers
    end at the lower bill's base). Returns dict(C (nodes back -> margin, mm), keys (mm), lat, Tm, Cm)"""
    la = _lower_axis(chain)
    jm = la['jm']
    Cm, Tm = la['C'][jm], la['Tn'][jm]
    lat = np.array([1.0, 0.0, 0.0])
    LC = LOWER_COLLAR
    tc = np.linspace(LC['length'], 0.0, LC['n'])
    f = _smooth(tc / LC['length'])
    km = la['keys'][jm]
    keys = []
    for j in range(len(tc)):
        k_ = km * np.array([(km[:, 0].max() + LC['grow'][0] * f[j]) / km[:, 0].max(), 1.0])
        k_ = k_ + np.column_stack([np.zeros(len(k_)), np.where(k_[:, 1] < 0, -LC['grow'][1] * f[j] *
                                                                (-k_[:, 1] / max(-k_[:, 1].min(), 1e-9)), 0.0)])
        keys.append(_offset_polygon(k_, np.full(len(k_), LC['skin'][0] + (LC['skin'][1] - LC['skin'][0]) * f[j])))
    return dict(C=Cm[None] - tc[:, None] * Tm[None], keys=np.array(keys), lat=lat, Tm=Tm, Cm=Cm)


def _surface_along(prog, o, d, t_hi=30.0, it=40):
    """the distance (mm) from o (inside prog's solid) along d to its surface, by bisection; o (n, 3), d (3,) or (n, 3)"""
    o = np.atleast_2d(np.asarray(o, float))
    d = np.broadcast_to(np.asarray(d, float), o.shape)
    lo, hi = np.zeros(len(o)), np.full(len(o), t_hi)
    for _ in range(it):
        mid = 0.5 * (lo + hi)
        f = prog.eval((o + d * mid[:, None]) * MM)
        lo = np.where(f < 0, mid, lo)
        hi = np.where(f < 0, hi, mid)
    return 0.5 * (lo + hi)


def _eye_opening(ff, c_cap, R_c, R_l, d, up_f, sg):
    """the LIDS' OPENING of one eye (D1.3c fix 1): c018's outline EYE_OPEN_PX, closed and smoothed (a periodic cubic
    through its points, LID['n'] points by arc length), each point carried from the face frame's sagittal plane out
    along x onto the LID's surface (the sphere round the cap's centre c_cap of radius R_l: so the build's lateral camera
    sees the margin on c018's), then read in the eye's frame (X forward, Y up, both normal to the axis d). A PRISM along
    d carves it (a PSWEEP with one key on a straight line: its divisor 1, an exact distance), from 1 mm under the cap's
    sphere (R_c) at the outline's reach to well outside the skin. Returns dict(P (the prism's nodes, mm), key (its
    section, mm: x along `normal`, y along d x normal), normal, X, Y (the outline in the eye's frame, mm), Xe, Ye,
    r_max, poly (the margin's world points, mm))"""
    from scipy.interpolate import CubicSpline
    yz = ff['to_w'](EYE_OPEN_PX)[:, 1:]
    Q = np.vstack([yz, yz[:1]])
    s = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(Q, axis=0), axis=1))])
    cs = CubicSpline(s, Q, bc_type='periodic')
    q = cs(np.linspace(0.0, s[-1], 8 * LID['n'], endpoint=False))
    q = _arc_resample(np.vstack([q, q[:1]]), LID['n'] + 1)[:-1]
    r2 = R_l ** 2 - (q[:, 0] - c_cap[1]) ** 2 - (q[:, 1] - c_cap[2]) ** 2
    W = np.column_stack([c_cap[0] + sg * np.sqrt(np.maximum(r2, 0.0)), q[:, 0], q[:, 1]])
    Ye = _u(up_f - d * float(up_f @ d))
    Xe = np.cross(Ye, d)
    Xe = Xe if Xe[2] > 0 else -Xe
    X, Y = (W - c_cap) @ Xe, (W - c_cap) @ Ye
    # (c018's front corner lies 11.3 mm before the globe's centre: at the edge of the eye seen from the side, the 65 deg
    # axis turning the globe's front away from the camera. The outline is held LID['reach'] inside the cap's sphere
    # in the eye's frame, so the cap fills the whole opening: the front corner up to 1.7 mm short of c018's)
    r_ = np.hypot(X, Y)
    f_ = np.minimum(1.0, (R_c - LID['reach']) / np.maximum(r_, 1e-9))
    X, Y = X * f_, Y * f_
    W = c_cap[None] + X[:, None] * Xe[None] + Y[:, None] * Ye[None] + \
        np.sqrt(np.maximum(R_l ** 2 - X ** 2 - Y ** 2, 0.0))[:, None] * d[None]
    sgn = 1.0 if float(np.cross(d, Xe) @ Ye) > 0 else -1.0
    r_max = float(np.hypot(X, Y).max())
    z0 = float(np.sqrt(max(R_c ** 2 - r_max ** 2, 0.0))) - 1.0
    z1 = R_l + 8.0
    P = c_cap[None] + np.linspace(z0, z1, 3)[:, None] * d[None]
    # the BALL's own prism: the outline grown LID['under'] (the eye's ball runs that far under the margin), its floor
    # 0.5 mm under the opening's
    XYg = _offset_polygon(np.column_stack([X, Y]), np.full(len(X), LID['under']))
    Pg = c_cap[None] + np.linspace(z0 - 0.5, z1, 3)[:, None] * d[None]
    return dict(P=P, key=np.column_stack([X, sgn * Y]), normal=Xe, X=X, Y=Y, Xe=Xe, Ye=Ye, r_max=r_max, poly=W,
                P_cap=Pg, key_cap=np.column_stack([XYg[:, 0], sgn * XYg[:, 1]]))


# ----------------------------------------------------------------------------------------- the head's skin
def head_members(prog, spec, chain, k_blend=3.0):
    """add the head's skin members to prog (one group: the envelope, eyes, lids, brows, cere, gape folds, round-blended
    by k_blend mm) and return the landmarks (world mm) the cage and the gates read"""
    ff = face_frame(chain)
    to_w = ff['to_w']
    P = chain['pos']
    hd = spec['head']
    pl = hd['plumage']
    eyeL = np.asarray(P['eye_L'], float)
    edir = _u(P['eye_dir_L'])
    r_eye = 0.5 * hd['eye']
    # the envelope's centreline: the occiput -> the cere's middle, its sections from CROWN less the plumage
    crown_w = to_w(CROWN_PX)
    occ = np.asarray(P['occiput'], float)
    cere_mid = 0.5 * (to_w([CERE_PX['back_top']])[0] + to_w([CERE_PX['front_foot']])[0])
    # the axis: occiput (a little forward of it, the round's centre) to the cere's middle, lowered toward the jaw line
    # the back end BURIED in the neck (PSWEEP's ends are flat: D1.3 saw the back face's rim as a line across the
    # nape): it starts behind and below the occiput, its first sections tapered inside the neck's radius (BACK_TAPER)
    a0 = occ + np.array([0.0, -9.0, -2.0])
    # ... ending INSIDE the cere collar, 3 mm behind the bill's base section's centre, its last sections tapered to
    # fit in the collar (D1.3: PSWEEP's ends are flat planes; ended at the cere's back the envelope left a flat wall
    # with the collar and the bill floating in front of it)
    cf_, tom0_ = to_w([CERE_PX['front_top']])[0], to_w([TOMIUM_PX[0]])[0]
    h0_ = float(np.linalg.norm(cf_ - tom0_))
    D0_ = _u(cf_ - tom0_)
    c0_ = cf_ - A_TOP * h0_ * D0_
    T0_ = _u(np.cross(np.array([1.0, 0.0, 0.0]), D0_))
    T0_ = T0_ if T0_[2] > 0 else -T0_
    a1 = c0_ - T0_ * 3.0
    n_ax = 48
    tt = np.linspace(0.0, 1.0, n_ax)
    C = a0[None] + tt[:, None] * (a1 - a0)[None]
    fwd = _u(a1 - a0)
    up = _u(np.cross(fwd, np.array([1.0, 0.0, 0.0])) * -1.0)
    if up[1] < 0:
        up = -up
    # the top: the CROWN trace less the plumage, its height above the axis at each station (interpolated in the
    # axis's forward coordinate)
    fz = (crown_w - a0) @ fwd
    fy = (crown_w - a0) @ up - pl
    order = np.argsort(fz)
    top = np.interp((C - a0) @ fwd, fz[order], fy[order])
    # the bottom: the gape line (c018: the tomium's foot -> the rictus, carried flat behind it) less CHIN mm of jaw
    # and throat skin [E] (D1.3: the first rule sat above the gape line, so the gape fold stood out as a rod)
    ric = to_w([RICTUS_PX])[0]
    gz = np.array([(ric - a0) @ fwd, (tom0_ - a0) @ fwd])
    gy = np.array([(ric - a0) @ up, (tom0_ - a0) @ up])
    sz = (C - a0) @ fwd
    gape_h = np.interp(sz, gz, gy)
    chin = np.interp(tt, [0.0, 0.7, 1.0], [CHIN[0], CHIN[0], CHIN[1]])
    bot = gape_h - chin
    # at the eyes the head is as wide as the globes less EYE_PROUD: only the cornea's cap and the lids stand out (c040,
    # c019: the eye sits nearly flush under the brow); the stations' forward positions from the eye's own
    t_eye = float(np.clip(((eyeL - a0) @ fwd) / np.linalg.norm(a1 - a0), 0.3, 0.8))
    # ... and that width held forward over the globe's front half (D1.3 probe: 6 mm before the eye centre the
    # envelope was 15 mm wide against the globe's 22.5, so the globe's whole front stood free: goggles), then the
    # lores' V to the cere
    L_ax = float(np.linalg.norm(a1 - a0))
    t_front = min(t_eye + (r_eye * edir[2] + 2.0) / L_ax, 0.9)
    # the half width whose ellipse passes EYE_PROUD inside the globe's lateral pole AT THE EYE'S HEIGHT (D1.3 set the
    # ellipse's widest point there, but the eye sits above the section's centre, so the skin at the eye's height was
    # 2-3 mm narrower and the globes stood out as discs: goggles, the D1.3 check)
    t_e = (eyeL - a0) @ fwd / L_ax
    yc_e = float(np.interp(t_e, tt, 0.5 * (top + bot)))
    hh_e = float(np.interp(t_e, tt, 0.5 * (top - bot)))
    dy_e = (eyeL - a0) @ up - yc_e
    # (D1.3c) the section at the eye is widest at the brows' root, HEAD_WIDEST['above_eye'] over the eye's centre: the
    # half width that puts the skin at the eye's height through the lower half ellipse there
    yw_e = float(np.clip(dy_e + HEAD_WIDEST['above_eye'], -0.4 * hh_e, HEAD_WIDEST['max_frac'] * hh_e))
    w_eye = (eyeL[0] + r_eye * edir[0] - EYE_PROUD) / np.sqrt(max(1.0 - ((yw_e - dy_e) / (hh_e + yw_e)) ** 2, 0.3))
    # the BILL BASE with the cere on it (D1.3c fix 2: _bill_base; D1.3b r2's sleeve), first: the lores and the forehead
    # are shaped onto it
    sleeve = _bill_base(spec, chain)
    tz, ty = (sleeve['top'] - a0) @ fwd, (sleeve['top'] - a0) @ up
    o_ = np.argsort(tz)
    sz_ = (C - a0) @ fwd
    sx_ = (sleeve['C'] - a0) @ fwd
    # (the base's ARCH half width, its first BILL_BASE['n'][0] points: D1.3c fix 2. The whole key's widest points are
    # the TOMIA, 0.2-0.5 mm wider than the arch: held to those, the envelope's ellipse stood 0.3-0.5 mm OUT of the
    # base's flanks over the cere's back half (sections 6 and 8 mm behind the margin, scratch sx.py): the cere's own
    # skin buried there and a crease down its flank where the two surfaces crossed)
    shw_ = np.abs(sleeve['keys'][:, :BILL_BASE['n'][0], 0]).max(1) * sleeve['scale']
    o2_ = np.argsort(sx_)
    t_cb = float(np.clip(tz.min() / L_ax, t_front + 0.05, 0.97))      # the cere's back
    # the LORES: one V from the eye's front (t_front) to the cere's back, there LORE_OUT wider than the sleeve (r2: the
    # old knot HALF_W['lore'] 6 mm before the eye's front dropped the width 20 -> 12.5 there, and a parallel-sided
    # muzzle 9.5 mm a side ran on 12 mm to the cere: a hood on a snout, beside c019's straight V)
    hw = np.interp(tt, [0.0, 0.18, t_eye, t_front, t_cb, 1.0],
                   [HALF_W['occiput'], HALF_W['brain'], w_eye, w_eye - 3.0,
                    float(np.interp(tz.min(), sx_[o2_], shw_[o2_])) + LORE_OUT, BEAK_W0 + 1.5])
    d_end = (1.0 - tt) * float(np.linalg.norm(a1 - a0))
    # the forehead onto the sleeve: forward of the cere's back the envelope's top stays CAP_IN under the sleeve's top
    # line, and over the cere's back FOREHEAD_RAMP mm it ramps up to the crown (c018: the forehead's skin slopes down
    # onto the cere; a step cap left a wall across the head at the cere's back, a dome over a collar). Forward of the
    # cere's back only: the skull roof behind it is the crown gate's
    cap = np.interp(sz_, tz[o_], ty[o_]) - CAP_IN
    ramp = np.clip((tz.min() + FOREHEAD_RAMP - sz_) / FOREHEAD_RAMP, 0.0, 1.0)
    top = np.minimum(top, cap + (top - cap).clip(0.0) * ramp ** 1.5)
    # ... and flush with the cere's flanks: from 3 mm behind the cere's back forward, the half width no less than the
    # sleeve's less LORE_IN (r2: the face 1-3 mm narrower than the sleeve left the cere a hood standing off it)
    w_c = _smooth((sz_ - (tz.min() - 3.0)) / 3.0) * (sz_ <= sx_.max())
    hw = hw + w_c * (np.maximum(hw, np.interp(sz_, sx_[o2_], shw_[o2_]) - LORE_IN) - hw)
    # the back end inside the neck: the section eased to a BACK_TAPER-radius circle about the axis over the first
    # 15 % (the occiput's round is the taper)
    wb = np.clip(tt / 0.15, 0.0, 1.0) ** 0.5
    top = BACK_TAPER + (top - BACK_TAPER) * wb
    bot = -BACK_TAPER + (bot + BACK_TAPER) * wb
    hw = BACK_TAPER + (hw - BACK_TAPER) * wb
    # the front end inside the shells: over FRONT_TAPER the half width to the lower bill's base less 1 mm
    wf = _smooth(np.clip(d_end / FRONT_TAPER, 0.0, 1.0))         # (a smoothstep: a power under 1 has an infinite
    #                                                               slope at the end, and the PSWEEP's divisor follows it)
    hw = np.minimum(hw, (LOWER_W0 - 1.0) + (hw - (LOWER_W0 - 1.0)) * wf)
    from scipy.ndimage import gaussian_filter1d
    top = gaussian_filter1d(top, ENV_SMOOTH[0], mode='nearest')   # the crown trace's clicks: creases across the
    bot = gaussian_filter1d(bot, ENV_SMOOTH[0], mode='nearest')   # crown (D1.3 head render), 2 stations = ~3 mm
    hw = gaussian_filter1d(hw, ENV_SMOOTH[1], mode='nearest')     # (1.0: the eye-to-lore taper set two pieces'
    #                                                               divisors to 1.81, |grad| 0.55)
    # (the cap again after the smoothing: the Gaussian carried the forehead's ramp 1.5 mm over the sleeve's top, r2)
    top = np.minimum(top, cap + (top - cap).clip(0.0) * ramp ** 1.5)
    # ... and the half width again (D1.3c fix 2): over the cere it stays LORE_IN inside the base's arch (the Gaussian
    # carried the lores' width 6 mm forward over the cere's back half), the hold let go over 3 mm behind the cere's back
    hw = np.where(sz_ <= sx_.max(), np.minimum(hw, np.interp(sz_, sx_[o2_], shw_[o2_]) - LORE_IN +
                                               20.0 * _smooth((tz.min() - sz_) / 3.0)), hw)
    # the front end sunk all round (ENV_FRONT_SINK's note): its flat end plane out of the smooth unions' reach
    fs_ = ENV_FRONT_SINK[0] * (1.0 - _smooth(d_end / ENV_FRONT_SINK[1]))
    top, bot, hw = top - fs_, bot + fs_, hw - fs_
    centre_off = 0.5 * (top + bot)
    half_h = 0.5 * (top - bot)
    # the WIDEST LEVEL of each section (D1.3c, ellipse_psweep's y_w): at the eyes the brows' root, easing to the
    # section's middle over HEAD_WIDEST['behind'] / ['ahead'] mm along the axis (c044 head-on: the brows' edges are the
    # face's widest; the plain ellipse, widest 4.5 mm under the eye's centre, receded 6 mm over the eye's top and left
    # the brow shelf nothing to stand on)
    s_ax = tt * L_ax - t_e * L_ax
    win = _smooth((s_ax + HEAD_WIDEST['behind']) / HEAD_WIDEST['behind']) * \
        _smooth((HEAD_WIDEST['ahead'] - s_ax) / HEAD_WIDEST['ahead'])
    y_w = np.clip((((eyeL - a0) @ up) + HEAD_WIDEST['above_eye'] - centre_off) * win, -0.4 * half_h,
                  HEAD_WIDEST['max_frac'] * half_h)
    Cs = C + up[None] * centre_off[:, None]
    # the CAGE's centreline (returned as 'centre': the spine's face rings are cast from it): the middle of the VISIBLE
    # section, whose bottom in front of the lower bill's margin is the mouth line (CHIN_CUT removes the chin there).
    # On the envelope's own middle the last face rings sat 1-2 mm low and folded a quad into a dart at the mouth's
    # corner (D1.3b r2)
    low_m = 0.5 * (to_w([LOWER_TOP_PX[0]])[0] + to_w([CHIN_PX[0]])[0])
    d_low = float((a1 - low_m) @ fwd)
    y_low = float((to_w([LOWER_TOP_PX[0]])[0] - a0) @ up)
    wl = _smooth(np.clip((d_end - d_low) / 0.8, 0.0, 1.0))
    Cc_ = C + up[None] * (0.5 * (top + np.maximum(bot, y_low + (bot - y_low) * wl)))[:, None]
    r0 = hw
    aspect = half_h / hw
    nrm = np.tile([1.0, 0.0, 0.0], (n_ax, 1))
    prog.begin_group(op=sdf.UNION, k=k_blend * MM)
    from ..families.avian_body import ellipse_psweep            # exact ellipses (SWEEP's aspect is no bound)
    # THE STATIONS BETWEEN THE NODES (ENV_DENSE; D1.3c fix 2): each profile (centre line, half width, half height,
    # widest level) carried to ENV_DENSE[0] stations per node and smoothed along the axis, so no key meets the next at
    # an angle; the pieces keep their 3-node overlap in mm (ellipse_psweep's lap)
    k_d = ENV_DENSE[0]
    t_d = np.linspace(0.0, n_ax - 1.0, k_d * (n_ax - 1) + 1)

    def dense(v):
        v = np.asarray(v, float)
        w_ = v.reshape(n_ax, -1)
        o_d = np.stack([np.interp(t_d, np.arange(n_ax), w_[:, c_]) for c_ in range(w_.shape[1])], 1)
        return gaussian_filter1d(o_d, ENV_DENSE[1] * k_d, axis=0, mode='nearest').reshape((len(t_d),) + v.shape[1:])
    Cs, r0, hh0, y_w = dense(Cs), dense(r0), dense(r0 * aspect), dense(y_w)
    env_kw = dict(pieces=HEAD_PIECES, n=ENV_N, straight=True, axis=fwd, y_w=y_w, lap=3 * k_d)
    ellipse_psweep(prog, Cs, [1.0, 0.0, 0.0], r0, hh0, op=sdf.UNION, k=0.0, name='head_envelope', **env_kw)
    # the LIDS and the periorbital skin ON THE GLOBE (D1.3c fix 2, the lead's call 2; LID's note): LID['thick'] over
    # the eye's ball (SPEC's globe about the eye joint, with the cornea's dome on it: the skin rides over the dome),
    # smooth-unioned LID['fair'] with the envelope: in the head's group, and in the probes (the brow, the gape and the
    # nostril are placed on the surface as it is with the lids). The cornea: CORNEA's note
    a_k = 0.5 * CORNEA['base']
    z_l = float(np.sqrt(r_eye ** 2 - a_k ** 2))                    # the limbus' plane, mm from the globe's centre
    R_k = (a_k ** 2 + CORNEA['sag'] ** 2) / (2.0 * CORNEA['sag'])  # the cornea's radius; its centre z_k along the axis
    z_k = z_l + CORNEA['sag'] - R_k

    def add_lids(p):
        for sg_, sd_ in ((1.0, 'L'), (-1.0, 'R')):
            m_ = np.array([sg_, 1.0, 1.0])
            p.ellipsoid(eyeL * m_ * MM, np.full(3, (r_eye + LID['thick']) * MM), op=sdf.UNION, k=LID['fair'] * MM,
                        name=f'lid_skin_{sd_}')
            p.ellipsoid((eyeL + edir * z_k) * m_ * MM, np.full(3, (R_k + LID['thick']) * MM), op=sdf.UNION,
                        k=LID['fair'] * MM, name=f'lid_cornea_{sd_}')
    add_lids(prog)
    # a probe of the envelope + lids alone: the gape line and the nostril are placed on ITS surface (D1.3 put the
    # gape fold at a fixed x = 9 mm, 6-10 mm inside the head's side: buried, so the mouth stopped at the bill)
    probe = sdf.Program()
    ellipse_psweep(probe, Cs, [1.0, 0.0, 0.0], r0, hh0, op=sdf.UNION, k=0.0, name='probe', **env_kw)
    add_lids(probe)
    cb, cf = to_w([CERE_PX['back_top']])[0], to_w([CERE_PX['front_top']])[0]
    foot = to_w([CERE_PX['front_foot']])[0]
    tom0 = to_w([TOMIUM_PX[0]])[0]
    h0 = float(np.linalg.norm(cf - tom0))
    D0 = _u(cf - tom0)
    c0 = cf - A_TOP * h0 * D0                                     # the bill's base section centre (beak()'s rule)
    T0 = _u(np.cross(np.array([1.0, 0.0, 0.0]), D0))              # forward, normal to the section
    if T0[2] < 0:
        T0 = -T0
    # the CERE (for the probe too: the nostril sits on it): the bill base with its wax skin (_bill_base)
    Cc, cere_keys = sleeve['C'], sleeve['keys']
    nrm_c = np.tile(sleeve['lat'], (len(Cc), 1))

    def add_cere(p, k_, name='cere'):
        # the keys as they are (rho 0: the arc's 0.15 mm edges leave no room for a core offset)
        p.psweep(Cc * MM, cere_keys * MM, rho=0.0, key=np.arange(len(Cc), dtype=float), scale=sleeve['scale'],
                 normal=nrm_c, op=sdf.UNION, k=k_, name=name, check=False, **pn_kw())
    add_cere(probe, CERE_K * MM)
    collar = _lower_collar(chain)                                  # the jaw's skin round the lower bill's base

    def add_collar(p):
        p.psweep(collar['C'] * MM, collar['keys'] * MM, rho=0.0, key=np.arange(len(collar['C']), dtype=float),
                 normal=np.tile(collar['lat'], (len(collar['C']), 1)), op=sdf.UNION, k=LOWER_COLLAR['k'] * MM,
                 name='lower_collar', check=False, **pn_kw())
    add_collar(probe)
    # ... and a FAIRED probe for the mouth line alone: the same members, the cere blended 2 mm. Between the cere's
    # tomial corner and the lower collar the true surface has the mouth's own hollow, and the line's last points,
    # looked up on it, fell 4-5 mm into the corner: a notch at the bill's base (D1.3c, with CERE_K)
    probe_m = sdf.Program()
    ellipse_psweep(probe_m, Cs, [1.0, 0.0, 0.0], r0, hh0, op=sdf.UNION, k=0.0, name='probe', **env_kw)
    add_lids(probe_m)
    add_cere(probe_m, 2.0 * MM)
    add_collar(probe_m)

    def surf_x(y_z, sg, x_in=2.0, p=None):
        """a probe's surface x (signed by sg) at each (world y, z): bisection along x from x_in mm"""
        p = probe if p is None else p
        y_z = np.atleast_2d(y_z)
        lo = np.full(len(y_z), x_in)
        hi = np.full(len(y_z), 45.0)
        for _ in range(40):
            mid = 0.5 * (lo + hi)
            f = p.eval(np.column_stack([sg * mid, y_z[:, 0], y_z[:, 1]]) * MM)
            lo = np.where(f < 0, mid, lo)
            hi = np.where(f < 0, hi, mid)
        return sg * 0.5 * (lo + hi)

    # the mouth line, rictus -> the tomium's foot: a cubic through the trace by its arc length (the trace's clicks are
    # corners), GAPE['n'] points; and its unit normal in the sagittal plane, up (the lips stand off it)
    from scipy.interpolate import CubicSpline, PchipInterpolator
    s_px = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(GAPE_PX, axis=0), axis=1))])
    gape_w = to_w(CubicSpline(s_px, GAPE_PX)(np.linspace(0.0, s_px[-1], GAPE['n'])))
    s_g = np.concatenate([[0.0], np.cumsum(np.linalg.norm(np.diff(gape_w, axis=0), axis=1))])
    tg_ = np.gradient(gape_w[:, 1:], axis=0)
    tg_ /= np.linalg.norm(tg_, axis=1, keepdims=True)
    up_g = np.stack([tg_[:, 1], -tg_[:, 0]], 1)                   # (y, z): the tangent turned a quarter
    up_g *= np.sign(up_g[:, :1])
    tint_cere, tint_gape = sdf.Program(), sdf.Program()           # the bare parts alone (the previews' yellow)
    add_cere(tint_cere, 0.0)
    # the FACE FRAME's axes in the world (c018's level and up: face_frame's rotation)
    a_f = np.radians(ff['pitch_deg'])
    lat_f, up_f, fwd_f = np.array([1.0, 0.0, 0.0]), np.array([0.0, np.cos(a_f), -np.sin(a_f)]), \
        np.array([0.0, np.sin(a_f), np.cos(a_f)])
    # the nostril's mouth centre on the sagittal plane: NOSTRIL['at'] in the upper shell's margin frame (c018's
    # reading; D1.3c fix 1 carried the traced point 1.6 mm back to keep the dish off the shell's sunk base: 1.0 mm
    # back and 1.2 mm up of c018's, check 2)
    nos_w = sleeve['Cm'] - NOSTRIL['at'][0] * sleeve['Tm'] + NOSTRIL['at'][1] * sleeve['bm']
    sub = []
    brows = []
    ridges = []
    caps = {}
    for sg, sd in ((1.0, 'L'), (-1.0, 'R')):
        e = eyeL * np.array([sg, 1.0, 1.0])
        d = edir * np.array([sg, 1.0, 1.0])
        # the EYE (D1.3c fix 2, the lead's call 2): SPEC's globe at the eye joint; the lids are the head's skin lying on
        # it (add_lids, above); the LID OPENING: c018's own outline (EYE_OPEN_PX) placed on the lid's sphere and carved
        # along the eye's axis (_eye_opening: fix 1's); in it the eye's BALL, the globe with the CORNEA's dome on it
        # (the EYE set's parts replace this surface: plan §4.7). caps: c / R the globe, R_lid the lid's sphere, rim a
        # point of the limbus' plane on the axis, cornea (centre, radius), apex (the dome's top)
        R_l = r_eye + LID['thick']
        op_ = _eye_opening(ff, e, r_eye, R_l, d, up_f, sg)
        sub.append(('opening', sd, op_))
        sub.append(('cap', sd, (e, r_eye, e + d * z_k, R_k, op_)))
        caps[sd] = dict(c=e, R=r_eye, R_lid=R_l, rim=e + d * z_l, r_cut=op_['r_max'] + LID['cut'], poly=op_['poly'],
                        X=op_['X'], Y=op_['Y'], z_r=z_l, cornea=(e + d * z_k, R_k), apex=e + d * (z_l + CORNEA['sag']))
        # the BROW: the supraorbital SHELF (plan §2.4: the raptor glare; a bony process under skin and short feathers):
        # an EAVE PSWEEP on a straight line above the eye (BROW's note). Its frame: n_b out (level, `yaw` deg forward of
        # the bird's lateral), t_b forward along the head's side and `pitch` deg down, b_up across them (up)
        from scipy.ndimage import gaussian_filter1d
        ya, pb = np.radians(BROW['yaw']), np.radians(BROW['pitch'])
        # (level and up are the FACE FRAME's, c018's own: the bind's head is pitched ff['pitch_deg'] against the photo,
        # and a shelf level in the world ran down toward the bill beside c018's)
        n_b = sg * np.cos(ya) * lat_f + np.sin(ya) * fwd_f
        t_b = np.cos(pb) * (-sg * np.sin(ya) * lat_f + np.cos(ya) * fwd_f) - np.sin(pb) * up_f
        b_up = sg * np.cross(t_b, n_b)
        sb = np.linspace(-BROW['back'], BROW['front'], BROW['n'])
        o_b = e[None] - 6.0 * n_b[None] + sb[:, None] * t_b[None] + BROW['y_root'] * b_up[None]
        dz = (sb[1] - sb[0])
        sm_ = lambda v: gaussian_filter1d(v, BROW['smooth'] / dz, mode='nearest')
        y_e = BROW['y'] - BROW['y_root']                          # the edge's FOOT height on the line's frame
        r_e, n_top = BROW['edge'], BROW['n_top']
        y_c = y_e + r_e                                            # the edge's round's centre (its widest point's) height
        t_k = np.linspace(0.0, 1.0, n_top + 1)                    # up the head over the round, its centre's height up
        bump = _smooth((sb + BROW['back']) / BROW['ramp'][0]) * _smooth((BROW['front'] - sb) / BROW['ramp'][1])
        # the top's reach per node: `top` where the shelf stands, 0.4 of it at its buried ends (the forehead is low at
        # the cere's back: a full reach there started over the head, a notch on the crown's midline)
        top_j = BROW['top'] * (0.4 + 0.6 * bump)
        # the head's surface at the edge's widest point's height and up the head over it (each cast from inside it)
        z_s = sm_(_surface_along(probe, o_b + y_c * b_up[None], n_b))
        rows = [o_b + (y_c + t_ * top_j)[:, None] * b_up[None] for t_ in t_k]
        assert all((probe.eval(r_ * MM) < 0.0).all() for r_ in rows), 'brow: a top station starts outside the head'
        z_h = np.stack([sm_(_surface_along(probe, r_, n_b)) for r_ in rows], 1)
        # THE EDGE OVER THE EYE (D1.3c fix 1): where the shelf is over the eye its widest point stands BROW['over']
        # past the LID's outermost point in the node's plane (the lid sphere's support along n_b), so it overhangs the
        # eye and shades it (c018: the brow's edge meets the lids' top; c044: the eyes sit under the brows); forward of
        # the eye's widest the edge runs on parallel to the shelf's line (the lacrimal's blade, the lores falling away
        # under it); behind the eye it follows the lid round and sinks into the head (bump); elsewhere it stands
        # BROW['stand'] off the head. D1.3c held the edge 0.3 mm past the head's widest half width (x_over): the cap
        # stood 0.3-0.7 mm past it at the eye's centre plane, so nothing overhung it (the check's sections, k11)
        cl = caps[sd]
        hc = (cl['c'][None] - o_b) @ t_b                                 # the lid sphere's centre off each node's plane
        z_eye = (cl['c'][None] - o_b) @ n_b + np.sqrt(np.maximum(cl['R_lid'] ** 2 - hc ** 2, 0.0)) + BROW['over']
        w_c = _smooth((cl['r_cut'] - np.abs(hc)) / 3.0)                  # over the eye (its opening's reach)
        i_p = int(np.argmax(np.where(w_c > 0.5, z_eye, -np.inf)))
        hold = np.where(np.arange(len(sb)) > i_p, z_eye[i_p], z_eye)    # forward of its widest: on the shelf's line
        # ... and BEHIND its widest too, for BROW['hold_back'] mm, then eased onto the lid's outline over 4 mm (D1.3c
        # fix 2: following the lid sphere's outline from the eye's centre back, the shelf stood level with the eye
        # 3 mm behind the centre and was gone at 6: check 2; c018 / c022: it runs back past the eye's back corner)
        hold = hold + (z_eye[i_p] - hold) * _smooth((sb - (sb[i_p] - BROW['hold_back'] - 4.0)) / 4.0)
        z_t = w_c * hold + (1.0 - w_c) * (z_s + BROW['stand'])
        ov = sm_(-BROW['bury'] + bump * (np.maximum(z_t - z_s, BROW['stand']) + BROW['bury']))
        ov0 = float(ov.max())
        z_e = z_s + ov
        Lz = float(np.mean(z_s)) - 2.0                              # the PSWEEP's line, inside the head
        Pb = o_b + n_b[None] * Lz
        from scipy.spatial import ConvexHull
        th_r = np.linspace(-0.5 * np.pi, 0.5 * np.pi, BROW['n_arc'])  # the edge's round, foot -> widest -> its top
        keys_b = []
        for j in range(len(sb)):
            # the section's outline, point by point (rho 0): from the edge's FOOT (the soffit's outer end) over its
            # ROUND and up the TOP to the head's own surface `top_j` over the round's centre, as ONE CONVEX chain (the
            # hull of the round and the head's profile, set 0.3 -> 1 mm inside the surface going up; the buried ends
            # `bury` under it), resampled to BROW['n_ch'] points; the inner closing point; the SOFFIT's inner end,
            # rising `rise` over w_u. D1.3c's top eased the stand off the head by a cubic, (1 - t)^3 where the shelf
            # stood out: a concave notch over a round knob in every section, "flat brims" head-on (the D1.3c check);
            # the builder's hull ran 9 mm up the forehead over the lores, where the shelf then stood 3-4 mm off (here
            # it stands BROW['stand'] there)
            f_ = float(np.clip(ov[j] / ov0, 0.0, 1.0))
            arc = np.stack([z_e[j] - r_e + r_e * np.cos(th_r), y_c + r_e * np.sin(th_r)], 1)
            # (the top's last rows ease down BROW['top_sink'] x t^4 more, out of the smooth union's reach: BROW's note)
            prof = np.stack([z_h[j] - ((1.0 - f_) * BROW['bury'] + f_ * (0.3 + 0.7 * t_k) + BROW['top_sink'] * t_k ** 4),
                             y_c + t_k * top_j[j]], 1)
            pts = np.vstack([arc, prof, [[min(arc[:, 0].min(), prof[:, 0].min()) - 8.0, y_c]]])
            hv = list(ConvexHull(pts).vertices)                     # counter-clockwise
            i_f, i_t = 0, len(arc) + len(prof) - 1                  # the foot, the top's end
            assert i_f in hv and i_t in hv, 'brow: the foot or the top\'s end is off the section\'s hull'
            hv = hv[hv.index(i_f):] + hv[:hv.index(i_f)]
            chain = _arc_resample(pts[hv[:hv.index(i_t) + 1]], BROW['n_ch'])
            x_u = z_e[j] - r_e - BROW['w_u']
            y_u = y_e + BROW['rise'] * bump[j] - 1.5 * (1.0 - bump[j])
            x_i = min(chain[-1, 0], x_u, z_s[j]) - BROW['w_in']
            keys_b.append((np.vstack([chain, [[x_i, y_c + 0.5 * top_j[j]], [x_u, y_u]]]) -
                           np.array([Lz, 0.0])) * MM)
        # (point by point along the shelf, over BROW['key_smooth'] nodes: the hull's tangent point steps from one
        # profile row to the next, and the keys' linear blend between nodes read as terraces across the brow head-on)
        keys_b = gaussian_filter1d(np.array(keys_b), BROW['key_smooth'], axis=0, mode='nearest')
        if sg < 0:                                                  # mirrored: run it back to front (the frame's y,
            Pb, keys_b = Pb[::-1], keys_b[::-1]                     # t_b x n_b, stays up)
        # (added AFTER the openings' carve, below: the lid opening's dish, r_open round the eye's axis, cut the shelf's
        # edge away wherever it overhung the opening, the whole point of it; D1.3c)
        brows.append((Pb, keys_b, n_b, sd))
        # the GAPE: the mouth line from the rictus (under the eye's front, c018) to the tomium's foot, ON the head's
        # side: a crease (SUBTRACT, below) along it and the FLANGE's two lips, over and under it (GAPE's note): each
        # lip's centre line stands half its height off the crack, on the faired probe's surface, sunk so its circle
        # stands `p` proud over a chord `h` tall
        xs = surf_x(gape_w[:, 1:], sg, p=probe_m)
        G = gape_w.copy()
        G[:, 0] = xs
        for nm_l, sgn_l in (('upper', 1.0), ('lower', -1.0)):
            kn = np.array(GAPE[nm_l])
            h_l = np.clip(PchipInterpolator(kn[:, 0], kn[:, 1], extrapolate=False)(s_g), 0.0, None)
            p_l = np.clip(PchipInterpolator(kn[:, 0], kn[:, 2], extrapolate=False)(s_g), 0.0, None)
            on = np.nan_to_num(p_l) > 0.03
            if on.sum() < 2:
                continue
            h_l, p_l = h_l[on], p_l[on]
            # the roll's radius from its chord and its stand, held under r_max; the chord it then shows; its centre
            # line half that chord off the crack on the faired probe's surface, sunk along that surface's normal
            r_l = np.minimum((0.25 * h_l ** 2 + p_l ** 2) / (2.0 * p_l), GAPE['r_max'])
            h_e = 2.0 * np.sqrt(np.maximum(2.0 * r_l * p_l - p_l ** 2, 0.0))
            yz = gape_w[on, 1:] + sgn_l * 0.5 * h_e[:, None] * up_g[on]
            # (the UPPER lip on the TRUE surface (the probe with the cere as it is, D1.3c fix 2): its centre line runs
            # over the mouth line, on the bill base's own flank, which is there to stand on. On the faired probe (the
            # cere blended 2 mm: fatter than the head by up to 1 mm round the base's tomial corner) the lip's last 3
            # mm stood 1.0-1.6 mm out and 2.5 mm tall: "a lump at the bill" (check 2; scratch gp.py on c9: relief
            # 0.99 / 1.28 / 1.65 mm at x 1290 / 1330 / 1370 against 0.67-0.71 over x 1040-1220). The LOWER lip and
            # the crease stay on the faired probe: under the line the true surface is the mouth's own hollow)
            p_lip = probe if nm_l == 'upper' else probe_m
            Ps = np.column_stack([surf_x(yz, sg, p=p_lip), yz])
            Gl = Ps - _u(p_lip.normals(Ps * MM)) * (r_l - p_l)[:, None]
            # (its own group after the head's, hard-unioned in itself: as members of the head's group each cone blended
            # with the cones before it, a beaded line; D1.3c)
            ridges.append((f'gape_{nm_l}_{sd}', Gl, r_l, GAPE['k']))
            for i in range(len(Gl) - 1):
                tint_gape.roundcone(Gl[i] * MM, Gl[i + 1] * MM, (r_l[i] + 0.3) * MM, (r_l[i + 1] + 0.3) * MM,
                                    op=sdf.UNION, k=0.0, name=f'gape_{nm_l}_{sd}_{i}')
        Gc = G.copy()
        Gc[:, 0] = G[:, 0] + sg * (GAPE_CREASE[0] - GAPE_CREASE[1])
        sub.append(('crease', sd, Gc))
        # the NOSTRIL (D1.3c fix 2; NOSTRIL's note): its mouth's centre on the cere at c018's place (on the probe's
        # surface out along x from the sagittal point, so the build's lateral camera sees it on c018's), the frame on
        # the cere there (the surface's normal, the long axis along the bill's base, the short axis toward the upper
        # side) and the FUNNEL's axis into the head, leaning back and up under the upper lip
        xn = float(surf_x(nos_w[None, 1:], sg)[0])
        Pn = np.array([xn, nos_w[1], nos_w[2]])
        h_ = 0.05
        n_s = _u(np.array([(probe.eval(((Pn + np.eye(3)[k] * h_) * MM)[None])[0] -
                            probe.eval(((Pn - np.eye(3)[k] * h_) * MM)[None])[0]) for k in range(3)]))
        ax_n = np.radians(NOSTRIL['axis'])
        l_0 = np.cos(ax_n) * sleeve['Tm'] + np.sin(ax_n) * sleeve['bm']
        l_ax = _u(l_0 - n_s * float(n_s @ l_0))                    # forward along the bill's base, on the cere
        s_up = _u(np.cross(n_s, l_ax))
        if s_up[1] < 0:
            s_up = -s_up
        th_n, ph_n = np.radians(NOSTRIL['lean'])
        a_in = -np.cos(th_n) * n_s + np.sin(th_n) * (-np.cos(ph_n) * l_ax + np.sin(ph_n) * s_up)
        sub.append(('nostril', sd, (Pn, n_s, l_ax, s_up, a_in)))
    add_cere(prog, CERE_K * MM)
    add_collar(prog)
    prog.end_group()
    # the low RIDGES on the head's surface (the gape's flesh, the nostrils' rims): each a chain of round cones hard-
    # unioned in its own group, the group blended into the head
    for nm_, Pr_, rr_, k_ in ridges:
        prog.begin_group(op=sdf.UNION, k=k_ * MM)
        for i in range(len(Pr_) - 1):
            prog.roundcone(Pr_[i] * MM, Pr_[i + 1] * MM, rr_[i] * MM, rr_[i + 1] * MM, op=sdf.UNION, k=0.0,
                           name=f'{nm_}_{i}')
        prog.end_group()
    # (the LIDS' skin is in the head's own group now: add_lids. D1.3c fix 1 raised a lid sphere here in the opening's
    # outline grown 2 mm, its own group: "the lid zone a raised ring", check 2)
    # the chin's end at the lower bill's margin plane (CHIN_CUT): the lower trace's start and axis as beak() takes them;
    # its own SUBTRACT group, blended CHIN_CUT_K (D1.3c fix 1: in the openings' group, k 0.35, its edge was a crease
    # across the jaw under the bill)
    prog.begin_group(op=sdf.SUBTRACT, k=CHIN_CUT_K * MM)
    Lt_, Lb_ = _pair_curves(to_w(LOWER_TOP_PX), to_w(CHIN_PX), 200)
    Lt_ = Lt_ + np.array([0.0, -LOWER_GAP, 0.0])
    f_b = _u(Lt_[8] - Lt_[0] + Lb_[8] - Lb_[0])
    lat_b = np.array([1.0, 0.0, 0.0])
    u_b = _u(np.cross(f_b, lat_b))
    m_c = 0.5 * (Lt_[0] + Lb_[0])
    top_b = float((Lt_[0] - m_c) @ u_b) + CHIN_CUT[3]
    prog.roundbox((m_c + f_b * CHIN_CUT[2] + u_b * (top_b - CHIN_CUT[1])) * MM, np.array(CHIN_CUT[:3]) * MM, r=0.3 * MM,
                  axes=np.column_stack([lat_b, u_b, f_b]), op=sdf.UNION, k=0.0, name='chin_end')
    prog.end_group()
    # the BILL BASE ONCE MORE, hard-unioned after the chin's cut (D1.3c fix 2, 11-11): the cut's box ends the JAW's skin
    # at the lower bill's margin plane, its top 0.2 mm over the lower bill's top edge and its blend 1 mm: that reached
    # the UPPER base's tomial edge too and ate it back 0.5-0.75 mm for its last 2 mm (the skin's outer surface at the
    # mouth line's height stopped 2 mm short of the margin plane; scratch d13c_fix2, the table of 02:05): a notch
    # between the shell's tomium and the head's own tomial edge, the "ledge" and "foot" under the keratin band at
    # c019's / c044's cameras, and the hollow the cage's commissure fell into. The base's own surface is already the
    # skin wherever nothing was cut (a hard union of a surface with itself changes nothing): this only puts back what
    # the chin's cut took, so the tomial edge runs crisp to the plane and meets the shell's
    prog.begin_group(op=sdf.UNION, k=0.0)
    add_cere(prog, 0.0, name='cere_after_chin_cut')
    prog.end_group()
    # the mouth's crease (a SUBTRACT group: carved after the head's union). It ENDS WHERE THE JAW'S SKIN ENDS (11-11):
    # its radius eases to nothing over CREASE_END mm behind the lower bill's margin plane. In front of that plane
    # there is no lower lip to make a crease with, only the upper base's tomial edge over the lower shell; carried on
    # to the tomium's foot the cones cut a 0.28 mm groove into that edge right up to the upper shell
    prog.begin_group(op=sdf.SUBTRACT, k=0.35 * MM)
    for kind, sd, P_ in sub:
        if kind == 'crease':
            r_c = GAPE_CREASE[0] * _smooth(((m_c[None] - P_) @ f_b) / CREASE_END)
            for i in range(len(P_) - 1):
                if max(r_c[i], r_c[i + 1]) > 0.03:
                    prog.roundcone(P_[i] * MM, P_[i + 1] * MM, max(r_c[i], 0.02) * MM, max(r_c[i + 1], 0.02) * MM,
                                   op=sdf.UNION, k=0.0, name=f'gape_crease_{sd}_{i}')
    prog.end_group()
    # the NOSTRILS (their own SUBTRACT group, its blend the rim's round; NOSTRIL's note): each ONE SCOOP, an oblique
    # oval prism on a straight leaning axis (a PSWEEP: an exact 2D distance over its divisor, a bound: d1_03's bound
    # gate; iq's ellipsoids over-read the carved air by 0.4-0.6 mm, D1.3c). Its key is the mouth's oval on the cere
    # carried along the axis onto the plane normal to it, so the prism cuts the cere's tangent plane in that oval;
    # its nodes run OUT along the axis from its end to NOSTRIL['out'] mm outside the surface (past the oval's own
    # reach along the axis: the flat end plane must stand clear of the mouth)
    prog.begin_group(op=sdf.SUBTRACT, k=NOSTRIL['k'] * MM)
    for kind, sd, P_ in sub:
        if kind == 'nostril':
            Pn, n_s, l_ax, s_up, a_in = P_
            lg, sh = NOSTRIL['mouth']
            a_o = np.linspace(0.0, 2.0 * np.pi, 96, endpoint=False)
            Q_ = (0.5 * lg * np.cos(a_o))[:, None] * l_ax[None] + (0.5 * sh * np.sin(a_o))[:, None] * s_up[None]
            # ... each point carried from the tangent plane ONTO THE CERE along its normal (bisection on the probe, the
            # surface the mouth's centre was found on): the prism is drawn through the oval where the cere really is,
            # so the opening it cuts is that oval however the cere curves and however the passage leans (NOSTRIL's
            # note: drawn through the tangent plane's oval it cut 1.1 mm farther back and 0.8 mm higher)
            lo_n, hi_n = np.full(len(Q_), -1.5), np.full(len(Q_), 4.0)       # mm under the tangent plane
            for _ in range(40):
                mid_n = 0.5 * (lo_n + hi_n)
                out_n = probe.eval((Pn[None] + Q_ - mid_n[:, None] * n_s[None]) * MM) > 0.0
                lo_n = np.where(out_n, mid_n, lo_n)
                hi_n = np.where(out_n, hi_n, mid_n)
            Q_ = Q_ - (0.5 * (lo_n + hi_n))[:, None] * n_s[None]
            e1 = _u(l_ax - a_in * float(l_ax @ a_in))
            e2 = np.cross(-a_in, e1)
            oval = np.column_stack([Q_ @ e1, Q_ @ e2])
            r_out, r_in = float(-(Q_ @ a_in).min()), float((Q_ @ a_in).max())     # the oval's reach along the axis, mm
            assert NOSTRIL['out'] >= r_out + 1.0 and NOSTRIL['taper'][2] >= r_in, \
                f'nostril: the prism\'s end plane or its taper cuts the mouth (the oval reaches {r_out:.2f} mm out ' \
                f'and {r_in:.2f} mm in along the axis)'
            s_inf, d_t, t_0 = NOSTRIL['taper']
            dn = np.concatenate([np.linspace(NOSTRIL['depth'], 0.0, 33), -np.linspace(0.0, NOSTRIL['out'], 5)[1:]])
            sc_n = np.where(dn > t_0, s_inf + (1.0 - s_inf) * np.exp(-np.maximum(dn - t_0, 0.0) / d_t), 1.0)
            prog.psweep((Pn[None] + dn[:, None] * a_in[None]) * MM, oval * MM, rho=0.0, key=0.0, scale=sc_n,
                        normal=np.tile(e1, (len(dn), 1)), op=sdf.UNION, k=0.0, name=f'nostril_{sd}')
    prog.end_group()
    # the HOLLOW at each eye's front corner (LID['canthus']; D1.3c fix 2): a round cone whose first sphere touches the
    # lid's sphere from outside at the opening's foremost point, running forward and out, subtracted with a wide
    # blend, before the opening's own carve
    r_ca, k_ca, l_ca, h_ca, r_cb = LID['canthus']
    prog.begin_group(op=sdf.SUBTRACT, k=k_ca * MM)
    for kind, sd, P_ in sub:
        if kind == 'opening':
            cl_ = caps[sd]
            n_c = _u(P_['poly'][int(np.argmax(P_['X']))] - cl_['c'])
            A_ca = cl_['c'] + n_c * (cl_['R_lid'] + r_ca)
            d_ca = _u(cl_['rim'] - cl_['c'])                         # the eye's axis
            prog.roundcone(A_ca * MM, (A_ca + l_ca * P_['Xe'] + h_ca * d_ca) * MM, r_ca * MM, r_cb * MM, op=sdf.UNION,
                           k=0.0, name=f'canthus_{sd}')
    prog.end_group()
    # the LIDS' OPENINGS (D1.3c fix 1): each c018's outline as a prism along the eye's axis (_eye_opening), carved out
    # of the head's skin, which is the lids round it; a group of their own, its blend LID['k'] the margin's round
    prog.begin_group(op=sdf.SUBTRACT, k=LID['k'] * MM)
    for kind, sd, P_ in sub:
        if kind == 'opening':
            prog.psweep(P_['P'] * MM, P_['key'] * MM, rho=0.0, key=0.0, normal=np.tile(P_['normal'], (len(P_['P']), 1)),
                        op=sdf.UNION, k=0.0, name=f'lid_opening_{sd}')
    prog.end_group()
    # the BROWS over the carved openings (one group: each eave hard-unioned, the group blended into the head by k)
    prog.begin_group(op=sdf.UNION, k=BROW['k'] * MM)
    for Pb, keys_b, n_b, sd in brows:
        prog.psweep(Pb * MM, keys_b, rho=0.0, key=np.arange(len(Pb), dtype=float),
                    normal=np.tile(n_b, (len(Pb), 1)), op=sdf.UNION, k=0.0, name=f'brow_{sd}', **pn_kw())
    prog.end_group()
    # the eyes' BALLS in their openings (the EYE set's cornea and iris replace this surface: plan §4.7; D1.3c fix 2,
    # the lead's call 2): SPEC's globe about the eye joint with the CORNEA's dome on it (a smaller sphere, blended
    # CORNEA['k']: the limbus' furrow), cut to the opening's prism grown LID['under'] (the ball runs that far under
    # the margin and down to the carve's floor), its own group so the cut stays local. (D1.3c fix 1: one flat sphere
    # of radius 11.0 whose top lay 1.25 mm inside the globe's own sphere: "a flat lens", check 2)
    for kind, sd, P_ in sub:
        if kind == 'cap':
            c_, R_, c_k, R_kk, op_ = P_
            prog.begin_group(op=sdf.UNION, k=LID_K * MM)
            prog.ellipsoid(c_ * MM, np.full(3, R_ * MM), op=sdf.UNION, k=0.0, name=f'eye_globe_{sd}')
            prog.ellipsoid(c_k * MM, np.full(3, R_kk * MM), op=sdf.UNION, k=CORNEA['k'] * MM, name=f'eye_cornea_{sd}')
            prog.psweep(op_['P_cap'] * MM, op_['key_cap'] * MM, rho=0.0, key=0.0,
                        normal=np.tile(op_['normal'], (len(op_['P_cap']), 1)), op=sdf.INTERSECT, k=0.0,
                        name=f'eye_cap_cut_{sd}')
            prog.end_group()
    return dict(axis=(a0, a1), centre=Cc_, fwd=fwd, collar=(c0_, T0_), eye=eyeL, eye_dir=edir, r_eye=r_eye,
                caps=caps, probe=probe, brows=brows,
                # (cere['edge']: the cere | keratin edge on the +x side, world mm, the front edge from the culmen down then
                # the lower edge back (mirror it for -x): in front of and under it the head's own surface is KERATIN by
                # material, the band under the nostril; cere['flush']: the shell's own field at station 0's points, mm)
                # (cere['n_front']: the edge's first points are the FRONT edge, culmen -> the nostril's lower front, the
                # rest the LOWER edge going back; cere['band']: BILL_BASE's band, the keratin band's back end under the
                # nostril as (y, t) knots in the margin frame (Cm, Tm, bm): keratin = in front of the front edge, or
                # under the lower edge and in front of the band's back end)
                cere=dict(back=cb, front=cf, foot=foot, c0=c0, T0=T0, D0=D0, keys=cere_keys, C=Cc, edge=sleeve['edge'],
                          n_front=sleeve['n_front'], band=BILL_BASE['band'],
                          flush=sleeve['flush'], Cm=sleeve['Cm'], Tm=sleeve['Tm'], bm=sleeve['bm']),
                # (the NOSTRILS, L then R. 'nostril': a point 1.2 mm down each funnel's axis; 'nostril_frame': that point,
                # the axis outward, the long axis, the third axis; 'nostril_traced': the mouth's centre on the cere
                # (c018's reading); 'nostril_dish': the mouth's centre, the cere's normal there, the long axis
                # (forward), the short axis (toward the upper side); 'nostril_size': the mouth's oval and the funnel's
                # section 2.5 mm in, mm; 'nostril_ring' / 'nostril_pit': the cage's two rings, NOSTRIL's note)
                nostril=[p[0] + 1.2 * p[4] for k_, s_, p in sub if k_ == 'nostril'],
                nostril_traced=[p[0] for k_, s_, p in sub if k_ == 'nostril'],
                nostril_frame=[(p[0] + 1.2 * p[4], -p[4], p[2], _u(np.cross(-p[4], p[2])))
                               for k_, s_, p in sub if k_ == 'nostril'], gape=[p for k_, s_, p in sub if k_ == 'crease'],
                nostril_dish=[(p[0], p[1], p[2], p[3]) for k_, s_, p in sub if k_ == 'nostril'],
                nostril_size=(NOSTRIL['mouth'], tuple(NOSTRIL['taper'][0] * np.asarray(NOSTRIL['mouth']))),
                nostril_ring=NOSTRIL['ring'], nostril_pit=NOSTRIL['pit'], nostril_loop=NOSTRIL['loop'],
                r_open=0.5 * hd['iris'] + 2.0, tint=dict(cere=tint_cere, gape=tint_gape), rictus=to_w([RICTUS_PX], x=9.0)[0], crown=crown_w, frame=ff)
