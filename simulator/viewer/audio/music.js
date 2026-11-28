// Background music: picks a track for the current context (title menu, briefing, dive, results, incident
// tension), crossfades between tracks, ducks under radio calls and alarms, and pauses while the tab is hidden.
// Dive and tension music are non-diegetic and follow the `diveMusic` fidelity item (off in `real`); menu and
// results music only follow the 音樂 volume. Tracks stream from <audio> elements created on first use, routed
// into the shared audio engine's music bus, so nothing loads before the first user gesture.
import {getFidelity} from '../fidelity.js';
import {diveMusicEnabled} from './music_fidelity.js';

export const MUSIC_BASE = new URL('./music/', import.meta.url).href;

// Every file is public domain or CC0; see simulator/viewer/models/CREDITS.md and research_notes/音樂/sources.md.
export const MUSIC_TRACKS = Object.freeze({
  title: [{id: 'title_drone', file: 'title_drone.opus', loop: true, level: 0.8}],
  briefing: [
    {id: 'briefing_wtc_prelude1', file: 'briefing_wtc_prelude1.opus', loop: true, level: 0.75},
    {id: 'title_goldberg_aria', file: 'title_goldberg_aria.opus', loop: true, level: 0.75}
  ],
  dive: [
    {id: 'dive_underwater_theme_ii', file: 'dive_underwater_theme_ii.opus', loop: true, level: 0.45},
    {id: 'dive_underwater_theme', file: 'dive_underwater_theme.opus', loop: true, level: 0.4}
  ],
  results: [{id: 'results_peer_gynt_morning', file: 'results_peer_gynt_morning.opus', loop: false, level: 0.8}],
  tension: [{id: 'tension_peer_gynt_aase', file: 'tension_peer_gynt_aase.opus', loop: true, level: 0.55}]
});

// The prologue and cold open share the director. Relief uses the dive gate until the closing card;
// sharing a track id lets the card continue the same phrase after a successful release.
export const CINEMATIC_TRACKS = Object.freeze({
  cinematic: [MUSIC_TRACKS.dive[0]],
  openingTension: [MUSIC_TRACKS.tension[0]],
  relief: [MUSIC_TRACKS.results[0]],
  flashback: [MUSIC_TRACKS.results[0]]
});

// Contexts heard while the vehicle is in the water; a real operator does not hear them.
export const IN_DIVE_CONTEXTS = new Set(['dive', 'tension', 'relief']);

const BRIEFING_SCREENS = new Set(['hangar', 'sites', 'briefing']);
const DUCKING_CUES = new Set(['warn', 'broken', 'hard', 'severe']);
const TENSION_HOLD_SECONDS = 20;
const DUCK_ALERT_SECONDS = 2.5;
const RADIO_SELECTOR = '.story-radio:not([hidden]), .tether-radio:not([hidden]), .cold-open-radio.speaking';
const TICK_MS = 100;

// Launch-menu screen name → music context. No screen (leaving the menu) means silence.
export function menuContext(screen) {
  if (!screen) return null;
  return BRIEFING_SCREENS.has(screen) ? 'briefing' : 'title';
}

// True while the dive has an ongoing problem the pilot must deal with.
export function incidentActive(state) {
  if (!state) return false;
  const tether = state.tether || {};
  const power = state.power || {};
  if (tether.warn || tether.broken || (tether.snagged_on || []).length) return true;
  if (state.leak?.detected || power.tripped || power.cutoff) return true;
  if (state.link?.state === 'lost') return true;
  if ((state.thermal?.warnings || []).length) return true;
  return typeof state.battery === 'number' && state.battery <= 10;
}

function latestSevereEvent(state) {
  let latest = -Infinity;
  for (const event of state?.events || []) {
    if (event.severity === 'severe' && typeof event.t === 'number') latest = Math.max(latest, event.t);
  }
  return latest;
}

