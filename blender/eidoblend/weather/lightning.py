"""Lightning from eidoverse/weather_system.js: the deterministic profile and the per-frame scheduler. Plain Python.

The profile is EANPA_LIGHTNING_PROFILE: styles and palettes, cadence tables, event gaps, the return-stroke plan, the
flash and channel envelopes and the local-strike candidate rule. Every value comes from the event index through
jsHash, so the same frames always give the same strikes, colours, impacts and thunder.

LightningScheduler is the lightning part of the JS weather.update(t, camera), decision for decision: one event per
update at most, the darkstorm entry and remote-run guarantees, the 45 s local-strike cooldown, the forced forward
strike, the strike record and the surface-damage record. It works in three.js coordinates (Y up), like the JS; the
Blender side converts at its edges. Finding the surface a local strike lands on is the caller's: find_local_strike.
"""
import math

# ------------------------------------------------------------------------------------------------ profile ---


def js_hash(n):
    """The JS jsHash: fract(sin(n * 127.1 + 311.7) * 43758.5453)."""
    x = math.sin(n * 127.1 + 311.7) * 43758.5453
    return x - math.floor(x)


LIGHTNING_STYLES = {
    'white': {'hex': 0xf2f6ff},
    'blue': {'hex': 0x5d9dff},
    'purple': {'hex': 0xb26cff},
    'red': {'hex': 0xff4438},
    'green': {'hex': 0x54ff8a},
}

LIGHTNING_PALETTES = {
    'standard': (('white', 0.52), ('blue', 0.44), ('purple', 0.04)),
    'darkstorm': (('white', 0.40), ('blue', 0.36), ('purple', 0.16), ('red', 0.04), ('green', 0.04)),
}

LIGHTNING_CADENCE = {
    'standard': dict(referenceLevel=0.30, minGapSeconds=16, maxGapSeconds=38, maxStrokes=2, clusterThresholds=(0.72,),
                     strokeGapMinSeconds=0.085, strokeGapMaxSeconds=0.19),
    'darkstorm': dict(referenceLevel=0.85, initialGapMinSeconds=6, initialGapMaxSeconds=9, minGapSeconds=12,
                      maxGapSeconds=28, maxStrokes=2, clusterThresholds=(0.68,), strokeGapMinSeconds=0.075,
                      strokeGapMaxSeconds=0.17, firstLocalCandidateWithinEvents=1,
                      maxRemoteEventsBetweenLocalCandidates=6),
}

# The cadence above is authored for a realtime world. eidoverse's offline renderer compresses the gaps to 0.42 so a
# 15-90 s clip catches strikes; Blender renders offline, so that is the default here. 1.0 = the authored spacing.
DEFAULT_GAP_SCALE = 0.42


def srgb_to_linear(c):
    """three.js SRGBToLinear (ColorManagement: Color.setHex reads hex as sRGB)."""
    return c * 0.0773993808 if c < 0.04045 else math.pow(c * 0.9478672986 + 0.0521327014, 2.4)


def hex_to_linear(h):
    return tuple(srgb_to_linear(((h >> s) & 255) / 255.0) for s in (16, 8, 0))


def style_color(key):
    """The linear RGB of a lightning style, as three's Color.setHex gives it."""
    return hex_to_linear(LIGHTNING_STYLES[key]['hex'])


def lightning_style_key_at(interval, palette_name='standard'):
    palette = LIGHTNING_PALETTES.get(palette_name, LIGHTNING_PALETTES['standard'])
    sample = js_hash(interval * 23.17 + 91.3)
    cumulative = 0.0
    for key, weight in palette:
        cumulative += weight
        if sample < cumulative:
            return key
    return palette[-1][0]


def lightning_cadence_for(palette_name='standard'):
    return LIGHTNING_CADENCE.get(palette_name, LIGHTNING_CADENCE['standard'])


def _finite(v):
    return isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)


