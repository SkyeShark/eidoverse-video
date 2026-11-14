"""HORN PRESETS: the data of the horn generator (forge/families/horn.py; work/bestiary/research/DEER_PLAN.md §5,
DEER_CRITIC.md §1b; the build's notes work/bestiary/deer/horns/build_NOTES.md). One row per donor; a family is a
BUILDER NAME ('antler', 'spiral', 'cone') plus rows of measured numbers, so a new horn is data, never code.

UNITS: LIFE MILLIMETRES and degrees, the donor's own size; `U_native` is the donor's skull length, so the generator
sizes a part by the host's skull (plan §5.8: isometric by default, scale = U_host / U_native).

THE PART FRAME (every direction below): z the root axis (the port ring's Z: out of the head along the pedicle or the
horn core), x the FRONT (the side the tines leave from; a spiral's first curl), y = z cross x, which is OUTWARD
(lateral) on the LEFT part. The right part is the left mirrored (y -> -y), as data. `launch` puts the part frame in the
host's head axes at rest (+Y up, +Z forward, +X the host's left): on another host the skull record supplies it.

TAGS holds each leaf's source in the deer plan's legend: [P] a primary measurement (a paper), [C] compiled, [M-ph]
my measure on a photo of deer/horns/refs (good to about 10 %), [L] looked at in a photo at full size, [E] an
estimate with the gate that checks it, [D] derived. The antler's [P] rows are ALL Bils, Willems & Reiner 2023 (Eur.
J. Wildl. Res. 69:27; 355 antlers of 35 stags aged 8.5 +- 2.2 y, 3D scans; the text in
work/bestiary/deer/anatomy/refs/antler/): D1 is their MEAN antler, with a royal's crown of three.
"""

