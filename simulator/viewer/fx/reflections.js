// Small procedural underwater reflection cube; no external texture or scene recapture.
// Only high/ultra use it. It is intentionally dim so deep lamps remain necessary.
import * as THREE from 'three';
const scenes = new WeakMap();

export function updateReflections(scene, mode) {
  let data = scenes.get(scene);
  const enabled = ['high', 'ultra'].includes(mode);
  if (!data && !enabled) return;
  if (!data) {
    const faces = [];
    for (let face = 0; face < 6; face++) {
      const canvas = document.createElement('canvas');
      canvas.width = 32;
      canvas.height = 32;
      const context = canvas.getContext('2d');
      const gradient = context.createLinearGradient(0, 0, 0, 32);
      gradient.addColorStop(0, face === 2 ? '#132a2e' : '#08191c');
      gradient.addColorStop(1, face === 3 ? '#010303' : '#020707');
      context.fillStyle = gradient;
      context.fillRect(0, 0, 32, 32);
      faces.push(canvas);
    }
    const texture = new THREE.CubeTexture(faces);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.needsUpdate = true;
    data = { original: scene.environment, texture };
    scenes.set(scene, data);
  }
  scene.environment = enabled ? data.texture : data.original;
}

export function disposeReflections(scene) {
  const data = scenes.get(scene);
  if (!data) return;
  scene.environment = data.original;
  data.texture.dispose();
  scenes.delete(scene);
}
