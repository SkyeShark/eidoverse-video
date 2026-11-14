// Port of blender/eidoblend/terrain/core/recipe.py at f90c6fc.
//
// Stages and recipes (design section 2.3): a recipe is data, an ordered list of stages plus a few named knobs.
//
//     import { Stage, Recipe, Knob } from './core/recipe.js';
//
//     function spacingToD(p) {                         // a knob's apply: writes DERIVED stage parameters
//         const f = p.stage('fluvial');
//         f.D = f.K * (p.valley_spacing_m / 6.5) ** 2;
//     }
//
//     export const RECIPES = [new Recipe(
//         'fluvial_range', 'A mountain range carved by rivers', ['san_gabriel'],
//         { size: 12000.0, resolution: 1024, context: 4, hero_cell: 0.5, palette: 'alpine' },
//         { relief_m: new Knob(2000.0, 'm', [200.0, 6000.0], 'p99.5 height above base on the coarsest level'),
//           valley_spacing_m: new Knob(400.0, 'm', [60.0, 3000.0], "the smallest valleys' spacing", spacingToD) },
//         [new Stage('uplift', { shape: { kind: 'ridge' } }, 'all'),
//          new Stage('fluvial', { K: 1.5e-5, relief_m: '$relief_m' }, 'all'),
//          new Stage('breakup', { ... }, 'hero', 'smoothstep(30, 45, slope)')])];
//
//     const [values, stages] = recipe.resolve({ relief_m: 2800 });   // knob values checked against unit and range;
//                                                                    // '$knob' strings replaced; each knob's apply
//                                                                    // run in order
//     const d = recipe.toDict();                                     // JSON: the same as Python's to_dict()
//     const r2 = Recipe.fromDict(d, recipe);                         // knob apply functions come from the base
//     console.log(recipe.describe());
//
// new Stage(op, params, levels = 'all', where = null, name = null)
//     levels  'all' | 'first' | 'last' | 'context' | 'main' | 'hero' | 'cell>=30' | 'cell<=2' | 'resolves:<metres>'
//             | a level index | a list of these (core/levels.js selectLevels)
//     where   a mask expression limiting the stage (core/expr.js): combined with * + - min max smoothstep(a, b, m)
//     name    optional, to tell two stages of one op apart (params.stage('talus_hero'))
//
// new Knob(default, unit, range, doc, apply)
//     unit    'm', 'yr', 'kyr', 'Myr', 'deg', 'm/yr', 'm2/yr', '' (a number without unit), 'choice', 'bool', 'list'
//     range   [lo, hi] for numbers, the allowed values for a 'choice', null for no check
//
// An op registry lets solver modules register the functions behind op names without a shared list
// (registerOp / getOp / opNames); the level runner decides how it calls them.
//
// Recipes are data: toDict() is the same JSON as Python's to_dict() for the same recipe, and describe() the same
// text. Where this differs from recipe.py, and why:
//   - JavaScript has one number type, so a float with an integral value (Python's 2000.0) prints as 2000 in
//     describe() and in Stage and Knob text, where Python prints 2000.0; as JSON the two are the same number.
//   - Params (what a knob's apply receives) holds the knob values as its own properties, p.relief_m or
//     p['relief_m'], with stage() and stages() on its prototype (Python's Params is a dict).
//   - Errors are ValueError, KeyError and TypeError (core/levels.js) carrying Python's messages.

import * as E from './expr.js';
import { KeyError, ValueError, closeMatches, parseLevelsSpec, pyReprValue, pyStr, pyFormat, selectLevels } from './levels.js';

export const UNITS = ['m', 'yr', 'kyr', 'Myr', 'deg', 'm/yr', 'm2/yr', '', 'choice', 'bool', 'list', 'name'];

/** "; did you mean a, b?" or "; valid: ..." (recipe.py _nearest). */
export function nearestText(name, names) {
    const all = [...names];
    const near = closeMatches(name, all, 3, 0.5);
    return near.length ? `; did you mean ${near.join(', ')}?` : `; valid: ${[...all].sort().join(', ') || '(none)'}`;
}

const isPlainObject = (v) => v !== null && typeof v === 'object' && (Object.getPrototypeOf(v) === Object.prototype ||
    Object.getPrototypeOf(v) === null);

/** v as plain JSON types (typed arrays become lists); throws TypeError naming where it failed (recipe.py
 * _jsonable). */
