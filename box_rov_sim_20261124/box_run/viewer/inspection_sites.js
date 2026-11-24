// Original procedural reconstruction from the references in docs/subsea-inspection-references.md.
// Manifest dimensions are shared with server collision shapes. Small fasteners,
// fouling and scratches are decorative; no reference photograph is embedded.
import * as THREE from 'three';

const P = p => new THREE.Vector3(-p[1], -p[2], p[0]);
const UP = new THREE.Vector3(0, 1, 0);
const COLORS = {steel:0x525a57,concrete:0x88867a,cable:0x222a29,polymer:0x968946,
  yellow:0xb2a252,pipe:0x655f4c,anode:0x929b91,pile:0x444b42,rust:0x755243,
  rubber:0x252e2c,rock:0x737266,grout:0x918875,rope:0x5b6857,fouling:0x737e60,
  dark:0x292e28,paint:0xcbcbb1,oxide:0x44372a,exposed:0x59615b};

function random(seed=193781) {
  return () => { seed = Math.imul(seed ^ seed >>> 15, 1 | seed); seed ^= seed + Math.imul(seed ^ seed >>> 7, 61 | seed); return ((seed ^ seed >>> 14) >>> 0) / 4294967296; };
}

function weatherTexture() {
  // Single reusable, original 128px texture: mottled mineral deposits and pits.
  const c=document.createElement('canvas');c.width=c.height=128;
  const ctx=c.getContext('2d'), rng=random(346789), data=ctx.createImageData(128,128);
  for(let y=0;y<128;y++)for(let x=0;x<128;x++) {
    const noise=rng(),grain=Math.sin(x*.39+Math.sin(y*.21))*Math.cos(y*.33)*9;
    const v=Math.round(204+noise*38+grain),o=(y*128+x)*4;
    data.data[o]=v;data.data[o+1]=v;data.data[o+2]=v-3;data.data[o+3]=255;
  }
  ctx.putImageData(data,0,0);
  for(let i=0;i<115;i++) {
    ctx.fillStyle=`rgba(63,65,48,${.04+rng()*.18})`;
    ctx.beginPath();ctx.ellipse(rng()*128,rng()*128,1+rng()*9,.5+rng()*3,rng()*6.28,0,6.28);ctx.fill();
  }
  const t=new THREE.CanvasTexture(c);t.colorSpace=THREE.SRGBColorSpace;
  t.wrapS=t.wrapT=THREE.RepeatWrapping;t.anisotropy=2;return t;
}