// In-dive context from a state snapshot. `memory` keeps the tension hold between calls (sim time, seconds),
// so a brief incident keeps the tension track long enough to avoid flapping.
export function diveContext(state, memory = {}) {
  if (!state) return null;
  if (state.score?.finished) return 'results';
  const now = typeof state.t === 'number' ? state.t : 0;
  if (memory.until !== undefined && now < memory.since) memory.until = undefined;
  memory.since = now;
  const severeAt = latestSevereEvent(state);
  if (incidentActive(state) || now - severeAt < TENSION_HOLD_SECONDS) {
    memory.until = Math.max(memory.until ?? -Infinity, now + TENSION_HOLD_SECONDS);
  }
  if (memory.until !== undefined && now < memory.until) return 'tension';
  return 'dive';
}

// Whether a context may play under the current fidelity settings.
export function musicAllowed(context, fidelity) {
  if (!context) return false;
  if (IN_DIVE_CONTEXTS.has(context)) return diveMusicEnabled(fidelity);
  return true;
}

function approach(value, target, step) {
  if (value < target) return Math.min(target, value + step);
  return Math.max(target, value - step);
}

// Pure crossfade and ducking state machine. Times are seconds on any monotonic clock.
export function createMusicDirector(options = {}) {
  const fadeSeconds = options.fadeSeconds ?? 2.5;
  const duckLevel = options.duckLevel ?? 0.3;
  const duckAttack = options.duckAttack ?? 0.25;
  const duckRelease = options.duckRelease ?? 1.5;
  const tracks = options.tracks || MUSIC_TRACKS;
  const layers = new Map();
  const rotation = {};
  let context = null;
  let current = null;
  let duckUntil = -Infinity;
  let held = false;
  let duck = 1;
  let last = null;

  function pickTrack(name) {
    const list = tracks[name] || [];
    if (!list.length) return null;
    const index = rotation[name] || 0;
    rotation[name] = (index + 1) % list.length;
    return list[index];
  }

  function setContext(name) {
    const next = name || null;
    if (next === context) return false;
    context = next;
    if (current) layers.get(current.id).target = 0;
    current = next ? pickTrack(next) : null;
    if (current) {
      const layer = layers.get(current.id) || {track: current, gain: 0, fresh: true};
      layer.target = 1;
      layers.set(current.id, layer);
    }
    return true;
  }

  function duckFor(now, seconds = DUCK_ALERT_SECONDS) {
    duckUntil = Math.max(duckUntil, now + seconds);
  }

  function hold(flag) {
    held = !!flag;
  }

  function step(now) {
    const dt = last === null ? 0 : Math.max(0, now - last);
    last = now;
    const ducked = held || now < duckUntil;
    const duckTarget = ducked ? duckLevel : 1;
    const duckRate = (1 - duckLevel) / (ducked ? duckAttack : duckRelease);
    duck = approach(duck, duckTarget, duckRate * dt);
    const stopped = [];
    const started = [];
    for (const [id, layer] of layers) {
      if (layer.fresh) {
        started.push(layer.track);
        layer.fresh = false;
      }
      layer.gain = approach(layer.gain, layer.target, dt / fadeSeconds);
      if (layer.gain === 0 && layer.target === 0) {
        layers.delete(id);
        stopped.push(layer.track);
      }
    }
    return {context, duck, started, stopped, layers: snapshot()};
  }

  function snapshot() {
    return [...layers.values()].map(function describe(layer) {
      return {track: layer.track, gain: layer.gain, target: layer.target};
    });
  }

  return {
    setContext,
    duckFor,
    hold,
    step,
    get context() {
      return context;
    },
    get current() {
      return current;
    },
    get duck() {
      return duck;
    },
    get layers() {
      return snapshot();
    }
  };
}

function radioShowing() {
  return !!globalThis.document?.querySelector(RADIO_SELECTOR);
}

let sharedMusic;