export function jsonable(v, where = 'value') {
    if (Array.isArray(v)) return v.map((x, i) => jsonable(x, `${where}[${i}]`));
    if (ArrayBuffer.isView(v) && !(v instanceof DataView)) return Array.from(v, (x) => (typeof x === 'bigint' ? Number(x) : x));
    if (isPlainObject(v)) {
        const out = {};
        for (const [k, x] of Object.entries(v)) out[String(k)] = jsonable(x, `${where}.${k}`);
        return out;
    }
    if (v === null || typeof v === 'boolean' || typeof v === 'number' || typeof v === 'string') return v;
    const kind = v === undefined ? 'undefined' : typeof v === 'function' ? 'function' : v?.constructor?.name ?? typeof v;
    throw new TypeError(`${where}: ${kind} is not JSON data (recipes are data: use numbers, strings, lists, dicts, or a ` +
        'file path for an array)');
}

const deepCopy = (v) => (v === undefined ? v : structuredClone(v));

// Python's json.dumps(v) with its default separators (', ' and ': ') and ensure_ascii
function jsonText(s) {
    let out = '"';
    for (let i = 0; i < s.length; i++) {
        const c = s.charCodeAt(i);
        const ch = s[i];
        if (ch === '"') out += '\\"';
        else if (ch === '\\') out += '\\\\';
        else if (ch === '\n') out += '\\n';
        else if (ch === '\r') out += '\\r';
        else if (ch === '\t') out += '\\t';
        else if (ch === '\b') out += '\\b';
        else if (ch === '\f') out += '\\f';
        else if (c < 0x20 || c > 0x7e) out += '\\u' + c.toString(16).padStart(4, '0');
        else out += ch;
    }
    return out + '"';
}

/** Python's json.dumps(v) (default separators, ensure_ascii): the text describe() prints. */
export function pyJsonDumps(v) {
    if (v === null || v === undefined) return 'null';
    if (v === true) return 'true';
    if (v === false) return 'false';
    if (typeof v === 'number') {
        if (Number.isNaN(v)) return 'NaN';
        if (!Number.isFinite(v)) return v > 0 ? 'Infinity' : '-Infinity';
        return pyStr(v);
    }
    if (typeof v === 'string') return jsonText(v);
    if (Array.isArray(v)) return '[' + v.map(pyJsonDumps).join(', ') + ']';
    return '{' + Object.entries(v).map(([k, x]) => `${jsonText(String(k))}: ${pyJsonDumps(x)}`).join(', ') + '}';
}

// Python's bool() of a JSON-like value
const pyBool = (v) => !(v === null || v === undefined || v === false || v === 0 || v === '' ||
    (Array.isArray(v) && v.length === 0) || (isPlainObject(v) && Object.keys(v).length === 0));


// ----------------------------------------------------------------------------------------------------- Stage ---

const STAGE_KEYS = ['op', 'params', 'levels', 'where', 'name'];

/** One step of a recipe: an op with parameters (metres, years, degrees), the levels it runs on, an optional
 * region. */
export class Stage {
    constructor(op, params = null, levels = 'all', where = null, name = null) {
        if (typeof op !== 'string' || !op) throw new ValueError(`a stage op is a name, got ${pyReprValue(op)}`);
        this.op = op;
        this.params = { ...(params ?? {}) };
        this.levels = levels;
        parseLevelsSpec(levels);                          // fail at construction, not mid-run
        this.where = where;
        this.whereExpr = where !== null && where !== undefined ? E.parse(where) : null;
        this.name = name;
    }

    get label() { return this.name || this.op; }

    /** The indices of the levels of `plan` this stage runs on. */
    select(plan, warn = null) { return selectLevels(this.levels, plan, warn); }

    toDict() {
        const d = { op: this.op, params: jsonable(this.params, `stage ${this.label}.params`), levels: jsonable(this.levels),
            where: this.where ?? null };
        if (this.name) d.name = this.name;
        return d;
    }

    static fromDict(d) {
        if (d instanceof Stage) return d;
        const extra = Object.keys(d).filter((k) => !STAGE_KEYS.includes(k)).sort();
        if (extra.length) throw new KeyError(`stage keys ${pyStr(extra)} unknown` + nearestText(extra[0], STAGE_KEYS));
        return new Stage(d.op, d.params ?? null, d.levels ?? 'all', d.where ?? null, d.name ?? null);
    }

    copy() { return new Stage(this.op, deepCopy(this.params), deepCopy(this.levels), this.where, this.name); }

    toString() {
        return `Stage(${pyReprValue(this.op)}` + (this.name ? `, name=${pyReprValue(this.name)}` : '') +
            `, levels=${pyReprValue(this.levels)}` + (this.where ? `, where=${pyReprValue(this.where)}` : '') +
            `, params=${pyStr(this.params)})`;
    }
}
Stage.prototype.to_dict = Stage.prototype.toDict;
Stage.from_dict = Stage.fromDict;


// ------------------------------------------------------------------------------------------------------ Knob ---

