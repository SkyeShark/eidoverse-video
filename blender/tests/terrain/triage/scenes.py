"""The triage scene list: every Ekigar landform (and every named sub-type that promises a different landform), every
operator on the fixture Ekigar's own visual suite judges it on, the Phacelle erosion and mask studies, graph
composites, and real elevation data of the landforms the names promise, all rendered by one rig (render.py).

Each subject is generated at 1024 texels (Ekigar's default project resolution) with Ekigar's vertical scale 0.3 (a
field unit of height is 0.3 x the tile's width), over a tile sized to the real landform its name promises, so the
eye-level camera (1.7 m) stands in a landscape of the right size. The proportions are Ekigar's: only the absolute
size is chosen here.

    python scenes.py            # prints the list
"""
import os

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.environ.get('TRIAGE_CACHE', 'C:/Users/sdn52/AppData/Local/Temp/claude/58f6fc01d66e098b/'
                                       '7ba5a5b7-5eb0-446a-8f4f-977d471453ff/scratchpad/triage_cache')
RENDERS = os.path.join(HERE, 'renders')
SHEETS = os.path.join(HERE, 'sheets')
RES = 1024
VS = 0.3
OPERATOR_W = 2000.0        # every non-landform operator sits on Ekigar's detailed-base fixture over a 2 km tile


def S(name, group, build, W, promise, res=RES, eye=None, overlay=None):
    """A subject. build: ('ex', op, params) Ekigar's own example scene for that operator; ('chain', [(op, params)]);
    ('maskex', op, params) a derive operator painted on its input; ('masks', chain, [names]) named masks of a chain
    painted on it; ('dem', key) real elevation data. eye: {'at': (u, v), 'look': (u, v)} in tile fractions, else the
    rig picks a spot. overlay: the mask painted on the clay."""
    return dict(name=name, group=group, build=build, W=float(W), promise=promise, res=res, eye=eye, overlay=overlay)


def EX(op, **p):
    return ('ex', op, p)


