// Trigger-time photo evidence. This is client evidence, not scoring authority.
// No screenshot is generated here: capture the renderer immediately afterwards,
// before any animation/update, so matrices and the image describe the same view.
import * as THREE from 'three';

const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
const NED=p=>[p.z,-p.x,-p.y];
function shown(o,camera){
  for(let p=o;p;p=p.parent)if(!p.visible)return false;
  return o.layers.test(camera.layers);
}
function opaque(material){
  return material && material.visible!==false && material.depthTest!==false &&
    !material.wireframe && (!material.transparent || (material.opacity>=.5 && material.depthWrite));
}
function physical(o,camera){
  return o.isMesh && shown(o,camera) && !o.userData.observationIgnore &&
    (Array.isArray(o.material)?o.material:[o.material]).some(opaque);
}
function matrixFor(mesh,index){
  const matrix=mesh.matrixWorld.clone();
  if(mesh.isInstancedMesh){const local=new THREE.Matrix4();mesh.getMatrixAt(index,local);matrix.multiply(local);}
  return matrix;
}

// Match kelpMaterial's vertex displacement exactly, including per-instance phase.
// Three's built-in raycaster otherwise intersects the undeformed flat blade.
function bentProxy(mesh,index){
  const u=mesh.userData.observationBend, local=new THREE.Matrix4();mesh.getMatrixAt(index,local);
  const geo=mesh.geometry.clone(), pos=geo.attributes.position;
  const phase=local.elements[12]*.37+local.elements[14]*.53;
  for(let i=0;i<pos.count;i++){
    const h=pos.getY(i),sway=Math.sin(u.uTime.value*.9+phase+h*.6)*.35+Math.sin(u.uTime.value*1.7+phase*2.1)*.12;
    const bend=h*h*1.1;
    pos.setXYZ(i,pos.getX(i)+(u.uFlow.value.x*1.2+sway)*bend,h,pos.getZ(i)+(u.uFlow.value.z*1.2+sway*.6)*bend);
  }
  geo.computeBoundingBox();geo.computeBoundingSphere();
  const proxy=new THREE.Mesh(geo,mesh.material);proxy.matrixAutoUpdate=false;
  proxy.matrixWorld.copy(mesh.matrixWorld).multiply(local);
  proxy.userData.observationSource={mesh,index};
  return proxy;
}
function samples(part,camera){
  const {mesh,index}=part,geo=mesh.geometry,matrix=matrixFor(mesh,index);
  if(!geo.boundingBox)geo.computeBoundingBox();
  const box=geo.boundingBox,lo=box.min,hi=box.max,corners=[];
  for(const x of [lo.x,hi.x])for(const y of [lo.y,hi.y])for(const z of [lo.z,hi.z])corners.push(new THREE.Vector3(x,y,z).applyMatrix4(matrix).project(camera));
  const front=corners.filter(v=>v.z>=-1&&v.z<=1);
  if(!front.length)return null;
  const left=Math.max(-1,Math.min(...front.map(v=>v.x))),right=Math.min(1,Math.max(...front.map(v=>v.x)));
  const bottom=Math.max(-1,Math.min(...front.map(v=>v.y))),top=Math.min(1,Math.max(...front.map(v=>v.y)));
  if(left>=right||bottom>=top)return null;
  const points=[box.getCenter(new THREE.Vector3()).applyMatrix4(matrix)];
  const attr=geo.attributes.position,idx=geo.index,triangles=Math.floor((idx?idx.count:attr.count)/3);
  const count=Math.min(12,triangles);
  // Triangle centroids land on actual surfaces rather than an empty school box.
  for(let j=0;j<count;j++){
    const tri=Math.min(triangles-1,Math.floor((j+.5)*triangles/count))*3,p=new THREE.Vector3();
    for(let k=0;k<3;k++)p.add(new THREE.Vector3().fromBufferAttribute(attr,idx?idx.getX(tri+k):tri+k));
    points.push(p.multiplyScalar(1/3).applyMatrix4(matrix));
  }
  return {area:(right-left)*(top-bottom)/4,points,center:new THREE.Vector2((left+right)/2,(bottom+top)/2)};
}

/**
 * targets: optional engineering [{entity_id,category,mesh,instanceIds?}]. A mesh
 * may be a Group of physical parts. Engineering targets take priority when
 * visible; empty waypoint markers cannot become evidence.
 */
