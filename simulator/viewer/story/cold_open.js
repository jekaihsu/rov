// Cold open presentation (docs/design/cold-open/README.md): the screen side of the new-game flash-forward. The
// director (cold_open_model.js) decides the beat from telemetry; this module draws it: the black opening, the
// establishing shot round the vehicle, a documentary location super, deck-radio subtitles with the crew's voices,
// one hint at a time with the player's own controls, the HUD parts as they become relevant, the photo stamp, the
// tension read-out, and the closing 三個月前 title card before the prologue starts.
//
// It runs only on a game URL made by cold_open_flow.js (?coldOpen=1|replay, campaign chapter cold_open). It never
// changes the vehicle's physics or controls: it puts the vehicle in its mid-job state from the first frame
// (thrusters unlocked, depth hold on, lamps on: the dive is already under way) and leaves the flying to the player;
// the simulation keeps running under the cutscene so the fish keep moving. Guidance stays on the radio, so nothing
// here exceeds the real vehicle while the player flies. The one exception, approved by the owner, is the look of
// the scripted beats before the handover (cold_open_presentation.js): sun shafts and cutscene music, dropped the
// moment the player takes control.
//
//   const coldOpen = installColdOpen({input, setCam, camera, rovG, hidden: [objG, guide], music});
//   coldOpen.update(state, world);   // every server state
//   coldOpen.frame(dt);              // every frame, after the camera rig and before the render
import {createBeatStage, createTensionMeter, element, establishingShot, presentStage} from './beat_stage.js';
import { TIMING, createColdOpenDirector } from './cold_open_model.js';
import { CHAPTER, FLAG, followUpUrl, markColdOpenSeen } from './cold_open_flow.js';
import { CINEMATIC_MUSIC, createCinematicLook, isScriptedBeat } from './cutscene_look.js';
import { beautifyEnabled } from '../fx/beautify.js';
import { getFidelity } from '../fidelity.js';
import { actionCaps, axisCaps } from '../play/onboarding.js';
import { deviceFamily } from '../input/glyphs.js';
import { axisChannel, bindingRow } from '../input/bindings.js';
import { setIntroSkipLabel } from '../play/intro_skip.js';
import { showTitleCard } from '../brand/chapter_card.js';
import { chapterCardData } from '../brand/chapters.js';
import { installVoice } from '../audio/voice.js';
import { getLanguage, localize } from '../i18n/index.js';

const STRINGS = localize('story.cold_open', {
  speakers: {
    supervisor: '林岑 · 向潮指揮',
    tender: '周楷 · 纜手',
    senior: '馬力 · R-2',
  },
  lines: {
    open: 'R-1，這裡是指揮。平潮還剩二十分鐘。',
    crew: '纜放好了，線還夠。慢慢飛。',
    task: '先拍 C 腿陽極，就在你正前方。',
    nudgeMove: 'R-1，往前推一點。陽極在你正前方。',
    nudgePhoto: '靠近到兩米左右，拍一張就好。',
    praise: '乾淨。陽極消耗看得很清楚。',
    praiseFar: '拍到了。下次再靠近一點。',
    skipPhoto: '照片先放著。轉去 B 腿。',
    toLegB: '好。沿西面往北去 B 腿，保持深度。',
    nudgeLegB: 'R-1，B 腿在你北邊。轉過去，往前。',
    tension: '張力 {n}！卡住了！',
    stop: '先停！退路想好了嗎？',
    backOut: '別拉。照原路退，往南，退過陽極。',
    dontPull: '還在拉！{n} 牛頓，別硬拉！',
    free: '……鬆了。線是自由的。',
    slipped: '……自己滑開了。線鬆了。',
    lucky: '這次是運氣。下次先想好退路。記住這個感覺。',
    remember: '很好。記住這個感覺。',
    stuck: '停住。我們放纜，等平潮再解。',
    snapped: '……線斷了。張力歸零。',
    lost: '人沒事就好。機子有信標，撈得回來。記住這個感覺。',
    noSnag: '好，先到這裡。B 腿下一潛再補。',
  },
  hints: {
    move: '前進',
    photo: '拍照',
    turn: '轉向',
    forward: '前進',
    release: '放開推桿',
    reverse: '後退',
    unlock: '解鎖推進器',
  },
  location: ['離岸風場 · 導管架 C 腿', '水深 12 m · 平潮'],
  stamp: '照片已記錄 · C 腿陽極',
  tension: '纜線張力',
  skip: '跳過開場',
  card: {title: '三個月前', chapterTitle: '序章｜三個月前'},
});
// Who says each line (bible.md §3: 林岑 supervisor, 周楷 tether hand, 馬力 senior pilot).
const SPEAKER_OF = {
  open: 'supervisor', crew: 'tender', task: 'supervisor', nudgeMove: 'supervisor', nudgePhoto: 'senior',
  praise: 'senior', praiseFar: 'senior', skipPhoto: 'supervisor', toLegB: 'supervisor', nudgeLegB: 'supervisor',
  tension: 'tender', stop: 'supervisor', backOut: 'supervisor', dontPull: 'tender', free: 'tender',
  remember: 'supervisor', slipped: 'tender', lucky: 'supervisor', stuck: 'supervisor', noSnag: 'supervisor',
  snapped: 'tender', lost: 'supervisor',
};
// Fallback spots (NED) of qysim/cold_open.py when the world message carries no objectives.
const FALLBACK_SPOTS = {anode: [-6.93, -6.93], start: [-12.0, -9.0]};
const CARD_MS = 4800;
// Longest step of the cold open's clock per rendered frame (s). The dive runs in real time on the server: the
// vehicle drifts with the slack-water current through the opening, so a page drawing a frame a second must not
// stretch those fifteen seconds into minutes. A page that stalls for longer still does not skip beats.
const CLOCK_STEP_MAX_S = 1.0;
const CUT_SETTLE_S = 0.6;

