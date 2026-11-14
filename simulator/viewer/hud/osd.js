// Camera on-screen display (OSD) for the real preset seen from the onboard camera: monospace text burned in
// at the four corners like inspection video, a text heading tape, a centre cross, frame corner marks and the
// motor lock message. Shows only what the simulator state provides; a field it does not report (water
// temperature, camera tilt) is left out rather than invented.
const STRINGS = {
  depth: 'DEPTH',
  alt: 'ALT',
  pitch: 'PITCH',
  roll: 'ROLL',
  tether: 'TETHER',
  light: 'LIGHT',
  mode: 'MODE',
  rec: '● REC',
  dive: 'DIVE',
  hold: 'D-HOLD',
  nav: 'NAV',
  paused: 'PAUSED',
  heading: 'HDG',
  levels: ['MANUAL', 'VEL ASSIST', 'POS HOLD'],
  locked: 'MOTORS LOCKED — {key} TO ARM',
  cardinals: {0: 'N', 90: 'E', 180: 'S', 270: 'W'},
};
const TAPE_HALF_DEG = 30;
let root = null;
let recordingSince = null;
const parts = {};

function escapeText(value) {
  return String(value).replace(/[&<>"]/g, function escapeChar(char) {
    return {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;'}[char];
  });
}

function setHTML(el, html) {
  if (el._html === html) return;
  el._html = html;
  el.innerHTML = html;
}

function row(label, value, width, className = '') {
  const key = `<span class="k">${escapeText(label.padEnd(width))}</span>`;
  return `<div class="${className}">${key} ${escapeText(value)}</div>`;
}

function signed(value, digits) {
  const text = Math.abs(value).toFixed(digits);
  return `${value < 0 ? '-' : '+'}${text}°`;
}

function pad2(value) {
  return String(value).padStart(2, '0');
}

function clock(date) {
  const day = `${date.getFullYear()}-${pad2(date.getMonth() + 1)}-${pad2(date.getDate())}`;
  return `${day} ${pad2(date.getHours())}:${pad2(date.getMinutes())}:${pad2(date.getSeconds())}`;
}

function duration(seconds) {
  const whole = Math.max(0, Math.floor(seconds));
  return `${pad2(Math.floor(whole / 3600))}:${pad2(Math.floor(whole / 60) % 60)}:${pad2(whole % 60)}`;
}

// A fixed-width text tape: labels every 10°, dots between, and the current heading in the middle.
export function osdHeadingTape(heading) {
  const rounded = Math.round(heading) % 360;
  const centre = Math.round(heading / 5) * 5;
  const items = [];
  for (let angle = centre - TAPE_HALF_DEG; angle <= centre + TAPE_HALF_DEG; angle += 5) {
    const normalized = ((angle % 360) + 360) % 360;
    if (angle === centre) {
      items.push(`<b>${STRINGS.heading} ${String(rounded).padStart(3, '0')}°</b>`);
    } else if (normalized % 10) {
      items.push('·');
    } else {
      const label = STRINGS.cardinals[normalized] || String(normalized).padStart(3, '0');
      items.push(label.padStart(2).padEnd(3));
    }
  }
  return items.join(' ');
}

function recordingTime(s) {
  if (!s.recording) {
    recordingSince = null;
    return null;
  }
  if (recordingSince == null || s.t < recordingSince) recordingSince = s.t ?? 0;
  return (s.t ?? 0) - recordingSince;
}

function diveLine(s, w) {
  const items = [];
  const dive = s.expedition?.dive_id;
  if (dive) items.push(`${STRINGS.dive} ${String(dive).slice(0, 6).toUpperCase()}`);
  if (w?.scenario?.name) items.push(w.scenario.name);
  return items.join(' · ');
}

// Creates the OSD layer inside the viewport. Safe to call more than once.
export function installOsd(viewport) {
  if (root) return root;
  root = document.createElement('div');
  root.id = 'flightOsd';
  root.className = 'flight';
  root.innerHTML = '<div class="osd-frame"><i></i><i></i><i></i><i></i></div><div class="osd-cross"></div>'
    + '<div class="osd-heading"></div><div class="osd-block osd-tl"></div><div class="osd-block osd-tr"></div>'
    + '<div class="osd-block osd-bl"></div><div class="osd-block osd-br"></div><div class="osd-lock"></div>';
  for (const name of ['heading', 'tl', 'tr', 'bl', 'br', 'lock']) {
    parts[name] = root.querySelector(`.osd-${name}`);
  }
  viewport.append(root);
  return root;
}

// r: smoothed readings from the flight HUD; s: delayed display state; w: world; extra: assist and key text.
export function updateOsd(r, s, w, extra) {
  if (!root) return;
  setHTML(parts.heading, osdHeadingTape(r.heading));
  const top = [row(STRINGS.depth, `${r.depth.toFixed(1)} m`, 5)];
  if (r.alt != null) top.push(row(STRINGS.alt, `${r.alt.toFixed(1)} m`, 5, r.altWarn ? 'warn' : ''));
  setHTML(parts.tl, top.join(''));
  const right = [];
  const rec = recordingTime(s);
  if (rec != null) right.push(`<div><span class="rec">${STRINGS.rec}</span> ${duration(rec)}</div>`);
  right.push(`<div>${clock(new Date())}</div>`);
  const dive = diveLine(s, w);
  if (dive) right.push(`<div class="k">${escapeText(dive)}</div>`);
  setHTML(parts.tr, right.join(''));
  const [roll = 0, pitch = 0] = s.euler || [];
  setHTML(parts.bl, row(STRINGS.pitch, signed(pitch, 1), 5) + row(STRINGS.roll, signed(roll, 1), 5));
  const mode = `${s.ctrl_mode || '—'} · ${STRINGS.levels[extra.assistLevel] || STRINGS.levels[0]}`;
  const bottom = [
    row(STRINGS.tether, `${r.cable.toFixed(0)} m / ${r.tension.toFixed(0)} N`, 6, s.tether?.warn ? 'warn' : ''),
    row(STRINGS.light, `${r.light} / 2`, 6),
    row(STRINGS.mode, mode, 6),
  ];
  if (s.keep_depth && s.depth_hold != null) bottom.push(row(STRINGS.hold, `${s.depth_hold.toFixed(1)} m`, 6));
  if (s.nav?.mode && s.nav.mode !== 'IDLE') bottom.push(row(STRINGS.nav, s.nav.mode, 6));
  if (s.paused) bottom.push(`<div class="warn">${STRINGS.paused}</div>`);
  if (extra.assistStatus) bottom.push(`<div class="warn">${escapeText(extra.assistStatus)}</div>`);
  setHTML(parts.br, bottom.join(''));
  const lock = s.locked ? STRINGS.locked.replace('{key}', extra.lockKey.toUpperCase()) : '';
  if (parts.lock.textContent !== lock) parts.lock.textContent = lock;
}
