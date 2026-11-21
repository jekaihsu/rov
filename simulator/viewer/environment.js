// Shared server habitat; older recordings fall back to decorative surroundings.
//   under water  seabed with a per-site material (seabed.js), rock outcrops, scattered steel debris,
//                kelp that sways with the current, fish schools circling the structures, kelp and
//                anemones on structures; marine meshes come from marine_registry.js
//   on the surface  surface_set.js: an offshore wind farm where the site has one, distant land where the
//                site is near shore, other vessels and navigation buoys
// Everything is placed from a seeded random generator (same layout every time for a scenario)
// and kept clear of the structures, objectives and the start area, because the ROV can fly
// through these props: they must never sit where the training happens.
//
//   const env = new Environment(scene, world /* the simulator's world message */, {detail: 'low'|'medium'|'high'});
//   each frame: env.update(dt, camera, currentVec3 /* three-space water velocity */, state, flowField)
//   env.dispose()
import * as THREE from 'three';
import { KELP_FLOW_GLSL, createKelpFlowUniforms, updateKelpFlow } from './kelp_flow.js';
import {marineGeometry, upgradeMarineMesh} from './marine_registry.js';
import {createSharedSchools} from './fish_schools.js';
import {installReefDressing, reefCoralGeometry, reefCoralMaterial, reefCoralStyle, reefCoralTint} from './reef_life.js';
import {seabedMaterial, siteProfile} from './seabed.js';
import {HABITAT_ROCKS, habitatRockGeometry, rockLod, upgradeRockMesh} from './scan_materials.js';
import {buildSurfaceSet} from './surface_set.js';
import {installDiscoveryDetails} from './discovery_details.js';

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

/** Kelp blade material: the vertex shader bends each blade with height, time and the current. */
function kelpMaterial(uniforms) {
  const m = M(0x5b6b2c, { side: THREE.DoubleSide, roughness: 0.8 });
  m.onBeforeCompile = (sh) => {
    sh.uniforms.uTime = uniforms.uTime; sh.uniforms.uFlow = uniforms.uFlow;
    sh.uniforms.uFlowGrid = uniforms.uFlowGrid; sh.uniforms.uFlowBox = uniforms.uFlowBox;
    const header = 'uniform float uTime; uniform vec3 uFlow;\n' + KELP_FLOW_GLSL;
    sh.vertexShader = header + sh.vertexShader.replace('#include <begin_vertex>', `
      #include <begin_vertex>
      float h = position.y;                                   // 0 at the root
      float ph = instanceMatrix[3].x * 0.37 + instanceMatrix[3].z * 0.53;
      vec3 flow = kelpFlow(vec2(instanceMatrix[3].x, instanceMatrix[3].z));   // host flow at the root
      float sway = (sin(uTime * 0.9 + ph + h * 0.6) * 0.35 + sin(uTime * 1.7 + ph * 2.1) * 0.12) * kelpStir(flow);
      float bend = h * h * 1.1;                               // local units: the instance scales y to the blade height
      transformed.x += (flow.x * 1.2 + sway) * bend;
      transformed.z += (flow.z * 1.2 + sway * 0.6) * bend;
    `);
  };
  return m;
}

