// Port of blender/eidoblend/terrain/__init__.py at f90c6fc.
//
// eidoverse/terrain: the terrain generator of the three.js edition (PORT_PLAN.md; the Blender edition's design is
// blender/tests/terrain/DESIGN.md on the blender branch).
//
//     import { makeTerrain, Terrain, recipes } from './terrain/index.js';
//     const t = await makeTerrain({ recipe: 'real_place', params: { dem: 'lauterbrunnen' }, focus: [480, -1640], seed: 1 });
//     const { mesh, heightAt, masks } = t;        // or t.mesh, t.heightAt(x, z), t.mask('slope').at(x, z)
//     makeTerrain.recipes()                       // every recipe's name and title
//     await makeTerrain.describe('real_place')    // its stages, knobs (units, defaults, ranges) and references
//     const t2 = await Terrain.load('<dir>/name') // a saved terrain: this edition's or the Blender edition's
//
// In a scene, eidoverse/terrain.js (an injected helper) installs globalThis.makeTerrain, which imports this module
// on first use.
//
// Where this differs from __init__.py, and why: a JavaScript module namespace is not callable, so `recipes` is the
// registry (recipes/index.js: listing(), get(name), resolve(x), getOp(name)) and makeTerrain.recipes() lists the
// recipes, where Blender's `recipes` does both. The surface tools for built geometry (layer_surface and the others
// Blender's package also exports) are this edition's own eidoverse/surface_layers.js, unchanged.

import * as recipes from './recipes/index.js';

export { makeTerrain, generate, Terrain, Mask, MaskSet, PlantSpots, describe, placeCamera, flattenFields, clayMaterial,
    API_VERSION, ARGS } from './api.js';
export { NpGenerator, defaultRng } from './core/np_random.js';
export { recipes };
