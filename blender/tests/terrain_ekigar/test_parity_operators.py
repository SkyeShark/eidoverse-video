"""Every registry operator (and every enum arm, named output, mask wire, warp, disabled node and blend mode) evaluated
by Ekigar's own code and by the port, compared to float tolerance.

    python blender/tests/terrain_ekigar/test_parity_operators.py [grid]

Prints a PASS/FAIL line per probe. The landform library has its own test (test_parity_landforms.py).
"""
import sys

import parity_lib as L
from parity_lib import node, edge, probe, gen, filt, base_terrain


def probes():
    ps = []
    # primitives standing alone
    for op in ('constant', 'gradient', 'radialGradient', 'fbm', 'ridged', 'voronoi', 'perlin', 'cellular',
               'dotNoise', 'lineNoise', 'cracks', 'shape', 'cone', 'hemisphere', 'pattern'):
        ps.append(gen(op))
    ps.append(gen('gradient', {'angle': 0.7, 'scale': -1.3}, 'angled'))
    ps.append(gen('radialGradient', {'centre': [0.2, 0.9], 'radius': 0.6, 'falloff': 2.5}, 'offcentre'))
    ps.append(gen('fbm', {'frequency': 3.3, 'octaves': 5}, 'snapped'))
    ps.append(gen('ridged', {'sharpness': 2.2, 'octaves': 6}, 'sharp'))
    ps.append(gen('voronoi', {'mode': 'f2-f1'}, 'f2f1'))
    ps.append(gen('voronoi', {}, '', 'cells'))
    for t in ('fbm', 'ridged', 'billowy'):
        ps.append(gen('perlin', {'type': t, 'seed': 11}, t))
    for m in ('euclidianManhattan', 'euclidianChebyshev'):
        for fn in ('hash', 'distanceInv', 'distance2Inv', 'distanceDiff', 'distanceToEdge'):
            ps.append(gen('cellular', {'distanceMetric': m, 'distanceFunction': fn, 'metricMorph': 0.6, 'seed': 3},
                          f'{m}_{fn}'))
    ps.append(gen('cellular', {}, '', 'cells'))
    ps.append(gen('dotNoise', {'style': 'square', 'iterations': 3}, 'square'))
    for s in ('sharp', 'soft', 'flat', 'vague'):
        ps.append(gen('lineNoise', {'style': s, 'direction': 90, 'seed': 5}, s))
    for s in ('normal', 'hard', 'classic'):
        ps.append(gen('cracks', {'style': s, 'octaves': 3}, s))
    ps.append(gen('cracks', {}, '', 'cracks'))
    ps.append(gen('shape', {'geometry': 'rectangle', 'scaleX': 1.5}, 'rect'))
    ps.append(gen('shape', {'sides': 6, 'thickness': 0.3}, 'hexring'))
    ps.append(gen('hemisphere', {'flatten': True}, 'flat'))
    for t in ('lines', 'engraving', 'grid', 'dots'):
        ps.append(gen('pattern', {'type': t, 'direction': 90}, t))
    # filters on a varied terrain (Ekigar's smoke-test chain)
    for op in ('phacelle', 'thermal', 'snow', 'crater', 'terrace', 'stratify', 'curves', 'clampOp', 'roughen',
               'heightMask', 'slopeMask', 'angleMask', 'curvatureMask', 'peaksMask', 'textureBase', 'seamless',
               'edgeFade', 'invert', 'clip', 'threshold', 'softClip', 'gamma', 'fold', 'blur', 'sharpen', 'median',
               'dilate', 'recurve', 'steps', 'fractalTerraces', 'sandstone', 'sand', 'mountain', 'mountainRange',
               'canyon', 'island', 'volcano', 'rugged', 'math'):
        ps.append(filt(op))
    for port in ('wear', 'ridge', 'flow'):
        ps.append(filt('phacelle', {}, '', port))
    ps.append(filt('phacelle', {'scale': 0.2, 'octaves': 5, 'strength': 0.3, 'offset': 0.2, 'preserve': 0.3}, 'strong'))
    ps.append(filt('thermal', {}, '', 'talus'))
    ps.append(filt('snow', {'line': 0.4}, 'low', 'depth'))
    ps.append(filt('crater', {}, '', 'rim'))
    ps.append(filt('crater', {}, '', 'ejecta'))
    ps.append(filt('stratify', {}, '', 'layers'))
    ps.append(filt('sandstone', {'passes': 3, 'direction': 90}, 'p3', 'layers'))
    ps.append(filt('canyon', {}, '', 'depth'))
    for st in ('classic', 'strata'):
        ps.append(filt('canyon', {'style': st, 'direction': 0, 'meanders': 3}, st))
    for port in ('crater', 'rim', 'breach'):
        ps.append(filt('volcano', {'breachWidth': 40, 'breachDir': 60}, 'breach', port))
    for prof in ('cone', 'shield', 'pyroclasticShield'):
        ps.append(filt('volcano', {'profile': prof, 'surface': 'smooth'}, prof))
    for st in ('basic', 'old', 'alpine', 'strata'):
        ps.append(filt('mountain', {'style': st, 'bulk': 'high'}, st))
    ps.append(filt('mountain', {'reduceDetails': True, 'bulk': 'low'}, 'reduced'))
    for st in ('basic', 'stratified', 'alpine'):
        ps.append(filt('mountainRange', {'style': st, 'octaves': 5}, st))
    for st in 'bcde':
        ps.append(filt('rugged', {'style': st}, st))
    for m in ('add', 'subtract', 'divide', 'power', 'min', 'max', 'abs', 'oneMinus', 'sqrt', 'floor', 'fract'):
        ps.append(filt('math', {'operation': m, 'value': 0.6 if m != 'floor' else 7}, m))
    for m in ('concave', 'convex', 'profile', 'plan', 'mean'):
        ps.append(filt('curvatureMask', {'mode': m, 'gain': 4}, m))
    ps.append(filt('textureBase', {'reverse': True, 'accentuate': 0.9}, 'rev'))
    ps.append(filt('seamless', {'shiftX': 0.25, 'shiftY': 0.5, 'edge': 0.3}, 'shift'))
    ps.append(filt('edgeFade', {'style': 'round'}, 'round'))
    ps.append(filt('softClip', {'clipMode': 'belowThreshold'}, 'below'))
    for w in ('triangle', 'sawtooth'):
        ps.append(filt('fold', {'waveform': w}, w))
    ps.append(filt('fold', {'waveform': 'triangle', 'symmetric': True}, 'sym'))
    ps.append(filt('blur', {'radius': 6}, 'r6'))
    ps.append(filt('sharpen', {'method': 'frequency'}, 'freq'))
    ps.append(filt('median', {'mode': 'classic'}, 'classic'))
    for k in ('rectangle', 'line', 'lineVertical'):
        ps.append(filt('dilate', {'kernel': k}, k))
    ps.append(filt('dilate', {'invert': True, 'iterations': 2}, 'erode2'))
    ps.append(filt('recurve', {'style': 'inward'}, 'inward'))
    ps.append(filt('clampOp', {'mode': 'normalized', 'lo': 0.3, 'hi': 0.7}, 'norm'))
    ps.append(filt('clampOp', {'drop': True, 'lo': 0.4}, 'drop'))
    ps.append(filt('terrace', {'uniformity': 0.4, 'seed': 9, 'intensity': 0.7}, 'jitter'))
    ps.append(filt('sand', {'warpByTerrain': 0.6, 'direction': 90}, 'warped'))
    # warp threads the position into the generator downstream
    a = node('warp', {'frequency': 3, 'strength': 0.2})
    b = node('ridged')
    ps.append(probe('warp_then_ridged', [a, b], [edge(a, b)], b))
    a = node('warp')
    ps.append(probe('warp_alone', [a], [], a))
    # a mask wire confines a filter
    t0, t1, es = base_terrain()
    m = node('heightMask', {'lo': 0.45, 'hi': 2, 'falloff': 0.05})
    er = node('phacelle', {'strength': 0.4})
    ps.append(probe('phacelle_masked_by_height', [t0, t1, m, er], es + [edge(t1, m), edge(t1, er), edge(m, er, 'mask')],
                    er))
    # a named output as the mask (crater rim confines a roughen)
    t0, t1, es = base_terrain()
    c = node('crater')
    r = node('roughen', {'amplitude': 0.1})
    ps.append(probe('roughen_masked_by_crater_rim', [t0, t1, c, r],
                    es + [edge(t1, c), edge(c, r), {'from': {'node': c['id'], 'port': 'rim'},
                                                    'to': {'node': r['id'], 'port': 'mask'}}], r))
    # a disabled node is a pass-through
    t0, t1, es = base_terrain()
    d = node('terrace', disabled=True)
    ps.append(probe('disabled_terrace', [t0, t1, d], es + [edge(t1, d)], d))
    # Combine: every mode, three inputs, clamp output
    import importlib
    ek = L._ekigar_load.load()
    for mode in importlib.import_module(f'{ek.__name__}.ops_shared').COMBINE_MODE_VALUES:
        a = node('fbm', {'frequency': 3, 'amplitude': 0.8})
        b = node('ridged', {'frequency': 5})
        c = node('combine', {'mode': mode, 'amount': 0.7})
        ps.append(probe(f'combine_{mode}', [a, b, c], [edge(a, c), edge(b, c, 'in2')], c))
    a = node('fbm')
    b = node('ridged')
    c3 = node('voronoi')
    c = node('combine', {'mode': 'multiply', 'output': 'clamp'})
    ps.append(probe('combine_three_clamped', [a, b, c3, c], [edge(a, c), edge(b, c, 'in2'), edge(c3, c, 'in3')], c))
    # route / switch / compare
    a = node('fbm')
    b = node('ridged')
    rt = node('route', {'choice': 2})
    ps.append(probe('route_2', [a, b, rt], [edge(a, rt, 'in1'), edge(b, rt, 'in2')], rt))
    sw = node('switchOp', {'switchRoute': True})
    a = node('fbm')
    b = node('ridged')
    ps.append(probe('switch_true', [a, b, sw], [edge(a, sw), edge(b, sw, 'in2')], sw))
    for perp, swap in ((False, False), (True, True)):
        a = node('fbm')
        b = node('ridged')
        cp = node('compare', {'perpendicular': perp, 'swap': swap, 'ab': 0.35})
        ps.append(probe(f'compare_{int(perp)}{int(swap)}', [a, b, cp], [edge(a, cp), edge(b, cp, 'in2')], cp))
    # Texture Base with a guide
    t0, t1, es = base_terrain()
    gd = node('radialGradient')
    tb = node('textureBase')
    ps.append(probe('textureBase_guided', [t0, t1, gd, tb], es + [edge(t1, tb), edge(gd, tb, 'guide')], tb))
    # x-only tiling (the ring band) and a non-periodic tile
    ps.append(dict(filt('phacelle', {}, 'tile_x_only'), tile={'x': 1, 'y': 0}))
    ps.append(dict(filt('seamless', {}, 'nonperiodic'), tile={'x': 0, 'y': 0}))
    ps.append(dict(gen('fbm', {'frequency': 3.3}, 'tile2'), tile={'x': 2, 'y': 2}))
    return ps


if __name__ == '__main__':
    grid = int(sys.argv[1]) if len(sys.argv) > 1 else 48
    ok = L.report(L.run(probes(), grid=grid), 'operators')
    sys.exit(0 if ok else 1)
