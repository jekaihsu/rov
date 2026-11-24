// Chapter 2 directed presentation: beat_stage + chapter2_model for the three aquaculture contracts.
// Cinematic look only during scripted beats; never writes fidelity or localStorage.
import {actionCaps, axisCaps} from '../play/onboarding.js';
import {deviceFamily} from '../input/glyphs.js';
import {installVoice} from '../audio/voice.js';
import {getLanguage} from '../i18n/index.js';
import {getFidelity} from '../fidelity.js';
import {showTitleCard} from '../brand/chapter_card.js';
import {showLicenceAward, licenceSerial} from '../brand/licence_award.js';
import {createBeatStage, establishingShot, presentStage} from './beat_stage.js';
import {createCinematicLook} from './cutscene_look.js';
import {CHAPTER2_CONTRACTS, createChapter2Director} from './chapter2_model.js';
import {STRINGS, locationFor, speakerFor} from './chapter2_copy.js';

const SCRIPT_BEATS = new Set(['black', 'establish', 'fade', 'ending', 'wrap', 'relief']);

function stickInput(input) {
  if (!input?.out) return 0;
  return Math.max(...Object.values(input.out).map((value) => Math.abs(Number(value) || 0)));
}

function billowFromWorld(world, pos) {
  const band = world?.scenario?.aquaculture?.chapter2?.billow;
  if (!band || !Array.isArray(pos)) return false;
  const center = band.center || [24, 0];
  const radius = Math.hypot(pos[0] - center[0], pos[1] - center[1]);
  const [r0, r1] = band.radius_m || [19, 22.8];
  if (radius < r0 || radius > r1) return false;
  const [d0, d1] = band.depth_m || [4, 14];
  if (pos[2] < d0 || pos[2] > d1) return false;
  const dn = pos[0] - center[0];
  const de = pos[1] - center[1];
  const deg = ((Math.atan2(de, dn) * 180 / Math.PI) + 360) % 360;
  let clock = deg / 30;
  if (clock < 0.5) clock = 12;
  const [c0, c1] = band.clock || [1.5, 4.5];
  return c0 <= clock && clock <= c1;
}

export function chapter2ControlsBlocked(state, career) {
  const id = career?.contract?.id;
  if (!CHAPTER2_CONTRACTS.includes(id)) return false;
  const beat = state?.__chapter2Beat;
  return SCRIPT_BEATS.has(beat);
}

/**
 * career: installCareerDive API (contract, snapshot, settled). Returns {update(state, world), active}.
 */
