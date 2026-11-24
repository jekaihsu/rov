// Shared server habitat; older recordings fall back to decorative surroundings.
//   under water  seabed relief with sand ripples, rock outcrops, scattered steel debris,
//                kelp that sways with the current, fish schools circling the structures
//   on the surface  coastline and islands on the horizon, other vessels, navigation buoys and a
//                row of offshore wind turbines
// Everything is placed from a seeded random generator (same layout every time for a scenario)
// and kept clear of the structures, objectives and the start area, because the ROV can fly
// through these props: they must never sit where the training happens.
//
//   const env = new Environment(scene, world /* the simulator's world message */);
//   each frame: env.update(dt, camera, currentVec3 /* three-space water velocity */)
//   env.dispose()
import * as THREE from 'three';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);          // NED -> three
const M = (color, o = {}) => new THREE.MeshStandardMaterial({ color, roughness: 0.9, metalness: 0.05, ...o });

function rng(seedStr) {                                            // mulberry32 seeded by a string
  let h = 1779033703 ^ seedStr.length;
  for (let i = 0; i < seedStr.length; i++) { h = Math.imul(h ^ seedStr.charCodeAt(i), 3432918353); h = (h << 13) | (h >>> 19); }
  let a = h >>> 0;
  return () => { a |= 0; a = (a + 0x6d2b79f5) | 0; let t = Math.imul(a ^ (a >>> 15), 1 | a); t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t; return ((t ^ (t >>> 14)) >>> 0) / 4294967296; };
}

// smooth value noise (deterministic, cheap) for rocks and terrain
function hash3(x, y, z) { const s = Math.sin(x * 127.1 + y * 311.7 + z * 74.7) * 43758.5453; return s - Math.floor(s); }
function noise3(x, y, z) {
  const xi = Math.floor(x), yi = Math.floor(y), zi = Math.floor(z);
  const xf = x - xi, yf = y - yi, zf = z - zi;
  const u = xf * xf * (3 - 2 * xf), v = yf * yf * (3 - 2 * yf), w = zf * zf * (3 - 2 * zf);
  let r = 0;
  for (let dz = 0; dz < 2; dz++) for (let dy = 0; dy < 2; dy++) for (let dx = 0; dx < 2; dx++) {
    r += hash3(xi + dx, yi + dy, zi + dz) * (dx ? u : 1 - u) * (dy ? v : 1 - v) * (dz ? w : 1 - w);
  }
  return r;
}

function sandTexture() {
  const c = document.createElement('canvas'); c.width = c.height = 256;
  const g = c.getContext('2d');
  g.fillStyle = '#6d6650'; g.fillRect(0, 0, 256, 256);
  for (let y = 0; y < 256; y++) {                                  // ripples: wavy dark/light bands
    for (let x = 0; x < 256; x += 2) {
      const r = Math.sin((y + Math.sin(x * 0.05) * 6) * 0.35) * 0.5 + 0.5;
      const n = hash3(x, y, 1) * 0.25;
      const l = 0.82 + 0.28 * r + n * 0.4;
      g.fillStyle = `rgb(${Math.round(109 * l)},${Math.round(102 * l)},${Math.round(80 * l)})`;
      g.fillRect(x, y, 2, 1);
    }
  }
  const t = new THREE.CanvasTexture(c);
  t.wrapS = t.wrapT = THREE.RepeatWrapping; t.colorSpace = THREE.SRGBColorSpace;
  return t;
}

function rockGeometry(seed, detail = 2) {
  const g = new THREE.IcosahedronGeometry(1, detail);
  const p = g.attributes.position, v = new THREE.Vector3();
  for (let i = 0; i < p.count; i++) {
    v.fromBufferAttribute(p, i);
    const n = noise3(v.x * 1.7 + seed, v.y * 1.7, v.z * 1.7) * 0.55 + noise3(v.x * 4 + seed, v.y * 4, v.z * 4) * 0.18;
    v.multiplyScalar(0.72 + n);
    v.y *= 0.62;                                                   // squat, sitting on the sand
    p.setXYZ(i, v.x, v.y, v.z);
  }
  g.computeVertexNormals();
  return g;
}

