// Cold open director: the beat machine of the new-game flash-forward (docs/design/cold-open/README.md), without
// any DOM, so node tests can step it with made-up telemetry. Each step takes the presentation clock (seconds) and
// what the dive is doing (photos taken, raw snag flag, tether tension, position, speed) and returns what the
// screen should show: the beat, the one hint, the HUD parts revealed so far, the black and letterbox levels and
// the radio lines queued in this step. It never touches the vehicle: the dive itself stays the server's physics.
//
// Beats: black → establish (cinematic) → handover → approach (fly to the anode, photograph it)
// → payoff → transit (head for leg B) → incident (the tether snags; stop, back out) → relief → fade → card → done.
// Nothing waits on the player for ever: idle nudges come over the radio, and every beat that needs the player has
// a time limit after which the story moves on (a missed photo, a route that never snags, a snag never cleared).
// `snagged` is a held hook of the server's snag model (state.tether.snags), not a tether merely touching steel.
// A hook that lets go before the back-out call was not cleared by the pilot: the radio calls it luck (`slipped`).

export const TIMING = Object.freeze({
  black: 5.0,              // black screen with the first radio line
  establish: 8.0,          // the cinematic shot, fading in over `fadeIn`
  fadeIn: 2.4,
  handover: 1.6,           // letterbox retracts, camera returns to the onboard view
  photoHintRange: 3.2,     // m from the photo spot at which the hint changes from moving to the shutter
  photoHintAfter: 22,      // s into the approach when the shutter hint shows anyway
  nudgeMove: 18,           // s without moving before the radio prompts
  nudgePhoto: 48,
  approachLimit: 110,      // s; past it the story moves on without the photo
  payoff: 6.0,
  transitNudge: 20,
  transitLimit: 85,        // s without a snag: the story ends without the incident
  snagConfirm: 0.6,        // s a hook must hold before it is the incident (a hook can form and let go at once)
  stopFirst: 6.0,          // s after the incident before the back-out call comes anyway
  pullCall: 7.0,           // s between two tension calls
  pullTension: 40,         // N: the tender calls it out above this
  releaseConfirm: 1.5,     // s with no snag before it counts as free
  incidentLimit: 100,
  relief: 6.5,
  fade: 2.0,
  stickInput: 0.15,        // stick deflection (0..1) above which the pilot counts as flying
  stoppedTension: 20,      // N: below this the pilot has stopped pulling
});

const BEATS = ['black', 'establish', 'handover', 'approach', 'payoff', 'transit', 'incident', 'relief', 'fade',
  'card', 'done'];

function distance2(a, b) {
  if (!a || !b) return Infinity;
  return Math.hypot(a[0] - b[0], a[1] - b[1]);
}

function roundTension(value) {
  return Math.max(10, Math.round((Number(value) || 0) / 10) * 10);
}

/**
 * spots: {anode: [n, e], start: [n, e]} from the scenario (world objectives). Returns {step(now, telemetry),
 * skip(now), get beat}. telemetry: {photos, snagged, broken, tension, pos, input}. step() returns
 * {beat, hint, reveal, black, letterbox, cinematic, said: [{id, params}], ended, outcome}.
 */
