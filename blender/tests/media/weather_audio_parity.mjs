// weather_audio_parity.mjs — the engine's own recorder (eidoverse/weather_audio.js) over a synthetic storm, for
// test_weather_audio_parity.py. Reads <states.json>: [{ t, rainK, denseA, wind, strike, cam: [16 column-major],
// pos: [x, y, z] }], prints the recorder's timeline JSON.
const states = JSON.parse(await Deno.readTextFile(Deno.args[0]));
await import(new URL('../../../eidoverse/weather_audio.js', import.meta.url).href);
const weather = { uniforms: { rainK: { value: 0 }, denseA: { value: 1 }, windVec: { value: { length: () => 0 } } }, state: {} };
const camera = { matrixWorld: { elements: new Array(16).fill(0) }, position: { x: 0, y: 0, z: 0 } };
const rec = globalThis.makeWeatherAudio({ weather, camera, quiet: true });
for (const s of states) {
    weather.uniforms.rainK.value = s.rainK;
    weather.uniforms.denseA.value = s.denseA;
    weather.uniforms.windVec.value = { length: () => s.wind };
    weather.state.strike = s.strike;
    camera.matrixWorld.elements = s.cam;
    camera.position = { x: s.pos[0], y: s.pos[1], z: s.pos[2] };
    rec.update(s.t);
}
console.log(rec.toJSON());