function isCjk(language) {
  return /^(zh|ja)/.test(language || '');
}

// How long a subtitle stays up: reading time for its length, never shorter than a radio call takes.
export function lineSeconds(text, language) {
  const length = String(text || '').length;
  const perChar = isCjk(language) ? 0.13 : 0.05;
  return Math.min(6.5, Math.max(2.6, 1.6 + length * perChar));
}

export function lineText(id, params = {}) {
  let text = STRINGS.lines[id] || '';
  for (const [key, value] of Object.entries(params)) text = text.replace(`{${key}}`, String(value));
  return text;
}

function easeInOut(x) {
  const k = Math.max(0, Math.min(1, x));
  return k * k * (3 - 2 * k);
}

function wantedMode(params) {
  return params.get(FLAG) === 'replay' ? 'replay' : params.get(FLAG) ? 'first' : '';
}

/**
 * Options: input (installInput result), setCam(mode), camera, rovG, hidden (objects kept hidden while the
 * cold open runs: objective markers, guide line, tether wrap rings and contact dots), plain (called every frame
 * to clear the viewer's tether-contact tint on the structure: the scene is the bare camera view, and the crew's
 * radio is the only word on where the tether lies), music (installMusic result), readOnly, params, navigate.
 */
export function installColdOpen({
  input, setCam, camera, rovG, hidden = [], plain = null, music = null, readOnly = false,
  params = new URLSearchParams(globalThis.location?.search || ''),
  navigate = function go(href) {
    location.assign(href);
  },
} = {}) {
  const mode = readOnly ? '' : wantedMode(params);
  const inert = {update() {}, frame() {}, get active() {
    return false;
  }};
  if (!mode) return inert;
  const voice = installVoice();
  const stage = createBeatStage('coldOpen', STRINGS.location, STRINGS.stamp);
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
  let lampsSet = false;
  let unlockedOnce = false;
  let cineMode = false;
  let cutAt = -Infinity;
  let hintSignature = '';
  let lastCue = '';
  const look = createCinematicLook();
  const log = [];
  const report = {beats: [], lines: log, hints: [], outcome: null, mode};
  window.__coldOpen = {
    controls: () => ({surge: axisControl('surge'), yaw: axisControl('yaw'), heave: axisControl('heave'),
      sway: axisControl('sway'), photo: actionControl('photo')}),
    debug: () => ({beat: view?.beat || 'waiting', reveal: view?.reveal || [], hint: view?.hint || null,
      outcome: view?.outcome || null, lines: log.map(function id(entry) {
        return entry.id;
      }), look: {cinematic: look.active, beautify: beautifyEnabled(), fidelity: getFidelity().snapshot()}}),
    report,
    skip: () => skip('api'),
  };

  const skipButton = document.getElementById('skipIntro');
  const skippable = mode === 'replay';
  if (skipButton && skippable) {
    new MutationObserver(function skipped() {
      if (skipButton.dataset.skipped && !ended && director) skip(skipButton.dataset.skipped);
    }).observe(skipButton, {attributes: true, attributeFilter: ['data-skipped']});
  }
  // Captured before the flight keys, so the Esc that skips does not also open the pause menu.
  addEventListener('keydown', function escape(event) {
    if (!skippable || ended || event.code !== 'Escape' || !director) return;
    event.preventDefault();
    event.stopImmediatePropagation();
    skip('key');
  }, true);
  document.addEventListener('rov-key-rows', function invalidateHint() {
    hintSignature = '';
  });
  document.addEventListener('rov-input-device', function deviceChanged(event) {
    family = event.detail && event.detail !== 'touch' ? deviceFamily(event.detail) : 'keyboard';
    hintSignature = '';
  });

  // The cold open's own clock advances with rendered frames, so a stalled or captured page keeps the beats in
  // step with what was actually shown; each frame adds the real time since the last one, up to CLOCK_STEP_MAX_S.
  function now() {
    return clock;
  }
  function controls() {
    const hud = input?.hudState?.() || {};
    return {bindings: hud.bindings, rows: hud.keyRows,
      operationMode: state?.operation_mode || hud.operationMode || 'ROV_USA'};
  }
  // Key codes and pad source of a pilot axis (positive direction first) and of an action, for the browser checks.
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
    const anode = objectives.find(function inspect(item) {
      return item.kind === 'inspect';
    })?.point;
    return {anode: anode ? anode.slice(0, 2) : FALLBACK_SPOTS.anode, start: FALLBACK_SPOTS.start};
  }
  function telemetry(s) {
    const tether = s?.tether || {};
    // Held hooks only: `snagged_on` lists every obstacle the tether touches, which is not a snag. Hosts older
    // than the `snags` list fall back to it.
    const snags = Array.isArray(tether.snags) ? tether.snags.length : (tether.snagged_on || []).length;
    const vel = s?.vel || [0, 0, 0];
    const sticks = Object.values(input?.out || {}).reduce(function largest(most, value) {
      return Math.max(most, Math.abs(Number(value) || 0));
    }, 0);
    return {
      input: sticks,
      photos: s?.photos || 0,
      snagged: snags > 0,
      broken: !!tether.broken,
      tension: tether.tension_rov || 0,
      pos: s?.pos,
      heading: s?.euler?.[2],
      speed: Math.hypot(vel[0] || 0, vel[1] || 0, vel[2] || 0),
    };
  }
  function enqueue(entries) {
    for (const entry of entries) {
      const text = lineText(entry.id, entry.params);
      queue.push({id: entry.id, speaker: STRINGS.speakers[SPEAKER_OF[entry.id]] || '', text});
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
    speaking = {...next, until: time + lineSeconds(next.text, language) * (getFidelity().get("radioDuration") ?? 1)};
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
    if (id === 'turn') return [[axisCaps('yaw', family, keys), STRINGS.hints.turn]];
    if (id === 'forward') return [[axisCaps('surge', family, keys), STRINGS.hints.forward]];
    if (id === 'reverse') return [[axisCaps('surge', family, keys), STRINGS.hints.reverse]];
    if (id === 'release') return [['', STRINGS.hints.release]];
    if (id === 'unlock') return [[actionCaps('lock', family, keys), STRINGS.hints.unlock]];
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
  // A vehicle locked while the player flies (their own lock key, or the link failsafe after a stalled page) can
  // not move; the one hint then says how to unlock, with the player's own control.
  function relockHint(next) {
    const flying = ['approach', 'payoff', 'transit', 'incident'].includes(next.beat);
    return flying && unlockedOnce && state?.locked ? 'unlock' : null;
  }
  const tensionMeter = createTensionMeter(tension, STRINGS.tension, TIMING.pullTension);
  // Mid-job state at the handover; asserted until the server echoes it once, then left to the player.
  function midJob(s) {
    const rc = input?.rc;
    if (!rc || !s) return;
    if (!lampsSet) {
      if ((s.rc?.right_switch || 0) >= 2) lampsSet = true;
      else rc.right_switch = 2;
    }
    // Until the handover the cutscene owns the controls (a failsafe relock is undone); afterwards the player does.
    const cutscene = !view || ['black', 'establish', 'handover'].includes(view.beat);
    if (unlockedOnce && !cutscene) return;
    if (!s.locked && s.keep_depth) {
      unlockedOnce = true;
      return;
    }
    rc.keep_depth = 1;
    // After a scenario load the server latches the controls until it has seen a locked packet (server.py), the
    // same rule a player's unlock key follows; only then is the unlock sent.
    rc.rc_lock = s.input_latched ? 1 : 0;
  }
  function cue(name) {
    if (name === lastCue) return;
    lastCue = name;
    music?.cue?.(name);
  }
  // A short dip to black on the cut from the establishing shot to the onboard camera, so the rig's blend between the
  // two poses (through the lamp beams) is never seen.
  function cutDip() {
    const since = now() - cutAt;
    if (since < 0 || since > CUT_SETTLE_S) return 0;
    return since < CUT_SETTLE_S / 2 ? 1 : 2 - 2 * since / CUT_SETTLE_S;
  }
  function applyView(next) {
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
      location: next.beat === 'establish' && now() > TIMING.black + 1.2,
      reveal: next.reveal,
    });
    stamp.classList.toggle('visible', next.beat === 'payoff');
    tension.classList.toggle('visible', next.reveal.includes('tether') && !next.ended);
    renderHint(next.ended ? null : relockHint(next) || next.hint);
    // Scripted beats only: the beautified picture and the cutscene music. From the handover on, and after an end
    // or a skip, the picture and the music are the player's own fidelity settings again.
    look.set(isScriptedBeat(next));
    if (isScriptedBeat(next)) cue(CINEMATIC_MUSIC.scripted);
    else if (next.outcome?.released && ['relief', 'fade'].includes(next.beat)) cue('relief');
    else if (next.ended) cue(CINEMATIC_MUSIC.closing);
    else cue(null);
    if (skipButton && skippable) skipButton.hidden = next.ended;
    if (next.ended && !ended) end();
  }
  function skip(source) {
    if (!director || ended) return;
    report.skipped = source;
    queue = [];
    applyView(director.skip(now()));
  }
  function end() {
    ended = true;
    look.release();
    report.outcome = view.outcome;
    setIntroSkipLabel(null);
    markColdOpenSeen();
    radio.classList.remove('speaking');
    queue = [];
    voice.stop?.();
    const data = chapterCardData({id: 'prologue', title: STRINGS.card.chapterTitle, scenario: 'tutorial_pool'});
    data.id = 'cold_open_flashback';
    data.title = STRINGS.card.title;
    const card = showTitleCard(data, {duration: CARD_MS});
    card.done.then(function leave() {
      director.finish(now());
      report.done = true;
      navigate(followUpUrl(location.href));
    });
  }
  function begin(s) {
    clock = 0;
    lastFrameAt = null;
    director = createColdOpenDirector(spots());
    if (skippable) {
      setIntroSkipLabel(STRINGS.skip);
      if (skipButton) skipButton.hidden = false;
    }
    applyView(director.step(0, telemetry(s)));
  }
  function update(s, w) {
    if (w) world = w;
    state = s;
    if (ended) return;
    if (!director) {
      if (s?.campaign?.chapter !== CHAPTER || s.campaign.status !== 'active') return;
      begin(s);
    }
    midJob(s);
  }
  // Cinematic camera: an arc round the vehicle from in front (its lamps towards the lens, the leg behind the
  // camera) to over its shoulder looking at the leg, where the onboard camera takes over.
  function shot() {
    if (!camera || !rovG || view?.beat !== 'establish') return;
    const time = Math.max(0, now() - TIMING.black);
    establishingShot(camera, rovG, easeInOut(time / TIMING.establish));
  }
  function frame(dt = 0) {
    for (const object of hidden) {
      if (object) object.visible = false;
    }
    plain?.();
    if (!director || ended) return;
    const wall = performance.now() / 1000;
    const since = lastFrameAt === null ? dt : wall - lastFrameAt;
    lastFrameAt = wall;
    clock += Math.max(0, Math.min(CLOCK_STEP_MAX_S, since));
    applyView(director.step(now(), telemetry(state)));
    if (ended) return;
    updateRadio(now());
    if (view?.reveal?.includes('tether')) tensionMeter(now(), state?.tether?.tension_rov || 0);
    shot();
  }
  return {
    update,
    frame,
    get active() {
      return !ended;
    },
  };
}