# ---------------------------------------------------------------------------------------------------- the antler
# D1: the prime stag's royal (12 points: brow, bay, tray and a crown of three a side)
RED_DEER = dict(
    family='antler', cls='bone', U_native=400.0,
    # the pedicle's axis and the tines' front on the deer's own head, the stag standing alert (head axes at rest)
    # (11-12, check 2's failure 1, "the pair reads as a V, not a red deer's lyre": this row, `beam.bow`,
    # `beam.lateral` and the tines' az / bend directions RE-FITTED TOGETHER to six front-view beams and one side
    # view, fit `_d` of work/bestiary/deer/horns/build/scripts/fix3/g03_fit.py; the first row, axis (0.465, 0.832,
    # 0.304) and front (0.091, -0.386, 0.918), stood the lower beam 24 deg out)
    launch=dict(axis=(0.7678, 0.5585, 0.314), front=(-0.2428, -0.1999, 0.9493)),
    beam=dict(
        length=967.5,
        # girths along the beam: (station mm from the signet, girth mm, thickness / width). Width lies in the tines'
        # plane (x), thickness across it (y)
        girth=((0.0, 184.8, 0.94), (3.0, 187.0, 0.94), (9.0, 204.0, 0.94), (15.0, 213.0, 0.935), (22.0, 215.2, 0.93),
               (66.0, 189.4, 0.90), (130.0, 158.0, 0.90), (185.0, 145.6, 0.90), (250.0, 150.0, 0.86),
               (300.0, 146.0, 0.84), (420.0, 134.7, 0.88), (520.0, 140.0, 0.80), (568.7, 150.0, 0.66),
               (640.0, 122.0, 0.70), (716.9, 118.0, 0.68)),
        # the in-plane turns: (station mm, degrees, half length mm of the bend). + is AWAY from the tines (back)
        turns=((38.5, 41.5, 26.0), (93.8, 6.3, 20.0), (275.5, -20.9, 34.0), (568.7, 10.0, 34.0), (716.9, -14.0, 34.0)),
        # a smooth bow on top of the turns: (station mm, degrees of tilt added; + away from the tines), interpolated
        bow=((0.0, 0.0), (110.0, 0.0), (250.0, -2.0), (545.0, 32.78), (700.0, -0.97), (967.5, -27.78)),
        # the lateral angle of the beam out of the tines' plane: (station mm, degrees toward OUT), interpolated.
        # Negative = toward the other antler: the beam sweeps out with the launch and this row turns it up and IN
        # through the crown (the lyre)
        lateral=((0.0, 0.0), (60.0, -0.22), (275.5, -5.56), (420.0, -13.83), (568.7, -18.08), (760.0, -49.44),
                 (967.5, -75.94)),
    ),
    # the burr: the rim's crest station, its length along the beam, the beads' count round it and their size. rim:
    # the irregular ring under the beads (its own closed sweep): r its half height along the beam, aspect its depth
    # out of the beam over that, r_var the share its thickness changes by round it, wander (mm along the beam, mm
    # in and out), proud the share of r its centre stands off the beam's surface, blend its fillet to the beam
    # rim.lobes: the lobe counts round the rim of its three wanders (along the beam, in and out, its thickness)
    # low_proud: how far the LOW's rim crest stands out of the clay's rim (the nodules' middle height)
    # THE CRUST (11-12, check 2's failure 2: "a ring of even, round, glossy beads that read as teeth at 0.5 m" where
    # refs c11 Rothirsch Geweihansatz 070816 1 shows "a low crust of fused knobs of many sizes run into by the beam's
    # furrows"). The first two recipes were ONE row of knobs (32 of r 3.0-5.75 mm, then 40 of r 1.8-5.5) each taller
    # than wide with a notch cut between every two: a row of molars however the sizes were drawn. Now:
    #   nodules  rows of lumps ON the rim, each (count, radius mm (lo, hi), where across the rim's section in
    #            degrees from straight out of the beam toward its distal side (centre, half spread), how far a lump
    #            stands out of the rim as a share of its own radius (lo, hi)): three staggered rows that overlap, so
    #            the lumps FUSE; sizes skewed small, bigger where the rim itself is thick (the low's outline is
    #            the rim's: its swells carry the big knobs); none taller than wide
    #   notches  how many furrows cut into the rim, at random places (the beam's furrows running in; not one
    #            between every two knobs)
    #   crust    how many 0.4-1.2 mm nodules lie over all of it
    burr=dict(station=8.0, length=11.0, low_proud=0.8, lobes=(0.035, 0.022),
              nodules=((46, (0.9, 2.4), (-42.0, 16.0), (0.30, 0.65)),
                       (36, (1.2, 3.4), (6.0, 20.0), (0.35, 0.70)),
                       (44, (0.8, 2.2), (54.0, 18.0), (0.30, 0.60))),
              notches=12, crust=260,
              # (the lobes stop at 6 round the beam: the low's 24 columns carry a wave of four columns or more;
              # with lobes of 8 and 10 the low's straight edges cut 0.6-0.8 mm under the clay rim's bumps)
              rim=dict(r=4.6, aspect=0.95, r_var=0.30, wander=(2.0, 1.4), proud=0.25, blend=2.5, seed=7,
                       lobes=((1, 2, 3), (2, 3, 5, 6), (2, 3, 4, 6))),
              seal_dome=3.0),
    # the three main tines. out: the outgoing angle to the beam BELOW the fork; az: the launch's turn about the beam
    # from the front toward OUT; bend: (degrees, direction) pairs, the direction turning about the launch from
    # "toward the beam's distal side" (0) toward OUT (90); bend_profile: the turning's weight at the tine's base and
    # at its tip (1, 1 a circular arc; 0.3, 1.7 a tine that runs straight and hooks late); taper: radius / the mid
    # radius at u = 0, .25, .5, .75, .9, 1
    tines=(
        dict(name='brow', station=38.5, arc=351.1, secant=293.9, sagitta=79.3, girth=92.7, out=108.8, az=-0.59,
             bend=((118.0, -43.05),), bend_profile=(0.5, 1.5), flat=0.86, taper=(1.42, 1.17, 1.0, 0.74, 0.52, 0.26)),
        dict(name='bay', station=93.8, arc=294.2, secant=264.6, sagitta=55.4, girth=80.2, out=98.8, az=0.15,
             bend=((93.0, -26.89),), bend_profile=(0.55, 1.45), flat=0.88, taper=(1.40, 1.16, 1.0, 0.74, 0.52, 0.26)),
        dict(name='tray', station=275.5, arc=352.1, secant=300.7, sagitta=80.7, girth=88.9, out=116.9, az=-3.0,
             bend=((112.0, -68.32),), bend_profile=(0.55, 1.45), flat=0.84,
             taper=(1.42, 1.17, 1.0, 0.74, 0.52, 0.26)),
    ),
    # the crown: its base, then the forks. Each crown tine as a tine row whose `out` is the angle to the beam's own
    # direction ABOVE the fork (acute: a crown tine leaves beside the beam), `girth` at its half
    crown=dict(
        base=568.7,
        tines=(
            # (11-12: fork 60 -> 66 and 58 -> 62. With the re-fitted az the crown's box read 245 mm long in the
            # tines' plane, -1.11 sd of Bils' 336 +- 82 (it was 259, -0.94); at 66 / 62 it is 271, -0.79, inside one
            # sd like every other row, and the cup opens a little)
            dict(name='crown_a', station=568.7, arc=261.2, girth=74.0, fork=66.0, az=-5.9, bend=((14.0, 0.0),),
                 flat=0.74, taper=(1.50, 1.20, 1.0, 0.74, 0.52, 0.26)),
            dict(name='crown_c', station=716.9, arc=196.4, girth=66.0, fork=62.0, az=196.19, bend=((12.0, 0.0),),
                 flat=0.74, taper=(1.50, 1.20, 1.0, 0.74, 0.52, 0.27)),
        ),
        # the beam's own end, from the last fork to its tip, tapers as a tine: its girth half way and its taper
        top=dict(name='crown_b', girth=70.0, taper=(1.50, 1.20, 1.0, 0.74, 0.52, 0.26)),
    ),
    # the blend where one form flows into the next (the ROUND union's radius, mm) and the surface's scale
    blend=16.0,
    # mm. pearl_len is a pearl's HALF length; ridge_pearl the size of the grain's ridge pearls against the channels';
    # grain_window the length of one stagger of grain lines
    # polish_from: where the sculpt's pearls and channels give way to the smooth tip, a share of each tine (0.62 was
    # read on the sun-bleached CAST antler; fix round 1 sets the plan's default, a LIVING prime stag in hard antler:
    # pearled to his short ivory ends, refs c11 Richmond Park 2025 01, the ivory over the last 15-30 %)
    # round_pearls: the share of the grain's crest pearls that are round tubercles (a living stag's crust)
    surface=dict(gutter_pitch=9.0, gutter_depth=(0.35, 1.5), gutter_width=(1.8, 3.8), pearl_r=(0.6, 1.3),
                 pearl_len=(1.0, 2.3), ridge_pearl=0.85, grain_pitch=2.4, grain_depth=(0.10, 0.30),
                 grain_width=(1.0, 1.8), grain_window=55.0, polish_from=0.74, round_pearls=0.70),
    # UV stacking classes (plan §5.4): the hero rule keeps beam, brow and tray their own texels
    classes=dict(hero=('beam', 'brow', 'tray'), tine_b=('bay', 'crown_a', 'crown_c')),
)

