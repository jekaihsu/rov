// Vehicle visuals use Three coordinates (-starboard, -down, forward), metres.
import * as THREE from 'three';
import { loadGLTF } from './glb.js';
import { PayloadRig } from './tool_visuals.js';
import { createRov01IndustrialMesh, ROV01_LIVERY_PALETTES, resolveRov01Livery } from './rov01_mesh.js';

const point = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const defaults = {
  rov01: { id: 'rov01', model: 'procedural://rov-01', livery: 'cyber_cyan', camera_body: [.28, 0, .01], lamp_body: [[.27, -.13, .01], [.27, .13, .01]], gland_body: [-.29, 0, -.04], arm_mount_body: [.27, 0, .12] },
  rov02_heavy: { id: 'rov02_heavy', model: 'procedural://rov-02-heavy', camera_body: [.245, 0, -.015], lamp_body: [[.24, -.18, -.09], [.24, .18, -.09]], gland_body: [-.2, 0, -.15], arm_mount_body: [.18, 0, .15] },
  rov01_pro: { id: 'rov01_pro', model: 'procedural://rov-01-pro', camera_body: [.485, 0, -.175], lamp_body: [[.418, -.225, .025], [.418, .225, .025]], gland_body: [-.25, 0, -.27], arm_mount_body: [.30, -.12, .40] },
};

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
  root.attach(joints[0]);
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

/** Load an independent vehicle instance. Lighting intentionally lives outside root. */
export async function createVehicleModel(definition='rov01') {
  const rawId=typeof definition==='string'?definition:definition?.id || 'rov01';
  const id=defaults[rawId]?rawId:'rov01';
  const def={...(defaults[id] || defaults.rov01),...(typeof definition==='object'?definition:{})};
  const root=new THREE.Group(); root.name=`Vehicle ${id}`;
  let model, loadError=null, rov01Instance=null;
  const isProceduralRov01 = id==='rov01' || !def.model || String(def.model).startsWith('procedural://');
  const initialLivery = def.livery || 'cyber_cyan';
  if (isProceduralRov01) {
    rov01Instance = createRov01IndustrialMesh({ livery: initialLivery });
    model = rov01Instance.root;
  } else {
    try { model=(await loadGLTF(def.model)).scene; }
    catch(e) { loadError=e; rov01Instance=createRov01IndustrialMesh({ livery: initialLivery }); model=rov01Instance.root; }
  }
  root.add(model); root.updateMatrixWorld(true);
  const rotors=[];
  model.traverse((o) => {
    if(o.userData.role!=='rotor') return;
    const worldQ=o.getWorldQuaternion(new THREE.Quaternion());
    let axis;
    if(Number.isInteger(o.userData.thruster_index)) {
      const t=def.thrusters?.[o.userData.thruster_index];
      axis=t?point(t.axis).applyQuaternion(worldQ.clone().invert()).normalize():new THREE.Vector3(1,0,0);
    } else axis=new THREE.Vector3(...(o.userData.axis || [1,0,0])).applyQuaternion(worldQ.clone().invert()).normalize();
    rotors.push({o,base:o.quaternion.clone(),axis,pos:o.getWorldPosition(new THREE.Vector3()),ang:0,thrusterIndex:o.userData.thruster_index});
  });
  const arm=id==='rov01_pro'?(bindModelArm(root,model) || manipulator(def.arm_mount_body)):null;
  if(arm && arm.root.parent!==root) root.add(arm.root);
  const lampAnchors=(def.lamp_body || []).map((p) => ({position:point(p),direction:new THREE.Vector3(0,-.055,1).normalize()}));
  const payload=new PayloadRig(root,id);
  return {root,model,rotors,arm,definition:def,loadError,lampAnchors,payload,
    cameraAnchor:point(def.camera_body),tetherAnchor:point(def.gland_body),
    updatePayload:(loadout,states,armState,time)=>{if(loadout){if(arm)arm.root.visible=false;payload.update(loadout,states,armState,time);}},
    updateArm:(state) => arm?.update(state),
    livery: rov01Instance?.livery || initialLivery,
    setLivery: (nextLivery) => rov01Instance?.setLivery?.(nextLivery),
    updateThrusters: rov01Instance?.updateThrusters,
    dispose:() => {payload.dispose();disposeTree(root);}};
}
export { ROV01_LIVERY_PALETTES, resolveRov01Livery };