def lightning_event_gap_at(event_index, palette_name='standard', level=1.0, gap_scale=DEFAULT_GAP_SCALE):
    cadence = lightning_cadence_for(palette_name)
    lv = float(level) if _finite(level) else 0.0
    safe_level = max(0.01, min(1.0, lv or 0.0))
    rarity = max(1.0, min(2.75, math.sqrt(cadence['referenceLevel'] / safe_level)))
    spread = cadence['maxGapSeconds'] - cadence['minGapSeconds']
    return (cadence['minGapSeconds'] + js_hash(event_index * 47.17 + 19.73) * spread) * rarity * gap_scale


def lightning_initial_event_gap_at(event_index, palette_name='standard', level=1.0, gap_scale=DEFAULT_GAP_SCALE):
    cadence = lightning_cadence_for(palette_name)
    if 'initialGapMinSeconds' not in cadence or 'initialGapMaxSeconds' not in cadence:
        return lightning_event_gap_at(event_index, palette_name, level, gap_scale)
    return (cadence['initialGapMinSeconds'] + js_hash(event_index * 53.71 + 41.9)
            * (cadence['initialGapMaxSeconds'] - cadence['initialGapMinSeconds'])) * gap_scale


def lightning_stroke_plan_at(event_index, palette_name='standard'):
    cadence = lightning_cadence_for(palette_name)
    cluster = js_hash(event_index * 61.31 + 7.91)
    count = 1
    for threshold in cadence['clusterThresholds']:
        if cluster >= threshold:
            count += 1
    count = max(1, min(cadence['maxStrokes'], count))
    offsets = [0.0]
    amplitudes = [0.78 + js_hash(event_index * 67.9 + 5.3) * 0.22]
    for stroke in range(1, count):
        gap_mix = js_hash(event_index * 71.7 + stroke * 13.1 + 11.9)
        offsets.append(offsets[-1] + cadence['strokeGapMinSeconds']
                       + gap_mix * (cadence['strokeGapMaxSeconds'] - cadence['strokeGapMinSeconds']))
        amplitudes.append(0.42 + js_hash(event_index * 73.3 + stroke * 17.7 + 3.1) * 0.38)
    # long enough for the channel afterglow to decay fully; the scene flash is ~1e-9 by then
    return dict(count=count, offsets=offsets, amplitudes=amplitudes, durationSeconds=offsets[-1] + 0.85)


def lightning_flash_at(elapsed, plan):
    """The scene / sky flash: exp(-25 t) per return stroke, summed and clamped to [0, 1]."""
    if not plan or not _finite(elapsed) or elapsed < 0:
        return 0.0
    flash = 0.0
    for s in range(plan['count']):
        age = elapsed - plan['offsets'][s]
        if age < 0:
            continue
        flash += math.exp(-age * 25) * plan['amplitudes'][s]
    return max(0.0, min(1.0, flash if math.isfinite(flash) else 0.0))


def lightning_channel_at(elapsed, plan):
    """The visible channel's afterglow: exp(-6.5 t), ~4x slower than the scene flash (the ribbon lingers ~0.5 s)."""
    if not plan or not _finite(elapsed) or elapsed < 0:
        return 0.0
    glow = 0.0
    for s in range(plan['count']):
        age = elapsed - plan['offsets'][s]
        if age < 0:
            continue
        glow += math.exp(-age * 6.5) * plan['amplitudes'][s]
    return max(0.0, min(1.0, glow if math.isfinite(glow) else 0.0))


def lightning_local_candidate_at(event_index, chance, palette_name='standard', entry_event_count=0,
                                 remote_events_since_local=0, has_local_strike=False):
    random_candidate = js_hash(event_index * 101.9 + 43.7) < max(0.0, min(1.0, chance))
    if palette_name != 'darkstorm':
        return random_candidate
    cadence = LIGHTNING_CADENCE['darkstorm']
    entry = (not has_local_strike) and entry_event_count >= cadence['firstLocalCandidateWithinEvents']
    remote = remote_events_since_local >= cadence['maxRemoteEventsBetweenLocalCandidates']
    return random_candidate or entry or remote


