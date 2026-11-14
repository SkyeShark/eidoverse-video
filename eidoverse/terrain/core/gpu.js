// Port of blender/eidoblend/terrain/core/gpu.py at f90c6fc.
//
// The terrain family's GPU runner: WGSL compute kernels over 2D fields held in storage buffers (PORT_PLAN.md
// section 4). The counterpart of the Blender edition's core/gpu.py, grown from the plan's prototype
// (tests/design_probes/mini_runner.mjs), whose calls it keeps (Runner, field, kernel, check, run, flush, read, idle).
//
//     import * as G from './core/gpu.js';
//     const R = await G.init();                          // the scene's GPU_DEVICE, { renderer }'s device, or (CLI and
//                                                        // tests) a device of its own; checks the limits it needs
//                                                        // and reads one dispatch back exactly (the self test)
//     const k = R.kernel('route_incise');                // kernels/route_incise.wgsl, common.wgsl prefixed; compiled
//                                                        // once per channel signature of the fields bound to it
//     const k2 = R.kernel('x', sourceText);              // or source text, or R.kernel('x', { source, defines })
//     const t = R.field(h, w, 4, float32Array);          // (h, w, 1 | 2 | 4) f32: array<f32 | vec2f | vec4f>
//     const o = R.empty([h, w], 4);                      // zeroed
//     R.run(k, { st: t }, { outS: o }, { uDx: 7.8 });    // one dispatch covering the first image; recorded, not sent
//     const a = await R.read(o);                         // Float32Array, h * w * channels: bit for bit the field
//     const pp = R.pair(h, w, 4, data);                  // pp.src / pp.dst, pp.swap(), await pp.read()
//
// Arrays are [row j, column i] with row 0 the SOUTH edge (core/grid.js); cell (x, y) = (i, j), so st_at(vec2(i, j))
// reads arr[j * w + i] and +y in a kernel is north. The Blender textures' layout, in buffers.
//
// A kernel file declares its interface in `//!` lines, the Blender kernels' own grammar (parse_spec), so a GLSL
// kernel's header is copied over unchanged:
//
//     //! sampler st                 an input field, read with st_at(q) -> vec4<f32> (a 1- or 2-channel field widens
//                                    to (r, 0, 0, 1) / (r, g, 0, 1), as texelFetch does on R32F / RG32F) and st_size()
//     //! image   outS rgba32f       an output field (rgba32f is the default; r32f, rg32f): outS_store(q, v: vec4<f32>)
//                                    and outS_size(); a store outside the field does nothing, as imageStore
//     //! uniform float uDx          a uniform, read as u.uDx: float int vec2 vec3 vec4 ivec2 ivec3 ivec4
//     //! local   16 16              the work-group size (16 x 16 is the default and the house rule)
//
// and its body is `fn kmain(p: vec2<i32>)`, called once per invocation with the cell. So a GLSL body moves over with
// texelFetch(st, q, 0) read as st_at(q), imageStore as *_store, textureSize as *_size(), uDx as u.uDx, and `out`
// parameters as pointers. Every declared binding and uniform must be given on every run, a name that is not declared
// is refused with the nearest declared ones, and a field may not be a sampler and an image of the same dispatch
// (ping-pong instead). common.wgsl (neighbour tables, boundary modes, pins, the PCG hash) is prefixed to every kernel.
//
// What this port adds to that grammar (none of it changes how a Blender header is read):
//     //! include noise              prefix kernels/noise.wgsl too (plan 4.2: what Blender's breakup_source() does by
//                                    substituting GLSL_NOISE); a path is relative to kernels/ ('prims/lib')
//     //! image   outL r32ui         integer outputs r32ui / r32i: outL_store(q, v: u32 | i32). The numpy code that
//                                    moves to the GPU (plan 3.4) keeps labels, receivers and counts as integers
//     //! image   hist atomic_u32    an atomic<u32> (or atomic_i32) array, for atomicAdd / atomicMin / atomicMax on
//                                    order-independent quantities (plan 2.3): hist_b is the raw array
//     //! sampler lab r32ui          a sampler's format, when it is not float: lab_at(q) -> u32 (r32i: i32). A float
//                                    sampler may name its format too (r32f, rg32f, rgba32f); then the field given is
//                                    checked against it. Without one, any float field binds (Blender's behaviour)
// Every binding's raw array is <name>_b (row-major, index j * w + i), and an image can be read where a kernel works
// in place: <name>_load(q).
//
// Where this differs from gpu.py, and why:
//   - Fields are storage buffers, not textures (plan 4.3): no format limits, read-write, atomics; measured as fast or
//     faster. A Field is (h, w, channels, kind); texture(arr) is field(h, w, channels, data), read(tex) is
//     `await read(field)`, PingPong is Pair (both names are exported).
//   - WebGPU has no push constants: every dispatch's uniforms take one 256-byte slot of a 4 MB ring, chosen by a
//     dynamic offset (plan 4.4). The sizes of every sampler and image ride in the same slot.
//   - Dispatches are recorded into one compute pass per command buffer and submitted in batches (every `submitEvery`
//     dispatches, at a read, or at flush()): one submit per dispatch costs a hundred times more (plan 4.4, measured).
//     Blender's implicit barrier after every dispatch is the order of the recorded commands.
//   - WebGPU cannot read back synchronously: read(), readRange(), readAll() and idle() are async, and every wait
//     costs about 16 ms here (plan 4.5). They reuse one mapped readback buffer and copy into a caller's array.
//   - Compile and validation errors are caught in error scopes and raised at the next read / idle / check, naming
//     the kernel and listing the generated source with line numbers (plan 4.2).
//   - pack() / unpack() run on the GPU (kernels/prims/pack.wgsl, unpack.wgsl): Blender stacks numpy arrays on the
//     CPU; this edition does no per-cell work in JavaScript.
//   - `defines` become WGSL consts prefixed to the kernel (WGSL has no preprocessor).
//   - RGBA16F is not offered: no Blender terrain kernel declares it, and a float32 buffer would not round as it does.
//   - Modules compile through GPUDevice.prototype.createShaderModule.call(device, desc), never the device's own
//     method: on a scene's device eidoverse/render_common.mjs replaces it with a wrapper that rewrites u32(0) to 0
//     for three.js's shaders, which would make a terrain kernel's `var c = u32(0);` an i32 (plan 4.2, C7).
//   - The dispatch hook (plan 4.2, 5.7): onDispatch(fn) and onReadback(fn) see every dispatch and every readback,
//     the port's half of the dispatch log and the step snapshots (Runner.snapshot); off, they cost one branch.
//     context.op names the op the records carry (run.js sets it as each op starts).
//
// One rule for kernel text on this edition's devices: `%` only of non-negative numbers. On Deno 2.8.1's wgpu here
// an i32 `%` with a negative operand gives the remainder of the bits read as unsigned (measured: -1 % 300 = 195, where
// WGSL defines -1; `/` is right). kernels/prims/lib.wgsl reflect_index and prims/box_pass.wgsl show two ways round it.
//
// The runner fails loudly without WebGPU compute or with too few storage buffers per stage; there is no CPU path in
// production. The Blender numpy twins (core/twins.py) are the test oracles, run in Python (tests/core_runner/).

import { requestRenderAdapter } from '../../gpu_check.mjs';

export const LOCAL = [16, 16];                          // the house work-group size
export const PUSH_LIMIT_BYTES = 128;                    // Vulkan's guaranteed minimum (Blender's limit): kernels stay
                                                        // portable to both editions
