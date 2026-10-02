import * as THREE from 'three';
import {createVehicleModel} from './vehicle_models.js';
import {Cable} from './cable.js';
import {applyVehicleSticker} from './vehicle_stickers.js';
const P=(p)=>new THREE.Vector3(-p[1],-p[2],p[0]);
const Q=q=>new THREE.Quaternion(-q[2],-q[3],q[1],q[0]);
export class Fleet {
  constructor(scene){this.scene=scene;this.peers=new Map();this.objects=new Map();this.world=null;this.rotorRotation=new THREE.Quaternion();}
  reset(world){this.world=world;for(const peer of this.peers.values())this.disposePeer(peer);this.peers.clear();for(const mesh of this.objects.values()){this.scene.remove(mesh);mesh.geometry.dispose();mesh.material.dispose();}this.objects.clear();}
  disposePeer(p){p.dead=true;p.model?.dispose();this.scene.remove(p.root,p.cable.mesh);p.cable.geometry.dispose();p.cable.mesh.material.dispose();}
  ingest(s){
    const seen=new Set();
    for(const v of s.vehicles||[]){
      const id=v.id||v.vehicle_id;if(id===s.vehicle_id)continue;seen.add(id);
      let p=this.peers.get(id);
      if(p&&p.modelId!==v.model_id){this.disposePeer(p);this.peers.delete(id);p=null;}
      if(!p){
        const root=new THREE.Group();this.scene.add(root);
        const cable=new Cable(new THREE.MeshStandardMaterial({color:0xe4bd32,roughness:.8}),{segments:90,radial:5});this.scene.add(cable.mesh);
        p={root,cable,modelId:v.model_id,samples:[],dead:false,lights:[]};this.peers.set(id,p);
        const def=this.world?.vehicle_catalogue?.find(d=>d.id===v.model_id)||{id:v.model_id,model:'models/rov.glb'};
        createVehicleModel(def).then(model=>{if(p.dead){model.dispose();return;}p.model=model;p.root.add(model.root);});
        for(const anchor of def.lamp_body||[[.36,-.12,.02],[.36,.12,.02]]){
          const light=new THREE.SpotLight(0xfff2dc,0,22,.5,.55,1.3);light.position.copy(P(anchor));light.target.position.copy(light.position).add(new THREE.Vector3(0,-.25,6));root.add(light,light.target);p.lights.push(light);
        }
      }
      p.state=v;p.cableDirty=true;p.samples.push({time:s.t,pos:P(v.pos),q:Q(v.q)});if(p.samples.length>8)p.samples.shift();p.received=performance.now();
      if(p.samples.length===1){p.root.position.copy(P(v.pos));p.root.quaternion.copy(Q(v.q));}
    }
    for(const[id,p]of this.peers)if(!seen.has(id)){this.disposePeer(p);this.peers.delete(id);}
    const visible=new Set();
    for(const ob of s.operations?.objects||[]){
      visible.add(ob.id);let mesh=this.objects.get(ob.id);
      if(!mesh){mesh=new THREE.Mesh(new THREE.CylinderGeometry(ob.radius,ob.radius,ob.radius*1.8,12),new THREE.MeshStandardMaterial({color:ob.mass>10?0x555d61:ob.mass>2?0xd09130:0xc9dadb,metalness:.45,roughness:.5}));this.scene.add(mesh);this.objects.set(ob.id,mesh);}
      mesh.position.copy(P(ob.pos));
    }
    for(const[id,mesh]of this.objects)if(!visible.has(id)){this.scene.remove(mesh);mesh.geometry.dispose();mesh.material.dispose();this.objects.delete(id);}
  }
  update(dt){
    for(const p of this.peers.values()){
      const frames=p.samples;if(!frames.length)continue;
      const t=frames.at(-1).time+Math.min(.1,(performance.now()-p.received)/1000)-.1;
      let a=frames[0],b=frames.at(-1);for(let i=1;i<frames.length;i++)if(frames[i].time>=t){a=frames[i-1];b=frames[i];break;}
      const k=Math.max(0,Math.min(1,(t-a.time)/Math.max(.001,b.time-a.time)));
      p.root.position.lerpVectors(a.pos,b.pos,k);p.root.quaternion.slerpQuaternions(a.q,b.q,k);
      p.model?.updateArm(p.state.operations?.arm);
      applyVehicleSticker(p.model,p.state.appearance?.sticker||'none');
      for(const rotor of p.model?.rotors||[]){rotor.ang+=(p.state.thrust?.[rotor.thrusterIndex]||0)*dt*40;rotor.o.quaternion.copy(rotor.base).multiply(this.rotorRotation.setFromAxisAngle(rotor.axis,rotor.ang));}
      const led=p.state.rc?.right_switch||0;p.lights.forEach(l=>l.intensity=led===2?38:led===1?14:0);
      // Network nodes stay unchanged between packets; avoid rebuilding the same
      // tube geometry on every display frame while hull interpolation continues.
      if(p.cableDirty){p.cable.update((p.state.tether?.nodes||[]).map(P));p.cableDirty=false;}
    }
  }
}