export function createColdOpenDirector(spots = {}) {
  let beat = 'black';
  let since = null;
  let clock = 0;
  let photosAtStart = null;
  let lastMoved = 0;
  let snagSince = null;
  let freeSince = null;
  let stoppedSince = null;
  let lastPullCall = -Infinity;
  let backOutCalled = false;
  let nudged = new Set();
  let said = [];
  let photoNear = false;
  let outcome = {photo: false, snag: false, released: false, broken: false, skipped: false};
  const reveal = new Set();

  function say(id, params) {
    said.push(params ? {id, params} : {id});
  }
  function enter(next, now) {
    beat = next;
    since = now;
    nudged = new Set();
    if (next === 'black') say('open');
    if (next === 'establish') say('crew');
    if (next === 'handover') {
      reveal.add('depth');
      reveal.add('heading');
      say('task');
    }
    if (next === 'approach') lastMoved = now;
    if (next === 'payoff') {
      reveal.add('photo');
      say(photoNear ? 'praise' : 'praiseFar');
    }
    if (next === 'transit') {
      lastMoved = now;
      say(outcome.photo ? 'toLegB' : 'skipPhoto');
    }
    if (next === 'incident') {
      reveal.add('tether');
      outcome.snag = true;
      backOutCalled = false;
      stoppedSince = null;
      freeSince = null;
    }
    if (next === 'relief') {
      if (outcome.released && !backOutCalled) {
        say('slipped');
        say('lucky');
      } else if (outcome.released) {
        say('free');
        say('remember');
      } else if (outcome.broken) {
        say('snapped');
        say('lost');
      } else if (outcome.snag) {
        say('stuck');
      } else {
        say('noSnag');
      }
    }
  }
  function elapsed(now) {
    return now - since;
  }
  function nudge(id, now, after, idleSince) {
    if (nudged.has(id) || now - idleSince < after) return;
    nudged.add(id);
    say(id);
  }
  function approach(now, t) {
    if (photosAtStart === null) photosAtStart = t.photos || 0;
    if ((t.photos || 0) > photosAtStart) {
      outcome.photo = true;
      photoNear = distance2(t.pos, spots.anode) < TIMING.photoHintRange + 1;
      enter('payoff', now);
      return;
    }
    nudge('nudgeMove', now, TIMING.nudgeMove, lastMoved);
    nudge('nudgePhoto', now, TIMING.nudgePhoto, since);
    if (elapsed(now) > TIMING.approachLimit) enter('transit', now);
  }
  function transit(now, t) {
    if (t.broken) {
      outcome.broken = true;
      enter('relief', now);
      return;
    }
    if (t.snagged) snagSince ??= now;
    else snagSince = null;
    if (snagSince !== null && now - snagSince >= TIMING.snagConfirm) {
      enter('incident', now);
      say('tension', {n: roundTension(t.tension)});
      say('stop');
      lastPullCall = now;
      return;
    }
    nudge('nudgeLegB', now, TIMING.transitNudge, lastMoved);
    if (elapsed(now) > TIMING.transitLimit) enter('relief', now);
  }
  function incident(now, t) {
    // Pulled hard enough, the termination parts (tether.py): the vehicle is off the tether, the scene still ends.
    if (t.broken) {
      outcome.broken = true;
      enter('relief', now);
      return;
    }
    if (t.snagged) freeSince = null;
    else freeSince ??= now;
    if (freeSince !== null && now - freeSince >= TIMING.releaseConfirm) {
      outcome.released = true;
      enter('relief', now);
      return;
    }
    const pulling = (Number(t.tension) || 0) >= TIMING.stoppedTension;
    if (pulling) stoppedSince = null;
    else stoppedSince ??= now;
    const stopped = stoppedSince !== null && now - stoppedSince > 1.2;
    if (!backOutCalled && (stopped || elapsed(now) > TIMING.stopFirst)) {
      backOutCalled = true;
      say('backOut');
    }
    if (backOutCalled && (Number(t.tension) || 0) > TIMING.pullTension && now - lastPullCall > TIMING.pullCall) {
      lastPullCall = now;
      say('dontPull', {n: roundTension(t.tension)});
    }
    if (elapsed(now) > TIMING.incidentLimit) enter('relief', now);
  }
  function hint(now, t) {
    if (beat === 'approach') {
      const near = distance2(t.pos, spots.anode) < TIMING.photoHintRange;
      return near || elapsed(now) > TIMING.photoHintAfter ? 'photo' : 'move';
    }
    if (beat === 'transit') return 'turn';
    if (beat === 'incident') return backOutCalled ? 'reverse' : 'release';
    return null;
  }
  function step(now, telemetry = {}) {
    said = [];
    clock = now;
    if (since === null) enter('black', now);
    const t = telemetry;
    if ((Number(t.input) || 0) > TIMING.stickInput) lastMoved = now;
    const time = elapsed(now);
    if (beat === 'black' && time >= TIMING.black) enter('establish', now);
    else if (beat === 'establish' && time >= TIMING.establish) enter('handover', now);
    else if (beat === 'handover' && time >= TIMING.handover) enter('approach', now);
    else if (beat === 'approach') approach(now, t);
    else if (beat === 'payoff' && time >= TIMING.payoff) enter('transit', now);
    else if (beat === 'transit') transit(now, t);
    else if (beat === 'incident') incident(now, t);
    else if (beat === 'relief' && time >= TIMING.relief) enter('fade', now);
    else if (beat === 'fade' && time >= TIMING.fade) enter('card', now);
    return view(now, t);
  }
  function view(now, t) {
    const time = elapsed(now);
    let black = 0;
    if (beat === 'black' || beat === 'card' || beat === 'done') black = 1;
    else if (beat === 'establish') black = Math.max(0, 1 - time / TIMING.fadeIn);
    else if (beat === 'fade') black = Math.min(1, time / TIMING.fade);
    return {
      beat,
      hint: hint(now, t),
      reveal: [...reveal],
      black,
      letterbox: beat === 'black' || beat === 'establish',
      cinematic: beat === 'black' || beat === 'establish',
      said,
      ended: beat === 'card' || beat === 'done',
      outcome: {...outcome},
    };
  }
  // Replays may skip straight to the closing card.
  function skip(now) {
    outcome.skipped = true;
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

export const COLD_OPEN_BEATS = Object.freeze(BEATS);
