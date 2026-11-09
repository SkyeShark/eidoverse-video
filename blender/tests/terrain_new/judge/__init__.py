"""The terrain judge (DESIGN.md section 10; package 2): a generated terrain beside the real place it is named for.

    import sys; sys.path.insert(0, '<worktree>/blender/tests/terrain_new')
    from judge import judge
    v = judge(t, 'mount_fuji')                  # t: a Terrain, a dict(h=, cell=, ...), an .npz path or (h, cell)
    print(v.table())                            # every number beside the reference's, its band, PASS / FAIL
    v.passed, v.failures                        # the verdict and the reasons

From the command line (numbers, bands, renders and the compare sheet in one go): judge/run.py (its doc).
Modules: refs (the references in the terrain frame), match (onto the reference's grid), generic (section 10 item
2, on core/metrics.py), family (item 4), bands (item 3, bands.json), judging (judge()), views (eye spots, Blender
renders), sheet (the compare sheet), video (the review videos), calibrate (writes bands.json).
"""
import importlib

_EXPORTS = {'judge': ('.judging', 'judge'), 'Verdict': ('.judging', 'Verdict'),
            'load_reference': ('.refs', 'load'), 'reference_names': ('.refs', 'names'),
            'RECIPE_REFERENCES': ('.refs', 'RECIPE_REFERENCES')}
__all__ = sorted(_EXPORTS)


def __getattr__(name):
    if name not in _EXPORTS:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    mod, attr = _EXPORTS[name]
    value = getattr(importlib.import_module(mod, __name__), attr)
    globals()[name] = value
    return value
