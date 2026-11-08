"""eidoblend.harness.showpiece: the palette report's showpiece nudge (render_scene.mjs), plain Python.

A full-length production (15 s or more) that used no showpiece or procedural family gets the specific flagships its
content asks for: trigger words in its object and material names and its _brief.txt name the fitting one (a bar scene
with a coffee mug and no pour gets the liquid), or the general menu when nothing matches. INFO only, a creative
pointer and never a re-render demand: the digest's 'palette.showpiece' record. The engine's tools registered
themselves in _eidoToolUsage; here the families a scene imported stand for them.
"""

from __future__ import annotations

import os

# the families whose use counts as a showpiece or procedural tool (the engine's self-registering tools: particles,
# particle morph, loft, fluids, cloth, terrain, SeedThree trees, and the SDF solids)
SHOWPIECE_FAMILIES = ('eidoblend.fx', 'eidoblend.terrain', 'eidoblend.trees', 'eidoblend.sdf')
SHOWPIECES = (
    ('eidoblend.fx.swe (heightfield liquid: pools, pours with stream and spray, whitewater)',
     ('water', 'liquid', 'pour', 'drink', 'coffee', 'tea', 'juice', 'potion', 'beer', 'wine', 'cocktail', ' bar ',
      'kitchen', ' lab', 'chemical', 'fountain', 'splash', 'flood', 'blood', ' oil', 'milk', 'soup', 'elixir',
      'serum')),
    ('eidoblend.fx.cloth (flags, banners, capes, curtains, fabric, with collision and text on cloth)',
     ('flag', 'banner', 'cape', 'curtain', 'fabric', 'cloth', ' sail', 'tapestry', 'drape', 'tablecloth', ' robe',
      'scarf', ' veil', 'awning')),
    ('eidoblend.terrain.loft (vases, horns, pipes, ducts, columns, ornament, ribbons)',
     ('vase', ' horn', ' pipe', ' duct', 'column', 'pillar', 'ornament', 'spiral', 'ribbon', 'bottle', 'goblet',
      'trumpet', 'vessel', ' urn', 'chalice', 'tentacle', 'archway')),
    ('eidoblend.fx.particle_morph (dissolve and reform any mesh, text, or a VRM mid-pose)',
     ('dissolve', 'transform', 'materializ', 'reform', 'shatter', 'disintegrat', ' morph', 'assemble', 'teleport',
      'reveal', 'manifest', 'emerge')),
    ('eidoblend.fx.particles (smoke, fire, sparks, dust, embers, magic)',
     ('smoke', ' fire', 'spark', 'ember', ' dust', 'magic', 'flame', 'explos', ' glow', 'firefly', ' ash', 'steam',
      'incense')),
)
MIN_DURATION = 15.0      # s: the engine nudged full-length productions only


def brief_text(scene_json=None, repo=None):
    """The production's _brief.txt, if there is one: beside the scene config, else at the repository root (the
    engine read it from its working directory, the repository root)."""
    dirs = ([os.path.dirname(scene_json)] if scene_json else []) + ([repo] if repo else [])
    for d in dirs:
        p = os.path.join(d, '_brief.txt')
        if os.path.isfile(p):
            try:
                with open(p, encoding='utf-8', errors='replace') as f:
                    return f.read()
            except OSError:
                pass
    return ''


def showpiece_nudge(scene, duration, modules, brief=''):
    """(message, [fitting showpieces]) or None. scene: anything with .objects (each with .name and material_slots);
    modules: the eidoblend modules the scene imported."""
    if duration < MIN_DURATION or any(m == f or m.startswith(f + '.') for m in modules for f in SHOWPIECE_FAMILIES):
        return None
    names = [o.name for o in scene.objects]
    mats = [s.material.name for o in scene.objects for s in getattr(o, 'material_slots', []) if s.material]
    blob = (' ' + ' '.join(names + mats) + ' ' + (brief or '')).lower()
    hits = [name for name, words in SHOWPIECES if any(w in blob for w in words)]
    if hits:
        return ("This scene's content reads like it WANTS a showpiece and used none. Strong fit for what's in it: "
                + '  •  '.join(hits) + ". These are the toolkit's flagships and almost no production reaches for "
                'them; weaving the matching one in is usually the line between "fine" and "memorable". (Creative '
                'call, not a hard gate, but a pointed one.)'), hits
    return ('note: no simulation or particle showpiece in this production. The under-used flagships (see '
            'tools-guides/production.md, choose techniques for the story): eidoblend.fx.swe (liquid), '
            'eidoblend.fx.cloth (fabric), eidoblend.terrain.loft (lofted forms), eidoblend.fx.particles, '
            'eidoblend.fx.particle_morph (dissolve and reform any mesh). One showpiece is often the difference '
            'between fine and memorable. Your call.'), []
