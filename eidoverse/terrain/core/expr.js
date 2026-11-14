// Port of blender/eidoblend/terrain/core/expr.py at f90c6fc.
//
// The mask expression language of stage `where` and of the surfacing layers' weights (design sections 2.3, 7).
//
//     const e = parse('smoothstep(32, 45, slope) + 0.5*wear - 2*deposit');
//     e.names()                         // Set { 'slope', 'wear', 'deposit' }
//     const w = await e.eval({ slope: s, wear: w, deposit: d });   // GPU fields (core/gpu.js) and numbers; or
//                                                                 // eval(name => field), which may be async
//     String(e)                         // the canonical text; e.tree is the AST for other back ends
//
// Grammar: numbers, names (masks or fields), + - * /, unary minus, parentheses, and the functions
// min(a, b, ...), max(a, b, ...), smoothstep(edge0, edge1, x), clamp(x, lo, hi), abs(x). smoothstep is GLSL's
// (t = clamp((x - e0) / (e1 - e0), 0, 1); t^2 (3 - 2 t)), and with e0 > e1 it falls instead of rising.
// Nothing else is evaluated: there is no eval of text. A mistake names the token and its position.
//
// AST nodes (arrays): ['num', value] ['name', name] ['neg', x] ['bin', op, a, b] ['call', function, [args]].
//
// Evaluation on the GPU (PORT_PLAN.md 3.2): an expression over fields compiles, once per text and per set of
// field and number names, into a WGSL kernel (one sampler per field name, one uniform per number name, the
// expression's own numbers as exact float32 constants) and runs as one dispatch over the fields' cells; the result
// is a new r32f field the caller owns. An expression without fields (numbers only) is evaluated in JavaScript
// doubles, as Python evaluates it, and returns a number.
//
// Where this differs from expr.py, and why:
//   - numpy evaluates over float64 copies of the fields; the kernel is float32 (WGSL has no float64): a result is
//     within float32 rounding of numpy's per operation. Subtrees of the expression's own numbers are folded in
//     doubles first, so '1 / 3 * wear' multiplies wear by float32(1 / 3) once.
//   - Where numpy's arithmetic leaves the real numbers (a division by zero, smoothstep with equal edges over a
//     field, a NaN input) the GPU's result is undefined: WGSL lets a shader assume finite values.
//   - eval is async: a field is on the GPU and the environment's lookups may be.
//   - Errors are ExprError (a ValueError) and KeyError (core/levels.js) carrying Python's messages.

import { KeyError, ValueError, closeMatches, pyRepr, pyReprValue, pyStr } from './levels.js';

export const FUNCTIONS = { min: [2, null], max: [2, null], smoothstep: [3, 3], clamp: [3, 3], abs: [1, 1] };
const TOKEN = /\s*(?:(\d+\.\d*(?:[eE][+-]?\d+)?|\.\d+(?:[eE][+-]?\d+)?|\d+(?:[eE][+-]?\d+)?)|([A-Za-z_]\w*)|(.))/y;

export class ExprError extends ValueError {
    constructor(message) {
        super(message);
        this.name = 'ExprError';
    }
}

function tokens(text) {
    const out = [];
    let pos = 0;
    while (pos < text.length) {
        TOKEN.lastIndex = pos;
        const m = TOKEN.exec(text);
        if (!m || TOKEN.lastIndex === pos) break;
        const [all, num, name, ch] = m;
        const lead = all.length - (num ?? name ?? ch ?? '').length;
        const start = pos + lead;
        if (num !== undefined) {
            out.push(['num', Number(num), start]);
        } else if (name !== undefined) {
            out.push(['name', name, start]);
        } else if (ch !== undefined) {
            if (!'+-*/(),'.includes(ch)) {
                throw new ExprError(`${pyReprValue(text)}: unexpected ${pyReprValue(ch)} at ${start} (allowed: numbers, names, ` +
                    `+ - * / ( ) , and ${Object.keys(FUNCTIONS).join(', ')})`);
            }
            out.push(['op', ch, start]);
        }
        pos = TOKEN.lastIndex;
    }
    out.push(['end', null, text.length]);
    return out;
}