/** A named recipe input in its own unit; apply(params) writes the stage parameters it derives. */
export class Knob {
    constructor(defaultValue, unit = '', range = null, doc = '', apply = null) {
        if (!UNITS.includes(unit)) throw new ValueError(`knob unit ${pyReprValue(unit)} is not one of (${UNITS.map(pyReprValue).join(', ')})`);
        this.default = defaultValue;
        this.unit = unit;
        this.range = range;
        this.doc = doc;
        this.apply = apply;
    }

    /** The value, checked against the unit and range; throws ValueError naming the knob. */
    check(name, value) {
        if (this.unit === 'choice') {
            if (this.range !== null && this.range !== undefined && !this.range.some((r) => r === value)) {
                throw new ValueError(`knob ${name}: ${pyReprValue(value)} is not one of ${pyStr([...this.range])}`);
            }
            return value;
        }
        if (this.unit === 'bool') return pyBool(value);
        if (this.unit === 'list' || this.unit === 'name') return value;
        if (typeof value !== 'number') {
            throw new ValueError(`knob ${name}: expected a number in ${this.unit || '(no unit)'}, got ${pyReprValue(value)}`);
        }
        const v = value;
        if (!Number.isFinite(v)) throw new ValueError(`knob ${name}: ${pyReprValue(value)} is not finite`);
        if (this.range !== null && this.range !== undefined) {
            const [lo, hi] = this.range;
            if ((lo !== null && lo !== undefined && v < lo) || (hi !== null && hi !== undefined && v > hi)) {
                throw new ValueError(`knob ${name} = ${pyFormat(v, 'g')} ${this.unit} is outside its range ` +
                    `[${pyStr(lo)}, ${pyStr(hi)}] ${this.unit}`);
            }
        }
        return v;
    }

    toDict() {
        return { default: jsonable(this.default), unit: this.unit, range: jsonable(this.range ?? null), doc: this.doc,
            derives: this.apply !== null && this.apply !== undefined };
    }
}
Knob.prototype.to_dict = Knob.prototype.toDict;


// ---------------------------------------------------------------------------------------------------- Params ---

/** What a knob's apply() receives: the resolved knob values as its own properties, and the stages' parameter
 * objects to write derived values into (p.stage(opOrName) for the first match, p.stages(opOrName) for all). */
export class Params {
    constructor(values, stages, recipe = null) {
        Object.assign(this, values);
        Object.defineProperty(this, '_stages', { value: stages, enumerable: false });
        Object.defineProperty(this, 'recipe', { value: recipe, enumerable: false });
    }

    stages(sel) { return this._stages.filter((s) => s.name === sel || s.op === sel).map((s) => s.params); }

    stage(sel) {
        const hit = this.stages(sel);
        if (!hit.length) {
            throw new KeyError(`no stage named or of op ${pyReprValue(sel)}` + nearestText(sel, new Set(this._stages.map((s) => s.label))));
        }
        return hit[0];
    }
}

function substitute(v, values, where) {
    if (typeof v === 'string' && v.startsWith('$')) {
        const k = v.slice(1);
        if (!(k in values)) throw new KeyError(`${where}: ${pyReprValue(v)} names no knob` + nearestText(k, Object.keys(values)));
        return values[k];
    }
    if (Array.isArray(v)) return v.map((x, i) => substitute(x, values, `${where}[${i}]`));
    if (isPlainObject(v)) {
        const out = {};
        for (const [kk, x] of Object.entries(v)) out[kk] = substitute(x, values, `${where}.${kk}`);
        return out;
    }
    return v;
}


// ---------------------------------------------------------------------------------------------------- Recipe ---

/** new Recipe(name, title, references, defaults, knobs, stages, doc): see the module doc. */
export class Recipe {
    constructor(name, title, references = [], defaults = null, knobs = null, stages = [], doc = '') {
        this.name = name;
        this.title = title;
        this.references = [...references];
        this.defaults = { ...(defaults ?? {}) };
        this.knobs = { ...(knobs ?? {}) };
        for (const [k, v] of Object.entries(this.knobs)) {
            if (!(v instanceof Knob)) throw new TypeError(`recipe ${name}: knob ${k} is a ${v?.constructor?.name ?? typeof v}, not a Knob`);
        }
        this.stages = stages.map((s) => (s instanceof Stage ? s : Stage.fromDict(s)));
        this.doc = doc;
    }

    /** Every knob's value (defaults overridden by `params`), checked. An unknown knob names the nearest. */
    knobValues(params = null) {
        params = { ...(params ?? {}) };
        for (const k of Object.keys(params)) {
            if (!(k in this.knobs)) throw new KeyError(`recipe ${pyReprValue(this.name)} has no knob ${pyReprValue(k)}` + nearestText(k, Object.keys(this.knobs)));
        }
        const out = {};
        for (const [k, kn] of Object.entries(this.knobs)) out[k] = kn.check(k, k in params ? params[k] : kn.default);
        return out;
    }