export const SLOT = 256;                                // one dispatch's uniforms (minUniformBufferOffsetAlignment)
export const RING_BYTES = 4 << 20;                      // 16384 dispatches per command buffer
export const SUBMIT_EVERY = 512;                        // dispatches per submit: about 50 nine-pass steps (plan 4.4)
export const MIN_STORAGE_BUFFERS = 9;                   // route_incise and u_carve bind 7 inputs + 2 outputs
// the limits a device must be asked for (eidoverse/render_common.mjs asks for the same list)
export const DEVICE_LIMITS = ['maxStorageBufferBindingSize', 'maxBufferSize', 'maxUniformBufferBindingSize',
    'maxStorageBuffersPerShaderStage', 'maxComputeWorkgroupStorageSize'];

const KERNEL_DIR = new URL('../kernels/', import.meta.url);

// uniform types: [WGSL type, alignment, size in the struct, Blender's push-constant bytes, components, integer]
const UNIFORM_TYPES = {
    float: ['f32', 4, 4, 4, 1, false], int: ['i32', 4, 4, 4, 1, true],
    vec2: ['vec2<f32>', 8, 8, 8, 2, false], vec3: ['vec3<f32>', 16, 12, 12, 3, false],
    vec4: ['vec4<f32>', 16, 16, 16, 4, false],
    ivec2: ['vec2<i32>', 8, 8, 8, 2, true], ivec3: ['vec3<i32>', 16, 12, 12, 3, true],
    ivec4: ['vec4<i32>', 16, 16, 16, 4, true],
};
// field formats: the element type of the buffer, channels, the scalar kind, atomic
const FORMATS = {
    r32f: { elem: 'f32', channels: 1, kind: 'f32' },
    rg32f: { elem: 'vec2<f32>', channels: 2, kind: 'f32' },
    rgba32f: { elem: 'vec4<f32>', channels: 4, kind: 'f32' },
    r32ui: { elem: 'u32', channels: 1, kind: 'u32' },
    r32i: { elem: 'i32', channels: 1, kind: 'i32' },
    atomic_u32: { elem: 'atomic<u32>', channels: 1, kind: 'u32', atomic: true },
    atomic_i32: { elem: 'atomic<i32>', channels: 1, kind: 'i32', atomic: true },
};
const FLOAT_FORMAT = { 1: 'r32f', 2: 'rg32f', 4: 'rgba32f' };
const ARRAY_OF = { f32: Float32Array, u32: Uint32Array, i32: Int32Array };

const HEADER = /^\s*\/\/!\s*(\w+)\s*(.*?)\s*$/;
// GPUDevice's own createShaderModule (the instance's may be render_common.mjs's wrapper, plan 4.2)
const SHADER_MODULE = globalThis.GPUDevice?.prototype?.createShaderModule ??
    function (desc) { return Object.getPrototypeOf(this).createShaderModule.call(this, desc); };
const IDENT = /^[A-Za-z_]\w*$/;
const LOOKS_LIKE_FORMAT = /^((r|rg|rgb|rgba)\d+(f|i|ui)?|atomic_[ui]32)$/i;


// ---------------------------------------------------------------------------------------------------- names ---

function editDistance(a, b) {
    const d = Array.from({ length: a.length + 1 }, (_, i) => [i, ...new Array(b.length).fill(0)]);
    for (let j = 1; j <= b.length; j++) d[0][j] = j;
    for (let i = 1; i <= a.length; i++) {
        for (let j = 1; j <= b.length; j++) {
            d[i][j] = Math.min(d[i - 1][j] + 1, d[i][j - 1] + 1, d[i - 1][j - 1] + (a[i - 1] === b[j - 1] ? 0 : 1));
        }
    }
    return d[a.length][b.length];
}

/** The names closest to `name` (difflib.get_close_matches' job): at most n, nearest first, none when all are far. */
export function nearestNames(name, names, n = 3) {
    const low = String(name).toLowerCase();
    return [...names].map((s) => [editDistance(low, String(s).toLowerCase()), s])
        .filter(([d, s]) => d <= Math.max(2, Math.ceil(0.5 * Math.max(low.length, String(s).length))))
        .sort((a, b) => a[0] - b[0]).slice(0, n).map(([, s]) => s);
}

function nearestText(name, names) {
    const near = nearestNames(name, names);
    return near.length ? ` (did you mean ${near.map((s) => `'${s}'`).join(', ')}?)` :
        ` (declared: ${[...names].sort().map((s) => `'${s}'`).join(', ') || 'none'})`;
}

function fnv1a(text) {                                  // a short name for a source, for logs and cache keys
    let a = 0x811c9dc5, b = 0x9e3779b9;
    for (let i = 0; i < text.length; i++) {
        const c = text.charCodeAt(i);
        a = Math.imul(a ^ c, 0x01000193);
        b = Math.imul(b ^ (c + i), 0x85ebca6b);
    }
    return (a >>> 0).toString(16).padStart(8, '0') + (b >>> 0).toString(16).padStart(8, '0');
}


// -------------------------------------------------------------------------------------------------- kernels ---

/** A kernel's interface, parsed from its `//!` lines: samplers (names, in order), samplerFormats {name: format}
 * (only those that declare one), images {name: format}, uniforms {name: glsl type}, local [x, y], includes. Plain
 * JavaScript: no GPU needed. */
export class KernelSpec {
    constructor(name, samplers, samplerFormats, images, uniforms, local, includes) {
        Object.assign(this, { name, samplers, samplerFormats, images, uniforms, local, includes });
    }

    /** Blender's push-constant bytes: what the same uniforms cost there (the limit both editions keep). */
    pushBytes() {
        return Object.values(this.uniforms).reduce((s, t) => s + UNIFORM_TYPES[t][3], 0);
    }
}

/** Read the `//!` declarations of a kernel source (gpu.py parse_spec). Anything after a declaration's name (and
 * its format) is a description. Throws naming the line on a bad one. */
export function parseSpec(text, name = 'kernel') {
    const samplers = [], samplerFormats = {}, images = {}, uniforms = {}, includes = [];
    let local = LOCAL;
    const lines = String(text).split(/\r?\n/);
    for (let ln = 1; ln <= lines.length; ln++) {
        const m = HEADER.exec(lines[ln - 1]);
        if (!m) continue;
        const kind = m[1];
        const toks = m[2].split(/\s+/).filter(Boolean).map((t) => t.replace(/;+$/, ''));
        let bad = null;
        const format = () => {
            if (toks.length > 1 && LOOKS_LIKE_FORMAT.test(toks[1])) {
                const f = toks[1].toLowerCase();
                if (!FORMATS[f]) bad = `format '${toks[1]}' is not one of ${Object.keys(FORMATS).join(', ')}`;
                return f;
            }
            return null;
        };
        if (kind === 'sampler' && toks.length && IDENT.test(toks[0])) {
            samplers.push(toks[0]);
            const f = format();
            if (f && FORMATS[f]?.atomic) bad = `a sampler is read-only; '${toks[1]}' is an image format`;
            if (f) samplerFormats[toks[0]] = f;
        } else if (kind === 'image' && toks.length && IDENT.test(toks[0])) {
            images[toks[0]] = format() ?? 'rgba32f';
        } else if (kind === 'uniform' && toks.length >= 2 && IDENT.test(toks[1])) {
            if (!UNIFORM_TYPES[toks[0]]) bad = `uniform type '${toks[0]}' is not one of ${Object.keys(UNIFORM_TYPES).sort().join(', ')}`;
            uniforms[toks[1]] = toks[0];
        } else if (kind === 'local' && toks.length >= 2 && /^\d+$/.test(toks[0]) && /^\d+$/.test(toks[1])) {
            local = [parseInt(toks[0], 10), parseInt(toks[1], 10)];
        } else if (kind === 'include' && toks.length && /^[A-Za-z_][\w/]*$/.test(toks[0])) {
            includes.push(toks[0]);
        } else {
            bad = `cannot read the declaration '${lines[ln - 1].trim()}'; expected '//! sampler <name> [format]', ` +
                `'//! image <name> [format]', '//! uniform <type> <name>', '//! local <x> <y>' or '//! include <file>' ` +
                `(then any description)`;
        }
        if (bad) throw new Error(`${name}:${ln}: ${bad}`);
    }
    const names = [...samplers, ...Object.keys(images), ...Object.keys(uniforms)];
    const seen = new Set(), dup = new Set();
    // an image or a uniform redeclared replaces its entry above, so count the declarations themselves
    for (const line of lines) {
        const m = HEADER.exec(line);
        if (!m || !['sampler', 'image', 'uniform'].includes(m[1])) continue;
        const toks = m[2].split(/\s+/).filter(Boolean).map((t) => t.replace(/;+$/, ''));
        const n = m[1] === 'uniform' ? toks[1] : toks[0];
        if (seen.has(n)) dup.add(n);
        seen.add(n);
    }
    if (dup.size) throw new Error(`${name}: declared twice: ${[...dup].sort().join(', ')}`);
    if (!Object.keys(images).length) throw new Error(`${name}: a kernel needs at least one \`//! image\` output`);
    for (const n of names) {
        if (n.startsWith('_n_') || n === 'u') throw new Error(`${name}: '${n}' is a name the runner generates`);
    }
    const spec = new KernelSpec(name, samplers, samplerFormats, images, uniforms, local, includes);
    if (spec.pushBytes() > PUSH_LIMIT_BYTES) {
        throw new Error(`${name}: ${spec.pushBytes()} bytes of uniforms; the limit is ${PUSH_LIMIT_BYTES} bytes, ` +
            `Blender's push constants (put per-cell or long parameter lists in a field)`);
    }
    return spec;
}