export class Environment {
  constructor(scene, world, options = {}) {
    this.scene = scene;
    this.group = new THREE.Group();
    this.group.name = 'environment';
    scene.add(this.group);
    this.t = 0;
    this.world = world;
    this.detail = options.detail || 'medium';
    // Stable server identities, separate from draw buckets / instance ordering.
    // Read only at photo capture; no raycasts or observation work in update().
    this.observationTargets = [];
    this.uniforms = { uTime: { value: 0 }, uFlow: { value: new THREE.Vector3() }, ...createKelpFlowUniforms() };
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
      this._sharedFish();
      this.reef = installReefDressing(this.group, world, this.detail);
    } else {
      this._rocks(R);
      this._debris(R);
      this._kelp(R);
      this._fish(R, world);
    }
    this.discoveries = installDiscoveryDetails(this.group, world, this.observationTargets);
    this._structureLife(world, options.detail || 'medium');
    this._surface(R);
  }

  // ── sessile life on structures: kelp in the top metres, anemones deeper (registry kinds, no collision) ──
  _structureLife(world, detail) {
    const counts = {low: [0, 0], medium: [0, 0], high: [48, 22]}[detail] || [0, 0];   // structure life on high only
    const hosts = (world.obstacles || []).filter((ob) => ob.type === 'cylinder' &&
      ['jacket_leg', 'pile', 'monopile', 'transition_piece'].includes(ob.kind));
    if (!hosts.length || !counts[0]) return;
    const R = rng(`life:${world.scenario?.key || 'x'}`);
    const kelp = [];
    const anemones = [];
    for (const ob of hosts) {
      const a = P(ob.p0), b = P(ob.p1);
      const dir = b.clone().sub(a).normalize();
      const length = a.distanceTo(b);
      for (let i = 0; i < counts[0] + counts[1]; i++) {
        const t = R();
        const p = a.clone().addScaledVector(dir, t * length);
        const depth = -p.y;
        const angle = R() * Math.PI * 2;
        const out = new THREE.Vector3(Math.cos(angle), 0, Math.sin(angle));
        p.addScaledVector(out, ob.radius + 0.01);
        if (i < counts[0] && depth > 0.8 && depth < 7) kelp.push({p, out, s: .5 + R() * .9, yaw: R() * 6.28});
        else if (i >= counts[0] && depth > 14 && depth < this.world.seabed_depth - 1) {
          anemones.push({p, out, s: .07 + R() * .08});
        }
      }
    }
    const m4 = new THREE.Matrix4(), q = new THREE.Quaternion(), up = new THREE.Vector3(0, 1, 0);
    if (kelp.length) {
      const mesh = new THREE.InstancedMesh(marineGeometry('kelp'), kelpMaterial(this.uniforms), kelp.length);
      mesh.material.color.set(0x5e6236);
      kelp.forEach((k, i) => {
        q.setFromAxisAngle(up, k.yaw);
        m4.compose(k.p, q, new THREE.Vector3(1, k.s * 1.6, 1));
        mesh.setMatrixAt(i, m4);
      });
      mesh.frustumCulled = false;
      mesh.userData.structureLife = 'kelp';
      upgradeMarineMesh(mesh, 'kelp', 0).catch(() => false);
      this.group.add(mesh);
    }
    if (anemones.length) {
      const mesh = new THREE.InstancedMesh(marineGeometry('anemone'), M(0xe4dccb, { roughness: .9 }), anemones.length);
      anemones.forEach((k, i) => {
        q.setFromUnitVectors(up, k.out);
        m4.compose(k.p, q, new THREE.Vector3(k.s, k.s, k.s));
        mesh.setMatrixAt(i, m4);
      });
      mesh.computeBoundingSphere();
      mesh.userData.structureLife = 'anemone';
      upgradeMarineMesh(mesh, 'anemone', 0).catch(() => false);
      this.group.add(mesh);
    }
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
      else if (ob.type === 'ship_hull') add(P(ob.center), ob.length / 2 + 12);
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
      const material = seabedMaterial(siteProfile(this.world), this.detail);
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
    const terrain = new THREE.Mesh(g, seabedMaterial(siteProfile(this.world), this.detail));
    terrain.position.set(this.centre.x, this.seabedY, this.centre.z);
    terrain.receiveShadow = true;terrain.userData.paintable=true;
    this.group.add(terrain);
  }

  _habitat(habitat) {
    const buckets = new Map();
    for (const entity of habitat.entities || []) {
      const key = `${entity.kind}:${entity.kind === 'coral' ? reefCoralStyle(entity) : entity.variant}`;
      if (!buckets.has(key)) buckets.set(key, []);
      buckets.get(key).push(entity);
    }
    const matrix = new THREE.Matrix4(), rotation = new THREE.Quaternion();
    for (const entities of buckets.values()) {
      const {kind,variant} = entities[0]; let geo, mat;
      if (kind === 'coral') {
        geo = reefCoralGeometry(reefCoralStyle(entities[0]), this.detail);
        mat = reefCoralMaterial(reefCoralStyle(entities[0]));
      } else if (kind === 'seastar') {
        geo = marineGeometry('seastar', variant); mat=M([0xaf7148,0x927650,0x765e55][variant]);
      } else if (kind === 'rock') {
        geo=rockGeometry(variant*17.3); geo.translate(0,.48,0); mat=M(0x676354);
      } else {
        geo=marineGeometry(kind, variant);
        mat=kelpMaterial(this.uniforms);
        mat.color.set(kind==='seagrass'?0x53683d:0x5e643a);
      }
      const mesh = new THREE.InstancedMesh(geo,mat,entities.length);
      if(kind!=='rock')upgradeMarineMesh(mesh,kind,variant).catch(()=>false);
      else upgradeRockMesh(mesh, (rocks) => habitatRockGeometry(rocks, variant, this.detail), this.detail)
        .catch(() => false);
      mesh.userData.observationEntities = entities.map(e=>({entity_id:e.id,category:e.kind}));
      if(kind==='kelp'||kind==='seagrass') mesh.userData.observationBend = this.uniforms;
      for (let i=0;i<entities.length;i++) {
        const item=entities[i], p=P(item.pos);
        rotation.setFromAxisAngle(new THREE.Vector3(0,1,0),-item.yaw*Math.PI/180);
        const scale = new THREE.Vector3(item.scale,item.scale,item.scale);
        if(kind==='kelp') scale.y*=2.3;
        if(kind==='seagrass') scale.y*=.55;
        matrix.compose(p,rotation,scale);mesh.setMatrixAt(i,matrix);
        if (kind === 'coral') mesh.setColorAt(i, reefCoralTint(item));
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

  _sharedFish() {
    // Server schools drawn as swimming, schooling fish (fish_schools.js); one instanced mesh per school.
    this.fishSchools = createSharedSchools(this.group, this.world, this.detail, this.world.world_seed);
    this.sharedSchools = this.fishSchools.schools;
    this.observationTargets.push(...this.fishSchools.observationTargets);
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
        // visual only (no collider): stones up to 0.6 m, never boulders the vehicle would fly through
        const big = R() < 0.18 ? 0.45 + R() * 0.15 : 0.15 + R() * 0.3;
        s.set(big * (0.8 + R() * 0.5), big * (0.7 + R() * 0.6), big * (0.8 + R() * 0.5));
        q.setFromEuler(e.set((R() - 0.5) * 0.4, R() * 6.28, (R() - 0.5) * 0.4));
        m4.compose(new THREE.Vector3(x, this.seabedY + s.y * 0.25, z), q, s);
        const im = mesh[k % 3]; if (im.count < per * clusters) im.setMatrixAt(im.count++, m4);
      }
    }
    mesh.forEach((m) => { m.instanceMatrix.needsUpdate = true; });
    const lod = rockLod(this.detail);
    mesh.forEach((m, i) => upgradeRockMesh(m, (rocks) => rocks.geometry(HABITAT_ROCKS[i], lod), this.detail)
      .catch(() => false));
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
    const geo = marineGeometry('fish');
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

  // ── surface: wind farm, coastline, vessels and buoys (surface_set.js) ─────
  _surface(R) {
    const set = buildSurfaceSet(this.world, this.centre, R, {detail: this.detail, time: this.uniforms.uTime});
    this.surf = set.group;
    this.group.add(set.group);
    this.rotors = [];                                              // rotors turn in the farm's vertex shader
    this.vessels = set.vessels;
    this.buoys = set.buoys;
  }

  // ── per frame ─────────────────────────────────────────────────────────
  update(dt, camera, flow = null, state = null, flowField = null) {
    this.t = Number.isFinite(state?.t) ? state.t : this.t + dt;
    const t = this.t;
    this.discoveries?.update(camera);
    this.reef?.update(t, this.fishSchools?.vehicle);
    this.uniforms.uTime.value = t;
    if (flow) this.uniforms.uFlow.value.lerp(flow, 1 - Math.exp(-dt));
    updateKelpFlow(this.uniforms, flowField, this.uniforms.uFlow.value, -this.seabedY, performance.now());
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
    this.fishSchools?.update(dt, t, camera, state);
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
    this.discoveries?.dispose();
    this.scene.remove(this.group);
    const geometries=new Set(),materials=new Set(),textures=new Set();
    this.group.traverse((o)=>{if(o.geometry)geometries.add(o.geometry);if(o.material)for(const m of(Array.isArray(o.material)?o.material:[o.material]))materials.add(m);});
    for(const m of materials){for(const value of Object.values(m))if(value?.isTexture)textures.add(value);m.dispose();}
    for(const g of geometries)g.dispose();for(const t of textures)t.dispose();
  }
}