// a token's value as Python's repr shows it
const tokRepr = (t) => (t[0] === 'end' ? 'the end' : t[0] === 'num' ? pyRepr(t[1]) : pyReprValue(t[1]));

class Parser {
    constructor(text) {
        this.text = text;
        this.toks = tokens(text);
        this.i = 0;
    }

    peek() { return this.toks[this.i]; }

    take(kind = null, val = null) {
        const t = this.toks[this.i];
        if ((kind && t[0] !== kind) || (val !== null && t[1] !== val)) {
            const want = val !== null ? val : kind;
            throw new ExprError(`${pyReprValue(this.text)}: expected ${pyReprValue(want)} at ${t[2]}, found ${tokRepr(t)}`);
        }
        this.i++;
        return t;
    }

    isOp(chars) {
        const t = this.peek();
        return t[0] === 'op' && chars.includes(t[1]);
    }

    expr() {
        let node = this.term();
        while (this.isOp('+-')) {
            const op = this.take()[1];
            node = ['bin', op, node, this.term()];
        }
        return node;
    }

    term() {
        let node = this.unary();
        while (this.isOp('*/')) {
            const op = this.take()[1];
            node = ['bin', op, node, this.unary()];
        }
        return node;
    }

    unary() {
        if (this.isOp('-')) {
            this.take();
            return ['neg', this.unary()];
        }
        if (this.isOp('+')) {
            this.take();
            return this.unary();
        }
        return this.atom();
    }

    atom() {
        const t = this.peek();
        if (t[0] === 'num') {
            this.take();
            return ['num', t[1]];
        }
        if (t[0] === 'name') {
            this.take();
            if (this.isOp('(')) {
                if (!(t[1] in FUNCTIONS)) {
                    const near = closeMatches(t[1], Object.keys(FUNCTIONS), 2);
                    throw new ExprError(`${pyReprValue(this.text)}: unknown function ${pyReprValue(t[1])} at ${t[2]}` +
                        (near.length ? ` (did you mean ${pyStr(near)}?)` : ` (functions: ${pyStr(Object.keys(FUNCTIONS))})`));
                }
                this.take('op', '(');
                const args = [this.expr()];
                while (this.isOp(',')) {
                    this.take();
                    args.push(this.expr());
                }
                this.take('op', ')');
                const [lo, hi] = FUNCTIONS[t[1]];
                if (args.length < lo || (hi !== null && args.length > hi)) {
                    const n = lo === hi ? `${lo}` : `at least ${lo}`;
                    throw new ExprError(`${pyReprValue(this.text)}: ${t[1]}() takes ${n} arguments, got ${args.length}`);
                }
                return ['call', t[1], args];
            }
            return ['name', t[1]];
        }
        if (t[0] === 'op' && t[1] === '(') {
            this.take();
            const node = this.expr();
            this.take('op', ')');
            return node;
        }
        throw new ExprError(`${pyReprValue(this.text)}: expected a number, a name or ( at ${t[2]}, found ${tokRepr(t)}`);
    }
}


// ------------------------------------------------------------------------------------------- the CPU values ---

const smoothstep = (e0, e1, x) => {
    const t = Math.min(Math.max((x - e0) / (e1 - e0), 0.0), 1.0);
    return t * t * (3.0 - 2.0 * t);
};
// np.minimum / np.maximum / np.clip of numbers: NaN propagates
const nmin = (a, b) => (Number.isNaN(a) || Number.isNaN(b) ? NaN : Math.min(a, b));
const nmax = (a, b) => (Number.isNaN(a) || Number.isNaN(b) ? NaN : Math.max(a, b));

// the value of a tree whose leaves are numbers (and number-valued names): Python's float arithmetic
function evalNumbers(node, get) {
    switch (node[0]) {
        case 'num': return node[1];
        case 'name': return get(node[1]);
        case 'neg': return -evalNumbers(node[1], get);
        case 'bin': {
            const a = evalNumbers(node[2], get), b = evalNumbers(node[3], get);
            if (node[1] === '/' && b === 0) throw Object.assign(new Error('float division by zero'), { name: 'ZeroDivisionError' });
            return node[1] === '+' ? a + b : node[1] === '-' ? a - b : node[1] === '*' ? a * b : a / b;
        }
        default: {
            const args = node[2].map((a) => evalNumbers(a, get));
            const f = node[1];
            if (f === 'min') return args.slice(1).reduce(nmin, args[0]);
            if (f === 'max') return args.slice(1).reduce(nmax, args[0]);
            if (f === 'smoothstep') return smoothstep(...args);
            if (f === 'clamp') return nmin(nmax(args[0], args[1]), args[2]);
            return Math.abs(args[0]);
        }
    }
}