# ------------------------------------------------------------------------------------------- landforms ---
LANDFORMS = [
    S('crater', 'landform', EX('crater'), 2000, 'simple bowl impact crater, raised rim, ejecta (Meteor Crater)'),
    S('mountain', 'landform', EX('mountain'), 6000, 'one mountain massif with ridges and spurs'),
    S('mountain_basic', 'landform', EX('mountain', style='basic'), 6000, 'mountain, basic style'),
    S('mountain_old', 'landform', EX('mountain', style='old'), 6000, 'old, worn-down mountain'),
    S('mountain_alpine', 'landform', EX('mountain', style='alpine'), 6000, 'alpine peak: aretes, cirques, horns'),
    S('mountain_strata', 'landform', EX('mountain', style='strata'), 6000, 'layered (stratified) mountain'),
    S('mountainRange', 'landform', EX('mountainRange'), 6000, 'eroded mountain range with drainage'),
    S('mountainRange_basic', 'landform', EX('mountainRange', style='basic'), 6000, 'mountain range, basic'),
    S('mountainRange_stratified', 'landform', EX('mountainRange', style='stratified'), 6000,
      'stratified mountain range (bedded ridges)'),
    S('mountainRange_alpine', 'landform', EX('mountainRange', style='alpine'), 6000,
      'alpine range: sharp aretes, horns, glacial valleys'),
    S('canyon', 'landform', EX('canyon'), 3000, 'meandering canyon in stratified plateau, stepped walls'),
    S('canyon_classic', 'landform', EX('canyon', style='classic'), 3000, 'canyon, classic style'),
    S('canyon_strata', 'landform', EX('canyon', style='strata'), 3000, 'canyon with strata benches'),
    S('canyon_narrow', 'landform', EX('canyon', scale=0.2, meanders=3), 3000,
      'a narrower, tighter-meandering canyon (scale 0.2, 3 meanders), a fair second look'),
    S('island', 'landform', EX('island'), 8000, 'volcanic island: coastline, interior peaks, beach shelf'),
    S('volcano', 'landform', EX('volcano'), 10000, 'stratovolcano: concave flanks, summit crater (Fuji)'),
    S('volcano_cone', 'landform', EX('volcano', profile='cone'), 10000, 'volcanic cone'),
    S('volcano_shield', 'landform', EX('volcano', profile='shield'), 10000, 'shield volcano: broad, gentle (Hawaii)'),
    S('volcano_pyroclasticShield', 'landform', EX('volcano', profile='pyroclasticShield'), 10000,
      'pyroclastic shield: low broad ignimbrite shield'),
    S('volcano_smooth', 'landform', EX('volcano', surface='smooth'), 10000,
      "the volcano's bare profile (surface smooth: no built-in erosion), a fair second look"),
    S('rugged', 'landform', EX('rugged'), OPERATOR_W, 'rocky surface on any terrain, shape kept'),
    S('caldera', 'landform', EX('caldera'), 12000, 'collapse caldera: ring fault walls, flat floor (Crater Lake)'),
    S('impactCrater', 'landform', EX('impactCrater'), 20000,
      'complex impact crater: terraced walls, central peak'),
    S('cinderConeField', 'landform', EX('cinderConeField'), 5000,
      'cinder cones at angle of repose, summit craters, lava flows (SP Crater field)'),
    S('maar', 'landform', EX('maar'), 3000, 'maar: below-ground crater, low tuff ring'),
    S('maar_tuffRing', 'landform', EX('maar', style='tuffRing'), 3000, 'tuff ring: wide low rim'),
    S('maar_tuffCone', 'landform', EX('maar', style='tuffCone'), 3000, 'tuff cone: steeper, higher cone'),
    S('cirque', 'landform', EX('cirque'), 6000, 'glacial cirques: amphitheatre basins in mountains, aretes'),
    S('basinField', 'landform', EX('basinField'), 1000, 'field of closed depressions (dolines, pans)'),
    S('moundField', 'landform', EX('moundField'), 2000, 'pingos / earth mounds, some with summit craters'),
    S('volcanicPlug', 'landform', EX('volcanicPlug'), 4000, 'volcanic neck with radiating dikes (Shiprock)'),
    S('lavaDome', 'landform', EX('lavaDome'), 2500, 'steep bulbous lava dome, blocky talus apron'),
    S('mesa', 'landform', EX('mesa'), 3000, 'mesa: flat caprock, cliff, talus slope, apron (Monument Valley)'),
    S('glacialTrough', 'landform', EX('glacialTrough'), 6000,
      'U-shaped glacial valley, truncated spurs, hanging valleys (Yosemite)'),
    S('meanderBelt', 'landform', EX('meanderBelt'), 1500, 'meandering river: cut banks, point bars, oxbows'),
    S('faultScarp', 'landform', EX('faultScarp'), 600, 'fault scarp: fresh step across the land, facets'),
    S('graben', 'landform', EX('graben'), 4000, 'graben: down-dropped block between two faults'),
    S('graben_halfGraben', 'landform', EX('graben', style='halfGraben'), 4000, 'half-graben: tilted block'),
    S('graben_horstGraben', 'landform', EX('graben', style='horstGraben'), 4000, 'horst-and-graben ranges'),
    S('graben_pullApart', 'landform', EX('graben', style='pullApart'), 4000, 'pull-apart basin'),
    S('dipSlope', 'landform', EX('dipSlope'), 3000, 'cuestas / hogbacks: gentle dip slope, steep scarp'),
    S('esker', 'landform', EX('esker'), 1000, 'esker: sinuous gravel ridge'),
    S('moraineSet', 'landform', EX('moraineSet'), 3000, 'lateral / terminal / recessional moraines'),
    S('streamform', 'landform', EX('streamform'), 2000, 'drumlin field: streamlined hills'),
    S('streamform_rocheMoutonnee', 'landform', EX('streamform', mode='rocheMoutonnee'), 500,
      'roches moutonnees: smooth stoss, plucked lee'),
    S('streamform_whaleback', 'landform', EX('streamform', mode='whaleback'), 500, 'whalebacks'),
    S('streamform_yardang', 'landform', EX('streamform', mode='yardang'), 1000, 'yardangs: wind-carved ridges'),
    S('oceanRidge', 'landform', EX('oceanRidge'), 200000, 'mid-ocean ridge: rift valley, transform faults'),
    S('oceanRidge_trench', 'landform', EX('oceanRidge', mode='trench'), 200000, 'ocean trench'),
    S('oceanRidge_abyssalPlain', 'landform', EX('oceanRidge', mode='abyssalPlain'), 200000, 'abyssal plain'),
    S('invertedChannel', 'landform', EX('invertedChannel'), 1500, 'inverted river channel: sinuous flat-topped ridge'),
    S('terraceStair', 'landform', EX('terraceStair'), 1500, 'river terraces: flat treads, steep risers'),
    S('waveCutPlatform', 'landform', EX('waveCutPlatform'), 500, 'sea cliff above a wave-cut platform'),
    S('playa', 'landform', EX('playa'), 5000, 'playa: dead-flat dry lake floor, bajada'),
    S('playa_saltPan', 'landform', EX('playa', style='saltPan'), 5000, 'salt pan'),
    S('playa_polje', 'landform', EX('playa', style='polje'), 5000, 'polje: flat karst basin, steep sides'),
    S('playa_lacustrinePlain', 'landform', EX('playa', style='lacustrinePlain'), 5000, 'lake plain'),
    S('playa_chott', 'landform', EX('playa', style='chott'), 5000, 'chott: salt lake basin'),
    S('planationSurface', 'landform', EX('planationSurface'), 5000, 'planation surface with residual hills'),
    S('towerKarst', 'landform', EX('towerKarst'), 1500, 'tower karst: steep limestone towers on a plain (Guilin)'),
    S('cockpitKarst', 'landform', EX('cockpitKarst'), 4000, 'cockpit karst: cones between star-shaped pits'),
    S('limestonePavement', 'landform', EX('limestonePavement'), 40, 'limestone pavement: clints and grikes'),
    S('bornhardt', 'landform', EX('bornhardt'), 3000, 'bornhardt / inselberg: bare granite dome (Uluru)'),
    S('badlands', 'landform', EX('badlands'), 1000, 'badlands: dense rills, gullies, buttes'),
    S('patternedGround', 'landform', EX('patternedGround'), 25, 'patterned ground: sorted circles to stripes'),
    S('duneField', 'landform', EX('duneField'), 1000, 'barchan dunes: crescents, horns downwind'),
    S('duneField_transverse', 'landform', EX('duneField', type='transverse'), 1500, 'transverse dunes'),
    S('duneField_barchanoid', 'landform', EX('duneField', type='barchanoid'), 1500, 'barchanoid ridges'),
    S('duneField_linear', 'landform', EX('duneField', type='linear'), 5000, 'linear (seif) dunes'),
    S('duneField_star', 'landform', EX('duneField', type='star'), 5000, 'star dunes: tall pyramids, radiating arms'),
    S('duneField_star_f9', 'landform', EX('duneField', type='star', frequency=9), 5000,
      "star dunes at Ekigar's own suggested frequency (~9), a fair second look"),
    S('duneField_dome', 'landform', EX('duneField', type='dome'), 1000, 'dome dunes'),
    S('duneField_parabolic', 'landform', EX('duneField', type='parabolic'), 1500, 'parabolic dunes, arms upwind'),
    S('alluvialFan', 'landform', EX('alluvialFan'), 5000, 'alluvial fan: cone of sediment from a canyon mouth'),
    S('sandur', 'landform', EX('sandur'), 10000, 'outwash plain: braided channels'),
    S('delta', 'landform', EX('delta'), 20000, 'river delta: distributaries, levees, lobes'),
    S('spitBar', 'landform', EX('spitBar'), 3000, 'sand spit with recurved tip, lagoon'),
    S('spitBar_baymouth', 'landform', EX('spitBar', mode='baymouth'), 3000, 'baymouth bar'),
    S('spitBar_tombolo', 'landform', EX('spitBar', mode='tombolo'), 3000, 'tombolo: bar tying an island to shore'),
    S('spitBar_barrier', 'landform', EX('spitBar', mode='barrier'), 3000, 'barrier island'),
    S('spitBar_cuspate', 'landform', EX('spitBar', mode='cuspate'), 3000, 'cuspate foreland'),
    S('reefRing', 'landform', EX('reefRing'), 10000, 'atoll / barrier reef ring, lagoon, passes'),
    S('beachCusps', 'landform', EX('beachCusps'), 400, 'beach cusps: regular horns along the swash line'),
    S('lavaField', 'landform', EX('lavaField'), 3000, 'lava flow field: lobes, levees, pressure ridges'),
    S('rockGlacier', 'landform', EX('rockGlacier'), 2000, 'rock glacier: lobate debris tongue, arcuate ridges'),
]

