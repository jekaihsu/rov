// In-dive deliverable tracker of a YX work order: turns the state stream into the contract's checklist —
// procedure steps, points reached, station keeping, photos with the target in frame, laser-scaler measurements,
// contact probes (CP / UT), objects lifted with the arm and manual confirmations (LOTO) — plus the contacts,
// tether overloads, tether wraps and safety violations the score deducts. Pure (no DOM): the dive module feeds
// it states and photo events. Optional Chapter-1 fields (truth_cm, growth, rating, compare, gate) are stored on
// the item for overlays and scoring; LOTO unlock gating lives in loto_gate.js.

import { comparePose } from './photo_compare.js';

import { localize } from '../i18n/index.js';
const STRINGS = localize('career.deliverables', {
  offboard: '照片未列入交付：請用機載鏡頭拍攝。',
  tooFar: '照片未列入交付：離目標太遠。',
  tooClose: '照片未列入交付：離目標太近，拍不到全貌。',
  murky: '照片未列入交付：能見度不足，目標看不清楚。',
  offFrame: '照片未列入交付：目標不在畫面中。',
  noTarget: '照片已存檔，但附近沒有待拍的交付項目。',
  accepted: '照片列入交付：{label}',
  saved: '照片已存檔。',
  contact: '碰撞 {name}',
  overload: '纜線張力過載',
  wrap: '纜線繞上 {name}',
  needs: '需要裝備：{item}',
  after: '先完成：{label}',
  last: '完成其他必要項目後回收',
  rated: '附著評級 FR {n}',
  angleDrift: '拍攝角度偏離參考',
  measureSoft: '軟附著 {cm} cm',
  measureHard: '硬附著 {cm} cm',
  measurePlain: '{cm} cm',
});
// Score points per event: contacts follow qysim/scenarios.py PENALTY; the rest are game values.
export const PENALTY_POINTS = { touch: 5, hard: 15, severe: 30, overload: 10, wrap: 10 };
export const ANGLE_DRIFT_POINTS = 5;
const FACING_DEG = 35;
const MEASURE_FACING_DEG = 20;
const ELEVATION_DEG = 60;
const STILL_SPEED = 0.3;
const MEASURE_SPEED = 0.2;
const PROBE_SPEED = 0.15;
const PROBE_CONTACT_M = 1.0;
const WRAP_TURNS = 1;
const DEFAULT_HOLD_S = 3;

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

