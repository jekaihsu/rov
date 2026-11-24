// Chapter 1 presentation: documentary beats over the four career contracts (docs/story/chapters/chapter1.md).
// The director (chapter1_model.js) owns timing and radio; this module draws the stage like cold_open —
// establishing shot, location super, one hint, HUD reveal, photo/measure stamp, closing chapter cards.
// Presentation only: never writes fidelity or localStorage. Scripted beats may hold the cutscene look.
import {createBeatStage, element, establishingShot, presentStage} from './beat_stage.js';
import {CHAPTER1_MISSIONS, TIMING, createChapter1Director} from './chapter1_model.js';
import {STRINGS, SPEAKER_OF} from './chapter1_copy.js';
import {CINEMATIC_MUSIC, createCinematicLook, isScriptedBeat} from './cutscene_look.js';
import {lineSeconds} from './cold_open.js';
import {FLAG as COLD_OPEN_FLAG} from './cold_open_flow.js';
import {beautifyEnabled} from '../fx/beautify.js';
import {getFidelity} from '../fidelity.js';
import {actionCaps, axisCaps} from '../play/onboarding.js';
import {deviceFamily} from '../input/glyphs.js';
import {axisChannel, bindingRow} from '../input/bindings.js';
import {showTitleCard} from '../brand/chapter_card.js';
import {careerChapterCardData} from '../brand/chapters.js';
import {installVoice} from '../audio/voice.js';
import {getLanguage} from '../i18n/index.js';

const CARD_MS = 4200;
const CLOCK_STEP_MAX_S = 1.0;
const CUT_SETTLE_S = 0.6;
const TENSION_HOLD_S = 3;
const MISSION_SET = new Set(CHAPTER1_MISSIONS);

function easeInOut(x) {
  const k = Math.max(0, Math.min(1, x));
  return k * k * (3 - 2 * k);
}

function wantedMission(params, getContractId) {
  if (params.get(COLD_OPEN_FLAG)) return '';
  const id = getContractId?.() || params.get('contract') || '';
  return MISSION_SET.has(id) ? id : '';
}

function lineText(id, params = {}) {
  let text = STRINGS.lines[id] || '';
  for (const [key, value] of Object.entries(params)) text = text.replace(`{${key}}`, String(value));
  return text;
}

let activeChapter1 = null;

/** True while a Chapter 1 scripted beat or closing card owns the sticks. */
export function chapter1ControlsBlocked() {
  return !!activeChapter1?.controlsBlocked?.();
}

/**
 * Options: input, setCam, camera, rovG, music, getContractId (optional; defaults to ?contract=),
 * getWorld, readOnly, params, navigate.
 */
