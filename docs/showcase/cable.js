// A cable drawn as a tube whose geometry is allocated once and updated in place every frame
// (rebuilding a TubeGeometry per frame churns memory and stutters on slower laptops).
//
//   const cable = new Cable(material, { radius: 0.0065, segments: 240, radial: 8, colors: true });
//   scene.add(cable.mesh);
//   each frame: cable.update(points /* Vector3[] */, (s, colour) => { … })   // s = 0..1 along the cable
import * as THREE from 'three';

export class Cable {
  constructor(material, { radius = 0.0065, segments = 240, radial = 8, colors = false } = {}) {
    this.radius = radius; this.S = segments; this.R = radial;
    const nv = (segments + 1) * (radial + 1);
    const g = (this.geometry = new THREE.BufferGeometry());
    this.pos = new Float32Array(nv * 3); this.nrm = new Float32Array(nv * 3);
    g.setAttribute('position', new THREE.BufferAttribute(this.pos, 3).setUsage(THREE.DynamicDrawUsage));
    g.setAttribute('normal', new THREE.BufferAttribute(this.nrm, 3).setUsage(THREE.DynamicDrawUsage));
    if (colors) {
      this.col = new Float32Array(nv * 3);
      g.setAttribute('color', new THREE.BufferAttribute(this.col, 3).setUsage(THREE.DynamicDrawUsage));
    }
    const idx = [];
    for (let i = 0; i < segments; i++) {
      for (let j = 0; j < radial; j++) {
        const a = i * (radial + 1) + j, b = a + radial + 1;
        idx.push(a, b, a + 1, b, b + 1, a + 1);
      }
    }
    g.setIndex(idx);
    this.mesh = new THREE.Mesh(g, material);
    this.mesh.frustumCulled = false;
    this.mesh.visible = false;
    this.curve = new THREE.CatmullRomCurve3([], false, 'centripetal');
    this._p = Array.from({ length: segments + 1 }, () => new THREE.Vector3());
    this._t = new THREE.Vector3(); this._n = new THREE.Vector3(); this._b = new THREE.Vector3();
    this._c = new THREE.Color();
  }

  update(points, colorAt = null) {
    if (!points || points.length < 2) { this.mesh.visible = false; return; }
    this.mesh.visible = true;
    const { S, R, radius, _p: P, _t: T, _n: N, _b: B } = this;
    this.curve.points = points;
    for (let i = 0; i <= S; i++) this.curve.getPoint(i / S, P[i]);
    // parallel-transport frames so the tube does not twist
    let k = 0;
    for (let i = 0; i <= S; i++) {
      T.subVectors(P[Math.min(S, i + 1)], P[Math.max(0, i - 1)]);
      if (T.lengthSq() < 1e-12) T.set(0, 1, 0);
      T.normalize();
      if (i === 0) {
        N.set(0, 1, 0); if (Math.abs(T.y) > 0.9) N.set(1, 0, 0);
      }
      N.addScaledVector(T, -N.dot(T));
      if (N.lengthSq() < 1e-12) N.set(T.z, 0, -T.x);
      N.normalize();
      B.crossVectors(T, N);
      if (colorAt && this.col) colorAt(i / S, this._c);
      for (let j = 0; j <= R; j++, k++) {
        const a = (j / R) * Math.PI * 2, c = Math.cos(a), s = Math.sin(a);
        const nx = N.x * c + B.x * s, ny = N.y * c + B.y * s, nz = N.z * c + B.z * s;
        this.nrm[k * 3] = nx; this.nrm[k * 3 + 1] = ny; this.nrm[k * 3 + 2] = nz;
        this.pos[k * 3] = P[i].x + nx * radius; this.pos[k * 3 + 1] = P[i].y + ny * radius; this.pos[k * 3 + 2] = P[i].z + nz * radius;
        if (colorAt && this.col) { this.col[k * 3] = this._c.r; this.col[k * 3 + 1] = this._c.g; this.col[k * 3 + 2] = this._c.b; }
      }
    }
    const at = this.geometry.attributes;
    at.position.needsUpdate = true; at.normal.needsUpdate = true;
    if (at.color) at.color.needsUpdate = true;
    this.geometry.computeBoundingSphere();
  }

  hide() { this.mesh.visible = false; }
  dispose() { this.geometry.dispose(); }
}