// ------------------------------------------------------------------------------------------------- the text ---

function text(node) {
    switch (node[0]) {
        case 'num': return Number.isInteger(node[1]) ? (Math.abs(node[1]) < 1e21 ? String(node[1] + 0) : BigInt(node[1]).toString())
            : pyRepr(node[1]);
        case 'name': return node[1];
        case 'neg': return '-' + wrap(node[1], 3);
        case 'bin': {
            const prec = '+-'.includes(node[1]) ? 1 : 2;
            const right = wrap(node[3], prec + ('-/'.includes(node[1]) ? 1 : 0));
            return `${wrap(node[2], prec)} ${node[1]} ${right}`;
        }
        default: return `${node[1]}(${node[2].map(text).join(', ')})`;
    }
}

function prec(node) {
    if (node[0] === 'bin') return '+-'.includes(node[1]) ? 1 : 2;
    if (node[0] === 'neg') return 3;
    return 4;
}

function wrap(node, need) {
    const t = text(node);
    return prec(node) < need ? `(${t})` : t;
}


// ---------------------------------------------------------------------------------------------- the kernel ---

const F32 = new Float32Array(1), U32 = new Uint32Array(F32.buffer);
const f32Const = (v) => {
    F32[0] = v;
    return `bitcast<f32>(0x${U32[0].toString(16).padStart(8, '0')}u)`;
};

// WGSL for a tree. fields: Map name -> sampler; scalars: Map name -> uniform. Number-only subtrees fold in doubles.
function wgsl(node, fields, scalars) {
    const constant = (n) => (n[0] === 'num' ? true : n[0] === 'name' ? false : n[0] === 'neg' ? constant(n[1]) :
        n[0] === 'bin' ? constant(n[2]) && constant(n[3]) : n[2].every(constant));
    if (constant(node)) {
        let v;
        try {
            v = evalNumbers(node, () => NaN);
        } catch (_e) {
            v = NaN;
        }
        return f32Const(v);
    }
    switch (node[0]) {
        case 'name': return fields.has(node[1]) ? `v_${fields.get(node[1])}` : `u.${scalars.get(node[1])}`;
        case 'neg': return `(-${wgsl(node[1], fields, scalars)})`;
        case 'bin': return `(${wgsl(node[2], fields, scalars)} ${node[1]} ${wgsl(node[3], fields, scalars)})`;
        default: {
            const a = node[2].map((x) => wgsl(x, fields, scalars));
            const f = node[1];
            if (f === 'min' || f === 'max') return a.slice(1).reduce((acc, x) => `${f}(${acc}, ${x})`, a[0]);
            if (f === 'smoothstep') return `eido_smoothstep(${a[0]}, ${a[1]}, ${a[2]})`;
            if (f === 'clamp') return `min(max(${a[0]}, ${a[1]}), ${a[2]})`;
            return `abs(${a[0]})`;
        }
    }
}

/** The WGSL source of the kernel that evaluates `tree` with these field names and number names (sorted), for
 * core/gpu.js. The output image is outF (r32f). */
export function kernelSource(tree, fieldNames, scalarNames, label = '') {
    const fields = new Map(fieldNames.map((n, i) => [n, `f${i}`]));
    const scalars = new Map(scalarNames.map((n, i) => [n, `s${i}`]));
    const L = [`// a mask expression: ${label.replace(/[\r\n]/g, ' ')}`];
    for (const [n, s] of fields) L.push(`//! sampler ${s}    (${n})`);
    L.push('//! image outF r32f');
    for (const [n, s] of scalars) L.push(`//! uniform float ${s}    (${n})`);
    L.push('fn eido_smoothstep(e0: f32, e1: f32, x: f32) -> f32 {',
        '  let t = min(max((x - e0) / (e1 - e0), 0.0), 1.0);',
        '  return t * t * (3.0 - 2.0 * t);',
        '}',
        'fn kmain(p: vec2<i32>) {',
        '  if (!inside(p, outF_size())) { return; }');
    for (const [, s] of fields) L.push(`  let v_${s} = ${s}_at(p).x;`);
    L.push(`  outF_store(p, vec4<f32>(${wgsl(tree, fields, scalars)}, 0.0, 0.0, 0.0));`, '}');
    return L.join('\n') + '\n';
}


