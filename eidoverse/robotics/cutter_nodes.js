// MIT. GPU counterpart of the analytic vertical cutter-envelope intersection.
import { float, Fn, If, sqrt } from "three/tsl";

export function cutterHeightNode(radius, kind) {
  return Fn(([xz, a, b]) => {
    const q = xz.sub(a.xz), v = b.xz.sub(a.xz), dy = b.y.sub(a.y);
    const h2 = v.dot(v),
      r2 = float(radius * radius),
      answer = float(1e6).toVar();
    If(h2.lessThan(1e-18), () => {
      const d2 = q.dot(q);
      If(d2.lessThanEqual(r2), () => {
        const cap = sqrt(r2.sub(d2).max(0));
        answer.assign(
          a.y.min(b.y).add(kind === "ball" ? float(radius).sub(cap) : 0),
        );
      });
    }).Else(() => {
      const h = sqrt(h2), projected = q.dot(v).div(h);
      // Subtracting two long squared distances loses the tiny radial distance
      // near a tangent. The 2D cross product retains it without cancellation;
      // otherwise boundary vertices can alternate between cut and uncut stock.
      const cross = q.x.mul(v.y).sub(q.y.mul(v.x));
      const perpendicular2 = cross.mul(cross).div(h2);
      If(perpendicular2.lessThanEqual(r2), () => {
        const section = sqrt(r2.sub(perpendicular2).max(0));
        const lo = projected.sub(section).div(h).max(0),
          hi = projected.add(section).div(h).min(1);
        If(lo.lessThanEqual(hi), () => {
          const t = float(0).toVar();
          if (kind === "ball") {
            t.assign(
              projected.sub(dy.mul(section).div(sqrt(h2.add(dy.mul(dy))))).div(
                h,
              ).clamp(lo, hi),
            );
          } else {
            If(dy.greaterThanEqual(0), () => {
              t.assign(lo);
            }).Else(() => {
              t.assign(hi);
            });
          }
          const delta = q.sub(v.mul(t));
          const cap = sqrt(r2.sub(delta.dot(delta)).max(0));
          answer.assign(
            a.y.add(dy.mul(t)).add(
              kind === "ball" ? float(radius).sub(cap) : 0,
            ),
          );
        });
      });
    });
    return answer;
  });
}