_B = ('[P]', 'Bils, Willems & Reiner 2023')
TAGS_RED_DEER = {
    'U_native': ('[E]', 'the stag\'s condylobasal length ~0.40 m (anatomy STUDY §4.1); gate: D6.0\'s skull'),
    'launch': ('[M-ph]', 'FITTED 11-12 with beam.bow, beam.lateral and the tines\' az / bend directions (deer/horns/'
                         'build/scripts/fix3/g03_fit.py, fit `_d`; the readings g02_attitude.py -> build/out/fix3/'
                         'g02_refs.json) to SIX FRONT-VIEW BEAMS, each a polyline drawn back on its photo (the living '
                         'stag f03 = anatomy refs "Red deer during the rut (48858471992)"; the mounts c11 Fotothek '
                         '0047447 and 0047443: check 2\'s readings), and ONE SIDE VIEW (the alert stag d03 = "Cerf '
                         'elaphe (Rhodes) (1)", both beams, his head turned 23.5 deg toward the camera), every '
                         'measured row of Bils held. The beam\'s lean from the vertical in a front view, mean over '
                         'the first fifth / 0.3-0.6 / the last fifth of its length: 52.1 / 35.9 / -13.0 deg at rest '
                         '(the photos 48-63 / 30-52 / -33 to +2), turning 65 deg (47-97); the chords burr-tray, '
                         'tray-crown, crown-tip in head axes (0.723, 0.584, -0.369), (0.557, 0.702, -0.444), (0.040, '
                         '0.993, -0.107); in d03\'s view 47 / 42 / 7 deg back on the near beam and 5 / 15 / 5 on the '
                         'far (his 52 / 35 / 4 and 3 / 15 / 10). The head pitch of a front photo is MEASURED, never '
                         'free (f03\'s face: nose to eye 118-128 px tall over 215 px eye to eye = 22-24 deg off the '
                         'line of sight against d03\'s 28: +5 deg; free, it bought 20-30 deg on all three photos and '
                         'a lower beam only 32 deg out). The pair is then 0.904 m wide centre to centre on pedicles '
                         '90 mm apart, an inside spread of 0.91 of the beam (the widest class: D1\'s beam is long, '
                         'the leans are the photos\'); the brow, bay and tray tips point UP (the basket). The first '
                         'row (24 deg out, a V: check 2) read 0047443 as "45 deg out" by eye. Gate: HN6, on the '
                         'deer\'s own head'),
    'beam.length': (_B[0], _B[1] + ' Table 2: 967.5 +- 101.1 (centre line)'),
    'beam.girth': ('[P] + [E]', 'Bils: signet 184.8 +- 18.8, burr 245.9 +- 21.0, base-brow 215.2 +- 23.9, brow-bay '
                                '189.4 +- 26.9 (smallest), lower beam 145.6 +- 13.9, upper beam 134.7 +- 15.4. The '
                                'other rows and every thickness / width are [E] / [M-ph]: the beam flattens and '
                                'widens ~1.5x into each fork (c06, my pixels; c11 BLW, LM369-9); gate: the clay '
                                'beside c06 at its camera, widths in pixels'),
    'beam.turns': ('[P] + [M-ph]', 'Bils Table 2: the beam angle at the brow 138.5 +- 11.3, bay 173.7 +- 6.4, tray '
                                   '159.1 +- 6.7 deg (turns 41.5 / 6.3 / 20.9). SIGNS [M-ph]: away from the brow '
                                   '(the base is a Y: the three angles sum to 360 only so), TOWARD the tray (c11 '
                                   'by-dpc: tray to distal beam 48 deg, = 159.1 - 116.9 = 42.2; opposite it would '
                                   'be 84). The crown\'s two turns [M-ph] by-dpc, LM369-9'),
    'beam.bow': ('[M-ph]', 'fitted with `launch` (its tag) on the front and side photos; the beam\'s sagitta signet -> '
                           'crown base 42.2 mm against Bils\' 55.1 +- 17.0 (z -0.76)'),
    'beam.lateral': ('[M-ph]', 'fitted with `launch` (its tag): on every front view the beams SWEEP OUT at 48-63 deg '
                               'and then turn UP AND IN through the crown (c11 Fotothek 0047443 measured: 61 / 48 deg '
                               'at the burr, the crown vertical; 0047447: 51 / 51, the top 7-16 deg in; f03: 50 / 63, '
                               'the top 33 in). The first row called them "straight and leaning out" (check 2\'s '
                               'failure 1)'),
    'burr': ('[P] + [M-ph]', 'girth 245.9 [P]; the rim low and irregular, about 10-12 mm tall and 4-5 mm proud of '
                             'the beam over it, a crust of fused nodules 2-6 mm across in two or three uneven rows, a '
                             'few big ones on its thick side, the beam\'s furrows running into its upper edge (c11 '
                             'Rothirsch Geweihansatz 070816 1 at full size, 11-12; Corne de cervide, c06). Gate: the '
                             'engine\'s 0.5 m close-up beside that photo'),
    'tines': ('[P] + [M-ph]', 'Bils Table 3: stations (signet-brow 38.5 +- 6.5; brow-bay 55.3 +- 25.5; brow-tray '
                              '237.0 +- 43.4), arcs, secants, sagittas, girths (half way), outgoing angles 108.8 / '
                              '98.8 / 116.9. THE BEND [D]: each tine\'s arc, secant and sagitta are ONE circular arc '
                              '(brow 351 / 294 / 79 = 115 deg of turn, bay 90, tray 110), so bend = that turn. az '
                              'and the bend directions fitted to the tip distances with the measured rows held '
                              '(first by build/scripts/h03_direction_fit.py; again on 11-12 with the launch, its tag: '
                              'the tips stay up and none crosses the midline once the beam leans 52 deg out) (the '
                              'tray curls across the fork plane: its tip '
                              'to the crown base 263 puts its chord 53 deg off the beam, its launch 42) '
                              '(brow-bay 176.6 +- 45.0, brow-tray 336.7 +- 92.5, bay-tray 260.4 +- 65.3, brow-crown '
                              'base 512.8 +- 84.4, tray-crown base 262.8 +- 39.7). taper [M-ph] c11 by-dpc (tray: '
                              'base 1.43, .75 0.71, .95 0.40 of the mid width), LM369-6'),
    'crown': ('[P] + [M-ph]', 'Bils Table 4: tray-crown base 293.2 +- 48.1; crown beams (level 1) 114.3 +- 52.3, '
                              'crown tines 261.2 +- 57.8 (level 1), 196.4 +- 68.8 (level 2); 4.6 +- 1.2 crown tines: '
                              'a ROYAL carries three (the commonest level-2 crown, 21 %). The crown beam here 148 mm '
                              '(+0.65 sd) so the beam ends at 967.5 through a 250.6 mm top. Angles and girths '
                              '[M-ph] c11 LM369-9, by-dpc; gate: crown height / length / width against Bils\' '
                              '333 +- 61 / 336 +- 82 / 210 +- 75'),
    'blend': ('[M-ph]', 'crotch radii 6-12 mm (c11 LM369-9, BLW)'),
    'surface': ('[M-ph]', 'gutters 5-10 mm apart on the lower beam, a few deep among many faint; pearls as pale '
                          'flecks 2-4.5 mm long and 1-2 mm wide in rows 2-3.5 mm apart, lying along the beam, and '
                          'streaks 1-3 mm apart everywhere between them (c11 Cervus_elaphus_01_by-dpc at ~0.35 mm a '
                          'pixel: the burr 220 px across; BLW, Geweihansatz, LM369-6); the tips ivory over the last '
                          '30-40 % (LM369-9)'),
    'classes': ('[H]', 'DEER_PLAN §5.4, the hero rule'),
}

