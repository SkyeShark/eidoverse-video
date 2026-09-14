// MIT. The inspector uses the same NodeMaterial runtime as native rendering.

import * as T from "three/webgpu";

import { OrbitControls } from "three/addons/controls/OrbitControls.js";

import { assetRoot, catalog, loadRobot } from "../index.js";

import { frameCamera, studio } from "../studio.js";

import * as fab from "../fabrication.js";
import {manufacturingSample} from '../manufacturing_samples.js';
import {STLLoader} from 'three/addons/loaders/STLLoader.js';
import {GLTFLoader} from 'three/addons/loaders/GLTFLoader.js';

const $ = (id) => document.getElementById(id),
  renderer = new T.WebGPURenderer({ canvas: $("canvas"), antialias: true });
await renderer.init();
renderer.setPixelRatio(Math.min(devicePixelRatio, 2));
renderer.toneMapping = T.ACESFilmicToneMapping;

const scene = studio(renderer),
  camera = new T.PerspectiveCamera(35, 1, .001, 40),
  controls = new OrbitControls(camera, $("canvas"));
controls.enableDamping = true;

let robot = null,
  job = null,
  playing = false,
  time = 0,
  last = null,
  selection = "",
  wires = [],
  references = [],
  generation = 0,
  loading = false,
  manual = false;
let inputMesh=null,inputName='';
function releaseSource(){
  if(inputMesh?.isBufferGeometry)inputMesh.dispose();
  else inputMesh?.traverse(o=>{if(o.isMesh){o.geometry.dispose();for(const m of (Array.isArray(o.material)?o.material:[o.material])){for(const v of Object.values(m))if(v?.isTexture)v.dispose();m.dispose();}}});
  inputMesh=null;
}

const entries = await catalog();
for (const [id, r] of Object.entries(entries.models)) {
  if (id.startsWith("rotors_")) continue;
  const o = new Option(r.label, id);
  $("asset").append(o);
}

function error(e) {
  $("error").textContent = e?.stack ?? String(e);
  console.error(e);
  playing = false;
  $("play").textContent = "Play";
}

function resize() {
  const rect = $("viewport").getBoundingClientRect();
  renderer.setSize(Math.max(1, rect.width), Math.max(1, rect.height), false);
  camera.aspect = rect.width / rect.height;
  camera.updateProjectionMatrix();
}
new ResizeObserver(resize).observe($("viewport"));

function fit() {
  const box = new T.Box3(), clip = $("clip").value;
  const expand = () => {
    robot.group.updateMatrixWorld(true);
    robot.group.traverseVisible((o) => {
      if (!o.isMesh || o.userData.overlay) return;
      if (!o.geometry.boundingBox) o.geometry.computeBoundingBox();
      box.union(o.geometry.boundingBox.clone().applyMatrix4(o.matrixWorld));
    });
  };
  if (
    !manual && !job &&
    (["walk", "drive-circle", "flight"].includes(clip) ||
      clip.startsWith("run-"))
  ) {
    for (let t = 0; t <= 20; t += .5) {
      robot.sample(clip, t);
      robot.group.updateMatrixWorld(true);
      expand();
    }
    sample();
  } else expand();
  controls.target.copy(
    frameCamera(camera, [box], {
      margin: 1.08,
      direction: robot.filament ? [-.9, .55, 1.5] : [.9, .55, 1.5],
    }),
  );
  controls.update();
}
function scan() {
  const meshes = [];
  robot.model.traverse((o) => {
    if (o.isMesh && o.userData.eidoverseRobotics && !o.userData.overlay) {
      meshes.push(o);
    }
  });
  return meshes;
}

function buildWire() {
  for (const w of wires) {
    w.removeFromParent();
    w.geometry.dispose();
    w.material.dispose();
  }
  wires = [];
  for (const o of scan()) {
    const wire = new T.LineSegments(
      new T.WireframeGeometry(o.geometry),
      new T.LineBasicNodeMaterial({
        color: 0x132e37,
        transparent: true,
        opacity: .65,
      }),
    );
    if (o.userData.proceduralCurve) {
      wire.material.positionNode = o.material.positionNode;
    }
    wire.userData.overlay = true;
    wire.visible = $("wire").checked;
    wire.renderOrder = 2;
    o.add(wire);
    wires.push(wire);
  }
}

