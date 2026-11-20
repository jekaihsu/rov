// Stage the training watch against the host's active beat and live vehicle telemetry.
import * as THREE from 'three';
import {beatDecision, idleReminder} from './beat_director.js';
import {createBeatStage, establishingShot, presentStage} from './beat_stage.js';
import {createCinematicLook} from './cutscene_look.js';
import {STRINGS} from './prologue_copy.js';
import {actionCaps, axisCaps} from '../play/onboarding.js';
import {deviceFamily} from '../input/glyphs.js';
import {installVoice} from '../audio/voice.js';
import {getLanguage} from '../i18n/index.js';
import {licenceSerial, showLicenceAward} from '../brand/licence_award.js';
import {showTitleCard} from '../brand/chapter_card.js';
import {chapterCardData} from '../brand/chapters.js';

function wallPlate(id, [north, east, depth]) {
  const canvas = document.createElement('canvas');
  canvas.width = canvas.height = 256;
  const ctx = canvas.getContext('2d');
  ctx.fillStyle = '#e3dec6';
  ctx.fillRect(0, 0, 256, 256);
  ctx.fillStyle = '#163540';
  ctx.fillRect(8, 8, 240, 240);
  ctx.fillStyle = '#f3eedb';
  ctx.font = 'bold 164px sans-serif';
  ctx.textAlign = 'center';
  ctx.fillText(id, 128, 186);
  for (let x = 18; x < 240; x += 20) ctx.fillRect(x, 211, 10, 17);
  const map = new THREE.CanvasTexture(canvas);
  map.colorSpace = THREE.SRGBColorSpace;
  const plate = new THREE.Mesh(new THREE.PlaneGeometry(1.5, 1.5), new THREE.MeshBasicMaterial({map}));
  plate.position.set(-east, -depth, north);
  plate.lookAt(0, -depth, 0);
  return plate;
}

export function prologueControlsBlocked(state) {
  const campaign = state?.campaign;
  return campaign?.directed && campaign.status === 'active' && (campaign.node?.cinematic || campaign.node?.card);
}

