// Read-only forward proximity estimate against known world geometry in NED metres.
function distance(p, ob) {
  if (ob.type === 'cylinder') {
    const ab = ob.p1.map((v, i) => v - ob.p0[i]);
    const ap = p.map((v, i) => v - ob.p0[i]);
    const length = ab.reduce((sum, v) => sum + v * v, 0);
    const t = Math.max(0, Math.min(1, ap.reduce((sum, v, i) => sum + v * ab[i], 0) / (length || 1)));
    return Math.hypot(...ap.map((v, i) => v - ab[i] * t)) - ob.radius;
  }
  if (ob.type === 'box') {
    const a = (ob.yaw_deg || 0) * Math.PI / 180;
    const r = p.map((v, i) => v - ob.center[i]);
    const local = [r[0] * Math.cos(a) + r[1] * Math.sin(a), -r[0] * Math.sin(a) + r[1] * Math.cos(a), r[2]];
    return Math.hypot(...local.map((v, i) => Math.max(0, Math.abs(v) - ob.half[i])));
  }
  if (ob.type === 'wall') {
    const a = ob.normal_deg * Math.PI / 180;
    const n = p[0] - ob.point[0];
    const e = p[1] - ob.point[1];
    if (Math.abs(-n * Math.sin(a) + e * Math.cos(a)) > ob.width / 2 || p[2] < ob.top) return Infinity;
    return Math.abs(n * Math.cos(a) + e * Math.sin(a));
  }
  return Infinity;
}
export function forwardRange(s, w) {
  const yaw = (s.euler?.[2] || 0) * Math.PI / 180;
  const pitch = (s.euler?.[1] || 0) * Math.PI / 180;
  const forward = [Math.cos(yaw) * Math.cos(pitch), Math.sin(yaw) * Math.cos(pitch), -Math.sin(pitch)];
  for (let r = 0; r <= 5; r += .1) {
    const point = s.pos.map((v, i) => v + forward[i] * r);
    if ((w?.obstacles || []).some(ob => distance(point, ob) < .15)) return r;
  }
  return null;
}