def make_lightning_profile(gap_scale=DEFAULT_GAP_SCALE):
    """globalThis.EANPA_LIGHTNING_PROFILE, with this system's gap scale bound into the gap functions."""
    return dict(
        styles=LIGHTNING_STYLES, palettes=LIGHTNING_PALETTES, styleKeyAt=lightning_style_key_at,
        cadence=LIGHTNING_CADENCE,
        eventGapAt=lambda i, p='standard', lv=1.0: lightning_event_gap_at(i, p, lv, gap_scale),
        initialEventGapAt=lambda i, p='standard', lv=1.0: lightning_initial_event_gap_at(i, p, lv, gap_scale),
        strokePlanAt=lightning_stroke_plan_at, flashAt=lightning_flash_at, channelAt=lightning_channel_at,
        localCandidateAt=lambda i, c, **kw: lightning_local_candidate_at(i, c, **kw),
    )


EANPA_LIGHTNING_PROFILE = make_lightning_profile()

# --------------------------------------------------------------------------------------- scene constants ---

LIGHTNING_LIGHT_PEAK = 12000.0          # three.js candela
LIGHTNING_LIGHT_RANGE = 900.0
LOCAL_STRIKE_COOLDOWN = 45.0
LOCAL_STRIKE_PLAYER_GUARD = 28.0
FORCED_LOCAL_STRIKE_MIN_RADIUS = 34.0
FORCED_LOCAL_STRIKE_MAX_RADIUS = 58.0
LOCAL_STRIKE_SURFACE_DAMAGE_RADIUS = 4.5
IMPACT_POOL_SIZE = 2
SCORCH_POOL_SIZE = 4
SCORCH_LIFETIME = 90.0
SPARK_LIFE = 0.82
PUFF_LIFE = 4.5
UPWARD_NORMAL_MIN = 0.72


def impact_counts(rain_count):
    """IMPACT_SPARK_COUNT and IMPACT_PUFF_COUNT, which the JS scales with the rain population."""
    spark = max(24, min(64, int(math.floor(rain_count / 250 + 0.5))))
    puff = max(8, min(16, int(math.floor(rain_count / 850 + 0.5))))
    return spark, puff


def js_round(x):
    return int(math.floor(x + 0.5))


# ------------------------------------------------------------------------------------------- candidates ---

def strike_candidates(interval, cam_pos, cam_forward, prefer_forward=False):
    """findLocalStrike's eight candidate columns (three x, z) around the camera, forward-biased when forced."""
    fx, fz = cam_forward[0], cam_forward[2]
    ln = math.hypot(fx, fz)
    if ln * ln < 1e-5:
        fx, fz = 0.0, -1.0
    else:
        fx, fz = fx / ln, fz / ln
    out = []
    for c in range(8):
        span = 0.28 if prefer_forward else 0.84
        angle = (js_hash(interval * 89.3 + c * 17.1 + 31) - 0.5) * math.pi * span
        r = js_hash(interval * 97.7 + c * 13.7 + 37)
        radius = (FORCED_LOCAL_STRIKE_MIN_RADIUS + r * (FORCED_LOCAL_STRIKE_MAX_RADIUS - FORCED_LOCAL_STRIKE_MIN_RADIUS)
                  if prefer_forward else 45 + r * 125)
        ca, sa = math.cos(angle), math.sin(angle)
        dx, dz = fx * ca - fz * sa, fx * sa + fz * ca
        out.append((cam_pos[0] + dx * radius, cam_pos[2] + dz * radius))
    return out