function vector(value) {
  return Array.isArray(value) && value.length >= 3 ? value.map(Number) : null;
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function speed(state) {
  const vel = vector(state.vel);
  return vel ? Math.hypot(vel[0], vel[1], vel[2]) : 0;
}

function wrapDegrees(value) {
  return ((value + 540) % 360) - 180;
}

// Horizontal angle between the vehicle heading and the target, and the target's elevation, in degrees.
export function aim(state, point) {
  const pos = vector(state.pos);
  const heading = Number(state.euler?.[2]) || 0;
  const dn = point[0] - pos[0];
  const de = point[1] - pos[1];
  const dd = point[2] - pos[2];
  const bearing = Math.atan2(de, dn) * 180 / Math.PI;
  const elevation = Math.atan2(Math.abs(dd), Math.hypot(dn, de)) * 180 / Math.PI;
  return { yaw: Math.abs(wrapDegrees(bearing - heading)), elevation };
}

// Same limit as observation_camera.js: farthest distance a subject still keeps enough contrast.
export function visibleRange(visibility) {
  return 0.3 + 0.8 * Math.max(0, visibility * 1.35 - 0.3);
}

/** Whether a photo taken now would show the deliverable's target: {ok, reason, yaw}. */
export function photoCheck(item, state, { view = 'onboard', visibility = 12 } = {}) {
  if (view !== 'onboard') return { ok: false, reason: 'offboard' };
  const pos = vector(state.pos);
  if (!pos) return { ok: false, reason: 'offFrame' };
  const gap = distance(pos, item.point);
  const [near, far] = item.standoff || [0.5, 5];
  if (gap > far) return { ok: false, reason: 'tooFar' };
  if (gap > visibleRange(visibility)) return { ok: false, reason: 'murky' };
  if (gap < near) return { ok: false, reason: 'tooClose' };
  const angle = aim(state, item.point);
  if (angle.yaw > FACING_DEG && Math.hypot(pos[0] - item.point[0], pos[1] - item.point[1]) > 0.5) {
    return { ok: false, reason: 'offFrame', yaw: angle.yaw };
  }
  if (angle.elevation > ELEVATION_DEG) return { ok: false, reason: 'offFrame', yaw: angle.yaw };
  return { ok: true, reason: '', yaw: angle.yaw };
}

function readPath(state, path) {
  let value = state;
  for (const part of String(path).split('.')) {
    if (value == null) return undefined;
    value = Array.isArray(value) ? value[Number(part)] : value[part];
  }
  return value;
}

/** The campaign condition format ({path, op, value}) against a state. */
export function conditionMatches(condition, state) {
  const value = readPath(state, condition.path);
  if (value === undefined) return false;
  if (condition.op === 'eq') return value === condition.value;
  if (condition.op === 'gt') return value > condition.value;
  return value < condition.value;
}

function formatMeasureReading(result, def) {
  const cm = Number(result?.thickness_cm);
  const shown = Number.isFinite(cm) ? (Math.round(cm * 10) / 10).toFixed(1) : '';
  if (!shown) return def.reading || '';
  if (result.growth === 'soft') return format(STRINGS.measureSoft, { cm: shown });
  if (result.growth === 'hard') return format(STRINGS.measureHard, { cm: shown });
  return format(STRINGS.measurePlain, { cm: shown });
}

/**
 * contract: a contracts.json entry; owned: item ids of the career save; itemLabel(id): player name of an item.
 * Returns {observe, photo, confirm, rate, setMeasureResult, snapshot}.
 */
export function createTracker(contract, { owned = [], itemLabel = String } = {}) {
  const items = (contract.deliverables || []).map(function track(def) {
    return {
      def,
      done: false,
      progress: 0,
      reading: '',
      pendingRating: false,
      rated: null,
      truthRating: def.rating == null ? null : def.rating,
      growthPick: '',
      compareOk: null,
      thickness_cm: null,
    };
  });
  const byId = new Map(items.map(function entry(item) {
    return [item.def.id, item];
  }));
  const penalties = [];
  const lifted = new Map();
  const seenEvents = new Set();
  const violated = new Set();
  const wrapped = new Set();
  const measureResults = new Map();
  let primed = false;
  let warned = false;
  let broken = false;

  function required(item) {
    return item.def.required !== false;
  }
  function missingEquipment(item) {
    return item.def.equipment && !owned.includes(item.def.equipment) ? item.def.equipment : '';
  }
  function othersDone(item) {
    return items.every(function done(other) {
      return other === item || !required(other) || other.def.kind === 'surface' || other.done;
    });
  }
  function blockedBy(item) {
    if (item.def.after && !byId.get(item.def.after)?.done) return byId.get(item.def.after);
    return null;
  }
  function workable(item) {
    if (item.done || item.pendingRating || missingEquipment(item) || blockedBy(item)) return false;
    return item.def.kind !== 'surface' || othersDone(item);
  }
  function hold(item, ok, dt) {
    const seconds = item.def.hold_s || DEFAULT_HOLD_S;
    if (ok) item.progress = Math.min(1, item.progress + dt / seconds);
    else item.progress = Math.max(0, item.progress - dt / seconds * 0.5);
    if (item.progress >= 1) finish(item);
  }
  function finish(item, extra = {}) {
    item.progress = 1;
    if (item.def.kind === 'photo' && item.def.rating != null && extra.rated == null) {
      // Photo is filed; the checklist row waits until the pilot picks FR0–FR4.
      item.done = false;
      item.pendingRating = true;
      item.truthRating = item.def.rating;
      item.reading = '';
      item.photographed = true;
      if (extra.compare) {
        item.compareOk = !!extra.compare.ok;
        if (!extra.compare.ok) {
          penalties.push({
            kind: 'quality',
            label: STRINGS.angleDrift,
            points: ANGLE_DRIFT_POINTS,
          });
        }
      }
      return;
    }
    item.done = true;
    if (item.def.kind === 'measure' && measureResults.has(item.def.id)) {
      const result = measureResults.get(item.def.id);
      item.reading = formatMeasureReading(result, item.def);
      item.growthPick = result.growth || '';
      item.thickness_cm = Number(result.thickness_cm);
    } else {
      item.reading = item.def.reading || '';
    }
    if (extra.compare) {
      item.compareOk = !!extra.compare.ok;
      if (!extra.compare.ok) {
        penalties.push({
          kind: 'quality',
          label: STRINGS.angleDrift,
          points: ANGLE_DRIFT_POINTS,
        });
      }
    }
  }
  function setMeasureResult(id, result) {
    const item = byId.get(id);
    if (!item || item.def.kind !== 'measure') return false;
    measureResults.set(id, {
      thickness_cm: Number(result?.thickness_cm),
      growth: result?.growth === 'soft' || result?.growth === 'hard' ? result.growth : '',
    });
    if (item.done) {
      const stored = measureResults.get(id);
      item.reading = formatMeasureReading(stored, item.def);
      item.growthPick = stored.growth || '';
      item.thickness_cm = Number(stored.thickness_cm);
    }
    return true;
  }
  function rate(id, value) {
    const item = byId.get(id);
    if (!item || item.def.kind !== 'photo' || item.def.rating == null) return false;
    if (!item.photographed && !item.pendingRating && !item.done) return false;
    const n = Math.max(0, Math.min(4, Math.round(Number(value))));
    if (!Number.isFinite(n)) return false;
    item.rated = n;
    item.truthRating = item.def.rating;
    item.pendingRating = false;
    item.reading = format(STRINGS.rated, { n });
    item.done = true;
    item.progress = 1;
    if (item.rated !== item.truthRating) {
      penalties.push({
        kind: 'quality',
        label: format(STRINGS.rated, { n: item.truthRating }),
        points: Math.min(15, Math.abs(item.rated - item.truthRating) * 5),
      });
    }
    return true;
  }
  function within(state, item, radius) {
    const pos = vector(state.pos);
    return !!pos && distance(pos, item.def.point) <= radius;
  }
  function update(item, state, dt) {
    const def = item.def;
    if (def.kind === 'state') {
      if (conditionMatches(def.condition, state)) finish(item);
    } else if (def.kind === 'checkpoint' || def.kind === 'surface') {
      if (within(state, item, def.radius || 1.5)) finish(item);
    } else if (def.kind === 'station_keep') {
      hold(item, within(state, item, def.radius || 1) && speed(state) < STILL_SPEED, dt);
    } else if (def.kind === 'inspect') {
      const facing = aim(state, def.face || def.point).yaw <= FACING_DEG;
      hold(item, within(state, item, def.radius || 1.5) && facing, dt);
    } else if (def.kind === 'measure') {
      const [near, far] = def.standoff || [0.4, 1.5];
      const pos = vector(state.pos);
      const gap = pos ? distance(pos, def.point) : Infinity;
      const facing = aim(state, def.point).yaw <= MEASURE_FACING_DEG;
      hold(item, gap >= near && gap <= far && facing && speed(state) < MEASURE_SPEED, dt);
    } else if (def.kind === 'probe') {
      hold(item, within(state, item, def.radius || PROBE_CONTACT_M) && speed(state) < PROBE_SPEED, dt);
    } else if (def.kind === 'lift') {
      trackLift(item, state);
    }
  }
  // An object of def.object_kind held by the arm (state.operations) and raised above def.below (depth, m)
  // counts once per object; def.count objects complete the item.
  function trackLift(item, state) {
    const held = state.operations?.arm?.held;
    const object = (state.operations?.objects || []).find(function byId(entry) {
      return entry.id === held;
    });
    const set = lifted.get(item) || new Set();
    lifted.set(item, set);
    const raised = object && object.kind === item.def.object_kind && Number(object.pos?.[2]) < item.def.below;
    if (raised) set.add(object.id);
    const count = item.def.count || 1;
    item.progress = Math.min(1, set.size / count);
    if (set.size >= count) finish(item);
  }
  function trackEvents(state) {
    for (const event of state.events || []) {
      const key = `${event.t}:${event.obstacle}:${event.severity}`;
      if (seenEvents.has(key)) continue;
      seenEvents.add(key);
      if (!primed) continue;
      const points = PENALTY_POINTS[event.severity] || PENALTY_POINTS.touch;
      penalties.push({ kind: 'contact', severity: event.severity, label: format(STRINGS.contact,
        { name: event.obstacle || '' }), points });
    }
    const warn = !!state.tether?.warn;
    if (primed && warn && !warned) penalties.push({ kind: 'overload', label: STRINGS.overload, points:
      PENALTY_POINTS.overload });
    warned = warn;
    if (state.tether?.broken) broken = true;
    for (const [name, turns] of Object.entries(state.tether?.wraps || {})) {
      if (Math.abs(Number(turns)) < WRAP_TURNS || wrapped.has(name)) continue;
      wrapped.add(name);
      penalties.push({ kind: 'wrap', label: format(STRINGS.wrap, { name }), points: PENALTY_POINTS.wrap });
    }
  }
  function trackHazards(state) {
    for (const hazard of contract.hazards || []) {
      if (violated.has(hazard.id) || byId.get(hazard.until)?.done) continue;
      const pos = vector(state.pos);
      if (!pos || distance(pos, hazard.point) > hazard.radius) continue;
      violated.add(hazard.id);
      penalties.push({ kind: 'safety', label: hazard.label, points: hazard.points });
    }
  }
  function observe(state, dt = 0) {
    if (!state) return;
    trackEvents(state);
    primed = true;
    trackHazards(state);
    for (const item of items) {
      if (workable(item)) update(item, state, Math.max(0, dt));
    }
  }
  function photo(state, options = {}) {
    const candidates = items.filter(function waiting(item) {
      return item.def.kind === 'photo' && workable(item);
    });
    if (!candidates.length) return { accepted: null, reason: 'noTarget', message: STRINGS.noTarget };
    const checks = candidates.map(function check(item) {
      return { item, result: photoCheck(item.def, state, options) };
    });
    const hit = checks.filter(function ok(entry) {
      return entry.result.ok;
    }).sort(function centred(a, b) {
      return a.result.yaw - b.result.yaw;
    })[0];
    if (hit) {
      const extra = {};
      if (hit.item.def.compare) extra.compare = comparePose(hit.item.def, state);
      finish(hit.item, extra);
      const message = format(STRINGS.accepted, { label: hit.item.def.label });
      return {
        accepted: hit.item.def.id,
        reason: '',
        message,
        pendingRating: !!hit.item.pendingRating,
        compareOk: hit.item.compareOk,
      };
    }
    // Report the reason for the nearest waiting target.
    const pos = vector(state.pos);
    const nearest = checks.sort(function closest(a, b) {
      return (pos ? distance(pos, a.item.def.point) - distance(pos, b.item.def.point) : 0);
    })[0];
    const reason = nearest.result.reason;
    return { accepted: null, reason, message: STRINGS[reason] || STRINGS.saved };
  }
  function confirm(id) {
    const item = byId.get(id);
    if (!item || item.def.kind !== 'confirm' || !workable(item)) return false;
    finish(item);
    return true;
  }
  function note(item) {
    const equipment = missingEquipment(item);
    if (equipment) return format(STRINGS.needs, { item: itemLabel(equipment) });
    const before = blockedBy(item);
    if (before && !item.done) return format(STRINGS.after, { label: before.def.label });
    if (item.def.kind === 'surface' && !item.done && !othersDone(item)) return STRINGS.last;
    return '';
  }
  function snapshot() {
    const list = items.map(function view(item) {
      return {
        id: item.def.id,
        kind: item.def.kind,
        label: item.def.label,
        point: item.def.point || null,
        required: required(item),
        done: item.done,
        progress: item.progress,
        reading: item.reading,
        note: note(item),
        confirmable: item.def.kind === 'confirm' && workable(item),
        rating: item.rated,
        truthRating: item.truthRating,
        pendingRating: !!item.pendingRating,
        growthPick: item.growthPick || '',
        compareOk: item.compareOk,
        truth_cm: item.def.truth_cm == null ? null : item.def.truth_cm,
        growth: item.def.growth || '',
        gate: item.def.gate || '',
      };
    });
    const mandatory = list.filter(function isRequired(item) {
      return item.required;
    });
    function delivered(item) {
      return item.done && !item.pendingRating;
    }
    return {
      items: list,
      done: list.filter(delivered).length,
      total: list.length,
      requiredDone: mandatory.filter(delivered).length,
      requiredTotal: mandatory.length,
      complete: mandatory.every(delivered),
      penalties: penalties.slice(),
      tetherBroken: broken,
    };
  }
  return { observe, photo, confirm, rate, setMeasureResult, snapshot };
}
