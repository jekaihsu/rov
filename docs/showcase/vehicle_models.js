// Vehicle visuals use Three coordinates (-starboard, -down, forward), metres.
import * as THREE from 'three';
import { loadGLTF } from './glb.js';

const point = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const defaults = {
  x1: { id: 'x1', model: 'models/rov.glb', camera_body: [.39, 0, -.03], lamp_body: [[.36, -.12, .02], [.36, .12, .02]], gland_body: [-.38, 0, -.06], arm_mount_body: [.27, 0, .16] },
  bluerov2_heavy: { id: 'bluerov2_heavy', model: 'models/bluerov2_heavy.glb', camera_body: [.245, 0, -.015], lamp_body: [[.24, -.18, -.09], [.24, .18, -.09]], gland_body: [-.2, 0, -.15], arm_mount_body: [.18, 0, .15] },
  falcon: { id: 'falcon', model: 'models/falcon.glb', camera_body: [.485, 0, -.175], lamp_body: [[.418, -.225, .025], [.418, .225, .025]], gland_body: [-.25, 0, -.27], arm_mount_body: [.30, -.12, .40] },
};

function matchLegacyRotors(rotors, thrusters) {
  // Legacy X1 exports have swapped L/R names, so use the original spatial match.
  const positions=(thrusters?.map((t)=>t.pos) || [[.250,-.193,.032],[.250,.193,.032],[-.251,-.171,-.035],[-.251,.171,-.035],[-.061,-.205,.068],[-.061,.205,.068]]).map(point);
  if(positions.length!==rotors.length) return;
  const mean=(a)=>a.reduce((s,p)=>s.add(p),new THREE.Vector3()).divideScalar(a.length);
  const centre=mean(positions), rotorCentre=mean(rotors.map((r)=>r.pos));
  const a=positions.map((p)=>p.clone().sub(centre)), b=rotors.map((r)=>r.pos.clone().sub(rotorCentre));
  let best=null,bestCost=Infinity; const used=new Set(), candidate=[];
  function visit(i,cost) {
    if(cost>=bestCost) return;
    if(i===a.length){best=candidate.slice();bestCost=cost;return;}
    for(let j=0;j<b.length;j++) if(!used.has(j)) {
      used.add(j);candidate.push(j);visit(i+1,cost+a[i].distanceToSquared(b[j]));candidate.pop();used.delete(j);
    }
  }
  visit(0,0);best?.forEach((rotorIndex,thrusterIndex)=>{rotors[rotorIndex].thrusterIndex=thrusterIndex;});
}

function disposeTree(root) {
  const geometries = new Set(), materials = new Set(), textures = new Set();
  root.traverse((o) => {
    if (o.geometry) geometries.add(o.geometry);
    for (const m of (Array.isArray(o.material) ? o.material : o.material ? [o.material] : [])) {
      materials.add(m);
      for (const value of Object.values(m)) if (value?.isTexture) textures.add(value);
    }
  });
  geometries.forEach((g) => g.dispose()); materials.forEach((m) => m.dispose()); textures.forEach((t) => t.dispose());
  root.removeFromParent();
}

function manipulator(mount) {
  const root = new THREE.Group(); root.name = 'Sampling manipulator'; root.position.copy(point(mount));
  const steel = new THREE.MeshStandardMaterial({ color: 0x71838d, metalness: .8, roughness: .3 });
  const dark = new THREE.MeshStandardMaterial({ color: 0x20282e, metalness: .3, roughness: .45 });
  const accent = new THREE.MeshStandardMaterial({ color: 0xb58d30, metalness: .2, roughness: .5 });
  function link(parent, length) {
    for (const x of [-.023, .023]) {
      const bar = new THREE.Mesh(new THREE.BoxGeometry(.025, .032, length), steel);
      bar.position.set(x, 0, length / 2); parent.add(bar);
    }
    const actuator = new THREE.Mesh(new THREE.CylinderGeometry(.016, .016, length * .8, 12), dark);
    actuator.rotation.x = Math.PI/2; actuator.position.set(0,.024,length*.45); parent.add(actuator);
  }
  function hinge(parent, z) {
    const joint = new THREE.Group(); joint.position.z = z; parent.add(joint);
    const pin = new THREE.Mesh(new THREE.CylinderGeometry(.037, .037, .080, 20), accent);
    pin.rotation.z = Math.PI/2; joint.add(pin); return joint;
  }
  const yaw = new THREE.Group(); root.add(yaw);
  const base = new THREE.Mesh(new THREE.CylinderGeometry(.06,.07,.045,24), dark); yaw.add(base);
  const shoulder=hinge(yaw,0); link(shoulder,.32);
  const elbow=hinge(shoulder,.32); link(elbow,.30);
  const wrist=hinge(elbow,.30); link(wrist,.12);
  const jaws=[];
  for (const sign of [-1,1]) {
    const jaw=new THREE.Group(); jaw.position.z=.075; wrist.add(jaw);
    const finger=new THREE.Mesh(new THREE.BoxGeometry(.015,.036,.09), steel); finger.position.z=.04; jaw.add(finger);
    const tip=new THREE.Mesh(new THREE.BoxGeometry(.03,.03,.018), dark); tip.position.set(-sign*.01,0,.087); jaw.add(tip);
    jaws.push({jaw,sign});
  }
  const tip=new THREE.Object3D(); tip.position.z=.12; wrist.add(tip);
  const update=(state={}) => {
    root.visible = state.available !== false;
    const j=state.joints || [0,-15,30,-15], deg=Math.PI/180;
    // Server arm bend is positive toward FRD down (Three -Y), yaw toward starboard.
    yaw.rotation.y = -(j[0] || 0)*deg;
    shoulder.rotation.x = (j[1] || 0)*deg; elbow.rotation.x=(j[2] || 0)*deg; wrist.rotation.x=(j[3] || 0)*deg;
    const opening=THREE.MathUtils.clamp(state.grip ?? 1,0,1);
    for (const {jaw,sign} of jaws) jaw.position.x=sign*(.008+opening*.045);
  };
  update(); return {root,joints:[yaw,shoulder,elbow,wrist],jaws,tip,update};
}