def storm_cell_strike_xz(interval, weather_at, storm_center=(0.0, 0.0), storm_range=700.0):
    """Where a strike lands when it is not local: a hashed point in the storm range, moved to the first of 12 hashed
    candidates over a dense world cell (weatherAt > 1.3). three x, z."""
    cx, cz = storm_center
    R = storm_range
    I = interval
    sx = cx + (js_hash(I * 7 + 11) - 0.5) * 2 * R
    sz = cz + (js_hash(I * 7 + 29) - 0.5) * 2 * R
    for q in range(12):
        qx = cx + (js_hash(I * 13 + q * 3 + 1) - 0.5) * 2 * R
        qz = cz + (js_hash(I * 13 + q * 3 + 2) - 0.5) * 2 * R
        if weather_at(qx, qz) > 1.3:
            return qx, qz
    return sx, sz


# -------------------------------------------------------------------------------------------- the impact ---

def _cross(a, b):
    return (a[1] * b[2] - a[2] * b[1], a[2] * b[0] - a[0] * b[2], a[0] * b[1] - a[1] * b[0])


def _norm(v):
    n = math.sqrt(v[0] * v[0] + v[1] * v[1] + v[2] * v[2]) or 1.0
    return (v[0] / n, v[1] / n, v[2] / n)


def _add(*vs):
    return tuple(sum(v[i] for v in vs) for i in range(3))


def _scale(v, k):
    return (v[0] * k, v[1] * k, v[2] * k)


def impact_basis(normal):
    n = _norm(normal)
    axis = (0.0, 0.0, 1.0) if abs(n[0]) > 0.8 else (1.0, 0.0, 0.0)
    tangent = _norm(_cross(axis, n))
    bitangent = _norm(_cross(n, tangent))
    return n, tangent, bitangent


def impact_particles(interval, normal, spark_count, puff_count):
    """triggerImpact's per-particle data (three space): spark velocities and lengths, puff offsets, drifts, sizes,
    and the scorch disc size."""
    I = interval
    n, t, b = impact_basis(normal)
    sparks = []
    for i in range(spark_count):
        angle = js_hash(I * 37.1 + i * 11.7 + 3) * math.pi * 2
        side = 1.5 + js_hash(I * 41.3 + i * 7.9 + 5) * 7.0
        lift = 4.0 + js_hash(I * 43.7 + i * 13.1 + 7) * 9.5
        v = _add(_scale(n, lift), _scale(t, math.cos(angle) * side), _scale(b, math.sin(angle) * side))
        sparks.append(dict(velocity=v, length=0.07 + js_hash(I * 47.9 + i * 5.3 + 9) * 0.20))
    puffs = []
    for i in range(puff_count):
        angle = js_hash(I * 53.3 + i * 9.1 + 11) * math.pi * 2
        radius = js_hash(I * 59.9 + i * 4.7 + 13) * 1.2
        offset = _add(_scale(t, math.cos(angle) * radius), _scale(b, math.sin(angle) * radius),
                      _scale(n, 0.30 + js_hash(I * 61.7 + i * 8.3 + 15) * 0.75))
        drift = _add(_scale(t, (js_hash(I * 67.1 + i * 3.7 + 17) - 0.5) * 0.75),
                     _scale(b, (js_hash(I * 71.3 + i * 6.1 + 19) - 0.5) * 0.75),
                     _scale(n, 0.45 + js_hash(I * 73.9 + i * 2.9 + 21) * 0.75))
        puffs.append(dict(offset=offset, drift=drift, size=1.1 + js_hash(I * 79.7 + i * 10.7 + 23) * 1.6,
                          jitter=0.85 + js_hash(I * 97.7 + i * 6.7 + 31) * 0.5,
                          roll0=js_hash(I * 91.3 + i * 12.7 + 27) * math.pi * 2,
                          roll_rate=(js_hash(I * 89.1 + i * 15.1 + 33) - 0.5) * 0.45))
    return dict(normal=n, tangent=t, bitangent=b, sparks=sparks, puffs=puffs,
                scorch_size=0.9 + js_hash(I * 83.9 + 29) * 1.2)


