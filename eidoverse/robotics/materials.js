// MIT. Preserve the approved linear mask composition and reflected tangent frames.
import * as T from "three/webgpu";
import { normalMap, texture, uniform, vec2 } from "three/tsl";
import { imageTexture } from "./io.js";
export async function prepareMaterials(scene, modelURL, opts = {}) {
  const originals = new Set();
  scene.traverse((o) => {
    if (o.isMesh) { for (const m of [].concat(o.material)) originals.add(m); }
  });
  const palette = {
    primary: uniform(new T.Color()),
    accent: uniform(new T.Color()),
    filament: uniform(new T.Color(opts.filament ?? "#218675")),
  };
  let initialized = false;
  const materialMap = new Map();
  for (const old of originals) {
    const m = new T.MeshStandardNodeMaterial();
    for (
      const key of [
        "map",
        "normalMap",
        "roughnessMap",
        "metalnessMap",
        "aoMap",
        "emissiveMap",
        "side",
        "transparent",
        "opacity",
        "alphaTest",
        "roughness",
        "metalness",
        "aoMapIntensity",
        "emissiveIntensity",
        "depthWrite",
      ]
    ) if (old[key] !== undefined) m[key] = old[key];
    m.color.copy(old.color);
    m.emissive.copy(old.emissive);
    m.normalScale.copy(old.normalScale);
    m.name = old.name;
    m.userData = { ...old.userData };
    const r = old.userData.eidoverse_recolor;
    if (r) {
      if (!initialized) {
        palette.primary.value.fromArray(r.default_primary_linear);
        palette.accent.value.fromArray(r.default_accent_linear);
        initialized = true;
      }
      if (opts.textures !== false) {
        const fixed = await imageTexture(new URL(r.fixed, modelURL), true),
          mask = await imageTexture(new URL(r.mask, modelURL), false),
          weights = texture(mask);
        m.colorNode = texture(fixed).rgb.add(palette.primary.mul(weights.r))
          .add(palette.accent.mul(weights.g));
        if (r.filament_channel === "b") {
          m.colorNode = m.colorNode.add(palette.filament.mul(weights.b));
        }
        m.userData.fixedMap = fixed;
        m.userData.maskMap = mask;
      }
    }
    if (m.normalMap && opts.textures !== false) {
      // Object update also handles a child reattached under a reflected parent.
      const parity = uniform(1).onObjectUpdate(({ object }) =>
        object.matrixWorld.determinant() < 0 ? -1 : 1
      );
      m.normalNode = normalMap(
        texture(m.normalMap),
        vec2(m.normalScale.x, parity.mul(m.normalScale.y)),
      );
    }
    materialMap.set(old, m);
  }
  scene.traverse((o) => {
    if (o.isMesh) {
      o.material = Array.isArray(o.material)
        ? o.material.map((m) => materialMap.get(m))
        : materialMap.get(o.material);
      o.castShadow = o.receiveShadow = true;
      o.userData._loadedAsset = true;
      o.geometry.userData._loadedAsset = true;
      o.userData.eidoverseRobotics = true;
    }
  });
  function setColor(primary, accent) {
    if (primary !== undefined) palette.primary.value.set(primary);
    if (accent !== undefined) palette.accent.value.set(accent);
  }
  setColor(opts.color ?? opts.primary, opts.accent);
  return { palette, setColor, materials: [...materialMap.values()] };
}
