// Picture-in-picture "pilot at the console" view: a seated operator holding a gamepad whose
// sticks, triggers, bumpers and face buttons follow the live RC input, in front of a monitor
// that mirrors the main 3D view (flight-simulator style).
//
//   const pip = new PilotPiP(containerElement, { mirror: mainRenderer.domElement });
//   each frame: pip.update(dt, state.rc)
import * as THREE from 'three';
import { makePerson, makeGamepad, POSES, applyPose } from './figures.js';

export class PilotPiP {
  constructor(container, { mirror = null, width = 360, height = 230 } = {}) {
    this.container = container;
    this.mirror = mirror;
    this.renderer = new THREE.WebGLRenderer({ antialias: true, alpha: false, preserveDrawingBuffer: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
    this.renderer.setSize(width, height, false);
    this.renderer.domElement.className = 'pilot-pip-canvas';
    this.renderer.domElement.style.width = '100%';
    this.renderer.domElement.style.height = '100%';
    container.appendChild(this.renderer.domElement);
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;

    const scene = (this.scene = new THREE.Scene());
    scene.background = new THREE.Color(0x0b141c);
    this.camera = new THREE.PerspectiveCamera(38, width / height, 0.05, 20);

    scene.add(new THREE.HemisphereLight(0x9fb8c8, 0x101418, 0.9));
    const key = new THREE.DirectionalLight(0xffffff, 1.4); key.position.set(-1.5, 2.5, 2); scene.add(key);
    this.screenLight = new THREE.PointLight(0x5fc8ff, 1.2, 3); this.screenLight.position.set(0, 1.25, 0.55); scene.add(this.screenLight);

    // console desk + monitor (the monitor faces the pilot along -Z; the pilot sits at z = -0.9 facing +Z)
    const desk = new THREE.Mesh(new THREE.BoxGeometry(1.6, 0.06, 0.7), new THREE.MeshStandardMaterial({ color: 0x2a3138, roughness: 0.8 }));
    desk.position.set(0, 0.74, 0.25); scene.add(desk);
    const stand = new THREE.Mesh(new THREE.BoxGeometry(0.08, 0.3, 0.08), new THREE.MeshStandardMaterial({ color: 0x1a1d21 }));
    stand.position.set(0, 0.92, 0.45); scene.add(stand);
    this.screenCanvas = document.createElement('canvas');
    this.screenCanvas.width = 480; this.screenCanvas.height = 270;
    this.screenTex = new THREE.CanvasTexture(this.screenCanvas);
    this.screenTex.colorSpace = THREE.SRGBColorSpace;
    const monitor = new THREE.Mesh(new THREE.PlaneGeometry(0.96, 0.54), new THREE.MeshBasicMaterial({ map: this.screenTex }));
    monitor.position.set(0, 1.33, 0.46); monitor.rotation.y = Math.PI; scene.add(monitor);
    const bezel = new THREE.Mesh(new THREE.BoxGeometry(1.0, 0.58, 0.03), new THREE.MeshStandardMaterial({ color: 0x111316 }));
    bezel.position.set(0, 1.33, 0.48); scene.add(bezel);
    const chair = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.08, 0.5), new THREE.MeshStandardMaterial({ color: 0x20252b }));
    chair.position.set(0, 0.46, -0.95); scene.add(chair);
    const back = new THREE.Mesh(new THREE.BoxGeometry(0.5, 0.6, 0.06), new THREE.MeshStandardMaterial({ color: 0x20252b }));
    back.position.set(0, 0.8, -1.2); back.rotation.x = 0.12; scene.add(back);

    // pilot: seated, facing the monitor (+Z)
    this.pilot = makePerson({ vest: 0x2f6f4f, helmet: 0x303840 });
    this.pilot.root.position.set(0, 0, -0.98);
    scene.add(this.pilot.root);
    applyPose(this.pilot.j, POSES.seated);
    this.pilot.j.hips.position.y = 0.52;

    // gamepad held between the hands (re-positioned every frame), face tilted up towards the eyes
    this.pad = makeGamepad();
    this.pad.root.scale.setScalar(1.6);
    scene.add(this.pad.root);
    this._hL = new THREE.Vector3(); this._hR = new THREE.Vector3();

    this.t = 0;
    this.lastMirror = 0;
    this.flash = { X: 0, Y: 0 };
    this.prev = {};
  }

  _thumbs() {
    // bend forearms so the hands sit on the grips; small twitches follow the sticks
    const j = this.pilot.j;
    j.shoulderL.rotation.set(-0.72, 0, 0.32); j.shoulderR.rotation.set(-0.72, 0, -0.32);
    j.elbowL.rotation.x = -1.05; j.elbowR.rotation.x = -1.05;
  }

  update(dt, rc = {}) {
    this.t += dt;
    // toggles (lock / depth hold) show as a short press flash
    for (const [key, btn] of [['rc_lock', 'Y'], ['keep_depth', 'X']]) {
      if (this.prev[key] !== undefined && this.prev[key] !== rc[key]) this.flash[btn] = 0.35;
      this.prev[key] = rc[key];
      this.flash[btn] = Math.max(0, this.flash[btn] - dt);
    }
    this.pad.set({ ...rc, _flashX: this.flash.X > 0, _flashY: this.flash.Y > 0 });
    this._thumbs();
    const u = (v) => ((v ?? 1500) - 1500) / 500;
    // body language: lean with the sticks a little, head bob
    this.pilot.j.spine.rotation.z = -u(rc.right_lr) * 0.05 - u(rc.left_lr) * 0.04;
    this.pilot.j.spine.rotation.x = POSES.seated.spineX + u(rc.right_ud) * 0.05;
    this.pilot.j.head.rotation.y = u(rc.left_lr) * 0.12 + Math.sin(this.t * 0.7) * 0.03;
    // keep the pad in the hands
    this.pilot.root.updateMatrixWorld(true);
    this.pilot.j.handL.getWorldPosition(this._hL); this.pilot.j.handR.getWorldPosition(this._hR);
    this.pad.root.position.lerpVectors(this._hL, this._hR, 0.5).add(new THREE.Vector3(0, -0.02, 0.03));
    this.pad.root.rotation.set(-1.05, 0, -u(rc.right_lr) * 0.08);

    // mirror the main view onto the monitor at ~15 fps
    if (this.mirror && this.t - this.lastMirror > 1 / 15) {
      this.lastMirror = this.t;
      const ctx = this.screenCanvas.getContext('2d');
      try { ctx.drawImage(this.mirror, 0, 0, this.screenCanvas.width, this.screenCanvas.height); } catch (e) { /* not ready */ }
      ctx.fillStyle = 'rgba(0,0,0,0.25)'; ctx.fillRect(0, 0, 480, 22);
      ctx.fillStyle = '#9fe3ff'; ctx.font = '14px monospace'; ctx.fillText('ROV CAM  ●REC', 8, 16);
      this.screenTex.needsUpdate = true;
    }
    this.screenLight.intensity = 1.0 + Math.sin(this.t * 13) * 0.08;

    // over-the-shoulder camera that slowly drifts; the gamepad stays in frame
    // front three-quarter shot from beside the monitor: face, hands and gamepad in frame
    const a = Math.sin(this.t * 0.15) * 0.12;
    this.camera.position.set(-0.62 + a, 1.28, 0.05);
    this.camera.lookAt(0.02, 0.98, -0.62);
    this.renderer.render(this.scene, this.camera);
  }

  dispose() {
    this.renderer.dispose();
    this.renderer.domElement.remove();
  }
}