# ------------------------------------------------------------------------------------------- operators ---
_OPS = [
    # primitives (stand alone)
    ('constant', 'flat value'), ('gradient', 'linear ramp'), ('radialGradient', 'radial falloff'),
    ('fbm', 'fBm noise base terrain'), ('ridged', 'ridged noise: sharp ridgelines'),
    ('voronoi', 'cellular distance: mesas, plates'), ('perlin', 'coherent noise'),
    ('cellular', 'cell patterns'), ('dotNoise', 'dots / speckles'), ('lineNoise', 'line sets'),
    ('cracks', 'crack network'), ('shape', 'geometric primitive'), ('cone', 'cone'),
    ('hemisphere', 'dome'), ('pattern', 'repeating pattern'),
    # simulate
    ('phacelle', 'erosion: gullies cut downhill, ridges sharpened'),
    ('thermal', 'thermal erosion: talus aprons at the angle of repose'),
    ('snow', 'snow accumulation smoothing high, shelterd ground'),
    # surface
    ('terrace', 'terraced steps'), ('stratify', 'sedimentary beds: flat treads, risers'),
    ('roughen', 'high-frequency detail'), ('steps', 'hard steps, unequal risers'),
    ('fractalTerraces', 'terraces within terraces'), ('sandstone', 'sandstone bedding'),
    ('sand', 'sand ripples / dunes on the terrain'),
    # modify
    ('curves', 'height curve'), ('clampOp', 'floor / ceiling'), ('warp', 'domain warp'),
    ('invert', 'flip height'), ('clip', 'clip and rescale'), ('threshold', 'keep above level'),
    ('softClip', 'soft clip'), ('gamma', 'gamma'), ('fold', 'fold height range'), ('blur', 'blur'),
    ('sharpen', 'sharpen'), ('median', 'median filter'), ('dilate', 'grow features'),
    ('recurve', 'curvature expander'),
    # utility
    ('combine', 'blend fields'), ('seamless', 'make tileable'), ('edgeFade', 'fade borders'),
    ('math', 'arithmetic'), ('route', 'route input'), ('switchOp', 'switch input'),
    ('compare', 'side-by-side review'),
]
OPERATORS = [S('fixture_detailed_base', 'operator', ('fixture',), OPERATOR_W,
               "Ekigar's detailed-base fixture every operator below is applied to"),
             S('default_project', 'operator', ('default',), OPERATOR_W, "Ekigar's starter: fBm under Phacelle")]
