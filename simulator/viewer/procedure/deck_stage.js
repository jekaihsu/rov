// What the deck pre-dive check shows on the aft deck while the launch intro holds its opening frame
// (deploy_intro.js). Each hands-on step gets a reaction and a camera move to the part being checked:
//   walk-around  the camera walks round the vehicle, station by station; a planted defect is drawn where it is
//                (a line on a thruster guard, a cracked guard, sand and a hair on the seal face, a locking ring
//                backed off the tether connector) and marked once reported, gone once fixed;
//   power        status LEDs light on the hull and the start-up tone plays;
//   thrusters    close on the pulsed thruster; its prop spins (deck_flow.js rotorRate) and the motor is heard
//                (a thruster in air is audible on deck, so this is topside sound, not the underwater audio item);
//   lights       both lamps glow and throw light on the deck in front of the vehicle;
//   camera       the view cuts to the onboard camera with a feed frame (OSD-style corners, LIVE, clock).
// Positions are approximate, from the intro's measured vehicle bounds and the model's rotor nodes; X1 part
// positions are not measured. Nothing here runs without a held intro (optIntro off, ?nointro, replay).
// Vehicle frame of the viewer model: +z forward, +x port, +y up (three = (-east, -down, north)).
import * as THREE from 'three';
import {installAudio} from '../audio/engine.js';
import {deckShot} from './deck_flow.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('procedure.deck_stage', {
  feed: 'CAM 1',
  live: 'LIVE',
});
const V = (x, y, z) => new THREE.Vector3(x, y, z);
const CAMERA_RESPONSE = 2.4;          // 1/s: how fast the deck camera settles on a new shot
const LED_GREEN = 0x3cff6e;
const LED_BLUE = 0x3aa8ff;
const LAMP_CANDELA = 900;             // bright enough to read on a sunlit deck; presentation value
const DEFECT_PULSE_HZ = 1.6;

function glowTexture() {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,255,1)');
  gradient.addColorStop(0.3, 'rgba(255,255,255,0.75)');
  gradient.addColorStop(1, 'rgba(255,255,255,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function glow(texture, color, size) {
  const material = new THREE.SpriteMaterial({map: texture, color, transparent: true, depthWrite: false,
    blending: THREE.AdditiveBlending});
  const sprite = new THREE.Sprite(material);
  sprite.scale.setScalar(size);
  return sprite;
}

function tube(points, radius, color, options = {}) {
  const curve = new THREE.CatmullRomCurve3(points);
  const geometry = new THREE.TubeGeometry(curve, Math.max(8, points.length * 6), radius, 6, false);
  const material = new THREE.MeshStandardMaterial({color, roughness: .8, metalness: 0, ...options});
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  return mesh;
}

/** Spherical shot around a pivot in the vehicle frame: azimuth from +z towards +x, elevation, distance. */
function orbitShot(pivot, azimuth, elevation, distance) {
  return {pivot, azimuth, elevation, distance};
}

function shortestAngle(from, to) {
  return from + Math.atan2(Math.sin(to - from), Math.cos(to - from));
}

function createFeedOverlay() {
  const root = document.createElement('div');
  root.className = 'pp-feed';
  root.id = 'procedureFeed';
  root.hidden = true;
  const label = document.createElement('span');
  label.className = 'pp-feed-label';
  label.textContent = STRINGS.feed;
  const live = document.createElement('span');
  live.className = 'pp-feed-live';
  live.textContent = STRINGS.live;
  const clock = document.createElement('span');
  clock.className = 'pp-feed-clock';
  root.append(label, live, clock);
  document.body.append(root);
  return {root, clock};
}

/**
 * ``getIntro()`` returns the deploy intro (or null); ``rov`` is the vehicle group; ``getRotors()`` the viewer's
 * rotor list by thruster index. update(procedure) follows each state; the stage animates itself while active.
 */
