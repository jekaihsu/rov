import * as THREE from 'three';
import {loadGLTF} from './glb.js';
import {toolCatalogue,toolsById} from './loadout_store.js';
const P=p=>new THREE.Vector3(-p[1],-p[2],p[0]);
export async function createTool(id){
  const def=toolsById.get(id);
  let root;
  try {
    root = (await loadGLTF(def.model)).scene;
  } catch {
    root = new THREE.Group();
    const dims = def?.dimensions_m || [0.18, 0.08, 0.08];
    const mesh = new THREE.Mesh(
      new THREE.BoxGeometry(dims[1], dims[2], dims[0]),
      new THREE.MeshStandardMaterial({ color: def?.color || '#38bdf8', metalness: 0.55, roughness: 0.35 })
    );
    root.add(mesh);
  }
  const named=new Map();root.traverse(o=>{named.set(o.name,o);o.userData.tool=true;if(o.isMesh){o.castShadow=true;o.receiveShadow=true;}});
  let light;
  const dots=[];
  if(id==='laser')for(const x of [-.05,.05]){const dot=new THREE.Mesh(new THREE.SphereGeometry(.007,8,6),new THREE.MeshBasicMaterial({color:0x56ff78}));dot.position.x=x;dot.visible=false;root.add(dot);dots.push(dot);}
  if(id==='light'){light=new THREE.SpotLight(0xe2f5ff,30,20,.65,.65,2);light.position.set(0,0,def.dimensions_m[0]);light.target.position.set(0,0,3);root.add(light,light.target);}
  function update(s={},arm={}){
    const phase=s.phase??0,opening=s.grip??(id==='sediment'?1-(s.progress||0):arm.grip??.65);
    for(const [name,sign] of [['tool_jaw_left',-1],['tool_jaw_right',1]]){const o=named.get(name);if(o)o.rotation.y=sign*opening*.40;}
    const j=arm.joints||s.joints||[0,-15,30,-15];
    ['tool_yaw','tool_shoulder','tool_elbow','tool_wrist'].forEach((n,i)=>{const o=named.get(n);if(o){if(i===0)o.rotation.y=-j[i]*Math.PI/180;else o.rotation.x=j[i]*Math.PI/180;}});
    const rotor=named.get('tool_scanner');if(rotor)rotor.rotation.y=phase;
    const valve=named.get('tool_valve');if(valve)valve.rotation.z=(s.progress||0)*Math.PI*.5;
    const fluid=named.get('tool_sample');if(fluid){fluid.visible=(s.progress||0)>0;fluid.scale.z=Math.max(.02,s.progress||0);}
    if(light)light.intensity=s.enabled===false?0:40*(s.level??.7);
    dots.forEach((dot,i)=>{const d=s.ranges?.[i];dot.visible=s.enabled!==false&&Number.isFinite(d)&&d<12;if(dot.visible)dot.position.z=d;});
    for(const name of ['tool_led','tool_emitter']){const o=named.get(name);if(o?.material){o.material.emissiveIntensity=s.enabled===false?0:.4+(s.level??.7);}}
  }
  return {root,def,update,named,dispose(){root.traverse(o=>{o.geometry?.dispose();if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());});root.removeFromParent();}};
}
export class PayloadRig{
 constructor(parent,model){this.parent=parent;this.model=model;this.items=new Map();this.signature='';this.generation=0;this.dead=false;this.errors=[];}
 update(loadout,states={},arm={},time=0){
   if(!loadout)return;
   const signature=JSON.stringify(loadout);
   if(signature!==this.signature){this.signature=signature;const generation=++this.generation;for(const t of this.items.values())t.dispose();this.items.clear();this.errors=[];
     for(const item of loadout){const mount=toolCatalogue.vehicles[this.model].mounts.find(m=>m.id===item.slot);if(!mount)continue;
       createTool(item.tool).then(t=>{if(this.dead||generation!==this.generation){t.dispose();return;}t.root.position.copy(P(mount.position));if(['altimeter','ins'].includes(item.tool))t.root.rotation.x=Math.PI/2;this.parent.add(t.root);this.items.set(item.tool,t);}).catch(e=>{if(this.dead||generation!==this.generation)return;this.errors.push(`${item.tool}: ${e.message}`);console.error('工具模型載入失敗',item.tool,e);});
     }
   }
   for(const [id,t]of this.items)t.update({...states[id],phase:time*.9},arm);
 }
 dispose(){this.dead=true;this.generation++;for(const t of this.items.values())t.dispose();this.items.clear();}
}
