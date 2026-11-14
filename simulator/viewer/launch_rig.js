// Launch rig for the deploy intro: the work boat's luffing stern A-frame, its sheave block, hydraulic rams and
// lifting hook, plus the steel lifting wire and the vehicle's soft four-leg lifting bridle. The vehicle is
// lifted by a lifting line, never by its tether.
//
// Uses the support-vessel GLB nodes from cad/build_support_vessel.py: "AFrame" (pivot at the deck hinges,
// rotation 0 = stowed), "LiftBlock" (kept plumb), "SheaveBottom" (wire exit), "LiftHook" (moved along the wire),
// "AFrameRam_P/S" (origin on the deck lug, local +Y along the ram) and "RamAttach_P/S". A boat without these
// nodes gets a virtual A-frame of the same geometry, so the launch still reads correctly.
//
// All positions handed in or out are world coordinates unless named "local" (boat-local).
import * as THREE from 'three';

const UP = new THREE.Vector3(0, 1, 0);
const X_AXIS = new THREE.Vector3(1, 0, 0);
const HOOK_TOP = 0.11;            // wire socket above the hook origin (m)
const HOOK_BEND = 0.06;           // master link rests this far below the hook origin (m)
const WIRE_RADIUS = 0.005;
const SLING_RADIUS = 0.006;

// Virtual A-frame used when the boat model has no rig nodes (boat-local offsets from sternZ / deckY).
const VIRTUAL = { hingeS: 0.32, hingeAboveDeck: 0.2, block: new THREE.Vector3(0, 2.1, -0.62), sheaveDrop: 0.32 };

function stretchBetween(mesh, a, b) {
  const delta = new THREE.Vector3().subVectors(b, a);
  const length = delta.length();
  mesh.visible = length > 1e-4;
  if (!mesh.visible) return;
  mesh.position.copy(a).addScaledVector(delta, 0.5);
  mesh.quaternion.setFromUnitVectors(UP, delta.divideScalar(length));
  mesh.scale.set(1, length, 1);
}

function makeStrand(radius, color, roughness) {
  const geometry = new THREE.CylinderGeometry(radius, radius, 1, 6, 1, true);
  const material = new THREE.MeshStandardMaterial({ color, roughness, metalness: color === 0x60666c ? 0.6 : 0 });
  const mesh = new THREE.Mesh(geometry, material);
  mesh.castShadow = true;
  mesh.frustumCulled = false;
  return mesh;
}

function localPosition(node, ancestor) {
  const out = new THREE.Vector3();
  node.getWorldPosition(out);
  return ancestor.worldToLocal(out);
}

export class LaunchRig {
  /** ``boat``: the placed boat group (its local frame is the vessel model's frame). */
  constructor(boat) {
    this.boat = boat;
    const find = function findNode(name) {
      return boat.getObjectByName(name) || null;
    };
    this.frame = find('AFrame');
    this.block = find('LiftBlock');
    this.sheave = find('SheaveBottom');
    this.hook = find('LiftHook');
    this.real = !!(this.frame && this.block && this.sheave);
    boat.updateMatrixWorld(true);
    const ud = boat.userData;
    if (this.real) {
      this.hinge = localPosition(this.frame, boat);
      this.blockOffset = localPosition(this.block, boat).sub(this.hinge);
      this.sheaveDrop = localPosition(this.block, boat).sub(localPosition(this.sheave, boat)).y;
    } else {
      this.hinge = new THREE.Vector3(0, ud.deckY + VIRTUAL.hingeAboveDeck, ud.sternZ + VIRTUAL.hingeS);
      this.blockOffset = VIRTUAL.block.clone();
      this.sheaveDrop = VIRTUAL.sheaveDrop;
    }
    this.rams = [];
    for (const side of ['P', 'S']) {
      const ram = find('AFrameRam_' + side);
      const attach = find('RamAttach_' + side);
      if (!ram || !attach) continue;
      const length = localPosition(attach, ram.parent).distanceTo(ram.position);
      this.rams.push({ ram, attach, length });
    }
    this.group = new THREE.Group();
    this.wire = makeStrand(WIRE_RADIUS, 0x60666c, 0.45);
    this.legs = [];
    for (let i = 0; i < 4; i++) {
      const leg = makeStrand(SLING_RADIUS, 0x3a4c66, 0.85);
      this.legs.push(leg);
      this.group.add(leg);
    }
    this.link = new THREE.Mesh(new THREE.TorusGeometry(0.035, 0.008, 6, 16),
      new THREE.MeshStandardMaterial({ color: 0x8a9096, roughness: 0.4, metalness: 0.7 }));
    this.link.castShadow = true;
    this.group.add(this.wire, this.link);
    if (!this.hook) {
      this.virtualHook = new THREE.Mesh(new THREE.TorusGeometry(0.06, 0.016, 6, 14, 4.5),
        new THREE.MeshStandardMaterial({ color: 0x9aa0a6, roughness: 0.4, metalness: 0.7 }));
      this.group.add(this.virtualHook);
    }
    this.angle = 0;
    this._a = new THREE.Vector3();
    this._b = new THREE.Vector3();
  }

  /** Boat-local position of the wire exit under the sheave for A-frame angle ``theta`` (0 = stowed). */
  sheaveLocal(theta, out = new THREE.Vector3()) {
    out.copy(this.blockOffset).applyAxisAngle(X_AXIS, theta).add(this.hinge);
    out.y -= this.sheaveDrop;
    return out;
  }

  /** Luff the A-frame to ``theta`` (radians about the hinge; positive swings the apex inboard). */
  setAngle(theta) {
    this.angle = theta;
    if (!this.real) return;
    this.frame.rotation.x = theta;
    this.block.rotation.x = -theta;
    this.boat.updateMatrixWorld(true);
    for (const { ram, attach, length } of this.rams) {
      const target = localPosition(attach, ram.parent).sub(ram.position);
      const reach = target.length();
      ram.quaternion.setFromUnitVectors(UP, target.divideScalar(reach));
      ram.scale.set(1, reach / length, 1);
    }
  }

  /** World position of the wire exit for the current angle. */
  sheaveWorld(out = new THREE.Vector3()) {
    return this.boat.localToWorld(this.sheaveLocal(this.angle, out));
  }

  /**
   * Place the hook and the master link, draw the wire, and the bridle legs from the link to ``slings``
   * (world attachment points on the vehicle frame). ``hook`` is the hook origin; ``link`` the master link.
   */
  draw(hook, link, slings) {
    const top = this._a.copy(hook).addScaledVector(UP, HOOK_TOP);
    stretchBetween(this.wire, this.sheaveWorld(this._b), top);
    if (this.hook) {
      this.hook.position.copy(this.hook.parent.worldToLocal(hook.clone()));
    } else {
      this.virtualHook.position.copy(hook);
    }
    this.link.position.copy(link);
    this.legs.forEach(function drawLeg(leg, i) {
      stretchBetween(leg, link, slings[i]);
    });
  }

  /** Hook origin that holds the master link at ``link``. */
  hookForLink(link, out = new THREE.Vector3()) {
    return out.copy(link).addScaledVector(UP, HOOK_BEND);
  }

  /** Remove the intro-only wire and bridle (the boat's own nodes stay where they are). */
  hideRigging() {
    this.group.visible = false;
  }

  dispose() {
    this.group.traverse(function free(o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
  }
}
