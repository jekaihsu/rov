// Chapter 1 beat directors (docs/story/chapters/chapter1.md): pure timing and radio queue, no DOM.
// Shared skeleton per mission: black → establish → handover → work → [turn] → report → card → done.
// Every player beat has a hard limit and an idle nudge; beatDecision drives routine cuts.
import {beatDecision, idleReminder} from './beat_director.js';

export const CHAPTER1_MISSIONS = Object.freeze([
  'c1_pier_level2',
  'c1_hull_fouling',
  'c1_dropped_object',
  'c1_signoff_exam',
]);

export const TIMING = Object.freeze({
  black: 4.5,
  establish: 7.5,
  fadeIn: 2.2,
  handover: 1.6,
  workNudge: 20,
  workLimit: 120,
  turnHold: 4.5,
  report: 5.5,
  fade: 1.8,
  stickInput: 0.15,
  nearRange: 3.5,
  tensionWarn: 40,
});

const PREFIX = Object.freeze({
  c1_pier_level2: 'pier',
  c1_hull_fouling: 'hull',
  c1_dropped_object: 'drop',
  c1_signoff_exam: 'sign',
});

const TURN_FLAGS = Object.freeze({
  c1_pier_level2: [
    {flag: 'nearPile', beat: 'turnNear', line: 'near'},
    {flag: 'measured', beat: 'turnMeasured', line: 'measured'},
    {flag: 'contact', beat: 'turnContact', line: 'contact'},
    {flag: 'murky', beat: 'turnMurky', line: 'murky'},
  ],
  c1_hull_fouling: [
    {flag: 'lotoDone', beat: 'turnLoto', line: 'loto'},
    {flag: 'nearProp', beat: 'turnProp', line: 'nearProp'},
    {flag: 'suction', beat: 'turnSuction', line: 'suction'},
    {flag: 'rated', beat: 'turnRated', line: 'rated'},
  ],
  c1_dropped_object: [
    {flag: 'echoesSeen', beat: 'turnEchoes', line: 'echoes'},
    {flag: 'atDecoy', beat: 'turnDecoy', line: 'decoy'},
    {flag: 'atTarget', beat: 'turnTarget', line: 'target'},
    {flag: 'photographed', beat: 'turnPhoto', line: 'photo'},
  ],
  c1_signoff_exam: [
    {flag: 'photosDone', beat: 'turnPhotos', line: 'photos'},
    {flag: 'snagged', beat: 'turnSnag', line: 'snag'},
    {flag: 'tension', beat: 'turnTension', line: 'tension'},
    {flag: 'aborted', beat: 'turnAbort', line: 'abort'},
  ],
});

function lineKey(prefix, suffix) {
  return `${prefix}_${suffix}`;
}

function sharedBeats(prefix) {
  return {
    black: {limit: TIMING.black, next: 'establish', cinematic: true, radio: lineKey(prefix, 'open')},
    establish: {limit: TIMING.establish, next: 'handover', cinematic: true, radio: lineKey(prefix, 'establish')},
    handover: {limit: TIMING.handover, next: 'work', hud: ['depth', 'heading'], radio: lineKey(prefix, 'task')},
    work: {hint: 'move'},
    report: {limit: TIMING.report, next: 'fade', hud: ['photo']},
    fade: {limit: TIMING.fade, next: 'card', cinematic: true},
    card: {},
    done: {},
  };
}

function turnBeats(missionId, prefix) {
  const turns = {};
  for (const entry of TURN_FLAGS[missionId] || []) {
    const abortTurn = entry.flag === 'aborted';
    turns[entry.beat] = {
      limit: TIMING.turnHold,
      next: abortTurn ? 'report' : 'work',
      radio: lineKey(prefix, entry.line),
      hud: entry.flag === 'snagged' || entry.flag === 'tension' ? ['tether'] : undefined,
      hint: entry.flag === 'snagged' || entry.flag === 'tension' ? 'reverse' : null,
    };
  }
  return turns;
}

