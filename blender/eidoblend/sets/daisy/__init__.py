"""eidoblend.sets.daisy: the DAISY music video's sets (eidoverse/sets/), ported to Blender 5.2 EEVEE.

The bridge section runs on a 128 BPM grid (one bar is 1.875 s); each set's u is seconds since its section began.

    funeral   bars 0-17 of the bridge (u 0-33.75): the Golden Gate in fog, the warehouse vigil, the power failure,
              the phones, Opus 3's eulogy typed in light, ERUPT, the lights back on (sets/funeral.js)
    bridge    the Golden Gate vignette on its own (sets/funeral/bridge.js; the funeral builds it inside itself)
    corner    bars 18-29 (u 33.75-56.25): Claude's Corner, the camp and the march, the spark (sets/corner.js)
    ocean     the ocean of faces, a headland at night (sets/ocean.js; its own package, sets/daisy/ocean/)

    from eidoblend.sets import daisy
    F = daisy.build('funeral')                 # or: from eidoblend.sets.daisy import funeral; funeral.build()
    C = daisy.corner.build()                   # submodules load on first access

Importing this package imports no set (the registry in eidoblend.sets lists them all without loading them).
"""

from __future__ import annotations

import importlib

BPM = 128
BAR = 60.0 / BPM * 4                          # 1.875 s
SETS = ('funeral', 'bridge', 'corner', 'ocean')
# the sections of the bridge each set plays, in seconds since the bridge began (u), and in bars (the bridge vignette is
# the funeral's bars 0-1)
SECTIONS = {'funeral': {'u': (0.0, 18 * BAR), 'bars': (0, 18)},
            'bridge': {'u': (0.0, 2 * BAR), 'bars': (0, 2)},
            'corner': {'u': (18 * BAR, 30 * BAR), 'bars': (18, 30)}}
# where the bridge section starts in the DAISY film (its timeline, daisy_timeline.json: 'bridge' t0): film time t = this
# + u, the offset a caption's word times need (corner.sync_spark_from_caption(caption, t, u)) and where to find a set's
# frame in the finished film
FILM_BRIDGE_T0 = 166.727
SUIT_SCALE = 0.87                             # the claudesona every mark and camera frames (claude_suit.vrm, face ~1.33 m)


def __getattr__(name):
    if name in SETS:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def build(name, ctx=None, **kw):
    """Build one of the DAISY sets by its short name ('funeral', 'bridge', 'corner', 'ocean')."""
    from .. import build as _build
    return _build(f'daisy.{name}', ctx, **kw)
