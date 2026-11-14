// Particle and light effects for the deploy intro: a gentle set-down splash (the vehicle is lowered, not thrown),
// expanding surface rings and foam, thruster wash bubbles, rising bubbles while the vehicle submerges, and the
// lamp glow used for the surface function check. All effects are plain three.js objects added to the scene by
// the caller; update(dt) advances them and dispose() frees their GPU resources.
import * as THREE from 'three';

const RING_COUNT = 6;
const GRAVITY = -9.81;

function makeParticles(count, color, size, map) {
  const geometry = new THREE.BufferGeometry();
  const positions = new Float32Array(count * 3).fill(-9999);
  geometry.setAttribute('position', new THREE.BufferAttribute(positions, 3));
  const material = new THREE.PointsMaterial({ color, size, map, transparent: true, opacity: 0.9, depthWrite: false,
    alphaTest: 0.05 });
  const points = new THREE.Points(geometry, material);
  points.frustumCulled = false;
  points.userData.velocity = new Float32Array(count * 3);
  points.userData.life = new Float32Array(count);
  points.userData.next = 0;
  return points;
}

function spawn(points, at, velocity, life) {
  const data = points.userData;
  const i = data.next;
  data.next = (i + 1) % data.life.length;
  const position = points.geometry.attributes.position.array;
  position[i * 3] = at.x;
  position[i * 3 + 1] = at.y;
  position[i * 3 + 2] = at.z;
  data.velocity[i * 3] = velocity.x;
  data.velocity[i * 3 + 1] = velocity.y;
  data.velocity[i * 3 + 2] = velocity.z;
  data.life[i] = life;
}

function stepParticles(points, dt, gravity, drag, keep) {
  const position = points.geometry.attributes.position.array;
  const velocity = points.userData.velocity;
  const life = points.userData.life;
  const damping = Math.max(0, 1 - drag * dt);
  for (let i = 0; i < life.length; i++) {
    if (life[i] <= 0) {
      position[i * 3 + 1] = -9999;
      continue;
    }
    life[i] -= dt;
    velocity[i * 3 + 1] += gravity * dt;
    velocity[i * 3] *= damping;
    velocity[i * 3 + 2] *= damping;
    position[i * 3] += velocity[i * 3] * dt;
    position[i * 3 + 1] += velocity[i * 3 + 1] * dt;
    position[i * 3 + 2] += velocity[i * 3 + 2] * dt;
    if (!keep(position[i * 3 + 1])) life[i] = 0;
  }
  points.geometry.attributes.position.needsUpdate = true;
}

function makeGlowTexture() {
  const size = 64;
  const canvas = document.createElement('canvas');
  canvas.width = size;
  canvas.height = size;
  const context = canvas.getContext('2d');
  const gradient = context.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  gradient.addColorStop(0, 'rgba(255,255,250,1)');
  gradient.addColorStop(0.25, 'rgba(255,244,214,0.8)');
  gradient.addColorStop(1, 'rgba(255,236,200,0)');
  context.fillStyle = gradient;
  context.fillRect(0, 0, size, size);
  const texture = new THREE.CanvasTexture(canvas);
  texture.colorSpace = THREE.SRGBColorSpace;
  return texture;
}

function makeRing() {
  const material = new THREE.MeshBasicMaterial({
    color: 0xffffff, transparent: true, opacity: 0, side: THREE.DoubleSide, depthWrite: false,
  });
  const ring = new THREE.Mesh(new THREE.RingGeometry(0.85, 1.0, 48), material);
  ring.rotation.x = -Math.PI / 2;
  ring.visible = false;
  ring.userData = { age: 0, life: 1, grow: 1, alpha: 0.5 };
  return ring;
}

export class IntroEffects {
  constructor() {
    this.group = new THREE.Group();
    this.glowTexture = makeGlowTexture();
    this.splash = makeParticles(260, 0xf2fbff, 0.07, this.glowTexture);
    this.bubbles = makeParticles(360, 0xcfefff, 0.05, this.glowTexture);
    this.group.add(this.splash, this.bubbles);
    this.rings = [];
    for (let i = 0; i < RING_COUNT; i++) {
      const ring = makeRing();
      this.rings.push(ring);
      this.group.add(ring);
    }
    this.foam = new THREE.Mesh(new THREE.CircleGeometry(0.9, 40),
      new THREE.MeshBasicMaterial({ color: 0xf4fbff, transparent: true, opacity: 0, depthWrite: false }));
    this.foam.rotation.x = -Math.PI / 2;
    this.foam.visible = false;
    this.group.add(this.foam);
    this.lamps = [];
    for (let i = 0; i < 2; i++) {
      const sprite = new THREE.Sprite(new THREE.SpriteMaterial({
        map: this.glowTexture, color: 0xfff4dc, transparent: true, opacity: 0, depthWrite: false,
        depthTest: false, blending: THREE.AdditiveBlending,
      }));
      sprite.renderOrder = 10;                     // lamps sit just under the surface: glow through the water
      sprite.scale.setScalar(0.32);
      sprite.visible = false;
      this.lamps.push(sprite);
      this.group.add(sprite);
    }
    this.lampLight = new THREE.PointLight(0xfff2dc, 0, 6, 1.6);
    this.group.add(this.lampLight);
    this._velocity = new THREE.Vector3();
    this._point = new THREE.Vector3();
  }