# THE AGE TABLE: the younger heads of ONE stag, as rows D1 is multiplied by (families/horn.py `aged`; head 7 is D1
# itself: Bils' stags are 8.5 +- 2.2 years old, the 7th-8th head). Read off refs c06, one stag's cast antlers from
# his 1st to his 7th head on one board (my polylines: work/bestiary/deer/horns/build/scripts/h13_age_series.py,
# its reading in build/out/h13_c06_reading.json), then made regular: a real series jumps from year to year (his 5th
# beam is longer than his 6th; his 7th has no bay and a stub for a tray), a table should not.
#   beam   the beam's length / D1's          girth  every girth / D1's (the beam's thickness in pixels at its middle)
#   tines  name -> the tine's arc / D1's; a tine not named does not exist on that head (and the beam does not turn
#          at it). The crown: crown_a alone is a fork with the beam's end, crown_a + crown_c the crown of three
#   at     name -> its station as a SHARE OF THIS HEAD'S BEAM ('crown': the crown's base); not named: D1's own
#          station scaled with the beam (the first tine, the brow, scales with the girth: it sits on the burr)
RED_DEER_AGE = {
    1: dict(beam=0.55, girth=0.45, tines=dict(brow=0.42)),
    2: dict(beam=0.63, girth=0.55, tines=dict(brow=0.75, tray=0.60, crown_a=0.23), at=dict(tray=0.34, crown=0.81)),
    3: dict(beam=0.78, girth=0.72, tines=dict(brow=0.95, tray=0.65, crown_a=0.20), at=dict(tray=0.33, crown=0.78)),
    4: dict(beam=0.86, girth=0.80, tines=dict(brow=1.00, tray=0.80, crown_a=0.22), at=dict(tray=0.32, crown=0.68)),
    5: dict(beam=0.93, girth=0.92, tines=dict(brow=1.00, bay=0.15, tray=0.90, crown_a=0.45, crown_c=0.36),
            at=dict(tray=0.31, crown=0.67)),
    6: dict(beam=0.97, girth=0.95, tines=dict(brow=1.00, bay=0.85, tray=1.00, crown_a=0.60, crown_c=0.90),
            at=dict(tray=0.30, crown=0.64)),
    7: dict(beam=1.00, girth=1.00, tines=dict(brow=1.00, bay=1.00, tray=1.00, crown_a=1.00, crown_c=1.00)),
}
RED_DEER['age_table'] = RED_DEER_AGE
TAGS_RED_DEER['age_table'] = (
    '[M-ph]', 'refs c06 (one stag\'s seven heads, no scale in the picture: every number a share), my polylines, +- 0.03 '
              'in a station and +- 15 % in a length. HIS heads: beam / his 7th 0.55, 0.62, 0.78, 0.84, 0.97, 0.92, 1; '
              'points a side 2, 4, 4, 4, 6 (one a snag), 6, 6; the tray at 0.34, 0.33, 0.19, 0.41, 0.36, 0.20 of the '
              'beam (heads 2-7: Bils\' mean 0.285 +- 0.045); the crown\'s base at 0.81, 0.78, 0.64, 0.67, 0.71, 0.51 '
              '(it moves DOWN the beam as the crown gains points: Bils 0.588); a bay only from the 5th head (a '
              'snag), long on the 6th; the brow at 0.4 / 0.7 / 0.95 of its full length on heads 1 / 2 / 3; the first '
              'crown tine 0.2 of its full length on heads 2-4, 0.45 on 5-6. His first head may carry a third point '
              '(two antlers overlap in the picture): read as a fork. Gate: the board beside c06')

