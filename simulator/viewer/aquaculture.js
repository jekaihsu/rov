// Collision-derived pen surfaces, alpha netting and bounded flow-driven visual displacement.
import * as THREE from 'three';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const P = (p) => new THREE.Vector3(-p[1], -p[2], p[0]);
const UP = new THREE.Vector3(0, 1, 0);

export function penMaterial(kind) {
  const colors = {pen_net: 0xb4b19a, pen_frame: 0x182b30, pen_sinker: 0x47463c,
    pen_rope: 0x78705a, pen_buoy: 0xc79532, pen_anchor: 0x595950};
  const material = new THREE.MeshStandardMaterial({color: colors[kind], roughness: .88});
  material.userData.structureKind = kind;
  if (kind === 'pen_net') {
    material.side = THREE.DoubleSide;
    material.alphaTest = .35;
    if (typeof document !== 'undefined') {
      const texture = new THREE.TextureLoader().load('models/aquaculture/net.webp');
      texture.wrapS = texture.wrapT = THREE.RepeatWrapping;
      texture.colorSpace = THREE.SRGBColorSpace;
      material.map = texture;
      material.addEventListener('dispose', () => texture.dispose());
    }
    material.onBeforeCompile = (shader) => {
      shader.vertexShader = 'varying float penDepth;\n' + shader.vertexShader;
      shader.vertexShader = shader.vertexShader.replace('#include <begin_vertex>',
        '#include <begin_vertex>\npenDepth = -position.y;');
      shader.fragmentShader = 'varying float penDepth;\n' + shader.fragmentShader;
      shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>',
        '#include <color_fragment>\n' +
        'diffuseColor.rgb *= mix(vec3(.32,.49,.22),vec3(.85,.81,.65),smoothstep(1.,12.,penDepth));');
    };
    material.customProgramCacheKey = () => 'pen-net-v1';
  }
  return material;
}

export function buildPenPart(set, ob) {
  let geometry;
  if (ob.type === 'box') {
    if (ob.kind === 'pen_net' && ob.half[2] < .1) {
      geometry = new THREE.PlaneGeometry(ob.half[0] * 2, ob.half[1] * 2, 4, 2);
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
      uv.setXY(i, pos.getZ(i) * 5, (ob.half[2] < .1 ? pos.getX(i) : pos.getY(i)) * 5);
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

export function updatePenNet(set, flow, time) {
  if (!set || !flow?.ready) return;
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
      flow.sample(z, -x, -y, now, velocity);
      const amplitude = .035 * Math.sin(Math.PI * Math.max(0, Math.min(16, -y)) / 16);
      const wave = amplitude * Math.sin(time * .7 + z * .3 + x * .2);
      position.setXYZ(i, x - wave * Math.tanh(velocity[1]), y, z + wave * Math.tanh(velocity[0]));
    }
    position.needsUpdate = true;
  }
}
