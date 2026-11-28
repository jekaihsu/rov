// Compact full-dive evidence collected before replay frame decimation. Times are simulation seconds.
import {approach, rules} from './rules.js';

export const channels = ['depth', 'heading', 'speed', 'tension', 'length'];

function clearance(pos, pile) {
  const axis = pile.p1.map((v, i) => v - pile.p0[i]);
  const offset = pos.map((v, i) => v - pile.p0[i]);
  const projection = offset.reduce((sum, v, i) => sum + v * axis[i], 0);
  const u = Math.max(0, Math.min(1, projection / (Math.hypot(...axis) ** 2 || 1)));
  return Math.hypot(...offset.map((v, i) => v - u * axis[i])) - pile.radius;
}

export function createDiveRecord(world) {
  const piles = (world?.obstacles || []).filter(p => p.kind === approach.kind && p.p0 && p.p1);
  const samples = [];
  const events = [];
  const metrics = {approach: null, loaded: null, recoveries: 0, collisions: null};
  const seen = new Set();
  let prev = {};
  let peak = null;
  let loaded = 0;
  let descended = false;
  let shallowest = Infinity;
  let cable = [];
  let lastSample;

  function mark(kind, t, detail = '') {
    const key = JSON.stringify([kind, t, detail]);
    if (seen.has(key)) return;
    seen.add(key);
    events.push({kind, t, detail});
  }

  function observe(f, measurements = []) {
    const {t, pos, tether = {}, tether_ops: ops = {}} = f;
    if (!Number.isFinite(t)) return;
    const depth = pos?.[2];
    const speed = f.vel?.length === 3 ? Math.hypot(...f.vel) : null;
    const tension = tether.tension_max ?? tether.tension_rov;
    const row = {t, pos, depth, speed, heading: f.euler?.[2], tension, length: tether.length};
    if (!samples.length || t - samples.at(-1).t >= 0.5) samples.push(row);
    lastSample = row;
    if (tether.nodes?.length) cable = tether.nodes;
    if (Number.isFinite(tension) && (!peak || peak.value < tension)) peak = {t, value: tension, row};
    if (f.locked === false && prev.locked !== false) mark('unlock', t);
    if (Number.isFinite(depth)) shallowest = Math.min(shallowest, depth);
    if (!descended && (f.procedure?.phase === 'diving' || depth > shallowest + 0.1)) {
      descended = true;
      mark('dive', t);
    }
    const beat = f.campaign?.node?.id;
    if (beat && beat !== prev.beat) {
      mark('beat', t, beat);
      if (beat === 'abort') mark('abort', t, beat);
    }
    if (f.photos > (prev.photos ?? 0)) mark('photo', t, String(f.photos));
    for (const item of measurements) {
      if (item.kind === 'measure' && item.done && !seen.has('measurement/' + item.id)) {
        seen.add('measurement/' + item.id);
        mark('measure', t, item.reading || item.label || item.id);
      }
    }
    if (Array.isArray(f.events)) metrics.collisions ??= 0;
    for (const hit of f.events || []) {
      const count = events.length;
      mark('collision', hit.t ?? t, [hit.obstacle, hit.where, hit.severity].filter(Boolean).join(' · '));
      metrics.collisions += events.length - count;
    }
    const contact = tether.contact_nodes > 0 || !!tether.snagged_on?.length;
    if (contact && !prev.contact) mark('contact', t, String(tether.contact_nodes));
    const snag = ops.snag?.name || tether.snags?.[0]?.name || Object.keys(tether.wraps || {})[0];
    if (snag && snag !== prev.snag) mark('snag', t, snag);
    if (ops.snag?.returned && !prev.returned) mark('returned', t, snag);
    if (prev.snag && !snag) {
      mark(tether.broken ? 'broken' : 'released', t, prev.snag);
      if (!tether.broken && ops.result?.correct) metrics.recoveries++;
    }
    // Count observed intervals with both ends snagged and over working load.
    const pulling = !!(snag && tether.warn);
    if (pulling && prev.pulling && snag === prev.snag) loaded += Math.max(0, t - prev.t);
    else loaded = 0;
    if (loaded > (metrics.loaded || 0)) metrics.loaded = loaded;
    if (speed != null && pos && piles.some(p => clearance(pos, p) <= approach.clearanceM)) {
      metrics.approach = Math.max(metrics.approach ?? 0, speed);
    }
    if (f.score?.failed && !prev.failed) mark('abort', t, f.score.failed);
    prev = {t, locked: f.locked, photos: f.photos, beat, contact,
      snag, pulling, returned: ops.snag?.returned, failed: f.score?.failed};
  }

  function snapshot() {
    const timeline = [...events];
    if (peak) timeline.push({kind: 'peak', t: peak.t, detail: peak.value.toFixed(1) + ' N'});
    const rows = lastSample && samples.at(-1) !== lastSample ? [...samples, lastSample] : [...samples];
    if (peak && !rows.some(r => r.t === peak.t)) {
      rows.push(peak.row);
      rows.sort((a, b) => a.t - b.t);
    }
    return {samples: rows, events: timeline.sort((a, b) => a.t - b.t), metrics: {...metrics}, cable};
  }
  return {observe, mark, snapshot};
}

export function findings(metrics) {
  return rules.filter(rule => Number.isFinite(metrics[rule.metric]) &&
    (rule.above == null || metrics[rule.metric] > rule.above) &&
    (rule.atMost == null || metrics[rule.metric] <= rule.atMost));
}
