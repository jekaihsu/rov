// Load inspection relief once per structure set and pile radius. Meshes use metres and glTF Y up.
import * as THREE from 'three';
import {loadGLTF} from './glb.js';

const assets = new WeakMap();

function wrapPile(geometry, radius) {
  // Model Y is height off the substrate. Bend both the positions and the authored smooth normals.
  const p = geometry.attributes.position;
  const n = geometry.attributes.normal;
  for (let i = 0; i < p.count; i++) {
    const a = p.getX(i) / radius;
    const r = radius + p.getY(i);
    const c = Math.cos(a);
    const s = Math.sin(a);
    const nx = n.getX(i);
    const ny = n.getY(i);
    p.setXYZ(i, r * s, -p.getZ(i), r * c - radius);
    n.setXYZ(i, nx * c + ny * s, -n.getZ(i), -nx * s + ny * c);
  }
  geometry.computeBoundingSphere();
}

function sway(material, current) {
  const phase = {value: 0};
  const direction = THREE.MathUtils.degToRad(current?.mid_dir || 0);
  const strength = Math.min(.045, .046 * (current?.mid_kn || 0));
  const flow = new THREE.Vector3(-Math.sin(direction), 0, Math.cos(direction)).multiplyScalar(strength);
  material.onBeforeRender = () => { phase.value = performance.now() * .001; };
  material.onBeforeCompile = shader => {
    shader.uniforms.harborTime = phase;
    shader.uniforms.harborFlow = {value: flow};
    shader.vertexShader = 'uniform float harborTime;\nuniform vec3 harborFlow;\n' + shader.vertexShader;
    shader.vertexShader = shader.vertexShader.replace('#include <project_vertex>', `
      #include <project_vertex>
      float w = color.r;
      vec4 origin = modelMatrix * vec4(0., 0., 0., 1.);
      float drift = w*w * (0.65 + 0.35*sin(harborTime*1.8 + origin.x + w*2.0));
      mvPosition.xyz += mat3(viewMatrix) * harborFlow * drift;
      gl_Position = projectionMatrix * mvPosition;`);
    shader.fragmentShader = shader.fragmentShader.replace('#include <color_fragment>', '');
  };
}

function source(set, name, radius) {
  let cache = assets.get(set);
  if (!cache) {
    cache = new Map();
    assets.set(set, cache);
    set.group.addEventListener('dispose', () => assets.delete(set));
  }
  const key = name + '/' + radius;
  if (!cache.has(name)) {
    const url = new URL('./models/harbor/' + name + '.glb', import.meta.url);
    cache.set(name, (set.harborLoader || loadGLTF)(url.href).then(({scene}) => {
      const levels = [0, 1, 2].map(i => scene.getObjectByName('LOD' + i));
      const material = levels[0].material;
      // All eleven files embed the same atlas for standalone use. Upload each map once in the game.
      for (const key of ['map', 'normalMap', 'metalnessMap', 'roughnessMap', 'aoMap']) {
        const texture = material[key];
        if (!texture) continue;
        const id = 'atlas/' + texture.name;
        if (!cache.has(id)) cache.set(id, texture);
        material[key] = cache.get(id);
        if (material[key] !== texture) texture.dispose();
      }
      if (name === 'filaments-ascidians') sway(material, set.world.current);
      function release() {
        for (const mesh of levels) mesh.geometry.dispose();
        for (const texture of new Set(Object.values(material).filter(value => value?.isTexture))) texture.dispose();
        material.dispose();
      }
      if (assets.has(set)) set.group.addEventListener('dispose', release);
      else release();
      return levels;
    }));
  }
  if (!radius) return cache.get(name);
  if (!cache.has(key)) cache.set(key, cache.get(name).then(levels => levels.map(mesh => {
    const bent = mesh.clone();
    bent.geometry = mesh.geometry.clone();
    wrapPile(bent.geometry, radius);
    return bent;
  })));
  return cache.get(key);
}

export function prop(set, name, position, {radius = 0, rotation, scale, obstacles = []} = {}) {
  const lod = new THREE.LOD();
  lod.name = name;
  lod.position.copy(position);
  lod.userData.role = radius ? 'attached' : 'solid';
  if (rotation) lod.quaternion.copy(rotation);
  if (scale) lod.scale.copy(scale);
  set.group.add(lod);
  if (!radius) for (const ob of obstacles) set.anchor(ob, lod);
  if (!set.harborLoader && typeof document === 'undefined') return lod;
  const ready = source(set, name, radius).then(levels => {
    if (!assets.has(set)) return;
    levels.forEach((sourceMesh, i) => {
      const mesh = sourceMesh.clone();
      mesh.userData.role = radius ? 'attached' : 'solid';
      mesh.userData.paintable = !radius;
      mesh.userData.colliders = obstacles.map(ob => ob.name);
      lod.addLevel(mesh, [0, 2.5, 5][i]);
      if (!i && !radius) {
        for (const ob of obstacles) set.anchor(ob, mesh);
      }
    });
    lod.addLevel(new THREE.Group(), radius ? 7 : 14);
  });
  if (set.harborLoader) set.pendingHarbor.push(ready);
  else ready.catch(error => console.error('Harbor prop', name, error));
  return lod;
}
