// MIT. Shared binary/image cache for native Deno and browser clients.
import * as T from "three/webgpu";
const binaries = new Map(), images = new Map(), jsonCache = new Map();
export async function bytes(url) {
  url = String(url);
  if (!binaries.has(url)) {
    binaries.set(
      url,
      (async () => {
        if (globalThis.Deno && url.startsWith("file:")) {
          return await Deno.readFile(new URL(url));
        }
        const r = await fetch(url);
        if (!r.ok) throw Error(`Robotics asset ${r.status}: ${url}`);
        return new Uint8Array(await r.arrayBuffer());
      })().catch((e) => {
        binaries.delete(url);
        throw e;
      }),
    );
  }
  return binaries.get(url);
}
export async function json(url) {
  url = String(url);
  if (!jsonCache.has(url)) {
    jsonCache.set(
      url,
      bytes(url).then((b) => JSON.parse(new TextDecoder().decode(b))),
    );
  }
  return jsonCache.get(url);
}
export async function imageTexture(url, srgb = false) {
  const key = String(url) + "|" + srgb;
  if (!images.has(key)) {
    images.set(
      key,
      (async () => {
        const b = await bytes(url);
        let t;
        if (globalThis.loadImageTexture) {
          t = await globalThis.loadImageTexture(b, { srgb, flipY: false });
        } else if (typeof createImageBitmap === "function") {
          const bitmap = await createImageBitmap(
            new Blob([b], { type: "image/png" }),
            { colorSpaceConversion: "none", premultiplyAlpha: "none" },
          );
          t = new T.Texture(bitmap);
        } else {throw Error(
            "PNG decoder unavailable: use Eidoverse render_scene.mjs or a browser, or pass textures:false for geometry-only inspection.",
          );}
        t.flipY = false;
        t.colorSpace = srgb ? T.SRGBColorSpace : T.NoColorSpace;
        t.wrapS = t.wrapT = T.ClampToEdgeWrapping;
        t.minFilter = T.LinearMipmapLinearFilter;
        t.magFilter = T.LinearFilter;
        t.generateMipmaps = true;
        t.needsUpdate = true;
        return t;
      })().catch((e) => {
        images.delete(key);
        throw e;
      }),
    );
  }
  return images.get(key);
}
export function texturePlugin(base, enabled = true) {
  return (parser) => ({
    name: "EIDOVERSE_shared_images",
    async loadTexture(index) {
      const def = parser.json.textures[index],
        im = parser.json.images[def.source];
      if (!im?.uri) return null;
      const anisotropy = parser.json.samplers?.[def.sampler]?.extras
        ?.eidoverse_anisotropy ?? 1;
      if (!Number.isInteger(anisotropy) || anisotropy < 1 || anisotropy > 16) {
        throw Error("Atlas anisotropy must be an integer from 1 to 16");
      }
      const sampled = (t) => {
        if (t.anisotropy < anisotropy) {
          t.anisotropy = anisotropy;
          t.needsUpdate = true;
        }
        return t;
      };
      if (!enabled) {
        const t = new T.DataTexture(new Uint8Array([220, 220, 220, 255]), 1, 1);
        t.needsUpdate = true;
        return t;
      }
      const color = parser.json.materials.some((m) =>
        m.pbrMetallicRoughness?.baseColorTexture?.index === index ||
        m.emissiveTexture?.index === index
      );
      return sampled(await imageTexture(new URL(im.uri, base), color));
    },
  });
}
export function cacheStats() {
  return { binaryFiles: binaries.size, decodedTextures: images.size };
}
