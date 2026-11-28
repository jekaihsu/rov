// The support work boat holding station at the launch point for the whole dive.
//
// In reality the boat that launched the vehicle stays at the launch point while it works and the tether runs
// up to its stern, where the winch is. The deployment intro (deploy_intro.js) brings its own boat; whenever no
// intro exists (`?nointro`, the intro switched off, a joined room, a replay) this module shows the same boat,
// placed the same way: transom at the spool, bow pointing away from the dive site, one crew member idling by
// the tether reel. It is presentation only: the server has no boat collider, so the hull must stay clear of
// where the vehicle surfaces (see docs/design/wind-farm/README.md).
//
//   const station = new SpoolStation(scene, loadIntroAssets);
//   station.build(world, startNed);          // after every world (re)build
//   each frame: station.update(dt, introBoatShown, camera)   // camera: hide it while the water hides it
//   station.labelPosition(world)             // where the "spool" label sits: the boat's stern
import * as THREE from 'three';
import {deinterleaveGeometry, mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';
import {assetTextureTier} from './render_quality.js';
import {Humanoid} from './humanoid.js';
import {placeWorkBoat} from './deploy_intro.js';
import {surfacePlan} from './surface_set.js';
import {hiddenByWater, localBoundingSphere} from './water_cull.js';

const LABEL_LIFT = 1.2;

// The station shares source assets with the deck intro. Keep a smaller texture set
// for a vessel seen through water or at a distance. Never mutate the intro's materials.
const stationMaterials = new WeakMap();
const stationMaps = new WeakMap();

function stationMap(source) {
  if (stationMaps.has(source)) return stationMaps.get(source);
  const image = source.image;
  const scale = 128 / Math.max(image?.width || 0, image?.height || 0);
  if (scale >= 1) return source;
  const canvas = document.createElement('canvas');
  canvas.width = Math.max(1, Math.round(image.width * scale));
  canvas.height = Math.max(1, Math.round(image.height * scale));
  canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
  const map = source.clone();
  map.source = new THREE.Source(canvas);
  map.needsUpdate = true;
  stationMaps.set(source, map);
  return map;
}

function stationMaterial(source) {
  if (stationMaterials.has(source)) return stationMaterials.get(source);
  const material = source.clone();
  // Three copies userData but not onBeforeCompile. The clone needs its own water shader.
  delete material.userData.waterLighting;
  for (const key of Object.keys(material)) {
    if (material[key]?.isTexture) material[key] = stationMap(material[key]);
  }
  stationMaterials.set(source, material);
  return material;
}

// The farthest authored LOD has static fittings sharing finishes. Batch each finish
// in level-local space so the chase camera can show the complete deck at one draw per finish.
function batchFarDeck(level) {
  level.updateWorldMatrix(true, true);
  const inverse = level.matrixWorld.clone().invert();
  const groups = new Map();
  level.traverse(mesh => {
    if (!mesh.isMesh || Array.isArray(mesh.material)) return;
    if (!groups.has(mesh.material)) groups.set(mesh.material, []);
    groups.get(mesh.material).push(mesh);
  });
  const batches = [];
  for (const [material, meshes] of groups) {
    if (meshes.length < 2) continue;
    const parts = meshes.map(function deckPart(mesh) {
      const geometry = mesh.geometry.clone();
      deinterleaveGeometry(geometry);
      return geometry.applyMatrix4(new THREE.Matrix4().multiplyMatrices(inverse, mesh.matrixWorld));
    });
    const merged = mergeGeometries(parts);
    for (const part of parts) part.dispose();
    if (!merged) continue;
    const batch = new THREE.Mesh(merged, material);
    batch.castShadow = true;
    batch.receiveShadow = true;
    for (const mesh of meshes) mesh.removeFromParent();
    level.add(batch);
    batches.push(merged);
  }
  return batches;
}

export class SpoolStation {
  constructor(scene, loadAssets) {
    this.scene = scene;
    this.loadAssets = loadAssets;
    this.boat = null;
    this.crew = null;
    this.sphere = null;
    this.generation = 0;
    this.t = 0;
  }

  /** (Re)places the boat for a world; the boat model loads once and is shared with the intro's assets. */
  async build(world, start) {
    this.clear();
    const generation = ++this.generation;
    // An indoor pool is worked from its edge, not from a boat.
    if (!world?.spool || surfacePlan(world).kind === 'indoor') return;
    const assets = await this.loadAssets().catch(() => ({}));
    if (generation !== this.generation) return;
    const boat = placeWorkBoat(assets, world.spool, start);
    boat.name = 'spool-station-boat';
    const ud = boat.userData;
    if (assets.human) {
      this.crew = new Humanoid(assets.human, {shirt: 0x2b3f55, pants: 0x2a2f36, vest: 0xff6a13, helmet: 0xf4f4ef});
      this.crew.root.position.set(-0.62, ud.deckY, ud.sternZ + 1.1);
      this.crew.root.rotation.y = Math.PI * 0.85;
      this.crew.play('Idle', {at: 0.7});
      boat.add(this.crew.root);
    }
    if (assetTextureTier() === 'standard') {
      // The deployed boat is background scenery for chase cameras. Reserve close
      // detail for the transom underwater, where its propellers are inspection landmarks.
      const levels = ud.lod?.levels;
      if (levels?.length === 3) {
        this.detailLevels = levels;
        this.closeDistances = [levels[1].distance, levels[2].distance];
        levels[1].distance = 2;
        levels[2].distance = 4;
        this.batches = batchFarDeck(levels[2].object);
      }
      boat.traverse(function reduceStationMaterial(mesh) {
        if (!mesh.isMesh) return;
        mesh.material = Array.isArray(mesh.material)
          ? mesh.material.map(stationMaterial) : stationMaterial(mesh.material);
      });
    }
    this.boat = boat;
    // The water surface occludes deck fittings from below. Cache bounds while the boat
    // is level, leaving a margin for the roll, pitch and heave applied in update().
    boat.updateMatrixWorld(true);
    const deckMeshes = [];
    const bounds = new THREE.Box3();
    boat.traverse(function collect(mesh) {
      if (!mesh.isMesh || !mesh.visible || mesh.isSkinnedMesh) return;
      if (!mesh.geometry.boundingBox) mesh.geometry.computeBoundingBox();
      bounds.copy(mesh.geometry.boundingBox).applyMatrix4(mesh.matrixWorld);
      if (bounds.min.y > 0.4) deckMeshes.push(mesh);
    });
    this.deckMeshes = deckMeshes;
    this.submerged = false;
    this.sphere = localBoundingSphere(boat);
    this.scene.add(boat);
  }

  /**
   * introBoat: the deployment intro's own boat is in the scene, so this one stays hidden. camera (optional): the
   * boat is skipped, crew animation included, while the water between it and the camera hides it (water_cull.js).
   */
  update(dt, introBoat, camera = null) {
    if (!this.boat) return;
    const hidden = introBoat || (!!camera && hiddenByWater(this.boat, this.sphere, camera, this.scene));
    this.boat.visible = !hidden;
    if (hidden) return;
    const submerged = !!camera && camera.position.y < -0.5;
    if (submerged !== this.submerged) {
      if (this.detailLevels) {
        this.detailLevels[1].distance = submerged ? this.closeDistances[0] : 2;
        this.detailLevels[2].distance = submerged ? this.closeDistances[1] : 4;
      }
      for (const mesh of this.deckMeshes) mesh.visible = !submerged;
      if (this.crew) this.crew.root.visible = !submerged;
      this.submerged = submerged;
    }
    this.t += dt;
    // Holding station in a slight sea: the same gentle motion the intro gives its boat.
    this.boat.rotation.z = Math.sin(this.t * 0.9) * 0.018;
    this.boat.rotation.x = Math.sin(this.t * 0.7 + 1) * 0.012;
    this.boat.position.y = Math.sin(this.t * 0.8) * 0.05;
    if (!submerged) this.crew?.update(dt);
  }

  /** The spool label: on the boat's stern above the winch when the boat is shown, else over the spool point. */
  labelPosition(world) {
    if (this.boat) {
      const ud = this.boat.userData;
      return this.boat.localToWorld(new THREE.Vector3(0, ud.deckY + LABEL_LIFT, ud.sternZ + 0.5));
    }
    const s = world.spool;
    return new THREE.Vector3(-s[1], -s[2], s[0]).add(new THREE.Vector3(0, LABEL_LIFT, 0));
  }

  clear() {
    this.deckMeshes = [];
    this.detailLevels = null;
    for (const geometry of this.batches || []) geometry.dispose();
    this.batches = [];
    this.generation++;
    if (this.boat) this.scene.remove(this.boat);
    this.boat = null;
    this.crew = null;
  }
}
