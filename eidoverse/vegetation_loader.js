// Eval-injected shim for the vegetation brush. The HELPER_MODULES loop
// (0,eval)()s plain scripts, so the ES-module vegetation.js can't sit in the
// list directly — this loader dynamic-imports it (legal in eval'd code) and
// installs the globals. createFlora is already async at every call site, so
// the readiness await hides inside the wrapper; by first use the real
// functions have replaced it.
globalThis.__vegetationReady = import(
    'file:///' + Deno.cwd().replace(/\\/g, '/') + '/eidoverse/vegetation.js'
).then((m) => {
    globalThis.createFlora = m.createFlora;
    globalThis.FLORA_SPECIES = m.FLORA_SPECIES;
    globalThis.GRASS_COLORS = m.GRASS_COLORS;
    globalThis.resetFloraOccupancy = m.resetFloraOccupancy;
    return m;
}).catch((e) => {
    console.warn('[vegetation] module load failed:', e.message);
    return null;
});
globalThis.createFlora = async function (opts) {
    const m = await globalThis.__vegetationReady;
    if (!m) throw new Error('[vegetation] module failed to load — see startup log');
    return m.createFlora(opts);
};
globalThis.resetFloraOccupancy = function () {
    globalThis.__vegetationReady.then((m) => m && m.resetFloraOccupancy());
};