    /** [knob values, stages]: copies of the stages with '$knob' references replaced by the values, then each knob's
     * apply() run in declaration order to write its derived parameters. */
    resolve(params = null) {
        const values = this.knobValues(params);
        const stages = this.stages.map((s) => s.copy());
        for (const s of stages) s.params = substitute(s.params, values, `stage ${s.label}`);
        const p = new Params(values, stages, this);
        for (const kn of Object.values(this.knobs)) if (kn.apply) kn.apply(p);
        return [values, stages];
    }

    toDict() {
        const d = { name: this.name, title: this.title, references: [...this.references],
            defaults: jsonable(this.defaults, `recipe ${this.name}.defaults`),
            knobs: Object.fromEntries(Object.entries(this.knobs).map(([k, v]) => [k, v.toDict()])),
            stages: this.stages.map((s) => s.toDict()) };
        if (this.doc) d.doc = this.doc;
        JSON.stringify(d);                                // it is JSON, or this throws
        return d;
    }

    /** A recipe from its dict. Knob apply functions are code, which a dict cannot carry: they come from `base` (the
     * registered recipe of the same name, passed by the registry) for the knobs it shares. */
    static fromDict(d, base = null) {
        if (d instanceof Recipe) return d;
        const knobs = {};
        for (const [k, kd] of Object.entries(d.knobs ?? {})) {
            const src = base ? base.knobs[k] : undefined;
            knobs[k] = new Knob(kd.default ?? null, kd.unit ?? '', kd.range ?? null, kd.doc ?? '', src ? src.apply : null);
        }
        return new Recipe('name' in d ? d.name : (base ? base.name : 'custom'), 'title' in d ? d.title : (base ? base.title : ''),
            d.references ?? [], d.defaults ?? {}, knobs, (d.stages ?? []).map((s) => Stage.fromDict(s)), d.doc ?? '');
    }

    static fromStages(stages, name = 'custom', title = 'a list of stages', defaults = null) {
        return new Recipe(name, title, [], defaults, {}, stages.map((s) => (s instanceof Stage ? s : Stage.fromDict(s))));
    }

    describe() {
        const lines = [`${this.name}: ${this.title}`];
        if (this.doc) lines.push('  ' + this.doc);
        if (this.references.length) lines.push('  judged against: ' + this.references.join(', '));
        const dk = Object.entries(this.defaults);
        if (dk.length) lines.push('  defaults: ' + dk.map(([k, v]) => `${k}=${pyStr(v)}`).join(', '));
        const kk = Object.entries(this.knobs);
        if (kk.length) {
            lines.push('  knobs:');
            for (const [k, kn] of kk) {
                const rng = kn.range !== null && kn.range !== undefined ? ` in ${pyStr([...kn.range])}` : '';
                lines.push(`    ${k} = ${pyReprValue(kn.default)} ${kn.unit}${rng}${kn.apply ? ' (derives stage parameters)' : ''}` +
                    (kn.doc ? `: ${kn.doc}` : ''));
            }
        }
        lines.push('  stages:');
        this.stages.forEach((s, i) => {
            lines.push(`    ${i}. ${s.label} on ${pyStr(s.levels)}` + (s.where ? ` where ${s.where}` : '') +
                (Object.keys(s.params).length ? `: ${pyJsonDumps(jsonable(s.params))}` : ''));
        });
        return lines.join('\n');
    }

    toString() {
        return `Recipe(${pyReprValue(this.name)}, ${this.stages.length} stages, knobs ${pyStr(Object.keys(this.knobs))})`;
    }
}
Recipe.prototype.to_dict = Recipe.prototype.toDict;
Recipe.prototype.knob_values = Recipe.prototype.knobValues;
Recipe.from_dict = Recipe.fromDict;
Recipe.from_stages = Recipe.fromStages;


// ----------------------------------------------------------------------------------------------- op registry ---

export const OPS = {};

/** Register the function behind a stage op (registerOp(name, fn), or registerOp(name) as a decorator-like
 * wrapper). The level runner (run.js) owns the calling convention; this only maps names to functions without a
 * shared list. */
export function registerOp(name, fn = null) {
    const deco = (f) => {
        OPS[name] = f;
        return f;
    };
    return fn !== null ? deco(fn) : deco;
}

export function getOp(name) {
    if (Object.prototype.hasOwnProperty.call(OPS, name)) return OPS[name];
    throw new KeyError(`no op ${pyReprValue(name)} is registered` + nearestText(name, Object.keys(OPS)) +
        ' (ops register when their solver module is imported)');
}

export const opNames = () => Object.keys(OPS).sort();
export { registerOp as register_op, getOp as get_op, opNames as op_names };
