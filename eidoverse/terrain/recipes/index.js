// Port of blender/eidoblend/terrain/recipes/__init__.py at f90c6fc.
//
// The recipe registry (design section 2.3). Every module in this folder that exports RECIPES (an array or an object
// of core/recipe.js Recipes) is collected when this module is imported (the folder read with Deno.readDir, as
// Blender's pkgutil.iter_modules reads its package), so no package edits a shared list; one module per family.
//
//     import * as recipes from './recipes/index.js';
//     recipes.listing()                   // { name: title }, every recipe
//     recipes.get('alpine_valley')        // the Recipe; an unknown name raises naming the nearest
//     recipes.resolve(x)                  // a name, a Recipe, a recipe dict or a list of stages -> a Recipe
//     await recipes.getOp('impact_crater')   // the function behind a stage op
//     recipes.failed()                    // { module: error } for recipe modules that did not import
//
// Ops. A stage's op name maps to a function, found in this order: core/recipe.js's registerOp table, then the OPS
// object of every recipe module here, then the OPS object of every module in terrain/solvers/ (imported on the
// first miss). The Blender solvers' convention is op(fields, level, params, seed), writing the level's Fields in
// place; run.js (the level runner) owns how it calls them.
//
// Recipe hooks a module may set on a Recipe object (properties, not data, so they come from the registered recipe
// when a dict of the same name is passed back):
//     defaultsFor(values, ctx) -> object   defaults that depend on the knob values (real_place: the DEM's extent)
//     prepare(values, plan, ctx)           called once before the levels run (load data, build a plan shared by levels)
// (Blender's defaults_for and prepare; the snake_case names are kept as aliases on the recipes that set them.) Both
// may be async here: the port's file reading and GPU work are.
//
// Where this differs from recipes/__init__.py, and why:
//   - JavaScript imports modules asynchronously, so the recipe modules are imported when this module is (a
//     top-level await), and listing, get and resolve stay synchronous; the solvers' ops are imported on the first
//     miss, so getOp, hasOp and opNames are async.
//   - The module is not callable (a JavaScript module namespace cannot be): listing() is Blender's recipes(), and
//     makeTerrain.recipes() (api.js) calls it.

import * as Rc from '../core/recipe.js';
import { KeyError, closeMatches } from '../core/levels.js';

const HERE = new URL('./', import.meta.url);
const SOLVERS = new URL('../solvers/', import.meta.url);
const HOOKS = ['defaultsFor', 'prepare'];
const HOOK_ALIASES = { defaultsFor: 'defaults_for', prepare: 'prepare' };

let RECIPES = null;
const FAILED = {};
const MODULES = {};                                     // recipe module name -> its namespace
let OPS = null;

function moduleNames(dir) {
    const out = [];
    try {
        for (const e of Deno.readDirSync(dir)) {
            if (!e.isFile || !e.name.endsWith('.js') || e.name.startsWith('_') || e.name === 'index.js') continue;
            out.push(e.name.slice(0, -3));
        }
    } catch (_e) { /* no folder: no modules */ }
    return out.sort();
}

async function load() {
    if (RECIPES !== null) return RECIPES;
    const found = {}, where = {};
    for (const name of moduleNames(HERE)) {
        let mod;
        try {
            mod = await import(new URL(`${name}.js`, HERE).href);
        } catch (e) {                                   // one family's broken module must not hide every recipe
            FAILED[name] = `${e.name}: ${e.message}`;
            console.log(`[terrain.recipes] recipe module '${name}' did not import: ${FAILED[name]}`);
            continue;
        }
        MODULES[name] = mod;
        const rs = mod.RECIPES;
        if (rs === undefined || rs === null) continue;
        for (const r of Array.isArray(rs) ? rs : Object.values(rs)) {
            if (r.name in found) throw new Error(`recipe '${r.name}' is defined in both ${where[r.name]} and ${name}`);
            found[r.name] = r;
            where[r.name] = name;
        }
    }
    RECIPES = Object.fromEntries(Object.keys(found).sort().map((k) => [k, found[k]]));
    return RECIPES;
}

await load();

/** Every recipe's name, sorted. */
export function names() { return Object.keys(RECIPES); }