function fishGeometry() {
  // a simple streamlined body (nose +Z) with a tail fin; ~0.3 m long
  const body = new THREE.SphereGeometry(0.06, 10, 6);
  body.scale(0.55, 0.8, 2.2);
  const tail = new THREE.ConeGeometry(0.05, 0.1, 4);
  tail.rotateX(Math.PI / 2); tail.scale(0.25, 1.2, 1); tail.translate(0, 0, -0.17);
  const fin = new THREE.ConeGeometry(.035, .085, 3);
  fin.scale(.2, 1, 1); fin.translate(0, .065, -.02);
  const merged = mergeGeometries([body, tail, fin]);
  return merged;
}

function mergeGeometries(list) {                                   // positions + normals only
  const geos = list.map((g) => (g.index ? g.toNonIndexed() : g));
  let n = 0; for (const g of geos) n += g.attributes.position.count;
  const pos = new Float32Array(n * 3), nrm = new Float32Array(n * 3);
  let o = 0;
  for (const g of geos) {
    g.computeVertexNormals();
    pos.set(g.attributes.position.array, o * 3); nrm.set(g.attributes.normal.array, o * 3);
    o += g.attributes.position.count;
  }
  const out = new THREE.BufferGeometry();
  out.setAttribute('position', new THREE.BufferAttribute(pos, 3));
  out.setAttribute('normal', new THREE.BufferAttribute(nrm, 3));
  for (const g of new Set([...geos, ...list])) g.dispose();
  return out;
}

function coralGeometry(variant) {
  if (variant === 0) {
    const g = new THREE.SphereGeometry(.56, 12, 8); g.scale(1, .8, 1); g.translate(0, .44, 0); return g;
  }
  const branches = [];
  const up = new THREE.Vector3(0, 1, 0);
  const stem = (a, b, radius) => {
    const direction = b.clone().sub(a);
    const g = new THREE.CylinderGeometry(radius*.65, radius, direction.length(), 5);
    g.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(up, direction.clone().normalize()));
    g.translate(...a.clone().add(b).multiplyScalar(.5).toArray()); branches.push(g);
  };
  stem(new THREE.Vector3(), new THREE.Vector3(0,.65,0), .12);
  for (let i = 0; i < 7; i++) {
    const a = i * 2.39996, h = .35 + i * .065;
    const from = new THREE.Vector3(0, h*.6, 0);
    const to = new THREE.Vector3(Math.cos(a)*.45, h, Math.sin(a)*.45);
    stem(from, to, .06);
    stem(to, to.clone().add(new THREE.Vector3(.06*Math.sin(a), .21, .06*Math.cos(a))), .04);
  }
  return mergeGeometries(branches);
}

function seastarGeometry() {
  const shape = new THREE.Shape();
  for (let i = 0; i < 10; i++) {
    const a = i*Math.PI/5, r = i % 2 ? .32 : 1;
    const x = Math.cos(a)*r, y = Math.sin(a)*r;
    if (i === 0) shape.moveTo(x,y); else shape.lineTo(x,y);
  }
  shape.closePath();
  const g = new THREE.ExtrudeGeometry(shape, {depth:.11, bevelEnabled:true, bevelThickness:.06, bevelSize:.06, bevelSegments:1, steps:1});
  g.rotateX(-Math.PI/2); g.translate(0,.03,0); return g;
}