function updateStats() {
  const s = robot.stats();
  $("status").textContent =
    `${s.triangles.toLocaleString()} triangles · ${s.meshes} meshes · ${s.materials} material bindings · ${s.textures} shared maps`;

  let selected = 0;
  for (const o of scan()) {
    for (const name of o.userData.partForFace ?? []) {
      if (name === selection) selected++;
    }
  }
  $("partStats").textContent = selection
    ? `${selected.toLocaleString()} selected triangles`
    : "";
}

async function drawUV() {
  if (!$("split").checked) return;
  const ctx = $("uv").getContext("2d"), size = $("uv").width;
  let width = size, height = size, left = 0, top = 0;
  const showMap = (im) => {
    const aspect = (im.naturalWidth ?? im.width) /
      (im.naturalHeight ?? im.height);
    width = aspect < 1 ? size * aspect : size;
    height = aspect > 1 ? size / aspect : size;
    left = (size - width) / 2;
    top = (size - height) / 2;
    ctx.drawImage(im, left, top, width, height);
  };
  ctx.fillStyle = "#111a1e";
  ctx.fillRect(0, 0, size, size);

  const [batch, channel] = $("map").value.split("|"),
    binding = robot.report.texture_bindings?.[batch]?.[channel],
    selectedMaterial = batch?.startsWith("@")
      ? robot.materials.materials[Number(batch.slice(1))]
      : null;

  if (selectedMaterial) {
    const tex = selectedMaterial[channel] ?? selectedMaterial.userData[channel],
      im = tex?.image;
    if (im) {
      showMap(im);
      $("mapStats").textContent =
        `${im.width} × ${im.height} · ${selectedMaterial.name} / ${channel}`;
    }
  } else if (binding) {
    const uri = typeof binding === "string" ? binding : binding.uri,
      im = new Image();
    im.src = new URL(uri, new URL(robot.entry.metadata, assetRoot));
    await im.decode();
    showMap(im);
    $("mapStats").textContent =
      `${im.naturalWidth} × ${im.naturalHeight} · ${batch} / ${channel}`;
  } else {$("mapStats").textContent =
      "UV geometry (maps are shared with the source modules)";}

  let count = 0;
  ctx.strokeStyle = "#f180a1";
  ctx.lineWidth = .55;

  for (const o of scan()) {
    if (
      selectedMaterial
        ? o.material !== selectedMaterial
        : (batch && o.userData.batch !== batch)
    ) continue;
    const g = o.geometry, uv = g.attributes.uv;
    if (!uv) continue;
    const faces = o.userData.partForFace ?? [],
      n = (g.index?.count ?? g.attributes.position.count) / 3;

    for (let i = 0; i < n; i++) {
      if (selection && faces[i] !== selection) continue;
      ctx.beginPath();
      for (let j = 0; j < 3; j++) {
        const k = g.index ? g.index.getX(i * 3 + j) : i * 3 + j,
          u = uv.getX(k),
          v = uv.getY(k);
        if (j === 0) ctx.moveTo(left + u * width, top + v * height);
        else ctx.lineTo(left + u * width, top + v * height);
      }
      ctx.closePath();
      ctx.stroke();
      count++;
    }
  }
  ctx.strokeStyle = "#a3c6c6";
  ctx.strokeRect(left, top, width, height);
  $("mapStats").textContent += ` · ${count.toLocaleString()} triangles shown`;
}

function pickPart(name) {
  selection = name;
  $("part").value = name;
  updateStats();
  drawUV().catch(error);
}

