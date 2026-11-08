"""eidoblend.fabrication.fab_sim: the G430 CNC / FDM simulation facade (fab_sim.js, MIT).

    from eidoblend.fabrication import FabSim, PrintSim, CNCSim
    job = FabSim.print(printer, source, duration=18)       # PrintSim.print(...) is the same call
    job = CNCSim.carve(cnc_relief, FabSim.sample_relief(), material='wood', duration=24)
    FabSim.stock_materials()                               # the material table

The WebGPU facade is asynchronous because it imports the module on first use; here every method is an ordinary call
(ready() returns the module). The rotary methods forward to eidoblend.fabrication.rotary, the stock-rotating machine's
own package.
"""

from __future__ import annotations


def _module():
    from . import processes
    return processes


def _rotary(name):
    from . import rotary
    return getattr(rotary, name)


class _FabSim:
    def ready(self):
        import sys
        return sys.modules[__package__]

    def print(self, *a, **k):
        return _module().print(*a, **k)

    def carve(self, *a, **k):
        return _module().carve(*a, **k)

    def mill(self, *a, **k):
        return _module().mill(*a, **k)

    def rotary_carve(self, *a, **k):
        return _rotary('rotary_carve')(*a, **k)

    def rotary_program(self, *a, **k):
        return _rotary('rotary_program')(*a, **k)

    def rotary_mesh_program(self, *a, **k):
        return _rotary('rotary_mesh_program')(*a, **k)

    def source_geometry(self, *a, **k):
        from .source_geometry import source_geometry
        return source_geometry(*a, **k)

    def fit_source_geometry(self, *a, **k):
        from .source_geometry import fit_source_geometry
        return fit_source_geometry(*a, **k)

    def sample_rotary(self):
        return _rotary('sample_rotary')

    def pocket_program(self, *a, **k):
        return _module().pocket_program(*a, **k)

    def relief_program(self, *a, **k):
        from .relief import relief_program
        return relief_program(*a, **k)

    def relief_from_mesh(self, *a, **k):
        from .relief import relief_from_mesh
        return relief_from_mesh(*a, **k)

    def sample_relief(self):
        from .relief import sample_relief
        return sample_relief

    def stock_materials(self):
        from .cutting import STOCK_MATERIALS
        return STOCK_MATERIALS


class _PrintSim:
    def print(self, *a, **k):
        return FabSim.print(*a, **k)


class _CNCSim:
    def carve(self, *a, **k):
        return FabSim.carve(*a, **k)

    def mill(self, *a, **k):
        return FabSim.mill(*a, **k)

    def rotary_carve(self, *a, **k):
        return FabSim.rotary_carve(*a, **k)


FabSim = _FabSim()
PrintSim = _PrintSim()
CNCSim = _CNCSim()
