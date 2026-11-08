// Stand-ins for the three/tsl names terrain_mesh.js imports, so its CPU-side functions (terrainVertexSide,
// terrainGeometryCost, buildTerrainGeometry) load under deno; fieldHeightBilinear (a shader node) is not called.
const node = () => ({});
export const texture = node, textureLoad = node, textureSize = node, vec2 = node, ivec2 = node, int = node,
    floor = node, mix = node;
