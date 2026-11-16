// Optional live small-boat menu base. Reuses the game's surface set, daylight and vehicle assets.
import * as THREE from 'three';
import {dressBoatSurfaces} from './boat_surfaces.js';
import {loadGLTF} from '../glb.js';
import {createVehicleModel} from '../vehicle_models.js';
import {applyVehicleSticker} from '../vehicle_stickers.js';
import {createDaylight} from '../fx/daylight.js';
import {buildSurfaceSet} from '../surface_set.js';
import {configureRenderQuality} from '../render_quality.js';

const ROUTES = {
  title: 'platform', main: 'cockpit', modes: 'cockpit', briefing: 'cockpit',
  hangar: 'platform', shop: 'platform', settings: 'logbook', training: 'logbook',
  sites: 'horizon', preview: 'horizon', multiplayer: 'cockpit', launch: 'platform',
};
export function createBoatStage(host, {quality = 'auto'} = {}) {
  const scene = new THREE.Scene();
  scene.background = new THREE.Color(0x7594aa);
  const renderer = new THREE.WebGLRenderer({antialias: true});
  renderer.outputColorSpace = THREE.SRGBColorSpace;
  renderer.toneMapping = THREE.ACESFilmicToneMapping;
  renderer.domElement.className = 'menu-canvas';
  host.prepend(renderer.domElement);
  configureRenderQuality(renderer, quality);
  const camera = new THREE.PerspectiveCamera(48, innerWidth / innerHeight, .03, 6000);
  const daylight = createDaylight(scene);
  const state = {modelReady: false, sceneReady: false, modelId: '', sceneKey: ''};
  let boat;
  let releaseSurfaces;
  let models = [];
  let surface;
  let world;
  let desired = 'anchor_platform';
  let sticker = 'none';
  let ticket = 0;
  let disposed = false;
  let last = performance.now();
  let frameId;
  let snap = true;
  const eye = new THREE.Vector3();
  const look = new THREE.Vector3();
  const target = new THREE.Vector3();
  const ready = loadGLTF('models/small_boat.glb').then(async function loaded(asset) {
    boat = asset.scene;
    // Stand off from the inspected foundation; the menu boat must not sit inside its legs.
    boat.position.set(-25, 0, -45);
    boat.getObjectByName('target_horizon').position.x += 25;
    scene.add(boat);
    boat.traverse(function prepare(node) {
      if (node.isMesh) {
        node.castShadow = true;
        node.receiveShadow = true;
        if (/screen_|photo_wall_|frame_licence/.test(node.name)) node.material.side = THREE.DoubleSide;
      }
    });
    releaseSurfaces = await dressBoatSurfaces(boat);
    state.sceneReady = true;
  });
  function goTo(name, {immediate = false} = {}) {
    if (!/^anchor_(cockpit|platform|logbook|horizon)$/.test(name)) throw new Error(`Unknown boat anchor: ${name}`);
    desired = name;
    snap = immediate || matchMedia('(prefers-reduced-motion: reduce)').matches;
  }
  async function setModel(id) {
    const current = ++ticket;
    state.modelReady = false;
    await ready;
    const next = await Promise.all([createVehicleModel(id), createVehicleModel('x1')]);
    if (current !== ticket || disposed) {
      next.forEach(function release(model) { model.dispose(); });
      return;
    }
    for (const model of models) {
      model.root.removeFromParent();
      model.dispose();
    }
    const error = next.find(function failed(model) { return model.loadError; })?.loadError;
    if (error) {
      next.forEach(function release(model) { model.dispose(); });
      throw error;
    }
    models = next;
    models.forEach(function place(model, i) {
      const slot = boat.getObjectByName(`rov_slot_${i}`);
      slot.add(model.root);
      model.root.rotation.y = Math.PI;
      const bounds = new THREE.Box3().setFromObject(model.root);
      model.root.position.y += slot.getWorldPosition(new THREE.Vector3()).y - bounds.min.y + .01;
      applyVehicleSticker(model, sticker);
    });
    state.modelId = id;
    state.modelReady = true;
  }
  function setScene(entry) {
    if (!entry) return;
    world = entry.world;
    state.sceneKey = entry.key;
    if (surface) {
      surface.group.removeFromParent();
      surface.group.traverse(function release(node) {
        node.geometry?.dispose();
        node.material?.dispose();
      });
    }
    let seed = 81;
    function random() {
      seed = (seed * 1664525 + 1013904223) >>> 0;
      return seed / 4294967296;
    }
    surface = buildSurfaceSet(world, new THREE.Vector3(), random);
    scene.add(surface.group);
  }
  function resize() {
    renderer.setSize(innerWidth, innerHeight);
    camera.aspect = innerWidth / innerHeight;
    camera.updateProjectionMatrix();
  }
  function frame(now) {
    if (disposed) return;
    const dt = Math.min(.1, (now - last) / 1000);
    last = now;
    if (boat) {
      boat.getObjectByName(desired).getWorldPosition(eye);
      boat.getObjectByName(desired.replace('anchor_', 'target_')).getWorldPosition(target);
      const blend = snap ? 1 : 1 - Math.exp(-dt * 3);
      camera.position.lerp(eye, blend);
      look.lerp(target, blend);
      camera.lookAt(look);
      snap = false;
    }
    daylight.update({camera, world, dt, renderer});
    renderer.render(scene, camera);
    frameId = requestAnimationFrame(frame);
  }
  resize();
  addEventListener('resize', resize);
  frameId = requestAnimationFrame(frame);
  const api = {
    renderer, scene, camera, state, goTo, setModel, setScene,
    setPose(name) { goTo('anchor_' + (ROUTES[name] || 'cockpit')); },
    setSticker(value) {
      sticker = value;
      models.forEach(function apply(model) { applyVehicleSticker(model, value); });
    },
    rotate() {},
    configureQuality(value) { configureRenderQuality(renderer, value); },
    get showcase() { return false; },
    get stickerMeshes() { return models[0]?.stickerGroup?.children.length || 0; },
    dispose() {
      disposed = true;
      ticket++;
      cancelAnimationFrame(frameId);
      removeEventListener('resize', resize);
      daylight.dispose();
      releaseSurfaces?.();
      models.forEach(function release(model) { model.dispose(); });
      renderer.dispose();
      renderer.domElement.remove();
    },
  };
  if (new URLSearchParams(location.search).has('boatReview')) window.__boatStage = api;
  return api;
}
