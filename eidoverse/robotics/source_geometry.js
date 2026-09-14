// MIT. One-time geometry snapshots for manufacturing. No source mesh is edited.
import * as T from 'three/webgpu';

export function sourceGeometry(source, {matrix, space='world', visibleOnly=true, maxTriangles=2000000}={}) {
  if(!Number.isInteger(maxTriangles)||maxTriangles<1)throw Error('Manufacturing triangle budget must be a positive integer');
  if(!source?.isBufferGeometry&&!source?.isObject3D)throw Error('Supply a BufferGeometry, Mesh, or Object3D hierarchy');
  if(!['world','local'].includes(space))throw Error('Geometry space must be world or local');
  const after=matrix?.isMatrix4?matrix:new T.Matrix4();
  if(matrix&&!matrix.isMatrix4)throw Error('Source matrix must be a Matrix4');
  const positions=[],ranges=[];
  const p=[new T.Vector3(),new T.Vector3(),new T.Vector3()];
  let skippedDegenerate=0;
  const append=(geometry,transform,object,instance=null)=>{
    const a=geometry.getAttribute('position'),idx=geometry.getIndex();
    if(!a||a.itemSize!==3)throw Error('Source mesh has no three-dimensional position attribute');
    const available=idx?.count??a.count,start=geometry.drawRange.start??0;
    const end=Math.min(available,start+(geometry.drawRange.count??Infinity));
    if(start%3||end%3)throw Error('Source draw range must contain complete triangles');
    const first=positions.length/9;
    const flip=transform.determinant()<0;
    for(let k=start;k<end;k+=3){
      for(let c=0;c<3;c++){
        const j=idx?idx.getX(k+c):k+c;
        if(!Number.isInteger(j)||j<0||j>=a.count)throw Error('Source has an invalid triangle index');
        if(object?.getVertexPosition)object.getVertexPosition(j,p[c]);
        else p[c].fromBufferAttribute(a,j);
        p[c].applyMatrix4(transform);
        if(!p[c].toArray().every(Number.isFinite))throw Error('Source contains a non-finite vertex');
      }
      const area=new T.Vector3().subVectors(p[1],p[0]).cross(new T.Vector3().subVectors(p[2],p[0])).lengthSq();
      if(area===0){skippedDegenerate++;continue;}
      if(positions.length/9>=maxTriangles)throw Error('Source exceeds the configured manufacturing triangle budget');
      for(const c of flip?[0,2,1]:[0,1,2])positions.push(...p[c]);
    }
    if(positions.length/9>first)ranges.push({name:object?.name??source.name??'geometry',instance,firstTriangle:first,triangles:positions.length/9-first});
  };
  if(source.isBufferGeometry)append(source,after,null);
  else {
    source.updateWorldMatrix(true,true);
    const inverse=space==='local'?source.matrixWorld.clone().invert():new T.Matrix4();
    const visit=o=>{
      if(visibleOnly&&!o.visible)return;
      if(o.isMesh){
        const transform=after.clone().multiply(inverse).multiply(o.matrixWorld);
        if(o.isSkinnedMesh)o.skeleton.update();
        if(o.isInstancedMesh){
          if(o.morphTexture)throw Error('Snapshot instanced morphs to ordinary meshes before manufacturing');
          const instance=new T.Matrix4();
          for(let k=0;k<o.count;k++){o.getMatrixAt(k,instance);append(o.geometry,transform.clone().multiply(instance),o,k);}
        }else append(o.geometry,transform,o);
      }
      for(const child of o.children)visit(child);
    };
    visit(source);
  }
  if(!positions.length)throw Error('Source contains no visible non-degenerate triangles');
  const g=new T.BufferGeometry();
  // Retain double precision during fitting/slicing, even for a distant source.
  // These positions are planning data, not per-frame renderer uploads.
  g.setAttribute('position',new T.BufferAttribute(new Float64Array(positions),3));
  g.computeBoundingBox();
  g.userData.manufacturingSource={triangles:positions.length/9,ranges,skippedDegenerate,space};
  return g;
}

export function fitSourceGeometry(source,{bounds,size,base=0,center=[0,0],...snapshot}={}) {
  const g=sourceGeometry(source,snapshot),box=g.boundingBox,extent=box.getSize(new T.Vector3());
  let factor,offset;
  if(bounds){
    if(!bounds.isBox3||bounds.isEmpty())throw Error('Fit bounds must be a nonempty Box3');
    const span=bounds.getSize(new T.Vector3());
    factor=Math.min(...[0,1,2].map(k=>extent.getComponent(k)>0?span.getComponent(k)/extent.getComponent(k):Infinity));
    offset=bounds.getCenter(new T.Vector3()).sub(box.getCenter(new T.Vector3()).multiplyScalar(factor));
  }else{
    if(!(size>0&&Number.isFinite(size)))throw Error('Fit size must be positive');
    factor=size/Math.max(extent.x,extent.y,extent.z);
    offset=new T.Vector3(center[0],base,center[1]).sub(new T.Vector3((box.min.x+box.max.x)/2,box.min.y,(box.min.z+box.max.z)/2).multiplyScalar(factor));
  }
  if(!(factor>0&&Number.isFinite(factor))||!offset.toArray().every(Number.isFinite))throw Error('Invalid source fit');
  g.applyMatrix4(new T.Matrix4().makeScale(factor,factor,factor).setPosition(offset));
  g.computeBoundingBox();
  g.userData.manufacturingSource.fit={scale:factor,offset:offset.toArray(),bounds:[g.boundingBox.min.toArray(),g.boundingBox.max.toArray()]};
  return g;
}
