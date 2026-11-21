// Collision-derived pen surfaces, alpha netting and bounded flow-driven visual displacement.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const UP = new THREE.Vector3(0, 1, 0);

// Net look (visual assumptions, not site measurements): 40 mm bar knotless mesh with about 3 mm twine, dark
// dyed nylon, 26 mm ropes along the panel joints and every 4 m of depth, fouling strongest near the surface.
const NET_TILE_M = 0.32;
const NET_PANEL_HALF_M = 18 * Math.sin(Math.PI / 48);
const INTACT_EDGE_DISTANCE_M = 1; // Outside the 0.26 m fray band.

const NET_VERTEX_HEAD = `varying float penDepth;
varying float penFloor;
varying vec2 penUv;
varying vec3 penWorld;
`;
const NET_VERTEX_BODY = `#include <begin_vertex>
penDepth = -position.y;
penFloor = abs(normal.y);
penUv = uv;
penWorld = position;`;
const NET_FRAGMENT_HEAD = `varying float penDepth;
varying float penFloor;
varying vec2 penUv;
varying vec3 penWorld;
float penHash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453);
}
float penNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  f = f * f * (3.0 - 2.0 * f);
  float top = mix(penHash(i), penHash(i + vec2(1.0, 0.0)), f.x);
  float bottom = mix(penHash(i + vec2(0.0, 1.0)), penHash(i + vec2(1.0, 1.0)), f.x);
  return mix(top, bottom, f.y);
}
`;
// Resolve individual diamond bars in metre coordinates out to four metres. At grazing angles and at
// distance the filtered texture supplies the net's solidity, while growth still follows the panel.
const NET_FRAGMENT_MAP = `
#ifdef USE_MAP
  bool penIsFloor = penFloor > 0.5;
  float penAcross = penIsFloor ? penUv.y : penUv.x;
  float penAlong = penIsFloor ? penUv.x : penDepth;
  float penHalf = penIsFloor ? 1.0 : PEN_PANEL_HALF;
  float penBay = clamp(1.0 - (penAcross / penHalf) * (penAcross / penHalf), 0.0, 1.0);
  float penSag = penIsFloor ? 0.0 : 0.09 * penBay;
  vec2 penField = penIsFloor ? penWorld.xz * 0.45 : vec2(penWorld.x + penWorld.z * 0.6, penWorld.y * 1.4) * 0.45;
  float penPatch = penNoise(penField);
  float penFine = penNoise(penField * 5.3 + 11.0);
  // Hung netting is never a ruled grid: bars wander by a few centimetres over half a metre.
  vec2 penWander = vec2(penNoise(penField * 2.6 + 3.0), penNoise(penField * 2.6 + 19.0)) - 0.5;
  vec2 penPoint = vec2(penAcross, penAlong + penSag) + 0.07 * penWander + 0.012 * vec2(penFine, penPatch);
  // Cut ends lose their lateral tension: unravel and hang in small tufts along a damaged lip.
  float penFray = penIsFloor ? 0.0 : 1.0 - smoothstep(0.03, 0.26, penUv.y);
  penPoint.x += penFray * (0.035 * sin(penAcross * 17.0) + 0.05 * (penFine - 0.5));
  penPoint.y += penFray * 0.04 * sin(penAcross * 11.0);

  vec4 penTex = texture2D(map, penPoint / PEN_TILE);
  vec2 diamonds = vec2(penPoint.x + penPoint.y, penPoint.x - penPoint.y) / 0.075;
  vec2 edge = abs(fract(diamonds + 0.5) - 0.5);
  vec2 aa = max(fwidth(diamonds), vec2(0.001));
  vec2 strands = 1.0 - smoothstep(vec2(0.025), vec2(0.025) + aa, edge);
  float netRange = length(cameraPosition - penWorld);
  float penGrowth = penIsFloor ? 0.3 : mix(1.0, 0.16, smoothstep(0.5, 11.0, penDepth));
  float penFoul = clamp(penGrowth * (0.15 + 1.5 * penPatch * penPatch + 0.4 * penFine), 0.0, 1.0);

  float penFar = clamp(penTex.a * (1.5 + 2.4 * penFoul), 0.0, 1.0);

  float penAlpha = mix(max(strands.x, strands.y), min(0.32, penFar), smoothstep(4.0, 9.0, netRange));
  // Tufts of growth close single meshes where the net is fouled.
  float colony = penPatch * 0.78 + penFine * 0.22 + 0.18 * penFray;
  float tufts = penNoise(penField * 27.0);
  float penTuft = smoothstep(0.57, 0.72, colony) * smoothstep(0.22, 0.65, penGrowth)
    * smoothstep(0.25, 0.78, tufts) * mix(1.0, 0.32, smoothstep(4.0, 10.0, netRange));
  penAlpha = max(penAlpha, 0.94 * penTuft);
  float penJoint = penHalf - abs(penAcross);
  float penBand = abs(fract((penAlong + 0.6 * penSag) / 4.0 + 0.5) - 0.5) * 4.0;
  float penRopeDistance = penIsFloor ? penJoint : min(penJoint, penBand);
  float penRope = clamp((0.016 - penRopeDistance) / max(fwidth(penRopeDistance), 1e-4) + 0.5, 0.0, 1.0);
  vec3 penAlgae = mix(vec3(0.15, 0.135, 0.085), vec3(0.12, 0.19, 0.075), (1.0 - smoothstep(1.0, 7.0, penDepth)));
  vec3 penTwine = mix(vec3(0.03, 0.035, 0.033), penAlgae, penFoul);
  penTwine *= (0.55 + 0.6 * penTex.r) * (0.6 + 0.8 * penPatch);
  penTwine = mix(penTwine, mix(vec3(0.13, 0.105, 0.035), vec3(0.35, 0.27, 0.12), tufts), penTuft);
  vec3 penRopeColor = mix(vec3(0.2, 0.21, 0.18), penAlgae * 1.3, 0.75 * penFoul);
  diffuseColor.rgb *= mix(penTwine, penRopeColor, penRope);
  float penLoose = smoothstep(0.2, 0.75, penFine + 0.2 * sin(90.0 * penAcross));
  diffuseColor.a *= max(penAlpha * mix(1.0, penLoose, penFray), penRope);
#endif
`;