/** kernels/<name>.wgsl as a URL ('prims/reduce_first' names a file in a subfolder). */
export function kernelUrl(name) {
    return new URL(`${name}.wgsl`, KERNEL_DIR);
}

function readText(url) {
    if (typeof Deno === 'undefined' || !Deno.readTextFileSync) {
        throw new Error(`terrain GPU runner: cannot read ${url} here (no synchronous file access); pass the kernel's source text`);
    }
    return Deno.readTextFileSync(url);
}

function kernelNames(dirUrl, prefix = '') {
    const out = [];
    try {
        for (const e of Deno.readDirSync(dirUrl)) {
            if (e.isFile && e.name.endsWith('.wgsl')) out.push(prefix + e.name.slice(0, -5));
            else if (e.isDirectory) out.push(...kernelNames(new URL(e.name + '/', dirUrl), prefix + e.name + '/'));
        }
    } catch (_e) { /* no folder: no names */ }
    return out;
}

/** { name, text, spec }: a kernel's own text and its parsed interface (gpu.py load_source; common.wgsl and the
 * includes are joined when it is compiled). Give `name` (a file in kernels/), opts.url (a file anywhere) or
 * opts.source (text). */
export function loadSource(name = null, opts = {}) {
    let text = opts.source ?? null;
    if (text == null) {
        const url = opts.url ? new URL(opts.url) : kernelUrl(name);
        try {
            text = readText(url);
        } catch (e) {
            if (!(typeof Deno !== 'undefined' && e instanceof Deno.errors.NotFound)) throw e;
            const near = nearestNames(name ?? '', kernelNames(KERNEL_DIR));
            throw new Error(`no kernel file ${url.pathname.split('/').slice(-3).join('/')}` +
                (near.length ? `; did you mean ${near.map((s) => `'${s}'`).join(', ')}?` : ''));
        }
        name = name ?? url.pathname.split('/').pop().replace(/\.wgsl$/, '');
    }
    name = name ?? 'kernel';
    return { name, text, spec: parseSpec(text, name) };
}

/** A kernel: .name, .text, .spec, .hash, .blender (transcribed from a Blender kernel: a file directly in kernels/,
 * as against the port's own in kernels/<owner>/, plan 3.1; what the dispatch log marks, 5.2); compiled per channel
 * signature when it first runs. */
export class Kernel {
    constructor(name, text, spec, defines, common, hash, blender = false) {
        Object.assign(this, { name, text, spec, defines, common, hash, blender });
        this.imageNames = Object.keys(spec.images);
        this.imageSigs = this.imageNames.map((n) => `${FORMATS[spec.images[n]].channels}${FORMATS[spec.images[n]].kind[0]}`);
        this.uniformNames = Object.keys(spec.uniforms);
        this._compiled = new Map();
    }

    /** The work groups that cover (h, w). */
    groupsFor(shape) {
        const [lx, ly] = this.spec.local;
        return [Math.ceil(shape[1] / lx), Math.ceil(shape[0] / ly), 1];
    }
}


// --------------------------------------------------------------------------------------------------- fields ---

/** A 2D field on the GPU: h rows, w columns, 1 | 2 | 4 channels of f32 (or one of u32 / i32), row 0 south.
 * .name (null until its owner sets one, a level field's name, say) is what the readback records carry. */
export class Field {
    constructor(runner, h, w, channels, kind, buffer) {
        Object.assign(this, { runner, h, w, channels, kind, buffer });
        this.name = null;
        this.id = runner._nextId++;
        this.sig = `${channels}${kind[0]}`;                 // '4f', '1f', '1u', '1i': the channel signature
        this._groups = null;                                // cached bind-group keys that hold this field
        this.destroyed = false;
    }

    get bytes() { return this.h * this.w * this.channels * 4; }
    get shape() { return [this.h, this.w, this.channels]; }
    get format() { return this.kind === 'f32' ? FLOAT_FORMAT[this.channels] : (this.kind === 'u32' ? 'r32ui' : 'r32i'); }

    destroy() { this.runner.release(this); }
}

/** Two fields of one size and format for an iterated kernel: read .src, write .dst, then swap() (gpu.py PingPong).
 * Bind groups are cached per (kernel, fields), so a pair costs two bind groups for a whole run. */
export class Pair {
    constructor(runner, h, w, channels = 4, data = null, kind = 'f32') {
        this.runner = runner;
        this.src = runner.field(h, w, channels, data, kind);
        this.dst = runner.field(h, w, channels, null, kind);
    }

    swap() { const t = this.src; this.src = this.dst; this.dst = t; }
    read(into = null) { return this.runner.read(this.src, into); }
    destroy() { this.src.destroy(); this.dst.destroy(); }
}
export { Pair as PingPong };


// --------------------------------------------------------------------------------------------------- layout ---

function uniformLayout(spec) {
    // WGSL's uniform-struct layout: each member at its alignment; the samplers' and images' sizes appended as
    // vec2<i32> (w, h)
    const members = [...Object.entries(spec.uniforms),
        ...spec.samplers.map((s) => [`_n_${s}`, 'ivec2']), ...Object.keys(spec.images).map((s) => [`_n_${s}`, 'ivec2'])];
    let off = 0;
    const out = [];
    for (const [name, type] of members) {
        const [, align, size, , comps, isInt] = UNIFORM_TYPES[type];
        off = Math.ceil(off / align) * align;
        out.push({ name, type, off: off / 4, comps, isInt, sizeOf: name.startsWith('_n_') ? name.slice(3) : null });
        off += size;
    }
    const size = Math.ceil(Math.max(off, 16) / 16) * 16;
    if (size > SLOT) throw new Error(`${spec.name}: its uniforms and sizes take ${size} bytes; a slot holds ${SLOT}`);
    return { members: out, size };
}

