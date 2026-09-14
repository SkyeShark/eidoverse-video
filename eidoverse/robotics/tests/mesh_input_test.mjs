import * as T from 'three/webgpu';
import {sourceGeometry,fitSourceGeometry} from '../source_geometry.js';
import {sliceGeometry} from '../fabrication.js';
import {meshSlicer} from '../mesh_slices.js';
import {reliefFromMesh} from '../relief.js';
const assert=(x,m='Assertion failed')=>{if(!x)throw Error(m);};
const near=(a,b,e=1e-8)=>assert(Math.abs(a-b)<=e,`${a} != ${b}`);
const area=r=>Math.abs(r.slice(1).reduce((s,p,i)=>s+r[i][0]*p[1]-p[0]*r[i][1],0)/2);

Deno.test('solid skins close local ledges below taller features while keeping sparse internal fill',()=>{
  const group=new T.Group(),slab=new T.Mesh(new T.BoxGeometry(.04,.010,.02)),tower=new T.Mesh(new T.BoxGeometry(.012,.010,.012));
  slab.position.y=.005;tower.position.y=.015;group.add(slab,tower);
  const spec=sliceGeometry(group,{size:.04,base:0,layerHeight:.001,beadWidth:.0005,infill:.25,solidLayers:3});
  function distance(x,z,y){
    let closest=Infinity;
    for(let i=1;i<spec.points.length;i++){
      const a=spec.points[i-1].position,b=spec.points[i].position;if(spec.points[i].type!=='extrude'||Math.abs(a[1]-y)>1e-8||Math.abs(b[1]-y)>1e-8)continue;
      const dx=b[0]-a[0],dz=b[2]-a[2],f=Math.max(0,Math.min(1,((x-a[0])*dx+(z-a[2])*dz)/(dx*dx+dz*dz)));
      closest=Math.min(closest,Math.hypot(x-a[0]-dx*f,z-a[2]-dz*f));
    }return closest;
  }
  for(const y of [.008,.009,.010])for(let x=.009;x<.018;x+=.0011)for(let z=-.007;z<.007;z+=.00037){
    assert(distance(x,z,y)<=.000251,'Local roof is still open at '+[x,y,z]);
    assert(distance(-x,z,y)<=.000251,'Opposite roof is still open');
  }
  assert([-.0049,-.0037,-.0023,.0011].some(x=>[-.0031,-.0017,.0013,.0031].some(z=>distance(x,z,.005)>.0005)),'Interior was made solid instead of keeping infill');
});

Deno.test('a disconnected solid inside a hollow shell survives STL-style single-mesh slicing',()=>{
  const group=new T.Group(),ring=new T.LatheGeometry([[.020,0],[.030,0],[.030,.010],[.020,.010],[.020,0]].map(p=>new T.Vector2(...p)),48);
  const core=new T.Mesh(new T.CylinderGeometry(.008,.008,.010,32));core.position.y=.005;group.add(new T.Mesh(ring),core);
  const geometry=sourceGeometry(group);delete geometry.userData.manufacturingSource;
  const rings=meshSlicer(geometry)(.005);assert(rings.length===3,'The separate inner solid was erased by the shell hole');geometry.dispose();
});

Deno.test('FDM honors explicitly selected local orientation and source matrices',()=>{
  const m=new T.Mesh(new T.BoxGeometry(.040,.010,.020));m.rotation.z=Math.PI/2;
  const world=sliceGeometry(m,{size:.04,base:0,layerHeight:.001,solidLayers:0});
  const local=sliceGeometry(m,{space:'local',size:.04,base:0,layerHeight:.001,solidLayers:0});
  assert(world.layers===40&&local.layers===10,'FDM ignored the source space option');
  const transformed=sliceGeometry(m.geometry,{matrix:new T.Matrix4().makeRotationZ(Math.PI/2),size:.04,base:0,layerHeight:.001,solidLayers:0});
  assert(transformed.layers===40,'FDM ignored its explicit source matrix');
});

