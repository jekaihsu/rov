// Accumulate one practice session from viewer state snapshots. Uses only fields
// the server already publishes (score, tether, events, photos, procedure).
// Photo "quality" is a provisional standoff proxy when an objective point exists;
// curriculum still treats image quality as instructor-reviewed evidence.

function number(value, fallback = 0) {
  return Number.isFinite(value) ? value : fallback;
}

function eventKey(event) {
  return [
    event?.t,
    event?.obstacle,
    event?.severity,
    event?.where,
    event?.vehicle_id,
  ].join('\0');
}

function objectiveOrderOk(score) {
  if (!score || !Array.isArray(score.objectives)) return true;
  let seenOpen = false;
  for (const objective of score.objectives) {
    if (objective?.done) {
      if (seenOpen) return false;
    } else {
      seenOpen = true;
    }
  }
  return true;
}

function photoStandoff(state) {
  const score = state?.score;
  const objectives = score?.objectives;
  if (!Array.isArray(objectives) || !state?.pos) return null;
  const current = objectives[score.current_index];
  const point = current?.point;
  if (!Array.isArray(point) || point.length < 3) return null;
  const dx = state.pos[0] - point[0];
  const dy = state.pos[1] - point[1];
  const dz = state.pos[2] - point[2];
  return Math.sqrt(dx * dx + dy * dy + dz * dz);
}

export function createSessionMetrics({lessonId = '', startedAt = null} = {}) {
  return {
    lessonId,
    startedAt: startedAt || new Date().toISOString(),
    elapsedS: 0,
    tetherContactEpisodes: 0,
    tetherContactNodesPeak: 0,
    _wasContacting: false,
    _seenEventKeys: new Set(),
    maxTensionN: 0,
    collisions: 0,
    severeCollisions: 0,
    photos: 0,
    photoStandoffsM: [],
    procedureInOrder: true,
    objectivesDone: 0,
    objectivesTotal: 0,
    finished: false,
    failed: '',
    score: null,
    fidelityPreset: 'real',
    fidelityLeftReal: false,
    assistedUsed: false,
    injections: [],
  };
}

function accumulateCollisions(metrics, events) {
  if (!Array.isArray(events) || !metrics._seenEventKeys) return;
  for (const event of events) {
    const key = eventKey(event);
    if (metrics._seenEventKeys.has(key)) continue;
    metrics._seenEventKeys.add(key);
    metrics.collisions += 1;
    if (event?.severity === 'severe') metrics.severeCollisions += 1;
  }
}

export function observeState(metrics, state) {
  if (!metrics || !state) return metrics;
  const score = state.score || {};
  metrics.elapsedS = number(score.elapsed, metrics.elapsedS);
  metrics.finished = !!score.finished;
  metrics.failed = score.failed || '';
  metrics.score = Number.isFinite(score.score) ? score.score : metrics.score;
  metrics.objectivesDone = Array.isArray(score.objectives)
    ? score.objectives.filter(function done(item) { return item?.done; }).length
    : metrics.objectivesDone;
  metrics.objectivesTotal = Array.isArray(score.objectives)
    ? score.objectives.length
    : metrics.objectivesTotal;
  if (!objectiveOrderOk(score)) metrics.procedureInOrder = false;

  const tether = state.tether || {};
  const contactNodes = number(tether.contact_nodes);
  const snagged = Array.isArray(tether.snagged_on) && tether.snagged_on.length > 0;
  const contacting = contactNodes > 0 || snagged;
  if (contacting && !metrics._wasContacting) metrics.tetherContactEpisodes += 1;
  metrics._wasContacting = contacting;
  metrics.tetherContactNodesPeak = Math.max(metrics.tetherContactNodesPeak, contactNodes);
  metrics.maxTensionN = Math.max(
    metrics.maxTensionN,
    number(tether.tension_max),
    number(tether.tension_rov),
  );

  accumulateCollisions(metrics, state.events);

  const photos = number(state.photos);
  if (photos > metrics.photos) {
    const standoff = photoStandoff(state);
    if (standoff != null) metrics.photoStandoffsM.push(Number(standoff.toFixed(2)));
  }
  metrics.photos = Math.max(metrics.photos, photos);

  const assist = state.assist;
  if (assist && number(assist.level) > 0) metrics.assistedUsed = true;
  return metrics;
}

export function recordFidelityChange(metrics, {preset, assisted} = {}) {
  if (!metrics) return metrics;
  if (preset) metrics.fidelityPreset = preset;
  if (preset && preset !== 'real') metrics.fidelityLeftReal = true;
  if (assisted) metrics.assistedUsed = true;
  return metrics;
}

export function recordInjection(metrics, injection) {
  if (!metrics || !injection) return metrics;
  metrics.injections.push({
    kind: injection.kind || '',
    at: injection.at || new Date().toISOString(),
    strength: injection.strength,
    duration: injection.duration,
  });
  return metrics;
}

export function photoQualitySummary(metrics) {
  const samples = metrics?.photoStandoffsM || [];
  if (!metrics?.photos) {
    return {photos: 0, meanStandoffM: null, label: 'none'};
  }
  if (!samples.length) {
    return {photos: metrics.photos, meanStandoffM: null, label: 'count_only'};
  }
  const mean = samples.reduce(function sum(a, b) { return a + b; }, 0) / samples.length;
  // Working distance is visibility-linked; without a measured quality score we only
  // report standoff as a provisional proxy for instructor review.
  let label = 'review';
  if (mean <= 2.5) label = 'close';
  else if (mean <= 5) label = 'nominal';
  else label = 'far';
  return {photos: metrics.photos, meanStandoffM: Number(mean.toFixed(2)), label};
}