async function load(id) {
  const token = ++generation;
  loading = true;
  playing = false;
  $("play").textContent = "Play";
  $("error").textContent = "";
  $("status").textContent = "Loading shared assets…";

  try {
    const next = await loadRobot(id);
    if (token !== generation) {
      next.dispose();
      return;
    }
    if (job) {
      job.dispose();
      job = null;
    }
    robot?.dispose();
    robot = next;
    scene.add(robot.group);
    time = 0;
    manual = false;
    $("time").value = 0;
    $("clip").replaceChildren(...robot.clips.map((c) => new Option(c, c)));

    if (robot.machine?.tool) {
      $("clip").prepend(
        new Option(
          robot.machine.tool === "extruder_fixed"
            ? "FDM process"
            : "CNC process",
          "process",
        ),
      );
    }

    $("clip").value = robot.machine?.tool ? "process" : robot.clips[0];

    const p = new Set();
    scan().forEach((o) =>
      (o.userData.part_ids ?? [o.userData.part_id]).forEach((n) => {
        if (n) p.add(n);
      })
    );
    $("part").replaceChildren(
      new Option("All parts", ""),
      ...[...p].sort().map((n) => new Option(n, n)),
    );
    selection = "";

    $("map").replaceChildren();
    for (
      const [batch, b] of Object.entries(robot.report.texture_bindings ?? {})
    ) {
      for (const channel of Object.keys(b)) {
        $("map").append(
          new Option(batch + " / " + channel, batch + "|" + channel),
        );
      }
    }

    if (!$("map").options.length) {
      for (const [i, m] of robot.materials.materials.entries()) {
        for (
          const channel of ["map", "normalMap", "aoMap", "fixedMap", "maskMap"]
        ) {
          if (m[channel] ?? m.userData[channel]) {
            $("map").append(
              new Option(m.name + " / " + channel, "@" + i + "|" + channel),
            );
          }
        }
      }
    }
    if (!$("map").options.length) $("map").append(new Option("All UVs", ""));

    const palette = robot.materials.palette;
    $("primary").value = "#" + palette.primary.value.getHexString();
    $("accent").value = "#" + palette.accent.value.getHexString();

    $("filamentControls").hidden = !robot.filament &&
      robot.machine?.tool !== "extruder_fixed";
    $("filamentColor").value = "#" +
      robot.materials.palette.filament.value.getHexString();
    $("stockControls").hidden = robot.machine?.tool !== "spindle_fixed";
    $("rotaryStockControls").hidden = !robot.rotarySetup || !robot.machine;
    if (robot.roots.rotary_chuck) $("stockMaterial").value = "wood";
    $("processControls").hidden = !robot.machine?.tool;
    $("joints").replaceChildren();
    for (const [n, s] of Object.entries(robot.specs)) {
      const rotaryAxis = robot.report.rotary_fixture && n === "rotary_output";
      if (
        !rotaryAxis &&
        (!["revolute", "prismatic"].includes(s.joint_type) || !s.limits)
      ) {
        continue;
      }
      const label = document.createElement("label");
      label.textContent = rotaryAxis ? "A axis / chuck" : n;
      const input = document.createElement("input");
      input.type = "range";
      [input.min, input.max] = rotaryAxis ? [-Math.PI, Math.PI] : s.limits;
      input.value = robot.state[n] ?? 0;
      input.step = s.joint_type === "prismatic" ? .0001 : .001;
      input.oninput = () => {
        playing = false;
        manual = true;
        try {
          robot.setJoints({ [n]: Number(input.value) });
        } catch (e) {
          error(e);
        }
      };
      label.append(input);
      $("joints").append(label);
    }

    $("ports").textContent = Object.entries(robot.ports).map(([n, p]) =>
      n + " · " + p.interface
    ).join("\n") || "No declared interface on this individual library part.";

    references = robot.graspReference();
    references.forEach((o) =>
      o.visible = $("reference").checked
    );
    buildWire();
    await chooseClip();
    fit();
    updateStats();
    await drawUV();

    window.robot = robot;
    window.roboticsInspector = {
      robot,
      renderer,
      scene,
      camera,
      controls,
      get job() {
        return job;
      },
      setTime(t) {
        time = t;
        sample();
      },
      setMotion(c) {
        $("clip").value = c;
        return chooseClip();
      },
      setSource(source,name='Supplied mesh') { releaseSource();inputMesh=source;inputName=name;$('clip').value='process';return chooseClip(); },
      ready: true,
    };
  } catch (e) {
    error(e);
  } finally {
    if (token === generation) loading = false;
  }
}