export function installPrologue({input, send, camera, scene, rovG, setCam, music}) {
  const look = createCinematicLook();
  const voice = installVoice();
  let stage;
  let beat;
  let entered;
  let reminded;
  let lastInput;
  let card;
  let lastPlate;
  let lastCount = 0;
  let stampedUntil = 0;
  let shotStart = 0;
  let retryAt = 0;
  let nextLineAt = null;
  let family = 'keyboard';
  let plates = [];
  let radioUntil = 0;
  document.addEventListener('rov-input-device', function device(event) {
    family = deviceFamily(event.detail === 'touch' ? '' : event.detail);
  });

  function say(key, now, count = 0) {
    const text = STRINGS[key];
    if (!text) return;
    const words = text.replace('{n}', count);
    const speaker = STRINGS[beat.speaker];
    stage.words.textContent = words;
    stage.speaker.textContent = speaker;
    stage.radio.classList.add('speaking');
    radioUntil = now + 6;
    Promise.resolve(voice.playLine({speaker, text: words, language: getLanguage()})).catch(function quiet() {});
  }

  function enter(node, s) {
    beat = node;
    entered = s.campaign.beat_since;
    lastInput = s.t;
    shotStart = performance.now() / 1000;
    reminded = false;
    retryAt = 0;

    if (lastPlate && s.campaign.accepted > lastCount) {
      stage.stamp.textContent = lastPlate + '  ✓';
      stampedUntil = s.t + 2.6;
    }
    lastCount = s.campaign.accepted;
    lastPlate = beat.target ? beat.id : null;
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
    nextLineAt = null;
    if (s.campaign.missed && !beat.card) {
      say('miss', s.t);
      nextLineAt = s.t + 2.6;
    } else if (!beat.card) say(beat.radio, s.t, s.campaign.accepted);
    if (beat.card === 'licence') {
      const holder = s.room.players.find(player => player.vehicle_id === s.vehicle_id)?.name || 'R-1';
      card = showLicenceAward({
        grade: 'trainee',
        holderName: holder,
        issuedOn: new Date().toISOString(),
        serial: licenceSerial({createdAt: holder}),
      });
    }
    if (beat.card === 'harbor') card = showTitleCard(chapterCardData({id: 'harbor', title: STRINGS.harbor}));
  }

  function clear() {
    if (!stage) return;
    if (look.active) setCam('onboard');
    look.release();
    music.cue(null);
    voice.stop();
    card?.dismiss();
    card = null;
    for (const plate of plates) {
      scene.remove(plate);
      plate.geometry.dispose();
      plate.material.map.dispose();
      plate.material.dispose();
    }
    stage.body.classList.remove('cold-open', 'cold-open-cinematic');
    delete stage.body.dataset.coldReveal;
    delete stage.body.dataset.coldHint;
    stage.root.remove();
    stage.style.remove();
    stage = null;
    beat = null;
    lastPlate = null;
    stampedUntil = 0;
  }

  function update(s) {
    const c = s.campaign;
    if (!c?.directed || c.status !== 'active') return clear();
    if (!stage) {
      stage = createBeatStage('prologue', [STRINGS.site, STRINGS.sub], '');
      plates = c.plates.map(({id, target}) => wallPlate(id, target));
      scene.add(...plates);
    }
    if (beat?.id !== c.node.id || s.t < entered) enter(c.node, s);
    const presented = performance.now() / 1000 - shotStart;
    const age = beat.cinematic || beat.card ? Math.min(presented, s.t - entered) : s.t - entered;
    if (nextLineAt !== null && s.t >= nextLineAt) {
      say(beat.radio, s.t, c.accepted);
      nextLineAt = null;
    }
    const host = s.room.players.find(player => player.id === s.room.host_id)?.vehicle_id === s.vehicle_id;
    const flying = !!beat.hint;
    let hint = beat.hint;
    let control = hint;
    if (beat.target) {
      const [n, e, d] = beat.target.map((coord, i) => coord - s.pos[i]);
      const bearing = Math.atan2(e, n) * 180 / Math.PI;
      const angle = Math.abs((bearing - s.euler[2] + 540) % 360 - 180);
      const horizontal = Math.hypot(n, e);
      const [north, east] = beat.target;
      const standOff = (n * north + e * east) / Math.hypot(north, east);
      if (angle >= 20) hint = control = 'yaw';
      else if (standOff < 2) {
        hint = 'back';
        control = 'surge';
      } else if (Math.abs(d) >= horizontal * .3) {
        hint = 'level';
        control = 'heave';
      } else if (Math.hypot(n, e, d) >= 8) {
        hint = 'range';
        control = 'surge';
      }
    }
    if (flying && s.locked) hint = control = 'lock';
    stage.body.dataset.coldHint = hint || '';
    stage.hint.classList.toggle('visible', !!hint);
    if (hint) {
      const hud = input.hudState();
      const controls = {bindings: hud.bindings, rows: hud.keyRows, operationMode: s.operation_mode};
      const caps = ['surge', 'heave', 'yaw'].includes(control) ? axisCaps(control, family, controls)
        : hint === 'neutral' ? '' : actionCaps(control, family, controls);
      const html = caps + ' ' + STRINGS[hint];
      if (stage.hint.innerHTML !== html) stage.hint.innerHTML = html;
    }
    if (Object.values(input.out).some(value => Math.abs(value) > 0.15)) lastInput = s.t;
    if (idleReminder(beat.reminder, beat.idle, s.t - lastInput, reminded)) {
      reminded = true;
      say(beat.reminder, s.t);
    }
    stage.stamp.classList.toggle('visible', s.t < stampedUntil);
    stage.radio.classList.toggle('speaking', s.t < radioUntil && !beat.card);
    const next = beatDecision(beat, age, {...s, drift: c.drift, framedPhoto: c.framedPhoto});
    if (next && host && s.t >= retryAt) {
      retryAt = s.t + 0.4;
      send({type: 'operation', action: 'campaign_advance', beat: beat.id, next});
    }
  }

  function frame() {
    if (!beat?.location) return;
    const progress = Math.min(1, (performance.now() / 1000 - shotStart) / beat.limit);
    establishingShot(camera, rovG, progress);
  }
  return {update, frame};
}