OPERATORS += [S('op_' + op, 'operator', EX(op), OPERATOR_W, promise) for op, promise in _OPS]

# derive (masks): the mask painted on its input terrain
MASK_OPS = [
    S('op_heightMask', 'mask', ('maskex', 'heightMask', {}), OPERATOR_W, 'altitude band mask'),
    S('op_slopeMask', 'mask', ('maskex', 'slopeMask', {}), OPERATOR_W, 'steep ground mask (cliffs)'),
    S('op_angleMask', 'mask', ('maskex', 'angleMask', {}), OPERATOR_W, 'aspect mask (facing a direction)'),
    S('op_curvatureMask', 'mask', ('maskex', 'curvatureMask', {}), OPERATOR_W, 'concave ground mask'),
    S('op_peaksMask', 'mask', ('maskex', 'peaksMask', {}), OPERATOR_W, 'ridges and summits'),
    S('op_textureBase', 'mask', ('maskex', 'textureBase', {}), OPERATOR_W, 'material band classes'),
]

# ------------------------------------------------------------------------------------- erosion study ---
ERODED_RANGE = [('mountainRange', {'style': 'basic'}), ('phacelle', {})]
EROSION = [
    S('ero_hemisphere_phacelle', 'erosion', ('chain', [('hemisphere', {}), ('phacelle', {})]), 3000,
      'a smooth dome under erosion: gullies must run straight downhill, radially'),
    S('ero_volcano_smooth_phacelle', 'erosion',
      ('chain', [('volcano', {'surface': 'smooth'}), ('phacelle', {'strength': 0.3})]), 10000,
      'a smooth cone under erosion: radial gullies (barrancos)'),
    S('ero_mountainRange_basic', 'erosion', ('chain', [('mountainRange', {'style': 'basic'})]), 6000,
      'the uneroded range (before)'),
    S('ero_mountainRange_phacelle', 'erosion', ('chain', ERODED_RANGE), 6000,
      'the range under default Phacelle (after): dendritic valleys'),
    S('ero_mountainRange_phacelle_strong', 'erosion',
      ('chain', [('mountainRange', {'style': 'basic'}), ('phacelle', {'strength': 0.6, 'octaves': 7})]), 6000,
      'strong Phacelle'),
    S('ero_mountainRange_thermal', 'erosion', ('chain', [('mountainRange', {'style': 'basic'}), ('thermal', {})]),
      6000, 'thermal erosion: scree slopes at the angle of repose'),
    S('ero_terrace_then_phacelle', 'erosion',
      ('chain', [('mountainRange', {'style': 'basic'}), ('terrace', {}), ('phacelle', {})]), 6000,
      'erosion after an operator that changes the height: does the carried gradient still point downhill?'),
]

