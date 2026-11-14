// Design probe (PORT_PLAN.md C9 and 10.1), the Deno half: Deno's CompressionStream('deflate') of zlib_payload.py's
// payload against every Python zlib's output in <dir> (payload.zlib_<version>.z6), and DecompressionStream on each
// of those (does it give the payload back exactly?). No GPU.
//     deno run --no-config --no-lock --allow-read deflate_vs_zlib.mjs <dir>
const dir = Deno.args[0];
const raw = Deno.readFileSync(`${dir}/payload.bin`);
const pipe = async (bytes, stream) => new Uint8Array(await new Response(new Blob([bytes]).stream().pipeThrough(stream)).arrayBuffer());
const eq = (a, b) => a.length === b.length && a.every((v, i) => v === b[i]);
const deno = await pipe(raw, new CompressionStream('deflate'));
const out = { deno: Deno.version.deno, payload_bytes: raw.length, deno_compressed_bytes: deno.length, against: {} };
for (const e of Deno.readDirSync(dir)) {
    const m = e.name.match(/^payload\.zlib_(.+)\.z6$/);
    if (!m) continue;
    const z = Deno.readFileSync(`${dir}/${e.name}`);
    out.against[m[1]] = { compressed_bytes: z.length, deno_output_identical: eq(deno, z),
        decompression_stream_gives_payload: eq(await pipe(z, new DecompressionStream('deflate')), raw) };
}
console.log(JSON.stringify(out, null, 1));