export function penMaterial(kind) {
  const colors = {pen_net: 0xffffff, pen_frame: 0x182b30, pen_sinker: 0x47463c,
    pen_rope: 0x78705a, pen_buoy: 0xc79532, pen_anchor: 0x595950};
  const material = new THREE.MeshStandardMaterial({color: colors[kind], roughness: kind === 'pen_frame' ? .36 : .88});
  material.userData.structureKind = kind;
  if (kind === 'pen_net') dressNetMaterial(material);
  return material;
}

function dressNetMaterial(material) {
  material.side = THREE.DoubleSide;
  // Enable the alpha-test chunk; the shader replaces it with a low cutoff for the distant haze.
  material.alphaTest = .35;
  material.transparent = true;
  material.depthWrite = false;
  material.defines = {PEN_TILE: NET_TILE_M.toFixed(4), PEN_PANEL_HALF: NET_PANEL_HALF_M.toFixed(4)};
  if (typeof document !== 'undefined') {
    const texture = new THREE.TextureLoader().load('models/aquaculture/net.webp');
    texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
    texture.colorSpace = THREE.NoColorSpace;
    texture.anisotropy = 4;
    material.map = texture;
    material.addEventListener('dispose', () => texture.dispose());
  }
  material.onBeforeCompile = function patchNetShader(shader) {
    shader.vertexShader = NET_VERTEX_HEAD + shader.vertexShader.replace('#include <begin_vertex>', NET_VERTEX_BODY);
    shader.fragmentShader = NET_FRAGMENT_HEAD + shader.fragmentShader
      .replace('#include <map_fragment>', NET_FRAGMENT_MAP)
      .replace('#include <alphatest_fragment>', 'if (diffuseColor.a < 0.03) discard;');
  };
  material.customProgramCacheKey = () => 'pen-net-v2';
}

// Rotationally moulded mooring float with rounded shoulders and a rope eye below the waterline.
function buoyGeometry(radius, length) {
  const half = length * .5 + radius;
  const profile = [[.03, -.83], [.26, -.76], [.65, -.56], [.94, -.30], [1, .16],
    [.96, .40], [.74, .68], [.42, .82], [.15, .86], [0, .86]];
  const body = new THREE.LatheGeometry(profile.map(([r, y]) => new THREE.Vector2(radius * r, half * y)), 20);
  const eye = new THREE.TorusGeometry(radius * .16, radius * .052, 6, 12);
  eye.translate(0, -half * .87, 0);
  const geometry = mergeGeometries([body, eye]);
  body.dispose();
  eye.dispose();
  return geometry;
}

