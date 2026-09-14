// MIT. Async facade for the shared, baked modular kit. Injected by render_scene.
(function (g) {
  let api;
  const ready = () =>
    api ??= import(
      new URL(
        "robotics/index.js",
        g.EIDOVERSE_DIR || new URL("./eidoverse/", location.href),
      ).href
    );
  g.RoboticsKit = {
    version: 1,
    ready,
    catalog: async () => (await ready()).catalog(),
    load: async (...a) => (await ready()).loadRobot(...a),
    loadPart: async (...a) => (await ready()).loadPart(...a),
    createPTFETube: async (...a) => (await ready()).createPTFETube(...a),
    connect: (parent, child, options) => parent.attach(child, options),
  };
  g.makeRobot = async (type, options = {}) => g.RoboticsKit.load(type, options);
  g.makeBot = async (options = {}) =>
    g.RoboticsKit.load(options.model ?? "humanoid", options);
})(globalThis);