async function chooseClip() {
  job?.dispose();
  job = null;
  time = 0;
  manual = false;
  $('error').textContent='';

  const timeLapse = robot.roots.rotary_chuck ? 32 : 18;
  $("processTiming").options[0].textContent =
    `Time lapse (${timeLapse} seconds)`;
  const duration = $("processTiming").value === "physical"
    ? undefined
    : timeLapse;
  if ($("clip").value === "process") {
    if (robot.machine.tool === "extruder_fixed") {
      const g = new T.LatheGeometry(
        [[.014, 0], [.020, 0], [.020, .006], [.014, .006], [.014, 0]].map((p) =>
          new T.Vector2(...p)
        ),
        48,
      );
      job = fab.print(robot, inputMesh??g, {
        size: .04,
        infill: .25,
        duration,
        color: $("filamentColor").value,
      });
      g.dispose();
    } else if (robot.roots.rotary_chuck) {
      job = fab.rotaryCarve(robot, inputMesh??fab.sampleRotary, {
        renderer,
        duration,
        material: $("stockMaterial").value,
        stockLength: Number($("stockLength").value) / 1000,
        stockWidth: Number($("stockWidth").value) / 1000,
        stockHeight: Number($("stockHeight").value) / 1000,
      });
    } else if (robot.machine.cutter?.kind === "ball") {
      const fitted=inputMesh?fab.fitSourceGeometry(inputMesh,{bounds:new T.Box3(new T.Vector3(-.032,.004,-.055),new T.Vector3(.032,.019,.055))}):null;
      try{job = fab.carve(robot, fitted??fab.sampleRelief, {
        duration,
        material: $("stockMaterial").value,
        resolution: 192,
      });}finally{fitted?.dispose()}
    } else {
      if(inputMesh)throw Error('Choose the CNC relief or rotary machine to carve a supplied mesh.');
      job = fab.mill(robot, null, {
        duration,
        material: $("stockMaterial").value,
      });}
  }

  const report=job?.program?.report;
  $('sourceInfo').textContent=inputMesh?
    `${inputName}. ${report?`${report.source.triangles.toLocaleString()} source triangles; ${report.orientations} indexed views. ${report.reachLimitedSamples?'Some regions exceed tool reach and retain material. ':''}Undercuts and holding ends may remain.`:robot.machine?.tool==='extruder_fixed'?'Closed solids are sliced with 25% infill. Supports are not generated automatically.':'Upper surface relief; vertical undercuts remain.'}`:
    'Load a model or choose a mesh example to generate its actual toolpath.';

  $("time").max = job?.duration ?? 20;
  $("frameWork").hidden = !job;
  sample();
  fit();
}

function sample() {
  if (!robot || manual) return;
  if (job) job.seek(time);
  else robot.sample($("clip").value, time);
  $("time").value = time;
  $("timeLabel").value = time.toFixed(2) + " s";
  $("processState").textContent = !job
    ? ""
    : job.state.filamentLength !== undefined
    ? `${job.state.type} | ${
      (job.state.filamentLength * 1000).toFixed(1)
    } mm fed | ${(job.state.filamentRetraction * 1000).toFixed(2)} mm retracted`
    : `${job.settings.material} | ${job.settings.rpm.toLocaleString()} rpm | ${
      job.state.stage ?? job.state.type
    }${
      job.state.angle === undefined
        ? ""
        : ` | A ${(job.state.angle * 180 / Math.PI).toFixed(1)}°`
    } | ${(job.state.speed * 60000).toFixed(0)} mm/min`;
}