function generate(kernel, sigs, common, includeTexts) {
    const spec = kernel.spec;
    const lay = uniformLayout(spec);
    const L = [];
    L.push('struct Uniforms {', ...lay.members.map((m) => `  ${m.name}: ${UNIFORM_TYPES[m.type][0]},`), '}');
    L.push('@group(0) @binding(0) var<uniform> u: Uniforms;');
    let b = 1;
    const index = (s) => `q.y * u._n_${s}.x + q.x`;
    spec.samplers.forEach((s, i) => {
        const f = FORMATS[sigs[i]];
        L.push(`@group(0) @binding(${b++}) var<storage, read> ${s}_b: array<${f.elem}>;`);
        L.push(`fn ${s}_size() -> vec2<i32> { return u._n_${s}; }`);
        if (f.kind !== 'f32') {
            L.push(`fn ${s}_at(q: vec2<i32>) -> ${f.elem} { return ${s}_b[${index(s)}]; }`);
        } else {
            const e = `${s}_b[${index(s)}]`;
            const wide = f.channels === 1 ? `vec4<f32>(${e}, 0.0, 0.0, 1.0)` : f.channels === 2 ? `vec4<f32>(${e}, 0.0, 1.0)` : e;
            L.push(`fn ${s}_at(q: vec2<i32>) -> vec4<f32> { return ${wide}; }`);
        }
    });
    for (const [im, fmt] of Object.entries(spec.images)) {
        const f = FORMATS[fmt];
        const scalar = f.kind === 'u32' ? 'u32' : 'i32';
        const ok = `q.x >= 0 && q.y >= 0 && q.x < u._n_${im}.x && q.y < u._n_${im}.y`;
        L.push(`@group(0) @binding(${b++}) var<storage, read_write> ${im}_b: array<${f.elem}>;`);
        L.push(`fn ${im}_size() -> vec2<i32> { return u._n_${im}; }`);
        if (f.atomic) {
            L.push(`fn ${im}_store(q: vec2<i32>, v: ${scalar}) { if (${ok}) { atomicStore(&${im}_b[${index(im)}], v); } }`);
            L.push(`fn ${im}_load(q: vec2<i32>) -> ${scalar} { return atomicLoad(&${im}_b[${index(im)}]); }`);
        } else if (f.kind !== 'f32') {
            L.push(`fn ${im}_store(q: vec2<i32>, v: ${scalar}) { if (${ok}) { ${im}_b[${index(im)}] = v; } }`);
            L.push(`fn ${im}_load(q: vec2<i32>) -> ${scalar} { return ${im}_b[${index(im)}]; }`);
        } else {
            const v = f.channels === 1 ? 'v.x' : f.channels === 2 ? 'v.xy' : 'v';
            const e = `${im}_b[${index(im)}]`;
            const wide = f.channels === 1 ? `vec4<f32>(${e}, 0.0, 0.0, 1.0)` : f.channels === 2 ? `vec4<f32>(${e}, 0.0, 1.0)` : e;
            L.push(`fn ${im}_store(q: vec2<i32>, v: vec4<f32>) { if (${ok}) { ${e} = ${v}; } }`);
            L.push(`fn ${im}_load(q: vec2<i32>) -> vec4<f32> { return ${wide}; }`);
        }
    }
    for (const [name, value] of Object.entries(kernel.defines)) L.push(`const ${name} = ${value};`);
    let src = L.join('\n') + '\n';
    if (common != null) src += common + '\n';
    for (const t of includeTexts) src += t + '\n';
    const kernelLine = src.split('\n').length;
    src += kernel.text + '\n';
    src += `@compute @workgroup_size(${spec.local[0]}, ${spec.local[1]})\n` +
        'fn eido_entry(@builtin(global_invocation_id) gid: vec3<u32>) { kmain(vec2<i32>(gid.xy)); }\n';
    return { src, lay, kernelLine };
}

function numbered(src) {
    return src.split('\n').map((l, i) => `${String(i + 1).padStart(4)}: ${l}`).join('\n');
}


// --------------------------------------------------------------------------------------------------- runner ---

const SELF_TEST = `//! image outT rgba32f
fn kmain(p: vec2<i32>) { outT_store(p, vec4<f32>(f32(p.x) * 3.0 + 7.0, f32(p.y), 0.0, 1.0)); }
`;

export class Runner {
    /** A runner on `device`. opts: submitEvery (dispatches per submit, default SUBMIT_EVERY), info (the adapter's,
     * for logs), warn. Use init() unless you hold the device yourself: it also runs the self test. */
    constructor(device, opts = {}) {
        if (!device || typeof device.createBuffer !== 'function') throw new Error('terrain GPU runner: a GPUDevice is needed');
        const have = device.limits?.maxStorageBuffersPerShaderStage ?? 0;
        if (have < MIN_STORAGE_BUFFERS) {
            throw new Error(`terrain GPU runner: this device allows ${have} storage buffers per shader stage ` +
                `(maxStorageBuffersPerShaderStage); the kernels route_incise and u_carve bind ${MIN_STORAGE_BUFFERS}. ` +
                `Ask for the adapter's limit when the device is created (eidoverse/render_common.mjs and this ` +
                `module's requestDevice() do); an adapter that offers fewer cannot run the terrain generator`);
        }
        this.device = device;
        this.info = opts.info ?? null;
        this.warn = opts.warn ?? console.warn;
        this.submitEvery = Math.min(opts.submitEvery ?? SUBMIT_EVERY, RING_BYTES / SLOT);
        this.ring = device.createBuffer({ size: RING_BYTES, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST,
            label: 'terrain uniform ring' });
        this.stage = new ArrayBuffer(RING_BYTES);           // the ring's staging area: one upload per command buffer
        this.f32 = new Float32Array(this.stage);
        this.i32 = new Int32Array(this.stage);
        this.common = readText(new URL('common.wgsl', KERNEL_DIR));
        this._includes = new Map();
        this._kernels = new Map();                          // source key -> Kernel
        this.bindGroups = new Map();
        this._nextId = 1;
        this._errors = [];                                  // promises of errors caught in scopes, raised at a sync
        this._grave = [];                                   // buffers to destroy once the commands using them are sent
        this._readBuffer = null;
        this._chain = Promise.resolve();                    // reads take turns on the one readback buffer
        this._dummies = [];
        this._hold = false;
        this.lost = null;
        device.lost?.then((i) => { this.lost = i; });
        // counters: dispatches issued, command buffers submitted, bytes of fields alive and their peak
        this.dispatches = 0;
        this.submits = 0;
        this.fieldBytes = 0;
        this.peakFieldBytes = 0;
        this.fields = 0;
        this.compileMs = {};                                // kernel name -> the wall time of its first build, ms
        this._begin();
    }

    // ---- fields