def spark_at(origin, normal, spark, age):
    """One spark of updateImpactPool at `age`: (position, unit direction, scale) in three space, or None after life."""
    if age >= SPARK_LIFE:
        return None
    v = spark['velocity']
    pos = _add(origin, _scale(v, age), _scale(normal, -4.9 * age * age))
    d = _norm(_add(v, _scale(normal, -9.8 * age)))
    return pos, d, (0.038, spark['length'] * (1 - age / SPARK_LIFE * 0.65), 0.038)


def spark_alpha(age):
    return max(0.0, 1 - age / SPARK_LIFE) if age < SPARK_LIFE else 0.0


def puff_at(origin, normal, puff, age):
    """One puff body at `age`: (position, size, roll about the view axis), three space."""
    pos = _add(origin, puff['offset'], _scale(puff['drift'], age), _scale(normal, 0.14 * age * age))
    growth01 = math.pow(age / PUFF_LIFE, 0.25)
    size = puff['size'] * (0.6 + growth01 * 1.5 * puff['jitter'])
    return pos, size, puff['roll0'] + puff['roll_rate'] * age


def puff_uniforms(age):
    """(alpha, age01, glowK) of a puff slot at `age`: the fast rise-in, the shader clock and the strike afterglow."""
    if age >= PUFF_LIFE:
        return 0.0, 1.0, 0.0
    return min(1.0, age / 0.15), age / PUFF_LIFE, math.exp(-age * 3.4) * 1.1 + math.exp(-age * 0.8) * 0.30


def scorch_at(age, strike_color):
    """(alpha, rgb) of a scorch decal at `age`; alpha 0 once its 90 s life is over."""
    if age >= SCORCH_LIFETIME:
        return 0.0, (0.0, 0.0, 0.0)
    hot = max(0.0, 1 - age / 1.4)
    fade = 1.0 if age <= 65 else max(0.0, 1 - (age - 65) / 25)
    return ((0.62 - hot * 0.10) * fade,
            (0.018 + strike_color[0] * 0.22 * hot, 0.011 + strike_color[1] * 0.18 * hot,
             0.007 + strike_color[2] * 0.14 * hot))


# ------------------------------------------------------------------------------------------- the scheduler ---

