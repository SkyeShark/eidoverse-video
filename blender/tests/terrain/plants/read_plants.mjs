// read_plants.mjs: a plain reader of the terrain's plant spots (format eidoverse-terrain-plants/1), the way a
// three.js placer reads them: the JSON description, then each species' records as a Float32Array.
//
//   node read_plants.mjs <base>.plants.json <summary.json> [<echo folder>]
//
// readPlants(jsonPath) -> { meta, species: [{ name, kind, source, size_m, count, stride, fields, records, at(i) }] }
//   records   Float32Array, `stride` numbers per spot in the order of `fields`
//   at(i)     one spot as an object by field name, plus what a three.js instance takes:
//             position [x, z, -y] (three is y-up), rotationY = yaw, height = scale * size_m[1] (metres)
// The command writes a summary (count, per-field sum / min / max, the first spot as three takes it) for
// test_plants.py to compare with numpy, and with an echo folder writes each species' records back out.
import fs from 'node:fs';
import path from 'node:path';

export function readPlants(jsonPath) {
    const meta = JSON.parse(fs.readFileSync(jsonPath, 'utf8'));
    if (meta.format !== 'eidoverse-terrain-plants/1') throw new Error(`unknown format ${meta.format}`);
    const dir = path.dirname(jsonPath);
    const species = meta.species.map((s) => {
        const buf = fs.readFileSync(path.join(dir, s.file));
        // headerless little-endian float32; copy so the view is aligned whatever the file buffer's offset
        const records = new Float32Array(buf.buffer.slice(buf.byteOffset, buf.byteOffset + buf.byteLength));
        const stride = s.fields.length;
        if (records.length !== s.count * stride) throw new Error(`${s.file}: ${records.length} numbers, expected ${s.count} x ${stride}`);
        const col = Object.fromEntries(s.fields.map((f, k) => [f, k]));
        const at = (i) => {
            const o = {};
            for (const f of s.fields) o[f] = records[i * stride + col[f]];
            o.position = [o.x, o.z, -o.y];
            o.rotationY = o.yaw;
            o.height = o.scale * s.size_m[1];
            o.seed = s.source.seeds[o.variant];
            return o;
        };
        return { ...s, stride, records, at };
    });
    return { meta, species };
}

const [jsonPath, outPath, echoDir] = process.argv.slice(2);
if (jsonPath && outPath) {
    const { meta, species } = readPlants(jsonPath);
    const summary = { format: meta.format, ecotope: meta.ecotope, focus: meta.focus, species: [] };
    for (const s of species) {
        const sum = {}, min = {}, max = {};
        s.fields.forEach((f, k) => {
            let a = 0, lo = Infinity, hi = -Infinity;
            for (let i = k; i < s.records.length; i += s.stride) {
                const v = s.records[i];
                a += v; if (v < lo) lo = v; if (v > hi) hi = v;
            }
            sum[f] = a; min[f] = s.count ? lo : null; max[f] = s.count ? hi : null;
        });
        const first = s.count ? s.at(0) : null;
        summary.species.push({ name: s.name, kind: s.kind, file: s.file, count: s.count, stride: s.stride, sum, min, max,
            first_three: first ? first.position : null, first_three_yaw: first ? first.rotationY : null,
            first_height: first ? first.height : null, first_seed: first ? first.seed : null });
        if (echoDir) {
            fs.mkdirSync(echoDir, { recursive: true });
            fs.writeFileSync(path.join(echoDir, s.file), Buffer.from(s.records.buffer, s.records.byteOffset, s.records.byteLength));
        }
    }
    fs.writeFileSync(outPath, JSON.stringify(summary));
    console.log('[read_plants]', species.map((s) => `${s.name} ${s.count}`).join(', '));
}
