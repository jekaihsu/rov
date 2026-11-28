// Present the annual wind-farm watch using host-verified beats and tether telemetry.
import {installPrologue} from './prologue.js';
import {TIMING} from './cold_open_model.js';
import {beatDecision, idleReminder} from './beat_director.js';
import {createBeatStage, createTensionMeter, establishingShot, presentStage} from './beat_stage.js';
import {createCinematicLook} from './cutscene_look.js';
import {STRINGS as WIND} from './wind_copy.js';
import {STRINGS} from './prologue_copy.js';
import {actionCaps, axisCaps} from '../play/onboarding.js';
import {deviceFamily} from '../input/glyphs.js';
import {installVoice} from '../audio/voice.js';
import {getLanguage} from '../i18n/index.js';
import {getFidelity} from '../fidelity.js';
import {licenceSerial, showLicenceAward} from '../brand/licence_award.js';
import {showTitleCard} from '../brand/chapter_card.js';
import {chapterCardData} from '../brand/chapters.js';

function installWindWatch({input, send, camera, rovG, setCam, music, hidden, plain}) {
  const look = createCinematicLook();
  const voice = installVoice();
  let stage;
  let visibility;
  let tensionMeter;
  function copy(key) {
    return WIND[key] || STRINGS[key];
  }
  let beat;
  let entered;
  let reminded;
  let lastInput;
  let card;
  let stampedUntil = 0;
  let shotStart = 0;
  let retryAt = 0;
  let family = 'keyboard';
  let radioUntil = 0;
  document.addEventListener('rov-input-device', function device(event) {
    family = deviceFamily(event.detail === 'touch' ? '' : event.detail);
  });

  function say(key, now, count = 0) {
    const text = copy(key);
    if (!text) return;
    const words = text.replace('{n}', count);
    const speaker = copy(key === 'again' ? 'lin' : beat.speaker);
    stage.words.textContent = words;
    stage.speaker.textContent = speaker;
    stage.radio.classList.add('speaking');
    radioUntil = now + 6 * getFidelity().get('radioDuration');
    Promise.resolve(voice.playLine({speaker, text: words, language: getLanguage()})).catch(function quiet() {});
  }

  function enter(node, s, load) {
    beat = node;
    entered = s.campaign.beat_since;
    lastInput = s.t;
    shotStart = performance.now() / 1000;
    reminded = false;
    retryAt = 0;

    if (['logged', 'evidence', 'north'].includes(beat.id) && s.mission?.targets?.[0]?.completed) {
      stage.stamp.textContent = WIND.recorded;
      stampedUntil = s.t + 2.6;
    }
    stage.root.dataset.beat = beat.id;
    presentStage(stage, {
      black: beat.black || beat.card ? 1 : 0,
      letterbox: !!beat.cinematic,
      cinematic: !!beat.cinematic || !!beat.card,
      location: !!beat.location,
      reveal: beat.hud,
    });
    if (look.active !== !!beat.cinematic) setCam(beat.cinematic ? 'cine' : 'onboard');
    look.set(!!beat.cinematic);
    music.cue(beat.cue || null);
    if (!beat.card) say(beat.radio, s.t, load);
    if (beat.card === 'grade1') {
      const holder = s.room.players.find(player => player.vehicle_id === s.vehicle_id)?.name || 'R-1';
      card = showLicenceAward({
        grade: 'grade1',
        holderName: holder,
        issuedOn: new Date().toISOString(),
        serial: licenceSerial({createdAt: holder}),
      });
    }
    if (beat.card === 'end') {
      const title = chapterCardData({id: s.campaign.chapter, title: WIND.end});
      card = showTitleCard({...title, sub: WIND.sub}, {duration: 6000});
    }
  }

  function clear() {
    if (!stage) return;
    if (look.active) setCam('onboard');
    look.release();
    music.cue(null);
    voice.stop();
    card?.dismiss();
    card = null;
    stage.body.classList.remove('cold-open', 'cold-open-cinematic');
    delete stage.body.dataset.coldReveal;
    delete stage.body.dataset.coldHint;
    hidden.forEach((object, index) => { object.visible = visibility[index]; });
    stage.root.remove();
    stage.style.remove();
    stage = null;
    beat = null;
    stampedUntil = 0;
  }

  function update(s) {
    const c = s.campaign;
    if (!c?.directed || c.status !== 'active') return clear();
    if (stage && stage.root.dataset.chapter !== c.chapter) clear();
    if (!stage) {
      stage = createBeatStage('windWatch', [WIND[c.chapter], WIND.sub], '');
      stage.root.dataset.chapter = c.chapter;
      visibility = hidden.map(object => object.visible);
      tensionMeter = createTensionMeter(stage.tension, WIND.tension, TIMING.pullTension);
    }
    const load = tensionMeter(s.t, s.tether.tension_rov);
    if (beat?.id !== c.node.id || s.t < entered) enter(c.node, s, load);
    const presented = performance.now() / 1000 - shotStart;
    const age = beat.cinematic || beat.card ? Math.min(presented, s.t - entered) : s.t - entered;
    const host = s.room.players.find(player => player.id === s.room.host_id)?.vehicle_id === s.vehicle_id;

    let hint = beat.hint;
    let control = hint;
    if (beat.location && host) {
      input.rc.right_switch = 1;
      input.rc.keep_depth = 1;
      input.rc.rc_lock = s.input_latched ? 1 : 0;
    }
    if (hint === 'align') {
      control = 'surge';
      if (s.mission?.targets?.[0]?.ready) hint = control = 'photo';
    }
    if (hint === 'turnNorth') control = 'yaw';
    if (hint === 'retreat') control = 'surge';
    const tension = ['catch', 'reverse'].includes(beat.id);
    stage.tension.classList.toggle('visible', tension);
    if (beat.hint && s.locked) hint = control = 'lock';
    stage.body.dataset.coldHint = hint || '';
    stage.hint.classList.toggle('visible', !!hint);
    if (hint) {
      const hud = input.hudState();
      const controls = {bindings: hud.bindings, rows: hud.keyRows, operationMode: s.operation_mode};
      const caps = ['surge', 'heave', 'yaw'].includes(control) ? axisCaps(control, family, controls)
        : hint === 'neutral' ? '' : actionCaps(control, family, controls);
      const html = caps + ' ' + copy(hint);
      if (stage.hint.innerHTML !== html) stage.hint.innerHTML = html;
    }
    if (Object.values(input.out).some(value => Math.abs(value) > 0.15)) lastInput = s.t;
    if (idleReminder(beat.reminder, beat.idle, s.t - lastInput, reminded)) {
      reminded = true;
      say(beat.reminder, s.t);
    }
    stage.stamp.classList.toggle('visible', s.t < stampedUntil);
    stage.radio.classList.toggle('speaking', s.t < radioUntil && !beat.card);
    const next = beatDecision(beat, age, s);
    if (next && host && s.t >= retryAt) {
      retryAt = s.t + 0.4;
      send({type: 'operation', action: 'campaign_advance', beat: beat.id, next});
    }
  }

  function frame() {
    if (!stage) return;
    for (const object of hidden) object.visible = false;
    plain();
    if (!beat?.location) return;
    const progress = Math.min(1, (performance.now() / 1000 - shotStart) / beat.limit);
    establishingShot(camera, rovG, progress);
    if (stage.root.dataset.chapter === 'wind_shadow') {
      // Keep the camera and the vehicle inside the same short visibility range.
      camera.position.lerp(rovG.position, .5);
      camera.lookAt(rovG.position);
    }
  }
  return {update, frame};
}

// Both stages own the same HUD and camera. Release the outgoing stage before entering the next.
export function installDirectedWatches(options) {
  const training = installPrologue(options);
  const wind = installWindWatch(options);
  let active = training;
  function update(state) {
    const next = ['wind_set', 'wind_shadow', 'wind_return'].includes(state.campaign?.chapter) ? wind : training;
    if (next !== active) active.update({});
    active = next;
    active.update(state);
  }
  return {update, frame: () => active.frame()};
}
