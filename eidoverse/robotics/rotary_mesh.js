// MIT. Indexed XYZ rasters from actual source triangles, about the X stock axis.
import * as T from 'three/webgpu';
import {fitSourceGeometry, sourceGeometry} from './source_geometry.js';
import {stockProfile} from './cutting.js';
import {RotaryPath, CENTRE_SEAT} from './rotary_path.js';
import {rotaryFixtureSetup} from './rotary_setup.js';

// Clip in X/Z while retaining interpolated Y. Taking the upper bound over each
// covered cell protects even a thin triangle between sampling rays.
function clip(poly, axis, value, keepGreater) {
  const out=[];
  for(let i=0;i<poly.length;i++){
    const a=poly[i],b=poly[(i+1)%poly.length],da=(a[axis]-value)*(keepGreater?1:-1),db=(b[axis]-value)*(keepGreater?1:-1);
    if(da>=-1e-12)out.push(a);
    if((da>0&&db<0)||(da<0&&db>0)){
      const t=da/(da-db);out.push(a.map((v,k)=>v+(b[k]-v)*t));
    }
  }
  return out;
}
export function meshEnvelope(geometry, angle, {minX,maxX,minZ,maxZ,step}) {
  const nx=Math.ceil((maxX-minX)/step),nz=Math.ceil((maxZ-minZ)/step);
  const dx=(maxX-minX)/nx,dz=(maxZ-minZ)/nz,heights=new Float64Array(nx*nz).fill(-Infinity);
  const p=geometry.getAttribute('position'),c=Math.cos(angle),s=Math.sin(angle);
  for(let t=0;t<p.count;t+=3){
    const tri=[0,1,2].map(k=>[p.getX(t+k),c*p.getY(t+k)-s*p.getZ(t+k),s*p.getY(t+k)+c*p.getZ(t+k)]);
    const ax=Math.max(0,Math.floor((Math.min(...tri.map(v=>v[0]))-minX)/dx)-1);
    const bx=Math.min(nx-1,Math.floor((Math.max(...tri.map(v=>v[0]))-minX)/dx));
    const az=Math.max(0,Math.floor((Math.min(...tri.map(v=>v[2]))-minZ)/dz)-1);
    const bz=Math.min(nz-1,Math.floor((Math.max(...tri.map(v=>v[2]))-minZ)/dz));
    for(let z=az;z<=bz;z++)for(let x=ax;x<=bx;x++){
      let poly=clip(tri,0,minX+x*dx,true);
      poly=clip(poly,0,minX+(x+1)*dx,false);
      poly=clip(poly,2,minZ+z*dz,true);
      poly=clip(poly,2,minZ+(z+1)*dz,false);
      if(poly.length)heights[x+nx*z]=Math.max(heights[x+nx*z],...poly.map(v=>v[1]));
    }
  }
  return {heights,nx,nz,dx,dz,minX,minZ};
}

function footprint(grid,x0,x1,z,R,kind){
  const {heights,nx,nz,dx,dz,minX,minZ}=grid;
  const ax=Math.max(0,Math.floor((x0-R-minX)/dx)),bx=Math.min(nx-1,Math.floor((x1+R-minX)/dx));
  const az=Math.max(0,Math.floor((z-R-minZ)/dz)),bz=Math.min(nz-1,Math.floor((z+R-minZ)/dz));
  let top=-Infinity;
  for(let j=az;j<=bz;j++)for(let i=ax;i<=bx;i++){
    const h=heights[i+nx*j];if(!Number.isFinite(h))continue;
    const cx=Math.max(0,minX+i*dx-x1,x0-minX-(i+1)*dx);
    const cz=Math.max(0,minZ+j*dz-z,z-minZ-(j+1)*dz),r2=cx*cx+cz*cz;
    if(r2<=R*R)top=Math.max(top,h+(kind==='ball'?Math.sqrt(Math.max(0,R*R-r2))-R:0));
  }
  return top;
}

