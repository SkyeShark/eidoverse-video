import * as T from 'three/webgpu';import {loadRobot} from '../index.js';
const assert=(v,m)=>{if(!v)throw Error(m)};
Deno.test('rotary fixture studs engage actual T-slot nuts and retain visible nut floors',async()=>{
 const r=await loadRobot('cnc_rotary',{textures:false});r.group.updateMatrixWorld(true);const fixture=r.roots.rotary_fixture,ray=new T.Raycaster();
 const fixings=[...[-.18375,-.1275].flatMap(x=>[-.070,.070].map(z=>[x,z])),...[.04125,.15375].flatMap(x=>[-.060,.060].map(z=>[x,z]))];
 const box=o=>new T.Box3().setFromObject(o).applyMatrix4(fixture.matrixWorld.clone().invert());
 for(const [j,[x,z]] of fixings.entries()){
  const nuts=r.part('RC table T-nut '+j),studs=r.part('RC table stud '+j);assert(nuts.length&&studs.length,'Missing nut/stud '+j);
  const nb=new T.Box3();nuts.forEach(o=>nb.union(box(o)));const sb=new T.Box3();studs.forEach(o=>sb.union(box(o)));
  assert(Math.abs(nb.min.x-x+.007)<2e-7&&Math.abs(nb.max.x-x-.007)<2e-7,'Nut width / slot centre mismatch');
  assert(Math.abs(nb.max.y+.008)<2e-7&&Math.abs(nb.min.y+.014)<2e-7,'Nut is not inside the slot undercut');
  assert(sb.min.y<-.0129&&sb.max.y>.0019,'Stud lacks nut engagement or continuous slot crossing');
  assert(Math.min(...[-3,-2,-1,0,1,2,3].map(k=>Math.abs(x+.015-k*.05625)))<1e-9,'Missing bed slot');
  const p=fixture.localToWorld(new T.Vector3(x,-.016,-z+.008));ray.set(p,new T.Vector3(0,1,0).transformDirection(fixture.matrixWorld));
  const hit=ray.intersectObjects(nuts,false)[0];assert(hit&&Math.abs(hit.distance-.002)<2e-7,'Visible nut underside missing');
 }
 assert(r.machine.cutter.kind==='flat'&&r.part('SP two flute cutter').length,'Original cutter not restored');r.dispose();
});