export function installChapter2({input, camera, rovG, setCam, music, career}) {
  const look = createCinematicLook();
  const voice = installVoice();
  let stage = null;
  let director = null;
  let contractId = null;
  let radioUntil = 0;
  let family = 'keyboard';
  let endingShown = false;
  let shotStart = 0;

  document.addEventListener('rov-input-device', function device(event) {
    family = deviceFamily(event.detail === 'touch' ? '' : event.detail);
  });

  function clear() {
    if (!stage) {
      director = null;
      contractId = null;
      return;
    }
    if (look.active) setCam('onboard');
    look.release();
    music?.cue?.(null);
    voice.stop?.();
    stage.body.classList.remove('cold-open', 'cold-open-cinematic');
    delete stage.body.dataset.coldReveal;
    delete stage.body.dataset.coldHint;
    stage.root.remove();
    stage.style.remove();
    stage = null;
    director = null;
    contractId = null;
    endingShown = false;
  }

  function say(line, now) {
    const text = STRINGS[line.id];
    if (!text || !stage) return;
    const words = line.params?.n != null ? text.replace('{n}', String(line.params.n)) : text;
    const speaker = speakerFor(line.id);
    stage.words.textContent = words;
    stage.speaker.textContent = speaker ? `${speaker}${STRINGS.sep}` : '';
    stage.radio.classList.add('speaking');
    radioUntil = now + 5.5 * getFidelity().get('radioDuration');
    Promise.resolve(voice.playLine({speaker, text: words, language: getLanguage()})).catch(function quiet() {});
  }

  function showEnding(state) {
    if (endingShown) return;
    endingShown = true;
    showTitleCard({
      id: 'ch2-continue',
      title: STRINGS.c23Continue,
      number: STRINGS.c23Schedule,
      client: STRINGS.stamp,
      sub: STRINGS.c23Ending,
      scenario: 'aquaculture_pen',
    });
    if (career?.contract?.exam) {
      const holder = state?.room?.players?.find((player) => player.vehicle_id === state.vehicle_id)?.name || 'R-1';
      showLicenceAward({
        grade: 'grade2',
        holderName: holder,
        issuedOn: new Date().toISOString(),
        serial: licenceSerial({createdAt: holder}),
        endorsement: 'aquaculture',
      });
    }
  }

  function ensure(id) {
    if (contractId === id && director && stage) return;
    clear();
    contractId = id;
    director = createChapter2Director(id);
    stage = createBeatStage('chapter2', locationFor(id), STRINGS.stamp);
    shotStart = performance.now() / 1000;
    endingShown = false;
  }

  function telemetry(state, world) {
    const snap = career?.snapshot?.() || {};
    const items = snap.items || [];
    const photos = items.filter((item) => item.kind === 'photo' && item.done).length;
    const reports = items.filter((item) => item.kind === 'report' && item.done).length;
    const vis = Number(state?.turbidity?.visibility_m);
    const hooks = state?.tether?.snags;
    const snagged = Array.isArray(hooks) ? hooks.length > 0 : !!state?.tether?.snagged_on?.length;
    const aqua = world?.scenario?.aquaculture || {};
    const windowS = aqua.escape?.window_s || aqua.chapter2?.escape?.window_s || 720;
    const windowLeft = Math.max(0, windowS - (Number(state?.t) || 0));
    const hole = aqua.escape?.truth?.pos || aqua.holes?.[0]?.pos;
    let nearHole = false;
    if (Array.isArray(hole) && Array.isArray(state?.pos)) {
      nearHole = Math.hypot(state.pos[0] - hole[0], state.pos[1] - hole[1], state.pos[2] - hole[2]) < 4;
    }
    return {
      photos,
      reports,
      complete: !!snap.complete,
      billow: billowFromWorld(world, state?.pos),
      snagged,
      tension: Number(state?.tether?.tension) || 0,
      visibility: Number.isFinite(vis) ? vis : Number(world?.scenario?.visibility_m) || 12,
      silted: Number.isFinite(vis) && vis < 2.5,
      nearHole,
      input: stickInput(input),
      holding: !!state?.operations?.arm?.held,
      windowLeft,
    };
  }

  function present(view, now) {
    presentStage(stage, {
      black: view.black,
      letterbox: view.letterbox,
      cinematic: view.cinematic,
      location: !!view.location,
      reveal: view.reveal,
    });
    if (look.active !== !!view.cinematic) setCam(view.cinematic ? 'cine' : 'onboard');
    look.set(!!view.cinematic);
    if (view.cinematic) {
      const k = Math.min(1, (performance.now() / 1000 - shotStart) / 7.5);
      establishingShot(camera, rovG, k);
    }
    for (const line of view.said || []) say(line, now);
    stage.radio.classList.toggle('speaking', now < radioUntil && !SCRIPT_BEATS.has(view.beat));
    const hint = view.hint;
    stage.body.dataset.coldHint = hint || '';
    stage.hint.classList.toggle('visible', !!hint && !view.cinematic);
    if (hint) {
      const hud = input.hudState();
      const controls = {bindings: hud.bindings, rows: hud.keyRows, operationMode: null};
      const axis = hint === 'move' || hint === 'slow' ? 'surge' : hint === 'hold' ? 'heave' : null;
      const caps = axis ? axisCaps(axis, family, controls)
        : hint === 'photo' ? actionCaps('photo', family, controls) : '';
      const label = STRINGS.hints[hint] || hint;
      const html = `${caps} ${label}`.trim();
      if (stage.hint.innerHTML !== html) stage.hint.innerHTML = html;
    }
  }

  function update(state, world) {
    const id = career?.contract?.id;
    if (!CHAPTER2_CONTRACTS.includes(id) || career?.settled) {
      if (state) delete state.__chapter2Beat;
      return clear();
    }
    if (!state || world?.scenario?.key && !String(world.scenario.key).startsWith('aquaculture_pen')) {
      return clear();
    }
    ensure(id);
    const now = Number(state.t) || performance.now() / 1000;
    const view = director.step(now, telemetry(state, world));
    state.__chapter2Beat = view.beat;
    present(view, now);
    if (view.beat === 'ending' || (view.beat === 'done' && id === 'c2_escape_event' && view.outcome.complete)) {
      showEnding(state);
    }
    if (view.beat === 'establish') music?.cue?.('cinematic');
    if (!view.cinematic && view.beat !== 'black') music?.cue?.(null);
  }

  return {
    update,
    clear,
    get active() {
      return !!director;
    },
  };
}
