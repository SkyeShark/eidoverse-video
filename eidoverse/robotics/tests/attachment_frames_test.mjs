import * as T from 'three/webgpu';
import { catalog, loadRobot } from '../index.js';

function assert(value, message) { if (!value) throw Error(message); }
function near(value, expected, message, epsilon = 2e-6) {
  assert(Math.abs(value - expected) < epsilon, `${message}: ${value} != ${expected}`);
}
async function rejects(fn, message) {
  try { await fn(); } catch (error) { assert(error.message.includes(message), error.message); return; }
  throw Error(`Expected failure: ${message}`);
}

// Measure the outer, planar mating face from actual exported triangles,
// independently of the port position and normal being tested.
function physicalFace(robot, part, owner, axis, sign) {
  robot.group.updateWorldMatrix(true, true);
  const inverse = owner.matrixWorld.clone().invert(), faces = [];
  let extreme = -Infinity;
  for (const mesh of robot.part(part)) {
    const matrix = inverse.clone().multiply(mesh.matrixWorld);
    const geometry = mesh.geometry, position = geometry.attributes.position, index = geometry.index;
    for (let i = 0; i < (index?.count ?? position.count); i += 3) {
      if (mesh.userData.partForFace[i / 3] !== part) continue;
      const points = [0, 1, 2].map(k => new T.Vector3().fromBufferAttribute(position,
        index ? index.getX(i + k) : i + k).applyMatrix4(matrix));
      const normal = points[1].clone().sub(points[0]).cross(points[2].clone().sub(points[0]));
      if (normal.lengthSq() < 1e-20) continue;
      normal.normalize();
      if (normal.getComponent(axis) * sign < .99999) continue;
      const depth = points[0].getComponent(axis) * sign;
      extreme = Math.max(extreme, depth);
      faces.push({points, normal, depth});
    }
  }
  assert(Number.isFinite(extreme), `Missing physical face: ${part}`);
  const box = new T.Box3(), normal = new T.Vector3();
  for (const face of faces) if (Math.abs(face.depth - extreme) < 1e-7) {
    for (const point of face.points) box.expandByPoint(point);
    normal.add(face.normal);
  }
  return { point: box.getCenter(new T.Vector3()).applyMatrix4(owner.matrixWorld),
    normal: normal.normalize().transformDirection(owner.matrixWorld) };
}

function checkPhysicalPorts(arm, gripper, spec) {
  const a = arm.port(spec.port), b = gripper.port('parallel_gripper/input');
  const faceA = physicalFace(arm, spec.part, a.owner, spec.axis, spec.sign);
  const faceB = physicalFace(gripper, 'TC robot side', b.owner, 1, 1);
  for (const [port, face] of [[a, faceA], [b, faceB]]) {
    const m = port.owner.matrixWorld.clone().multiply(port.matrix);
    near(new T.Vector3().setFromMatrixPosition(m).distanceTo(face.point), 0, `${port.name} centre on geometry`);
    near(new T.Vector3(0, 0, 1).transformDirection(m).dot(face.normal), 1, `${port.name} direction matches geometry`);
  }
  near(faceA.point.distanceTo(faceB.point), 0, 'Physical flanges touch');
  near(faceA.normal.dot(faceB.normal), -1, 'Physical flange normals oppose');
  near(new T.Vector3(0, -1, 0).transformDirection(b.owner.matrixWorld).dot(faceA.normal), 1,
    'Gripper extends along the arm flange axis');
}

for (const spec of [
  {id:'arm',port:'a650_j6/output',part:'A650 TC70 output flange common flange',axis:0,sign:1,
    method:'joints',poses:[[0,0,0,0,0,0],[.2,.4,-.6,.25,.6,-.2],[-.4,.6,.3,-.2,.7,.5]]},
  {id:'scara',port:'s500_tool/output',part:'S500 tool mounting flange common flange',axis:1,sign:-1,
    method:'scaraJoints',poses:[[0,0,0,0],[.2,.8,.04,-.4],[-.4,.5,.08,.6]]},
]) Deno.test(`${spec.id} gripper seats on physical flanges throughout articulation`, async () => {
  const arm = await loadRobot(spec.id,{textures:false}), gripper = await loadRobot('gripper',{textures:false});
  try {
    arm.group.position.set(.4,1.2,-.8);arm.group.rotation.set(.1,.65,-.15);arm.group.scale.setScalar(1.7);
    arm.attach(gripper,{port:spec.port,childPort:'parallel_gripper/input'});
    for (const [i, pose] of spec.poses.entries()) {
      arm[spec.method](pose);gripper.jawGap(i % 2 ? .044 : 0);
      arm.group.updateMatrixWorld(true);
      checkPhysicalPorts(arm,gripper,spec);
    }
  } finally { arm.dispose(); if (!gripper.disposed) gripper.dispose(); }
});

Deno.test('intentional twist rotates about the flange axis without tilting or moving it', async () => {
  const arm=await loadRobot('arm',{textures:false}), gripper=await loadRobot('gripper',{textures:false});
  try {
    arm.joints([.2,.4,-.6,.25,.6,-.2]);
    arm.attach(gripper,{port:'a650_j6/output',childPort:'parallel_gripper/input',twist:Math.PI/2});
    arm.group.updateMatrixWorld(true);
    const a=arm.port('a650_j6/output'), b=gripper.port('parallel_gripper/input');
    const ma=a.owner.matrixWorld.clone().multiply(a.matrix),mb=b.owner.matrixWorld.clone().multiply(b.matrix);
    near(new T.Vector3(1,0,0).transformDirection(mb).dot(new T.Vector3(0,1,0).transformDirection(ma)),1,'quarter-turn clocking');
    checkPhysicalPorts(arm,gripper,{port:a.name,part:'A650 TC70 output flange common flange',axis:0,sign:1});
  } finally { arm.dispose();if(!gripper.disposed)gripper.dispose(); }
});

Deno.test('missing, zero and parallel authored axes are rejected instead of guessed', async () => {
  const cat=await catalog(),frame=cat.port_frames.a650_j6.output;
  const normal=frame.normal,tangent=frame.tangent;
  try {
    for (const invalid of [undefined,[0,0,0],[NaN,0,0]]) {
      frame.normal=invalid;
      await rejects(()=>loadRobot('arm',{textures:false}),'Invalid mount a650_j6/output');
    }
    frame.normal=normal;frame.tangent=normal;
    await rejects(()=>loadRobot('arm',{textures:false}),'tangent must not be parallel');
  } finally {frame.normal=normal;frame.tangent=tangent;}
});

Deno.test('invalid attachment transforms cannot reparent a child', async () => {
  const arm=await loadRobot('arm',{textures:false}),gripper=await loadRobot('gripper',{textures:false});
  try {
    const parent=gripper.group.parent;
    await rejects(()=>arm.attach(gripper,{port:'a650_j6/output',childPort:'parallel_gripper/input',twist:NaN}),'finite radians');
    gripper.port('parallel_gripper/input').matrix.makeScale(0,0,0);
    await rejects(()=>arm.attach(gripper,{port:'a650_j6/output',childPort:'parallel_gripper/input'}),'Invalid mount matrix');
    assert(gripper.group.parent===parent&&arm.connections.length===0,'Invalid attachment changed hierarchy');
  } finally {arm.dispose();if(!gripper.disposed)gripper.dispose();}
});