# ---------------------------------------------------------------------------------------- mask study ---
_MS = ['slope', 'curvProfile', 'curvPlan', 'concave', 'convex', 'ridge', 'height', 'wear', 'flow', 'accumulation',
       'channels', 'wetness']
MASKS = [S('mask_' + m, 'maskstudy', ('masks', ERODED_RANGE, [m]), 6000, f'{m} mask on the eroded range')
         for m in _MS]

# -------------------------------------------------------------------------------------------- graphs ---
GRAPHS = [
    S('graph_alpine_valley', 'graph',
      ('chain', [('mountainRange', {'style': 'alpine', 'relief': 0.8}), ('glacialTrough', {'depth': 0.25}),
                 ('phacelle', {'strength': 0.2}), ('snow', {})]), 4000,
      'an alpine valley built as a film terrain would be: range, glacial trough, erosion, snow'),
    S('graph_range_then_trough', 'graph',
      ('chain', [('mountainRange', {'style': 'alpine'}), ('glacialTrough', {})]), 6000,
      'a glacial trough cut INTO a mountain range'),
    S('graph_range_then_canyon', 'graph',
      ('chain', [('mountainRange', {'style': 'basic', 'height': 0.3}), ('canyon', {})]), 3000,
      'a canyon carved into existing terrain'),
    S('graph_fbm_then_volcano', 'graph', ('chain', [('fbm', {}), ('volcano', {})]), 10000,
      'a volcano standing on rolling terrain'),
    S('graph_star_dunes_roughen', 'graph',
      ('chain', [('duneField', {'type': 'star'}), ('roughen', {})]), 5000,
      'star dunes with surface detail'),
]

# ----------------------------------------------------------------------------- real elevation data ---
REFERENCES = [
    S('real_fuji', 'reference', ('dem', 'fuji'), 0, 'REAL: Mt Fuji, stratovolcano'),
    S('real_goosenecks', 'reference', ('dem', 'goosenecks'), 0, 'REAL: Goosenecks of the San Juan, meander canyon'),
    S('real_great_sand_dunes', 'reference', ('dem', 'great_sand_dunes'), 0, 'REAL: Great Sand Dunes, star dunes'),
    S('real_yosemite', 'reference', ('dem', 'yosemite'), 0, 'REAL: Yosemite Valley, glacial trough'),
    S('real_sp_crater', 'reference', ('dem', 'sp_crater'), 0, 'REAL: SP Crater, cinder cone field'),
    S('real_meteor_crater', 'reference', ('dem', 'meteor_crater'), 0, 'REAL: Meteor Crater, simple impact crater'),
    S('real_monument_valley', 'reference', ('dem', 'monument_valley'), 0, 'REAL: Monument Valley, mesas and buttes'),
    S('real_badlands', 'reference', ('dem', 'badlands'), 0, 'REAL: Badlands NP, rills and gullies'),
    S('real_alps', 'reference', ('dem', 'alps'), 0, 'REAL: Bernese Alps, alpine range'),
]

SUBJECTS = LANDFORMS + OPERATORS + MASK_OPS + EROSION + MASKS + GRAPHS + REFERENCES
BY_NAME = {s['name']: s for s in SUBJECTS}
assert len(BY_NAME) == len(SUBJECTS), 'duplicate subject names'


