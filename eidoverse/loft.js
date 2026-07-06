// loft.js — LOFT MODELING for eidoverse scenes.
//
// Lofting skins a surface through a series of cross sections — the general
// case of LatheGeometry (fixed profile revolved) and TubeGeometry (circle
// swept along a path): here the section can be ANY shape and can change
// shape, size, position and orientation along the loft. Vases, horns,
// fuselages, ducts, blades, tentacles, trumpet bells, curved corridors,
// rivers/roads as ribbons, melted/organic architecture.
//
// Core class implements loft/skin surface generation over ordered
// cross-sections; the `Loft` namespace adds the agent-facing conveniences.
//
// API (all on globalThis):
//
//   // 1) PROFILES — Vector2 ring generators (CCW, profile space)
//   Loft.circle(r, n=24)            Loft.ellipse(rx, ry, n=24)
//   Loft.rect(w, h, n=24)           Loft.polygon(sides, r)
//   Loft.star(rOuter, rInner, points=5)
//   Loft.fromShape(threeShape, n)   // any THREE.Shape outline
//
//   // 2) SWEEP — profile(s) along a curve → ready Mesh. The workhorse.
//   const mesh = Loft.sweep({
//       path: curveOrPointArray,    // THREE.Curve, or [Vector3,...] (CatmullRom)
//       profile: Loft.circle(0.5),  // section ring (Vector2s)
//       profileEnd: Loft.star(0.6, 0.25, 6),  // optional: morph to this (same length!)
//       sections: 48,               // rows along the path
//       scale: t => 1 - 0.6 * t,    // number or fn(t 0..1) — taper
//       twist: Math.PI * 2,         // total radians, or fn(t) → radians
//       closed: true,               // ring section (default) vs open ribbon
//       capStart: true, capEnd: true,
//       material,                   // default MeshStandardNodeMaterial
//   });
//   scene.add(mesh);
//
//   // 3) RAW — full control over every section (rings of Vector3s)
//   const geo = new LoftGeometry(sections, { closed, capStart, capEnd });
//
// Rules of the craft:
//   - every section must have the SAME number of points; sweep() resamples
//     profileEnd is NOT resampled — generate both with the same n.
//   - sections wind CCW (seen from the loft's end looking back) for
//     outward normals. Loft.* profiles already do; if a custom loft renders
//     inside-out, reverse each section's point order.
//   - uv.x runs along the loft (0→1 start→end), uv.y around the section —
//     texture.repeat.set(alongCount, aroundCount).
//   - sweep() uses the curve's Frenet frames: a path with an inflection
//     can flip the frame — if the loft "kinks", add path points to smooth
//     the curve or rotate the kink out with `twist`.

