"""eidoblend.harness.navigation: the VRM navigation stack's sensing, memory and planning, ported from
eidoverse/robot_sensors.js, robot_memory.js and robot_planner.js to Blender's Z-up world.

    from eidoblend.harness.navigation import RobotSensors, RobotMemory, RobotPlanner, debug_overlay, timed_route

    sensors = RobotSensors(scene, h_fov=110, v_fov=70, range=6, h_rays=16, v_rays=14, exclude_objects=[robot])
    memory = RobotMemory(size=50, cell_size=0.2)
    planner = RobotPlanner(agent_radius=0.35, optimistic=True)
    reading = sensors.sense(head_position, heading, pitch)       # radians; heading 0 faces -Y, counter-clockwise;
                                                                  # pitch > 0 looks DOWN (as robot_sensors.js)
    memory.apply_sensor_reading(reading, floor_z=0.0)
    path = planner.find_path(memory, x0, y0, x1, y1)              # [{'x', 'y', 'z'}, ...] or None
    route = timed_route(path, speed=1.2, start=2.0)               # [(t, x, y, heading), ...] for a walker

Blender's axes: the ground is the XY plane, heights are Z. The WebGPU stack's XZ ground and Y heights map as
three (x, z) -> Blender (x, -z) (eidoblend.common.ground_from_three). Heading 0 faces -Y, which is where a VRM's
face points after import; positive heading turns counter-clockwise seen from above. The HEAD's pitch passed to
sense() is positive looking down, as the JS code computes it (its doc comment says up-positive; its code and
robot_body.js both look down for a positive pitch). Each ray's own ray_pitch, inside the cone, is negative below
the cone's axis (the memory's "floor ray" rule reads it that way, as the JS did).

The sensors are the only part that touches the scene: one BVH over every visible mesh that is not excluded
(refresh() rebuilds it after the scene changes; a moving obstacle needs a refresh per sense). Given the objects that
move, refresh(dynamic=movers) splits the view in two, the still part built once and the movers' own BVH, and
refresh(dynamic=movers, dynamic_only=True) rebuilds only the movers' at each sense. Memory and planner work only from
readings, never from the scene's mesh list.
"""

from __future__ import annotations

import base64
import builtins
import heapq
import math

import numpy as np

STATE_UNKNOWN, STATE_FREE, STATE_BLOCKED, STATE_CLIFF, STATE_HAZARD = 0, 1, 2, 3, 4


# -------------------------------------------------------------------------------------------------- memory ---

