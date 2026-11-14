// Design probe (PORT_PLAN.md section 3): a prototype of the port's GPU runner (core/gpu.js), the counterpart of the
// Blender edition's core/gpu.py. A kernel is a .wgsl file whose interface is declared in `//!` lines with the SAME
// syntax the Blender kernels use, so a GLSL kernel's header is copied over unchanged:
//
//     //! sampler st                 an input field (a storage buffer read through st_at(q) / st_size())
//     //! image   outS rgba32f       an output field (outS_store(q, v) / outS_size()); r32f, rg32f, rgba32f, r32ui
//     //! uniform float uDx          a uniform (u.uDx): float int vec2 vec3 vec4 ivec2 ivec3 ivec4
//
// The runner generates the bindings, the accessors and the uniform struct from those lines, prefixes common.wgsl,
// and wraps the kernel's `fn kmain(p: vec2<i32>)` in a 16 x 16 entry point. Every dispatch's uniforms take one
// 256-byte slot of a ring (a dynamic offset); dispatches are recorded into one compute pass and submitted on
// flush() or read(). A sampler's channel count comes from the field bound to it (1, 2 or 4), so a kernel is
// compiled once per channel signature.

const COMMON = new URL('./wgsl/common.wgsl', import.meta.url);
const KDIR = new URL('./wgsl/', import.meta.url);
const SLOT = 256;
const RING = 4 << 20;                                  // 16384 dispatches per submit
const UNI = { float: ['f32', 4, 4], int: ['i32', 4, 4], vec2: ['vec2<f32>', 8, 8], vec3: ['vec3<f32>', 16, 12],
    vec4: ['vec4<f32>', 16, 16], ivec2: ['vec2<i32>', 8, 8], ivec3: ['vec3<i32>', 16, 12], ivec4: ['vec4<i32>', 16, 16] };
const IMG = { r32f: ['f32', 1], rg32f: ['vec2<f32>', 2], rgba32f: ['vec4<f32>', 4], r32ui: ['u32', 1] };

export function parseSpec(text, name) {
    const samplers = [], images = {}, uniforms = [];
    for (const line of text.split('\n')) {
        const m = /^\s*\/\/!\s*(\w+)\s*(.*?)\s*$/.exec(line);
        if (!m) continue;
        const t = m[2].split(/\s+/).map((s) => s.replace(/;$/, ''));
        if (m[1] === 'sampler') samplers.push(t[0]);
        else if (m[1] === 'image') images[t[0]] = /^(r|rg|rgba)\d+(f|ui)$/i.test(t[1] ?? '') ? t[1].toLowerCase() : 'rgba32f';
        else if (m[1] === 'uniform') {
            if (!UNI[t[0]]) throw new Error(`${name}: uniform type ${t[0]}`);
            uniforms.push([t[1], t[0]]);
        } else if (m[1] !== 'local') throw new Error(`${name}: cannot read ${line.trim()}`);
    }
    return { name, samplers, images, uniforms };
}

function layout(spec) {
    // WGSL uniform-struct layout: each member at its alignment; the samplers' and images' sizes appended as ivec2
    const members = [...spec.uniforms, ...spec.samplers.map((s) => [`_n_${s}`, 'ivec2']),
        ...Object.keys(spec.images).map((s) => [`_n_${s}`, 'ivec2'])];
    let off = 0;
    const out = [];
    for (const [n, ty] of members) {
        const [, align, size] = UNI[ty];
        off = Math.ceil(off / align) * align;
        out.push({ n, ty, off });
        off += size;
    }
    return { members: out, size: Math.ceil(Math.max(off, 16) / 16) * 16 };
}

export class Field {
    constructor(runner, h, w, channels, buffer, kind = 'f32') {
        Object.assign(this, { runner, h, w, channels, buffer, kind });
    }
    get bytes() { return this.h * this.w * this.channels * 4; }
}

