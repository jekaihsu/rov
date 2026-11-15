// Original collision-derived cable site. Texture grime is procedural, never photographic.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {buildPenPart} from './aquaculture.js';
const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
export function cableMaterial(kind) {
  const colors = {route_cable: 0x333832, route_damage: 0x96917c, route_concrete: 0x777669,
    route_star: 0x806e54, route_urchin: 0x46433a, route_steel: 0x575449,
    route_sign: 0xaaa995, route_rope: 0x686353, route_trace: 0x514f43};
  const material = new THREE.MeshStandardMaterial({color: colors[kind], roughness: .94});
  material.userData.structureKind = kind;
  if (typeof document !== 'undefined' && kind !== 'route_sign') {
    const texture = new THREE.TextureLoader().load('models/cable_route/weathering.webp');
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.SRGBColorSpace;
    material.map = texture;
    material.bumpMap = texture;
    material.bumpScale = kind === 'route_concrete' ? .018 : .004;
    material.addEventListener('dispose', () => texture.dispose());
  }
  if (kind === 'route_trace') {
    material.transparent = true;
    material.opacity = .65;
    material.depthWrite = false;
    material.onBeforeCompile = (shader) => {
      shader.vertexShader = 'varying vec2 routeUV;\n' + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\nrouteUV = uv;');
      shader.fragmentShader = 'varying vec2 routeUV;\n' + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>',
        '#include <color_fragment>\n' +
        'diffuseColor.a *= smoothstep(0.,.4,routeUV.x)*smoothstep(1.,.6,routeUV.x);');
    };
    material.customProgramCacheKey = () => 'route-trace-soft-v1';
  }
  return material;
}
export function buildCablePart(set, ob) {
  if (ob.kind === 'route_cable') {
    const a = P(ob.p0);
    const b = P(ob.p1);
    const length = a.distanceTo(b);
    const geometry = new THREE.CylinderGeometry(ob.radius, ob.radius, length, 16, 1, false);
    const uv = geometry.attributes.uv;
    for (let i = 0; i < uv.count; i++) {
      uv.setXY(i, uv.getX(i) * 4, (ob.p0[0] + uv.getY(i) * length) * 4);
    }
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(
      new THREE.Vector3(0, 1, 0), b.clone().sub(a).normalize()));
    geometry.translate(...a.add(b).multiplyScalar(.5).toArray());
    set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
    return;
  }
  if (ob.kind === 'route_urchin') {
    const center = P(ob.p0).lerp(P(ob.p1), .5);
    const parts = [new THREE.SphereGeometry(.06, 12, 8)];
    for (let i = 0; i < 48; i++) {
      const y = (i + .5) / 48;
      const angle = i * 2.39996323;
      const radius = Math.sqrt(1 - y * y);
      const axis = new THREE.Vector3(radius * Math.cos(angle), y, radius * Math.sin(angle));
      const spine = new THREE.ConeGeometry(.005, .035, 4);
      spine.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), axis));
      spine.translate(...axis.multiplyScalar(.067).toArray());
      parts.push(spine);
    }
    const geometry = mergeGeometries(parts);
    for (const part of parts) part.dispose();
    geometry.translate(...center.toArray());
    set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
    return;
  }
  if (ob.kind === 'route_concrete') {
    const half = new THREE.Vector3(ob.half[1], ob.half[2], ob.half[0]);
    const geometry = new THREE.BoxGeometry(half.x * 2, half.y * 2, half.z * 2, 3, 3, 3);
    const pos = geometry.attributes.position;
    const inner = half.clone().subScalar(.035);
    for (let i = 0; i < pos.count; i++) {
      const p = new THREE.Vector3().fromBufferAttribute(pos, i);
      const q = p.clone().clamp(inner.clone().negate(), inner);
      p.sub(q).normalize().multiplyScalar(.035).add(q);
      pos.setXYZ(i, p.x, p.y, p.z);
    }
    geometry.computeVertexNormals();
    geometry.rotateY(-ob.yaw_deg * Math.PI / 180);
    geometry.translate(...P(ob.center).toArray());
    set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
    return;
  }
  if (ob.kind === 'route_damage') {
    const a = P(ob.p0);
    const b = P(ob.p1);
    const direction = b.clone().sub(a).normalize();
    const u = new THREE.Vector3(0, 1, 0).cross(direction).normalize();
    const v = direction.clone().cross(u);
    const core = new THREE.CylinderGeometry(.065, .065, a.distanceTo(b), 12);
    core.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0, 1, 0), direction));
    core.translate(...a.clone().add(b).multiplyScalar(.5).toArray());
    set.addBatched('route_cable', core, 'route_cable', [ob.name], 'solid', [ob]);
    const parts = [];
    for (let wire = 0; wire < 9; wire++) {
      const points = [];
      for (let i = 0; i <= 10; i++) {
        const angle = wire * Math.PI * 2 / 9 + (ob.p0[0] + i * a.distanceTo(b) / 10) * 5;
        points.push(a.clone().lerp(b, i / 10).addScaledVector(u, .08 * Math.cos(angle))
          .addScaledVector(v, .08 * Math.sin(angle)));
      }
      parts.push(new THREE.TubeGeometry(new THREE.CatmullRomCurve3(points), 10, .012, 5, false));
    }
    const geometry = mergeGeometries(parts);
    for (const part of parts) part.dispose();
    set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
    return;
  }
  buildPenPart(set, ob);
}
export function buildCableTraces(set) {
  const data = set.world.scenario?.cable_route;
  const terrain = set.world.terrain;
  if (!data || !terrain) return;
  function bed(n, e) {
    const x = Math.max(0, Math.min(terrain.size[0] - 1.000001, (n - terrain.origin[0]) / terrain.spacing));
    const y = Math.max(0, Math.min(terrain.size[1] - 1.000001, (e - terrain.origin[1]) / terrain.spacing));
    const i = Math.floor(x);
    const j = Math.floor(y);
    const a = x - i;
    const b = y - j;
    const d00 = terrain.depths[i][j];
    const d10 = terrain.depths[i + 1][j];
    const d01 = terrain.depths[i][j + 1];
    const d11 = terrain.depths[i + 1][j + 1];
    return a + b <= 1 ? d00 + a * (d10 - d00) + b * (d01 - d00) :
      d11 + (1 - a) * (d01 - d11) + (1 - b) * (d10 - d11);
  }
  function strip(a, b, width) {
    const side = new THREE.Vector2(b[1] - a[1], a[0] - b[0]).normalize().multiplyScalar(width);
    const vertices = [];
    for (const [p, sign] of [[a, -1], [b, -1], [a, 1], [a, 1], [b, -1], [b, 1]]) {
      const n = p[0] + side.x * sign;
      const e = p[1] + side.y * sign;
      vertices.push(...P([n, e, bed(n, e) - .03]).toArray());
    }
    const geometry = new THREE.BufferGeometry();
    geometry.setAttribute('position', new THREE.Float32BufferAttribute(vertices, 3));
    geometry.setAttribute('uv', new THREE.Float32BufferAttribute([0, 0, 0, 1, 1, 0, 1, 0, 0, 1, 1, 1], 2));
    geometry.computeVertexNormals();
    set.addBatched('route_trace', geometry, 'route_trace', [], 'decal', []);
  }
  const points = data.centerline;
  for (let i = 0; i < points.length - 1; i++) {
    if (points[i].burial === 'buried') strip(points[i].pos, points[i + 1].pos, .18);
  }
  const drag = data.anomalies.find((a) => a.id === 'anchor_drag').pos;
  for (let i = -24; i < 24; i++) {
    strip([drag[0] + i * .12, drag[1] + i * .25],
      [drag[0] + (i + 1) * .12, drag[1] + (i + 1) * .25], .22);
  }
}
