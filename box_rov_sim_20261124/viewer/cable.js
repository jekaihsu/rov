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
    this._cos=Float64Array.from({length:radial+1},(_,j)=>Math.cos(j/radial*Math.PI*2));
    this._sin=Float64Array.from({length:radial+1},(_,j)=>Math.sin(j/radial*Math.PI*2));
    this._lastPoints=new Float64Array(0);this._lastRadius=-1;this._lastLinear=false;
    this._ringColors=new Float32Array((segments+1)*3);
  }

  update(points, colorAt = null, {linear=false}={}) {
    if (!points || points.length < 2) { this.mesh.visible = false; return; }
    this.mesh.visible = true;
    const { S, R, radius, _p: P, _t: T, _n: N, _b: B } = this;
    let changed=this._lastPoints.length!==points.length*3||radius!==this._lastRadius||linear!==this._lastLinear;
    if(this._lastPoints.length!==points.length*3)this._lastPoints=new Float64Array(points.length*3);
    for(let i=0;i<points.length;i++){
      const p=points[i],at=i*3,old=this._lastPoints;
      if(old[at]!==p.x||old[at+1]!==p.y||old[at+2]!==p.z)changed=true;
      old[at]=p.x;old[at+1]=p.y;old[at+2]=p.z;
    }
    let colorsChanged=false;
    if(colorAt&&this.col)for(let i=0;i<=S;i++){
      colorAt(i/S,this._c);
      const r=Math.fround(this._c.r),g=Math.fround(this._c.g),b=Math.fround(this._c.b),at=i*3,old=this._ringColors;
      if(old[at]!==r||old[at+1]!==g||old[at+2]!==b)colorsChanged=true;
      old[at]=r;old[at+1]=g;old[at+2]=b;
    }
    if(!changed&&!colorsChanged)return;
    this._lastRadius=radius;this._lastLinear=linear;
    this.curve.points = points;
    // At contact, stay on the physical solver's polyline: a display spline
    // must not bow through a pile merely to make the cable look smoother.
    if(changed)for(let i=0;i<=S;i++){
      if(linear){const u=i/S*(points.length-1),j=Math.min(points.length-2,Math.floor(u));P[i].lerpVectors(points[j],points[j+1],u-j);}
      else this.curve.getPoint(i/S,P[i]);
    }
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
      if (N.lengthSq() < 1e-12) {N.set(Math.abs(T.x)<.8?1:0,Math.abs(T.x)<.8?0:1,0);N.addScaledVector(T,-N.dot(T));}
      N.normalize();
      B.crossVectors(T, N);
      for (let j = 0; j <= R; j++, k++) {
        const c=this._cos[j],s=this._sin[j];
        const nx = N.x * c + B.x * s, ny = N.y * c + B.y * s, nz = N.z * c + B.z * s;
        this.nrm[k * 3] = nx; this.nrm[k * 3 + 1] = ny; this.nrm[k * 3 + 2] = nz;
        this.pos[k * 3] = P[i].x + nx * radius; this.pos[k * 3 + 1] = P[i].y + ny * radius; this.pos[k * 3 + 2] = P[i].z + nz * radius;
        if (colorAt && this.col) { this.col[k * 3] = this._ringColors[i*3]; this.col[k * 3 + 1] = this._ringColors[i*3+1]; this.col[k * 3 + 2] = this._ringColors[i*3+2]; }
      }
    }
    const at = this.geometry.attributes;
    at.position.needsUpdate = true; at.normal.needsUpdate = true;
    if (at.color) at.color.needsUpdate = true;
    if(changed)this.geometry.boundingSphere=null;
    // The cable mesh intentionally disables frustum culling; no per-frame
    // vertex scan is needed. A photo raycast can rebuild this lazily.
  }

  hide() { this.mesh.visible = false; }
  dispose() { this.geometry.dispose(); }
}