    /** A field of h rows and w columns holding `data` exactly (a Float32Array / Uint32Array / Int32Array of
     * h * w * channels, row 0 south), or zeros. channels 1 | 2 | 4 for 'f32'; 1 for 'u32' and 'i32'. */
    field(h, w, channels = 4, data = null, kind = 'f32') {
        if (!Number.isInteger(h) || !Number.isInteger(w) || h < 1 || w < 1) throw new Error(`field: a size of ${h} x ${w} cells`);
        if (!ARRAY_OF[kind]) throw new Error(`field: kind '${kind}' is not 'f32', 'u32' or 'i32'`);
        if (![1, 2, 4].includes(channels) || (kind !== 'f32' && channels !== 1)) {
            throw new Error(`field: ${channels} channels of ${kind}; 1, 2 or 4 of f32 or 1 of u32 / i32 (pad three channels to four)`);
        }
        const bytes = h * w * channels * 4;
        this.device.pushErrorScope('out-of-memory');
        const buffer = this.device.createBuffer({ size: Math.max(bytes, 16),
            usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
        this._errors.push(this.device.popErrorScope().then((e) => e &&
            new Error(`terrain GPU runner: out of GPU memory for a ${h} x ${w} x ${channels} field (${this.fieldBytes >> 20} MB of fields held): ${e.message}`)));
        const f = new Field(this, h, w, channels, kind, buffer);
        this.fields++;
        this.fieldBytes += bytes;
        this.peakFieldBytes = Math.max(this.peakFieldBytes, this.fieldBytes);
        if (data != null) this._upload(f, data);
        return f;
    }

    /** A zeroed field of shape [h, w] (gpu.py empty). */
    empty(shape, channels = 4, kind = 'f32') { return this.field(shape[0], shape[1], channels, null, kind); }

    /** A zeroed field of the same size and format (gpu.py like). */
    like(f) { return this.field(f.h, f.w, f.channels, null, f.kind); }

    /** A Pair (two fields, the first holding `data`). */
    pair(h, w, channels = 4, data = null, kind = 'f32') { return new Pair(this, h, w, channels, data, kind); }

    _upload(f, data) {
        const want = ARRAY_OF[f.kind];
        if (!(data instanceof want) || data.length !== f.h * f.w * f.channels) {
            throw new Error(`field data: a ${want.name} of ${f.h} x ${f.w} x ${f.channels} = ${f.h * f.w * f.channels} values is ` +
                `needed, got ${data?.constructor?.name} of ${data?.length}`);
        }
        this.device.queue.writeBuffer(f.buffer, 0, data);
    }

    /** Replace a field's contents. Commands recorded so far are sent first, so they still see the old values. */
    write(f, data) {
        this._alive(f);
        if (this._dirty) this.flush();
        this._upload(f, data);
    }

    /** dst = src on the GPU (same size and format). */
    copy(src, dst) {
        this._alive(src);
        this._alive(dst);
        if (src.h !== dst.h || src.w !== dst.w || src.sig !== dst.sig) {
            throw new Error(`copy: ${src.h} x ${src.w} ${src.format} into ${dst.h} x ${dst.w} ${dst.format}`);
        }
        if (src === dst) return;
        this._endPass();
        this.enc.copyBufferToBuffer(src.buffer, 0, dst.buffer, 0, src.bytes);
        this._dirty = true;
    }

    /** Copies of `fields` as they stand after the commands recorded so far (a step snapshot, plan 5.7: taken inside
     * onDispatch it holds exactly that dispatch's output; read the copies later, then destroy them). */
    snapshot(fields) {
        return fields.map((f) => {
            const c = this.like(f);
            this.copy(f, c);
            return c;
        });
    }

    /** Zero a field on the GPU. */
    clear(f) {
        this._alive(f);
        this._endPass();
        this.enc.clearBuffer(f.buffer);
        this._dirty = true;
    }

    /** Release a field's buffer (after the commands recorded so far are sent). */
    release(f) {
        if (f.destroyed) return;
        f.destroyed = true;
        if (f._groups) for (const key of f._groups) this.bindGroups.delete(key);
        f._groups = null;
        this.fields--;
        this.fieldBytes -= f.bytes;
        if (this._dirty) this._grave.push(f.buffer);
        else f.buffer.destroy();
    }

    _alive(f) {
        if (!(f instanceof Field)) throw new Error('a Field of this runner is needed');
        if (f.destroyed) throw new Error(`a released field (${f.h} x ${f.w} ${f.format}) is used`);
        if (f.runner !== this) throw new Error('a field of another runner (another GPU device) is used');
    }

    // ---- kernels

    /** The kernel kernels/<name>.wgsl, or source text (a string, or opts.source), or a file anywhere (opts.url).
     * opts.defines {NAME: value} become consts; opts.common false leaves common.wgsl out; opts.blender marks a
     * transcribed Blender kernel loaded by url or source (a file directly in kernels/ is one; kernels/<owner>/ and
     * source text are the port's own). One Kernel per source and defines: later calls return it (gpu.py kernel). */
    kernel(name, opts = null) {
        if (typeof opts === 'string') opts = { source: opts };
        opts = opts ?? {};
        const { name: nm, text, spec } = loadSource(name, opts);
        const defines = Object.fromEntries(Object.entries(opts.defines ?? {}).map(([k, v]) => [String(k), String(v)])
            .sort((a, b) => (a[0] < b[0] ? -1 : 1)));
        const common = opts.common !== false;
        const blender = opts.blender ?? (opts.source == null && opts.url == null && !nm.includes('/'));
        const key = `${nm}\0${text}\0${JSON.stringify(defines)}\0${common}\0${blender}`;
        let k = this._kernels.get(key);
        if (!k) {
            k = new Kernel(nm, text, spec, defines, common, fnv1a(key), blender);
            this._kernels.set(key, k);
        }
        return k;
    }

    _include(name) {
        if (!this._includes.has(name)) {
            try {
                this._includes.set(name, readText(kernelUrl(name)));
            } catch (e) {
                throw new Error(`//! include ${name}: no kernels/${name}.wgsl (${e.message})`);
            }
        }
        return this._includes.get(name);
    }

    _signature(k, samplers) {
        const sigs = [];
        for (const s of k.spec.samplers) {
            const f = samplers[s];
            const fmt = f.format;
            const want = k.spec.samplerFormats[s];
            if (want ? want !== fmt : f.kind !== 'f32') {
                throw new Error(`kernel '${k.name}': sampler '${s}' is ${want ? `declared ${want}` : 'a float sampler'}, ` +
                    `the field is ${fmt}` + (want ? '' : ` (declare \`//! sampler ${s} ${fmt}\` to read integers)`));
            }
            sigs.push(fmt);
        }
        return sigs;
    }

    // the compiled pipeline for the formats `sigs` of the samplers, cached under `key` (the fields' .sig joined)
    _compile(k, sigs, key = null) {
        key = key ?? sigs.map((f) => `${FORMATS[f].channels}${FORMATS[f].kind[0]}`).join('');
        let c = k._compiled.get(key);
        if (c) return c;
        const { src, lay, kernelLine } = generate(k, sigs, k.common ? this.common : null, k.spec.includes.map((n) => this._include(n)));
        const d = this.device;
        const entries = [{ binding: 0, visibility: GPUShaderStage.COMPUTE,
            buffer: { type: 'uniform', hasDynamicOffset: true, minBindingSize: lay.size } }];
        let b = 1;
        for (let i = 0; i < k.spec.samplers.length; i++) {
            entries.push({ binding: b++, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } });
        }
        for (let i = 0; i < Object.keys(k.spec.images).length; i++) {
            entries.push({ binding: b++, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } });
        }
        if (entries.length - 1 > d.limits.maxStorageBuffersPerShaderStage) {
            throw new Error(`kernel '${k.name}' binds ${entries.length - 1} fields; this device allows ` +
                `${d.limits.maxStorageBuffersPerShaderStage} storage buffers per shader stage`);
        }
        const t0 = performance.now();
        d.pushErrorScope('validation');
        const bgl = d.createBindGroupLayout({ entries, label: k.name });
        // the prototype's method, never the instance's: a scene's device carries render_common.mjs's wrapper, which
        // rewrites u32(0) to 0 for three.js's shaders (plan 4.2, C7)
        const module = SHADER_MODULE.call(d, { code: src, label: k.name });
        const pipeline = d.createComputePipeline({ layout: d.createPipelineLayout({ bindGroupLayouts: [bgl] }),
            compute: { module, entryPoint: 'eido_entry' }, label: k.name });
        const err = d.popErrorScope().then((e) => e && new Error(`kernel '${k.name}' failed to compile: ${e.message}\n` +
            `(the kernel's own text starts at line ${kernelLine} of the generated source)\n${numbered(src)}`));
        this._errors.push(err);
        const ms = performance.now() - t0;
        if (!(k.name in this.compileMs)) this.compileMs[k.name] = +ms.toFixed(2);
        c = { id: this._nextId++, bgl, pipeline, lay, src, err };
        k._compiled.set(key, c);
        return c;
    }