function bindModelArm(root, model) {
  const names=['arm_yaw','arm_shoulder','arm_elbow','arm_wrist'];
  const joints=names.map((name)=>model.getObjectByName(name));
  if(joints.some((joint)=>!joint))return null;
  const jaws=['arm_jaw_left','arm_jaw_right'].map((name)=>model.getObjectByName(name));
  const tip=model.getObjectByName('arm_tip');
  root.attach(joints[0]); // Keep the manipulator visible when onboard hides the hull.
  const update=(state={})=>{
    joints[0].visible=state.available!==false;
    const angles=state.joints || [0,-15,30,-15],rad=Math.PI/180;
    joints[0].rotation.set(0,-(angles[0]||0)*rad,0);
    for(let i=1;i<4;i++)joints[i].rotation.set((angles[i]||0)*rad,0,0);
    const opening=THREE.MathUtils.clamp(state.grip??1,0,1);
    jaws.forEach((jaw,i)=>{if(jaw)jaw.position.x=(i===0?1:-1)*(.009+opening*.035);});
  };
  update();return {root:joints[0],joints,jaws,tip,update};
}

function fallback(id) {
  const root=new THREE.Group();
  const metal=new THREE.MeshStandardMaterial({color:0x45505a,metalness:.6,roughness:.4});
  const buoy=new THREE.MeshStandardMaterial({color:id==='bluerov2_heavy'?0x1676b9:0xe8b827,roughness:.55});
  const L=id==='falcon'?.86:.48, W=id==='falcon'?.50:.35;
  for(const x of [-W/2,W/2]) {
    const pod=new THREE.Mesh(new THREE.BoxGeometry(.12,.10,L*.85),buoy); pod.position.set(x,.16,0); root.add(pod);
    for(const z of [-L*.4,L*.4]) {const rail=new THREE.Mesh(new THREE.BoxGeometry(.025,.33,.025),metal);rail.position.set(x,0,z);root.add(rail);}
    const skid=new THREE.Mesh(new THREE.BoxGeometry(.035,.03,L),metal);skid.position.set(x,-.17,0);root.add(skid);
  }
  const housing=new THREE.Mesh(new THREE.CylinderGeometry(.065,.065,L*.8,24),metal);housing.rotation.x=Math.PI/2;root.add(housing);
  return root;
}

/** Load an independent vehicle instance. Lighting intentionally lives outside root. */
export async function createVehicleModel(definition='x1') {
  const id=typeof definition==='string'?definition:definition.id || 'x1';
  const def={...(defaults[id] || defaults.x1),...(typeof definition==='object'?definition:{})};
  const root=new THREE.Group(); root.name=`Vehicle ${id}`;
  let model, loadError=null;
  try { model=(await loadGLTF(def.model)).scene; }
  catch(e) { loadError=e; console.warn(`Vehicle model ${id} unavailable; using fallback`,e); model=fallback(id); }
  // Preserve the legacy X1 centring convention; fleet GLBs are authored about CG.
  if(id==='x1') { const box=new THREE.Box3().setFromObject(model); model.position.sub(box.getCenter(new THREE.Vector3())); }
  root.add(model); root.updateMatrixWorld(true);
  const rotors=[];
  model.traverse((o) => {
    if(o.userData.role!=='rotor') return;
    const worldQ=o.getWorldQuaternion(new THREE.Quaternion());
    let axis;
    if(Number.isInteger(o.userData.thruster_index)) {
      // Blender +Z local spin axis is glTF +Y after export's axis conversion.
      const t=def.thrusters?.[o.userData.thruster_index];
      axis=t?point(t.axis).applyQuaternion(worldQ.clone().invert()).normalize():new THREE.Vector3(0,1,0);
    } else axis=new THREE.Vector3(...(o.userData.axis || [0,0,1])).applyQuaternion(worldQ.clone().invert()).normalize();
    rotors.push({o,base:o.quaternion.clone(),axis,pos:o.getWorldPosition(new THREE.Vector3()),ang:0,thrusterIndex:o.userData.thruster_index});
  });
  if(id==='x1') matchLegacyRotors(rotors,def.thrusters);
  const arm=id==='falcon'?(bindModelArm(root,model) || manipulator(def.arm_mount_body)):null;
  if(arm && arm.root.parent!==root) root.add(arm.root);
  const lampAnchors=(def.lamp_body || []).map((p) => ({position:point(p),direction:new THREE.Vector3(0,-.055,1).normalize()}));
  return {root,model,rotors,arm,definition:def,loadError,lampAnchors,
    cameraAnchor:point(def.camera_body),tetherAnchor:point(def.gland_body),
    updateArm:(state) => arm?.update(state), dispose:() => disposeTree(root)};
}
