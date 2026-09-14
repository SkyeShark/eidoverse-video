// MIT. GPU solid subtraction in stock-local coordinates, with seekable history.
// A floating-point 3D scalar field is stored in tiled 2D render targets so the
// same implementation runs in native WebGPU and the browser WebGL backend.
import * as T from "three/webgpu";
import {
  abs,
  Break,
  cameraPosition,
  cameraProjectionMatrix,
  cameraViewMatrix,
  clamp,
  float,
  floor,
  Fn,
  If,
  int,
  ivec2,
  Loop,
  max,
  min,
  mix,
  modelWorldMatrix,
  positionWorld,
  sqrt,
  texture,
  textureLoad,
  transformNormalToView,
  uniform,
  uv,
  vec2,
  vec3,
  vec4,
} from "three/tsl";
import { finishStock, stockProfile } from "./cutting.js";
import { CENTRE_SEAT } from "./rotary_path.js";

function dataTexture(values, width = 1024) {
  const h = Math.max(1, Math.ceil(values.length / 4 / width)),
    data = new Float32Array(width * h * 4);
  data.set(values);
  const t = new T.DataTexture(data, width, h, T.RGBAFormat, T.FloatType);
  t.name = "eidoverse/data/rotary-sweep-index";
  t.needsUpdate = true;
  t.generateMipmaps = false;
  return t;
}
export function indexRotarySweeps(
  path,
  settings,
  bounds,
  dims = [40, 16, 16],
  band = .002,
) {
  const { radius, fluteLength } = settings, lo = bounds.min, hi = bounds.max;
  const bins = Array.from({ length: dims[0] * dims[1] * dims[2] }, () => []),
    records = [];
  const cell = lo.map((v, k) => (hi[k] - v) / dims[k]);
  for (const s of path.segments) {
    records.push(...s.a, s.a0, ...s.b, s.type === "cut" ? 1 : 0);
    if (s.type !== "cut") continue;
    const c = Math.cos(s.a0), sn = Math.sin(s.a0), p = [];
    for (const v of [s.a, s.b]) {
      for (const h of [settings.tool === 'flat' ? 0 : radius, fluteLength]) {
        p.push([v[0], (v[1] + h) * c + v[2] * sn, -(v[1] + h) * sn + v[2] * c]);
      }
    }
    const low = [0, 1, 2].map((k) =>
        Math.min(...p.map((v) => v[k])) - radius - band
      ),
      high = [0, 1, 2].map((k) =>
        Math.max(...p.map((v) => v[k])) + radius + band
      );
    const a = low.map((v, k) => Math.max(0, Math.floor((v - lo[k]) / cell[k]))),
      b = high.map((v, k) =>
        Math.min(dims[k] - 1, Math.floor((v - lo[k]) / cell[k]))
      );
    for (let z = a[2]; z <= b[2]; z++) {
      for (let y = a[1]; y <= b[1]; y++) {
        for (
          let x = a[0];
          x <= b[0];
          x++
        ) bins[x + dims[0] * (y + dims[1] * z)].push(s.index);
      }
    }
  }
  const links = [], headers = [];
  for (const b of bins) {
    headers.push(links.length, b.length, 0, 0);
    links.push(...b);
  }
  const packedLinks = new Float32Array(Math.ceil(links.length / 4) * 4);
  packedLinks.set(links);
  return {
    bins,
    headers,
    records,
    links: packedLinks,
    dims,
    cell,
    maxBin: Math.max(...bins.map((b) => b.length)),
    bounds,
  };
}

