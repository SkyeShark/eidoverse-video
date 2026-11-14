// gltf_cache.js (A2, wave 6): ONE GLB'S TEXTURES SHARED BY EVERY CREATURE MADE FROM IT. A crowd (production scenes hold 3-6
// people of one outfit glb, 3 robot octopuses) parsed each glb's PNGs again per creature: a human's bake set is 0.5-1 GB of RAM
// decoded and as much VRAM, so 4 humans and an octopus passed a 12 GB memcap (amc7_broadcast, kronos_kult_0715: 11-09). A
// loader plugin answers the parser's texture requests from a per-key cache: the first creature of a key decodes and uploads,
// the rest reuse those texture objects (their samplers and colour spaces are the glb's, the same for every creature of it).
// The parser's own loadTexture is the default path (GLTFParser dispatches plugins in getDependency), so the plugin calling it
// does not recurse; a creature's builders set the same flags on a shared texture as on its own.
//   const gltf = await parseShared(bytes, 'work/bestiary/octopus/octopus.glb', { vrm: false });
const caches = new Map();
export async function parseShared(bytes, key = null, { vrm = false } = {}) {
    const loader = new globalThis.GLTFLoader();
    if (vrm && globalThis.VRMLoaderPlugin) loader.register((p) => new globalThis.VRMLoaderPlugin(p));
    if (key) {
        if (!caches.has(key)) caches.set(key, new Map());
        const cache = caches.get(key);
        loader.register((parser) => ({
            name: 'BESTIARY_SHARED_TEXTURES',
            loadTexture(i) {
                if (!cache.has(i)) cache.set(i, parser.loadTexture(i));
                return cache.get(i);
            },
        }));
    }
    const buf = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength);
    return await new Promise((res, rej) => loader.parse(buf, '', res, rej));
}
// the glb files' bytes, read once per path (a crowd of one glb reads it once)
const files = new Map();
export function fileBytes(path) {
    if (!files.has(path)) files.set(path, Deno.readFileSync(path));
    return files.get(path);
}