function distance2(a, b) {
  if (!a || !b) return Infinity;
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function nearestRange(pos, points) {
  if (!pos || !points?.length) return Infinity;
  return Math.min(...points.map(function range(point) {
    return distance2(pos, point);
  }));
}

/** Enrich boolean telemetry from spots when callers only pass position. */
export function enrichTelemetry(missionId, telemetry = {}, spots = {}) {
  const t = {...telemetry};
  const pos = t.pos;
  if (missionId === 'c1_pier_level2') {
    if (t.nearPile == null) t.nearPile = nearestRange(pos, spots.piles) < TIMING.nearRange;
  }
  if (missionId === 'c1_hull_fouling') {
    if (t.nearProp == null) t.nearProp = distance2(pos, spots.prop) < TIMING.nearRange;
    if (t.suction == null) t.suction = !!t.flow || (Number(t.current) || 0) > 0.35;
  }
  if (missionId === 'c1_dropped_object') {
    if (t.atDecoy == null) t.atDecoy = distance2(pos, spots.decoy) < TIMING.nearRange;
    if (t.atTarget == null) t.atTarget = distance2(pos, spots.target) < TIMING.nearRange;
  }
  if (missionId === 'c1_signoff_exam') {
    if (t.tension == null) t.tension = (Number(t.tensionN) || 0) >= TIMING.tensionWarn;
  }
  return t;
}

function medalFor(outcome) {
  if (outcome.aborted || outcome.partial) return 'abort';
  if (outcome.complete && outcome.clean) return 'gold';
  if (outcome.complete) return 'silver';
  return 'bronze';
}

/**
 * spots: mission landmarks (piles, prop, decoy, target, …). Returns
 * {step(now, telemetry), skip(now), finish(now), get beat, get clock}.
 */
export function createChapter1Director(missionId, spots = {}) {
  if (!CHAPTER1_MISSIONS.includes(missionId)) {
    throw new Error(`unknown chapter1 mission: ${missionId}`);
  }
  const prefix = PREFIX[missionId];
  const beats = {...sharedBeats(prefix), ...turnBeats(missionId, prefix)};
  const turns = TURN_FLAGS[missionId];
  let beat = 'black';
  let since = null;
  let clock = 0;
  let lastMoved = 0;
  let nudged = new Set();
  let seenTurns = new Set();
  let said = [];
  let reveal = new Set();
  let outcome = {complete: false, clean: true, partial: false, aborted: false, skipped: false, medal: 'bronze'};

  function say(id, params) {
    if (!id) return;
    said.push(params ? {id, params} : {id});
  }
  function enter(next, now) {
    beat = next;
    since = now;
    nudged = new Set();
    const data = beats[next] || {};
    if (data.radio) say(data.radio);
    for (const instrument of data.hud || []) reveal.add(instrument);
    if (next === 'work') lastMoved = now;
    if (next === 'report') {
      outcome.medal = medalFor(outcome);
      say(lineKey(prefix, `settle_${outcome.medal}`));
      say(lineKey(prefix, 'report'));
    }
  }
  function elapsed(now) {
    return now - since;
  }
  function nudge(now) {
    const id = lineKey(prefix, 'nudge');
    if (!idleReminder(id, TIMING.workNudge, now - lastMoved, nudged.has(id))) return;
    nudged.add(id);
    say(id);
  }
  function pickTurn(t) {
    for (const entry of turns) {
      if (seenTurns.has(entry.beat)) continue;
      if (t[entry.flag]) return entry;
    }
    return null;
  }
  function work(now, t) {
    const turn = pickTurn(t);
    if (turn) {
      seenTurns.add(turn.beat);
      if (turn.flag === 'contact' || turn.flag === 'murky' || turn.flag === 'suction') outcome.clean = false;
      if (turn.flag === 'aborted') {
        outcome.aborted = true;
        outcome.partial = true;
      }
      enter(turn.beat, now);
      return;
    }
    if (t.missionDone || t.complete) {
      outcome.complete = true;
      if (t.rework) outcome.clean = false;
      enter('report', now);
      return;
    }
    nudge(now);
    if (elapsed(now) > TIMING.workLimit) {
      outcome.partial = true;
      say(lineKey(prefix, 'timeout'));
      enter('report', now);
    }
  }
  function hint(now, t) {
    const data = beats[beat] || {};
    if (data.hint) return data.hint;
    if (beat !== 'work') return null;
    if (missionId === 'c1_pier_level2' && t.nearPile) return 'measure';
    if (missionId === 'c1_hull_fouling' && !t.lotoDone) return 'loto';
    if (missionId === 'c1_hull_fouling' && t.nearProp) return 'rate';
    if (missionId === 'c1_dropped_object' && (t.atTarget || t.atDecoy)) return 'photo';
    if (missionId === 'c1_signoff_exam') return 'photo';
    return 'move';
  }
  function view(now, t) {
    const time = elapsed(now);
    let black = 0;
    if (beat === 'black' || beat === 'card' || beat === 'done') black = 1;
    else if (beat === 'establish') black = Math.max(0, 1 - time / TIMING.fadeIn);
    else if (beat === 'fade') black = Math.min(1, time / TIMING.fade);
    const data = beats[beat] || {};
    return {
      beat,
      hint: hint(now, t),
      reveal: [...reveal],
      black,
      letterbox: !!data.cinematic,
      cinematic: !!data.cinematic,
      said,
      ended: beat === 'card' || beat === 'done',
      stamp: !!(t.measured || t.photographed || t.rated || t.photosDone),
      outcome: {...outcome},
    };
  }
  function step(now, telemetry = {}) {
    said = [];
    clock = now;
    if (since === null) enter('black', now);
    const t = enrichTelemetry(missionId, telemetry, spots);
    if ((Number(t.input) || 0) > TIMING.stickInput) lastMoved = now;
    const time = elapsed(now);
    const cut = beatDecision(beats[beat], time, t);
    if (cut) enter(cut, now);
    else if (beat === 'work') work(now, t);
    return view(now, t);
  }
  function skip(now) {
    outcome.skipped = true;
    outcome.partial = true;
    said = [];
    enter('card', now);
    return view(now, {});
  }
  function finish(now) {
    enter('done', now);
  }
  return {
    step,
    skip,
    finish,
    get beat() {
      return beat;
    },
    get clock() {
      return clock;
    },
  };
}

export const CHAPTER1_BEATS = Object.freeze([
  'black', 'establish', 'handover', 'work', 'report', 'fade', 'card', 'done',
]);