$("asset").onchange = () => load($("asset").value);
$('sourceSample').onchange=()=>{
 releaseSource();if($('sourceSample').value!=='default'){inputMesh=manufacturingSample($('sourceSample').value);inputName=$('sourceSample').selectedOptions[0].text;}
 $('sourceFile').value='';$('clip').value='process';chooseClip().catch(error);
};
$('sourceFile').onchange=async()=>{
 try{
  const file=$('sourceFile').files[0];if(!file)return;
  if(file.size>64*1024*1024)throw Error('Use a source file under 64 MB for this inspector');
  const data=await file.arrayBuffer();let source;
  if(/\.stl$/i.test(file.name))source=new STLLoader().parse(data);
  else if(/\.glb$/i.test(file.name)){
    const manager=new T.LoadingManager();manager.setURLModifier(url=>{if(!url.startsWith('blob:')&&!url.startsWith('data:'))throw Error('Use an embedded GLB; external resources are not loaded');return url;});
    source=(await new GLTFLoader(manager).parseAsync(data,'')).scene;
  }else throw Error('Choose an STL or embedded GLB');
  releaseSource();inputMesh=source;inputName=file.name;$('sourceSample').value='default';$('clip').value='process';await chooseClip();
 }catch(e){error(e)}
};
$("clip").onchange = () => chooseClip().catch(error);
$("play").onclick = () => {
  playing = !playing;
  manual = false;
  last = null;
  $("play").textContent = playing ? "Pause" : "Play";
};
$("reset").onclick = () => {
  time = 0;
  manual = false;
  sample();
};
$("frame").onclick = fit;
$("frameWork").onclick = () => {
  if (job) {
    controls.target.copy(
      frameCamera(camera, [job.mesh], {
        direction: job.state.filamentLength !== undefined
          ? [-.7, .34, 1.3]
          : [.8, 1.1, .5],
        margin: job.state.filamentLength !== undefined ? 1.55 : 1.2,
      }),
    );
    controls.update();
  }
};

$("time").oninput = () => {
  playing = false;
  manual = false;
  time = Number($("time").value);
  try {
    sample();
  } catch (e) {
    error(e);
  }
};

$("filamentColor").oninput = () => {
  if (job?.state.filamentLength !== undefined) {
    job.setColor($("filamentColor").value);
  } else robot.filament?.setColor($("filamentColor").value);
};
$("stockMaterial").onchange = () => chooseClip().catch(error);
$("stockPreset").onchange = () => {
  $("stockPreset").value.split(",").forEach((v, i) => {
    $(["stockLength", "stockWidth", "stockHeight"][i]).value = v;
  });
};
$("applyStock").onclick = () => {
  $("clip").value = "process";
  chooseClip().catch(error);
};
$("processTiming").onchange = () => chooseClip().catch(error);
for (const id of ["primary", "accent"]) {
  $(id).oninput = () => robot.setColors($("primary").value, $("accent").value);
}

$("wire").onchange = () => wires.forEach((w) => w.visible = $("wire").checked);
$("split").onchange = () => {
  $("workspace").classList.toggle("split", $("split").checked);
  drawUV().catch(error);
  requestAnimationFrame(() => {
    resize();
    fit();
  });
};
$("part").onchange = () => pickPart($("part").value);
$("map").onchange = () => drawUV().catch(error);
$("reference").onchange = () =>
  references.forEach((o) => o.visible = $("reference").checked);

const ray = new T.Raycaster();
let down;
$("canvas").addEventListener(
  "pointerdown",
  (e) => down = [e.clientX, e.clientY],
);
$("canvas").addEventListener("pointerup", (e) => {
  if (
    !robot || !down || Math.hypot(e.clientX - down[0], e.clientY - down[1]) > 4
  ) return;
  const r = $("canvas").getBoundingClientRect();
  ray.setFromCamera(
    new T.Vector2(
      (e.clientX - r.left) / r.width * 2 - 1,
      1 - (e.clientY - r.top) / r.height * 2,
    ),
    camera,
  );
  const hit = ray.intersectObjects(scan(), false)[0];
  pickPart(hit?.object.userData.partForFace?.[hit.faceIndex] ?? "");
});

let rendering = false;
renderer.setAnimationLoop(async (ms) => {
  if (rendering) return;
  rendering = true;
  try {
    if (playing && !loading) {
      if (last !== null) {
        time = (time + (ms - last) / 1000) % (job?.duration ?? 20);
      }
      sample();
    }
    last = ms;
    controls.update();
    await renderer.renderAsync(scene, camera);
  } catch (e) {
    error(e);
    renderer.setAnimationLoop(null);
  } finally {
    rendering = false;
  }
});

$("asset").value = new URLSearchParams(location.search).get("model") ??
  "payloads/arm_hand";
await load($("asset").value);
resize();
