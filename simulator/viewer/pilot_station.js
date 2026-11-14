// Operator station for the pilot picture-in-picture: a console desk with three monitors (main ROV video,
// telemetry, sonar), a rugged topside control case with an open lid, keyboard, headset, an office chair and the
// room around it. Procedural three.js geometry in metres, Y up; the pilot sits at z = pilotZ facing +Z.
// The main monitor shows the texture handed in (the mirrored ROV view); the side screens are drawn here.
//
//   const station = buildPilotStation(scene, { pilotZ: -0.98, screenTexture });
//   each frame: station.update(t, rc)
import * as THREE from 'three';

const STRINGS = {
  depth: 'DEPTH',
  heading: 'HDG',
  tether: 'TETHER',
  sonar: 'SONAR 30 m',
  power: 'POWER',
  leak: 'LEAK',
};

const SIDE_SCREEN_HZ = 2;

function material(color, options = {}) {
  return new THREE.MeshStandardMaterial({ color, roughness: 0.6, metalness: 0.1, ...options });
}

function place(parent, geometry, mat, position, rotation = null) {
  const mesh = new THREE.Mesh(geometry, mat);
  mesh.position.set(position[0], position[1], position[2]);
  if (rotation) mesh.rotation.set(rotation[0], rotation[1], rotation[2]);
  mesh.castShadow = true;
  mesh.receiveShadow = true;
  parent.add(mesh);
  return mesh;
}

function roundedBox(w, h, d, r) {
  const shape = new THREE.Shape();
  shape.moveTo(-w / 2 + r, -d / 2);
  shape.lineTo(w / 2 - r, -d / 2);
  shape.quadraticCurveTo(w / 2, -d / 2, w / 2, -d / 2 + r);
  shape.lineTo(w / 2, d / 2 - r);
  shape.quadraticCurveTo(w / 2, d / 2, w / 2 - r, d / 2);
  shape.lineTo(-w / 2 + r, d / 2);
  shape.quadraticCurveTo(-w / 2, d / 2, -w / 2, d / 2 - r);
  shape.lineTo(-w / 2, -d / 2 + r);
  shape.quadraticCurveTo(-w / 2, -d / 2, -w / 2 + r, -d / 2);
  const geometry = new THREE.ExtrudeGeometry(shape, { depth: h, bevelEnabled: true, bevelSize: Math.min(r, h) * 0.4,
    bevelThickness: Math.min(r, h) * 0.4, bevelSegments: 2, curveSegments: 4 });
  geometry.rotateX(-Math.PI / 2);
  geometry.translate(0, -h / 2, 0);
  return geometry;
}

function screenCanvas(width, height) {
  const canvas = document.createElement('canvas');
  canvas.width = width;
  canvas.height = height;
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return { canvas, texture };
}

/** Monitor on a stand: bezel, screen plane facing -Z (towards the pilot), neck and foot. */
function monitor(parent, frame, texture, { w, h, position, yaw = 0, standHeight = 0.3 }) {
  const group = new THREE.Group();
  group.position.set(position[0], position[1], position[2]);
  group.rotation.y = yaw;
  parent.add(group);
  place(group, roundedBox(w + 0.04, 0.035, h + 0.04, 0.012), frame, [0, 0, 0.018], [Math.PI / 2, 0, 0]);
  const screen = new THREE.Mesh(new THREE.PlaneGeometry(w, h),
    new THREE.MeshBasicMaterial({ map: texture, toneMapped: false }));
  screen.rotation.y = Math.PI;
  screen.position.z = -0.009;                     // in front of the bezel's bevel
  group.add(screen);
  place(group, new THREE.BoxGeometry(0.06, standHeight, 0.03), frame, [0, -h / 2 - standHeight / 2 + 0.05, 0.06]);
  place(group, roundedBox(0.24, 0.015, 0.18, 0.03), frame, [0, -h / 2 - standHeight + 0.05, 0.08]);
  return group;
}