export class Runner {
    constructor(device) {
        this.device = device;
        this.ring = device.createBuffer({ size: RING, usage: GPUBufferUsage.UNIFORM | GPUBufferUsage.COPY_DST });
        this.stage = new ArrayBuffer(RING);
        this.f32 = new Float32Array(this.stage);
        this.i32 = new Int32Array(this.stage);
        this.common = Deno.readTextFileSync(COMMON);
        this.kernels = new Map();
        this.bindGroups = new Map();
        this.ids = new WeakMap();
        this.nextId = 1;
        this.dispatches = 0;
        this._begin();
    }

    _id(o) { if (!this.ids.has(o)) this.ids.set(o, this.nextId++); return this.ids.get(o); }

    field(h, w, channels = 4, data = null, kind = 'f32') {
        const buffer = this.device.createBuffer({ size: Math.max(h * w * channels * 4, 16),
            usage: GPUBufferUsage.STORAGE | GPUBufferUsage.COPY_SRC | GPUBufferUsage.COPY_DST });
        const f = new Field(this, h, w, channels, buffer, kind);
        if (data) this.device.queue.writeBuffer(buffer, 0, data);
        return f;
    }

    kernel(name, sourceText = null) {
        const text = sourceText ?? Deno.readTextFileSync(new URL(`${name}.wgsl`, KDIR));
        return { name, text, spec: parseSpec(text, name) };
    }

