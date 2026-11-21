// Bind each low-relief subject to its authoritative attachment and photograph the exact drawn instance.
// Instantiate a kind on first approach and pack only nearby subjects into its draw call.
import * as THREE from 'three';
import {discoveryGeometry} from './discovery_geometry.js';

const UP = new THREE.Vector3(0, 1, 0);
const SCALE = new THREE.Vector3(1, 1, 1);

function fromNed([n, e, d]) {
  return new THREE.Vector3(-e, -d, n);
}

// Shared 125 mm tile of mineral speckle and thin deposits. Mips suppress shimmer when a shard is subpixel.
function discoveryMaterial() {
  const size = 64;
  const pixels = new Uint8Array(size * size * 4);
  let seed = 46531;
  for (let y = 0; y < size; y++) {
    for (let x = 0; x < size; x++) {
      seed = (Math.imul(seed, 1664525) + 1013904223) >>> 0;
      const phaseX = x / size * Math.PI * 2;
      const phaseY = y / size * Math.PI * 2;
      const grain = 190 + 39 * (seed / 0xffffffff)
        + 14 * Math.sin(phaseX * 3 + Math.sin(phaseY * 2)) + 11 * Math.cos(phaseY + Math.sin(phaseX));
      pixels.set([grain, grain, grain, 255], 4 * (y * size + x));
    }
  }
  const map = new THREE.DataTexture(pixels, size, size);
  map.wrapS = map.wrapT = THREE.RepeatWrapping;
  map.magFilter = THREE.LinearFilter;
  map.minFilter = THREE.LinearMipmapLinearFilter;
  map.generateMipmaps = true;
  map.needsUpdate = true;
  return new THREE.MeshStandardMaterial({map, vertexColors: true, roughness: .88});
}

function attachment(marker) {
  const position = fromNed(marker.pos);
  const rotation = new THREE.Quaternion().setFromUnitVectors(UP, fromNed(marker.normal).normalize());
  const yaw = THREE.MathUtils.degToRad(-marker.yaw);
  rotation.multiply(new THREE.Quaternion().setFromAxisAngle(UP, yaw));
  return {
    position,
    visible: false,
    matrix: new THREE.Matrix4().compose(position, rotation, SCALE),
    target: {entity_id: marker.id, category: marker.kind, mesh: null, instanceIds: [-1]},
  };
}

export function installDiscoveryDetails(group, world, targets) {
  const markers = world.habitat?.discoveries;
  if (!markers?.length) return null;
  const buckets = new Map();
  for (const marker of markers) {
    let bucket = buckets.get(marker.kind);
    if (!bucket) {
      bucket = {kind: marker.kind, mesh: null, subjects: [], coarse: true, geometries: new Map()};
      buckets.set(marker.kind, bucket);
    }
    const subject = attachment(marker);
    bucket.subjects.push(subject);
    targets.push(subject.target);
  }
  const radius = Math.min(12, 1.35 * (world.scenario?.visibility_m ?? 10));
  const lastPosition = new THREE.Vector3(Infinity, Infinity, Infinity);
  let material;
  function repack(bucket, coarse) {
    if (!bucket.geometries.has(coarse)) {
      const geometry = discoveryGeometry(bucket.kind, coarse);
      if (!geometry) return;
      bucket.geometries.set(coarse, geometry);
    }
    const geometry = bucket.geometries.get(coarse);
    bucket.coarse = coarse;
    if (!bucket.mesh) {
      material ??= discoveryMaterial();
      bucket.mesh = new THREE.InstancedMesh(geometry, material, bucket.subjects.length);
      bucket.mesh.name = 'discovery-' + bucket.kind;
      bucket.mesh.instanceMatrix.setUsage(THREE.DynamicDrawUsage);
      group.add(bucket.mesh);
    }
    const mesh = bucket.mesh;
    mesh.geometry = geometry;
    mesh.count = 0;
    for (const subject of bucket.subjects) {
      subject.target.mesh = subject.visible ? mesh : null;
      subject.target.instanceIds[0] = subject.visible ? mesh.count : -1;
      if (subject.visible) mesh.setMatrixAt(mesh.count++, subject.matrix);
    }
    mesh.visible = mesh.count > 0;
    mesh.instanceMatrix.needsUpdate = true;
    if (mesh.visible) mesh.computeBoundingSphere();
  }
  function update(camera) {
    if (lastPosition.distanceToSquared(camera.position) < .04) return;
    lastPosition.copy(camera.position);
    for (const bucket of buckets.values()) {
      let changed = false;
      let closest = Infinity;
      for (const subject of bucket.subjects) {
        const distance = subject.position.distanceToSquared(camera.position);
        const cutoff = subject.visible ? radius + 1 : radius;
        const visible = distance <= cutoff * cutoff;
        if (visible) closest = Math.min(closest, distance);
        if (subject.visible !== visible) changed = true;
        subject.visible = visible;
      }
      // One silhouette per kind, upgraded in place when a subject is close enough to inspect its relief.
      const coarse = Number.isFinite(closest) ? closest > (bucket.coarse ? 2.4 ** 2 : 3.1 ** 2) : bucket.coarse;
      if (changed || coarse !== bucket.coarse) repack(bucket, coarse);
    }
  }
  function dispose() {
    // Environment disposes the group's geometries and materials; each batch owns its instance buffer.
    for (const bucket of buckets.values()) {
      bucket.mesh?.dispose();
      for (const geometry of bucket.geometries.values()) {
        if (geometry !== bucket.mesh?.geometry) geometry.dispose();
      }
    }
  }
  return {update, dispose};
}