function buildRoom(scene) {
  const floor = place(scene, new THREE.PlaneGeometry(8, 8), material(0x1d2329, { roughness: 0.95 }), [0, 0, 0],
    [-Math.PI / 2, 0, 0]);
  floor.castShadow = false;
  place(scene, new THREE.BoxGeometry(1.3, 0.012, 1.0), material(0x111417, { roughness: 1 }), [0, 0.006, -0.85]);
  const wall = place(scene, new THREE.PlaneGeometry(8, 3), material(0x1b2731, { roughness: 0.9 }), [0, 1.5, 1.6],
    [0, Math.PI, 0]);
  wall.castShadow = false;
  const panel = material(0x223240, { roughness: 1 });
  for (let i = -2; i <= 2; i++) {
    place(scene, new THREE.BoxGeometry(0.58, 0.9, 0.04), panel, [i * 0.62, 1.75, 1.57]);
  }
  place(scene, new THREE.BoxGeometry(1.6, 0.03, 0.22), material(0x2b3238), [0.2, 2.25, 1.47]);
  place(scene, new THREE.BoxGeometry(0.3, 0.22, 0.18), material(0xd9a400, { roughness: 0.45 }), [0.65, 2.38, 1.47]);
  place(scene, new THREE.CylinderGeometry(0.11, 0.11, 0.2, 20), material(0x2a2f34), [-0.2, 2.37, 1.47],
    [0, 0, Math.PI / 2]);
}

function buildDesk(scene) {
  const top = material(0x2f363d, { roughness: 0.55 });
  const frame = material(0x1a1f24, { roughness: 0.5, metalness: 0.4 });
  place(scene, roundedBox(1.7, 0.035, 0.75, 0.03), top, [0, 0.75, 0.35]);
  place(scene, new THREE.BoxGeometry(1.7, 0.04, 0.02), material(0x15191d), [0, 0.725, -0.015]);
  for (const x of [-0.8, 0.8]) {
    place(scene, new THREE.BoxGeometry(0.05, 0.72, 0.06), frame, [x, 0.36, 0.05]);
    place(scene, new THREE.BoxGeometry(0.05, 0.72, 0.06), frame, [x, 0.36, 0.65]);
    place(scene, new THREE.BoxGeometry(0.06, 0.04, 0.7), frame, [x, 0.02, 0.35]);
  }
  place(scene, new THREE.BoxGeometry(1.55, 0.05, 0.04), frame, [0, 0.62, 0.68]);
  const cabinet = material(0x262c32, { roughness: 0.6 });
  place(scene, new THREE.BoxGeometry(0.42, 0.62, 0.6), cabinet, [0.52, 0.36, 0.38]);
  for (let i = 0; i < 3; i++) {
    const y = 0.17 + i * 0.19;
    place(scene, new THREE.BoxGeometry(0.4, 0.17, 0.01), material(0x2d343b), [0.52, y, 0.075]);
    place(scene, new THREE.BoxGeometry(0.12, 0.015, 0.02), material(0x8a939a, { metalness: 0.6 }), [0.52, y + 0.05,
      0.065]);
  }
  place(scene, new THREE.BoxGeometry(1.4, 0.05, 0.12), frame, [0, 0.68, 0.62]);
}

function buildTopsideCase(scene) {
  const shell = material(0xd9a400, { roughness: 0.45 });
  const dark = material(0x1c2024, { roughness: 0.5 });
  const group = new THREE.Group();
  group.position.set(-0.56, 0.77, 0.42);
  group.rotation.y = 0.35;
  scene.add(group);
  place(group, roundedBox(0.42, 0.13, 0.3, 0.03), shell, [0, 0.065, 0]);
  place(group, new THREE.BoxGeometry(0.38, 0.01, 0.26), dark, [0, 0.13, 0]);
  place(group, new THREE.BoxGeometry(0.42, 0.3, 0.045), shell, [0, 0.27, 0.16], [-0.25, 0, 0]);
  place(group, new THREE.BoxGeometry(0.36, 0.24, 0.01), dark, [0, 0.27, 0.13], [-0.25, 0, 0]);
  for (let i = 0; i < 4; i++) {
    place(group, new THREE.CylinderGeometry(0.008, 0.008, 0.02, 10), material(0x9aa3aa, { metalness: 0.6 }),
      [-0.13 + i * 0.05, 0.145, -0.06]);
  }
  const leds = [];
  for (let i = 0; i < 5; i++) {
    const led = place(group, new THREE.BoxGeometry(0.018, 0.006, 0.01),
      new THREE.MeshStandardMaterial({ color: 0x0a2a12, emissive: 0x2cff6a, emissiveIntensity: 0.2 }),
      [0.04 + i * 0.026, 0.138, -0.06]);
    leds.push(led);
  }
  place(group, new THREE.CylinderGeometry(0.02, 0.02, 0.02, 16), material(0xc0392b), [0.13, 0.145, 0.06]);
  place(group, new THREE.CylinderGeometry(0.012, 0.012, 0.03, 12), dark, [-0.13, 0.15, 0.06]);
  const cable = new THREE.TubeGeometry(new THREE.CatmullRomCurve3([
    new THREE.Vector3(-0.21, 0.05, 0.05), new THREE.Vector3(-0.35, 0.0, 0.2), new THREE.Vector3(-0.38, -0.3, 0.25),
    new THREE.Vector3(-0.3, -0.75, 0.3)]), 24, 0.008, 6);
  place(group, cable, material(0xe9c534, { roughness: 0.5 }), [0, 0, 0]);
  return leds;
}