(function () {
    const THREE = globalThis.THREE;
    const { BufferGeometry, Float32BufferAttribute, ShapeUtils, Vector2, Vector3 } = THREE;

    const _vector = new Vector3();

    // ── LoftGeometry — cross-section skinning geometry ─────────────────────
    class LoftGeometry extends BufferGeometry {

        constructor(sections = [], options = {}) {
            super();
            this.type = 'LoftGeometry';
            const { closed = true, capStart = false, capEnd = false } = options;
            this.parameters = { sections, closed, capStart, capEnd };

            const rows = sections.length;
            if (rows < 2) {
                console.error('LoftGeometry: At least two sections are required.');
                return;
            }
            const columns = sections[0].length;
            for (let i = 1; i < rows; i++) {
                if (sections[i].length !== columns) {
                    console.error('LoftGeometry: All sections must have the same number of points.');
                    return;
                }
            }

            // closed sections repeat their first point so the surface wraps
            // with continuous uvs
            const pointsPerRow = closed ? columns + 1 : columns;

            const indices = [];
            const vertices = [];
            const uvs = [];

            for (let i = 0; i < rows; i++) {
                const section = sections[i];
                for (let j = 0; j < pointsPerRow; j++) {
                    const point = section[j % columns];
                    vertices.push(point.x, point.y, point.z);
                    uvs.push(i / (rows - 1), j / (pointsPerRow - 1));
                }
            }

            for (let i = 0; i < rows - 1; i++) {
                for (let j = 0; j < pointsPerRow - 1; j++) {
                    const a = i * pointsPerRow + j;
                    const b = i * pointsPerRow + j + 1;
                    const c = (i + 1) * pointsPerRow + j + 1;
                    const d = (i + 1) * pointsPerRow + j;
                    indices.push(a, b, d);
                    indices.push(b, c, d);
                }
            }

            if (capStart === true) generateCap(0);
            if (capEnd === true) generateCap(rows - 1);

            this.setIndex(indices);
            this.setAttribute('position', new Float32BufferAttribute(vertices, 3));
            this.setAttribute('uv', new Float32BufferAttribute(uvs, 2));
            this.computeVertexNormals();

            // seam vertices of closed sections are duplicated — average their
            // normals for smooth shading across the seam
            if (closed === true) {
                const normals = this.getAttribute('normal');
                for (let i = 0; i < rows; i++) {
                    const a = i * pointsPerRow;
                    const b = i * pointsPerRow + (pointsPerRow - 1);
                    _vector.set(
                        normals.getX(a) + normals.getX(b),
                        normals.getY(a) + normals.getY(b),
                        normals.getZ(a) + normals.getZ(b)
                    ).normalize();
                    normals.setXYZ(a, _vector.x, _vector.y, _vector.z);
                    normals.setXYZ(b, _vector.x, _vector.y, _vector.z);
                }
            }

            function generateCap(sectionIndex) {
                const section = sections[sectionIndex];

                // centroid + plane normal via Newell's method
                const centroid = new Vector3();
                const normal = new Vector3();
                for (let i = 0; i < columns; i++) {
                    const p = section[i];
                    const q = section[(i + 1) % columns];
                    centroid.add(p);
                    normal.x += (p.y - q.y) * (p.z + q.z);
                    normal.y += (p.z - q.z) * (p.x + q.x);
                    normal.z += (p.x - q.x) * (p.y + q.y);
                }
                centroid.divideScalar(columns);
                normal.normalize();

                // cap must face away from the rest of the surface
                const neighbor = sections[sectionIndex === 0 ? 1 : rows - 2];
                _vector.set(0, 0, 0);
                for (let i = 0; i < columns; i++) _vector.add(neighbor[i]);
                _vector.divideScalar(columns).sub(centroid);
                if (normal.dot(_vector) > 0) normal.negate();

                // project the section onto the cap plane
                const tangent = new Vector3(1, 0, 0);
                if (Math.abs(normal.x) > 0.9) tangent.set(0, 1, 0);
                const bitangent = new Vector3().crossVectors(normal, tangent).normalize();
                tangent.crossVectors(bitangent, normal);

                const contour = [];
                const points = section.slice();
                for (let i = 0; i < columns; i++) {
                    _vector.subVectors(points[i], centroid);
                    contour.push(new Vector2(_vector.dot(tangent), _vector.dot(bitangent)));
                }

                if (ShapeUtils.isClockWise(contour) === true) {
                    contour.reverse();
                    points.reverse();
                }
                const faces = ShapeUtils.triangulateShape(contour, []);

                const min = new Vector2(Infinity, Infinity);
                const max = new Vector2(-Infinity, -Infinity);
                for (let i = 0; i < columns; i++) {
                    min.min(contour[i]);
                    max.max(contour[i]);
                }
                const width = Math.max(max.x - min.x, Number.EPSILON);
                const height = Math.max(max.y - min.y, Number.EPSILON);

                // cap vertices are not shared with the wall → hard edge
                const indexOffset = vertices.length / 3;
                for (let i = 0; i < columns; i++) {
                    const point = points[i];
                    vertices.push(point.x, point.y, point.z);
                    uvs.push((contour[i].x - min.x) / width, (contour[i].y - min.y) / height);
                }
                for (let i = 0; i < faces.length; i++) {
                    const face = faces[i];
                    indices.push(indexOffset + face[0], indexOffset + face[1], indexOffset + face[2]);
                }
            }
        }

        copy(source) {
            super.copy(source);
            this.parameters = Object.assign({}, source.parameters);
            return this;
        }
    }

    // ── Profile generators (Vector2 rings, CCW) ────────────────────────────
    function circle(r = 1, n = 24) {
        const pts = [];
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2;
            pts.push(new Vector2(Math.cos(a) * r, Math.sin(a) * r));
        }
        return pts;
    }
    function ellipse(rx = 1, ry = 0.6, n = 24) {
        const pts = [];
        for (let i = 0; i < n; i++) {
            const a = (i / n) * Math.PI * 2;
            pts.push(new Vector2(Math.cos(a) * rx, Math.sin(a) * ry));
        }
        return pts;
    }
    function polygon(sides = 6, r = 1) {
        return circle(r, sides);
    }
    function star(rOuter = 1, rInner = 0.45, points = 5) {
        const pts = [];
        for (let i = 0; i < points * 2; i++) {
            const a = (i / (points * 2)) * Math.PI * 2;
            const r = (i % 2 === 0) ? rOuter : rInner;
            pts.push(new Vector2(Math.cos(a) * r, Math.sin(a) * r));
        }
        return pts;
    }
    // rectangle outline resampled to n evenly spaced points (corners kept)
    function rect(w = 1, h = 1, n = 24) {
        const hw = w / 2, hh = h / 2;
        const corners = [
            new Vector2(hw, -hh), new Vector2(hw, hh),
            new Vector2(-hw, hh), new Vector2(-hw, -hh),
        ];
        return _resampleOutline(corners, n);
    }
    function fromShape(shape, n = 48) {
        const pts = shape.getPoints(Math.max(8, Math.ceil(n / 2)));
        // drop a duplicated closing point if present
        if (pts.length > 1 && pts[0].distanceTo(pts[pts.length - 1]) < 1e-6) pts.pop();
        const ring = _resampleOutline(pts, n);
        // ensure CCW so the loft's normals point outward
        if (ShapeUtils.isClockWise(ring)) ring.reverse();
        return ring;
    }
    function _resampleOutline(loop, n) {
        const m = loop.length;
        const segLens = [];
        let total = 0;
        for (let i = 0; i < m; i++) {
            const l = loop[i].distanceTo(loop[(i + 1) % m]);
            segLens.push(l); total += l;
        }
        const out = [];
        let seg = 0, acc = 0;
        for (let i = 0; i < n; i++) {
            const target = (i / n) * total;
            while (acc + segLens[seg] < target) { acc += segLens[seg]; seg = (seg + 1) % m; }
            const f = segLens[seg] > 0 ? (target - acc) / segLens[seg] : 0;
            out.push(new Vector2().lerpVectors(loop[seg], loop[(seg + 1) % m], f));
        }
        return out;
    }

    // ── sweep — profile(s) along a curve with taper/twist/morph → Mesh ────
    function sweep(opts = {}) {
        let path = opts.path;
        if (Array.isArray(path)) path = new THREE.CatmullRomCurve3(path);
        if (!path || !path.getPointAt) throw new Error('Loft.sweep: path must be a THREE.Curve or an array of Vector3');

        const profile = opts.profile ?? circle(0.5, 24);
        const profileEnd = opts.profileEnd ?? null;
        if (profileEnd && profileEnd.length !== profile.length)
            throw new Error(`Loft.sweep: profile (${profile.length}) and profileEnd (${profileEnd.length}) must have the same point count`);
        const rows = Math.max(2, opts.sections ?? 32);
        const scaleOpt = opts.scale ?? 1;
        const scaleAt = (typeof scaleOpt === 'function') ? scaleOpt : () => scaleOpt;
        const twistOpt = opts.twist ?? 0;
        const twistAt = (typeof twistOpt === 'function') ? twistOpt : (t) => twistOpt * t;
        const profileFn = opts.profileFn ?? null;   // fn(t) → Vector2 ring (advanced)

        const frames = path.computeFrenetFrames(rows - 1, false);
        const sections = [];
        for (let i = 0; i < rows; i++) {
            const t = i / (rows - 1);
            const origin = path.getPointAt(t);
            const N = frames.normals[i], B = frames.binormals[i];
            const s = scaleAt(t);
            const tw = twistAt(t);
            const cosT = Math.cos(tw), sinT = Math.sin(tw);
            let ring = profileFn ? profileFn(t) : profile;
            const ringEnd = profileEnd;
            const sec = [];
            for (let j = 0; j < profile.length; j++) {
                let px = ring[j].x, py = ring[j].y;
                if (!profileFn && ringEnd) {
                    px = px + (ringEnd[j].x - px) * t;
                    py = py + (ringEnd[j].y - py) * t;
                }
                // twist in profile space, then map onto the frame
                const rx = (px * cosT - py * sinT) * s;
                const ry = (px * sinT + py * cosT) * s;
                sec.push(new Vector3(
                    origin.x + N.x * rx + B.x * ry,
                    origin.y + N.y * rx + B.y * ry,
                    origin.z + N.z * rx + B.z * ry,
                ));
            }
            sections.push(sec);
        }

        const closed = opts.closed ?? true;
        const geo = new LoftGeometry(sections, {
            closed,
            capStart: opts.capStart ?? closed,
            capEnd: opts.capEnd ?? closed,
        });
        const mat = opts.material ?? new THREE.MeshStandardNodeMaterial({
            color: 0xb8b8c0, roughness: 0.6, metalness: 0.1, side: closed ? THREE.FrontSide : THREE.DoubleSide,
        });
        const mesh = new THREE.Mesh(geo, mat);
        mesh.castShadow = mesh.receiveShadow = true;
        return mesh;
    }

    globalThis.LoftGeometry = LoftGeometry;
    globalThis.Loft = { circle, ellipse, polygon, star, rect, fromShape, sweep, LoftGeometry };
    (globalThis._eidoToolUsage = globalThis._eidoToolUsage || new Set()).add('loft');
    console.log('[loft] LoftGeometry + Loft.{circle,ellipse,polygon,star,rect,fromShape,sweep} ready');
})();