export function inspectObservation({scene,camera,environment,state={},world={},camMode,
  targets=[],minCoverage=.0025}={}){
  camera.updateWorldMatrix(true,false);scene.updateMatrixWorld(true);
  const pos=camera.getWorldPosition(new THREE.Vector3());
  const q=camera.getWorldQuaternion(new THREE.Quaternion()).multiply(new THREE.Quaternion(0,1,0,0)).normalize();
  if(q.w<0){q.x*=-1;q.y*=-1;q.z*=-1;q.w*=-1;}
  const base={ok:false,entity_id:null,category:null,view:camMode,visible:false,coverage:0,
    camera:{pos:NED(pos),q:[q.w,q.z,-q.x,-q.y],fov:camera.fov,aspect:camera.aspect}};
  if(camMode!=='onboard')return {...base,reason:'請切換機載鏡頭再拍攝；外部視角不計入觀察紀錄。'};
  const range=(world.scenario?.visibility_m||12)*(1-.75*clamp(state.silt||0,0,1));
  // Keep fog physically limiting observations even when the display fog toggle
  // is off. Retain at least 20% contrast in the renderer's linear fog model.
  const fogLimit=.3+.8*Math.max(0,range*1.35-.3);
  const candidates=[...targets.map(t=>({...t,priority:0})),...(environment?.observationTargets||[]).map(t=>({...t,priority:1}))];
  const blockers=[],proxies=[],replacement=new Map();
  scene.traverse(o=>{
    if(!physical(o,camera))return;
    if(o.userData.observationBend&&o.isInstancedMesh){
      const parts=[];
      for(let i=0;i<o.count;i++){const proxy=bentProxy(o,i);parts.push(proxy);proxies.push(proxy);blockers.push(proxy);}
      replacement.set(o,parts);
    }else {
      // Fish instance matrices move between captures; cached bounding spheres
      // must not suppress intersections with their current rendered positions.
      if(o.isInstancedMesh)o.computeBoundingSphere();
      blockers.push(o);
    }
  });
  const ray=new THREE.Raycaster(),ndc=new THREE.Vector3();
  const reports=[],prepared=[];
  try{
    for(const target of candidates){
      if(!target.mesh||!shown(target.mesh,camera))continue;
      const parts=[];
      target.mesh.traverse(o=>{
        if(!physical(o,camera))return;
        if(o.isInstancedMesh){
          const ids=o===target.mesh&&target.instanceIds?target.instanceIds:Array.from({length:o.count},(_,i)=>i);
          for(const index of ids){if(index<0||index>=o.count)continue;const proxy=replacement.get(o)?.[index];parts.push({mesh:proxy||o,index:proxy?null:index,source:o,sourceIndex:index});}
        }else parts.push({mesh:o,index:null,source:o,sourceIndex:null});
      });
      const projected=parts.map(part=>({part,sample:samples(part,camera)})).filter(x=>x.sample);
      if(!projected.length)continue;
      prepared.push({target,parts,projected,centerDistance:Math.min(...projected.map(x=>x.sample.center.length()))});
    }
    // Project bounds before casting any rays. Try engineering targets and the
    // most central visible subject first; stop as soon as that photo qualifies.
    prepared.sort((a,b)=>a.target.priority-b.target.priority||a.centerDistance-b.centerDistance);
    for(const {target,parts,projected} of prepared){
      let coverage=0,hits=0,attempts=0,distance=Infinity,centerDistance=Infinity,inRange=0;
      for(const {part,sample} of projected){
        centerDistance=Math.min(centerDistance,sample.center.length());
        let partHits=0,partAttempts=0;
        for(const point of sample.points){
          ndc.copy(point).project(camera);
          if(Math.abs(ndc.x)>1||Math.abs(ndc.y)>1||ndc.z< -1||ndc.z>1)continue;
          partAttempts++;attempts++;
          const dist=pos.distanceTo(point);distance=Math.min(distance,dist);
          if(dist>fogLimit)continue;
          inRange++;
          ray.setFromCamera(new THREE.Vector2(ndc.x,ndc.y),camera);ray.near=camera.near;ray.far=Math.min(camera.far,dist+.1);
          const intersections=ray.intersectObjects(blockers,false);
          const first=intersections.find(hit=>{
            const mat=Array.isArray(hit.object.material)?hit.object.material[hit.face?.materialIndex||0]:hit.object.material;
            return opaque(mat);
          });
          if(!first)continue;
          const source=first.object.userData.observationSource;
          const mesh=source?.mesh||first.object,index=source?source.index:first.instanceId??null;
          if(parts.some(p=>p.source===mesh&&p.sourceIndex===index)){partHits++;hits++;}
        }
        if(partAttempts)coverage+=sample.area*partHits/partAttempts;
      }
      coverage=Math.min(1,coverage);
      const enough=hits>=3;
      const ok=enough&&coverage>=minCoverage;
      reports.push({...base,ok,entity_id:target.entity_id,category:target.category,visible:enough,coverage,
        distance_m:distance,visible_samples:hits,sample_count:attempts,centerDistance,priority:target.priority,
        reason:ok?'已在機載畫面中清楚辨識目標。':!inRange?'目標超出目前水下能見度，請靠近再拍。':!enough?'目標被遮擋或未清楚入鏡，請調整位置。':'目標在畫面中太小，請靠近並對準後再拍。'});
      if(ok)break;
    }
    reports.sort((a,b)=>Number(b.ok)-Number(a.ok)||a.priority-b.priority||a.centerDistance-b.centerDistance||a.distance_m-b.distance_m);
    const best=reports[0];
    if(!best)return {...base,reason:'畫面中沒有可辨識的觀察目標，請對準生物或工程目標。'};
    const {priority,centerDistance,...evidence}=best;return evidence;
  }finally{for(const proxy of proxies)proxy.geometry.dispose();}
}
