// Vehicle system read-outs for the flight HUD: simulated link quality, stale video, power, temperature, leak.
// Self-contained: the HUD mounts it with one call per frame. Reads optional state fields only; an older
// server without `link`/`power`/`thermal`/`leak` shows nothing. Never sends vehicle controls.

import { localize } from '../i18n/index.js';

const STRINGS = localize('hud.system_status', {
  label: '載具系統',
  link: {healthy: '鏈路 正常', degraded: '鏈路 劣化', lost: '鏈路 中斷'},
  quality: '品質',
  reconnecting: '重新連線中',
  videoLag: '影像延遲',
  videoFrozen: '影像凍結',
  failsafe: {disarm: '失聯保護：已上鎖', depth_hold: '失聯保護：定深', surface: '失聯保護：上浮'},
  failsafeIn: '失聯保護倒數',
  rearm: '需重新解鎖',
  power: '功率',
  powerLimited: '功率受限',
  tripped: '電源跳脫',
  cutoff: '電池耗盡，馬達與燈光已切斷',
  temperature: '溫度',
  warnings: {dry_run: '馬達離水運轉過久', motor_hot: '馬達過熱', electronics_hot: '電子艙過熱'},
  leak: '漏水警報',
  seconds: 's',
  watts: 'W',
  volts: 'V',
});
// The pills stack under the lock state and mode chips in the top-right status column (.hud.tl), so a taller lock
// line (locked + unlock hint) pushes them down instead of printing over them. Without that column they float.
const STYLE = `
#flightSystem { right: 4%; top: 12%; transform: translateY(-100%); display: flex; flex-wrap: wrap;
  justify-content: flex-end; gap: 6px; max-width: 46%; }
.hud.tl > #flightSystem { position: static; transform: none; max-width: none; }
#flightSystem span { padding: 2px 8px; border: 1px solid var(--line); border-radius: var(--radius);
  background: var(--panel); color: var(--text); white-space: nowrap; }
#flightSystem span[hidden] { display: none; }
#flightSystem [data-tone=warn] { color: var(--warn); border-color: var(--warn); }
#flightSystem [data-tone=danger] { color: var(--danger); border-color: var(--danger); }
#flightSystem [data-tone=ok] { color: var(--go); }
body.hud-minimal #flightSystem span:not([data-tone=warn]):not([data-tone=danger]) { display: none; }
/* Narrow screens keep the floating placement: the column is short there and the radio sits beside it. */
@media (max-width: 720px) {
  #flightSystem { max-width: 70%; top: 18%; }
  .hud.tl > #flightSystem { position: fixed; right: 4%; top: 18%; transform: translateY(-100%); max-width: 70%; }
}
`;
const FIELDS = ['link', 'video', 'failsafe', 'power', 'temperature', 'warning', 'leak'];

let root = null;
const items = {};

function mount(viewport) {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
  root = document.createElement('div');
  root.id = 'flightSystem';
  root.className = 'flight';
  root.setAttribute('role', 'status');
  root.setAttribute('aria-label', STRINGS.label);
  for (const name of FIELDS) {
    const item = document.createElement('span');
    item.dataset.item = name;
    item.hidden = true;
    root.append(item);
    items[name] = item;
  }
  const column = viewport.querySelector('.hud.tl');
  if (column) column.append(root);
  else viewport.append(root);
}

function show(name, text, tone = '') {
  const item = items[name];
  item.hidden = !text;
  if (item.textContent !== text) item.textContent = text;
  item.dataset.tone = tone;
}

function linkText(link) {
  if (!link) return ['', ''];
  if (link.phase === 'reconnecting') return [`${STRINGS.reconnecting} ${Math.ceil(link.reconnect_in ?? 0)} s`, 'warn'];
  const quality = link.state === 'degraded' ? ` · ${STRINGS.quality} ${Math.round((link.quality ?? 0) * 100)}%` : '';
  const tone = link.state === 'lost' ? 'danger' : link.state === 'degraded' ? 'warn' : 'ok';
  return [(STRINGS.link[link.state] || '') + quality, tone];
}

function videoText(link, staleSince, now) {
  if (!link || link.state === 'healthy') return ['', ''];
  if (link.video_frozen) {
    const age = staleSince === null ? 0 : (now - staleSince) / 1000;
    return [`${STRINGS.videoFrozen} ${age.toFixed(0)} ${STRINGS.seconds}`, 'danger'];
  }
  const lag = link.video_lag_s ?? 0;
  if (lag >= 0.5) return [`${STRINGS.videoLag} ${lag.toFixed(1)} ${STRINGS.seconds}`, 'warn'];
  return ['', ''];
}

function failsafeText(link) {
  if (!link) return ['', ''];
  if (link.failsafe) {
    const rearm = link.rearm_required && link.phase === 'connected' ? ` · ${STRINGS.rearm}` : '';
    return [(STRINGS.failsafe[link.failsafe] || '') + rearm, 'danger'];
  }
  if (link.failsafe_in == null) return ['', ''];
  return [`${STRINGS.failsafeIn} ${link.failsafe_in.toFixed(1)} ${STRINGS.seconds}`, 'danger'];
}

function powerText(power) {
  if (!power) return ['', ''];
  if (power.tripped) return [STRINGS.tripped, 'danger'];
  if (power.cutoff) return [STRINGS.cutoff, 'danger'];
  if (power.type === 'tether') {
    const text = `${STRINGS.power} ${power.demand_w} / ${power.available_w} ${STRINGS.watts}`;
    return power.limited ? [`${text} · ${STRINGS.powerLimited}`, 'warn'] : [text, ''];
  }
  return power.voltage_v == null ? ['', ''] : [`${power.voltage_v.toFixed(1)} ${STRINGS.volts}`, ''];
}

function temperatureText(thermal) {
  if (!thermal) return [['', ''], ['', '']];
  const warnings = (thermal.warnings || []).map(code => STRINGS.warnings[code]).filter(Boolean);
  const reading = `${STRINGS.temperature} ${Math.round(thermal.motor_c)} / ${Math.round(thermal.mos_c)} °C`;
  return [[reading, warnings.length ? 'warn' : ''], [warnings.join(' · '), 'warn']];
}

let staleSince = null;
// `latest` carries the link as known topside; `onboard` is the telemetry the pilot has actually received.
export function updateSystemStatus(latest, onboard = latest) {
  if (!root) mount(document.getElementById('vp'));
  const now = performance.now();
  const link = latest?.link;
  staleSince = link?.video_frozen ? staleSince ?? now : null;
  const [linkLabel, linkTone] = linkText(link);
  show('link', linkLabel, linkTone);
  show('video', ...videoText(link, staleSince, now));
  show('failsafe', ...failsafeText(link));
  show('power', ...powerText(onboard?.power));
  const [reading, warning] = temperatureText(onboard?.thermal);
  show('temperature', ...reading);
  show('warning', ...warning);
  show('leak', onboard?.leak?.detected ? STRINGS.leak : '', 'danger');
  root.dataset.link = link?.phase === 'reconnecting' ? 'reconnecting' : link?.state || '';
}

// Battery percentage is meaningless for a vehicle powered through its tether.
export function batteryApplies(state) {
  return state?.power?.type !== 'tether';
}
