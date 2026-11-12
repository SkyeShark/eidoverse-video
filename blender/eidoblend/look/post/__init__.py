"""eidoblend.look.post: the post chain in the compositor (chain.py: its slots prebloom, bloom, under, overlay, over),
the effect registry (custom_effects.py: every WebGPU effect by name, apply_to / register) and its passes: era_looks.py
(graphic-arts looks from the history of computing), aeropittura.py (UNKNOWN FORCE's futurist painting), after_image.py
(three's afterImage), screen_effects.py (the smaller screen-space effects); history.py (earlier frames through the
disk), display.py (display space through the scene's view transform), _graph.py (the expression layer the shaders are
ported through).

    from eidoblend.look.post import custom_effects as FX
    fx = FX.apply_to(scene, 'vhs_tape, old_bw_film')       # or post.custom_effects, imported on first use

Each module is imported on first use. Guide: tools-guides/postprocessing.md."""

import importlib

MODULES = ('chain', 'custom_effects', 'era_looks', 'aeropittura', 'after_image', 'screen_effects', 'history',
           'display')


def __getattr__(name):
    if name in MODULES:
        return importlib.import_module(f'{__name__}.{name}')
    raise AttributeError(f'module {__name__!r} has no attribute {name!r}')


def __dir__():
    return sorted(set(globals()) | set(MODULES))
