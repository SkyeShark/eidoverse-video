// MIT. Closed cross-sections with holes and union of overlapping input meshes.
import polygon from './vendor/polygon-clipping/index.js';

const area=r=>r.slice(1).reduce((s,b,i)=>s+r[i][0]*b[1]-b[0]*r[i][1],0)/2;
function contains(r,p){
  let inside=false;
  for(let i=1;i<r.length;i++){
    const a=r[i-1],b=r[i];
    if((a[1]>p[1])!==(b[1]>p[1])&&p[0]<(b[0]-a[0])*(p[1]-a[1])/(b[1]-a[1])+a[0])inside=!inside;
  }return inside;
}
export function meshSlicer(geometry, {polygons=false}={}) {
  const a=geometry.getAttribute('position'),idx=geometry.getIndex(),n=(idx?.count??a.count)/3;
  const ranges=geometry.userData.manufacturingSource?.ranges??[{firstTriangle:0,triangles:n,name:'source'}];
  const owners=new Uint32Array(n);
  ranges.forEach((r,i)=>owners.fill(i,r.firstTriangle,r.firstTriangle+r.triangles));
  const triangles=[];
  const extent=geometry.boundingBox.max.clone().sub(geometry.boundingBox.min).length();
  const epsilon=Math.max(1e-11,extent*1e-8),key=p=>Math.round(p[0]/epsilon)+','+Math.round(p[1]/epsilon);
  for(let k=0;k<n;k++){
    const v=[0,1,2].map(c=>{const j=idx?idx.getX(k*3+c):k*3+c;return [a.getX(j),a.getY(j),a.getZ(j)];});
    triangles.push({v,owner:owners[k],lo:Math.min(...v.map(p=>p[1])),hi:Math.max(...v.map(p=>p[1]))});
  }
  triangles.sort((a,b)=>a.lo-b.lo);
  const active=new Set();let cursor=0,last=-Infinity;
  return y=>{
    if(y<last){active.clear();cursor=0;}last=y;
    while(cursor<triangles.length&&triangles[cursor].lo<=y)active.add(triangles[cursor++]);
    const groups=new Map();
    for(const t of active){
      if(t.hi<=y){active.delete(t);continue;}
      const hits=[];
      for(let j=0;j<3;j++){
        const a=t.v[j],b=t.v[(j+1)%3];
        if((a[1]<=y&&b[1]>y)||(b[1]<=y&&a[1]>y)){
          const u=(y-a[1])/(b[1]-a[1]);hits.push([a[0]+u*(b[0]-a[0]),a[2]+u*(b[2]-a[2])]);
        }
      }
      if(hits.length!==2||key(hits[0])===key(hits[1]))continue;
      // Preserve surface winding so inner walls are holes, not filled islands.
      const [a,b,c]=t.v,ux=b[0]-a[0],uy=b[1]-a[1],uz=b[2]-a[2],vx=c[0]-a[0],vy=c[1]-a[1],vz=c[2]-a[2];
      const nx=uy*vz-uz*vy,nz=ux*vy-uy*vx;
      if((hits[1][0]-hits[0][0])*(-nz)+(hits[1][1]-hits[0][1])*nx<0)hits.reverse();
      if(!groups.has(t.owner))groups.set(t.owner,[]);groups.get(t.owner).push(hits);
    }
    const solids=[];
    for(const [owner,segs] of groups){
      const graph=new Map();
      segs.forEach((s,i)=>s.forEach(p=>{const k=key(p);if(!graph.has(k))graph.set(k,[]);graph.get(k).push(i);}));
      for(const [k,edges] of graph)if(edges.length!==2)throw Error(`Open or nonmanifold slice at height ${y} in ${ranges[owner].name}, ${k}. Repair the source mesh.`);
      const used=new Set(),rings=[];
      for(let i=0;i<segs.length;i++)if(!used.has(i)){
        const ring=[...segs[i]];used.add(i);
        while(key(ring.at(-1))!==key(ring[0])){
          const j=graph.get(key(ring.at(-1))).find(j=>!used.has(j));
          if(j===undefined)throw Error('Source cross-section has an unclosed perimeter');
          if(key(segs[j][0])!==key(ring.at(-1)))throw Error('Source cross-section has inconsistent face winding');
          used.add(j);ring.push(segs[j][1]);
        }
        ring[ring.length-1]=ring[0];
        if(Math.abs(area(ring))>epsilon*epsilon)rings.push(ring);
      }
      if(!rings.length)continue;
      const orientation=Math.sign(area(rings.reduce((a,b)=>Math.abs(area(a))>Math.abs(area(b))?a:b)));
      const outers=rings.filter(r=>area(r)*orientation>0).map(r=>[r]);
      const holes=rings.filter(r=>area(r)*orientation<0);
      for(const hole of holes){
        const parents=outers.filter(p=>Math.abs(area(p[0]))>Math.abs(area(hole))&&contains(p[0],hole[0]));
        if(!parents.length)throw Error('Source cross-section has a hole without a containing solid');
        parents.sort((a,b)=>Math.abs(area(a[0]))-Math.abs(area(b[0])));parents[0].push(hole);
      }
      const solid=polygon.union(...outers);
      if(solid.length)solids.push(solid);
    }
    if(!solids.length)return [];
    const result=polygon.union(...solids);
    return polygons?result:result.flatMap(poly=>poly);
  };
}
