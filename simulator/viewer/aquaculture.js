// Collision-derived pen surfaces, alpha netting and bounded flow-driven visual displacement.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const UP = new THREE.Vector3(0, 1, 0);

// Net look (visual assumptions, not site measurements): 40 mm bar knotless mesh with about 3 mm twine, dark
// dyed nylon, 26 mm ropes along the panel joints and every 4 m of depth, fouling strongest near the surface.
const NET_TILE_M = 0.32;
const NET_PANEL_HALF_M = 18 * Math.sin(Math.PI / 48);
const NET_FLOOR_DEPTH_M = 15.9;

const NET_VERTEX_HEAD = `varying float penDepth;
varying vec2 penUv;
varying vec3 penWorld;
`;
const NET_VERTEX_BODY = `#include <begin_vertex>
penDepth = -position.y;
penUv = uv;
penWorld = position;`;
const NET_FRAGMENT_HEAD = `varying float penDepth;
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
// Replaces three's map_fragment. Near the camera the texture alpha is cut at alphaTest (lower where fouled, so
// fouled twine reads thicker); as the meshes shrink below a pixel the mip-averaged alpha (the net's solidity)
// takes over and the net becomes a haze instead of sparkling or vanishing.
const NET_FRAGMENT_MAP = `
#ifdef USE_MAP
  bool penIsFloor = penDepth > PEN_FLOOR_DEPTH;
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
  vec2 penTexel = penPoint / PEN_TILE * 256.0;
  float penLod = 0.5 * log2(max(dot(dFdx(penTexel), dFdx(penTexel)), dot(dFdy(penTexel), dFdy(penTexel))) + 1e-8);
  vec4 penTex = texture2D(map, penPoint / PEN_TILE);
  float penGrowth = penIsFloor ? 0.3 : mix(1.0, 0.16, smoothstep(0.5, 11.0, penDepth));
  float penFoul = clamp(penGrowth * (0.15 + 1.5 * penPatch * penPatch + 0.4 * penFine), 0.0, 1.0);
  float penCut = mix(alphaTest, 0.1, penFoul);
  float penEdge = max(fwidth(penTex.a), 0.04);
  float penNear = smoothstep(penCut - penEdge, penCut + penEdge, penTex.a);
  float penFar = clamp(penTex.a * (1.5 + 2.4 * penFoul), 0.0, 1.0);
  float penAlpha = mix(penNear, penFar, smoothstep(0.5, 2.2, penLod));
  // Tufts of growth close single meshes where the net is fouled.
  float penTuft = smoothstep(0.55, 0.8, penFine) * smoothstep(0.45, 0.9, penFoul);
  penAlpha = max(penAlpha, 0.7 * penTuft);
  float penJoint = penHalf - abs(penAcross);
  float penBand = abs(fract((penAlong + 0.6 * penSag) / 4.0 + 0.5) - 0.5) * 4.0;
  float penRopeDistance = penIsFloor ? penJoint : min(penJoint, penBand);
  float penRope = clamp((0.016 - penRopeDistance) / max(fwidth(penRopeDistance), 1e-4) + 0.5, 0.0, 1.0);
  vec3 penAlgae = mix(vec3(0.15, 0.135, 0.085), vec3(0.12, 0.19, 0.075), smoothstep(7.0, 1.0, penDepth));
  vec3 penTwine = mix(vec3(0.03, 0.035, 0.033), penAlgae, penFoul);
  penTwine *= (0.55 + 0.6 * penTex.r) * (0.6 + 0.8 * penPatch);
  vec3 penRopeColor = mix(vec3(0.2, 0.21, 0.18), penAlgae * 1.3, 0.75 * penFoul);
  diffuseColor.rgb *= mix(penTwine, penRopeColor, penRope);
  diffuseColor.a *= max(penAlpha, penRope);