    /** Compile `kernel` for the given fields' channel signature now and wait for the compiler: throws naming the
     * kernel, with the generated source, when it fails. `samplers` is the dict run() takes, or a list of channel
     * counts in the samplers' order (the prototype's form). */
    async check(kernel, samplers = {}) {
        const k = typeof kernel === 'string' ? this.kernel(kernel) : kernel;
        let sigs;
        if (Array.isArray(samplers)) {
            sigs = k.spec.samplers.map((s, i) => k.spec.samplerFormats[s] ?? FLOAT_FORMAT[samplers[i] ?? 4]);
        } else {
            for (const s of k.spec.samplers) if (!samplers[s]) throw new Error(`kernel '${k.name}': sampler '${s}' not given`);
            sigs = this._signature(k, samplers);
        }
        this._compile(k, sigs);
        await this._raise();
        return k;
    }

    // ---- dispatch

    _begin() {
        this.enc = this.device.createCommandEncoder();
        this.pass = null;
        this.slot = 0;
        this._dirty = false;
        this._batch = new Set();
    }

    _endPass() {
        if (this.pass) {
            if (this._hold) throw new Error('timed(): only dispatches can be timed (a copy or a clear ends the pass)');
            this.pass.end();
            this.pass = null;
        }
    }

    /** One dispatch of `kernel` (a Kernel, or a kernel's name), recorded. groups null covers the first image with
     * the kernel's local size. Every declared sampler, image and uniform must be given; names are checked against
     * the kernel's `//!` declarations and a mistake names the nearest declared ones (gpu.py run). */
    run(kernel, samplers = null, images = null, uniforms = null, groups = null) {
        const k = typeof kernel === 'string' ? this.kernel(kernel) : kernel;
        const spec = k.spec, sn = spec.samplers, im = k.imageNames, un = k.uniformNames;
        samplers = samplers ?? {};
        images = images ?? {};
        uniforms = uniforms ?? {};
        if (this.lost) throw new Error(`terrain GPU runner: the GPU device was lost (${this.lost.reason ?? ''} ${this.lost.message ?? ''})`);
        // every declared name given, and nothing else (the counts agree once every declared name is there)
        let given = 0, sk = '';
        for (const n in samplers) given++;
        for (const n in images) given++;
        for (const n in uniforms) given++;
        let ok = given === sn.length + im.length + un.length;
        for (let i = 0; ok && i < sn.length; i++) ok = samplers[sn[i]] != null;
        for (let i = 0; ok && i < im.length; i++) ok = images[im[i]] != null;
        for (let i = 0; ok && i < un.length; i++) ok = uniforms[un[i]] != null;
        if (!ok) this._refuse(k, samplers, images, uniforms);
        for (let i = 0; i < sn.length; i++) {
            const f = samplers[sn[i]];
            if (f.destroyed || f.runner !== this) this._alive(f);
            sk += f.sig;
        }
        for (let i = 0; i < im.length; i++) {
            const t = images[im[i]];
            if (t.destroyed || t.runner !== this) this._alive(t);
            if (t.sig !== k.imageSigs[i]) {
                throw new Error(`kernel '${k.name}': image '${im[i]}' is declared ${spec.images[im[i]]}, the field is ${t.format}`);
            }
            for (let s = 0; s < sn.length; s++) {
                if (samplers[sn[s]] === t) {
                    throw new Error(`kernel '${k.name}': a field bound as sampler '${sn[s]}' and as image '${im[i]}' in one dispatch; use a Pair`);
                }
            }
            for (let m = 0; m < i; m++) {
                if (images[im[m]] === t) throw new Error(`kernel '${k.name}': one field bound as images '${im[m]}' and '${im[i]}'`);
            }
        }
        const first = images[im[0]];
        const c = k._compiled.get(sk) ?? this._compile(k, this._signature(k, samplers), sk);
        if (this.slot >= RING_BYTES / SLOT) {
            if (this._hold) throw new Error(`timed(): more than ${RING_BYTES / SLOT} dispatches in one timed pass`);
            this.flush();
        }
        const base = (this.slot * SLOT) / 4;
        for (const m of c.lay.members) {
            const o = base + m.off;
            const view = m.isInt ? this.i32 : this.f32;
            if (m.sizeOf) {
                const f = samplers[m.sizeOf] ?? images[m.sizeOf];
                view[o] = f.w;
                view[o + 1] = f.h;
            } else if (m.comps === 1) {
                const v = uniforms[m.name];
                if (typeof v !== 'number') throw new Error(`kernel '${k.name}': uniform '${m.name}' (${m.type}) is ${JSON.stringify(v)}`);
                view[o] = v;
            } else {
                const v = uniforms[m.name];
                if (v == null || v.length !== m.comps) throw new Error(`kernel '${k.name}': uniform '${m.name}' (${m.type}) needs ${m.comps} numbers, got ${JSON.stringify(v)}`);
                for (let i = 0; i < m.comps; i++) view[o + i] = v[i];
            }
        }
        let key = '' + c.id;
        for (let i = 0; i < sn.length; i++) key += ',' + samplers[sn[i]].id;
        for (let i = 0; i < im.length; i++) key += ',' + images[im[i]].id;
        let bg = this.bindGroups.get(key);
        if (!bg) {
            const fields = [...sn.map((s) => samplers[s]), ...im.map((n) => images[n])];
            this.device.pushErrorScope('validation');
            bg = this.device.createBindGroup({ layout: c.bgl, entries: [
                { binding: 0, resource: { buffer: this.ring, size: c.lay.size } },
                ...fields.map((f, i) => ({ binding: i + 1, resource: { buffer: f.buffer } }))] });
            this._errors.push(this.device.popErrorScope().then((e) => e && new Error(`kernel '${k.name}': its bind group was refused: ${e.message}`)));
            this.bindGroups.set(key, bg);
            for (const f of fields) (f._groups ?? (f._groups = new Set())).add(key);
        }
        if (!this.pass) this.pass = this.enc.beginComputePass();
        this.pass.setPipeline(c.pipeline);
        this.pass.setBindGroup(0, bg, [this.slot * SLOT]);
        const g = groups ?? k.groupsFor([first.h, first.w]);
        this.pass.dispatchWorkgroups(g[0], g[1], g[2] ?? 1);
        this._batch.add(k.name);
        this._dirty = true;
        this.slot++;
        this.dispatches++;
        if (DISPATCH_HOOK !== null) {
            const count = (HOOK_COUNTS.get(k.name) ?? 0) + 1;
            HOOK_COUNTS.set(k.name, count);
            DISPATCH_HOOK({ op: context.op, kernel: k.name, blender: k.blender, uniforms, images, samplers, count,
                index: this.dispatches, runner: this, groups: g });
        }
        if (this.slot >= this.submitEvery && !this._hold) this.flush();
    }

    // say exactly what is wrong with the names given to a dispatch (the slow path of run())
    _refuse(k, samplers, images, uniforms) {
        const spec = k.spec;
        for (const [given, declared, what] of [[samplers, spec.samplers, 'sampler'], [images, k.imageNames, 'image'],
            [uniforms, k.uniformNames, 'uniform']]) {
            for (const n in given) {
                if (!declared.includes(n)) throw new Error(`kernel '${k.name}' has no ${what} '${n}'` + nearestText(n, declared));
            }
            const missing = declared.filter((n) => given[n] == null);
            if (missing.length) {
                throw new Error(`kernel '${k.name}': ${what}s not given: ${missing.join(', ')} (every declared ${what} is required on every run)`);
            }
        }
        throw new Error(`kernel '${k.name}': the names given do not match its declarations`);
    }

