// Flight-only presentation consumes telemetry without writing camera pose, RC or simulation state.
import {getFidelity} from '../fidelity.js';
import {localize} from '../i18n/index.js';
import {advanceReactions} from './crew_reactions.js';
import './feel_settings.js';

const STRINGS = localize('story.flight_feedback', {
  "impact": "向潮－指揮，機身碰到了。先穩住。",
  "snag": "向潮－纜手，纜繞上了。沿原路退。",
  "tension": "向潮－纜手，線繃緊了。先停推。",
  "battery": "向潮－甲板，電量偏低。準備回收。",
  "near": "向潮－指揮，目標在近處。慢慢靠。",
  "idle": "向潮－纜手，這頭纜理好了。你那邊呢？",
  "harbor": "向潮－指揮，巡樁時留意纜在哪一側。",
  "pen": "向潮－指揮，巡網時留一段退距。",
  "openWater": "向潮－指揮，下一個檢查點看得到嗎？",
  "check": "向潮－甲板，記錄還在走。你那邊清楚嗎？"
});

const ROLE = {impact: 'supervisor', snag: 'tender', tension: 'tender', battery: 'deck', near: 'supervisor'};
const BANDS = [
  {opacity: 0.35, clipPath: 'inset(23% 0 74%)'},
  {opacity: 0.18, clipPath: 'inset(70% 0 23%)'},
  {opacity: 0, clipPath: 'inset(38% 0 60%)'}
];
const SHAKE = ['translate(2px,-2px) scale(1.012)', 'translate(-3px,1px) scale(1.012)', 'none'];

export function installFlightFeedback({canvas, radio, onboard}) {
  const prefs = getFidelity();
  const noise = document.createElement('div');
  noise.className = 'impact-noise';
  canvas.after(noise);
  let model = null;
  let contact = '';
  let scene = '';
  let lastTime = -Infinity;
  let animations = [];
  let speaking = '';
  function clearVideo() {
    for (const animation of animations) animation.cancel();
    animations = [];
  }
  prefs.subscribe(function changed() {
    if (!prefs.get('contactVideo')) clearVideo();
    if (speaking && !prefs.get(speaking)) {
      radio.clearFlight();
      speaking = '';
    }
  });
  function update(state, world, covered) {
    const blocked = covered || document.hidden || document.body.classList.contains('cold-open') ||
      (state.procedure?.active && state.procedure.phase !== 'diving');
    const site = world?.scenario?.key || '';
    const mission = [site, state.vehicle_id, state.mission?.mode, state.campaign?.chapter].join('/');
    const hit = state.events?.filter(event => !event.vehicle_id || event.vehicle_id === state.vehicle_id).at(-1);
    const key = hit ? JSON.stringify([hit.t, hit.where, hit.obstacle]) : '';
    if (scene === mission && state.t >= lastTime && !blocked && !state.paused && onboard() && key && key !== contact &&
        hit.t <= state.t && state.t - hit.t < 2 && prefs.get('contactVideo')) {
      clearVideo();
      animations.push(noise.animate(BANDS, {duration: 160, easing: 'steps(2)'}));
      if (!matchMedia('(prefers-reduced-motion: reduce)').matches) {
        animations.push(canvas.animate(SHAKE.map(transform => ({transform})), 175));
      }
    }
    if (blocked || state.paused || scene !== mission || state.t < lastTime) radio.clearFlight();
    lastTime = state.t;
    scene = mission;
    contact = key;
    const busy = radio.busy();
    model = advanceReactions(model, state, {
      mission: blocked || !state.mission ? '' : mission, enabled: prefs.get('crewCalls'),
      idle: prefs.get('idleCalls') && state.mission?.mode !== 'free_explore',
      busy, now: performance.now() / 1000
    });
    const line = model?.line;
    if (!line) return;
    const siteHint = site.startsWith('aquaculture_pen') ? 'pen'
      : {harbor_inspection: 'harbor', open_water: 'openWater'}[site] || 'idle';
    const hint = model.idleCount % 2 === 0 ? 'check' : siteHint;
    speaking = line === 'idle' ? 'idleCalls' : 'crewCalls';
    const role = ROLE[line] || {idle: 'tender', check: 'deck'}[hint] || 'supervisor';
    radio.sayFlight([role, STRINGS[line === 'idle' ? hint : line]]);
  }
  return {update};
}
