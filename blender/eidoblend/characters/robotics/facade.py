"""eidoblend.characters.robotics.facade: robotics_kit.js, the RoboticsKit facade and makeBot, in Blender.

The WebGPU edition injects an asynchronous facade into every scene (globalThis.RoboticsKit, makeRobot, makeBot) and
imports index.js on first use. Blender's Python is synchronous and imports on demand, so the facade is a plain object:

    RoboticsKit.version                 1
    RoboticsKit.ready()                 the loader module (kit), as ready() resolves to index.js
    RoboticsKit.catalog()               catalog.json
    RoboticsKit.load(id, **opts)        make_robot
    RoboticsKit.load_part(id, part, **opts)
    RoboticsKit.connect(parent, child, port, child_port, twist=0)    parent.attach(child, ...)
    RoboticsKit.create_ptfe_tube(**opts) / service_loop(...)   filament.js's, which index.js re-exports: the
                                        fabrication port registers them in FABRICATION when imported, and the first
                                        call imports it; without that package they raise and say so
    make_bot(model='humanoid', **opts)  makeBot({model, ...options})
"""

from __future__ import annotations

from . import kit

FABRICATION = {}            # {'create_ptfe_tube': fn, 'service_loop': fn}: set by the fabrication port (filament.js)


def _fabrication(name):
    fn = FABRICATION.get(name)
    if fn is None and kit._import_fabrication():            # index.js re-exports them from filament.js: always there
        fn = FABRICATION.get(name)
    if fn is None:
        raise NotImplementedError(f'{name} is filament.js\'s (PTFE service tubing): the fabrication port provides it '
                                  "and registers it in eidoblend.characters.robotics.facade.FABRICATION")
    return fn


def connect(parent, child, port, child_port, twist=0.0):
    return parent.attach(child, port=port, child_port=child_port, twist=twist)


def create_ptfe_tube(**opts):
    return _fabrication('create_ptfe_tube')(**opts)


def service_loop(*a, **kw):
    return _fabrication('service_loop')(*a, **kw)


def make_bot(model='humanoid', **opts):
    """makeBot: a catalog model (default the humanoid) with the usual loader options"""
    return kit.load_robot(model, **opts)


class _RoboticsKit:
    version = 1

    @staticmethod
    def ready():
        return kit

    @staticmethod
    def catalog():
        return kit.catalog()

    @staticmethod
    def load(rid, **opts):
        return kit.load_robot(rid, **opts)

    @staticmethod
    def load_part(model_id, name, **opts):
        return kit.load_part(model_id, name, **opts)

    create_ptfe_tube = staticmethod(create_ptfe_tube)
    service_loop = staticmethod(service_loop)
    connect = staticmethod(connect)


RoboticsKit = _RoboticsKit()
