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
//   each frame: station.update(dt, introBoatShown)
//   station.labelPosition(world)             // where the "spool" label sits: the boat's stern
import * as THREE from 'three';
import {Humanoid} from './humanoid.js';
import {releaseLodQuality} from './model_lod.js';
import {placeWorkBoat} from './deploy_intro.js';
import {surfacePlan} from './surface_set.js';

const LABEL_LIFT = 1.2;

export class SpoolStation {
  constructor(scene, loadAssets) {
    this.scene = scene;
    this.loadAssets = loadAssets;
    this.boat = null;
    this.crew = null;
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
    this.boat = boat;
    this.scene.add(boat);
  }

  /** introBoat: the deployment intro's own boat is in the scene, so this one stays hidden. */
  update(dt, introBoat) {
    if (!this.boat) return;
    this.boat.visible = !introBoat;
    if (introBoat) return;
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
    if (this.boat) {
      releaseLodQuality(this.boat);
      this.scene.remove(this.boat);
    }
    this.boat = null;
    this.crew = null;
  }
}
