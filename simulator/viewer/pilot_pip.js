import {drawDetections} from './vision/overlay.js';
// Picture-in-picture "pilot at the console": a seated operator (Quaternius CC0 rig, IK hands on
// the grips) at the operator station of pilot_station.js, holding a gamepad whose sticks, triggers,
// bumpers and face buttons follow the live RC input, in front of a monitor that mirrors the main
// 3D view (flight-simulator style).
// The camera alternates between an over-the-shoulder shot (gamepad + monitor) and a front
// three-quarter shot (face + hands).
//
//   const pip = new PilotPiP(containerElement, { mirror: mainRenderer.domElement, human });
//   each frame: pip.update(dt, state.rc)
import * as THREE from 'three';
import { makeGamepad, makePerson, POSES, applyPose } from './figures.js';
import { Humanoid } from './humanoid.js';
import { buildPilotStation } from './pilot_station.js';

const V = (x, y, z) => new THREE.Vector3(x, y, z);
const PILOT_Z = -0.98;                          // pilot sits here facing +Z (the monitor)
const PAD_LOCAL = V(0, 0.88, 0.3);             // gamepad centre, pilot-local
const PAD_SCALE = 1.55;

export class PilotPiP {
  constructor(container, { mirror = null, width = 360, height = 230, human = null } = {}) {
    this.container = container;
    this.mirror = mirror;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    this.renderer.domElement.className = 'pilot-pip-canvas';
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    container.appendChild(this.renderer.domElement);

    const scene = (this.scene = new THREE.Scene());
    scene.background = new THREE.Color(0x0b141c);
    this.camera = new THREE.PerspectiveCamera(40, width / height, 0.05, 20);

    scene.add(new THREE.HemisphereLight(0xc4d6e4, 0x20262c, 2.0));
    const key = new THREE.DirectionalLight(0xfff1e0, 2.2); key.position.set(-1.6, 2.8, 1.2); scene.add(key);   // ceiling light in front
    const fill = new THREE.DirectionalLight(0xffffff, 0.9); fill.position.set(1.4, 1.6, -2.6); scene.add(fill);
    const rim = new THREE.DirectionalLight(0x8fb8ff, 0.8); rim.position.set(1.5, 1.8, 1.5); scene.add(rim);
    this.screenLight = new THREE.PointLight(0x5fc8ff, 0.7, 2.5); this.screenLight.position.set(0, 1.25, 0.4); scene.add(this.screenLight);

    // operator station (pilot_station.js): desk, monitors, topside case, chair; the main monitor mirrors the view
    this.screenCanvas = document.createElement('canvas');
    this.screenCanvas.width = 480; this.screenCanvas.height = 270;
    this.screenTex = new THREE.CanvasTexture(this.screenCanvas);
    this.screenTex.colorSpace = THREE.SRGBColorSpace;
    this.station = buildPilotStation(scene, { pilotZ: PILOT_Z, screenTexture: this.screenTex });

    // pilot
    if (human) {
      this.pilot = new Humanoid(human, { shirt: 0x1f3b57, pants: 0x2a2f36 });
      this.pilot.root.position.set(0, 0, PILOT_Z);
      this.pilot.play('Idle');
      scene.add(this.pilot.root);
    } else {
      this.fallback = makePerson({ vest: 0x2f6f4f, helmet: 0x303840 });
      this.fallback.root.position.set(0, 0, PILOT_Z);
      applyPose(this.fallback.j, POSES.seated); this.fallback.j.hips.position.y = 0.52;
      scene.add(this.fallback.root);
    }

    // gamepad: face tilted up towards the pilot's eyes
    this.pad = makeGamepad();
    this.pad.root.scale.setScalar(PAD_SCALE);
    scene.add(this.pad.root);

    this.t = 0;
    this.lastMirror = 0;
    this.flash = { X: 0, Y: 0 };
    this.prev = {};
  }

