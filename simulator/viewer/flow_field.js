// Host-sampled water flow for visual cues (drifting particles, kelp sway).
//
// The host sends `state.flow_field` (see PROTOCOL.md "Ocean current model"): a small NED grid around
// the vehicle with velocities in integer cm/s, refreshed about twice a second. This module
// interpolates it trilinearly (clamped at the grid edges) and blends between refreshes so the
// cues move with the same turbulence, tide and structure wakes that push the vehicle. Without a
// grid (older hosts, replays) `ready` stays false and callers keep their own fallback.

const BLEND_MS = 500;

/** Decode one state.flow_field packet into a grid object, or null if it is malformed. */
export function decodeFlowGrid(packet) {
  if (!packet || !Array.isArray(packet.size) || !Array.isArray(packet.cm_s)) return null;
  const [nx, ny, nz] = packet.size;
  if (!(nx > 0 && ny > 0 && nz > 0) || packet.cm_s.length !== nx * ny * nz * 3) return null;
  const values = Float32Array.from(packet.cm_s, (v) => v / 100);
  return { seq: packet.seq, origin: packet.origin, step: packet.step, size: [nx, ny, nz], values };
}

function axisWeight(value, origin, step, count) {
  const f = count > 1 ? Math.min(Math.max((value - origin) / step, 0), count - 1) : 0;
  const i = Math.min(Math.floor(f), Math.max(count - 2, 0));
  return [i, count > 1 ? f - i : 0];
}

/** Trilinear NED velocity (m/s) at NED point (n, e, d); writes into `out` and returns it. */
export function sampleGrid(grid, n, e, d, out = [0, 0, 0]) {
  const [nx, ny, nz] = grid.size;
  const [i, fi] = axisWeight(n, grid.origin[0], grid.step[0], nx);
  const [j, fj] = axisWeight(e, grid.origin[1], grid.step[1], ny);
  const [k, fk] = axisWeight(d, grid.origin[2], grid.step[2], nz);
  out[0] = 0; out[1] = 0; out[2] = 0;
  for (let a = 0; a < 2; a++) {
    const wi = a ? fi : 1 - fi;
    if (!wi) continue;
    for (let b = 0; b < 2; b++) {
      const wj = b ? fj : 1 - fj;
      if (!wj) continue;
      for (let c = 0; c < 2; c++) {
        const wk = c ? fk : 1 - fk;
        if (!wk) continue;
        const base = (((i + a) * ny + (j + b)) * nz + (k + c)) * 3;
        const w = wi * wj * wk;
        out[0] += grid.values[base] * w;
        out[1] += grid.values[base + 1] * w;
        out[2] += grid.values[base + 2] * w;
      }
    }
  }
  return out;
}

/** Holds the latest two grids and blends between them over BLEND_MS. */
export class FlowField {
  constructor(blendMs = BLEND_MS) {
    this.blendMs = blendMs;
    this.previous = null;
    this.current = null;
    this.receivedAt = 0;
    this._a = [0, 0, 0];
    this._b = [0, 0, 0];
  }

  get ready() {
    return this.current !== null;
  }

  /** Accept `state.flow_field`; repeated packets with the same seq are ignored. */
  ingest(packet, nowMs) {
    if (!packet || (this.current && packet.seq === this.current.seq)) return;
    const grid = decodeFlowGrid(packet);
    if (!grid) return;
    this.previous = this.current;
    this.current = grid;
    this.receivedAt = nowMs;
  }

  /** Blended NED velocity at (n, e, d), or null without a grid. */
  sample(n, e, d, nowMs, out = [0, 0, 0]) {
    if (!this.current) return null;
    sampleGrid(this.current, n, e, d, out);
    const t = this.previous ? Math.min(Math.max((nowMs - this.receivedAt) / this.blendMs, 0), 1) : 1;
    if (t >= 1) return out;
    const old = sampleGrid(this.previous, n, e, d, this._a);
    for (let c = 0; c < 3; c++) out[c] = old[c] + (out[c] - old[c]) * t;
    return out;
  }

  /** Horizontal extent of the current grid: [n0, e0, stepN, stepE, countN, countE]. */
  horizontalBox() {
    if (!this.current) return null;
    const g = this.current;
    return [g.origin[0], g.origin[1], g.step[0], g.step[1], g.size[0], g.size[1]];
  }
}

export function createFlowField() {
  return new FlowField();
}
