import * as THREE from 'three';
import {DecalGeometry} from 'three/addons/geometries/DecalGeometry.js';
export const STICKERS={none:'不貼',hazard:'警示斜紋',dive:'潛水旗',number:'巡檢編號 07'};
function textureFor(preset){
  const canvas=document.createElement('canvas');canvas.width=512;canvas.height=192;
  const c=canvas.getContext('2d');
  if(preset==='hazard'){
    c.fillStyle='#f2cb47';c.fillRect(0,0,512,192);c.fillStyle='#101c22';
    for(let x=-192;x<650;x+=128){c.beginPath();c.moveTo(x,0);c.lineTo(x+65,0);c.lineTo(x-127,192);c.lineTo(x-192,192);c.closePath();c.fill();}
  }else if(preset==='dive'){
    c.fillStyle='#d83132';c.fillRect(0,0,512,192);c.strokeStyle='#f4f5ed';c.lineWidth=60;c.beginPath();c.moveTo(0,0);c.lineTo(512,192);c.stroke();
  }else{
    c.fillStyle='#edf3e8';c.fillRect(0,0,512,192);c.fillStyle='#172b32';c.font='bold 125px monospace';c.textAlign='center';c.fillText('ROV 07',256,140);
  }
  const t=new THREE.CanvasTexture(canvas);t.colorSpace=THREE.SRGBColorSpace;return t;
}
export function applyVehicleSticker(vehicle,preset='none'){
  if(!vehicle||vehicle.stickerPreset===preset)return;
  const previous=vehicle.stickerGroup;
  if(previous){previous.traverse(o=>o.geometry?.dispose());previous.userData.material?.map?.dispose();previous.userData.material?.dispose();previous.removeFromParent();}
  vehicle.stickerPreset=preset;vehicle.stickerGroup=null;
  if(!STICKERS[preset]||preset==='none')return;
  vehicle.root.updateWorldMatrix(true,true);
  const group=new THREE.Group();group.name='Vehicle stickers';
  const material=new THREE.MeshStandardMaterial({map:textureFor(preset),transparent:true,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-4,roughness:.55,metalness:.05});
  group.userData.material=material;
  const id=vehicle.definition.id,large=id==='falcon';
  const width=large?.21:.14,height=width*192/512;
  const inverse=vehicle.model.matrixWorld.clone().invert();
  for(const side of [-1,1]){
    const start=vehicle.root.localToWorld(new THREE.Vector3(side*(large?.17:.11),1.4,large?.17:.06));
    const direction=new THREE.Vector3(0,-1,0).transformDirection(vehicle.root.matrixWorld);
    const ray=new THREE.Raycaster(start,direction,0,3);
    const hit=ray.intersectObject(vehicle.model,true).find(h=>h.object.isMesh&&h.face);
    if(!hit)continue;
    const normal=hit.face.normal.clone().applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld)).normalize();
    const projector=new THREE.Object3D();projector.position.copy(hit.point);projector.lookAt(hit.point.clone().add(normal));
    const geometry=new DecalGeometry(hit.object,hit.point,projector.rotation,new THREE.Vector3(width,height,.06));geometry.applyMatrix4(inverse);
    if(!geometry.attributes.position.count){geometry.dispose();continue;}
    const mesh=new THREE.Mesh(geometry,material);mesh.renderOrder=3;group.add(mesh);
  }
  if(!group.children.length){material.map.dispose();material.dispose();return;}
  vehicle.model.add(group);vehicle.stickerGroup=group;
}
