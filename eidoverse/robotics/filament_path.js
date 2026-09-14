// MIT. Direct-drive retraction/prime dwell and conserved filament volume.
export class FilamentPath {
  constructor(
    path,
    { filamentDiameter = .00175, retractLength = .0008, retractSpeed = .035 } =
      {},
  ) {
    if (
      ![filamentDiameter, retractSpeed].every((v) =>
        v > 0 && Number.isFinite(v)
      ) || !(retractLength >= 0 && Number.isFinite(retractLength))
    ) throw Error("Invalid filament or retraction dimensions");
    this.feedPath = path;
    this.area = Math.PI * filamentDiameter ** 2 / 4;
    this.filamentDiameter = filamentDiameter;
    this.volume = path.volume;
    this.length = path.length;
    this.spans = [];
    this.segments = [];
    this.retractLength = retractLength;
    let offset = 0, previous = null, retracted = false;
    for (const segment of path.segments) {
      const retract = segment.type === "rapid" && previous?.type === "extrude";
      const prime = segment.type === "extrude" && retracted;
      if ((retract || prime) && retractLength > 0) {
        const duration = retractLength / retractSpeed;
        this.spans.push({
          t0: segment.t0 + offset,
          t1: segment.t0 + offset + duration,
          baseTime: segment.t0,
          type: retract ? "retract" : "prime",
          e0: retract ? 0 : retractLength,
          e1: retract ? retractLength : 0,
        });
        offset += duration;
        retracted = retract;
      }
      this.spans.push({
        t0: segment.t0 + offset,
        t1: segment.t1 + offset,
        baseTime: segment.t0,
        type: "move",
        retraction: retracted ? retractLength : 0,
      });
      this.segments.push({
        ...segment,
        t0: segment.t0 + offset,
        t1: segment.t1 + offset,
      });
      previous = segment;
    }
    this.duration = path.duration + offset;
    this.retractionTime = offset;
    this.filamentLength = this.volume / this.area;
  }
  sample(seconds) {
    const time = Math.max(0, Math.min(this.duration, seconds));
    let lo = 0, hi = this.spans.length - 1;
    while (lo < hi) {
      const m = (lo + hi) >> 1;
      if (this.spans[m].t1 < time) lo = m + 1;
      else hi = m;
    }
    const span = this.spans[lo],
      dwell = span.type !== "move",
      dt = time - span.t0;
    const state = this.feedPath.sample(span.baseTime + (dwell ? 0 : dt));
    const retraction = dwell
      ? span.e0 + (span.e1 - span.e0) * Math.min(1, dt / (span.t1 - span.t0))
      : span.retraction;
    const filamentSpeed = dwell
      ? -(span.e1 - span.e0) / (span.t1 - span.t0)
      : state.type === "extrude"
      ? state.speed * this.feedPath.beadArea / this.area
      : 0;
    return {
      ...state,
      time,
      type: dwell ? span.type : state.type,
      ...(dwell
        ? { speed: 0, velocity: [0, 0, 0], acceleration: [0, 0, 0] }
        : {}),
      filamentLength: state.volume / this.area,
      filamentPosition: state.volume / this.area - retraction,
      filamentRetraction: retraction,
      filamentSpeed,
      done: time >= this.duration,
    };
  }
}