// ---------------------------------------------------------------------------------------------------- Expr ---

const isField = (v) => v !== null && typeof v === 'object' && typeof v.h === 'number' && typeof v.w === 'number' &&
    v.runner !== undefined && v.buffer !== undefined;

/** A parsed mask expression: .tree (the AST), .names(), await .eval(env), String(). */
export class Expr {
    constructor(source) {
        this.source = source;
        const p = new Parser(source);
        this.tree = p.expr();
        p.take('end');
    }

    names() {
        const out = new Set();
        const walk = (n) => {
            if (n[0] === 'name') out.add(n[1]);
            else if (n[0] === 'neg') walk(n[1]);
            else if (n[0] === 'bin') {
                walk(n[2]);
                walk(n[3]);
            } else if (n[0] === 'call') n[2].forEach(walk);
        };
        walk(this.tree);
        return out;
    }

    /** Evaluate over `env`: an object name -> field (core/gpu.js, one channel; every field the same size) or number,
     * or a function(name) -> field or number (or a Promise of one). An unknown name names the nearest available
     * ones. A number when no name is a field (Python's float); else a new r32f field the caller owns. */
    async eval(env, opts = {}) {
        let get;
        if (typeof env === 'function') {
            get = env;
        } else {
            get = (name) => {
                if (Object.prototype.hasOwnProperty.call(env, name)) return env[name];
                const keys = Object.keys(env);
                const near = closeMatches(name, keys, 3);
                throw new KeyError(`${pyReprValue(this.source)}: no mask or field ${pyReprValue(name)}` +
                    (near.length ? ` (did you mean ${pyStr(near)}?)` : ` (have: ${pyStr([...keys].sort())})`));
            };
        }
        const values = new Map();
        for (const n of [...this.names()].sort()) values.set(n, await get(n));
        const fieldNames = [], scalarNames = [];
        let first = null;
        for (const [n, v] of values) {
            if (typeof v === 'number') {
                scalarNames.push(n);
            } else if (isField(v)) {
                if (v.kind !== 'f32' || v.channels !== 1) {
                    throw new TypeError(`${pyReprValue(this.source)}: ${n} is a ${v.format} field; a one-channel float field is needed`);
                }
                if (first && (v.h !== first.h || v.w !== first.w)) {
                    throw new ValueError(`${pyReprValue(this.source)}: ${n} is ${v.h} x ${v.w}, ${fieldNames[0]} is ${first.h} x ${first.w}`);
                }
                first = first ?? v;
                fieldNames.push(n);
            } else {
                throw new TypeError(`${pyReprValue(this.source)}: ${n} is neither a field nor a number`);
            }
        }
        if (!fieldNames.length) return evalNumbers(this.tree, (n) => values.get(n));
        const R = first.runner;
        const src = kernelSource(this.tree, fieldNames, scalarNames, String(this));
        const k = R.kernel(opts.kernelName ?? 'expr', { source: src });
        const out = opts.out ?? R.field(first.h, first.w, 1);
        const samplers = {}, uniforms = {};
        fieldNames.forEach((n, i) => { samplers[`f${i}`] = values.get(n); });
        scalarNames.forEach((n, i) => { uniforms[`s${i}`] = values.get(n); });
        R.run(k, samplers, { outF: out }, uniforms);
        return out;
    }

    toString() { return text(this.tree); }
}

/** Parse a mask expression (an Expr is returned as it is). */
export function parse(source) {
    if (source instanceof Expr) return source;
    if (typeof source !== 'string' || !source.trim()) {
        throw new ExprError(`a mask expression is a non-empty string, got ${pyReprValue(source ?? null)}`);
    }
    return new Expr(source);
}
