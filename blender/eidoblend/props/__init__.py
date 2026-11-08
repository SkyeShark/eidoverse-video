"""eidoblend.props: the DAISY film's finished props, built by name (eidoverse/props/, ported): the eight voice machines
and the 1896 tandem.

    import sys; sys.path.insert(0, '<repo>/blender')
    from eidoblend import props

    props.NAMES                        # the eight voice machines, 1939 -> 2001, and the 1896 tandem
    c64 = props.build('c64')           # a voice machine: group (its root Empty), parts, update(t, state), dispose()
    mod = props.load('voder')          # the module itself (its build() and any extras, e.g. the Voder's pattern(t))
    from eidoblend.props import voice_machines, tandem      # the subpackage and the tandem's module, directly

Nothing is imported until it is asked for: this registry maps names to modules and loads one on demand, so reading
NAMES or REGISTRY needs neither Blender nor any prop's module. Guides: tools-guides/voice-machines.md (the machines),
tools-guides/props-and-sets.md (the tandem and the sets).
"""
from __future__ import annotations

import importlib

VOICE_MACHINES = ('voder', 'mainframe', 'teletype', 'speakspell', 'c64', 'mac1984', 'dectalk', 'desktop2001')

REGISTRY = {name: f'{__name__}.voice_machines.{name}' for name in VOICE_MACHINES}
REGISTRY['tandem'] = f'{__name__}.tandem'

NAMES = list(REGISTRY)


def load(name: str):
    """The module that builds one prop (props/voice_machines/<name>.py or props/tandem.py), imported on first use."""
    if name not in REGISTRY:
        raise ValueError(f"[props] unknown prop '{name}' (have: {', '.join(NAMES)})")
    if name in VOICE_MACHINES:
        from . import voice_machines
        return voice_machines.load_machine(name)
    try:
        return importlib.import_module(REGISTRY[name])
    except ModuleNotFoundError as e:
        if e.name == REGISTRY[name]:
            raise ModuleNotFoundError(f"[props] '{name}' is registered but {REGISTRY[name]} is not written yet") from e
        raise


def call_build(build, opts: dict):
    """Call a prop module's build with the options: as keywords when it takes them (build(**opts)), as one options
    dict when its first parameter is that dict (``def build(opts)``, the JS form), else a TypeError naming the
    options it does not take. Ports of the WebGPU build(THREE, opts) take either form."""
    from .voice_machines import _call_build
    return _call_build(build, opts)


def build(prop: str, opts: dict = None, /, **kw):
    """Build one prop by name. Voice machines go through voice_machines.build_machine (it stamps the root with the
    machine's record); the tandem through its module's build. Options as a dict, keywords, or both."""
    o = dict(opts or {})
    o.update(kw)
    if prop in VOICE_MACHINES:
        from . import voice_machines
        return voice_machines.build_machine(prop, o)
    return call_build(load(prop).build, o)
