// MIT / CC0. Ordinary source meshes shared by the inspector and scene examples.
import * as T from 'three/webgpu';
export function manufacturingSample(name='handle') {
  if(name==='handle'){
    const group=new T.Group();group.name='Offset handle mesh';
    const shaft=new T.Mesh(new T.CylinderGeometry(.012,.010,.080,40,6));shaft.rotation.z=Math.PI/2;group.add(shaft);
    const lug=new T.Mesh(new T.CapsuleGeometry(.005,.030,6,20));lug.rotation.z=Math.PI/2;lug.position.set(.004,.012,.004);group.add(lug);
    return group;
  }
  if(name==='bracket'){
    const s=new T.Shape();s.moveTo(-.030,-.015);s.lineTo(.030,-.015);s.lineTo(.030,.015);s.lineTo(.012,.015);s.lineTo(.012,-.001);s.lineTo(-.012,-.001);s.lineTo(-.012,.015);s.lineTo(-.030,.015);s.closePath();
    const hole=new T.Path();hole.absarc(-.021,.006,.004,0,Math.PI*2,true);s.holes.push(hole);
    const g=new T.ExtrudeGeometry(s,{depth:.012,bevelEnabled:false,curveSegments:24});g.rotateX(-Math.PI/2);g.name='Fork bracket with bore';return g;
  }
  if(name==='ring')return new T.TorusKnotGeometry(.018,.0045,128,16,2,3);
  throw Error('Unknown source mesh sample');
}
