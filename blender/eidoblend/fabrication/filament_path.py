"""eidoblend.fabrication.filament_path: direct-drive retraction / prime dwells and conserved filament volume
(filament_path.js, MIT).

    path = FilamentPath(feed_path, filament_diameter=0.00175, retract_length=0.0008, retract_speed=0.035)
    s = path.sample(t)   # the FeedPath state plus filament_length, filament_position, filament_retraction,
                         # filament_speed; type is 'retract' / 'prime' during a dwell (the nozzle stands still)

A retraction starts every rapid that follows an extrusion and a prime ends it before the next extrusion: each takes
retract_length / retract_speed seconds of physical time with the head stopped. Filament length is the deposited
volume over the filament's cross-section, so it pauses during travel and dwells.
"""

from __future__ import annotations

import math

from ._axes import Rec


class FilamentPath:
    def __init__(self, path, filament_diameter=.00175, retract_length=.0008, retract_speed=.035, **_ignored):
        ok = lambda v: isinstance(v, (int, float)) and math.isfinite(v)  # noqa: E731
        if (not all(ok(v) and v > 0 for v in (filament_diameter, retract_speed))
                or not (ok(retract_length) and retract_length >= 0)):
            raise ValueError('Invalid filament or retraction dimensions')
        self.feed_path = path
        self.area = math.pi * filament_diameter ** 2 / 4
        self.filament_diameter = filament_diameter
        self.volume = path.volume
        self.length = path.length
        self.spans = []
        self.segments = []
        self.retract_length = retract_length
        offset = 0.0
        previous = None
        retracted = False
        for segment in path.segments:
            retract = segment.type == 'rapid' and previous is not None and previous.type == 'extrude'
            prime = segment.type == 'extrude' and retracted
            if (retract or prime) and retract_length > 0:
                duration = retract_length / retract_speed
                self.spans.append(Rec(t0=segment.t0 + offset, t1=segment.t0 + offset + duration, base_time=segment.t0,
                                      type='retract' if retract else 'prime',
                                      e0=0.0 if retract else retract_length, e1=retract_length if retract else 0.0))
                offset += duration
                retracted = retract
            self.spans.append(Rec(t0=segment.t0 + offset, t1=segment.t1 + offset, base_time=segment.t0, type='move',
                                  retraction=retract_length if retracted else 0.0))
            self.segments.append(Rec(segment, t0=segment.t0 + offset, t1=segment.t1 + offset))
            previous = segment
        self.duration = path.duration + offset
        self.retraction_time = offset
        self.filament_length = self.volume / self.area
        self._t1 = [s.t1 for s in self.spans]

    def sample(self, seconds):
        time = max(0.0, min(self.duration, seconds))
        lo, hi = 0, len(self.spans) - 1
        t1 = self._t1
        while lo < hi:
            m = (lo + hi) >> 1
            if t1[m] < time:
                lo = m + 1
            else:
                hi = m
        span = self.spans[lo]
        dwell = span.type != 'move'
        dt = time - span.t0
        state = self.feed_path.sample(span.base_time + (0.0 if dwell else dt))
        if dwell:
            retraction = span.e0 + (span.e1 - span.e0) * min(1.0, dt / (span.t1 - span.t0))
            filament_speed = -(span.e1 - span.e0) / (span.t1 - span.t0)
        else:
            retraction = span.retraction
            filament_speed = state.speed * self.feed_path.bead_area / self.area if state.type == 'extrude' else 0.0
        out = Rec(state)
        out.update(time=time, type=span.type if dwell else state.type)
        if dwell:
            out.update(speed=0.0, velocity=(0.0, 0.0, 0.0), acceleration=(0.0, 0.0, 0.0))
        out.update(filament_length=state.volume / self.area, filament_position=state.volume / self.area - retraction,
                   filament_retraction=retraction, filament_speed=filament_speed, done=time >= self.duration)
        return out