# ------------------------------------------------------------------------------------- the other families (HN3)
# DATA ONLY this round (the lead's brief: the bovid, rhino, tusk and ossicone families wait; "build the generator so
# they are data"). families/horn.py builds their SKELETONS from these rows; their section tables are measured first
# at HN3 (DEER_CRITIC §1b: ram c02 a three-sided section with a flat front and a keel, bases as wide as the forehead)
BIGHORN = dict(
    family='spiral', cls='keratin', U_native=290.0,
    launch=dict(axis=(0.45, 0.80, -0.40), front=(0.30, 0.20, 0.93)),
    spiral=dict(length=521.0, excursion=164.0, turn=0.85, curl_ratio=4.0, hand=1.0),
    section=dict(keys=((0.0, 46.0, 0.80, 0.16), (0.6, 30.0, 0.70, 0.10), (1.0, 9.0, 0.50, 0.0)),),
    bands=dict(years=8, ridge_pitch=9.11, core=0.45),
)
TAGS_BIGHORN = {
    'spiral': ('[P] + [E]', 'Wheatley et al. (engrXiv 2806): centreline 521 +- 74 mm, lateral excursion 164 +- 29 mm '
                            '(n 4); turn 0.85 and the base / tip curl-radius ratio 4 are [E] (refs c02, c03)'),
    'section': ('[E]', '(u, half width mm, thickness / width, third harmonic): a rounded triangle flattening toward '
                       'the tip [P, words only]; HN3 measures it on c02 before any clay'),
    'bands': ('[P]', 'ridge pitch 9.11 +- 4.16 mm (Lee et al. 2024); the core 0.40-0.50 of the length (Wheatley)'),
}
NARWHAL = dict(
    family='cone', cls='ivory', U_native=550.0,
    launch=dict(axis=(0.0, 0.05, 1.0), front=(0.0, 1.0, 0.0)),
    cone=dict(length=2000.0, base_d=74.0, tip_d=10.0, bend=4.0, helix=dict(starts=3, angle=66.88, hand=-1.0, amp=0.05)),
)
TAGS_NARWHAL = {
    'cone': ('[P] + [M-ph]', 'helix angle 66.88 +- 0.61 deg, left-handed (Kiladze & Chernova 2018); D / L ~1/27 '
                             '[M-ph c09]; three ridges ~0.05 D [L c10]'),
}
WHITE_RHINO_NASAL = dict(
    family='cone', cls='fibre', U_native=700.0,
    launch=dict(axis=(0.0, 0.94, 0.34), front=(0.0, -0.34, 0.94)),
    cone=dict(length=600.0, base_d=180.0, tip_d=24.0, bend=28.0, aspect=0.78, helix=None),
)
TAGS_WHITE_RHINO_NASAL = {
    'cone': ('[C] + [E]', 'length ~60 cm [C]; a grown cylinder worn into a cone (Hieronymus et al. 2006): the wear '
                          'cone and the rubbing facet are HN3\'s, measured first'),
}
GIRAFFE_OSSICONE = dict(
    family='cone', cls='skin', U_native=650.0,
    launch=dict(axis=(0.10, 0.90, -0.42), front=(0.0, 0.42, 0.90)),
    cone=dict(length=150.0, base_d=62.0, tip_d=44.0, bend=6.0, helix=None, knob=1.25),
)
TAGS_GIRAFFE_OSSICONE = {
    'cone': ('[C]', 'conflicting sizes in the compiled sources (horns study §2.5): HN2 measures them'),
}

