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
import {Humanoid} from './humanoid.js';
import {placeWorkBoat} from './deploy_intro.js';
import {assetTextureTier} from './render_quality.js';
import {surfacePlan} from './surface_set.js';
import {hiddenByWater, localBoundingSphere} from './water_cull.js';

const LABEL_LIFT = 1.2;

// The dive boat is normally seen from below or at a distance. Keep its small texture set resident
// across world rebuilds; the deployment close-ups continue to use the original shared asset.
function stationMaterial(source, station) {
  if (!source.map && !source.normalMap && !source.roughnessMap && !source.metalnessMap) return source;
  if (station.materials.has(source)) return station.materials.get(source);
  const material = source.clone();
  for (const [slot, texture] of Object.entries(source)) {
    if (!texture?.isTexture || !texture.image) continue;
    let small = station.textures.get(texture);
    if (!small) {
      const image = texture.image;
      const scale = Math.min(1, 128 / Math.max(image.width, image.height));
      const canvas = document.createElement('canvas');
      canvas.width = Math.max(1, Math.round(image.width * scale));
      canvas.height = Math.max(1, Math.round(image.height * scale));
      canvas.getContext('2d').drawImage(image, 0, 0, canvas.width, canvas.height);
      small = texture.clone();
      small.source = new THREE.Source(canvas);
      small.needsUpdate = true;
      station.renderer.initTexture(small);
      station.textures.set(texture, small);
    }
    material[slot] = small;
  }
  station.materials.set(source, material);
  return material;
}

export class SpoolStation {
  constructor(scene, loadAssets, renderer = null) {
    this.renderer = renderer;
    this.materials = new WeakMap();
    this.textures = new WeakMap();
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
    if (assets.boat && this.renderer && assetTextureTier() === 'standard') {
      boat.traverse(mesh => {
        if (!mesh.isMesh) return;
        mesh.material = Array.isArray(mesh.material)
          ? mesh.material.map(material => stationMaterial(material, this))
          : stationMaterial(mesh.material, this);
      });
    }
    this.boat = boat;
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
    this.t += dt;
    // Holding station in a slight sea: the same gentle motion the intro gives its boat.
    this.boat.rotation.z = Math.sin(this.t * 0.9) * 0.018;
    this.boat.rotation.x = Math.sin(this.t * 0.7 + 1) * 0.012;
    this.boat.position.y = Math.sin(this.t * 0.8) * 0.05;
    this.crew?.update(dt);
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
    this.generation++;
    if (this.boat) this.scene.remove(this.boat);
    this.boat = null;
    this.crew = null;
  }
}