export function createDeckStage({getIntro, rov, getRotors}) {
  const texture = glowTexture();
  const root = new THREE.Group();
  root.name = 'PrediveDeck';
  const leds = [glow(texture, LED_GREEN, .08), glow(texture, LED_GREEN, .08), glow(texture, LED_BLUE, .08)];
  const lampGroup = new THREE.Group();
  const defectGroup = new THREE.Group();
  // A pulsed prop turns too fast to read in a still frame; a faint disc over the duct shows the blur of the blades.
  const blur = new THREE.Mesh(new THREE.CircleGeometry(1, 32), new THREE.MeshBasicMaterial({color: 0xd8dde2,
    transparent: true, opacity: .32, depthWrite: false, side: THREE.DoubleSide}));
  blur.visible = false;
  root.add(...leds, lampGroup, defectGroup, blur);
  const feed = createFeedOverlay();
  let procedure = null;
  let active = false;
  let built = null;               // vehicle bounds the lamps and LEDs were placed for
  let defectKey = '';
  let marker = null;
  let poweredAt = null;
  let motor = null;
  let frame = 0;
  let last = 0;
  const camera = {pivot: V(0, 0, 0), azimuth: .9, elevation: .45, distance: 2.2, ready: false};
  const shotPos = V(0, 0, 0);
  const shotLook = V(0, 0, 0);

  function intro() {
    const value = getIntro?.();
    return value?.playing && value.held ? value : null;
  }

  function geometry() {
    return intro()?.vehicleGeometry?.() || null;
  }

  function placeVehicleParts(shape) {
    const half = shape.half;
    built = half.clone();
    const top = half.y + .012;
    leds[0].position.set(.05, top, -half.z * .55);
    leds[1].position.set(-.05, top, -half.z * .55);
    leds[2].position.set(0, top, -half.z * .62);
    lampGroup.clear();
    for (const point of shape.lamps) {
      const lamp = new THREE.SpotLight(0xfff4e0, 0, 7, .62, .55, 1.6);
      lamp.position.copy(point);
      lamp.target.position.copy(point).add(V(0, -.55, 2.4));
      lamp.castShadow = false;
      const halo = glow(texture, 0xfff6e6, .22);
      halo.position.copy(point).add(V(0, 0, .02));
      const coneGeometry = new THREE.ConeGeometry(.42, 1.5, 24, 1, true);
      coneGeometry.translate(0, -.75, 0);
      coneGeometry.rotateX(-Math.PI / 2 + .22);
      const cone = new THREE.Mesh(coneGeometry, new THREE.MeshBasicMaterial({color: 0xfff1d6, transparent: true,
        opacity: .1, depthWrite: false, blending: THREE.AdditiveBlending, side: THREE.DoubleSide}));
      cone.position.copy(point);
      lampGroup.add(lamp, lamp.target, halo, cone);
    }
  }

  /** Vehicle-frame position of thruster ``index``: the model's rotor node, or the intro's estimate. */
  function thrusterLocal(index) {
    const rotor = getRotors?.()?.[index];
    if (rotor?.o) {
      rov.updateMatrixWorld(true);
      return rov.worldToLocal(rotor.o.getWorldPosition(V(0, 0, 0)));
    }
    const points = geometry()?.thrusters || [V(.25, 0, .3)];
    return points[index % points.length].clone();
  }

  /** Show the blade blur over the pulsed thruster's rotor, oriented on its shaft. */
  function placeBlur(index) {
    const rotor = index == null ? null : getRotors?.()?.[index];
    blur.visible = !!rotor?.o;
    if (!blur.visible) return;
    const size = new THREE.Box3().setFromObject(rotor.o).getSize(V(0, 0, 0));
    const sorted = [size.x, size.y, size.z].sort(function ascending(a, b) {
      return a - b;
    });
    const radius = Math.max(.02, sorted[1] * .48);
    blur.scale.setScalar(radius);
    const toLocal = rov.getWorldQuaternion(new THREE.Quaternion()).invert();
    const axis = (rotor.axis?.clone() || V(0, 0, 1)).applyQuaternion(rotor.o.getWorldQuaternion(new THREE.Quaternion()))
      .applyQuaternion(toLocal).normalize();
    blur.quaternion.setFromUnitVectors(V(0, 0, 1), axis);
    // On the duct mouth facing the camera, not in the blade plane where the blades would cut through it.
    const centre = thrusterLocal(index);
    const toCamera = rov.worldToLocal(shotPos.clone()).sub(centre);
    blur.position.copy(centre).addScaledVector(axis, Math.sign(toCamera.dot(axis)) * radius * .7);
  }

  function outward(local) {
    const flat = V(local.x, 0, local.z);
    if (flat.lengthSq() < 1e-4) flat.set(1, 0, 0);
    return flat.normalize();
  }

  function buildDefect(defect, shape) {
    defectGroup.clear();
    marker = null;
    if (!defect || defect.fixed) return;
    const half = shape.half;
    const parts = new THREE.Group();
    let focus = V(0, 0, 0);
    if (defect.kind === 'line_fouled' || defect.kind === 'guard_cracked') {
      const at = thrusterLocal(defect.thruster ?? 0);
      const out = outward(at);
      const rim = at.clone().addScaledVector(out, .05);
      focus = rim;
      if (defect.kind === 'line_fouled') {
        // A loose line end caught on the guard: one turn round it, the tail hanging down to the deck.
        const deck = Math.max(shape.deck ?? -half.y, -half.y - .4) + .008;
        const side = V(-out.z, 0, out.x);
        const points = [
          rim.clone().addScaledVector(side, -.05).add(V(0, .05, 0)),
          rim.clone().addScaledVector(out, .02).add(V(0, .045, 0)),
          rim.clone().addScaledVector(side, .05).add(V(0, .01, 0)),
          rim.clone().addScaledVector(out, .03).add(V(0, -.03, 0)),
          rim.clone().addScaledVector(out, .07).setY(deck + .08),
          rim.clone().addScaledVector(out, .14).addScaledVector(side, .07).setY(deck),
          rim.clone().addScaledVector(out, .2).addScaledVector(side, -.03).setY(deck),
        ];
        parts.add(tube(points, .006, 0x2f7fd2));
      } else {
        // A guard broken at its top: one bar snapped and bent out of line, a crack running down from the break,
        // and the broken-off piece lying on the deck under the thruster.
        const side = V(-out.z, 0, out.x);
        const top = rim.clone().add(V(0, .07, 0));
        parts.add(tube([top, top.clone().addScaledVector(out, .05).add(V(0, .04, 0)),
          top.clone().addScaledVector(out, .09).addScaledVector(side, .03).add(V(0, .11, 0))], .005, 0xe4e7ea,
        {metalness: .6, roughness: .35}));
        const crack = [];
        for (let i = 0; i <= 6; i++) {
          const u = i / 6;
          crack.push(rim.clone().addScaledVector(out, .014).addScaledVector(side, (i % 2 ? .012 : -.012) + u * .02)
            .add(V(0, .07 - u * .12, 0)));
        }
        parts.add(tube(crack, .003, 0x050505, {roughness: 1}));
        const deck = Math.max(shape.deck ?? -half.y, -half.y - .4);
        const piece = new THREE.Mesh(new THREE.TetrahedronGeometry(.03),
          new THREE.MeshStandardMaterial({color: 0x18191b, roughness: .7}));
        piece.position.copy(rim).addScaledVector(out, .16).addScaledVector(side, .05).setY(deck + .012);
        piece.rotation.set(.4, 1.1, .2);
        parts.add(piece);
        focus = top;
      }
    } else if (defect.kind === 'oring_debris') {
      // A housing end-cap seam on top with sand grains and a hair across the seal face.
      const seam = new THREE.Mesh(new THREE.TorusGeometry(.07, .006, 8, 40),
        new THREE.MeshStandardMaterial({color: 0x1b1d20, roughness: .6}));
      seam.rotation.x = Math.PI / 2;
      seam.position.set(0, half.y + .004, .02);
      parts.add(seam);
      const grains = new THREE.InstancedMesh(new THREE.SphereGeometry(.0035, 6, 4),
        new THREE.MeshStandardMaterial({color: 0xd6c08a, roughness: 1}), 26);
      const matrix = new THREE.Matrix4();
      for (let i = 0; i < 26; i++) {
        const angle = .4 + i * .09;
        const radius = .07 + Math.sin(i * 7.3) * .008;
        matrix.makeTranslation(Math.cos(angle) * radius, half.y + .008, .02 + Math.sin(angle) * radius);
        grains.setMatrixAt(i, matrix);
      }
      parts.add(grains);
      parts.add(tube([V(.03, half.y + .006, .1), V(.06, half.y + .009, .06), V(.075, half.y + .007, .02),
        V(.11, half.y + .008, -.02), V(.14, half.y + .006, -.01)], .0012, 0x111111));
      focus = V(.06, half.y, .03);
    } else if (defect.kind === 'connector_unlocked') {
      const gland = shape.gland.clone();
      // The locking ring backed off the connector: a bright thread band shows between ring and housing.
      const band = new THREE.Mesh(new THREE.CylinderGeometry(.022, .022, .018, 24),
        new THREE.MeshStandardMaterial({color: 0xff5a1f, roughness: .4, emissive: 0x401000}));
      band.rotation.x = Math.PI / 2;
      band.position.copy(gland).add(V(0, 0, -.02));
      const ring = new THREE.Mesh(new THREE.TorusGeometry(.026, .009, 10, 28),
        new THREE.MeshStandardMaterial({color: 0x2a2c30, roughness: .5, metalness: .4}));
      ring.position.copy(gland).add(V(0, 0, -.05));
      parts.add(band, ring);
      focus = gland.clone().add(V(0, 0, -.03));
    }
    defectGroup.add(parts);
    marker = new THREE.Mesh(new THREE.RingGeometry(.09, .105, 40), new THREE.MeshBasicMaterial({color: 0xff7a1a,
      transparent: true, opacity: 0, depthTest: false, side: THREE.DoubleSide}));
    marker.position.copy(focus);
    marker.renderOrder = 10;
    defectGroup.add(marker);
  }

  /** Target camera for the current step, in the vehicle frame. */
  function targetShot(p, shape) {
    const half = shape.half;
    const shot = deckShot(p) || {key: 'overview'};
    if (shot.key === 'station') {
      const stations = [
        orbitShot(V(0, 0, half.z * .8), .45, .95, .85),
        orbitShot(V(half.x * .8, 0, 0), Math.PI / 2, .3, .95),
        orbitShot(V(0, half.y, 0), Math.PI * .8, 1.15, .85),
        orbitShot(V(0, half.y * .2, -half.z * .9), Math.PI - .35, .22, .8),
        orbitShot(V(-half.x * .8, 0, 0), Math.PI * 1.5, .3, .95),
      ];
      return stations[shot.station] || stations[0];
    }
    if (shot.key === 'thruster') {
      // From the thruster's side of the vehicle and a little aft: the bow faces the transom on deck.
      const at = thrusterLocal(shot.thruster);
      return orbitShot(at, Math.atan2(Math.sign(at.x) || 1, -.45), .5, .7);
    }
    if (shot.key === 'power') return orbitShot(V(0, half.y, -half.z * .55), Math.PI - .7, .62, .8);
    if (shot.key === 'lights') return orbitShot(V(0, -half.y * .2, half.z + .3), Math.PI / 2 + .55, .5, 1.5);
    if (shot.key === 'launch') return orbitShot(V(0, .1, 0), .9, .55, 2.3);
    if (shot.key === 'onboard') return {onboard: true};
    return orbitShot(V(0, 0, 0), .9, .45, 2.2);
  }

  function placeCamera(p, shape, dt) {
    const target = targetShot(p, shape);
    const half = shape.half;
    if (target.onboard) {
      shotPos.set(0, -.02, half.z + .1);
      shotLook.set(0, -.12, half.z + 5);
      rov.localToWorld(shotPos);
      rov.localToWorld(shotLook);
      camera.ready = false;               // cut back from the feed, no swing through the hull
      return;
    }
    const k = camera.ready ? 1 - Math.exp(-CAMERA_RESPONSE * dt) : 1;
    camera.pivot.lerp(target.pivot, k);
    const azimuth = shortestAngle(camera.azimuth, target.azimuth);
    camera.azimuth += (azimuth - camera.azimuth) * k;
    camera.elevation += (target.elevation - camera.elevation) * k;
    camera.distance += (target.distance - camera.distance) * k;
    camera.ready = true;
    const flat = Math.cos(camera.elevation) * camera.distance;
    shotPos.set(Math.sin(camera.azimuth) * flat, Math.sin(camera.elevation) * camera.distance,
      Math.cos(camera.azimuth) * flat).add(camera.pivot);
    shotLook.copy(camera.pivot);
    rov.localToWorld(shotPos);
    rov.localToWorld(shotLook);
  }

  function driveMotor(on) {
    const audio = installAudio();
    if (!audio.ctx || !audio.buses) return;
    motor ||= audio.motor(audio.buses.vehicle);
    audio.drive(motor, on ? .55 : 0, .7);
  }

  function animate(now) {
    frame = 0;
    const held = intro();
    const p = procedure;
    if (!active || !held || !p) {
      detach();
      return;
    }
    // Wall time, up to half a second a frame: on a slow page the camera still settles in seconds.
    const dt = Math.min(.5, Math.max(0, (now - (last || now)) / 1000));
    last = now;
    const shape = held.vehicleGeometry();
    if (!built || !built.equals(shape.half)) {
      placeVehicleParts(shape);
      defectKey = '';
    }
    if (root.parent !== rov) rov.add(root);
    const key = JSON.stringify(p.defect || null);
    if (key !== defectKey) {
      defectKey = key;
      buildDefect(p.defect, shape);
    }
    if (marker) {
      const pulse = .5 + .5 * Math.sin(now / 1000 * Math.PI * 2 * DEFECT_PULSE_HZ);
      marker.material.opacity = p.defect?.found ? .55 + .4 * pulse : 0;
      marker.quaternion.copy(held.camera.quaternion);
      marker.quaternion.premultiply(rov.getWorldQuaternion(new THREE.Quaternion()).invert());
    }
    const powered = !!p.powered;
    if (powered && poweredAt == null) {
      poweredAt = now;
      installAudio().cue('complete');
    }
    if (!powered) poweredAt = null;
    leds[0].visible = leds[1].visible = powered;
    leds[2].visible = powered && Math.floor(now / 420) % 2 === 0;
    const lit = !!p.lamps;
    for (const object of lampGroup.children) {
      if (object.isSpotLight) object.intensity = lit ? LAMP_CANDELA : 0;
      else if (object.isSprite || object.isMesh) object.visible = lit;
    }
    driveMotor(p.diagnostic > 0);
    placeCamera(p, shape, dt);
    placeBlur(p.diagnostic > 0 ? p.diagnostic_index : null);
    feed.root.hidden = !(deckShot(p)?.key === 'onboard');
    if (!feed.root.hidden) feed.clock.textContent = new Date().toLocaleTimeString('zh-TW', {hour12: false});
    held.setDeckShot(function shot() {
      return {pos: shotPos, look: shotLook};
    });
    frame = requestAnimationFrame(animate);
  }

  function detach() {
    active = false;
    if (frame) cancelAnimationFrame(frame);
    frame = 0;
    last = 0;
    root.removeFromParent();
    feed.root.hidden = true;
    driveMotor(false);
    camera.ready = false;
    const held = getIntro?.();
    if (held?.held) held.setDeckShot?.(null);
  }

  /** Follow one procedure state: active during the deck flow's checks and while waiting to lower. */
  function update(p) {
    procedure = p;
    const wanted = p?.flow === 'deck' && (p.phase === 'checks' || p.phase === 'launch');
    if (!wanted) {
      if (active) detach();
      return;
    }
    active = true;
    if (!frame) frame = requestAnimationFrame(animate);
  }

  /** What is on deck now (browser checks): LEDs, lamps, feed, defect drawn and marked. */
  function debug() {
    const lamp = lampGroup.children.find(function spot(object) {
      return object.isSpotLight;
    });
    return {
      attached: root.parent === rov,
      leds: leds[0].visible,
      lamps: !!lamp && lamp.intensity > 0,
      spinning: blur.visible,
      feed: !feed.root.hidden,
      defect: defectGroup.children.length > 0,
      marked: !!marker && marker.material.opacity > 0,
      shot: deckShot(procedure)?.key || null,
    };
  }

  return {update, debug};
}