  /** Small set-down splash: the vehicle meets the water at lowering speed (well under 1 m/s). */
  setDown(at) {
    for (let i = 0; i < 160; i++) {
      const angle = Math.random() * Math.PI * 2;
      const radius = 0.25 + Math.random() * 0.2;
      this._point.set(at.x + Math.cos(angle) * radius, 0.03, at.z + Math.sin(angle) * radius);
      const out = 0.3 + Math.random() * 0.6;
      this._velocity.set(Math.cos(angle) * out, 0.6 + Math.random() * 1.1, Math.sin(angle) * out);
      spawn(this.splash, this._point, this._velocity, 0.5 + Math.random() * 0.5);
    }
    this.ripple(at, { size: 0.45, grow: 1.4, life: 2.6, alpha: 0.55 });
    this.foam.position.set(at.x, 0.022, at.z);
    this.foam.scale.setScalar(0.7);
    this.foam.visible = true;
    this.foamAge = 0;
  }

  /** Expanding surface ring (set-down, thruster wash). */
  ripple(at, { size = 0.3, grow = 1.2, life = 1.6, alpha = 0.45 } = {}) {
    const ring = this.rings.reduce(function oldest(a, b) {
      return a.userData.age / a.userData.life >= b.userData.age / b.userData.life ? a : b;
    });
    ring.position.set(at.x, 0.03, at.z);
    ring.scale.setScalar(size);
    ring.visible = true;
    ring.userData = { age: 0, life, grow, alpha, size };
  }

  /** ``count`` bubbles around ``at`` with an initial push along ``push`` (thruster wash) and buoyant rise. */
  bubble(at, count = 1, push = null, spread = 0.25) {
    for (let k = 0; k < count; k++) {
      this._point.set(at.x + (Math.random() - 0.5) * spread, at.y + (Math.random() - 0.5) * spread * 0.6,
        at.z + (Math.random() - 0.5) * spread);
      this._velocity.set((Math.random() - 0.5) * 0.2, 0.4 + Math.random() * 0.6, (Math.random() - 0.5) * 0.2);
      if (push) this._velocity.add(push);
      spawn(this.bubbles, this._point, this._velocity, 2.2);
    }
  }

  /** Lamp glow at the given world positions with brightness 0..1 (0 hides it). */
  setLamps(positions, level) {
    const on = level > 0.01;
    this.lamps.forEach(function placeLamp(sprite, i) {
      sprite.visible = on && !!positions[i];
      if (!sprite.visible) return;
      sprite.position.copy(positions[i]);
      sprite.material.opacity = level;
    });
    this.lampLight.intensity = on ? level * 25 : 0;
    if (on && positions[0]) this.lampLight.position.copy(positions[0]).lerp(positions[1] || positions[0], 0.5);
  }

  update(dt) {
    stepParticles(this.splash, dt, GRAVITY, 0.8, function aboveWater(y) {
      return y >= 0;
    });
    stepParticles(this.bubbles, dt, 0.5, 0.6, function belowSurface(y) {
      return y <= -0.03;
    });
    for (const ring of this.rings) {
      if (!ring.visible) continue;
      const data = ring.userData;
      data.age += dt;
      ring.scale.setScalar(data.size + data.age * data.grow);
      ring.material.opacity = Math.max(0, data.alpha * (1 - data.age / data.life));
      if (data.age >= data.life) ring.visible = false;
    }
    if (this.foam.visible) {
      this.foamAge += dt;
      this.foam.scale.setScalar(0.7 + this.foamAge * 0.35);
      this.foam.material.opacity = Math.max(0, 0.55 - this.foamAge * 0.14);
      if (this.foamAge > 4) this.foam.visible = false;
    }
  }

  /** Hide everything (end of the intro). */
  clear() {
    this.splash.userData.life.fill(0);
    this.bubbles.userData.life.fill(0);
    this.update(0);
    for (const ring of this.rings) ring.visible = false;
    this.foam.visible = false;
    this.setLamps([], 0);
  }

  dispose() {
    this.group.traverse(function free(o) {
      if (o.geometry) o.geometry.dispose();
      if (o.material) o.material.dispose();
    });
    this.glowTexture.dispose();
  }
}
