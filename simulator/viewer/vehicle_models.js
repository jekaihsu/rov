// Vehicle visuals use Three coordinates (-starboard, -down, forward), metres.
import * as THREE from 'three';
import { loadGLTF } from './glb.js';
import { genericVehicleUrl } from './asset_config.js';

const point = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const defaults = {
  x1: { id: 'x1', model: 'models/rov.glb', camera_body: [.39, 0, -.03], lamp_body: [[.36, -.12, .02], [.36, .12, .02]], gland_body: [-.38, 0, -.06], arm_mount_body: [.27, 0, .16] },
  bluerov2_heavy: { id: 'bluerov2_heavy', model: 'models/bluerov2_heavy.glb', camera_body: [.245, 0, -.015], lamp_body: [[.24, -.18, -.09], [.24, .18, -.09]], gland_body: [-.2, 0, -.15], arm_mount_body: [.18, 0, .15] },
  falcon: { id: 'falcon', model: 'models/falcon.glb', camera_body: [.485, 0, -.175], lamp_body: [[.418, -.225, .025], [.418, .225, .025]], gland_body: [-.25, 0, -.27], arm_mount_body: [.30, -.12, .40] },
};

// Fleet LODs (nearest first). Distances are metres from the camera. Close inspection
// (under about 12 m) stays on LOD0; peers pass options.lod >= 1 and start further out.
const FLEET_LODS = {
  x1: [
    { url: 'models/rov.glb', distance: 0 },
    { url: 'models/rov_lod1.glb', distance: 12 },
    { url: 'models/rov_lod2.glb', distance: 40 },
  ],
  bluerov2_heavy: [
    { url: 'models/bluerov2_heavy.glb', distance: 0 },
    { url: 'models/bluerov2_heavy_lod1.glb', distance: 14 },
    { url: 'models/bluerov2_heavy_lod2.glb', distance: 42 },
  ],
  falcon: [
    { url: 'models/falcon.glb', distance: 0 },
    { url: 'models/falcon_lod1.glb', distance: 16 },
    { url: 'models/falcon_lod2.glb', distance: 48 },
  ],
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

function collectRotors(model, def) {
  const rotors = [];
  model.traverse((o) => {
    if (o.userData.role !== 'rotor') return;
    const worldQ = o.getWorldQuaternion(new THREE.Quaternion());
    let axis;
    if (Number.isInteger(o.userData.thruster_index)) {
      // Blender +Z local spin axis is glTF +Y after export's axis conversion.
      const t = def.thrusters?.[o.userData.thruster_index];
      axis = t
        ? point(t.axis).applyQuaternion(worldQ.clone().invert()).normalize()
        : new THREE.Vector3(0, 1, 0);
    } else {
      axis = new THREE.Vector3(...(o.userData.axis || [0, 0, 1]))
        .applyQuaternion(worldQ.clone().invert())
        .normalize();
    }
    rotors.push({
      o,
      base: o.quaternion.clone(),
      axis,
      pos: o.getWorldPosition(new THREE.Vector3()),
      ang: 0,
      thrusterIndex: o.userData.thruster_index,
    });
  });
  return rotors;
}

function findRotorNodes(root) {
  const rotors = [];
  root.traverse((o) => {
    if (o.userData.role === 'rotor') rotors.push(o);
  });
  return rotors;
}

function disposeObject(object) {
  object.traverse((o) => {
    o.geometry?.dispose?.();
    for (const material of [].concat(o.material || [])) {
      material?.dispose?.();
    }
  });
  object.removeFromParent();
}

function usesCgFrame(root) {
  let found = false;
  root.traverse((object) => {
    if (object.userData && object.userData.frame === 'cg') found = true;
  });
  return found;
}

/**
 * Detach a subtree and free its geometries. Materials stay: a stripped arm or
 * rotor often shares them with the hull that remains in that same GLB.
 */
function dropTree(object) {
  object.traverse((node) => {
    node.geometry?.dispose?.();
  });
  object.removeFromParent();
}

function stripNamed(scene, name) {
  const found = [];
  scene.traverse((object) => {
    if (object.name === name) found.push(object);
  });
  for (const object of found) dropTree(object);
}

/**
 * Load one fleet vehicle's LOD files into a THREE.LOD. Rotors (and Model V's
 * arm) are lifted out of every level and kept at the nearest loaded detail, so
 * they keep spinning and articulating when the hull drops a level. minLod >= 1
 * skips nearer static levels so peer vehicles start further out.
 */
async function loadFleetLod(id, minLod = 0) {
  const table = FLEET_LODS[id];
  const start = Math.max(0, Math.min(minLod, table.length - 1));
  const candidates = table.slice(start);
  const loaded = [];
  for (const level of candidates) {
    try {
      loaded.push({ level, gltf: await loadGLTF(level.url) });
    } catch (error) {
      if (loaded.length === 0) throw error;
      console.warn(`Vehicle LOD unavailable (${level.url}); using ${loaded.length} level(s)`, error);
      break;
    }
  }
  const wrap = new THREE.Group();
  wrap.name = `${id}Visual`;
  const rotorRoot = new THREE.Group();
  rotorRoot.name = `${id}Rotors`;
  wrap.add(rotorRoot);

  const liftNearest = (scene) => {
    scene.updateMatrixWorld(true);
    for (const rotor of findRotorNodes(scene)) {
      rotorRoot.attach(rotor);
    }
  };

  const stripFar = (scene) => {
    for (const rotor of findRotorNodes(scene)) dropTree(rotor);
    stripNamed(scene, 'arm_yaw');
  };

  if (loaded.length === 1) {
    const scene = loaded[0].gltf.scene;
    liftNearest(scene);
    wrap.add(scene);
    return wrap;
  }

  const lod = new THREE.LOD();
  lod.name = `${id}LOD`;
  loaded.forEach((entry, index) => {
    const scene = entry.gltf.scene;
    scene.name = `LOD${start + index}`;
    if (index === 0) liftNearest(scene);
    else stripFar(scene);
    const distance = index === 0 ? 0 : entry.level.distance;
    lod.addLevel(scene, distance);
  });
  wrap.add(lod);
  return wrap;
}

// Centre the pre-I1 rov.glb had under the loose (per-mesh) Box3: its sheared node scales inflated the box to
// 0.600 x 0.415 x 0.790 m around this point, while the true geometry is 0.560 x 0.400 x 0.790 m. The packed LODs
// keep the true geometry, so reuse the old centre instead of measuring (and never rescale the mesh).
const TRAINING_X1_LEGACY_CENTRE = [0, 0.1925, -0.01008];

function legacyX1Centre(model, loadError) {
  if (!loadError) return new THREE.Vector3(...TRAINING_X1_LEGACY_CENTRE);
  return new THREE.Box3().setFromObject(model).getCenter(new THREE.Vector3());
}

/**
 * Load an independent vehicle instance. Lighting intentionally lives outside root.
 * options.assets ('training' | 'generic') overrides the ?assets= query; options.lod picks a LOD.
 */
export async function createVehicleModel(definition='x1', options={}) {
  const id=typeof definition==='string'?definition:definition.id || 'x1';
  const def={...(defaults[id] || defaults.x1),...(typeof definition==='object'?definition:{})};
  const root=new THREE.Group(); root.name=`Vehicle ${id}`;
  const genericUrl = genericVehicleUrl(id, options.lod ?? 0, options.assets);
  // Generic visuals are authored about the CG with explicit thruster_index extras, like the fleet GLBs.
  const legacyX1 = id === 'x1' && !genericUrl;
  if (genericUrl) def.model = genericUrl;
  let model, loadError=null;
  try {
    if (!genericUrl && FLEET_LODS[id]) model = await loadFleetLod(id, options.lod ?? 0);
    else model = (await loadGLTF(def.model)).scene;
  } catch (e) {
    loadError = e;
    console.warn(`Vehicle model ${id} unavailable; using fallback`, e);
    model = fallback(id);
  }
  // Older training X1 files were not centred on the CG. A rebuilt file marks
  // itself with frame=cg and is left on the origin, like the other two vehicles.
  const cgFrame = usesCgFrame(model);
  if (legacyX1 && !cgFrame) model.position.sub(legacyX1Centre(model, loadError));
  root.add(model); root.updateMatrixWorld(true);
  const rotors = collectRotors(model, def);
  const indexed = rotors.length > 0 && rotors.every((rotor) => Number.isInteger(rotor.thrusterIndex));
  if (legacyX1 && !indexed) matchLegacyRotors(rotors, def.thrusters);
  const arm=id==='falcon'?(bindModelArm(root,model) || manipulator(def.arm_mount_body)):null;
  if(arm && arm.root.parent!==root) root.add(arm.root);
  const lampAnchors=(def.lamp_body || []).map((p) => ({position:point(p),direction:new THREE.Vector3(0,-.055,1).normalize()}));
  const cameraGimbal = model.getObjectByName('camera_gimbal') || null;
  const lampPivots = [0, 1].map((i) => model.getObjectByName(`lamp_pivot_${i}`)).filter(Boolean);
  return {root,model,rotors,arm,definition:def,loadError,lampAnchors,cameraGimbal,lampPivots,
    cameraAnchor:point(def.camera_body),tetherAnchor:point(def.gland_body),
    updateArm:(state) => arm?.update(state), dispose:() => disposeTree(root)};
}