export function buildPenPart(set, ob) {
  let geometry;
  const torn = Boolean(ob.torn_edge);
  if (ob.type === 'box') {
    if (ob.kind === 'pen_net' && ob.half[2] < .1) {
      geometry = new THREE.PlaneGeometry(ob.half[0] * 2, ob.half[1] * 2, 4, 2);
      geometry.rotateX(-Math.PI / 2);
      geometry.rotateY(Math.PI / 2);
    } else if (ob.kind === 'pen_net') {
      geometry = new THREE.PlaneGeometry(ob.half[0] * 2, ob.half[2] * 2, torn ? 24 : 4, Math.ceil(ob.half[2] * 2));
      geometry.rotateY(Math.PI / 2);
    } else {
      geometry = new THREE.BoxGeometry(ob.half[1] * 2, ob.half[2] * 2, ob.half[0] * 2);
    }
    const uv = geometry.attributes.uv;
    const pos = geometry.attributes.position;
    const upper = ob.torn_edge === 'bottom';
    const lip = upper ? -ob.half[2] : ob.half[2];
    for (let i = 0; i < uv.count; i++) {
      const y = pos.getY(i);
      // Wall U is metres across. V only drives lip fraying; a large constant disables it on intact walls.
      const edgeDistance = torn ? Math.abs(y - lip) : INTACT_EDGE_DISTANCE_M;
      uv.setXY(i, pos.getZ(i), ob.half[2] < .1 ? pos.getX(i) : edgeDistance);
      if (torn && edgeDistance < .001) {
        const inset = .09 * Math.abs(Math.sin(pos.getZ(i) * 13 + lip));
        pos.setY(i, y + (upper ? inset : -inset));
      }
    }
    geometry.rotateY(-ob.yaw_deg * Math.PI / 180);
    geometry.translate(...P(ob.center).toArray());
  } else {
    const a = P(ob.p0);
    const b = P(ob.p1);
    if (ob.kind === 'pen_rope' && ob.name.endsWith('-3')) {
      const parts = [];
      const count = Math.ceil(a.distanceTo(b) / .18);
      const axis = b.clone().sub(a).normalize();
      const orientation = new THREE.Quaternion().setFromUnitVectors(UP, axis);
      for (let i = 0; i <= count; i++) {
        const link = new THREE.TorusGeometry(.075, .025, 4, set.detailName === 'high' ? 8 : 6);
        link.scale(1, 1.6, 1);
        link.rotateY(i % 2 ? Math.PI / 2 : 0);
        link.applyQuaternion(orientation);
        link.translate(...a.clone().lerp(b, i / count).toArray());
        parts.push(link);
      }
      geometry = mergeGeometries(parts);
      for (const part of parts) part.dispose();
      set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
      return;
    }
    if (ob.kind === 'pen_buoy') {
      geometry = buoyGeometry(ob.radius, a.distanceTo(b));
      if (b.y < a.y) geometry.rotateX(Math.PI);
    } else if (ob.kind === 'pen_frame') {
      // Fusion bead around each pipe end. A narrow overlapping sleeve closes the mitred joint.
      const length = a.distanceTo(b);
      const profile = [[0, 1.025], [.04, 1.045], [.07, 1], [length - .07, 1], [length, 1.025]];
      geometry = new THREE.LatheGeometry(profile.map(([s, r]) => new THREE.Vector2(r * ob.radius, s - length / 2)), 16);
    } else {
      geometry = new THREE.CapsuleGeometry(ob.radius, a.distanceTo(b), 2, 8);
    }
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(UP, b.clone().sub(a).normalize()));
    geometry.translate(...a.add(b).multiplyScalar(.5).toArray());
  }
  set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
}

export function updatePenNet(set, flow, time) {
  if (!set) return;
  const velocity = [0, 0, 0];
  const now = performance.now();
  for (const mesh of set.group.children) {
    if (mesh.material?.userData.structureKind !== 'pen_net') continue;
    const position = mesh.geometry.attributes.position;
    const uv = mesh.geometry.attributes.uv;
    if (!flow?.ready) {
      if (mesh.userData.penRest) {
        position.array.set(mesh.userData.penRest);
        position.needsUpdate = true;
        delete mesh.userData.penRest;
      }
      continue;
    }
    const rest = mesh.userData.penRest ||= position.array.slice();
    for (let i = 0; i < position.count; i++) {
      const x = rest[i * 3];
      const y = rest[i * 3 + 1];
      const z = rest[i * 3 + 2];
      const across = Math.min(1, Math.abs(uv.getX(i)) / NET_PANEL_HALF_M);
      const belly = 1 - across * across;
      if (belly === 0 || y >= 0 || y <= -16) continue;
      flow.sample(z, -x, -y, now, velocity);
      const amplitude = .035 * belly * Math.sin(-Math.PI * y / 16);
      const wave = amplitude * (.78 + .22 * Math.sin(time * .7 + z * .3 + x * .2));
      position.setXYZ(i, x - wave * Math.tanh(velocity[1]), y, z + wave * Math.tanh(velocity[0]));
    }
    position.needsUpdate = true;
  }
}