// Connects the director to <audio> elements on the engine's music bus. Call once per page.
export function installMusic({engine, fidelity = getFidelity(), base = MUSIC_BASE} = {}) {
  if (sharedMusic) return sharedMusic;
  const director = createMusicDirector({tracks: {...MUSIC_TRACKS, ...CINEMATIC_TRACKS}});
  const players = new Map();
  const memory = {};
  let requested = null;
  let cuePaused = false;
  let timer = 0;

  function player(track) {
    if (players.has(track.id)) return players.get(track.id);
    const element = new Audio();
    element.preload = 'auto';
    element.loop = track.loop;
    element.src = base + track.file;
    const source = engine.ctx.createMediaElementSource(element);
    const gain = engine.ctx.createGain();
    gain.gain.value = 0;
    source.connect(gain).connect(engine.buses.music);
    const entry = {track, element, gain};
    players.set(track.id, entry);
    return entry;
  }

  function play(entry) {
    if (document.hidden || !entry.element.paused || entry.element.ended) return;
    entry.element.play().catch(function blocked() {
      // Autoplay is refused until the first gesture; the next tick retries.
    });
  }

  function tick() {
    const ready = engine.ctx && engine.ctx.state === 'running' && engine.buses?.music;
    const wanted = musicAllowed(requested, fidelity) ? requested : null;
    director.setContext(ready ? wanted : null);
    director.hold(radioShowing());
    const output = director.step(performance.now() / 1000);
    for (const track of output.stopped) {
      const entry = players.get(track.id);
      if (!entry) continue;
      entry.element.pause();
      entry.element.currentTime = 0;
    }
    if (!ready) return;
    for (const layer of output.layers) {
      const entry = player(layer.track);
      const level = layer.gain * output.duck * layer.track.level;
      entry.gain.gain.setTargetAtTime(level, engine.ctx.currentTime, 0.05);
      if (document.hidden || cuePaused) entry.element.pause();
      else play(entry);
    }
  }

  let resultsShown = false;
  // A cold-open cue (CINEMATIC_TRACKS) overrides the dive context while it is set.
  let cinematic = null;
  function setRequested(context) {
    requested = context;
    tick();
  }

  function onCue(kind) {
    if (DUCKING_CUES.has(kind)) director.duckFor(performance.now() / 1000);
  }

  engine.cueListeners?.push(onCue);
  fidelity.subscribe?.(tick);
  document.addEventListener('visibilitychange', tick);
  timer = setInterval(tick, TICK_MS);

  sharedMusic = {
    // Launch menu: pass the screen name, or null when leaving the menu.
    setScreen(screen) {
      setRequested(menuContext(screen));
    },
    // In game: pass the displayed state snapshot every frame.
    update(state) {
      const context = cinematic || (resultsShown ? 'results' : diveContext(state, memory));
      if (context !== requested) setRequested(context);
    },
    // The results screen (play/results.js) is up: play the results track whatever the run was.
    showResults(open) {
      resultsShown = !!open;
    },
    // Cold open: play a cutscene cue ('cinematic', 'flashback') or hand back to the dive rules with null.
    cue(name) {
      cinematic = Object.hasOwn(CINEMATIC_TRACKS, name) ? name : null;
      if (cinematic) setRequested(cinematic);
    },
    pauseCue(value) {
      cuePaused = !!value;
      tick();
    },
    duck(seconds) {
      director.duckFor(performance.now() / 1000, seconds);
    },
    stop() {
      clearInterval(timer);
      requested = null;
      for (const entry of players.values()) entry.element.pause();
    },
    // For browser checks: what is requested, allowed and audible right now.
    debug() {
      return {
        requested,
        context: director.context,
        allowed: musicAllowed(requested, fidelity),
        duck: director.duck,
        players: [...players.values()].map(function describe(entry) {
          return {id: entry.track.id, paused: entry.element.paused, gain: entry.gain.gain.value,
            time: entry.element.currentTime};
        })
      };
    }
  };
  return sharedMusic;
}