/** Kelp blade material: the vertex shader bends each blade with height, time and the current. */
function kelpMaterial(uniforms) {
  const m = M(0x5b6b2c, { side: THREE.DoubleSide, roughness: 0.8 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = uniforms.uTime; sh.uniforms.uFlow = uniforms.uFlow;
    sh.vertexShader = 'uniform float uTime; uniform vec3 uFlow;\n' + sh.vertexShader.replace('#include <begin_vertex>', `
      #include <begin_vertex>
      float h = position.y;                                   // 0 at the root
      float ph = instanceMatrix[3].x * 0.37 + instanceMatrix[3].z * 0.53;
      float sway = sin(uTime * 0.9 + ph + h * 0.6) * 0.35 + sin(uTime * 1.7 + ph * 2.1) * 0.12;
      float bend = h * h * 1.1;                               // local units: the instance scales y to the blade height
      transformed.x += (uFlow.x * 1.2 + sway) * bend;
      transformed.z += (uFlow.z * 1.2 + sway * 0.6) * bend;
    `);
  };
  return m;
}

export class Environment {
  constructor(scene, world) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'environment';
    scene.add(this.group);
    this.t = 0;
    this.world = world;
    // Stable server identities, separate from draw buckets / instance ordering.
    // Read only at photo capture; no raycasts or observation work in update().
    this.observationTargets = [];
    this.uniforms = { uTime: { value: 0 }, uFlow: { value: new THREE.Vector3() } };
    const key = `${world.scenario?.key || 'x'}:${world.scenario?.seed ?? ''}`;
    const R = rng(key);
    this.R = R;
    this.seabedY = -world.seabed_depth;
    this.centre = P(world.start_pos || [0, 0, 0]).setY(0);
    this.spool = P(world.spool || [0, 0, 0]).setY(0);
    this._footprints(world);
    this._terrain();
    if (world.habitat) {
      this._habitat(world.habitat);
      this._sharedFish(world.habitat.fish_schools || []);
    } else {
      this._rocks(R);
      this._debris(R);
      this._kelp(R);
      this._fish(R, world);
    }
    this._surface(R);
  }

  // ── keep-clear areas (horizontal, three x/z) ───────────────────────────
  _footprints(world) {
    const F = (this.fp = []);                // {x, z, r} circles and {obb} boxes
    const add = (p, r) => F.push({ x: p.x, z: p.z, r });
    add(this.centre, 15); add(this.spool, 15);
    for (const o of world.objectives || []) add(P(o.point), 8);
    for (const ob of world.obstacles || []) {
      if (ob.type === 'cylinder') { add(P(ob.p0), ob.radius + 12); add(P(ob.p1), ob.radius + 12); add(P(ob.p0).lerp(P(ob.p1), 0.5), ob.radius + 12); }
      else if (ob.type === 'box') add(P(ob.center), Math.hypot(ob.half[0], ob.half[1]) + 12);
      else if (ob.type === 'wall') add(P(ob.point), ob.width / 2 + 12);
      else if (ob.type === 'model') {
        const a = ob.heading_deg * Math.PI / 180, [lo, hi] = ob.bounds_local;
        F.push({ obb: { o: P(ob.origin), a, lo, hi, m: 14 } });
      }
    }
  }

  _clear(x, z) {
    for (const f of this.fp) {
      if (f.obb) {
        const { o, a, lo, hi, m } = f.obb;
        // back into the model frame: local X along heading (cos a, sin a) in NED, local Y = (sin a, -cos a)
        const n = z - o.z, e = -(x - o.x);                             // three -> NED horizontal offset
        const lx = n * Math.cos(a) + e * Math.sin(a), ly = n * Math.sin(a) - e * Math.cos(a);
        if (lx > lo[0] - m && lx < hi[0] + m && ly > lo[1] - m && ly < hi[1] + m) return false;
      } else if (Math.hypot(x - f.x, z - f.z) < f.r) return false;
    }
    return true;
  }

  _spot(R, rMin, rMax, tries = 40) {
    for (let i = 0; i < tries; i++) {
      const a = R() * Math.PI * 2, r = rMin + (rMax - rMin) * Math.sqrt(R());
      const x = this.centre.x + Math.cos(a) * r, z = this.centre.z + Math.sin(a) * r;
      if (this._clear(x, z)) return new THREE.Vector3(x, this.seabedY, z);
    }
    return null;
  }

  // ── under water ───────────────────────────────────────────────────────
  _terrain() {
    if (this.world.terrain) {
      const t = this.world.terrain, [nn, ne] = t.size;
      const pos = [], indices = [], uv = [];
      for (let n=0; n<nn; n++) for(let e=0; e<ne; e++) {
        pos.push(-(t.origin[1]+e*t.spacing), -t.depths[n][e], t.origin[0]+n*t.spacing);
        uv.push(n*t.spacing/6,e*t.spacing/6);
      }
      for(let n=0;n<nn-1;n++) for(let e=0;e<ne-1;e++) {
        const a=n*ne+e,b=a+ne,c=a+1,d=b+1;
        indices.push(a,c,b,c,d,b);
      }
      const geo = new THREE.BufferGeometry();
      geo.setAttribute('position',new THREE.Float32BufferAttribute(pos,3));
      geo.setAttribute('uv',new THREE.Float32BufferAttribute(uv,2)); geo.setIndex(indices); geo.computeVertexNormals();
      const material = M(0xffffff,{map:sandTexture(),roughness:1});
      const terrain = new THREE.Mesh(geo,material);
      terrain.userData.paintable=true;terrain.receiveShadow=true; this.group.add(terrain);
      // Extend clamped edge depths, matching the server's out-of-grid sampling.
      const edge = (points, outward) => {
        const vertices=[], triangles=[], tex=[];
        points.forEach(([n,e],i)=>{
          const base=new THREE.Vector3(-(t.origin[1]+e*t.spacing),-t.depths[n][e],t.origin[0]+n*t.spacing);
          vertices.push(...base.toArray(),...base.clone().add(outward).toArray());tex.push(i,0,i,100);
          if(i<points.length-1){const k=i*2;triangles.push(k,k+1,k+2,k+1,k+3,k+2);}
        });
        const g=new THREE.BufferGeometry();g.setAttribute('position',new THREE.Float32BufferAttribute(vertices,3));
        g.setAttribute('uv',new THREE.Float32BufferAttribute(tex,2));g.setIndex(triangles);g.computeVertexNormals();
        const m=new THREE.Mesh(g,material);m.userData.paintable=true;m.material.side=THREE.DoubleSide;this.group.add(m);
      };
      edge(Array.from({length:ne},(_,e)=>[0,e]),new THREE.Vector3(0,0,-600));
      edge(Array.from({length:ne},(_,e)=>[nn-1,e]),new THREE.Vector3(0,0,600));
      edge(Array.from({length:nn},(_,n)=>[n,0]),new THREE.Vector3(600,0,0));
      edge(Array.from({length:nn},(_,n)=>[n,ne-1]),new THREE.Vector3(-600,0,0));
      return;
    }
    // flat where the physics seabed is (the operating area), rising into dunes and banks beyond
    const size = 1400, seg = 140;
    const g = new THREE.PlaneGeometry(size, size, seg, seg);
    g.rotateX(-Math.PI / 2);
    const p = g.attributes.position;
    for (let i = 0; i < p.count; i++) {
      const x = p.getX(i), z = p.getZ(i);
      const d = Math.hypot(x, z);
      const k = THREE.MathUtils.smoothstep(d, 110, 260);
      const h = (noise3(x * 0.012, 0, z * 0.012) * 9 + noise3(x * 0.04, 3, z * 0.04) * 2.5 - 4) * k + 0.02;
      p.setY(i, Math.max(h, 0.005));
    }
    g.computeVertexNormals();
    const tex = sandTexture(); tex.repeat.set(size / 6, size / 6);
    const terrain = new THREE.Mesh(g, M(0xffffff, { map: tex, roughness: 1 }));
    terrain.position.set(this.centre.x, this.seabedY, this.centre.z);
    terrain.receiveShadow = true;terrain.userData.paintable=true;
    this.group.add(terrain);
  }

  _habitat(habitat) {
    const buckets = new Map();
    for (const entity of habitat.entities || []) {
      const key = `${entity.kind}:${entity.variant}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(entity);
    }
    const matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion();
    for (const entities of buckets.values()) {
      const {kind,variant} = entities[0]; let geo, mat;
      if (kind === 'coral') {
        geo = coralGeometry(variant);
        mat = M([0x94765b,0x98785e,0x8a7c58][variant],{roughness:.94});
      } else if (kind === 'seastar') {
        geo = seastarGeometry(); mat=M([0xaf7148,0x927650,0x765e55][variant]);
      } else if (kind === 'rock') {
        geo=rockGeometry(variant*17.3); geo.translate(0,.48,0); mat=M(0x676354);
      } else {
        geo=new THREE.PlaneGeometry(kind==='seagrass'?.07:.18,1,1,7);geo.translate(0,.5,0);
        mat=kelpMaterial(this.uniforms);
        mat.color.set(kind==='seagrass'?0x53683d:0x5e643a);
      }
      const mesh = new THREE.InstancedMesh(geo,mat,entities.length);
      mesh.userData.observationEntities = entities.map(e=>({entity_id:e.id,category:e.kind}));
      if(kind==='kelp'||kind==='seagrass') mesh.userData.observationBend = this.uniforms;
      for (let i=0;i<entities.length;i++) {
        const item=entities[i], p=P(item.pos);
        rotation.setFromAxisAngle(new THREE.Vector3(0,1,0),-item.yaw*Math.PI/180);
        const scale = new THREE.Vector3(item.scale,item.scale,item.scale);
        if(kind==='kelp') scale.y*=2.3;
        if(kind==='seagrass') scale.y*=.55;
        matrix.compose(p,rotation,scale);mesh.setMatrixAt(i,matrix);
        if(['coral','seastar','kelp','seagrass'].includes(kind))
          this.observationTargets.push({entity_id:item.id,category:kind,mesh,instanceIds:[i]});
      }
      mesh.instanceMatrix.needsUpdate=true;
      mesh.receiveShadow=true;mesh.castShadow=kind==='rock'||kind==='coral';
      // Animated vertex displacement extends outside the unbent grass bounds.
      if(kind==='kelp'||kind==='seagrass')mesh.frustumCulled=false;
      else mesh.computeBoundingSphere();
      this.group.add(mesh);
    }
  }

  _sharedFish(schools) {
    this.sharedSchools=[];
    const geo=fishGeometry();
    for(const school of schools) {
      const R=rng(school.id+':'+this.world.world_seed);
      const fish=Array.from({length:school.count},()=>({offset:new THREE.Vector3((R()-.5)*2.1,(R()-.5)*.8,(R()-.5)*2.1),phase:R()*Math.PI*2,scale:.65+R()*.75}));
      const mesh=new THREE.InstancedMesh(geo,M([0x9caaa1,0x8d9784,0x94919e][school.variant],{metalness:.25,roughness:.45}),school.count);
      mesh.userData.observationEntities=fish.map(()=>({entity_id:school.id,category:'fish_school'}));
      this.observationTargets.push({entity_id:school.id,category:'fish_school',mesh,instanceIds:fish.map((_,i)=>i)});
      mesh.frustumCulled=false;this.group.add(mesh);
      this.sharedSchools.push({id:school.id,mesh,fish,pos:P(school.pos),target:P(school.pos),vel:new THREE.Vector3(0,0,.3)});
    }
  }

  _rocks(R) {
    const geos = [0, 1, 2].map((s) => rockGeometry(s * 17.3));
    const mats = [M(0x57544c), M(0x4d4a3f), M(0x625a4a)];
    const per = 40;
    const clusters = 7;
    const mesh = geos.map((g, i) => { const m = new THREE.InstancedMesh(g, mats[i], per * clusters); m.count = 0; this.group.add(m); return m; });
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), e = new THREE.Euler();
    for (let c = 0; c < clusters; c++) {
      const at = this._spot(R, 22, 140); if (!at) continue;
      const n = 8 + Math.floor(R() * 14);
      for (let k = 0; k < n; k++) {
        const x = at.x + (R() - 0.5) * 22, z = at.z + (R() - 0.5) * 22;
        if (!this._clear(x, z)) continue;
        const big = R() < 0.18 ? 2.2 + R() * 2.5 : 0.35 + R() * 1.3;
        s.set(big * (0.8 + R() * 0.5), big * (0.7 + R() * 0.6), big * (0.8 + R() * 0.5));
        q.setFromEuler(e.set((R() - 0.5) * 0.4, R() * 6.28, (R() - 0.5) * 0.4));
        m4.compose(new THREE.Vector3(x, this.seabedY + s.y * 0.25, z), q, s);
        const im = mesh[k % 3]; if (im.count < per * clusters) im.setMatrixAt(im.count++, m4);
      }
    }
    mesh.forEach((m) => { m.instanceMatrix.needsUpdate = true; });
  }

  _debris(R) {
    // steel plates, pipe spools and a coil of old cable, rusting on the seabed
    const rust = [M(0x6b3d24, { roughness: 0.95 }), M(0x55504a, { metalness: 0.3, roughness: 0.8 }), M(0x7a5a33)];
    for (let i = 0; i < 26; i++) {
      const at = this._spot(R, 14, 110); if (!at) continue;
      const kind = R();
      let m;
      if (kind < 0.45) { m = new THREE.Mesh(new THREE.BoxGeometry(1 + R() * 3, 0.04, 0.8 + R() * 2), rust[0]); m.rotation.set((R() - 0.5) * 0.5, R() * 6.28, (R() - 0.5) * 0.4); m.position.y = 0.1; }
      else if (kind < 0.8) { m = new THREE.Mesh(new THREE.CylinderGeometry(0.15 + R() * 0.25, 0.15 + R() * 0.25, 2 + R() * 6, 14, 1, true), rust[1]); m.material.side = THREE.DoubleSide; m.rotation.set(Math.PI / 2, 0, R() * 6.28); m.position.y = 0.25; }
      else { m = new THREE.Mesh(new THREE.TorusGeometry(0.7 + R() * 0.5, 0.06, 6, 28), rust[2]); m.rotation.x = Math.PI / 2; m.position.y = 0.06; }
      m.position.x = at.x; m.position.z = at.z; m.position.y += this.seabedY;
      this.group.add(m);
    }
  }

  _kelp(R) {
    const blade = new THREE.PlaneGeometry(0.22, 1, 1, 10);
    blade.translate(0, 0.5, 0);
    const count = 420;
    this.kelp = new THREE.InstancedMesh(blade, kelpMaterial(this.uniforms), count);
    this.kelp.count = 0;
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), e = new THREE.Euler();
    for (let c = 0; c < 12 && this.kelp.count < count; c++) {
      const at = this._spot(R, 16, 120); if (!at) continue;
      const n = 20 + Math.floor(R() * 30);
      for (let k = 0; k < n && this.kelp.count < count; k++) {
        const x = at.x + (R() - 0.5) * 9, z = at.z + (R() - 0.5) * 9;
        if (!this._clear(x, z)) continue;
        const h = 1.5 + R() * 4.5;
        q.setFromEuler(e.set(0, R() * 6.28, 0));
        m4.compose(new THREE.Vector3(x, this.seabedY, z), q, new THREE.Vector3(1 + R() * 0.6, h, 1));
        this.kelp.setMatrixAt(this.kelp.count++, m4);
      }
    }
    this.kelp.instanceMatrix.needsUpdate = true;
    this.kelp.frustumCulled = false;
    this.group.add(this.kelp);
  }

  _fish(R, world) {
    // schools circling near the structures (fish gather around wrecks and piles) or in open water
    const centres = [];
    for (const ob of world.obstacles || []) {
      if (ob.type === 'model') { const a = ob.heading_deg * Math.PI / 180, L = (ob.bounds_local[1][0] + ob.bounds_local[0][0]) / 2;
        centres.push(P([ob.origin[0] + Math.cos(a) * L * 0.5, ob.origin[1] + Math.sin(a) * L * 0.5, ob.origin[2] - 16]));
        centres.push(P([ob.origin[0] + Math.cos(a) * L * 1.4, ob.origin[1] + Math.sin(a) * L * 1.4, ob.origin[2] - 13])); }
      else if (ob.type === 'cylinder') centres.push(P(ob.p0).lerp(P(ob.p1), 0.35 + R() * 0.3).add(new THREE.Vector3(4, 0, 4)));
      else if (ob.type === 'box') centres.push(P(ob.center).add(new THREE.Vector3(0, ob.half[2] + 3, 0)));
    }
    while (centres.length < 3) { const s = this._spot(R, 30, 80); if (!s) break; s.y = this.seabedY * 0.5; centres.push(s); }
    const geo = fishGeometry();
    this.schools = [];
    for (const c of centres.slice(0, 4)) {
      const n = 36 + Math.floor(R() * 30);
      const mesh = new THREE.InstancedMesh(geo, M(0xaab4b8, { metalness: 0.55, roughness: 0.35 }), n);
      mesh.frustumCulled = false;
      const fish = Array.from({ length: n }, () => ({ r: 3 + R() * 5, a: R() * 6.28, y: (R() - 0.5) * 3, w: 0.25 + R() * 0.15, ph: R() * 6.28, s: 0.7 + R() * 0.8 }));
      this.group.add(mesh);
      this.schools.push({ c: c.clone(), mesh, fish, dir: R() < 0.5 ? 1 : -1 });
    }
  }

  // ── surface ───────────────────────────────────────────────────────────
  _surface(R) {
    const S = (this.surf = new THREE.Group());
    this.group.add(S);
    const c = this.centre;
    // coastline and islands on the horizon: low-poly mountains, hazed by the fog
    const rockM = M(0x5d6b5a, { flatShading: true, roughness: 1 }), cliffM = M(0x77705f, { flatShading: true, roughness: 1 });
    for (let i = 0; i < 9; i++) {
      const a = -0.6 + i * 0.28 + (R() - 0.5) * 0.12, d = 700 + R() * 380;
      const g = new THREE.ConeGeometry(60 + R() * 140, 25 + R() * 90, 9, 4);
      const p = g.attributes.position;
      for (let k = 0; k < p.count; k++) {
        const x = p.getX(k), y = p.getY(k), z = p.getZ(k);
        const n = noise3(x * 0.02 + i * 7, y * 0.03, z * 0.02) - 0.5;
        p.setXYZ(k, x * (1 + n * 0.5), y + n * 12, z * (1 + n * 0.5));
      }
      g.computeVertexNormals();
      const m = new THREE.Mesh(g, i % 3 === 0 ? cliffM : rockM);
      m.position.set(c.x + Math.cos(a) * d, g.parameters.height / 2 - 6, c.z + Math.sin(a) * d);
      m.scale.set(1, 1, 0.6 + R() * 0.6); m.rotation.y = R() * 6.28;
      S.add(m);
    }
    // offshore wind farm: a row of turbines, blades turning
    this.rotors = [];
    const white = M(0xe9eef0, { roughness: 0.5 }), yellow = M(0xf2b705, { roughness: 0.5 });
    const rowA = R() * 6.28;
    for (let i = 0; i < 6; i++) {
      const base = new THREE.Vector3(c.x + Math.cos(rowA) * 520 + Math.cos(rowA + 1.57) * (i - 2.5) * 260, 0, c.z + Math.sin(rowA) * 520 + Math.sin(rowA + 1.57) * (i - 2.5) * 260);
      const t = new THREE.Group(); t.position.copy(base); S.add(t);
      const tp = new THREE.Mesh(new THREE.CylinderGeometry(3.2, 3.2, 14, 16), yellow); tp.position.y = 5; t.add(tp);
      const tower = new THREE.Mesh(new THREE.CylinderGeometry(2.2, 3.1, 90, 16), white); tower.position.y = 57; t.add(tower);
      const nac = new THREE.Mesh(new THREE.BoxGeometry(4.5, 4.5, 13), white); nac.position.set(0, 104, -1.5); t.add(nac);
      const rotor = new THREE.Group(); rotor.position.set(0, 104, 5.5); t.add(rotor);
      rotor.add(new THREE.Mesh(new THREE.SphereGeometry(2.2, 12, 8), white));
      for (let b = 0; b < 3; b++) {
        const blade = new THREE.Mesh(new THREE.BoxGeometry(2.6, 62, 0.6), white);
        blade.geometry.translate(0, 31, 0); blade.rotation.z = b * 2.094; rotor.add(blade);
      }
      rotor.rotation.z = R() * 6.28;
      t.rotation.y = rowA + Math.PI;                               // all facing the same wind
      this.rotors.push({ rotor, w: 0.9 + R() * 0.25 });
    }
    // other vessels: simple hull + superstructure silhouettes of different sizes
    this.vessels = [];
    for (let i = 0; i < 4; i++) {
      const a = R() * 6.28, d = 160 + R() * 420, L = 18 + R() * 70;
      const v = new THREE.Group();
      const hullM = M([0x2b3a4a, 0x7a2222, 0x23313c, 0x3f5a3c][i % 4], { roughness: 0.6 });
      const hull = new THREE.Mesh(new THREE.BoxGeometry(L * 0.18, L * 0.1, L), hullM); hull.position.y = L * 0.02; v.add(hull);
      const bow = new THREE.Mesh(new THREE.ConeGeometry(L * 0.09, L * 0.22, 4), hullM); bow.rotation.set(Math.PI / 2, Math.PI / 4, 0); bow.scale.set(1, 1, 0.55); bow.position.set(0, L * 0.02, L * 0.6); v.add(bow);
      const sup = new THREE.Mesh(new THREE.BoxGeometry(L * 0.14, L * 0.12, L * 0.2), M(0xe8ebec)); sup.position.set(0, L * 0.12, -L * 0.28); v.add(sup);
      v.position.set(c.x + Math.cos(a) * d, 0, c.z + Math.sin(a) * d); v.rotation.y = R() * 6.28;
      S.add(v);
      this.vessels.push({ v, ph: R() * 6.28, speed: (R() < 0.5 ? 0 : 1.5 + R() * 3) });
    }
    // navigation buoys (cardinal/lateral colours) around the work site
    this.buoys = [];
    const cols = [0xf2c200, 0xc62828, 0x2e7d32, 0xf2c200];
    for (let i = 0; i < 5; i++) {
      const a = i * 1.26 + R() * 0.4, d = 70 + R() * 90;
      const b = new THREE.Group();
      const m = M(cols[i % 4], { roughness: 0.5 });
      const float = new THREE.Mesh(new THREE.CylinderGeometry(0.9, 1.1, 1.6, 16), m); b.add(float);
      const mast = new THREE.Mesh(new THREE.CylinderGeometry(0.12, 0.12, 2.6, 8), m); mast.position.y = 2; b.add(mast);
      const top = new THREE.Mesh(new THREE.ConeGeometry(0.5, 0.8, 12), M(0x222222)); top.position.y = 3.5; b.add(top);
      const lamp = new THREE.Mesh(new THREE.SphereGeometry(0.16, 8, 6), new THREE.MeshBasicMaterial({ color: 0xfff1a8 })); lamp.position.y = 4.05; b.add(lamp);
      b.position.set(c.x + Math.cos(a) * d, 0, c.z + Math.sin(a) * d);
      S.add(b);
      this.buoys.push({ b, lamp, ph: R() * 6.28 });
    }
  }

  // ── per frame ─────────────────────────────────────────────────────────
  update(dt, camera, flow = null, state = null) {
    this.t = Number.isFinite(state?.t) ? state.t : this.t + dt;
    const t = this.t;
    this.uniforms.uTime.value = t;
    if (flow) this.uniforms.uFlow.value.lerp(flow, 1 - Math.exp(-dt));
    const under = camera.position.y < 0;
    this.surf.visible = !under || camera.position.y > -6;          // horizon props only near the surface
    for (const { rotor, w } of this.rotors) rotor.rotation.z -= dt * w;
    for (const b of this.buoys) { b.b.position.y = Math.sin(t * 1.1 + b.ph) * 0.25; b.b.rotation.z = Math.sin(t * 0.9 + b.ph) * 0.08; b.lamp.visible = (t + b.ph) % 4 < 0.6; }
    for (const v of this.vessels) {
      v.v.position.y = Math.sin(t * 0.6 + v.ph) * 0.3;
      if (v.speed) { const f = new THREE.Vector3(0, 0, 1).applyQuaternion(v.v.quaternion); v.v.position.addScaledVector(f, v.speed * dt); }
    }
    // fish: each circles its school centre with its own radius, height and speed; tails wag
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), s = new THREE.Vector3(), p = new THREE.Vector3(), e = new THREE.Euler();
    const schools = state?.environment?.fish_schools || [];
    for(const school of this.sharedSchools || []) {
      const live=schools.find(x=>x.id===school.id);
      if(live){school.target.copy(P(live.pos));school.vel.copy(P(live.vel));}
      school.pos.lerp(school.target,1-Math.exp(-dt*12));
      school.mesh.visible=school.pos.distanceTo(camera.position)<55;
      if(!school.mesh.visible)continue;
      const heading=Math.atan2(school.vel.x,school.vel.z);
      school.fish.forEach((f,i)=>{
        p.copy(school.pos).add(f.offset);
        p.y+=Math.sin(t*1.7+f.phase)*.12;
        q.setFromEuler(e.set(0,heading+Math.sin(t*6+f.phase)*.07,Math.sin(t*5+f.phase)*.04));
        s.setScalar(f.scale);m4.compose(p,q,s);school.mesh.setMatrixAt(i,m4);
      });
      school.mesh.instanceMatrix.needsUpdate=true;
    }
    for (const sc of this.schools || []) {
      if (sc.c.distanceTo(camera.position) > 60) continue;         // out of sight: skip the work
      sc.fish.forEach((f, i) => {
        f.a += dt * f.w * sc.dir;
        const r = f.r + Math.sin(t * 0.3 + f.ph) * 1.2;
        p.set(sc.c.x + Math.cos(f.a) * r, sc.c.y + f.y + Math.sin(t * 0.5 + f.ph) * 0.6, sc.c.z + Math.sin(f.a) * r);
        const heading = -f.a - (sc.dir > 0 ? 0 : Math.PI);
        q.setFromEuler(e.set(0, heading, Math.sin(t * 9 + f.ph) * 0.12));
        s.setScalar(f.s);
        m4.compose(p, q, s); sc.mesh.setMatrixAt(i, m4);
      });
      sc.mesh.instanceMatrix.needsUpdate = true;
    }
  }

  dispose() {
    this.scene.remove(this.group);
    const geometries=new Set(),materials=new Set(),textures=new Set();
    this.group.traverse((o)=>{if(o.geometry)geometries.add(o.geometry);if(o.material)for(const m of(Array.isArray(o.material)?o.material:[o.material]))materials.add(m);});
    for(const m of materials){for(const value of Object.values(m))if(value?.isTexture)textures.add(value);m.dispose();}
    for(const g of geometries)g.dispose();for(const t of textures)t.dispose();
  }
}
