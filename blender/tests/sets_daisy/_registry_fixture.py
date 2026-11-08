"""test_registry.py's stand-in set builders (plain Python): the three builder shapes the registered sets have, so
sets.build() can be checked placing the harness ctx without Blender."""


def build_ctx(ctx=None, **kw):
    """the DAISY sets, bin, race, quiet_room, showroom: build(ctx=None, ...)"""
    return {'ctx': ctx, **kw}


def build_scene(scene=None, opts=None, collection=None, name='set'):
    """the corridor and the news: build(scene=None, opts=None, ...)"""
    return {'scene': scene, 'opts': opts, 'name': name}


def build_opts(opts=None, **kw):
    """the city and the hole: build(opts=None, **kw)"""
    return {'opts': opts, **kw}