class RobotMemory:
    """A top-down occupancy grid (state in the low 4 bits, confidence 0-15 in the high 4) with walkable-surface and
    blocking heights per cell and a landmark dictionary, built only from sensor readings."""

    def __init__(self, size=50.0, cell_size=0.2, origin_x=0.0, origin_y=0.0, bayesian=True, cliff_threshold=1.0,
                 step_up_tolerance=0.4):
        self.size, self.cell_size = float(size), float(cell_size)
        self.origin_x, self.origin_y = float(origin_x), float(origin_y)
        self.bayesian = bayesian
        self.max_confidence = 15
        self.cliff_threshold = cliff_threshold          # a floor this far below the body is a drop, not low ground
        self.step_up_tolerance = step_up_tolerance      # this far above is still "the floor I'm on" (a stair)
        self.n = int(math.ceil(self.size / self.cell_size))
        self.min_x = self.origin_x - self.size / 2
        self.min_y = self.origin_y - self.size / 2
        self.cells = np.zeros((self.n, self.n), np.uint8)            # [cy, cx]
        self.surface_z = np.full((self.n, self.n), np.nan, np.float32)
        self.blocking_z = np.full((self.n, self.n), np.nan, np.float32)
        self.landmarks = {}
        self.observation_count = 0

    # coordinates
    def world_to_cell(self, x, y):
        cx = int(math.floor((x - self.min_x) / self.cell_size))
        cy = int(math.floor((y - self.min_y) / self.cell_size))
        return (cx, cy) if self.in_bounds(cx, cy) else None

    def cell_to_world(self, cx, cy):
        return (self.min_x + (cx + 0.5) * self.cell_size, self.min_y + (cy + 0.5) * self.cell_size)

    def in_bounds(self, cx, cy):
        return 0 <= cx < self.n and 0 <= cy < self.n

    # cells
    def get_cell_state(self, cx, cy):
        return int(self.cells[cy, cx] & 0x0F) if self.in_bounds(cx, cy) else STATE_UNKNOWN

    def get_cell_confidence(self, cx, cy):
        return int(self.cells[cy, cx] >> 4) if self.in_bounds(cx, cy) else 0

    def get_cell_surface_z(self, cx, cy):
        return float(self.surface_z[cy, cx]) if self.in_bounds(cx, cy) else math.nan

    def get_cell_blocking_z(self, cx, cy):
        return float(self.blocking_z[cy, cx]) if self.in_bounds(cx, cy) else math.nan

    def observe_cell(self, cx, cy, state, z=None):
        """Nudge a cell toward an observed state: consistent observations grow confidence, conflicting ones erode
        it before the state flips. z: the walkable surface height (FREE / CLIFF, a running average) or the wall
        hit height (BLOCKED, the highest seen)."""
        if not self.in_bounds(cx, cy) or state == STATE_UNKNOWN:
            return
        cell = int(self.cells[cy, cx])
        cur, conf = cell & 0x0F, cell >> 4
        if not self.bayesian:
            new, nconf = state, self.max_confidence
        elif cur in (STATE_UNKNOWN, state):
            new, nconf = state, min(self.max_confidence, conf + 1)
        elif conf <= 1:
            new, nconf = state, 1
        else:
            new, nconf = cur, conf - 1
        self.cells[cy, cx] = (nconf << 4) | new
        if z is not None and new in (STATE_FREE, STATE_CLIFF):
            c = self.surface_z[cy, cx]
            if math.isnan(c):
                self.surface_z[cy, cx] = z
            else:
                w = min(conf, self.max_confidence - 1)
                self.surface_z[cy, cx] = (c * w + z) / (w + 1)
        if z is not None and new == STATE_BLOCKED:
            c = self.blocking_z[cy, cx]
            if math.isnan(c) or z > c:
                self.blocking_z[cy, cx] = z

    def apply_sensor_reading(self, reading, floor_z=0.0, agent_height=1.7):
        """Two passes, as the JS: floor evidence first (rays that landed on an up-facing surface, and downward
        misses, mark the cells they crossed FREE; a floor far below is a CLIFF), then walls (a hit on a vertical
        face within the body's height, not a step riser, not the side of a platform whose top is already seen,
        marks the cell just inside it BLOCKED)."""
        if not reading or not reading.get('hits'):
            return
        self.observation_count += 1
        ox, oy = reading['origin'][0], reading['origin'][1]
        cs = self.cell_size
        c0 = (int(math.floor((ox - self.min_x) / cs)), int(math.floor((oy - self.min_y) / cs)))
        for h in reading['hits']:                                   # pass 1: floor evidence
            p = h['point']
            c1 = (int(math.floor((p[0] - self.min_x) / cs)), int(math.floor((p[1] - self.min_y) / cs)))
            hz = p[2]
            normal_up = h['normal'] is not None and h['normal'][2] > 0.6
            drop = floor_z - hz
            if not h['hit']:
                if h['ray_pitch'] <= math.radians(-10):
                    self._walk_free(c0, c1, floor_z)
                continue
            if normal_up and drop <= self.cliff_threshold:
                self._walk_free(c0, c1, hz)
            elif normal_up:
                self.observe_cell(c1[0], c1[1], STATE_CLIFF, hz)
        off = cs * 0.6
        for h in reading['hits']:                                   # pass 2: walls
            if not h['hit'] or (h['normal'] is not None and h['normal'][2] > 0.6):
                continue
            p, d = h['point'], h['dir']
            hz = p[2]
            if hz >= floor_z + agent_height or floor_z - 0.05 <= hz <= floor_z + self.step_up_tolerance:
                continue
            cx = int(math.floor((p[0] + d[0] * off - self.min_x) / cs))
            cy = int(math.floor((p[1] + d[1] * off - self.min_y) / cs))
            if not self.in_bounds(cx, cy):
                continue
            ys, xs = slice(max(0, cy - 1), cy + 2), slice(max(0, cx - 1), cx + 2)
            known = self.surface_z[ys, xs]
            if np.any(~np.isnan(known) & (known >= hz - 0.05)):
                continue                                            # the side of a walkable top: not a wall
            self.observe_cell(cx, cy, STATE_BLOCKED, hz)

    def _walk_free(self, c0, c1, z_at_hit):
        x0, y0 = c0
        x1, y1 = c1
        adx, ady = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = adx - ady
        for _ in range(adx + ady + 4):
            last = x0 == x1 and y0 == y1
            self.observe_cell(x0, y0, STATE_FREE, z_at_hit if last else None)
            if last:
                break
            e2 = 2 * err
            if e2 > -ady:
                err -= ady
                x0 += sx
            if e2 < adx:
                err += adx
                y0 += sy

    def mark_standing_footprint(self, x, y, radius=None, z=0.0):
        """The body knows it stands on something walkable: mark its footprint FREE at its standing height."""
        r = self.cell_size * 1.5 if radius is None else radius
        cs = self.cell_size
        for cy in range(max(0, int((y - r - self.min_y) // cs)), min(self.n - 1, int((y + r - self.min_y) // cs)) + 1):
            for cx in range(max(0, int((x - r - self.min_x) // cs)), min(self.n - 1, int((x + r - self.min_x) // cs)) + 1):
                self.observe_cell(cx, cy, STATE_FREE, z)

    # landmarks
    def tag_landmark(self, name, x, y, type='point', last_seen=0.0, metadata=None):
        self.landmarks[name] = {'name': name, 'x': x, 'y': y, 'type': type, 'last_seen': last_seen,
                                'metadata': metadata or {}}

    def get_landmark(self, name):
        return self.landmarks.get(name)

    def forget_landmark(self, name):
        self.landmarks.pop(name, None)

    def list_landmarks(self):
        return list(self.landmarks.values())

    # queries
    def get_explored_area(self):
        return float(np.count_nonzero(self.cells & 0x0F) * self.cell_size ** 2)

    def get_known_cells(self):
        ys, xs = np.nonzero(self.cells & 0x0F)
        return [(int(x), int(y), int(self.cells[y, x] & 0x0F)) for y, x in zip(ys, xs)]

    def serialize(self):
        return {'size': self.size, 'cell_size': self.cell_size, 'origin_x': self.origin_x, 'origin_y': self.origin_y,
                'cliff_threshold': self.cliff_threshold, 'step_up_tolerance': self.step_up_tolerance,
                'cells_b64': base64.b64encode(self.cells.tobytes()).decode(),
                'surface_b64': base64.b64encode(self.surface_z.tobytes()).decode(),
                'blocking_b64': base64.b64encode(self.blocking_z.tobytes()).decode(),
                'landmarks': self.list_landmarks(), 'observation_count': self.observation_count}

    @classmethod
    def deserialize(cls, blob):
        m = cls(size=blob['size'], cell_size=blob['cell_size'], origin_x=blob['origin_x'], origin_y=blob['origin_y'],
                cliff_threshold=blob['cliff_threshold'], step_up_tolerance=blob['step_up_tolerance'])
        m.cells[:] = np.frombuffer(base64.b64decode(blob['cells_b64']), np.uint8).reshape(m.n, m.n)
        m.surface_z[:] = np.frombuffer(base64.b64decode(blob['surface_b64']), np.float32).reshape(m.n, m.n)
        if blob.get('blocking_b64'):
            m.blocking_z[:] = np.frombuffer(base64.b64decode(blob['blocking_b64']), np.float32).reshape(m.n, m.n)
        for lm in blob.get('landmarks', []):
            m.landmarks[lm['name']] = lm
        m.observation_count = blob.get('observation_count', 0)
        return m


# ------------------------------------------------------------------------------------------------- planner ---

class RobotPlanner:
    """A* over a RobotMemory grid: 8-connected, octile heuristic, no diagonal corner cutting, a height-aware
    clearance of the agent's radius around walls, unknown cells walkable but dearer when optimistic, step heights
    limited, and the cell path smoothed into straight segments by line of sight."""

    NEIGHBORS = ((1, 0, 1.0), (-1, 0, 1.0), (0, 1, 1.0), (0, -1, 1.0),
                 (1, 1, math.sqrt(2)), (1, -1, math.sqrt(2)), (-1, 1, math.sqrt(2)), (-1, -1, math.sqrt(2)))

    def __init__(self, agent_radius=0.35, optimistic=True, unknown_penalty=1.4, max_step_height=0.4,
                 dilation_cells=1, agent_height=1.7, max_expansions=50000, clearance_margin=None):
        self.agent_radius, self.optimistic = agent_radius, optimistic
        self.unknown_penalty, self.max_step_height = unknown_penalty, max_step_height
        self.dilation_cells, self.agent_height, self.max_expansions = dilation_cells, agent_height, max_expansions
        self.clearance_margin = clearance_margin
        self._clear_cache = {}

    def clearance(self, m):
        """The centre-to-centre distance kept from obstacle cells: the agent's radius plus a margin for the map's
        resolution (default: one cell). The memory marks a wall's BLOCKED cell just inside its face (0.6 of a cell
        along the ray, as the JS), so a face can sit up to about a cell in front of that cell's centre, and a
        straight segment between checked cell centres strays inside a cell. Measured on T11 (0.1 m cells, 0.35 m
        radius, against the true boxes): margin 0, the JS rule, came 0.307 m from a wall; half a cell 0.333 m; one
        cell 0.389 m. It is measured, not proven: a sparser scan can leave gaps. clearance_margin=0 is the JS
        planner exactly; the JS relied on its controller's collisions to keep the body out of the wall, and in a
        film nothing else does. The cost: a gap must be about 2 x (radius + margin) wide between its blocked cells
        to pass."""
        mg = m.cell_size if self.clearance_margin is None else float(self.clearance_margin)
        return self.agent_radius + mg

    def _clear(self, m, cx, cy, radius_cells, floor):
        """No BLOCKED / CLIFF / HAZARD cell within the clearance (the agent's radius + the margin) whose wall meets
        the body's column, and no LEDGE there either: a known surface higher than a step and lower than the head
        (the top of a crate or a wall the sensors saw from above) is in the body's way as much as a wall is. The JS
        planner let the body brush past such ledges and left the rest to the controller's collisions; here the
        route keeps its clearance (found by test T11: a 1.5 m head sees the tops of 1.4 m walls)."""
        key = (id(m), cx, cy, radius_cells, round(floor, 2))
        v = self._clear_cache.get(key)
        if v is not None:
            return v
        ceil = floor + self.agent_height
        reach = self.clearance(m)
        r = max(radius_cells, int(math.ceil(reach / m.cell_size)))
        ok = True
        for dy in range(-r, r + 1):
            for dx in range(-r, r + 1):
                if (dx == 0 and dy == 0) or math.hypot(dx, dy) * m.cell_size > reach:
                    continue
                nx, ny = cx + dx, cy + dy
                if not m.in_bounds(nx, ny):
                    continue
                s = m.get_cell_state(nx, ny)
                if s == STATE_FREE:
                    sz = m.get_cell_surface_z(nx, ny)
                    if not math.isnan(sz) and floor + self.max_step_height < sz < ceil:
                        ok = False                                  # a ledge in the body's column
                        break
                    continue
                if s not in (STATE_BLOCKED, STATE_CLIFF, STATE_HAZARD):
                    continue
                if s == STATE_BLOCKED:
                    wz = m.get_cell_blocking_z(nx, ny)
                    if not math.isnan(wz) and (wz < floor + 0.05 or wz > ceil):
                        continue                                    # below the feet or over the head
                ok = False
                break
            if not ok:
                break
        self._clear_cache[key] = ok
        return ok

    def is_walkable(self, m, cx, cy, radius_cells=None, from_cx=None, from_cy=None):
        radius_cells = self.dilation_cells if radius_cells is None else radius_cells
        if not m.in_bounds(cx, cy):
            return False
        s = m.get_cell_state(cx, cy)
        if s in (STATE_BLOCKED, STATE_CLIFF, STATE_HAZARD) or (not self.optimistic and s == STATE_UNKNOWN):
            return False
        floor = m.get_cell_surface_z(cx, cy)
        if math.isnan(floor) and from_cx is not None:
            floor = m.get_cell_surface_z(from_cx, from_cy)
        if math.isnan(floor):
            floor = 0.0
        if not self._clear(m, cx, cy, radius_cells, floor):
            return False
        if from_cx is not None:
            a, b = m.get_cell_surface_z(from_cx, from_cy), m.get_cell_surface_z(cx, cy)
            if not math.isnan(a) and not math.isnan(b) and abs(b - a) > self.max_step_height:
                return False
        return True

    def find_path(self, m, from_x, from_y, to_x, to_y):
        """A list of waypoints {'x', 'y', 'z'} (z: the surface height, NaN where unknown) from the start's cell to
        the goal's (snapped to the nearest walkable cell within 6 cells if it lands on a wall), or None."""
        self._clear_cache = {}
        rc = self.dilation_cells
        start, goal = m.world_to_cell(from_x, from_y), m.world_to_cell(to_x, to_y)
        if start is None or goal is None:
            return None
        if not self.is_walkable(m, goal[0], goal[1], rc):
            goal = self._snap(m, goal[0], goal[1], rc, 6)
            if goal is None:
                return None
        n = m.n
        g = np.full(n * n, np.inf, np.float64)
        came = np.full(n * n, -1, np.int64)
        closed = np.zeros(n * n, np.bool_)
        si, gi = start[1] * n + start[0], goal[1] * n + goal[0]
        g[si] = 0.0
        heap = [(self._h(start, goal), si)]
        exp = 0
        while heap:
            exp += 1
            if exp > self.max_expansions:
                print('[RobotPlanner] max expansions exceeded: giving up', flush=True)
                return None
            _, cur = heapq.heappop(heap)
            if closed[cur]:
                continue
            closed[cur] = True
            if cur == gi:
                return self._reconstruct(came, cur, m, rc)
            cx, cy = cur % n, cur // n
            for dx, dy, base in self.NEIGHBORS:
                nx, ny = cx + dx, cy + dy
                if not m.in_bounds(nx, ny):
                    continue
                ni = ny * n + nx
                if closed[ni] or not self.is_walkable(m, nx, ny, rc, cx, cy):
                    continue
                if dx and dy and (not self.is_walkable(m, cx + dx, cy, rc, cx, cy)
                                  or not self.is_walkable(m, cx, cy + dy, rc, cx, cy)):
                    continue                                        # no slipping between two blocked corners
                cost = base * (self.unknown_penalty if m.get_cell_state(nx, ny) == STATE_UNKNOWN else 1.0)
                t = g[cur] + cost
                if t < g[ni]:
                    came[ni], g[ni] = cur, t
                    heapq.heappush(heap, (t + self._h((nx, ny), goal), ni))
        return None

    @staticmethod
    def _h(a, b):
        dx, dy = abs(b[0] - a[0]), abs(b[1] - a[1])
        return (dx + dy) + (math.sqrt(2) - 2) * min(dx, dy)

    def _reconstruct(self, came, end, m, rc):
        n = m.n
        cells = []
        cur = end
        while cur != -1:
            cells.append((int(cur % n), int(cur // n)))
            cur = int(came[cur])
        cells.reverse()
        path = []
        for cx, cy in cells:
            x, y = m.cell_to_world(cx, cy)
            path.append({'x': x, 'y': y, 'z': m.get_cell_surface_z(cx, cy)})
        return self._smooth(m, path, rc)

    def _smooth(self, m, path, rc):
        if len(path) <= 2:
            return path
        out, i = [path[0]], 0
        while i < len(path) - 1:
            j = len(path) - 1
            while j > i + 1 and not self._line_of_sight(m, path[i], path[j], rc):
                j -= 1
            out.append(path[j])
            i = j
        return out

    def _line_of_sight(self, m, p0, p1, rc):
        a, b = m.world_to_cell(p0['x'], p0['y']), m.world_to_cell(p1['x'], p1['y'])
        if a is None or b is None:
            return False
        x0, y0 = a
        x1, y1 = b
        adx, ady = abs(x1 - x0), abs(y1 - y0)
        sx, sy = (1 if x0 < x1 else -1), (1 if y0 < y1 else -1)
        err = adx - ady
        px = py = None
        for _ in range(adx + ady + 4):
            if not self.is_walkable(m, x0, y0, rc, px, py):
                return False
            if x0 == x1 and y0 == y1:
                return True
            px, py = x0, y0
            e2 = 2 * err
            if e2 > -ady:
                err -= ady
                x0 += sx
            if e2 < adx:
                err += adx
                y0 += sy
        return False

    def _snap(self, m, cx, cy, rc, max_dist):
        for r in range(1, max_dist + 1):
            for dy in range(-r, r + 1):
                for dx in range(-r, r + 1):
                    if max(abs(dx), abs(dy)) == r and self.is_walkable(m, cx + dx, cy + dy, rc):
                        return (cx + dx, cy + dy)
        return None

    def is_path_blocked(self, m, path):
        """True if a segment of a planned path no longer has a clear line of sight (a replanning trigger)."""
        if not path or len(path) < 2:
            return False
        self._clear_cache = {}
        return any(not self._line_of_sight(m, path[i], path[i + 1], self.dilation_cells) for i in range(len(path) - 1))


# ------------------------------------------------------------------------------------------------- sensors ---

def _names_under(objects):
    """the names of these objects and of everything parented under them"""
    out = set()
    for o in objects:
        out.add(o.name)
        out.update(c.name for c in o.children_recursive)
    return out


def _read_view(dg, excluded, skip=frozenset(), only=None):
    """(BVHTree or None, the owner object of each polygon, meshes read) over the visible meshes, evaluated, in world
    space: none under an excluded object, none of `skip`, and, given `only`, only those. An instance counts as its own
    object and as the object that makes it."""
    from mathutils.bvhtree import BVHTree
    verts, polys, owners = [], [], []
    count = 0
    for inst in dg.object_instances:
        ob = inst.object
        if ob.type != 'MESH':
            continue
        src = inst.parent.original if inst.is_instance and inst.parent else ob.original
        names = {ob.original.name, src.name}
        if names & excluded or names & skip or (only is not None and not names & only) or src.hide_render:
            continue
        me = ob.data
        mw = inst.matrix_world
        base = len(verts)
        verts.extend(mw @ v.co for v in me.vertices)
        for p in me.polygons:
            polys.append([base + i for i in p.vertices])
            owners.append(src)
        count += 1
    return (BVHTree.FromPolygons(verts, polys, all_triangles=False) if polys else None), owners, count


class RobotSensors:
    """A depth-camera-like cone of rays against the scene's visible meshes (minus the excluded ones)."""

    def __init__(self, scene, h_fov=110, v_fov=70, range=6.0, h_rays=16, v_rays=14, exclude_objects=()):
        self.scene = scene
        self.h_fov, self.v_fov = math.radians(h_fov), math.radians(v_fov)
        self.range, self.h_rays, self.v_rays = float(range), int(h_rays), int(v_rays)
        self.exclude_objects = list(exclude_objects)
        self._local = []
        for yi in builtins.range(self.v_rays):                     # `range` is the JS option's name here
            pitch = 0.0 if self.v_rays == 1 else -self.v_fov / 2 + yi / (self.v_rays - 1) * self.v_fov
            for xi in builtins.range(self.h_rays):
                yaw = 0.0 if self.h_rays == 1 else -self.h_fov / 2 + xi / (self.h_rays - 1) * self.h_fov
                self._local.append((yaw, pitch))
        self._bvh, self._owners = None, []            # the view: everything, or after a split the still part
        self._bvh_dyn, self._owners_dyn = None, []    # after a split: the moving part
        self.dynamic = None                           # the names the split gave the moving part (None: no split)
        self.refresh()

    def refresh(self, dynamic=None, dynamic_only=False):
        """Rebuild the sensors' view of every visible mesh (evaluated, world space) not under an excluded object.
        Returns the number of meshes read. Call it after the scene's geometry moves or changes.

        dynamic (objects): what moves, and everything parented under it. The view is then two BVHs: the still part
        (every other mesh) and the moving part (these alone). dynamic_only=True rebuilds only the moving part and keeps
        the still part as it was built, so a sense where only the movers moved reads only them; with no split yet, or
        a different set of movers, it builds both. sense() and cast_one() cast both and keep the nearer hit. With
        dynamic=None (the default) the view is one BVH over everything."""
        import bpy
        dg = bpy.context.evaluated_depsgraph_get()
        excluded = _names_under(self.exclude_objects)
        if dynamic is None:
            self._bvh, self._owners, count = _read_view(dg, excluded)
            self._bvh_dyn, self._owners_dyn = None, []
            self.dynamic = None
            return count
        dyn = frozenset(_names_under(dynamic) - excluded)
        count = 0
        if not dynamic_only or dyn != self.dynamic:
            self._bvh, self._owners, count = _read_view(dg, excluded, skip=dyn)
        self._bvh_dyn, self._owners_dyn, n_dyn = _read_view(dg, excluded, only=dyn)
        self.dynamic = dyn
        return count + n_dyn

    def exclude(self, ob):
        """leave `ob` (and everything under it) out of the view from now on: the view is rebuilt, split as it was"""
        if ob not in self.exclude_objects:
            self.exclude_objects.append(ob)
            if self.dynamic is None:
                self.refresh()
            else:
                import bpy
                self.refresh(dynamic=[bpy.data.objects[n] for n in self.dynamic if n in bpy.data.objects])

    def _cast(self, o, d, dist):
        """the nearer hit of the view's BVHs -> (location, normal, owner object, distance), or Nones"""
        best = (None, None, None, None)
        for bvh, owners in ((self._bvh, self._owners), (self._bvh_dyn, self._owners_dyn)):
            if bvh is None:
                continue
            loc, nrm, idx, hd = bvh.ray_cast(o, d, dist)
            if loc is not None and (best[0] is None or hd < best[3]):
                best = (loc, nrm, owners[idx], hd)
        return best

    def _basis(self, heading, pitch):
        """forward, left, up of the cone. robot_sensors.js builds forward = (sin h cos p, -sin p, cos h cos p) in
        three's Y-up, so a POSITIVE pitch looks DOWN (robot_body.js passes -atan2(dy, horizontal) to look at a
        point: below the head is positive). Mapped to Z-up: (sin h cos p, -cos h cos p, -sin p)."""
        from mathutils import Vector
        f = Vector((math.sin(heading) * math.cos(pitch), -math.cos(heading) * math.cos(pitch), -math.sin(pitch)))
        left = Vector((0, 0, 1)).cross(f)
        if left.length < 1e-6:
            left = Vector((math.cos(heading), math.sin(heading), 0.0))
        left.normalize()
        up = f.cross(left).normalized()
        return f, left, up

    def sense(self, origin, heading=0.0, pitch=0.0):
        """Cast the cone from `origin` (a 3-vector) facing `heading` (radians about +Z, 0 = -Y) tilted by `pitch`
        (radians, POSITIVE LOOKS DOWN, as in robot_sensors.js: sense(head, heading, 0.35) looks 20 degrees down at
        the floor ahead). Returns {'origin', 'heading', 'pitch', 'hits': [...], 'count', 'hit_count'}; each
        hit: {'dir', 'hit', 'distance', 'point', 'normal' (None on a miss), 'object', 'ray_yaw', 'ray_pitch'},
        with a miss's point at the full range."""
        from mathutils import Vector
        o = Vector(origin)
        f, left, up = self._basis(heading, pitch)
        hits = []
        n_hit = 0
        for yaw, rp in self._local:
            d = (left * (math.cos(rp) * math.sin(yaw)) + up * math.sin(rp) + f * (math.cos(rp) * math.cos(yaw)))
            d.normalize()
            loc, nrm, owner, dist = self._cast(o, d, self.range)
            if loc is not None:
                if nrm.dot(d) > 0:
                    nrm = -nrm                                      # face the ray (BVH normals follow winding)
                hits.append({'dir': d, 'hit': True, 'distance': dist, 'point': loc, 'normal': nrm,
                             'object': owner, 'ray_yaw': yaw, 'ray_pitch': rp})
                n_hit += 1
            else:
                hits.append({'dir': d, 'hit': False, 'distance': self.range, 'point': o + d * self.range,
                             'normal': None, 'object': None, 'ray_yaw': yaw, 'ray_pitch': rp})
        return {'origin': o, 'heading': heading, 'pitch': pitch, 'hits': hits, 'count': len(hits), 'hit_count': n_hit}

    def cast_one(self, origin, direction, max_dist=None):
        from mathutils import Vector
        d = Vector(direction).normalized()
        dist = self.range if max_dist is None else max_dist
        loc, nrm, owner, hd = self._cast(Vector(origin), d, dist)
        if loc is not None:
            return {'hit': True, 'distance': hd, 'point': loc, 'normal': nrm, 'object': owner}
        return {'hit': False, 'distance': dist, 'point': None, 'normal': None, 'object': None}


# ------------------------------------------------------------------------------------------------ helpers ---

def timed_route(path, speed=1.2, start=0.0):
    """[(t, x, y, heading)] at each waypoint of a planned path, walking at `speed` m/s from `start` seconds. The
    heading (0 = -Y, counter-clockwise) faces the next segment. For a walker to follow (characters family)."""
    if not path:
        return []
    out, t = [], float(start)
    for i, p in enumerate(path):
        q = path[min(i + 1, len(path) - 1)] if i < len(path) - 1 else p
        prev = path[i - 1] if i else p
        dx, dy = (q['x'] - p['x'], q['y'] - p['y']) if i < len(path) - 1 else (p['x'] - prev['x'], p['y'] - prev['y'])
        heading = math.atan2(dx, -dy) if (dx or dy) else (out[-1][3] if out else 0.0)
        if i:
            t += math.hypot(p['x'] - prev['x'], p['y'] - prev['y']) / max(1e-6, speed)
        out.append((round(t, 4), p['x'], p['y'], heading))
    return out


def debug_overlay(memory, path=None, z=0.01, name='nav_debug', show_free=True):
    """Meshes that show what the memory knows (FREE green, BLOCKED red, CLIFF orange, HAZARD purple, unknown not
    drawn) and the path as a thin ribbon, z metres above each cell's surface. For diagnosis: remove it (or keep
    it, if it is the film's visual language) before the final render. Returns the overlay objects."""
    import bpy
    colours = {STATE_FREE: (0.1, 0.8, 0.25, 1), STATE_BLOCKED: (0.95, 0.12, 0.1, 1), STATE_CLIFF: (1.0, 0.55, 0.05, 1),
               STATE_HAZARD: (0.6, 0.15, 0.85, 1)}
    cs = memory.cell_size
    verts, faces, mat_idx = [], [], []
    order = [s for s in colours if show_free or s != STATE_FREE]
    for cx, cy, s in memory.get_known_cells():
        if s not in order:
            continue
        x, y = memory.cell_to_world(cx, cy)
        sz = memory.get_cell_surface_z(cx, cy)
        h = (0.0 if math.isnan(sz) else sz) + z
        k = len(verts)
        e = cs * 0.45
        verts += [(x - e, y - e, h), (x + e, y - e, h), (x + e, y + e, h), (x - e, y + e, h)]
        faces.append((k, k + 1, k + 2, k + 3))
        mat_idx.append(order.index(s))
    objs = []
    me = bpy.data.meshes.new(name + '_cells')
    me.from_pydata(verts, [], faces)
    for s in order:
        m = bpy.data.materials.new(f'{name}_state{s}')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = colours[s]
        b.inputs['Emission Color'].default_value = colours[s]
        b.inputs['Emission Strength'].default_value = 0.6
        me.materials.append(m)
    for p, i in zip(me.polygons, mat_idx):
        p.material_index = i
    ob = bpy.data.objects.new(name + '_cells', me)
    ob['no_motion_check'] = True
    ob['no_support_check'] = True
    bpy.context.scene.collection.objects.link(ob)
    objs.append(ob)
    if path and len(path) > 1:
        cu = bpy.data.curves.new(name + '_path', 'CURVE')
        cu.dimensions = '3D'
        cu.bevel_depth = 0.025
        sp = cu.splines.new('POLY')
        sp.points.add(len(path) - 1)
        for pt, p in zip(sp.points, path):
            pz = 0.0 if math.isnan(p['z']) else p['z']
            pt.co = (p['x'], p['y'], pz + z + 0.03, 1.0)
        m = bpy.data.materials.new(name + '_path')
        m.use_nodes = True
        b = m.node_tree.nodes['Principled BSDF']
        b.inputs['Base Color'].default_value = (0.1, 0.5, 1.0, 1)
        b.inputs['Emission Color'].default_value = (0.1, 0.5, 1.0, 1)
        b.inputs['Emission Strength'].default_value = 2.0
        cu.materials.append(m)
        po = bpy.data.objects.new(name + '_path', cu)
        po['no_motion_check'] = True
        po['no_support_check'] = True
        bpy.context.scene.collection.objects.link(po)
        objs.append(po)
    return objs