  update(dt, rc = {}) {
    this.t += dt;
    // the picture is small: 30 fps is plenty and halves its cost on a 60 Hz screen
    this._acc = (this._acc || 0) + dt;
    if (this._acc < 1 / 31) return;
    dt = this._acc; this._acc = 0;
    for (const [key, btn] of [['rc_lock', 'Y'], ['keep_depth', 'X']]) {       // toggles show as a press flash
      if (this.prev[key] !== undefined && this.prev[key] !== rc[key]) this.flash[btn] = 0.35;
      this.prev[key] = rc[key];
      this.flash[btn] = Math.max(0, this.flash[btn] - dt);
    }
    this.pad.set({ ...rc, _flashX: this.flash.X > 0, _flashY: this.flash.Y > 0 });
    const u = (v) => ((v ?? 1500) - 1500) / 500;

    // the pad follows the hands a little (people steer with their whole body)
    const lean = u(rc.right_lr) * 0.06 + u(rc.left_lr) * 0.03;
    const pad = this.pad.root;
    pad.position.set(PAD_LOCAL.x + lean * 0.3, PAD_LOCAL.y + u(rc.right_ud) * 0.012, PILOT_Z + PAD_LOCAL.z);
    pad.rotation.set(0.95 - u(rc.right_ud) * 0.05, Math.PI, -lean, 'XYZ');
    pad.updateMatrixWorld(true);

    if (this.pilot) {
      // pad-local points -> pilot-local; pad-local -x is the pilot's left once the pad faces him
      const P = (x, y, z) => this.pilot.root.worldToLocal(pad.localToWorld(V(x, y, z)));
      const faceUp = V(0, 0.35, 1).transformDirection(pad.matrixWorld);      // thumb side towards the face / up
      const cap = (st) => this.pilot.root.worldToLocal(st.localToWorld(V(0, 0, 0.016)));
      const grip = (sx, stick) => ({
        aim: P(sx * 0.085, -0.1, -0.035),        // fingers run down along the grip
        up: [faceUp.x, faceUp.y, faceUp.z],
        curl: P(sx * 0.07, -0.03, -0.065),       // wrap round the back of the grip
        thumb: cap(stick),                        // thumb tip on the stick cap
      });
      this.pilot.update(dt, {
        pelvis: [0, -0.24, -0.06],
        feet: [[0.15, 0.0, 0.4], [-0.15, 0.0, 0.36]],
        bend: 0.18 + u(rc.right_ud) * 0.03,
        lean: -lean * 0.8,
        head: [u(rc.left_lr) * 0.12 + Math.sin(this.t * 0.6) * 0.03, 0.12],
        handL: P(-0.1, -0.02, -0.01),         // wrists on the outside of the grips
        handR: P(0.1, -0.02, -0.01),
        gripL: grip(-1, this.pad.sticks.L),
        gripR: grip(1, this.pad.sticks.R),
      });
    }

    // mirror the main view onto the monitor at ~15 fps
    if (this.mirror && this.t - this.lastMirror > 1 / 15) {
      this.lastMirror = this.t;
      const ctx = this.screenCanvas.getContext('2d');
      try { ctx.drawImage(this.mirror, 0, 0, this.screenCanvas.width, this.screenCanvas.height); } catch (e) { /* not ready */ }
      drawDetections(ctx, window.rovVision?.detections || [], 480, 270);
      ctx.fillStyle = 'rgba(0,0,0,0.3)'; ctx.fillRect(0, 0, 480, 22);
      ctx.fillStyle = '#9fe3ff'; ctx.font = '14px monospace'; ctx.fillText('ROV CAM', 8, 16);
      ctx.fillStyle = (this.t % 1) < 0.5 ? '#ff4757' : '#7a2630'; ctx.fillText('● REC', 410, 16);
      this.screenTex.needsUpdate = true;
    }
    this.screenLight.intensity = 0.7 + Math.sin(this.t * 13) * 0.05;
    this.station.update(this.t, rc);

    // camera: over-the-shoulder (pad + monitor) <-> front three-quarter (face + hands), 9 s each
    const phase = (this.t % 18) < 9 ? 0 : 1;
    const drift = Math.sin(this.t * 0.25) * 0.05;
    const want = phase === 0
      ? [V(0.78 + drift, 1.72, PILOT_Z - 0.3), V(-0.08, 0.9, PILOT_Z + 0.55)]
      : [V(-0.8 + drift, 1.32, PILOT_Z + 0.98), V(0.02, 1.02, PILOT_Z + 0.12)];
    if (!this._cp || this._phase !== phase) { this._cp = want[0].clone(); this._cl = want[1].clone(); this._phase = phase; }
    this._cp.lerp(want[0], 0.1); this._cl.lerp(want[1], 0.1);
    this.camera.position.copy(this._cp);
    this.camera.lookAt(this._cl);
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
