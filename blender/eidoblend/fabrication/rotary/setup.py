"""Setup datums for the captured-jaw, sliding-tailstock G430 rotary fixture: the port of
eidoverse/robotics/rotary_setup.js (rotaryFixtureSetup). Plain arithmetic, no scene needed.

    from eidoblend.fabrication.rotary.setup import rotary_fixture_setup
    s = rotary_fixture_setup(stock_length=0.12, stock_width=0.03, stock_height=0.04, quill=0.002)
    s['axis_x'], s['axis_height'], s['start'], s['end']     # the A axis in machine X and above the bed; cut interval
    machine.set_joints(s['joints'])                           # jaws closed on the blank, tailstock + quill on its end

Machine coordinates (Blender, Z up, metres): X along the rotary axis, Z up from the bed top. The stock's long edge runs
along X, its width along Y and its height along Z. Other keyword options are ignored (the WebGPU edition destructures
the same options object every rotary call receives).
"""

from __future__ import annotations

import math


def rotary_fixture_setup(stock_length: float = .140, stock_width: float = .036, stock_height: float = .036,
                         quill: float = 0.0, **_options) -> dict:
    """Validate a blank for the fixture and return its datums and the fixture joints that hold it."""
    vals = (stock_length, stock_width, stock_height, quill)
    if not all(isinstance(v, (int, float)) and math.isfinite(v) for v in vals):
        raise ValueError('Rotary stock dimensions and quill travel must be finite')
    if (stock_length < .080 - 1e-9 or stock_length > .180 + 1e-9 or
            min(stock_width, stock_height) < .018 - 1e-9 or max(stock_width, stock_height) > .050 + 1e-9):
        raise ValueError('Fixture accepts 80–180 mm long stock, 18–50 mm wide and high')
    tailstock = stock_length - .140 - quill
    if abs(quill) > .006 + 1e-9 or tailstock < -.060 - 1e-9 or tailstock > .040 + 1e-9:
        raise ValueError('Tailstock carriage or quill exceeds its captured travel')
    return {
        'stock_length': stock_length,
        'stock_width': stock_width,
        'stock_height': stock_height,
        'quill': quill,
        'axis_x': -.055 + stock_length / 2,
        'axis_height': .097,
        'start': -stock_length / 2 + .029,
        'end': stock_length / 2 - .018,
        'joints': {
            'rotary_tailstock': tailstock,
            'rotary_quill': quill,
            'rotary_handwheel': -quill / .001 * 2 * math.pi,
            'rotary_jaw_0': stock_height / 2 - .018,
            'rotary_jaw_2': stock_height / 2 - .018,
            'rotary_jaw_1': stock_width / 2 - .018,
            'rotary_jaw_3': stock_width / 2 - .018,
        },
    }