export function rotaryMeshProgram(source,options={}){
  const setup=rotaryFixtureSetup(options),profile=stockProfile(options.material??'wood');
  const {stockLength,stockWidth,stockHeight,axisHeight,axisX,start,end}=setup;
  const radius=options.radius??.003,kind=options.tool??'flat',fluteLength=options.fluteLength??(kind==='flat'?.018:.017);
  const angles=options.angles??12,sampleStep=options.sampleStep??.001,gridStep=options.gridStep??.0005;
  const stepover=options.stepover??radius*.55,stepdown=options.stepdown??profile.stepdown;
  const allowance=options.roughAllowance??.0005,tolerance=options.tolerance??.00005;
  const feed=options.feed??profile.feed,plunge=options.plunge??profile.plunge,rpm=options.rpm??profile.rpm;
  if(!['flat','ball'].includes(kind))throw Error('Rotary tool must be flat or ball');
  if(!Number.isInteger(angles)||angles<4||angles>96)throw Error('Mesh indexing requires 4–96 orientations');
  if(![radius,fluteLength,sampleStep,gridStep,stepover,stepdown,feed,plunge,rpm].every(v=>Number.isFinite(v)&&v>0)||
    ![allowance,tolerance].every(v=>Number.isFinite(v)&&v>=0)||gridStep<.0001||sampleStep<.0002||stepover>radius*1.5||stepover<.0002)
    throw Error('Invalid mesh machining resolution, tool or feed');
  const box=new T.Box3(new T.Vector3(start,-stockHeight/2+.0005,-stockWidth/2+.0005),new T.Vector3(end,stockHeight/2-.0005,stockWidth/2-.0005));
  const geometry=options.fit===false?sourceGeometry(source,options):fitSourceGeometry(source,{...options,bounds:box});
  if(!box.clone().expandByScalar(1e-8).containsBox(geometry.boundingBox)){geometry.dispose();throw Error('Target does not fit the cutting region; enable fit or change stock size');}
  const stockRadius=Math.hypot(stockWidth/2,stockHeight/2),safe=stockRadius+.0022;
  // Conservative shank clearance against the original blank. Do not cut with
  // the non-cutting shank or silently pretend that unreachable stock vanished.
  const reachFloor=stockRadius-fluteLength+.0006;
  const nx=Math.ceil((end-start)/sampleStep),nz=Math.ceil(2*stockRadius/stepover);
  const rows=[],report={source:geometry.userData.manufacturingSource,orientations:angles,tool:kind,gridStep,
    reachLimitedSamples:0,minimumRequestedTip:Infinity,reachFloor,retainedEndStock:[start+stockLength/2,stockLength/2-end],
    limitations:['Indexed machining about X preserves surfaces inaccessible to these directions and this cutter.',
      'Sacrificial end stock and any material beyond cutting-length reach remain in the simulated result.']};
  try{
    for(let j=0;j<angles;j++){
      const angle=-j*Math.PI*2/angles,grid=meshEnvelope(geometry,angle,{minX:start-radius,maxX:end+radius,minZ:-stockRadius-radius,maxZ:stockRadius+radius,step:gridStep});
      const station=[];
      for(let k=0;k<=nz;k++){
        const z=-stockRadius+2*stockRadius*k/nz,seg=[];
        for(let i=0;i<nx;i++){
          const x0=start+(end-start)*i/nx,x1=start+(end-start)*(i+1)/nx;
          const required=footprint(grid,x0,x1,z,radius,kind);
          if(Number.isFinite(required)){report.minimumRequestedTip=Math.min(report.minimumRequestedTip,required);if(required+tolerance<reachFloor)report.reachLimitedSamples++;}
          seg.push(Math.max(reachFloor,required+tolerance));
        }
        // Both ends of a segment clear its complete swept footprint. Merely
        // sampling vertex heights can gouge peaks between path samples.
        station.push(Array.from({length:nx+1},(_,i)=>[start+(end-start)*i/nx,Math.max(seg[Math.max(0,i-1)],seg[Math.min(nx-1,i)]),z]));
      }
      rows.push(station);
    }
  }finally{geometry.dispose();}
  if(options.requireReach&&report.reachLimitedSamples)throw Error(`Target exceeds cutter reach at ${report.reachLimitedSamples} sampled footprints; use smaller stock, a longer tool, or another setup`);
  let minimum=Math.min(...rows.flat().map(row=>Math.min(...row.map(p=>p[1]))));
  const floors=[];for(let y=stockRadius-stepdown;y>minimum+allowance;y-=stepdown)floors.push(y);
  floors.push(minimum+allowance);floors.push(null);
  const stages=[],moves=[];let cursor=[start,safe,0],angle=0;
  const push=(position,a,type,stage,rate)=>{moves.push({position,angle:a,type,stage,feed:rate});cursor=position;angle=a;};
  push(cursor,0,'rapid','setup');
  for(let pass=0;pass<floors.length;pass++){
    const finish=floors[pass]===null,stage=finish?'finish':'rough '+(pass+1);
    stages.push({name:stage,firstMove:moves.length});
    for(let j=0;j<angles;j++){
      const a=-(pass+j/angles)*Math.PI*2;
      push([cursor[0],safe,cursor[2]],angle,'rapid',stage);
      push(cursor,a,'index',stage);
      const rowStride=finish?1:Math.max(1,Math.floor(radius*1.25/stepover));
      for(let k=0;k<rows[j].length;k+=rowStride){
        let row=rows[j][k].map(([x,y,z])=>[x,finish?y:Math.max(floors[pass],y+allowance),z]);
        if(!finish){
          const stride=Math.max(1,Math.floor(.003/sampleStep)),coarse=[];
          for(let i=0;i<row.length;i+=stride){const end=Math.min(row.length-1,i+stride);const start=Math.max(0,i-stride);coarse.push([row[i][0],Math.max(...row.slice(start,end+1).map(p=>p[1])),row[i][2]]);}
          if(coarse.at(-1)[0]!==row.at(-1)[0])coarse.push([row.at(-1)[0],Math.max(...row.slice(-stride-1).map(p=>p[1])),row.at(-1)[2]]);
          row=coarse;
        }
        if(k%2)row.reverse();
        push([cursor[0],safe,cursor[2]],a,'rapid',stage);
        push([row[0][0],safe,row[0][2]],a,'rapid',stage);
        push(row[0],a,'cut',stage,plunge);
        for(const p of row.slice(1))push(p,a,'cut',stage,feed);
      }
    }
  }
  push([cursor[0],safe,cursor[2]],angle,'rapid','retract');
  if(moves.length>400000)throw Error('Mesh toolpath exceeds 400,000 moves; increase sampling or stepover');
  const path=new RotaryPath(moves,{...options,feed});
  return {moves,path,stages,report,settings:{stockLength,stockWidth,stockHeight,start,end,axisX,axisHeight,radius,fluteLength,tool:kind,angles,sampleStep,stepover,gridStep,safe,material:options.material??'wood',feed,plunge,rpm,stepdown,centreSeat:{...CENTRE_SEAT}},target:source};
}
