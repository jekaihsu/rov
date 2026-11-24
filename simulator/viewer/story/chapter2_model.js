// Chapter 2 beat machines (C2-1 net / C2-2 morts / C2-3 escape). Pure functions, no DOM — node tests step
// them with made-up telemetry. Each mission opens with black → establish → handover, then a player beat that
// carries the turning point (billow/snag, silt, escape window). Uses beat_director for limits and idle nudges.
// Telemetry: {photos, reports, complete, billow, snagged, tension, visibility, silted, nearHole, input,
// holding, windowLeft}. Never touches the vehicle; physics stay on the server.

import {beatDecision, idleReminder} from './beat_director.js';

export const CHAPTER2_CONTRACTS = Object.freeze([
  'c2_net_inspection',
  'c2_mort_recovery',
  'c2_escape_event',
]);

export const TIMING = Object.freeze({
  black: 3.2,
  establish: 7.5,
  fadeIn: 2.2,
  handover: 1.5,
  idleNudge: 20,
  playerLimit: 120,
  wrap: 5.0,
  relief: 6.0,
  fade: 2.0,
  ending: 4.5,
  stickInput: 0.15,
  siltVis: 2.5,
  snagConfirm: 0.6,
});

const NET = {
  black: {limit: TIMING.black, next: 'establish', cinematic: true, radio: 'c21Open'},
  establish: {limit: TIMING.establish, next: 'handover', cinematic: true, location: true, radio: 'c21Crew'},
  handover: {limit: TIMING.handover, next: 'search', hud: ['depth', 'heading'], radio: 'c21Task'},
  search: {hint: 'move', hud: ['depth']},
  billow: {hint: 'clearance', hud: ['depth', 'tether']},
  report: {hint: 'photo', hud: ['photo']},
  wrap: {limit: TIMING.wrap, next: 'done', radio: 'c21Done'},
  done: {},
};

const MORT = {
  black: {limit: TIMING.black, next: 'establish', cinematic: true, radio: 'c22Open'},
  establish: {limit: TIMING.establish, next: 'handover', cinematic: true, location: true, radio: 'c22Crew'},
  handover: {limit: TIMING.handover, next: 'approach', hud: ['depth'], radio: 'c22Task'},
  approach: {hint: 'move', hud: ['depth']},
  silt: {hint: 'slow', hud: ['depth']},
  recover: {hint: 'grip'},
  wrap: {limit: TIMING.wrap, next: 'done', radio: 'c22Done'},
  done: {},
};

const ESCAPE = {
  black: {limit: TIMING.black, next: 'establish', cinematic: true, radio: 'c23Open'},
  establish: {limit: TIMING.establish, next: 'handover', cinematic: true, location: true, radio: 'c23Crew'},
  handover: {limit: TIMING.handover, next: 'search', hud: ['depth', 'heading'], radio: 'c23Task'},
  search: {hint: 'move', hud: ['depth']},
  found: {hint: 'photo', hud: ['photo']},
  watch: {hint: 'hold', hud: ['depth']},
  relief: {limit: TIMING.relief, next: 'fade', radio: 'c23Relief'},
  fade: {limit: TIMING.fade, next: 'ending'},
  ending: {limit: TIMING.ending, next: 'done'},
  done: {},
};

const SCRIPTS = Object.freeze({
  c2_net_inspection: NET,
  c2_mort_recovery: MORT,
  c2_escape_event: ESCAPE,
});

function scriptFor(contractId) {
  return SCRIPTS[contractId] || null;
}

/**
 * spots: optional {hole, basket} from the scenario. Returns {step, skip, finish, beat, clock}.
 */