/** Build all static objects once. targets contain only photographed physical geometry. */
export function buildInspectionSite(scene, manifest) {
  if(!manifest?.geometry?.length)return {group:null,targets:[],dispose(){}};
  const group=new THREE.Group();group.name=`inspection-site:${manifest.key}`;scene.add(group);
  const texture=weatherTexture(), mats={};
  for(const [key,color] of Object.entries(COLORS)) mats[key]=new THREE.MeshStandardMaterial({
    color,map:texture,roughness:key==='anode'?.82:.94,metalness:key==='steel'?.24:key==='anode'?.35:.04});
  const geo={box:new THREE.BoxGeometry(1,1,1),cylinder:new THREE.CylinderGeometry(1,1,1,16),
    bolt:new THREE.CylinderGeometry(1,1,1,6),pebble:new THREE.IcosahedronGeometry(1,0),
    sphere:new THREE.SphereGeometry(1,10,6),ring:new THREE.TorusGeometry(1,.095,5,16)};
  // A double tapered mattress block reproduces the interlinked waisted form
  // visible in the SPS loadout photo, rather than a rectangular tile grid.
  geo.mattress=new THREE.LatheGeometry([
    new THREE.Vector2(.28,-.5),new THREE.Vector2(.5,-.25),new THREE.Vector2(.43,0),
    new THREE.Vector2(.5,.25),new THREE.Vector2(.28,.5)],4);
  geo.mattress.rotateY(Math.PI/4);
  const batches=new Map(), scars=new Map(),extraGeometries=[],targetGroups=new Map(), rng=random(428561);
  for(const t of manifest.targets||[]) {
    const g=new THREE.Group();g.name=t.entity_id;g.userData.entity_id=t.entity_id;
    group.add(g);targetGroups.set(t.entity_id,g);
  }
  function enqueue(shape,material,matrix,entity=null) {
    const parent=targetGroups.get(entity)||group;
    const key=`${entity||'ambient'}:${shape}:${material}`;
    let batch=batches.get(key);if(!batch){batch={shape,material,parent,matrices:[]};batches.set(key,batch);}
    batch.matrices.push(matrix);
  }
  function box(p,size,material='steel',entity=null,rotation=0,shape='box') {
    const q=new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0,1,0),rotation);
    enqueue(shape,material,new THREE.Matrix4().compose(P(p),q,new THREE.Vector3(size[1],size[2],size[0])),entity);
  }
  function cylinder(a,b,r,material='steel',entity=null,shape='cylinder') {
    const pa=P(a),pb=P(b),d=pb.clone().sub(pa),q=new THREE.Quaternion().setFromUnitVectors(UP,d.clone().normalize());
    enqueue(shape,material,new THREE.Matrix4().compose(pa.add(pb).multiplyScalar(.5),q,new THREE.Vector3(r,d.length(),r)),entity);
  }
  function ball(p,size,material='rust',entity=null) {box(p,size,material,entity,0,'sphere');}
  function loop(p,r,material='steel',entity=null,normal=[0,0,1]) {
    const q=new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),P(normal).normalize());
    enqueue('ring',material,new THREE.Matrix4().compose(P(p),q,new THREE.Vector3(r,r,r)),entity);
  }
  function along(item,t) {return item.p0.map((v,k)=>v+(item.p1[k]-v)*t);}
  function scar(cx,cz,sx,sz,material,entity,seed,surface) {
    // A zero-thickness, ragged material boundary conforming to the real steel
    // surface. Unlike flattened spheres these never look like raised coins.
    const key=`${entity}:${material}`,r=random(seed),count=36,phase=r()*6.28;
    let batch=scars.get(key);
    if(!batch){batch={material,entity,positions:[],uv:[]};scars.set(key,batch);}
    const edge=[];
    for(let i=0;i<count;i++) {
      const angle=i/count*Math.PI*2;
      const radial=.72+.13*Math.sin(angle*3+phase)+.09*Math.sin(angle*7-phase)+.12*r();
      edge.push([cx+Math.cos(angle)*sx*radial,cz+Math.sin(angle)*sz*radial]);
    }
    const vertex=([n,d])=>{
      const p=P([n,surface(d),d]);batch.positions.push(p.x,p.y,p.z);
      batch.uv.push(n*3,d*3);
    };
    for(let i=0;i<count;i++) {vertex([cx,cz]);vertex(edge[i]);vertex(edge[(i+1)%count]);}
  }
  function rings(item,interval=.7,thickness=.045,material='steel',radiusScale=1.07) {
    const length=P(item.p0).distanceTo(P(item.p1)),n=Math.max(1,Math.floor(length/interval));
    const tangent=item.p1.map((v,k)=>(v-item.p0[k])/length);
    for(let i=0;i<=n;i++) {
      const c=along(item,(i+.15)/(n+.3)),a=c.map((v,k)=>v-tangent[k]*thickness/2),b=c.map((v,k)=>v+tangent[k]*thickness/2);
      cylinder(a,b,item.radius*radiusScale,material,item.entity_id);
    }
  }
  function boltsOnBox(item) {
    const [x,y,z]=item.center,[l,w,h]=item.size;
    for(const dx of [-l*.4,l*.4])for(const dz of [-h*.37,0,h*.37])
      cylinder([x+dx,y-w/2-.015,z+dz],[x+dx,y-w/2-.05,z+dz],.035,'steel',item.entity_id,'bolt');
  }
  function foulingCylinder(item,count=30) {
    const axis=P(item.p1).sub(P(item.p0)).normalize();
    const u=new THREE.Vector3().crossVectors(axis,Math.abs(axis.y)>.9?new THREE.Vector3(1,0,0):UP).normalize();
    const v=new THREE.Vector3().crossVectors(axis,u);
    for(let i=0;i<count;i++) {
      const t=.03+rng()*.94,a=rng()*Math.PI*2,r=item.radius+.01;
      const c=P(along(item,t)).addScaledVector(u,Math.cos(a)*r).addScaledVector(v,Math.sin(a)*r);
      if(c.y>-.1)continue;
      const scale=.018+rng()*.043;
      const matrix=new THREE.Matrix4().compose(c,new THREE.Quaternion(),new THREE.Vector3(scale,scale*.48,scale));
      enqueue('pebble','fouling',matrix); // decorative fauna, not photo target or collision.
    }
  }
  for(const item of manifest.geometry) {
    const e=item.entity_id,mat=item.material||'steel';
    if(item.type==='cylinder') {
      cylinder(item.p0,item.p1,item.radius,mat,e);
      if(['pipe','pile','brace'].includes(item.detail))foulingCylinder(item,item.detail==='pile'?85:34);
      if(item.detail==='pipe')rings(item,5,.045,'dark',1.025);
      if(item.detail==='restrictor') {
        rings(item,.34,.22,'polymer',1.17);rings(item,.34,.025,'dark',1.18);
        const n=14;
        for(let i=0;i<n;i++) {
          const p=along(item,(i+.5)/n);
          ball([p[0],p[1]-item.radius*1.13,p[2]],[.035,.015,.045],'steel',e);
        }
      }
      if(item.detail==='flange') {
        rings(item,.22,.12,'steel',1.03);
        for(let i=0;i<12;i++) {
          const a=i*Math.PI/6,y=Math.cos(a)*.41,z=Math.sin(a)*.41;
          cylinder([item.p0[0]-.055,y,item.p0[2]+z],[item.p1[0]+.055,y,item.p0[2]+z],.038,'anode',e,'bolt');
        }
      }
      if(item.detail==='anode') {
        rings(item,.65,.04,'steel',1.04);
        for(let i=0;i<22;i++) {
          const p=along(item,rng()),a=rng()*Math.PI*2;
          ball([p[0],p[1]+Math.cos(a)*item.radius,p[2]+Math.sin(a)*item.radius],[.1,.06,.07],i%3?'anode':'dark',e);
        }
      }
      if(e?.endsWith('-sheath')) {
        // Local surface scuff, not glowing damage or exposed live conductors.
        for(let i=0;i<8;i++)ball([30+(rng()-.5)*.65,-.08,17.73+(rng()-.5)*.06],[.12,.012,.022],'paint',e);
      }
      if(e?.endsWith('-coating')) {
        const z0=20.95,local=random(73051);
        const surface=offset=>z=>-Math.sqrt(Math.max(.001,.305*.305-(z-z0)**2))-offset;
        // One irregular coating holiday plus a smaller, disconnected scar.
        scar(10,z0,.61,.185,'oxide',e,74311,surface(.007));
        scar(9.97,z0-.006,.49,.145,'exposed',e,74311,surface(.011));
        scar(10.74,z0+.07,.14,.065,'oxide',e,87231,surface(.007));
        for(let i=0;i<52;i++) {
          const a=local()*6.28,edge=i<34;
          const x=10+Math.cos(a)*(edge?.45+local()*.18:local()*.45);
          const z=z0+Math.sin(a)*(edge?.13+local()*.04:local()*.11);
          scar(x,z,.008+local()*.027,.005+local()*.015,i%3?'oxide':'dark',e,74000+i,surface(.014));
        }
      }
    } else {
      const [x,y,z]=item.center,[l,w,h]=item.size;
      if(item.detail==='mattress') {
        const nx=8,ny=5;
        for(let a=0;a<nx;a++)for(let b=0;b<ny;b++) {
          const edge=a===nx-1&&b===0,px=x-l/2+(a+.5)*l/nx,py=y-w/2+(b+.5)*w/ny;
          box([px,py,z-(edge?.14:0)],[l/nx*.91,w/ny*.92,h],mat,e,edge?.09:0,'mattress');
        }
        for(let b=0;b<ny;b++)cylinder([x-l/2-.1,y-w/2+(b+.5)*w/ny,z],[x+l/2+.1,y-w/2+(b+.5)*w/ny,z],.018,'rope',e);
        for(let a=0;a<nx;a++)cylinder([x-l/2+(a+.5)*l/nx,y-w/2-.1,z],[x-l/2+(a+.5)*l/nx,y+w/2+.1,z],.018,'rope',e);
        for(const dx of [-l/2+.3,l/2-.3])loop([x+dx,y-w/2-.06,z],.13,'rope',e);
      } else if(item.detail==='grille') {
        // Open physical bars, with a conservative plate collision proxy. The
        // dark backing sits behind the bars inside the intake headwall.
        box([x,y+.03,z],[l,.04,h],'dark',e);
        for(let i=0;i<=10;i++) {
          const px=x-l/2+i*l/10,bend=i===4?.1:0;
          cylinder([px,y-.055,z-h/2],[px+bend,y-.07,z],.025,'steel',e);
          cylinder([px+bend,y-.07,z],[px,y-.055,z+h/2],.025,'steel',e);
        }
        for(const dz of [-h/2,h/2])box([x,y-.06,z+dz],[l+.12,.13,.1],'steel',e);
        for(const dx of [-l/2,l/2])box([x+dx,y-.06,z],[.1,.13,h],'steel',e);
        // A small snagged rope/net panel. Thin enough not to block the grille.
        for(let i=0;i<6;i++) {
          const px=x-.8+i*.17;
          cylinder([px,y-.105,z-.65],[px+.24,y-.13,z+.08],.008,'rope',e);
          cylinder([x-.8,y-.12,z-.65+i*.14],[x+.3,y-.12,z-.46+i*.14],.008,'rope',e);
        }
      } else if(item.detail==='skid') {
        for(const dx of [-l/2+.08,l/2-.08])box([x+dx,y,z],[.16,w,h],mat,e);
        for(const dy of [-w/2+.08,w/2-.08])box([x,y+dy,z],[l,.16,h],mat,e);
        for(let i=0;i<8;i++)box([x-l*.43+i*l*.123,y,z+.03],[.06,w*.9,.08],mat,e);
      } else if(item.detail==='rock') {
        box(item.center,item.size,mat,e,rng()*2,'pebble');
      } else {
        box(item.center,item.size,item.detail==='repair'?'pile':mat,e);
        if(['cabinet','repair','pile_anode'].includes(item.detail))boltsOnBox(item);
        if(item.detail==='sandbag') {
          for(let i=0;i<5;i++)cylinder([x-l*.49,y-w*.51,z-h*.4+i*h*.19],[x+l*.49,y-w*.51,z-h*.4+i*h*.19],.012,'dark');
        }
        if(item.detail==='cabinet') {
          box([x,y-w*.506,z],[l*.63,.015,h*.55],'steel');
          box([x,y-w*.52,z],[l*.57,.012,h*.47],'yellow');
          for(const dx of [-l*.33,l*.33])loop([x+dx,y,z-h*.58],.12,'steel',null,[0,1,0]);
        }
        if(item.detail==='valve') {
          cylinder([x,y,z-h*.5],[x,y,z-h*.5-.32],.055,'steel');
          loop([x,y,z-h*.5-.35],.37,'yellow',null,[0,0,1]);
          cylinder([x-.34,y,z-h*.5-.35],[x+.34,y,z-h*.5-.35],.025,'yellow');
          cylinder([x,y-.34,z-h*.5-.35],[x,y+.34,z-h*.5-.35],.025,'yellow');
        }
        if(item.detail==='fender') {
          for(const dx of [-l*.4,l*.4])cylinder([x+dx,y+.2,z-h*.45],[x+dx,y-.25,z-h*.3],.022,'steel');
          for(let i=0;i<4;i++)box([x,y-w*.506,z-h*.32+i*h*.21],[l*.82,.025,.035],'dark');
        }
        if(item.detail==='repair') {
          for(const dz of [-h*.4,h*.4])box([x,y-w*.515,z+dz],[l*1.05,.055,.09],'steel',e);
          const local=random(904173),surface=()=>y-w/2-.008;
          for(let i=0;i<7;i++)scar(x+(local()-.5)*l*.76,z+(local()-.5)*h*.75,
            .12+local()*.14,.08+local()*.2,'oxide',e,5800+i,surface);
          for(let i=0;i<65;i++)scar(x+(local()-.5)*l*.91,z+(local()-.5)*h*.87,
            .005+local()*.017,.005+local()*.025,i%5?'oxide':'exposed',e,5900+i,()=>y-w/2-.012);
        }
        if(item.detail==='pile_anode') {
          for(let i=0;i<15;i++)ball([x+(rng()-.5)*l*.86,y-w*.55,z+(rng()-.5)*h*.8],[.1,.035,.09],'dark',e);
        }
        if(item.detail==='cracked') {
          const pts=[[x-1.8,y+.6,z-h*.5-.006],[x-.8,y+.3,z-h*.5-.006],
            [x-.2,y-.15,z-h*.5-.006],[x+.55,y-.45,z-h*.5-.006],[x+1.5,y-.8,z-h*.5-.006]];
          for(let i=1;i<pts.length;i++)cylinder(pts[i-1],pts[i],.014,'dark',e);
          for(let i=0;i<14;i++)box([x-2.05-rng()*.3,y-1.5+rng()*3,z+.12],[.06+rng()*.18,.06+rng()*.14,.08],'rock',null,rng()*3,'pebble');
        }
        if(item.detail==='deck') {
          for(const dy of [-w*.45,w*.45]) {
            for(let i=0;i<17;i++)cylinder([x-l*.47+i*l*.0587,y+dy,z-h/2],[x-l*.47+i*l*.0587,y+dy,z-h/2-1.1],.025,'steel');
            for(const dz of [.55,1.1])cylinder([x-l*.47,y+dy,z-h/2-dz],[x+l*.47,y+dy,z-h/2-dz],.025,'steel');
          }
          for(let i=0;i<8;i++)box([x-l*.4+i*l*.115,y,z-h/2-.004],[.025,w,.006],'dark');
          for(const px of [x-l*.35,x+l*.35]) {
            cylinder([px,y-w*.35,z-h/2],[px,y-w*.35,z-h/2-.55],.12,'steel');
            cylinder([px-.28,y-w*.35,z-h/2-.42],[px+.28,y-w*.35,z-h/2-.42],.08,'steel');
          }
        }
      }
    }
  }
  // Ground contact details stay small and outside the manoeuvring strip. They
  // add sediment scale without creating large invisible collision obstacles.
  const d=manifest.seabed_depth;
  for(let i=0;i<160;i++) {
    const x=1+rng()*42,y=(rng()<.5?-1:1)*(3.8+rng()*5.5),s=.015+rng()*.075;
    box([x,y,d-s*.3],[s*2,s*1.4,s*.6],i%4?'rock':'fouling',null,rng()*6,'pebble');
  }
  for(const b of batches.values()) {
    const mesh=new THREE.InstancedMesh(geo[b.shape],mats[b.material],b.matrices.length);
    b.matrices.forEach((m,i)=>mesh.setMatrixAt(i,m));mesh.instanceMatrix.needsUpdate=true;
    mesh.computeBoundingSphere();mesh.name=`site:${b.shape}:${b.material}`;
    mesh.castShadow=false;mesh.receiveShadow=true;b.parent.add(mesh);
  }
  for(const b of scars.values()) {
    const geometry=new THREE.BufferGeometry();
    geometry.setAttribute('position',new THREE.Float32BufferAttribute(b.positions,3));
    geometry.setAttribute('uv',new THREE.Float32BufferAttribute(b.uv,2));
    geometry.computeVertexNormals();extraGeometries.push(geometry);
    const mesh=new THREE.Mesh(geometry,mats[b.material]);mesh.name=`surface-loss:${b.entity}`;
    // NED conversion preserves handedness; constructed triangles face the
    // inspected negative-East side. No transparency/alpha sorting required.
    (targetGroups.get(b.entity)||group).add(mesh);
  }
  group.updateMatrixWorld(true);
  const targets=(manifest.targets||[]).map(t=>({entity_id:t.entity_id,category:'engineering',
    mesh:targetGroups.get(t.entity_id),label:t.label}));
  return {group,targets,dispose(){
    scene.remove(group);for(const g of [...Object.values(geo),...extraGeometries])g.dispose();
    for(const m of Object.values(mats))m.dispose();texture.dispose();
    group.traverse(o=>{if(o.isInstancedMesh)o.dispose();});group.clear();
  }};
}