Deno.test('manufacturing snapshots preserve parent, reflection and instance transforms without editing source vertices',()=>{
  const root=new T.Group(),group=new T.Group(),g=new T.BoxGeometry(.012,.021,.008),part=new T.Mesh(g);
  root.position.set(5,.2,-2);root.rotation.y=.4;group.scale.set(-1.2,.6,1.1);group.rotation.z=.35;
  part.position.set(.007,.001,-.003);root.add(group);group.add(part);root.updateMatrixWorld(true);
  const original=Array.from(g.attributes.position.array),snapshot=sourceGeometry(group);
  const expected=new T.Box3().setFromObject(group);
  for(const k of ['x','y','z']){near(snapshot.boundingBox.min[k],expected.min[k]);near(snapshot.boundingBox.max[k],expected.max[k]);}
  assert(original.every((v,i)=>v===g.attributes.position.array[i]),'Input buffer changed');
  const instances=new T.InstancedMesh(g,new T.MeshBasicMaterial(),2);
  instances.setMatrixAt(0,new T.Matrix4().makeTranslation(-.02,0,0));instances.setMatrixAt(1,new T.Matrix4().makeTranslation(.03,0,0));
  const instanced=sourceGeometry(instances);
  near(instanced.boundingBox.min.x,-.026);near(instanced.boundingBox.max.x,.036);
  assert(instanced.userData.manufacturingSource.ranges.length===2);
  const fitted=fitSourceGeometry(group,{size:.04,base:.00065});
  near(fitted.boundingBox.min.y,.00065);
  near(Math.max(...fitted.boundingBox.getSize(new T.Vector3())),.04);
});

Deno.test('overlapping supplied solids produce their union, with no internal perimeter or XOR gap',()=>{
  const group=new T.Group();
  for(const x of [-.005,.005]){const m=new T.Mesh(new T.BoxGeometry(.02,.008,.02));m.position.set(x,.004,0);group.add(m);}
  const g=sourceGeometry(group),rings=meshSlicer(g)(.004);
  assert(rings.length===1,'Overlap retained an internal contour');near(area(rings[0]),.03*.02,1e-10);
  const sliced=sliceGeometry(group,{size:.03,layerHeight:.001,beadWidth:.0006,solidLayers:0});
  for(let layer=1;layer<=sliced.layers;layer++)assert(sliced.contours.filter(c=>c.layer===layer).length===1);
  assert(sliced.points.some((p,i)=>i&&p.type==='extrude'&&p.position[0]>0&&sliced.points[i-1].position[0]<0),'Infill never crosses the overlap');
});

Deno.test('arbitrary concave extruded outlines retain holes in perimeters and infill',()=>{
  const shape=new T.Shape();
  const outline=[[-.018,-.014],[.018,-.014],[.018,.014],[.004,.014],[.004,.006],[-.018,.006]];
  shape.moveTo(...outline[0]);outline.slice(1).forEach(p=>shape.lineTo(...p));shape.closePath();
  const hole=new T.Path();hole.absarc(-.008,-.004,.004,0,Math.PI*2,true);shape.holes.push(hole);
  const g=new T.ExtrudeGeometry(shape,{depth:.01,bevelEnabled:false,curveSegments:24});g.rotateX(Math.PI/2);
  const fit=fitSourceGeometry(g,{size:.036,base:0}),slicer=meshSlicer(fit),rings=slicer(.005);
  assert(rings.length===2,'Hole boundary lost');
  const spec=sliceGeometry(g,{size:.036,base:0,layerHeight:.001,beadWidth:.0005,solidLayers:0,infill:.25});
  const [tx,,tz]=fit.userData.manufacturingSource.fit.offset;
  const hx=-.008+tx,hz=-.004+tz;
  for(let i=1;i<spec.points.length;i++)if(spec.points[i].type==='extrude'){
    const a=spec.points[i-1].position,b=spec.points[i].position;
    for(let k=1;k<20;k++){
      const t=k/20,x=a[0]+(b[0]-a[0])*t,z=a[2]+(b[2]-a[2])*t;
      assert(Math.hypot(x-hx,z-hz)>.0039,'Deposition crosses the designed hole');
    }
  }
});

Deno.test('relief mesh input includes transforms above the supplied subtree',()=>{
  const parent=new T.Group(),mesh=new T.Mesh(new T.BoxGeometry(.012,.004,.018));
  parent.position.set(.010,.010,0);parent.add(mesh);
  const result=reliefFromMesh(mesh,{width:.06,depth:.06,stockHeight:.02,floor:.004,columns:61,rows:61});
  near(result.heights[30*61+40],.012,1e-8);
  near(result.heights[30*61+20],.004,1e-8);
});

Deno.test('invalid open or nonfinite manufacturing geometry fails instead of substituting a sample',()=>{
  let rejected=false;
  try{sliceGeometry(new T.PlaneGeometry(.02,.02));}catch(e){rejected=/Open|nonmanifold|shorter|triangles/.test(e.message);}
  assert(rejected,'Open mesh silently accepted');
  const g=new T.BoxGeometry(.02,.02,.02);g.attributes.position.setX(0,NaN);
  rejected=false;try{sourceGeometry(g);}catch(e){rejected=/non-finite/.test(e.message);}
  assert(rejected,'Nonfinite coordinates silently accepted');
});