    /** Send what has been recorded: one upload of the batch's uniform slots, then one command buffer. */
    flush() {
        if (!this._dirty) return;
        if (this._hold) throw new Error('timed(): the timed pass cannot be flushed from inside');
        const names = [...this._batch].join(', ');
        this.device.pushErrorScope('validation');
        if (this.pass) this.pass.end();
        if (this.slot) this.device.queue.writeBuffer(this.ring, 0, this.stage, 0, this.slot * SLOT);
        this.device.queue.submit([this.enc.finish()]);
        this._errors.push(this.device.popErrorScope().then((e) => e &&
            new Error(`terrain GPU runner: a batch was refused (kernels: ${names || 'none'}): ${e.message}`)));
        this.submits++;
        for (const b of this._grave) b.destroy();
        this._grave.length = 0;
        this._begin();
    }

    async _raise() {
        const errs = this._errors;
        this._errors = [];
        let first = null;
        for (const p of errs) {
            const e = await p;
            first = first ?? (e || null);
        }
        if (first) throw first;
    }

    _serial(fn) {
        const p = this._chain.then(fn, fn);
        this._chain = p.catch(() => {});
        return p;
    }

    // ---- reading

    _readback(bytes) {
        if (!this._readBuffer || this._readBuffer.size < bytes) {
            if (this._readBuffer) this._readBuffer.destroy();
            let size = 1 << 16;
            while (size < bytes) size *= 2;
            this._readBuffer = this.device.createBuffer({ size, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ,
                label: 'terrain readback' });
        }
        return this._readBuffer;
    }

    /** Several ranges in one wait. parts: [{ field, first, count, into }] (first / count in scalar elements; count
     * null = to the end). Returns the typed arrays, in order. */
    readParts(parts) {
        return this._serial(async () => {
            const spans = [];
            let total = 0;
            for (const p of parts) {
                this._alive(p.field);
                const elems = p.field.h * p.field.w * p.field.channels;
                const first = p.first ?? 0;
                const count = p.count ?? (elems - first);
                if (first < 0 || count < 0 || first + count > elems) throw new Error(`read: elements ${first}..${first + count} of a field of ${elems}`);
                const Arr = ARRAY_OF[p.field.kind];
                if (p.into != null && (!(p.into instanceof Arr) || p.into.length < count)) {
                    throw new Error(`read: 'into' must be a ${Arr.name} of at least ${count} values`);
                }
                spans.push({ p, first, count, at: total, Arr });
                total += Math.ceil((count * 4) / 8) * 8;        // every span starts on 8 bytes
            }
            if (!total) return spans.map((s) => s.p.into ?? new s.Arr(0));
            const rb = this._readback(total);
            this._endPass();
            for (const s of spans) if (s.count) this.enc.copyBufferToBuffer(s.p.field.buffer, s.first * 4, rb, s.at, s.count * 4);
            const after = this.dispatches;                   // the read sees every dispatch recorded before it
            this._dirty = true;
            this.flush();
            await this._raise();
            await rb.mapAsync(GPUMapMode.READ, 0, total);
            const out = [];
            try {
                for (const s of spans) {
                    const view = new s.Arr(rb.getMappedRange(s.at, Math.ceil((s.count * 4) / 8) * 8), 0, s.count);
                    if (s.p.into) {
                        s.p.into.set(view);
                        out.push(s.p.into);
                    } else {
                        out.push(view.slice());
                    }
                }
            } finally {
                rb.unmap();
            }
            if (READBACK_HOOK !== null) {
                spans.forEach((s, i) => READBACK_HOOK({ afterDispatch: after, op: context.op, name: s.p.field.name,
                    shape: s.p.field.shape, data: out[i], first: s.first, count: s.count, field: s.p.field, runner: this }));
            }
            return out;
        });
    }

    /** The field's contents (Float32Array / Uint32Array / Int32Array of h * w * channels): bit for bit what it holds
     * (gpu.py read). `into`: a preallocated array to fill instead. */
    async read(f, into = null) {
        return (await this.readParts([{ field: f, into }]))[0];
    }

    /** `count` scalar elements from element `first`: what a convergence check or a controller reads. */
    async readRange(f, first, count, into = null) {
        return (await this.readParts([{ field: f, first, count, into }]))[0];
    }

    /** Several whole fields in one wait: [arrays], in order. */
    readAll(fields, intos = null) {
        return this.readParts(fields.map((field, i) => ({ field, into: intos ? intos[i] : null })));
    }

    /** Send everything and wait until the GPU has done it (gpu.py sync). Raises what the error scopes caught. */
    idle() {
        return this._serial(async () => {
            this.flush();
            await this.device.queue.onSubmittedWorkDone();
            await this._raise();
        });
    }

    sync() { return this.idle(); }

