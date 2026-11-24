import * as THREE from 'three';
import { OrbitControls } from 'three/addons/controls/OrbitControls.js';
import { buildProceduralWreckGroup } from './sop-scene.mjs';

export async function createViewer(container, { onStatus = () => {} } = {}) {
  let renderer, controls, observer, scene, frame = 0, disposed = false;
  const status = (state, message) => onStatus({ state, message });
  const dispose = () => {
    disposed = true;
    cancelAnimationFrame(frame);
    observer?.disconnect();
    controls?.dispose();
    scene?.traverse(object => {
      object.geometry?.dispose();
      const materials = object.material ? (Array.isArray(object.material) ? object.material : [object.material]) : [];
      materials.forEach(material => {
        Object.values(material).forEach(value => { if (value?.isTexture) value.dispose(); });
        material.dispose();
      });
    });
    if (renderer) {
      renderer.domElement.removeEventListener('webglcontextlost', contextLost);
      renderer.dispose();
      renderer.domElement.remove();
    }
  };
  function contextLost(event) {
    event.preventDefault();
    status('error', '3D 顯示中斷，請重試載入模型。');
  }
  status('loading', '正在準備沉船三維結構模型…');
  try {
    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false });
    renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 1.5));
    renderer.outputColorSpace = THREE.SRGBColorSpace;
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.25;
    renderer.domElement.style.cssText = 'display:block;width:100%;height:100%;touch-action:none;';
    renderer.domElement.setAttribute('aria-label', '沉船三維模型，可拖曳旋轉及滾輪縮放');
    renderer.domElement.addEventListener('webglcontextlost', contextLost);
    container.append(renderer.domElement);
    scene = new THREE.Scene();
    scene.background = new THREE.Color('#0b1720');
    const camera = new THREE.PerspectiveCamera(38, 1, 0.05, 2000);
    camera.up.set(0, 0, 1);
    const hemi = new THREE.HemisphereLight(0xd4edf2, 0x687584, 2.8);
    hemi.position.set(0, 0, 1);
    scene.add(hemi);
    const key = new THREE.DirectionalLight(0xfff1dc, 3);
    key.position.set(-30, -40, 70);
    scene.add(key);
    const fill = new THREE.DirectionalLight(0xaddfe8, 2.2);
    fill.position.set(20, 40, 25);
    scene.add(fill);
    controls = new OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.12;
    controls.maxPolarAngle = Math.PI * 0.86;

    const render = () => {
      frame = 0;
      if (disposed) return;
      controls.update();
      renderer.render(scene, camera);
    };
    const invalidate = () => { if (!frame && !disposed) frame = requestAnimationFrame(render); };
    controls.addEventListener('change', invalidate);
    const resize = () => {
      const width = Math.max(container.clientWidth, 1);
      const height = Math.max(container.clientHeight, 1);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
      renderer.setSize(width, height, false);
      invalidate();
    };
    observer = new ResizeObserver(resize);
    observer.observe(container);
    resize();

    const model = buildProceduralWreckGroup();
    model.updateMatrixWorld(true);
    const originalBounds = new THREE.Box3().setFromObject(model);
    const center = originalBounds.getCenter(new THREE.Vector3());
    model.position.sub(center);
    scene.add(model);
    model.updateMatrixWorld(true);
    const bounds = new THREE.Box3().setFromObject(model);
    const size = bounds.getSize(new THREE.Vector3());
    const radius = size.length() / 2;
    controls.minDistance = radius * 0.3;
    controls.maxDistance = radius * 8;
    camera.near = Math.max(radius / 1000, 0.01);
    camera.far = radius * 50;

    const geometry = new THREE.BoxGeometry(size.x / 3, size.y * 1.025, size.z * 1.025);
    const band = new THREE.Mesh(geometry, new THREE.MeshBasicMaterial({
      color: 0x64d8e6, transparent: true, opacity: 0.065, depthWrite: false,
      side: THREE.DoubleSide,
    }));
    const outline = new THREE.LineSegments(new THREE.EdgesGeometry(geometry), new THREE.LineBasicMaterial({
      color: 0x64d8e6, transparent: true, opacity: 0.62, depthWrite: false,
    }));
    const selection = new THREE.Group();
    selection.add(band, outline);
    scene.add(selection);
    const selectSegment = id => {
      const index = { A: 0, MID: 1, B: 2 }[id];
      if (index === undefined) throw new Error('未知分段：' + id);
      selection.position.set(bounds.min.x + size.x * (index + 0.5) / 3, 0, 0);
      invalidate();
    };
    const reset = () => {
      const verticalFov = THREE.MathUtils.degToRad(camera.fov);
      const horizontalFov = 2 * Math.atan(Math.tan(verticalFov / 2) * camera.aspect);
      const distance = radius / Math.sin(Math.min(verticalFov, horizontalFov) / 2) * 0.8;
      controls.target.set(0, 0, 0);
      camera.position.copy(new THREE.Vector3(-0.6, -1.25, 0.92).normalize().multiplyScalar(distance));
      camera.updateProjectionMatrix();
      controls.update();
      invalidate();
    };
    reset();
    selectSegment('A');
    status('ready', '模型已載入 · 拖曳旋轉，滾輪縮放');
    return { selectSegment, reset, dispose };
  } catch (error) {
    dispose();
    status('error', '模型載入失敗，請重試；採集計畫仍可編輯。');
    throw error;
  }
}