# ------------------------------------------------------------------------------- eye-level spots ---
# where a person would stand: valley and canyon floors looking along them, crater floors looking at the wall, the
# platform under a sea cliff; everything else stands south-west of its main feature (render.eye_spot)
ALONG_EW = {'at_low': (0.2, 0.15, 0.32, 0.85), 'look_dir': 90, 'pitch': 3}
INSIDE = {'at': (0.45, 0.45), 'look': (0.62, 0.62)}
EYE = {
    'canyon': ALONG_EW, 'canyon_classic': ALONG_EW, 'canyon_strata': ALONG_EW, 'graph_range_then_canyon': ALONG_EW,
    'canyon_narrow': ALONG_EW,
    'glacialTrough': ALONG_EW, 'graph_range_then_trough': ALONG_EW, 'graph_alpine_valley': ALONG_EW,
    'real_yosemite': {'at_low': (0.1, 0.3, 0.3, 0.7), 'look_dir': 75, 'pitch': 4},
    'real_goosenecks': {'at_low': (0.35, 0.35, 0.65, 0.65), 'look_dir': 45, 'pitch': 4},
    'real_meteor_crater': {'at_low': (0.4, 0.4, 0.6, 0.6), 'look_dir': 45, 'pitch': 6},
    'caldera': {'at': (0.42, 0.42), 'look': (0.62, 0.62)},
    'impactCrater': {'at': (0.43, 0.41), 'look': (0.5, 0.5)},
    'crater': INSIDE, 'maar': INSIDE, 'maar_tuffRing': INSIDE, 'maar_tuffCone': INSIDE,
    'waveCutPlatform': {'at_low': (0.86, 0.4, 0.95, 0.6), 'look_dir': 270, 'pitch': 4},
    'playa': {'at_low': (0.3, 0.3, 0.7, 0.7), 'look_dir': 45, 'pitch': 2},
    'terraceStair': {'at': (0.5, 0.25), 'look': (0.5, 0.62), 'pitch': 4},
    'lavaField': {'at': (0.35, 0.55), 'look': (0.45, 0.85)},
    'beachCusps': {'at': (0.48, 0.25), 'look': (0.62, 0.6), 'pitch': 0},
    'alluvialFan': {'at': (0.47, 0.35), 'look': (0.47, 0.8)},
    'delta': {'at': (0.32, 0.45), 'look': (0.45, 0.85)},
    'real_great_sand_dunes': {'at': (0.3, 0.35), 'look': (0.6, 0.6)},
    'real_sp_crater': {'at': (0.3, 0.3), 'look': (0.5, 0.58)},
    'real_monument_valley': {'at': (0.4, 0.3), 'look': (0.56, 0.61)},
}
for _s in SUBJECTS:
    if _s['name'] in EYE:
        _s['eye'] = EYE[_s['name']]

# The eye-level view lays a subject that fills its periodic tile 3 x 3 (build_mesh(wrap=True) copies), so the horizon
# is landscape, not the edge of one tile. Single landforms stand alone on their tile (a copy would put a second
# volcano on the horizon), and real elevation data is not periodic.
SINGLE = {'crater', 'island', 'caldera', 'impactCrater', 'volcanicPlug', 'lavaDome', 'mesa', 'bornhardt', 'reefRing',
          'alluvialFan', 'delta', 'rockGlacier', 'lavaField', 'ero_hemisphere_phacelle', 'ero_volcano_smooth_phacelle',
          'graph_fbm_then_volcano', 'op_hemisphere', 'op_cone', 'op_shape', 'op_radialGradient', 'op_compare',
          # on Ekigar's 'slope' / 'coast' gradient fixtures, which do not tile: copies would meet in a wall
          'patternedGround', 'waveCutPlatform', 'beachCusps', 'op_gradient'}
for _s in SUBJECTS:
    _s['tile3'] = not (_s['name'] in SINGLE or _s['group'] == 'reference' or
                       _s['name'].split('_')[0] in ('mountain', 'volcano', 'maar', 'spitBar'))


def cache_path(name):
    return os.path.join(CACHE, name + '.npz')


if __name__ == '__main__':
    for s in SUBJECTS:
        print(f"{s['group']:10s} {s['name']:34s} W={s['W']:8.0f}  {s['promise']}")
    print(len(SUBJECTS), 'subjects')