    /** The GPU's own time, in ms, of the dispatches fn() issues (one pass, timestamp queries); null when the device
     * has no 'timestamp-query'. At most RING_BYTES / SLOT dispatches; fn may only call run(). */
    timed(fn) {
        return this._serial(async () => {
            if (!this.device.features.has('timestamp-query')) {
                fn();
                return null;
            }
            this.flush();
            const d = this.device;
            const qs = d.createQuerySet({ type: 'timestamp', count: 2 });
            const rs = d.createBuffer({ size: 16, usage: GPUBufferUsage.QUERY_RESOLVE | GPUBufferUsage.COPY_SRC });
            const rb = d.createBuffer({ size: 16, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
            this.pass = this.enc.beginComputePass({ timestampWrites: { querySet: qs, beginningOfPassWriteIndex: 0, endOfPassWriteIndex: 1 } });
            this._dirty = true;
            this._hold = true;
            try {
                fn();
            } finally {
                this._hold = false;
            }
            this.pass.end();
            this.pass = null;
            this.enc.resolveQuerySet(qs, 0, 2, rs, 0);
            this.enc.copyBufferToBuffer(rs, 0, rb, 0, 16);
            this.flush();
            await this._raise();
            await rb.mapAsync(GPUMapMode.READ);
            const v = new BigUint64Array(rb.getMappedRange().slice(0));
            rb.unmap();
            rb.destroy();
            rs.destroy();
            qs.destroy();
            return Number(v[1] - v[0]) / 1e6;
        });
    }

    // ---- packs (gpu.py pack / unpack, on the GPU)

    _dummy(i, kind = 'f32') {
        const key = `${kind}${i}`;
        let f = this._dummies.find((d) => d.key === key);
        if (!f) {
            f = this.field(1, 1, 1, null, kind);
            f.key = key;
            this._dummies.push(f);
        }
        return f;
    }

    /** Stack up to four named single-channel float fields into one rgba32f field; a name that is null or missing
     * from `fields` gives a zero channel. `fields` is a mapping (a level's Fields, say); shape [h, w] is only needed
     * when no named field exists. */
    pack(fields, names, shape = null) {
        if (names.length > 4) throw new Error(`an RGBA pack holds at most four fields, got ${JSON.stringify(names)}`);
        const given = names.map((n) => (n != null && fields[n] != null ? fields[n] : null));
        const any = given.find((f) => f);
        const [h, w] = shape ?? (any ? [any.h, any.w] : (() => { throw new Error('pack: no field and no shape'); })());
        const samplers = {}, has = [0, 0, 0, 0];
        for (let c = 0; c < 4; c++) {
            const f = given[c] ?? null;
            if (f && (f.h !== h || f.w !== w || f.sig !== '1f')) {
                throw new Error(`pack: field '${names[c]}' is ${f.h} x ${f.w} ${f.format}; ${h} x ${w} r32f is needed`);
            }
            samplers[`c${c}`] = f ?? this._dummy(0);
            has[c] = f ? 1 : 0;
        }
        const out = this.field(h, w, 4);
        this.run('prims/pack', samplers, { outP: out }, { uHas: has });
        return out;
    }

    /** The inverse of pack: { name: r32f field } for every name that is not null. */
    unpack(field, names) {
        if (field.sig !== '4f') throw new Error(`unpack: an rgba32f field is needed, got ${field.format}`);
        const images = {}, out = {};
        for (let c = 0; c < 4; c++) {
            const n = names[c] ?? null;
            images[`o${c}`] = n != null ? (out[n] = this.field(field.h, field.w, 1)) : this._dummy(c + 1);
        }
        this.run('prims/unpack', { src: field }, images, {}, [Math.ceil(field.w / 16), Math.ceil(field.h / 16), 1]);
        return out;
    }

    // ---- textures, only where rendering wants them (plan 4.3)

    /** Copy a float field into a GPUTexture of its size (r32float, rg32float or rgba32float, usage COPY_DST), on the
     * GPU. Rows whose byte length is not a multiple of 256 go through a padded staging buffer. */
    toTexture(f, texture) {
        this._alive(f);
        if (f.kind !== 'f32') throw new Error('toTexture: a float field is needed');
        const rowBytes = f.w * f.channels * 4;
        this._endPass();
        if (rowBytes % 256 === 0 || f.h === 1) {
            this.enc.copyBufferToTexture({ buffer: f.buffer, bytesPerRow: rowBytes, rowsPerImage: f.h }, { texture }, [f.w, f.h, 1]);
            this._dirty = true;
            return;
        }
        const stride = Math.ceil(rowBytes / 256) * 256;
        const stage = this.device.createBuffer({ size: stride * f.h, usage: GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
        for (let j = 0; j < f.h; j++) this.enc.copyBufferToBuffer(f.buffer, j * rowBytes, stage, j * stride, rowBytes);
        this.enc.copyBufferToTexture({ buffer: stage, bytesPerRow: stride, rowsPerImage: f.h }, { texture }, [f.w, f.h, 1]);
        this._dirty = true;
        this._grave.push(stage);
    }

    // ---- the self test and the end

    /** One tiny dispatch whose readback must be exact (gpu.py _self_test, gpu_check.mjs's idea), so a broken driver
     * fails here, loudly. */
    async selfTest() {
        const k = this.kernel('_self_test', { source: SELF_TEST, common: false });
        const t = this.empty([3, 20], 4);
        this.run(k, {}, { outT: t }, {});
        const a = await this.read(t);
        t.destroy();
        for (let j = 0; j < 3; j++) {
            for (let i = 0; i < 20; i++) {
                const o = 4 * (j * 20 + i);
                if (a[o] !== i * 3 + 7 || a[o + 1] !== j || a[o + 2] !== 0 || a[o + 3] !== 1) {
                    throw new Error(`terrain GPU runner: a compute dispatch on ${this.info?.description || 'this GPU'} read back ` +
                        `wrong values; see docs/SETUP.md for the GPU setup`);
                }
            }
        }
        return true;
    }

    /** Release the runner's own buffers (not the device, which may be the scene's). */
    destroy() {
        this.flush();
        for (const d of this._dummies) d.destroy();
        this._dummies.length = 0;
        if (this._readBuffer) this._readBuffer.destroy();
        this._readBuffer = null;
        this.ring.destroy();
        this.bindGroups.clear();
    }
}


// ---------------------------------------------------------------------------------------------- the context ---

// ---- the dispatch hook (plan 4.2, 5.7): the port's half of the dispatch log and the step snapshots

/** What the records carry besides the dispatch itself: op, the op being run (run.js sets it as each op starts). */
export const context = { op: null };

let DISPATCH_HOOK = null, READBACK_HOOK = null;
const HOOK_COUNTS = new Map();                          // kernel name -> its dispatches since the hook was set

/** fn(record) after every dispatch any runner records (null: off; off costs one branch a dispatch). The record:
 * { op (context.op), kernel (its name), blender (true for a kernel transcribed from Blender: 5.2's blender_kernel),
 * uniforms, images, samplers (as given to run(): names to values and to fields, whose h, w and format the log
 * takes), count (that kernel's dispatches so far), index (the runner's dispatch count), runner, groups }. A step
 * snapshot takes runner.snapshot(Object.values(images)) here, at its count, and reads the copies after the batch is
 * submitted: they hold exactly this dispatch's output. Setting a hook starts the counts again. */
export function onDispatch(fn) {
    DISPATCH_HOOK = fn ?? null;
    HOOK_COUNTS.clear();
}

/** fn(record) after every readback, once per field read (read, readRange, readAll, readParts), null: off. The
 * record: { afterDispatch (the runner's dispatch count the read saw), op, name (the field's .name), shape ([h, w,
 * channels]), data (what the read returned), first, count (the elements read), field, runner }. */
export function onReadback(fn) {
    READBACK_HOOK = fn ?? null;
}

const RUNNERS = new WeakMap();                          // GPUDevice -> Runner
let OWN = null;                                         // the device this module made for a CLI or a test

/** A device of the runner's own (the CLI and the tests; a scene's device comes from render_common.mjs):
 * gpu_check.mjs's adapter, the limits of DEVICE_LIMITS raised to the adapter's, 'timestamp-query' when offered.
 * Returns { adapter, device, info }. Fails naming the limit on an adapter with fewer than nine storage buffers per
 * stage. */
export async function requestDevice(opts = {}) {
    const { adapter, info } = await requestRenderAdapter(opts.gpu ?? globalThis.navigator?.gpu, opts.warn ?? console.warn);
    const offered = adapter.limits?.maxStorageBuffersPerShaderStage ?? 0;
    if (offered < MIN_STORAGE_BUFFERS) {
        throw new Error(`terrain GPU runner: the adapter ${info.description || '(unnamed)'} offers ${offered} storage buffers ` +
            `per shader stage (maxStorageBuffersPerShaderStage); the terrain kernels need ${MIN_STORAGE_BUFFERS}`);
    }
    const requiredLimits = {};
    for (const k of DEVICE_LIMITS) {
        const v = adapter.limits?.[k];
        if (v != null) requiredLimits[k] = v;
    }
    const requiredFeatures = ['timestamp-query'].filter((f) => adapter.features.has(f));
    const device = await adapter.requestDevice({ requiredFeatures, requiredLimits });
    return { adapter, device, info };
}

/** The runner of a device, made (and self-tested) once per device (gpu.py init). The device is opts.device, else
 * opts.renderer's (a three.js WebGPURenderer), else the scene's GPU_DEVICE (render_scene.mjs), else one of the
 * module's own (requestDevice). */
export async function init(opts = {}) {
    let device = opts.device ?? opts.renderer?.backend?.device ?? globalThis.GPU_DEVICE ?? null;
    let info = opts.info ?? null;
    if (!device) {
        OWN = OWN ?? await requestDevice(opts);
        ({ device, info } = OWN);
    }
    let R = RUNNERS.get(device);
    if (!R) {
        const raw = info ?? device.adapterInfo ?? null;
        const label = [raw?.description, raw?.vendor, raw?.device].filter(Boolean).join(' / ');
        const software = raw?.backend === 'software' || raw?.isFallbackAdapter === true ||
            /llvmpipe|lavapipe|swiftshader|software|basic render|\bwarp\b|softpipe/i.test(label);
        R = new Runner(device, { ...opts, info: raw });
        if (software) {
            R.warn(`[terrain.gpu] WARNING: software GPU ${label || '(unnamed)'}: kernels run on the CPU, many times slower`);
        }
        RUNNERS.set(device, R);
        try {
            await R.selfTest();
        } catch (e) {
            RUNNERS.delete(device);
            throw e;
        }
    }
    return R;
}

/** Release the module's own device (tests and the CLI call this before they exit). */
export function shutdown() {
    if (OWN) {
        RUNNERS.get(OWN.device)?.destroy();
        RUNNERS.delete(OWN.device);
        OWN.device.destroy();
        OWN = null;
    }
}