export function createChapter2Director(contractId, spots = {}) {
  const beats = scriptFor(contractId);
  if (!beats) {
    return {
      step() {
        return {beat: 'done', hint: null, reveal: [], black: 0, letterbox: false, cinematic: false,
          said: [], ended: true, outcome: {}};
      },
      skip() {
        return this.step();
      },
      finish() {},
      get beat() {
        return 'done';
      },
      get clock() {
        return 0;
      },
    };
  }

  let beat = 'black';
  let since = null;
  let clock = 0;
  let lastMoved = 0;
  let snagSince = null;
  let nudged = new Set();
  let said = [];
  let reveal = new Set();
  const outcome = {
    billow: false,
    snag: false,
    silt: false,
    hole: false,
    complete: false,
    skipped: false,
  };

  function say(id, params) {
    said.push(params ? {id, params} : {id});
  }

  function enter(next, now) {
    beat = next;
    since = now;
    nudged = new Set();
    const data = beats[next] || {};
    if (data.radio) say(data.radio);
    for (const instrument of data.hud || []) reveal.add(instrument);
    if (next === 'search' || next === 'approach') lastMoved = now;
    if (next === 'billow') outcome.billow = true;
    if (next === 'silt') outcome.silt = true;
    if (next === 'found') outcome.hole = true;
    if (next === 'wrap' || next === 'relief') outcome.complete = true;
  }

  function elapsed(now) {
    return now - since;
  }

  function nudge(id, now, after) {
    if (!idleReminder(id, after, now - lastMoved, nudged.has(id))) return;
    nudged.add(id);
    say(id);
  }

  function netSearch(now, t) {
    if (t.billow) {
      enter('billow', now);
      say('c21Billow');
      return;
    }
    if (t.snagged) snagSince ??= now;
    else snagSince = null;
    if (snagSince !== null && now - snagSince >= TIMING.snagConfirm) {
      outcome.snag = true;
      enter('billow', now);
      say('c21Snag');
      return;
    }
    if ((Number(t.photos) || 0) > 0 || (Number(t.reports) || 0) > 0) {
      enter('report', now);
      say('c21Report');
      return;
    }
    nudge('c21Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c21Timeout');
    }
  }

  function netBillow(now, t) {
    if ((Number(t.photos) || 0) > 0 || (Number(t.reports) || 0) > 0) {
      enter('report', now);
      say('c21Report');
      return;
    }
    if (t.complete) {
      enter('wrap', now);
      return;
    }
    nudge('c21Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c21Timeout');
    }
  }

  function netReport(now, t) {
    if (t.complete || (Number(t.reports) || 0) >= 2) {
      enter('wrap', now);
      return;
    }
    nudge('c21Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c21Timeout');
    }
  }

  function mortApproach(now, t) {
    if (t.silted || (Number(t.visibility) || 99) < TIMING.siltVis) {
      enter('silt', now);
      say('c22Silt');
      return;
    }
    if ((Number(t.photos) || 0) > 0 || t.holding) {
      enter('recover', now);
      say('c22Grip');
      return;
    }
    nudge('c22Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c22Timeout');
    }
  }

  function mortSilt(now, t) {
    if (t.holding || t.complete) {
      enter('recover', now);
      say('c22Grip');
      return;
    }
    nudge('c22Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c22Timeout');
    }
  }

  function mortRecover(now, t) {
    if (t.complete) {
      enter('wrap', now);
      return;
    }
    nudge('c22Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit) {
      enter('wrap', now);
      say('c22Timeout');
    }
  }

  function escapeSearch(now, t) {
    if (t.nearHole || (Number(t.photos) || 0) > 0) {
      enter('found', now);
      say('c23Found');
      return;
    }
    nudge('c23Idle', now, TIMING.idleNudge);
    if (elapsed(now) > TIMING.playerLimit || (Number(t.windowLeft) || 999) <= 0) {
      enter('relief', now);
      say('c23Timeout');
    }
  }

  function escapeFound(now, t) {
    if ((Number(t.reports) || 0) > 0 || t.holding) {
      enter('watch', now);
      say('c23Watch');
      return;
    }
    if (elapsed(now) > TIMING.playerLimit) {
      enter('relief', now);
      say('c23Timeout');
    }
  }

  function escapeWatch(now, t) {
    if (t.complete || elapsed(now) > 25) {
      enter('relief', now);
      return;
    }
    if ((Number(t.windowLeft) || 999) <= 0) {
      enter('relief', now);
      say('c23Timeout');
    }
  }

  function hintFor() {
    return beats[beat]?.hint || null;
  }

  function step(now, telemetry = {}) {
    said = [];
    clock = now;
    if (since === null) enter('black', now);
    const t = telemetry;
    if ((Number(t.input) || 0) > TIMING.stickInput) lastMoved = now;
    const time = elapsed(now);
    const cut = beatDecision(beats[beat], time, t);
    if (cut) enter(cut, now);
    else if (contractId === 'c2_net_inspection') {
      if (beat === 'search') netSearch(now, t);
      else if (beat === 'billow') netBillow(now, t);
      else if (beat === 'report') netReport(now, t);
    } else if (contractId === 'c2_mort_recovery') {
      if (beat === 'approach') mortApproach(now, t);
      else if (beat === 'silt') mortSilt(now, t);
      else if (beat === 'recover') mortRecover(now, t);
    } else if (contractId === 'c2_escape_event') {
      if (beat === 'search') escapeSearch(now, t);
      else if (beat === 'found') escapeFound(now, t);
      else if (beat === 'watch') escapeWatch(now, t);
    }
    return view(now, t);
  }

  function view(now, t) {
    const time = elapsed(now);
    let black = 0;
    if (beat === 'black' || beat === 'ending' || beat === 'done') black = 1;
    else if (beat === 'establish') black = Math.max(0, 1 - time / TIMING.fadeIn);
    else if (beat === 'fade') black = Math.min(1, time / TIMING.fade);
    const data = beats[beat] || {};
    return {
      beat,
      hint: hintFor(),
      reveal: [...reveal],
      black,
      letterbox: !!data.cinematic,
      cinematic: !!data.cinematic,
      location: !!data.location,
      said,
      ended: beat === 'done' || beat === 'ending',
      outcome: {...outcome, spots},
      windowLeft: t.windowLeft,
    };
  }

  function skip(now) {
    outcome.skipped = true;
    said = [];
    if (contractId === 'c2_escape_event') enter('ending', now);
    else enter('done', now);
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

export const CHAPTER2_BEATS = Object.freeze({
  c2_net_inspection: Object.keys(NET),
  c2_mort_recovery: Object.keys(MORT),
  c2_escape_event: Object.keys(ESCAPE),
});