function buildDeskItems(scene) {
  const dark = material(0x16191c, { roughness: 0.6 });
  place(scene, roundedBox(0.44, 0.02, 0.15, 0.015), dark, [0.25, 0.778, 0.2], [0, -0.12, 0]);
  const keys = material(0x2a2f34, { roughness: 0.8 });
  for (let r = 0; r < 4; r++) {
    for (let c = 0; c < 12; c++) {
      place(scene, new THREE.BoxGeometry(0.026, 0.008, 0.024), keys,
        [0.25 + (c - 5.5) * 0.031 * Math.cos(0.12) + (r - 1.5) * 0.03 * Math.sin(0.12), 0.792,
          0.2 + (r - 1.5) * 0.03 * Math.cos(0.12) - (c - 5.5) * 0.031 * Math.sin(0.12)], [0, -0.12, 0]);
    }
  }
  place(scene, new THREE.SphereGeometry(0.03, 14, 10), dark, [0.58, 0.785, 0.18]).scale.set(1, 0.5, 1.5);
  place(scene, new THREE.CylinderGeometry(0.04, 0.035, 0.1, 18), material(0xe8e4dc, { roughness: 0.4 }),
    [-0.3, 0.818, 0.12]);
  place(scene, new THREE.BoxGeometry(0.21, 0.01, 0.29), material(0xe6e2d6, { roughness: 0.9 }), [-0.2, 0.773,
    0.08], [0, 0.3, 0]);
  const band = new THREE.TorusGeometry(0.09, 0.008, 6, 24, Math.PI);
  place(scene, band, dark, [0.74, 0.95, 0.55], [0, Math.PI / 2, 0]);
  for (const z of [0.46, 0.64]) {
    place(scene, new THREE.CylinderGeometry(0.04, 0.04, 0.03, 18), dark, [0.74, 0.88, z], [Math.PI / 2, 0, 0]);
  }
}

function buildChair(scene, pilotZ) {
  const fabric = material(0x1f252b, { roughness: 0.95 });
  const metal = material(0x14171a, { roughness: 0.4, metalness: 0.5 });
  place(scene, roundedBox(0.5, 0.08, 0.48, 0.05), fabric, [0, 0.47, pilotZ + 0.02]);
  place(scene, roundedBox(0.46, 0.06, 0.56, 0.05), fabric, [0, 0.86, pilotZ - 0.27], [Math.PI / 2 - 0.1, 0, 0]);
  place(scene, new THREE.BoxGeometry(0.05, 0.3, 0.03), metal, [0, 0.55, pilotZ - 0.26], [-0.1, 0, 0]);
  place(scene, new THREE.CylinderGeometry(0.028, 0.028, 0.34, 14), metal, [0, 0.25, pilotZ]);
  for (let i = 0; i < 5; i++) {
    const a = (i / 5) * Math.PI * 2;
    const leg = place(scene, new THREE.BoxGeometry(0.04, 0.03, 0.3), metal,
      [Math.sin(a) * 0.14, 0.07, pilotZ + Math.cos(a) * 0.14], [0, a, 0]);
    leg.rotation.order = 'YXZ';
    place(scene, new THREE.SphereGeometry(0.025, 10, 8), metal, [Math.sin(a) * 0.29, 0.025,
      pilotZ + Math.cos(a) * 0.29]);
  }
}