export function createRotaryStock(
  path,
  settings,
  { renderer, parent, resolution = [256, 96, 96], color } = {},
) {
  if (!renderer) {
    throw Error("Rotary volume milling requires its scene renderer");
  }
  if (
    resolution.length !== 3 ||
    resolution.some((n) => !Number.isInteger(n) || n < 24 || n > 512)
  ) throw Error("Invalid stock resolution");
  const [nx, ny, nz] = resolution,
    { stockLength: L, stockWidth: W, stockHeight: H, radius: R, fluteLength } =
      settings;
  const eps = Math.max(L / (nx - 4), H / (ny - 4), W / (nz - 4)),
    pad = eps * 2,
    band = eps * 3;
  const bounds = {
    min: [-L / 2 - pad, -H / 2 - pad, -W / 2 - pad],
    max: [L / 2 + pad, H / 2 + pad, W / 2 + pad],
  };
  const extent = bounds.max.map((v, k) => v - bounds.min[k]),
    cell = extent.map((v, k) => v / (resolution[k] - 1));
  const indexed = indexRotarySweeps(path, settings, bounds, [40, 16, 16], band);
  const headers = dataTexture(indexed.headers),
    links = dataTexture(indexed.links),
    records = dataTexture(indexed.records);
  const cols = Math.ceil(Math.sqrt(nz)),
    rows = Math.ceil(nz / cols),
    width = nx * cols,
    height = ny * rows;
  const targets = [0, 1].map(() =>
    new T.RenderTarget(width, height, {
      type: T.HalfFloatType,
      format: T.RGBAFormat,
      depthBuffer: false,
      stencilBuffer: false,
      minFilter: T.NearestFilter,
      magFilter: T.NearestFilter,
      generateMipmaps: false,
    })
  );
  targets.forEach((t, i) => t.texture.name = "eidoverse/rotary-stock/" + i);
  // Allocate both attachments before either is sampled. Lazy allocation of a
  // sampled render-target texture otherwise precedes render-target setup.
  targets.forEach((t) => renderer.initRenderTarget(t));
  const fieldIndex = uniform(0, "int");
  const cursor = uniform(0, "int"),
    begin = uniform(0, "int"),
    fraction = uniform(0),
    reset = uniform(1, "int");
  const at = (tex, i) =>
    textureLoad(tex, ivec2(i.mod(int(1024)), i.div(int(1024))));
  const linkAt = (i) => {
    const v = at(links, i.div(int(4)));
    return int(v.element(i.mod(int(4))));
  };
  const segDist = Fn(([p, a, b]) => {
    const v = b.sub(a),
      q = p.sub(a),
      t = q.dot(v).div(v.dot(v).max(1e-16)).clamp(0, 1);
    return q.sub(v.mul(t)).length();
  });
  const cutDistance = Fn(([point, aa, bb, f]) => {
    const c = aa.w.cos(),
      s = aa.w.sin(),
      p = vec3(
        point.x,
        point.y.mul(c).sub(point.z.mul(s)),
        point.y.mul(s).add(point.z.mul(c)).sub(aa.z),
      );
    if (settings.tool === 'flat') {
      const d=bb.xy.sub(aa.xy).mul(f),q=p.xy.sub(aa.xy);
      const w=sqrt(max(float(R*R).sub(p.z.mul(p.z)),0));
      const tx=q.x.clamp(min(0,d.x),max(0,d.x));
      const radial=vec2(q.x.sub(tx),p.z).length().sub(R);
      const lo=float(0).toVar(),hi=float(1).toVar(),normalizer=float(1).toVar();
      If(d.x.abs().greaterThan(1e-12),()=>{
        const a=q.x.sub(w).div(d.x),b=q.x.add(w).div(d.x);
        lo.assign(min(a,b).clamp(0,1));hi.assign(max(a,b).clamp(0,1));
        const slope=d.y.div(d.x),lateral=p.z.div(w.max(1e-7));
        normalizer.assign(sqrt(float(1).add(slope.mul(slope).mul(float(1).add(lateral.mul(lateral))))));
      });
      const bottom=min(lo.mul(d.y),hi.mul(d.y)),top=max(lo.mul(d.y),hi.mul(d.y)).add(fluteLength);
      return max(radial,max(bottom.sub(q.y).div(normalizer),q.y.sub(top).div(normalizer)));
    }
    const a = vec2(aa.x, aa.y.add(R)),
      b = mix(a, vec2(bb.x, bb.y.add(R)), f),
      q = p.xy;
    const h = vec2(0, fluteLength - R), topA = a.add(h), topB = b.add(h);
    const distance = min(
      min(segDist(q, a, b), segDist(q, b, topB)),
      min(segDist(q, topB, topA), segDist(q, topA, a)),
    ).toVar();
    const dx = b.x.sub(a.x),
      u = q.x.sub(a.x).div(dx.abs().max(1e-12)).mul(dx.sign());
    const bottom = mix(a.y, b.y, u);
    If(
      dx.abs().greaterThan(1e-10).and(u.greaterThanEqual(0)).and(
        u.lessThanEqual(1),
      ).and(q.y.greaterThanEqual(bottom)).and(
        q.y.lessThanEqual(bottom.add(fluteLength - R)),
      ),
      () => distance.assign(0),
    );
    return sqrt(distance.mul(distance).add(p.z.mul(p.z))).sub(R);
  });
  const bake = (source) =>
    Fn(() => {
      const xy = ivec2(uv().flipY().mul(vec2(width, height))),
        tile = xy.div(ivec2(nx, ny)),
        zi = tile.x.add(tile.y.mul(int(cols)));
      const ijk = ivec2(xy.x.mod(int(nx)), xy.y.mod(int(ny)));
      const p = vec3(float(ijk.x), float(ijk.y), float(zi)).mul(vec3(...cell))
        .add(vec3(...bounds.min));
      const q = p.abs().sub(vec3(L / 2, H / 2, W / 2)),
        box = q.max(0).length().add(min(max(q.x, max(q.y, q.z)), 0));
      const rho = p.yz.length(),
        seatHeight = p.x.sub(L / 2 - CENTRE_SEAT.depth);
      const cone = max(
        rho.mul(Math.cos(CENTRE_SEAT.halfAngle))
          .sub(seatHeight.mul(Math.sin(CENTRE_SEAT.halfAngle))),
        seatHeight.negate(),
      );
      const pilot = max(
        rho.sub(CENTRE_SEAT.pilotRadius),
        float(L / 2 - CENTRE_SEAT.pilotDepth).sub(p.x),
      );
      const value = max(box, min(cone, pilot).negate()).clamp(-band, band)
        .toVar();
      If(reset.equal(0), () => value.assign(textureLoad(source, xy).r));
      const bi = p.sub(vec3(...bounds.min)).div(vec3(...indexed.cell)).floor()
        .clamp(vec3(0), vec3(...indexed.dims.map((n) => n - 1)));
      const id = int(bi.x).add(int(bi.y).mul(int(indexed.dims[0]))).add(
        int(bi.z).mul(int(indexed.dims[0] * indexed.dims[1])),
      );
      const head = at(headers, id), offset = int(head.x), count = int(head.y);
      // Find the first potentially changed stroke in a bin. Old complete cuts
      // already live in the previous GPU field. Rewind explicitly rebuilds it.
      const low = int(0).toVar(), high = count.toVar();
      Loop({ start: 0, end: 16, type: "int" }, () => {
        If(low.greaterThanEqual(high), () => Break());
        const mid = low.add(high).div(int(2)), sid = linkAt(offset.add(mid));
        If(sid.lessThan(begin), () => low.assign(mid.add(int(1)))).Else(() =>
          high.assign(mid)
        );
      });
      Loop({ start: low, end: count, type: "int" }, ({ i }) => {
        const sid = linkAt(offset.add(i));
        If(sid.greaterThan(cursor), () => Break());
        const aa = at(records, sid.mul(int(2))),
          bb = at(records, sid.mul(int(2)).add(int(1))),
          f = float(1).toVar();
        If(sid.equal(cursor), () => f.assign(fraction));
        value.assign(
          max(value, cutDistance(p, aa, bb, f).negate()).clamp(-band, band),
        );
      });
      return vec4(value, 0, 0, 1);
    });
  // Each pass permanently samples the opposite target. This also avoids stale
  // bind groups and render-object geometry reuse on the native WebGPU backend.
  const passes = targets.map((target) => {
    const material = new T.MeshBasicNodeMaterial({
      depthTest: false,
      depthWrite: false,
    });
    material.fragmentNode = bake(target.texture)();
    const geometry = new T.PlaneGeometry(2, 2);
    geometry.deleteAttribute("normal");
    const quad = new T.Mesh(geometry, material), scene = new T.Scene();
    scene.add(quad);
    return { material, geometry, scene };
  });
  const updateCamera = new T.OrthographicCamera(-1, 1, 1, -1, 0, 1);
  const read = Fn(([p]) => {
    const g = p.sub(vec3(...bounds.min)).div(vec3(...cell)),
      base = floor(g),
      f = g.sub(base);
    const voxel = (dx, dy, dz) => {
      const v = base.add(vec3(dx, dy, dz)).clamp(
        vec3(0),
        vec3(nx - 1, ny - 1, nz - 1),
      );
      const z = int(v.z),
        xy = ivec2(
          int(v.x).add(z.mod(int(cols)).mul(int(nx))),
          int(v.y).add(z.div(int(cols)).mul(int(ny))),
        );
      return fieldIndex.equal(0).select(
        textureLoad(targets[0].texture, xy).r,
        textureLoad(targets[1].texture, xy).r,
      );
    };
    return mix(
      mix(
        mix(voxel(0, 0, 0), voxel(1, 0, 0), f.x),
        mix(voxel(0, 1, 0), voxel(1, 1, 0), f.x),
        f.y,
      ),
      mix(
        mix(voxel(0, 0, 1), voxel(1, 0, 1), f.x),
        mix(voxel(0, 1, 1), voxel(1, 1, 1), f.x),
        f.y,
      ),
      f.z,
    );
  });
  const inverse = uniform(new T.Matrix4());
  const march = Fn(() => {
    const ro = inverse.mul(vec4(cameraPosition, 1)).xyz,
      rd = inverse.mul(vec4(positionWorld.sub(cameraPosition).normalize(), 0))
        .xyz.normalize();
    const inv = vec3(1).div(rd),
      a = vec3(...bounds.min).sub(ro).mul(inv),
      b = vec3(...bounds.max).sub(ro).mul(inv),
      near = min(a, b),
      far = max(a, b);
    const enter = max(near.x, max(near.y, near.z)).max(0),
      exit = min(far.x, min(far.y, far.z));
    const t = enter.toVar(),
      found = float(0).toVar(),
      hit = ro.add(rd.mul(t)).toVar();
    Loop({ start: 0, end: 480, type: "int" }, () => {
      If(t.greaterThan(exit), () => Break());
      hit.assign(ro.add(rd.mul(t)));
      const d = read(hit);
      If(d.lessThan(eps * .025), () => {
        found.assign(1);
        Break();
      });
      // The field is distance-clamped, which keeps interpolation/cell skipping
      // bounded around fine cuts while still stepping quickly through open air.
      t.addAssign(d.max(eps * .04).mul(.8));
    });
    return vec4(hit, found);
  })();
  const hp = march.xyz;
  const normal = vec3(
    read(hp.add(vec3(cell[0], 0, 0))).sub(read(hp.sub(vec3(cell[0], 0, 0)))),
    read(hp.add(vec3(0, cell[1], 0))).sub(read(hp.sub(vec3(0, cell[1], 0)))),
    read(hp.add(vec3(0, 0, cell[2]))).sub(read(hp.sub(vec3(0, 0, cell[2])))),
  ).div(vec3(...cell)).normalize();
  const profile = stockProfile(settings.material),
    material = new T.MeshStandardNodeMaterial({
      side: T.BackSide,
      metalness: profile.metalness,
      roughness: profile.roughness,
    });
  material.normalNode = transformNormalToView(normal);
  material.opacityNode = march.w;
  material.alphaTest = .5;
  // finishStock accepts a fragment hit position too: do not turn this into a
  // vertex varying, which would shade the proxy rather than the carved object.
  finishStock(material, vec3(hp.z, hp.y, hp.x), profile, color, {
    fragment: true,
  });
  const clip = cameraProjectionMatrix.mul(cameraViewMatrix).mul(
    modelWorldMatrix,
  ).mul(vec4(hp, 1));
  material.depthNode = renderer.backend?.isWebGLBackend
    ? clip.z.div(clip.w).mul(.5).add(.5)
    : clip.z.div(clip.w);
  const mesh = new T.Mesh(new T.BoxGeometry(...extent), material);
  mesh.name = "Rotary volumetric stock";
  mesh.frustumCulled = false;
  mesh.receiveShadow = true;
  mesh.onBeforeRender = () => {
    inverse.value.copy(mesh.matrixWorld).invert();
  };
  parent.add(mesh);
  let previous = null, targetIndex = 0, time = -1;
  const api = {
    mesh,
    bounds,
    cellSize: cell,
    resolution,
    index: indexed,
    settings,
    get texture() {
      return targets[targetIndex].texture;
    },
    update(state) {
      if (state.time === time) return;
      const rebuild = !previous || state.time < time;
      cursor.value = state.index;
      fraction.value = state.fraction;
      begin.value = rebuild ? 0 : previous.index;
      reset.value = rebuild ? 1 : 0;
      const source = targetIndex;
      targetIndex = 1 - source;
      const old = renderer.getRenderTarget(), oldAuto = renderer.autoClear;
      try {
        renderer.setRenderTarget(targets[targetIndex]);
        renderer.autoClear = true;
        renderer.render(passes[source].scene, updateCamera);
      } finally {
        renderer.setRenderTarget(old);
        renderer.autoClear = oldAuto;
      }
      fieldIndex.value = targetIndex;
      previous = { ...state };
      time = state.time;
    },
    async readback() {
      return renderer.readRenderTargetPixelsAsync(
        targets[targetIndex],
        0,
        0,
        width,
        height,
      );
    },
    layout: { width, height, cols, nx, ny, nz },
    dispose() {
      mesh.removeFromParent();
      mesh.geometry.dispose();
      material.dispose();
      passes.forEach((p) => {
        p.geometry.dispose();
        p.material.dispose();
      });
      targets.forEach((t) => t.dispose());
      [headers, links, records].forEach((t) => t.dispose());
    },
  };
  return api;
}