class LightningScheduler:
    """The lightning half of weather.update(t, camera). One instance per weather system; reset() starts it over.

    step(t, w, k, cadence_target, cam, sky) runs one frame. w is the live (lerped) weather def, k its amount,
    cadence_target the transition's target name or None, cam a dict(pos, forward) in three space, sky a dict with
    cloudStart, cloudHeight and weather_at(x, z). It returns the frame's lightning record; the events it began are in
    self.events (each with its strike, bolt seed and impact).
    """

    def __init__(self, gap_scale=DEFAULT_GAP_SCALE, storm_center=None, storm_range=700.0, rain_count=16000,
                 find_local_strike=None, on_local_strike=None):
        self.gap_scale = max(0.05, min(4.0, float(gap_scale)))
        self.storm_center = tuple(storm_center) if storm_center is not None else (0.0, 0.0)
        self.storm_range = float(storm_range)
        self.spark_count, self.puff_count = impact_counts(rain_count)
        self.find_local_strike = find_local_strike
        self.on_local_strike = on_local_strike
        self.reset()

    def reset(self):
        self.event_index = 0
        self.last_local_strike_at = -math.inf
        self.debug_forced_pending = False
        self.active_key = 'white'
        self.active_color = style_color('white')
        self.strike = None
        self.last_impact = None
        self.events = []
        self.impacts = []          # every local impact, with its pool slots and when they are taken
        self.impact_slots = [dict(birth=-math.inf, impact=None) for _ in range(IMPACT_POOL_SIZE)]
        self.scorch_slots = [dict(birth=-math.inf, impact=None) for _ in range(SCORCH_POOL_SIZE)]
        self.diag = dict(schedule='deterministic-separated-events-bounded-return-strokes', palette='standard',
                         eventCount=0, activeEvent=False, activeStrokeCount=0, eventElapsedSeconds=0.0,
                         nextEventAtSeconds=None, lastEventGapSeconds=None, activeStyle='white', flash=0.0,
                         lastStrike=None,
                         sceneLight=dict(peakIntensity=LIGHTNING_LIGHT_PEAK, distance=LIGHTNING_LIGHT_RANGE, decay=2,
                                         shadows=False),
                         localImpact=dict(cooldownSeconds=LOCAL_STRIKE_COOLDOWN,
                                          playerGuardMeters=LOCAL_STRIKE_PLAYER_GUARD,
                                          upwardNormalMinimum=UPWARD_NORMAL_MIN, effectSlots=IMPACT_POOL_SIZE,
                                          sparkInstancesPerSlot=self.spark_count,
                                          puffInstancesPerSlot=self.puff_count, scorchSlots=SCORCH_POOL_SIZE,
                                          scorchLifetimeSeconds=SCORCH_LIFETIME, strikes=0, candidateAttempts=0,
                                          forcedCandidates=0,
                                          firstCandidateWithinEvents=LIGHTNING_CADENCE['darkstorm'][
                                              'firstLocalCandidateWithinEvents'],
                                          maxRemoteEvents=LIGHTNING_CADENCE['darkstorm'][
                                              'maxRemoteEventsBetweenLocalCandidates'],
                                          remoteEventsSinceStrike=0, raycastMisses=0, lastSurfaceDamage=None))
        self._clear_schedule()

    def _clear_schedule(self):
        self.event_start = -math.inf
        self.event_seed = -1
        self.plan = None
        self.sheet_scale = 0.0
        self.cadence_key = 'none'
        self.next_event_at = None
        self.last_schedule_t = None
        self.entry_count = 0
        self.remote_since_local = 0
        self.has_local = False

    def force_local_strike(self, now, w, k):
        """debugForceLocalStrike: the next event becomes a forced close forward strike, pulled to now + 0.6 s."""
        level = max(0.0, float(w.get('lightning', 0) or 0)) * max(0.0, min(1.0, float(k or 0)))
        if level <= 0.0001:
            return False
        self.debug_forced_pending = True
        if self.next_event_at is None or not math.isfinite(self.next_event_at) or self.next_event_at > now + 0.6:
            self.next_event_at = now + 0.6
        return True

    def clear_on_set_weather(self):
        """setWeather to a state with no lightning: clear the schedule and the flash at once."""
        self._clear_schedule()
        if self.strike:
            self.strike['flash'] = 0.0

    def _steal(self, slots, t, impact, key):
        oldest = min(slots, key=lambda s: s['birth'])
        if oldest['impact'] is not None:
            oldest['impact'][key] = min(oldest['impact'][key], t)
        oldest['birth'] = t
        oldest['impact'] = impact
        return slots.index(oldest)

    def step(self, t, w, k, cadence_target, cam, sky):
        ft = t if _finite(t) else 0.0
        flash = 0.0
        channel = 0.0
        level = max(0.0, min(1.0, float(w.get('lightning', 0) or 0) * max(0.0, float(k or 0))))
        cadence_key = ('darkstorm' if cadence_target == 'darkstorm'
                       or (cadence_target is None and w.get('lightningPalette') == 'darkstorm') else 'standard')
        began = False
        D = self.diag
        LI = D['localImpact']
        if level > 0.0001:
            rewound = self.last_schedule_t is not None and ft + 0.001 < self.last_schedule_t
            if rewound or self.cadence_key != cadence_key or not _finite(self.next_event_at):
                if self.cadence_key != cadence_key:
                    self.entry_count = 0
                    self.remote_since_local = 0
                    self.has_local = False
                self.event_start = -math.inf
                self.event_seed = -1
                self.plan = None
                self.sheet_scale = 0.0
                self.cadence_key = cadence_key
                first = lightning_initial_event_gap_at(self.event_index + 1, cadence_key, level, self.gap_scale)
                self.next_event_at = ft + first
                D['lastEventGapSeconds'] = first
            self.last_schedule_t = ft
            if ft >= self.next_event_at:
                self.event_index += 1
                self.event_seed = self.event_index
                self.event_start = ft
                self.plan = lightning_stroke_plan_at(self.event_seed, cadence_key)
                distant = max(0.0, min(1.0, float(w.get('distant', 0) or 0) * max(0.0, k)))
                self.sheet_scale = (0.10 + js_hash(self.event_seed * 89.17 + 37.1) * 0.12
                                    if js_hash(self.event_seed * 83.71 + 29.3) < distant else 0.0)
                gap = lightning_event_gap_at(self.event_index + 1, cadence_key, level, self.gap_scale)
                self.next_event_at = ft + gap
                D['eventCount'] += 1
                D['lastEventGapSeconds'] = gap
                if cadence_key == 'darkstorm':
                    self.entry_count += 1
                    self.remote_since_local += 1
                    LI['remoteEventsSinceStrike'] = self.remote_since_local
                began = True
            elapsed = ft - self.event_start
            if self.plan and elapsed <= self.plan['durationSeconds']:
                flash = lightning_flash_at(elapsed, self.plan)
                channel = lightning_channel_at(elapsed, self.plan)
            else:
                self.plan = None
                self.sheet_scale = 0.0
            if began and cam is not None:
                self._begin_event(ft, w, k, cadence_key, cam, sky, flash)
            owns = self.strike is not None and self.strike['interval'] == self.event_seed
            bolt_visible = owns and channel > 0.02
            channel_k = max(0.0, min(1.15, channel)) if owns else 0.0
            if owns:
                self.strike['flash'] = flash
        else:
            self._clear_schedule()
            if self.strike:
                self.strike['flash'] = 0.0
            bolt_visible, channel_k, owns = False, 0.0, False
        flash = max(0.0, min(1.15, flash)) if math.isfinite(flash) else 0.0
        st = self.strike
        afterglow = (math.exp(-max(0.0, ft - st['time']) * 18) * 0.18
                     if float(w.get('lightning', 0) or 0) > 0 and st and st['local'] else 0.0)
        scene_flash = max(0.0, min(1.0, flash + afterglow))
        light_pos = None
        if owns:
            light_pos = (st['x'], st['y'] + 10 if st['local'] else 120.0, st['z'])
        flash_d = max(0.0, min(0.22, flash * self.sheet_scale))
        D['palette'] = w.get('lightningPalette') or 'standard'
        D['activeStyle'] = self.active_key
        D['flash'] = flash
        D['activeEvent'] = self.plan is not None
        D['activeStrokeCount'] = self.plan['count'] if self.plan else 0
        D['eventElapsedSeconds'] = max(0.0, ft - self.event_start) if self.plan else 0.0
        D['nextEventAtSeconds'] = self.next_event_at if _finite(self.next_event_at) else None
        if st and st['interval'] == self.event_seed:
            D['lastStrike'] = dict(st)
        return dict(flash=flash, flash_d=flash_d, channel=channel_k, bolt_visible=bolt_visible,
                    bolt_seed=self.event_seed if bolt_visible else None, scene_flash=scene_flash,
                    light_intensity=scene_flash * LIGHTNING_LIGHT_PEAK, light_pos=light_pos,
                    color=self.active_color, color_key=self.active_key, began=began,
                    strike=dict(st) if st else None,
                    sky_strike=((st['x'] if st else 0.0), float(sky['cloudStart']), (st['z'] if st else 0.0), flash))

    def _begin_event(self, ft, w, k, cadence_key, cam, sky, flash):
        I = self.event_seed
        D = self.diag
        LI = D['localImpact']
        self.active_key = lightning_style_key_at(I, w.get('lightningPalette') or 'standard')
        self.active_color = style_color(self.active_key)
        sx, sz = storm_cell_strike_xz(I, sky['weather_at'], self.storm_center, self.storm_range)
        bottom_y = 2.0
        local = False
        hit_obj = None
        kind = 'distant_world_cell'
        normal = (0.0, 1.0, 0.0)
        local_chance = max(0.0, float(w.get('localStrikeChance', 0) or 0)) * k
        dk = LIGHTNING_CADENCE['darkstorm']
        forced = self.debug_forced_pending or (cadence_key == 'darkstorm' and (
            (not self.has_local and self.entry_count >= dk['firstLocalCandidateWithinEvents'])
            or self.remote_since_local >= dk['maxRemoteEventsBetweenLocalCandidates']))
        candidate = lightning_local_candidate_at(I, local_chance, palette_name=cadence_key,
                                                 entry_event_count=self.entry_count,
                                                 remote_events_since_local=self.remote_since_local,
                                                 has_local_strike=self.has_local)
        impact = None
        if self.debug_forced_pending or (ft - self.last_local_strike_at >= LOCAL_STRIKE_COOLDOWN and candidate):
            LI['candidateAttempts'] += 1
            if forced:
                LI['forcedCandidates'] += 1
            hit = self.find_local_strike(I, cam, sky, forced) if self.find_local_strike else None
            if hit:
                self.debug_forced_pending = False
                local = True
                sx, sz = hit['point'][0], hit['point'][2]
                bottom_y = hit['point'][1] + 0.04
                kind = hit.get('kind') or 'upward_surface'
                hit_obj = hit.get('object')
                normal = tuple(hit['normal'])
                self.last_local_strike_at = ft
                impact = self._trigger_impact(I, ft, hit['point'], normal, self.active_color)
                LI['strikes'] += 1
                if cadence_key == 'darkstorm':
                    self.has_local = True
                    self.remote_since_local = 0
                    LI['remoteEventsSinceStrike'] = 0
            else:
                LI['raycastMisses'] += 1
        strike_id = js_round(ft * 1000) * 1000 + I
        self.strike = dict(id=strike_id, interval=I, time=ft, x=sx, y=bottom_y, z=sz, cloudY=float(sky['cloudStart']),
                           normal=list(normal), kind=kind, colorKey=self.active_key,
                           colorHex=LIGHTNING_STYLES[self.active_key]['hex'], local=local, flash=flash)
        damage = None
        if local:
            damage = dict(id=strike_id, interval=I, time=ft, point=[sx, bottom_y, sz], normal=list(normal), kind=kind,
                          colorKey=self.active_key, colorHex=LIGHTNING_STYLES[self.active_key]['hex'],
                          radiusMeters=LOCAL_STRIKE_SURFACE_DAMAGE_RADIUS, scorchLifetimeSeconds=SCORCH_LIFETIME)
            self.last_impact = damage
            LI['lastSurfaceDamage'] = damage
            if self.on_local_strike:
                try:
                    self.on_local_strike(damage, hit_obj)
                except Exception as e:             # notification only: it never suppresses the visible impact
                    print('[weather] local-strike notification failed', e)
        D['lastStrike'] = dict(self.strike)
        self.events.append(dict(interval=I, time=ft, plan=self.plan, cadence=cadence_key, strike=dict(self.strike),
                                color=self.active_color, color_key=self.active_key, cam=dict(cam), impact=impact,
                                damage=damage, hit_object=hit_obj, cloud_start=float(sky['cloudStart'])))

    def _trigger_impact(self, I, t, point, normal, color):
        data = impact_particles(I, normal, self.spark_count, self.puff_count)
        impact = dict(interval=I, birth=t, point=tuple(point), color=tuple(color), data=data,
                      fx_end=t + PUFF_LIFE, scorch_end=t + SCORCH_LIFETIME)
        impact['slot'] = self._steal(self.impact_slots, t, impact, 'fx_end')
        impact['scorch_slot'] = self._steal(self.scorch_slots, t, impact, 'scorch_end')
        self.impacts.append(impact)
        return impact
