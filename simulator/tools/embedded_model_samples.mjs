/** Read actual GLB surfaces for embedded snag checks; omit textures in the headless geometry-only loader. */
import {readFile} from 'node:fs/promises';
import * as THREE from 'three';
import {GLTFLoader} from '../viewer/vendor/three/examples/jsm/loaders/GLTFLoader.js';
import {MeshoptDecoder} from '../viewer/vendor/three/examples/jsm/libs/meshopt_decoder.module.js';

export async function geometryGLTF(url) {
  const loader = new GLTFLoader();
  loader.setMeshoptDecoder(MeshoptDecoder);
  loader.register(() => ({
    name: 'HEADLESS_GEOMETRY',
    loadMaterial: () => Promise.resolve(new THREE.MeshBasicMaterial()),
  }));
  const bytes = await readFile(new URL(url));
  return loader.parseAsync(bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength), '');
}

export async function embeddedModelSamples(world, sampleMesh) {
  const features = world.obstacles.filter((ob) => ob.embedded);
  if (!features.length) return [];
  const points = [];
  for (const ob of world.obstacles.filter((o) => o.type === 'model')) {
    const gltf = await geometryGLTF(new URL(`../viewer/${ob.model}`, import.meta.url));
    const holder = new THREE.Group();
    holder.position.set(-ob.origin[1], -ob.origin[2], ob.origin[0]);
    const angle = ob.heading_deg * Math.PI / 180;
    holder.rotation.y = Math.atan2(-Math.cos(angle), -Math.sin(angle));
    holder.add(gltf.scene);
    holder.updateMatrixWorld(true);
    gltf.scene.traverse((mesh) => {
      if (mesh.isMesh) {
        for (const point of sampleMesh(mesh, world.seabed_depth)) points.push(point);
      }
    });
  }
  return features.map((feature) => ({
    colliders: [feature.name], role: 'solid', kind: feature.kind,
    points: points.filter((p) => Math.hypot(...p.map((v, i) => v - feature.point[i])) <= feature.radius + 0.09),
  }));
}