# the two leaves every data-only row shares: both estimates until HN3 measures them (11-11: `untagged()` listed them)
for _t, _skull in ((TAGS_BIGHORN, 'a ram\'s skull ~0.29 m'), (TAGS_NARWHAL, 'a narwhal\'s skull ~0.55 m'),
                   (TAGS_WHITE_RHINO_NASAL, 'a white rhino\'s skull ~0.70 m'),
                   (TAGS_GIRAFFE_OSSICONE, 'a giraffe\'s skull ~0.65 m')):
    _t['U_native'] = ('[E]', _skull + ' (compiled, not measured here); gate: HN3, the donor\'s skull with a scale')
    _t['launch'] = ('[E]', 'the root axis and the front by eye from the family\'s photos (deer/horns/refs c01-c05, '
                           'c09, c10); gate: HN3, two world directions read off photos as the red deer\'s were')

PRESETS = dict(red_deer=RED_DEER, bighorn=BIGHORN, narwhal=NARWHAL, white_rhino_nasal=WHITE_RHINO_NASAL,
               giraffe_ossicone=GIRAFFE_OSSICONE)
TAGS = dict(red_deer=TAGS_RED_DEER, bighorn=TAGS_BIGHORN, narwhal=TAGS_NARWHAL,
            white_rhino_nasal=TAGS_WHITE_RHINO_NASAL, giraffe_ossicone=TAGS_GIRAFFE_OSSICONE)
# the old creator's five hornStyle names (creature_builder.js) as presets (plan §5.9); the rows that do not exist yet
# name the round that builds them
OLD_STYLES = dict(antler=('red_deer', dict(age=3)), ram=('bighorn', {}), narwhal=('narwhal', {}),
                  spike=('goat: HN3', {}), moose=('moose: HN3', {}))


def untagged(name):
    """the top-level leaves of a preset that carry no source tag (the SPEC convention: every leaf sourced)"""
    skip = {'family', 'cls'}
    return sorted(k for k in PRESETS[name] if k not in skip and k not in TAGS[name]
                  and not any(t.split('.')[0] == k for t in TAGS[name]))