#endif
`;

export function penMaterial(kind) {
  const colors = {pen_net: 0xffffff, pen_frame: 0x182b30, pen_sinker: 0x47463c,
    pen_rope: 0x78705a, pen_buoy: 0xc79532, pen_anchor: 0x595950};
  const material = new THREE.MeshStandardMaterial({color: colors[kind], roughness: .88});
  material.userData.structureKind = kind;
  if (kind === 'pen_net') dressNetMaterial(material);
  return material;
}

function dressNetMaterial(material) {
  material.side = THREE.DoubleSide;
  // alphaTest is the cut of the texture alpha for the near-field twine edge; the haze beyond it is blended.
  material.alphaTest = .35;
  material.transparent = true;
  material.depthWrite = false;
  material.defines = {PEN_TILE: NET_TILE_M.toFixed(4), PEN_PANEL_HALF: NET_PANEL_HALF_M.toFixed(4),
    PEN_FLOOR_DEPTH: NET_FLOOR_DEPTH_M.toFixed(2)};
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

export function buildPenPart(set, ob) {
  let geometry;
  if (ob.type === 'box') {
    if (ob.kind === 'pen_net' && ob.half[2] < .1) {
      geometry = new THREE.PlaneGeometry(ob.half[0] * 2, ob.half[1] * 2, Math.ceil(2 * ob.half[0]), 2);
      geometry.rotateX(-Math.PI / 2);
      geometry.rotateY(Math.PI / 2);
    } else if (ob.kind === 'pen_net') {
      geometry = new THREE.PlaneGeometry(ob.half[0] * 2, ob.half[2] * 2, 4, Math.ceil(ob.half[2] * 2));
      geometry.rotateY(Math.PI / 2);
    } else {
      geometry = new THREE.BoxGeometry(ob.half[1] * 2, ob.half[2] * 2, ob.half[0] * 2);
    }
    const uv = geometry.attributes.uv;
    const pos = geometry.attributes.position;
    for (let i = 0; i < uv.count; i++) {
      // metres: across the wall panel (or along the floor strip), and down the panel (or across the strip)
      uv.setXY(i, pos.getZ(i), ob.half[2] < .1 ? pos.getX(i) : pos.getY(i));
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
        const link = new THREE.TorusGeometry(.075, .025, 4, 8);
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
    geometry = new THREE.CapsuleGeometry(ob.radius, a.distanceTo(b), 2, 8);
    geometry.applyQuaternion(new THREE.Quaternion().setFromUnitVectors(UP, b.clone().sub(a).normalize()));
    geometry.translate(...a.add(b).multiplyScalar(.5).toArray());
  }
  set.addBatched(ob.kind, geometry, ob.kind, [ob.name], 'solid', [ob]);
}

export function updatePenNet(set, flow, time, contact) {
  if (!set) return;
  const point = contact && P(contact.point);
  const offset = contact && P(contact.offset);
  const velocity = [0, 0, 0];
  const now = performance.now();
  for (const mesh of set.group.children) {
    if (mesh.material?.userData.structureKind !== 'pen_net') continue;
    const position = mesh.geometry.attributes.position;
    const rest = mesh.userData.penRest ||= position.array.slice();
    for (let i = 0; i < position.count; i++) {
      const x = rest[i * 3];
      const y = rest[i * 3 + 1];
      const z = rest[i * 3 + 2];
      if (flow?.ready) flow.sample(z, -x, -y, now, velocity);
      const amplitude = .035 * Math.sin(Math.PI * Math.max(0, Math.min(16, -y)) / 16);
      const wave = amplitude * Math.sin(time * .7 + z * .3 + x * .2);
      const load = point ? Math.max(0, 1 - ((x - point.x) ** 2 + (y - point.y) ** 2 + (z - point.z) ** 2) / 2.25) : 0;
      position.setXYZ(i, x - wave * Math.tanh(velocity[1]) + (offset?.x || 0) * load,
        y + (offset?.y || 0) * load, z + wave * Math.tanh(velocity[0]) + (offset?.z || 0) * load);
    }
    position.needsUpdate = true;
  }
}