/** { name: title } of every recipe (Blender's recipes()). */
export function listing() { return Object.fromEntries(Object.entries(RECIPES).map(([k, r]) => [k, r.title])); }

/** { module: error } of the recipe modules that did not import. */
export function failed() { return { ...FAILED }; }

function unknown(name, options, what) {
    const opts = [...options];
    const near = closeMatches(String(name), opts, 3, 0.4);
    let msg = `no ${what} '${name}'`;
    msg += near.length ? `; nearest: ${near.join(', ')}` : `; valid: ${[...opts].sort().join(', ') || '(none)'}`;
    if (Object.keys(FAILED).length && what === 'recipe') {
        msg += ` (recipe modules that did not import: ${Object.entries(FAILED).map(([k, v]) => `${k} (${v})`).join(', ')})`;
    }
    return msg;
}

/** The registered Recipe called `name`; an unknown name throws a KeyError naming the nearest. */
export function get(name) {
    if (!Object.prototype.hasOwnProperty.call(RECIPES, name)) throw new KeyError(unknown(name, Object.keys(RECIPES), 'recipe'));
    return RECIPES[name];
}

/** A Recipe from a registered name, a Recipe, a recipe dict (toDict's form; knob apply functions and hooks come
 * from the registered recipe of the same name) or a list of stages (Stage objects or stage dicts). */
export function resolve(recipe) {
    if (recipe instanceof Rc.Recipe) return recipe;
    if (typeof recipe === 'string') return get(recipe);
    if (Array.isArray(recipe)) return Rc.Recipe.fromStages(recipe);
    if (recipe && typeof recipe === 'object') {
        const base = RECIPES[recipe.name] ?? null;
        const out = Rc.Recipe.fromDict(recipe, base);
        if (base) {
            for (const h of HOOKS) {
                if (base[h]) {
                    out[h] = base[h];
                    out[HOOK_ALIASES[h]] = base[h];
                }
            }
        }
        return out;
    }
    throw new TypeError(`recipe must be a name, a Recipe, a recipe dict or a list of stages, got ${recipe === null ? 'null' : typeof recipe}`);
}

async function collectOps() {
    if (OPS !== null) return OPS;
    const ops = {};
    const take = (mod, label) => {
        for (const [k, f] of Object.entries(mod.OPS ?? {})) {
            if (k in ops && ops[k][0] !== f) throw new Error(`op '${k}' is defined by both ${ops[k][1]} and ${label}`);
            if (!(k in ops)) ops[k] = [f, label];
        }
    };
    for (const name of Object.keys(MODULES).sort()) take(MODULES[name], `recipes.${name}`);
    for (const name of moduleNames(SOLVERS)) {
        try {
            take(await import(new URL(`${name}.js`, SOLVERS).href), `solvers.${name}`);
        } catch (e) {
            FAILED[`solvers.${name}`] = `${e.name}: ${e.message}`;
        }
    }
    OPS = ops;
    return ops;
}

/** The function behind stage op `name` (see the module doc for where it is looked up); a KeyError naming the
 * nearest when there is none. */
export async function getOp(name) {
    if (Object.prototype.hasOwnProperty.call(Rc.OPS, name)) return Rc.OPS[name];
    const ops = await collectOps();
    if (Object.prototype.hasOwnProperty.call(ops, name)) return ops[name][0];
    throw new KeyError(unknown(name, new Set([...Object.keys(Rc.OPS), ...Object.keys(ops)]), 'op'));
}

export async function hasOp(name) {
    try {
        await getOp(name);
        return true;
    } catch (e) {
        if (e instanceof KeyError) return false;
        throw e;
    }
}

export async function opNames() {
    return [...new Set([...Object.keys(Rc.OPS), ...Object.keys(await collectOps())])].sort();
}

/** Forget what was collected (a new recipe module dropped in during a session); the recipes are imported again. */
export async function reload() {
    RECIPES = null;
    OPS = null;
    for (const k of Object.keys(FAILED)) delete FAILED[k];
    for (const k of Object.keys(MODULES)) delete MODULES[k];
    await load();
}

export { getOp as get_op, hasOp as has_op, opNames as op_names };