    _compiled(k, chans) {
        const key = k.name + '|' + chans.join(',');
        let c = this.kernels.get(key);
        if (c) return c;
        const lay = layout(k.spec);
        const elem = (ch) => (ch === 1 ? 'f32' : ch === 2 ? 'vec2<f32>' : 'vec4<f32>');
        const widen = (ch, e) => (ch === 1 ? `vec4<f32>(${e}, 0.0, 0.0, 1.0)` : ch === 2 ? `vec4<f32>(${e}, 0.0, 1.0)` : e);
        let src = 'struct Uniforms {\n' + lay.members.map((m) => `  ${m.n}: ${UNI[m.ty][0]},`).join('\n') + '\n}\n';
        src += '@group(0) @binding(0) var<uniform> u: Uniforms;\n';
        let b = 1;
        k.spec.samplers.forEach((s, i) => {
            src += `@group(0) @binding(${b++}) var<storage, read> ${s}_b: array<${elem(chans[i])}>;\n`;
            src += `fn ${s}_size() -> vec2<i32> { return u._n_${s}; }\n`;
            src += `fn ${s}_at(q: vec2<i32>) -> vec4<f32> { return ${widen(chans[i], `${s}_b[q.y * u._n_${s}.x + q.x]`)}; }\n`;
        });
        for (const [im, fmt] of Object.entries(k.spec.images)) {
            const [ty, ch] = IMG[fmt];
            src += `@group(0) @binding(${b++}) var<storage, read_write> ${im}_b: array<${ty}>;\n`;
            src += `fn ${im}_size() -> vec2<i32> { return u._n_${im}; }\n`;
            const v = fmt === 'r32ui' ? 'v' : ch === 1 ? 'v.x' : ch === 2 ? 'v.xy' : 'v';
            src += `fn ${im}_store(q: vec2<i32>, v: ${fmt === 'r32ui' ? 'u32' : 'vec4<f32>'}) { ${im}_b[q.y * u._n_${im}.x + q.x] = ${v}; }\n`;
        }
        src += this.common + '\n' + k.text + '\n';
        src += '@compute @workgroup_size(16, 16)\nfn main(@builtin(global_invocation_id) gid: vec3<u32>) { kmain(vec2<i32>(gid.xy)); }\n';
        const d = this.device;
        const entries = [{ binding: 0, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'uniform', hasDynamicOffset: true, minBindingSize: lay.size } }];
        let bb = 1;
        for (const _ of k.spec.samplers) entries.push({ binding: bb++, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'read-only-storage' } });
        for (const _ of Object.keys(k.spec.images)) entries.push({ binding: bb++, visibility: GPUShaderStage.COMPUTE, buffer: { type: 'storage' } });
        const bgl = d.createBindGroupLayout({ entries });
        d.pushErrorScope('validation');
        const module = d.createShaderModule({ code: src, label: k.name });
        const pipeline = d.createComputePipeline({ layout: d.createPipelineLayout({ bindGroupLayouts: [bgl] }),
            compute: { module, entryPoint: 'main' }, label: k.name });
        c = { bgl, pipeline, lay, src, err: d.popErrorScope() };
        this.kernels.set(key, c);
        return c;
    }

    async check(k, chans) {
        const c = this._compiled(k, chans);
        const e = await c.err;
        if (e) throw new Error(`kernel ${k.name} failed: ${e.message}\n${c.src.split('\n').map((l, i) => `${i + 1}: ${l}`).join('\n')}`);
    }

    _begin() {
        this.enc = this.device.createCommandEncoder();
        this.pass = null;
        this.slot = 0;
    }

    run(k, samplers, images, uniforms) {
        const chans = k.spec.samplers.map((s) => { if (!samplers[s]) throw new Error(`${k.name}: sampler ${s} not given`); return samplers[s].channels; });
        for (const im of Object.keys(k.spec.images)) if (!images[im]) throw new Error(`${k.name}: image ${im} not given`);
        for (const [n] of k.spec.uniforms) if (!(n in uniforms)) throw new Error(`${k.name}: uniform ${n} not given`);
        for (const s of Object.values(samplers)) for (const o of Object.values(images)) {
            if (s === o) throw new Error(`${k.name}: a field bound as sampler and image in one dispatch; ping-pong`);
        }
        const c = this._compiled(k, chans);
        if (this.slot * SLOT >= RING) this.flush();
        const base = (this.slot * SLOT) / 4;
        for (const m of c.lay.members) {
            const o = base + m.off / 4;
            let v;
            if (m.n.startsWith('_n_')) {
                const f = samplers[m.n.slice(3)] ?? images[m.n.slice(3)];
                v = [f.w, f.h];
            } else v = uniforms[m.n];
            const isInt = m.ty === 'int' || m.ty.startsWith('ivec');
            const arr = Array.isArray(v) ? v : [v];
            for (let i = 0; i < arr.length; i++) (isInt ? this.i32 : this.f32)[o + i] = arr[i];
        }
        const fields = [...k.spec.samplers.map((s) => samplers[s]), ...Object.keys(k.spec.images).map((i) => images[i])];
        const key = k.name + '|' + chans.join(',') + '|' + fields.map((f) => this._id(f)).join(',');
        let bg = this.bindGroups.get(key);
        if (!bg) {
            bg = this.device.createBindGroup({ layout: c.bgl, entries: [{ binding: 0, resource: { buffer: this.ring, size: c.lay.size } },
                ...fields.map((f, i) => ({ binding: i + 1, resource: { buffer: f.buffer } }))] });
            this.bindGroups.set(key, bg);
        }
        if (!this.pass) this.pass = this.enc.beginComputePass();
        this.pass.setPipeline(c.pipeline);
        this.pass.setBindGroup(0, bg, [this.slot * SLOT]);
        const out = images[Object.keys(k.spec.images)[0]];
        this.pass.dispatchWorkgroups(Math.ceil(out.w / 16), Math.ceil(out.h / 16), 1);
        this.slot++;
        this.dispatches++;
    }

    flush() {
        if (this.pass) this.pass.end();
        if (this.slot) this.device.queue.writeBuffer(this.ring, 0, this.stage, 0, this.slot * SLOT);
        this.device.queue.submit([this.enc.finish()]);
        this._begin();
    }

    async read(f) {
        this.flush();
        const rb = this.device.createBuffer({ size: f.bytes, usage: GPUBufferUsage.COPY_DST | GPUBufferUsage.MAP_READ });
        this.enc.copyBufferToBuffer(f.buffer, 0, rb, 0, f.bytes);
        this.flush();
        await rb.mapAsync(GPUMapMode.READ);
        const out = f.kind === 'u32' ? new Uint32Array(rb.getMappedRange().slice(0)) : new Float32Array(rb.getMappedRange().slice(0));
        rb.unmap();
        rb.destroy();
        return out;
    }

    async idle() { this.flush(); await this.device.queue.onSubmittedWorkDone(); }
}