function drawTelemetry(ctx, w, h, t, rc) {
  ctx.fillStyle = '#071118';
  ctx.fillRect(0, 0, w, h);
  ctx.strokeStyle = '#1f4252';
  for (let x = 0; x < w; x += 32) {
    ctx.beginPath();
    ctx.moveTo(x, 40);
    ctx.lineTo(x, h - 10);
    ctx.stroke();
  }
  const heading = (214 + ((rc?.left_lr ?? 1500) - 1500) * 0.02 + Math.sin(t * 0.2) * 3 + 360) % 360;
  const depth = 12.4 + Math.sin(t * 0.13) * 0.3;
  ctx.fillStyle = '#9fe3ff';
  ctx.font = 'bold 22px monospace';
  ctx.fillText(`${STRINGS.depth} ${depth.toFixed(1)} m`, 14, 30);
  ctx.fillText(`${STRINGS.heading} ${heading.toFixed(0).padStart(3, '0')}`, 14, 62);
  ctx.fillText(`${STRINGS.tether} 38 m`, 14, 94);
  ctx.strokeStyle = '#4fd1ff';
  ctx.lineWidth = 2;
  ctx.beginPath();
  for (let x = 0; x < w; x += 4) {
    const y = h - 50 - Math.sin(x * 0.03 + t) * 18 - Math.sin(x * 0.011 + t * 0.4) * 22;
    if (x === 0) ctx.moveTo(x, y);
    else ctx.lineTo(x, y);
  }
  ctx.stroke();
  ctx.fillStyle = '#5be37d';
  ctx.fillText(`${STRINGS.power} OK  ${STRINGS.leak} OK`, 14, h - 14);
}

function drawSonar(ctx, w, h, t) {
  ctx.fillStyle = '#040b0e';
  ctx.fillRect(0, 0, w, h);
  const cx = w / 2;
  const cy = h - 12;
  const r = h - 30;
  for (let k = 0; k < 900; k++) {
    const a = -Math.PI / 2 + (k % 60 - 30) / 60 * 2.1;
    const d = ((k * 37) % 97) / 97;
    const echo = Math.max(0, Math.sin(a * 7 + t * 0.3) * 0.5 + 0.5 - Math.abs(d - 0.7) * 2.4);
    ctx.fillStyle = `rgba(255, ${150 + echo * 90 | 0}, 40, ${0.08 + echo * 0.8})`;
    ctx.fillRect(cx + Math.cos(a) * r * d - 2, cy + Math.sin(a) * r * d - 2, 4, 4);
  }
  ctx.strokeStyle = '#3c6d78';
  ctx.beginPath();
  ctx.moveTo(cx, cy);
  ctx.arc(cx, cy, r, -Math.PI / 2 - 1.05, -Math.PI / 2 + 1.05);
  ctx.closePath();
  ctx.stroke();
  ctx.fillStyle = '#9fe3ff';
  ctx.font = '16px monospace';
  ctx.fillText(STRINGS.sonar, 10, 22);
}

/** Build the station into ``scene``; returns an updater for the side screens and status LEDs. */
export function buildPilotStation(scene, { pilotZ, screenTexture }) {
  buildRoom(scene);
  buildDesk(scene);
  const frame = material(0x0e1013, { roughness: 0.4 });
  monitor(scene, frame, screenTexture, { w: 0.96, h: 0.54, position: [0, 1.3, 0.5], standHeight: 0.3 });
  const telemetry = screenCanvas(384, 256);
  const sonar = screenCanvas(320, 224);
  monitor(scene, frame, telemetry.texture, { w: 0.5, h: 0.33, position: [-0.85, 1.12, 0.36], yaw: -0.55,
    standHeight: 0.18 });
  monitor(scene, frame, sonar.texture, { w: 0.44, h: 0.3, position: [0.84, 1.1, 0.38], yaw: 0.55,
    standHeight: 0.17 });
  const leds = buildTopsideCase(scene);
  buildDeskItems(scene);
  buildChair(scene, pilotZ);
  let last = -1;
  function update(t, rc) {
    if (t - last < 1 / SIDE_SCREEN_HZ) return;
    last = t;
    drawTelemetry(telemetry.canvas.getContext('2d'), telemetry.canvas.width, telemetry.canvas.height, t, rc);
    telemetry.texture.needsUpdate = true;
    drawSonar(sonar.canvas.getContext('2d'), sonar.canvas.width, sonar.canvas.height, t);
    sonar.texture.needsUpdate = true;
    leds.forEach(function blink(led, i) {
      led.material.emissiveIntensity = (Math.sin(t * 3 + i) > -0.3) ? 1.2 : 0.15;
    });
  }
  return { update };
}
