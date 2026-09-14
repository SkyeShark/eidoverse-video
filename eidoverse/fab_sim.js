// MIT. G430 CNC/FDM simulation facade. All creation methods are asynchronous.
(function (g) {
  let module;
  const ready = () =>
    module ??= import(new URL("robotics/fabrication.js", g.EIDOVERSE_DIR).href);
  g.FabSim = {
    ready,
    print: async (...a) => (await ready()).print(...a),
    carve: async (...a) => (await ready()).carve(...a),
    mill: async (...a) => (await ready()).mill(...a),
    rotaryCarve: async (...a) => (await ready()).rotaryCarve(...a),
    rotaryProgram: async (...a) => (await ready()).rotaryProgram(...a),
    rotaryMeshProgram: async (...a) => (await ready()).rotaryMeshProgram(...a),
    sourceGeometry: async (...a) => (await ready()).sourceGeometry(...a),
    fitSourceGeometry: async (...a) => (await ready()).fitSourceGeometry(...a),
    sampleRotary: async () => (await ready()).sampleRotary,
    pocketProgram: async (...a) => (await ready()).pocketProgram(...a),
    reliefProgram: async (...a) => (await ready()).reliefProgram(...a),
    reliefFromMesh: async (...a) => (await ready()).reliefFromMesh(...a),
    sampleRelief: async () => (await ready()).sampleRelief,
    stockMaterials: async () => (await ready()).stockMaterials,
  };
  g.PrintSim = { print: (...a) => g.FabSim.print(...a) };
  g.CNCSim = {
    carve: (...a) => g.FabSim.carve(...a),
    mill: (...a) => g.FabSim.mill(...a),
    rotaryCarve: (...a) => g.FabSim.rotaryCarve(...a),
  };
})(globalThis);
