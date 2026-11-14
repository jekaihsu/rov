// Distances to the simulator's obstacle shapes (NED metres) and the parametric ship hull, without three.js.
// Mirrors qysim/world.py: shipHullParams / halfBreadth must match ship_hull_params / _half_breadth there;
// tests/test_scene_consistency.py builds the viewer meshes and checks them against the Python shapes.

/** Derived proportions of a ship hull from its length, beam and draft (see world.ship_hull_params). */
export function shipHullParams(ob) {
  const draft = ob.draft;
  return {
    length: ob.length,
    beam: ob.beam,
    draft,
    top: Number.isFinite(ob.top) ? ob.top : -Math.max(2, 0.6 * draft),
    bilge: Math.min(0.12 * ob.beam, 0.3 * draft),
    bow: 0.32 * ob.length,
    stern: 0.30 * ob.length,
    rake: 0.04 * ob.length,
    aperture: 0.075 * ob.length,
    counter: 0.3 * draft,
    fair: 0.6,
  };
}

function clamp(value, low, high) {
  return Math.max(low, Math.min(high, value));
}

/** Local x of the stern: the transom above the counter, the propeller aperture below it. */
export function aftEnd(z, hp) {
  const t = clamp((z - hp.counter) / hp.fair, 0, 1);
  return -hp.length / 2 + hp.aperture * t * t * (3 - 2 * t);
}

/** Half breadth at local (x forward, z down); also the stem position. */
export function halfBreadth(x, z, hp) {
  const half = hp.length / 2;
  const fwdMid = half - hp.bow;
  const aftMid = -half + hp.stern;
  const fwdEnd = half - hp.rake * clamp(z / hp.draft, 0, 1);
  const uBow = clamp((x - fwdMid) / Math.max(fwdEnd - fwdMid, 1e-6), 0, 1);
  const uAft = clamp((aftMid - x) / Math.max(aftMid - aftEnd(z, hp), 1e-6), 0, 1);
  const width = (1 - uBow * uBow) * (1 - uAft * uAft);
  const rb = hp.bilge;
  const s = clamp(z - (hp.draft - rb), 0, rb);
  const bilge = rb - Math.sqrt(Math.max(rb * rb - s * s, 0));
  return {hb: width * hp.beam / 2 - bilge, fwdEnd};
}

function hullDistance(x, y, z, hp) {
  const e = 0.05;
  const {hb, fwdEnd} = halfBreadth(x, z, hp);
  const hx = (halfBreadth(x + e, z, hp).hb - halfBreadth(x - e, z, hp).hb) / (2 * e);
  const hz = (halfBreadth(x, z + e, hp).hb - halfBreadth(x, z - e, hp).hb) / (2 * e);
  const slope = Math.min(Math.sqrt(1 + hx * hx + hz * hz), 6);
  return Math.max((Math.abs(y) - hb) / slope, z - hp.draft, hp.top - z, x - fwdEnd, aftEnd(z, hp) - x);
}

/** World NED point -> hull local (x along the bow heading, y starboard, z down). */
export function shipHullLocal(p, ob) {
  const a = ob.yaw_deg * Math.PI / 180;
  const n = p[0] - ob.center[0];
  const e = p[1] - ob.center[1];
  return [n * Math.cos(a) + e * Math.sin(a), -n * Math.sin(a) + e * Math.cos(a), p[2] - ob.center[2]];
}

export function shipHullDistance(p, ob) {
  const hp = shipHullParams(ob);
  const [x, y, z] = shipHullLocal(p, ob);
  return hullDistance(x, y, z, hp);
}

/** Approximate distance from a NED point to an obstacle's surface (1e3 when a wall does not apply). */
export function obstacleDistance(p, ob) {
  if (ob.type === 'cylinder') {
    const a = ob.p0;
    const ab = [ob.p1[0] - a[0], ob.p1[1] - a[1], ob.p1[2] - a[2]];
    const ap = [p[0] - a[0], p[1] - a[1], p[2] - a[2]];
    const length = ab[0] ** 2 + ab[1] ** 2 + ab[2] ** 2;
    const t = clamp((ap[0] * ab[0] + ap[1] * ab[1] + ap[2] * ab[2]) / (length || 1), 0, 1);
    return Math.hypot(ap[0] - ab[0] * t, ap[1] - ab[1] * t, ap[2] - ab[2] * t) - ob.radius;
  }
  if (ob.type === 'box') {
    const y = ob.yaw_deg * Math.PI / 180;
    const r = [p[0] - ob.center[0], p[1] - ob.center[1], p[2] - ob.center[2]];
    const l = [r[0] * Math.cos(y) + r[1] * Math.sin(y), -r[0] * Math.sin(y) + r[1] * Math.cos(y), r[2]];
    const q = l.map((v, i) => Math.max(Math.abs(v) - ob.half[i], 0));
    return Math.hypot(...q);
  }
  if (ob.type === 'wall') {
    const a = ob.normal_deg * Math.PI / 180;
    const n = [Math.cos(a), Math.sin(a)];
    const r = [p[0] - ob.point[0], p[1] - ob.point[1]];
    if (Math.abs(-r[0] * n[1] + r[1] * n[0]) > ob.width / 2 || p[2] < ob.top) return 1e3;
    return Math.abs(r[0] * n[0] + r[1] * n[1]);
  }
  if (ob.type === 'ship_hull') return shipHullDistance(p, ob);
  return 1e3;
}