export function installChapter1({
  input, setCam, camera, rovG, music = null, getContractId = null, getWorld = null,
  readOnly = false,
  params = new URLSearchParams(globalThis.location?.search || ''),
  navigate = null,
} = {}) {
  const missionId = readOnly ? '' : wantedMission(params, getContractId);
  const inert = {
    update() {},
    frame() {},
    controlsBlocked() {
      return false;
    },
    get active() {
      return false;
    },
  };
  if (!missionId) {
    activeChapter1 = inert;
    return inert;
  }

  const voice = installVoice();
  const location = STRINGS.locations[missionId] || STRINGS.locations.c1_pier_level2;
  const stage = createBeatStage('chapter1', location, STRINGS.stamp.photo);
  const {body, black, radio, speaker, words, hint, stamp, tension} = stage;
  let world = null;
  let state = null;
  let director = null;
  let view = null;
  let family = 'keyboard';
  let clock = 0;
  let lastFrameAt = null;
  let queue = [];
  let speaking = null;
  let ended = false;
  let cineMode = false;
  let cutAt = -Infinity;
  let hintSignature = '';
  let lastCue = '';
  let stampedUntil = -Infinity;
  let cardsPending = false;
  const look = createCinematicLook();
  const log = [];
  const report = {beats: [], lines: log, hints: [], outcome: null, missionId};
  window.__chapter1 = {
    controls: () => ({
      surge: axisControl('surge'),
      yaw: axisControl('yaw'),
      heave: axisControl('heave'),
      photo: actionControl('photo'),
    }),
    debug: () => ({
      beat: view?.beat || 'waiting',
      reveal: view?.reveal || [],
      hint: view?.hint || null,
      outcome: view?.outcome || null,
      lines: log.map(function id(entry) {
        return entry.id;
      }),
      look: {cinematic: look.active, beautify: beautifyEnabled(), fidelity: getFidelity().snapshot()},
    }),
    report,
  };

  document.addEventListener('rov-key-rows', function invalidateHint() {
    hintSignature = '';
  });
  document.addEventListener('rov-input-device', function deviceChanged(event) {
    family = event.detail && event.detail !== 'touch' ? deviceFamily(event.detail) : 'keyboard';
    hintSignature = '';
  });

  function now() {
    return clock;
  }
  function controls() {
    const hud = input?.hudState?.() || {};
    return {
      bindings: hud.bindings,
      rows: hud.keyRows,
      operationMode: state?.operation_mode || hud.operationMode || 'ROV_USA',
    };
  }
  function axisControl(axis) {
    const keys = controls();
    const rows = keys.rows || [];
    const own = rows.find(function pilotRow(row) {
      return row.action === axis && row.pilot;
    });
    const drive = axisChannel(axis, keys.operationMode);
    const channel = drive && rows.find(function channelRow(row) {
      return row.action === drive.channel;
    });
    const codes = own?.keys?.length === 2 ? own.keys : channel?.keys || [];
    return {
      keys: !own && drive?.sign < 0 ? [codes[1], codes[0]] : codes,
      pad: keys.bindings?.[drive?.channel] ?? bindingRow(drive?.channel)?.pad ?? null,
      sign: drive?.sign ?? 1,
    };
  }
  function actionControl(action) {
    const keys = controls();
    const row = (keys.rows || []).find(function actionRow(entry) {
      return entry.action === action;
    });
    return {keys: row?.keys || [], pad: keys.bindings?.[action] ?? bindingRow(action)?.pad ?? null};
  }
  function spots() {
    const objectives = world?.objectives || world?.scenario?.objectives || [];
    const piles = objectives.filter(function pile(item) {
      return /pile|pier|柱|樁/i.test(item.id || item.label || '');
    }).map(function point(item) {
      return (item.point || []).slice(0, 2);
    });
    const prop = objectives.find(function item(entry) {
      return /prop|螺槳/i.test(entry.id || entry.label || '');
    })?.point;
    const decoy = objectives.find(function item(entry) {
      return /decoy|rock|石/i.test(entry.id || entry.label || '');
    })?.point;
    const target = objectives.find(function item(entry) {
      return /instrument|target|儀/i.test(entry.id || entry.label || '');
    })?.point;
    return {
      piles: piles.length ? piles : [[0, 8], [4, 10], [-4, 10]],
      prop: prop ? prop.slice(0, 2) : [0, -6],
      decoy: decoy ? decoy.slice(0, 2) : [6, 4],
      target: target ? target.slice(0, 2) : [-6, 4],
    };
  }
  function telemetry(s) {
    const tether = s?.tether || {};
    const snags = Array.isArray(tether.snags) ? tether.snags.length : (tether.snagged_on || []).length;
    const sticks = Object.values(input?.out || {}).reduce(function largest(most, value) {
      return Math.max(most, Math.abs(Number(value) || 0));
    }, 0);
    const silt = Number(s?.turbidity?.silt || s?.silt || 0);
    const vis = Number(s?.turbidity?.visibility_m);
    const flow = Math.hypot(s?.current_here?.[0] || 0, s?.current_here?.[1] || 0);
    const career = s?.career || {};
    return {
      input: sticks,
      pos: s?.pos,
      photos: s?.photos || 0,
      nearPile: career.nearPile,
      measured: career.measured || career.laserLogged,
      contact: !!s?.collision || !!career.contact,
      murky: silt > 0.35 || (Number.isFinite(vis) && vis < 1.2),
      lotoDone: !!career.lotoDone || !!s?.loto?.complete,
      nearProp: career.nearProp,
      suction: flow > 0.35,
      flow: flow > 0.35,
      current: flow,
      rated: career.rated,
      echoesSeen: career.echoesSeen || (s?.sonar?.contacts || 0) > 0,
      atDecoy: career.atDecoy,
      atTarget: career.atTarget,
      photographed: career.photographed,
      photosDone: career.photosDone,
      snagged: snags > 0,
      tensionN: tether.tension_rov || 0,
      tension: (tether.tension_rov || 0) >= TIMING.tensionWarn,
      aborted: !!career.aborted,
      missionDone: !!career.missionDone || !!career.complete,
      complete: !!career.complete,
      rework: !!career.rework,
    };
  }
  function enqueue(entries) {
    for (const entry of entries) {
      const text = lineText(entry.id, entry.params);
      const who = SPEAKER_OF[entry.id];
      queue.push({id: entry.id, speaker: STRINGS.speakers[who] || '', text});
    }
  }
  function updateRadio(time) {
    if (speaking && time >= speaking.until) {
      speaking = null;
      radio.classList.remove('speaking');
    }
    if (speaking || !queue.length) return;
    const next = queue.shift();
    const language = getLanguage();
    const scale = getFidelity().get('radioDuration') ?? 1;
    speaking = {...next, until: time + lineSeconds(next.text, language) * scale};
    speaker.textContent = next.speaker;
    words.textContent = next.text;
    radio.classList.add('speaking');
    log.push({id: next.id, at: Math.round(time * 10) / 10, text: next.text});
    Promise.resolve(voice.playLine?.({speaker: next.speaker, text: next.text, language}))
      .catch(function quiet() {});
  }
  function hintLines(id) {
    const keys = controls();
    if (id === 'move') return [[axisCaps('surge', family, keys), STRINGS.hints.move]];
    if (id === 'photo') return [[actionCaps('photo', family, keys), STRINGS.hints.photo]];
    if (id === 'measure') return [[actionCaps('photo', family, keys), STRINGS.hints.measure]];
    if (id === 'rate') return [[actionCaps('photo', family, keys), STRINGS.hints.rate]];
    if (id === 'reverse') return [[axisCaps('surge', family, keys), STRINGS.hints.reverse]];
    if (id === 'release') return [['', STRINGS.hints.release]];
    if (id === 'unlock') return [[actionCaps('lock', family, keys), STRINGS.hints.unlock]];
    if (id === 'loto') return [['', STRINGS.hints.loto]];
    return [];
  }
  function renderHint(id) {
    const signature = `${id}|${family}`;
    if (signature === hintSignature) return;
    hintSignature = signature;
    hint.dataset.hint = id || '';
    body.dataset.coldHint = id || '';
    hint.classList.toggle('visible', !!id);
    if (!id) return;
    report.hints.push(id);
    hint.replaceChildren(...hintLines(id).map(function line([caps, label]) {
      const row = element('div', 'cold-open-hint-line');
      const capsNode = element('span', 'ob-caps');
      capsNode.innerHTML = caps;
      row.append(capsNode, element('span', 'cold-open-hint-label', label));
      return row;
    }));
  }
  const peaks = [];
  function renderTension(s) {
    const time = now();
    peaks.push([time, s?.tether?.tension_rov || 0]);
    while (peaks.length && time - peaks[0][0] > TENSION_HOLD_S) peaks.shift();
    const value = Math.round(peaks.reduce(function highest(most, [, next]) {
      return Math.max(most, next);
    }, 0));
    const text = `${STRINGS.tension} ${value} N`;
    if (tension.textContent !== text) tension.textContent = text;
    tension.dataset.tone = value >= TIMING.tensionWarn ? 'warn' : '';
  }
  function cue(name) {
    if (name === lastCue) return;
    lastCue = name;
    music?.cue?.(name);
  }
  function cutDip() {
    const since = now() - cutAt;
    if (since < 0 || since > CUT_SETTLE_S) return 0;
    return since < CUT_SETTLE_S / 2 ? 1 : 2 - 2 * since / CUT_SETTLE_S;
  }
  function stampKind(next, t) {
    if (t?.measured) return STRINGS.stamp.measure;
    if (t?.rated) return STRINGS.stamp.rate;
    if (t?.photographed || t?.photosDone) return STRINGS.stamp.photo;
    if (next.stamp) return STRINGS.stamp.photo;
    return '';
  }
  function applyView(next, t = {}) {
    const before = view?.beat;
    view = next;
    if (next.beat !== before) {
      report.beats.push({beat: next.beat, at: Math.round(now() * 10) / 10});
      body.dataset.coldBeat = next.beat;
    }
    enqueue(next.said);
    if (next.cinematic && !cineMode) {
      cineMode = true;
      setCam?.('cine');
    } else if (!next.cinematic && cineMode) {
      cineMode = false;
      cutAt = now();
      setCam?.('onboard');
    }
    const dip = cutDip();
    black.style.transition = dip > 0 ? 'none' : '';
    presentStage(stage, {
      black: Math.max(next.black, dip),
      letterbox: next.letterbox,
      cinematic: next.cinematic || cineMode || now() - cutAt < CUT_SETTLE_S,
      location: next.beat === 'establish' && now() > TIMING.black + 1.0,
      reveal: next.reveal,
    });
    const label = stampKind(next, t);
    if (label && (next.beat === 'report' || next.stamp || t.measured || t.photographed || t.rated)) {
      stamp.textContent = label;
      stampedUntil = now() + 2.6;
    }
    stamp.classList.toggle('visible', now() < stampedUntil);
    tension.classList.toggle('visible', next.reveal.includes('tether') && !next.ended);
    renderHint(next.ended ? null : next.hint);
    look.set(isScriptedBeat(next));
    if (isScriptedBeat(next)) cue(CINEMATIC_MUSIC.scripted);
    else if (next.ended) cue(CINEMATIC_MUSIC.closing);
    else cue(null);
    if (next.ended && !ended) end();
  }
  function finishDirector() {
    director.finish(now());
    report.done = true;
    cardsPending = false;
  }
  function showClosingCards() {
    cardsPending = true;
    const ch1 = careerChapterCardData('ch1', {title: STRINGS.cards.ch1End});
    showTitleCard(ch1, {duration: CARD_MS}).done.then(function nextCard() {
      const ch2 = careerChapterCardData('ch2', {title: STRINGS.cards.ch2Bridge});
      showTitleCard(ch2, {duration: CARD_MS}).done.then(function leave() {
        finishDirector();
        if (navigate) navigate(globalThis.location?.href || '');
      });
    });
  }
  function end() {
    ended = true;
    look.release();
    report.outcome = view.outcome;
    radio.classList.remove('speaking');
    queue = [];
    voice.stop?.();
    if (missionId === 'c1_signoff_exam') showClosingCards();
    else finishDirector();
  }
  function begin(s) {
    clock = 0;
    lastFrameAt = null;
    director = createChapter1Director(missionId, spots());
    applyView(director.step(0, telemetry(s)), telemetry(s));
  }
  function update(s, w) {
    if (w) world = w;
    else if (getWorld) world = getWorld() || world;
    state = s;
    if (ended) return;
    if (!director) begin(s);
  }
  function shot() {
    if (!camera || !rovG || view?.beat !== 'establish') return;
    const time = Math.max(0, now() - TIMING.black);
    establishingShot(camera, rovG, easeInOut(time / TIMING.establish));
  }
  function frame(dt = 0) {
    if (!director || ended) return;
    const wall = performance.now() / 1000;
    const since = lastFrameAt === null ? dt : wall - lastFrameAt;
    lastFrameAt = wall;
    clock += Math.max(0, Math.min(CLOCK_STEP_MAX_S, since));
    const t = telemetry(state);
    applyView(director.step(now(), t), t);
    if (ended) return;
    updateRadio(now());
    if (view?.reveal?.includes('tether')) renderTension(state);
    shot();
  }
  function controlsBlocked() {
    if (ended || cardsPending) return true;
    if (!view) return true;
    return !!view.cinematic || view.beat === 'report' || view.beat === 'fade';
  }
  const api = {
    update,
    frame,
    controlsBlocked,
    get active() {
      return !ended || cardsPending;
    },
  };
  activeChapter1 = api;
  return api;
}
