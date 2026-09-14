import * as T from 'three/webgpu';
import {rotaryProgram,sweepDistance} from '../rotary_path.js';
import {sourceGeometry} from '../source_geometry.js';
import {indexRotarySweeps} from '../rotary_stock.js';
const assert=(v,m='Assertion failed')=>{if(!v)throw Error(m)};

Deno.test('mesh CNC uses translated off-axis details and lateral tool travel; protects narrow features',()=>{
  const group=new T.Group(),body=new T.Mesh(new T.CylinderGeometry(.011,.011,.060,28,1));
  body.rotation.z=Math.PI/2;group.add(body);
  const ridge=new T.Mesh(new T.BoxGeometry(.045,.002,.00008));ridge.position.set(.002,.012,.0031);group.add(ridge);
  const o={fit:false,angles:4,gridStep:.00065,sampleStep:.003,stepover:.0035,stepdown:.006};
  const p=rotaryProgram(group,o),geometry=sourceGeometry(group),pos=geometry.getAttribute('position');
  assert(p.report.source.triangles===pos.count/3);
  assert(new Set(p.moves.filter(v=>v.type==='cut').map(v=>v.position[2].toFixed(5))).size>8,'Missing lateral rasters');
  const bounds={min:[-.07,-.027,-.027],max:[.07,.027,.027]},index=indexRotarySweeps(p.path,p.settings,bounds,[32,16,16],0);
  let worst=Infinity,queries=0;
  for(let i=0;i<pos.count;i++){
    const q=[pos.getX(i),pos.getY(i),pos.getZ(i)],b=q.map((v,k)=>Math.floor((v-bounds.min[k])/index.cell[k]));
    for(const id of index.bins[b[0]+32*(b[1]+16*b[2])]){queries++;worst=Math.min(worst,sweepDistance(q,p.path.segments[id],.003,.018,1,'flat'));}
  }
  assert(queries>100,'Independent surface queries absent');assert(worst>=-1e-8,'Source was gouged by '+(-worst));
  ridge.position.z=-.005;
  const changed=rotaryProgram(group,o);
  assert(JSON.stringify(p.moves)!==JSON.stringify(changed.moves),'Input changed but toolpath did not');
  assert(p.moves.every(v=>v.type!=='index'||v.position[1]>=p.settings.safe));
  geometry.dispose();
});

Deno.test('flat endmill sweep has a flat tip and agrees with independent moving cylinder membership',()=>{
  for(const angle of [0,.65])for(const delta of [[.016,0],[.016,.009],[0,-.011]]){
    const s={a:[-.008,.007,.002],b:[-.008+delta[0],.007+delta[1],.002],a0:angle};
    let seed=17;
    for(let n=0;n<240;n++){
      const rand=()=>{seed=(seed*16807)%2147483647;return seed/2147483647};
      const point=[-.015+rand()*.040,-.004+rand()*.043,-.012+rand()*.026];
      const q=[point[0],Math.cos(angle)*point[1]-Math.sin(angle)*point[2],Math.sin(angle)*point[1]+Math.cos(angle)*point[2]];
      let distance=Infinity;
      for(let j=0;j<=4000;j++){
        const f=j/4000,x=s.a[0]+delta[0]*f,y=s.a[1]+delta[1]*f;
        const radial=Math.hypot(q[0]-x,q[2]-.002)-.003,vertical=Math.max(y-q[1],q[1]-y-.018);
        distance=Math.min(distance,Math.max(radial,vertical));
      }
      if(Math.abs(distance)>.00001)assert((sweepDistance(point,s,.003,.018,1,'flat')<0)===(distance<0),'Flat sweep membership mismatch');
    }
  }
  const s={a:[0,0,0],b:[.01,0,0],a0:0};
  assert(sweepDistance([.005,-.0001,0],s,.003,.018,1,'flat')>0);
  assert(sweepDistance([.005,.0001,.0028],s,.003,.018,1,'flat')<0);
});

Deno.test('mesh planner reports reach-limited material and never silently substitutes an example',()=>{
  const g=new T.BoxGeometry(.060,.003,.005);
  const o={fit:false,angles:4,gridStep:.001,sampleStep:.005,stepover:.004,stepdown:.008};
  const p=rotaryProgram(g,o);
  assert(p.target===g&&p.report.reachLimitedSamples>0);
  let failed=false;try{rotaryProgram(g,{...o,requireReach:true})}catch(e){failed=/reach/.test(e.message)}assert(failed);
  failed=false;try{rotaryProgram({sample:'fake'},o)}catch(e){failed=/BufferGeometry/.test(e.message)}assert(failed);
});
