// Optional forward imaging sonar instrument: a fan display that peeks for a few seconds or stays pinned.
// It subscribes to the server's background scans (operation `sonar_subscribe`) only while it is shown, so idle
// viewers cost the server nothing. The peek key comes from input/bindings.js (`sonarPeek`); the engineering
// drawer carries a pointer toggle. The panel layer is --z-controls from hud/tokens.css because it holds controls.
// Acoustic settings are illustrative training assumptions, not a specific instrument's specification.
const STRINGS = {
  title: '聲納',
  range: '量程 m',
  gain: '增益',
  palette: '色表',
  amber: '琥珀',
  cyan: '青色',
  pin: '固定',
  toggle: '聲納（5）',
  waiting: '等待掃描',
  rate: '5 Hz',
};
const PEEK_MS = 3000;
const WIDTH = 304;
const HEIGHT = 200;
const STYLE = `
  .sonar-panel{position:fixed;right:4%;bottom:12%;width:320px;box-sizing:border-box;padding:8px;
    background:rgba(8,18,26,.82);color:#e8f1f5;border:1px solid #8fa6b2;border-radius:10px;z-index:var(--z-controls)}
  .sonar-panel[hidden]{display:none}
  .sonar-panel label{margin-right:8px;font-size:12px}
  .sonar-panel canvas{width:100%;display:block;margin-top:6px}
  .sonar-panel .sonar-status{font-size:12px;color:#8fa6b2}
`;

function select(parent, label, values) {
  const wrapper = document.createElement('label');
  wrapper.textContent = label;
  const input = document.createElement('select');
  for (const [value, text] of values) input.add(new Option(text, value));
  wrapper.append(input);
  parent.append(wrapper);
  return input;
}

function drawGrid(ctx, frame, origin, radius) {
  ctx.fillStyle = '#04090d';
  ctx.fillRect(0, 0, WIDTH, HEIGHT);
  ctx.strokeStyle = '#52616a';
  ctx.fillStyle = '#8fa6b2';
  ctx.font = '11px monospace';
  for (let ring = 1; ring <= 4; ring++) {
    ctx.beginPath();
    ctx.arc(origin.x, origin.y, radius * ring / 4, -5 * Math.PI / 6, -Math.PI / 6);
    ctx.stroke();
    ctx.fillText(`${frame.range_m * ring / 4}m`, origin.x + 3, origin.y - radius * ring / 4);
  }
  for (const degree of [-60, -30, 0, 30, 60]) {
    const angle = degree * Math.PI / 180;
    ctx.fillText(`${degree}°`, origin.x + Math.sin(angle) * radius - 10, origin.y - Math.cos(angle) * radius);
  }
}

function drawReturns(ctx, frame, origin, radius, gain, palette) {
  for (let beam = 0; beam < frame.beams; beam++) {
    const angle = (-60 + 120 * beam / (frame.beams - 1)) * Math.PI / 180;
    if (frame.sidelobe_m?.[beam] < frame.range_m) {
      const side = frame.sidelobe_m[beam] / frame.range_m * radius;
      const value = Math.min(255, frame.sidelobe_intensity[beam] * gain);
      ctx.fillStyle = palette === 'amber' ? `rgb(${value},${value * .7},0)` : `rgb(0,${value * .85},${value})`;
      ctx.fillRect(origin.x + Math.sin(angle) * side, origin.y - Math.cos(angle) * side, 2, 2);
    }
    const intensity = Math.min(255, frame.intensity[beam] * gain);
    const amber = `rgb(${intensity},${intensity * .7},0)`;
    ctx.fillStyle = palette === 'amber' ? amber : `rgb(0,${intensity * .85},${intensity})`;
    if (frame.distance_m[beam] < frame.range_m) {
      const r = frame.distance_m[beam] / frame.range_m * radius;
      ctx.fillRect(origin.x + Math.sin(angle) * r, origin.y - Math.cos(angle) * r, 3, 3);
    }
    if (frame.ghost_m[beam] < frame.range_m) {
      const ghost = frame.ghost_m[beam] / frame.range_m * radius;
      ctx.globalAlpha = .2;
      ctx.fillRect(origin.x + Math.sin(angle) * ghost, origin.y - Math.cos(angle) * ghost, 2, 2);
      ctx.globalAlpha = 1;
    }
  }
}

export function createSonar(send) {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
  const panel = document.createElement('section');
  panel.className = 'sonar-panel';
  panel.hidden = true;
  const title = document.createElement('strong');
  title.textContent = STRINGS.title;
  panel.append(title, document.createElement('br'));
  const range = select(panel, STRINGS.range, [10, 20, 30, 50].map(value => [value, value]));
  const gain = select(panel, STRINGS.gain, [1, 2, 4].map(value => [value, value]));
  const palette = select(panel, STRINGS.palette, [['amber', STRINGS.amber], ['cyan', STRINGS.cyan]]);
  range.value = '30';
  const pin = document.createElement('input');
  pin.type = 'checkbox';
  const pinLabel = document.createElement('label');
  pinLabel.textContent = STRINGS.pin;
  pinLabel.append(pin);
  panel.append(pinLabel);
  const canvas = document.createElement('canvas');
  canvas.width = WIDTH;
  canvas.height = HEIGHT;
  panel.append(canvas);
  const status = document.createElement('div');
  status.className = 'sonar-status';
  status.textContent = STRINGS.waiting;
  panel.append(status);
  document.body.append(panel);
  const toggle = document.createElement('button');
  toggle.type = 'button';
  toggle.id = 'sonarToggle';
  toggle.textContent = STRINGS.toggle;
  document.querySelector('.mission-tools')?.append(toggle);
  let timer = null;
  function subscribe(enabled) {
    send({type: 'operation', action: 'sonar_subscribe', enabled, range_m: Number(range.value)});
  }
  function close() {
    panel.hidden = true;
    subscribe(false);
  }
  function closeUnlessPinned() {
    if (!pin.checked) close();
  }
  function peek() {
    clearTimeout(timer);
    if (!panel.hidden) {
      close();
      return;
    }
    panel.hidden = false;
    subscribe(true);
    timer = setTimeout(closeUnlessPinned, PEEK_MS);
  }
  toggle.onclick = function togglePanel() {
    pin.checked = panel.hidden;
    peek();
  };
  range.onchange = function retune() {
    subscribe(true);
  };
  pin.onchange = function repin() {
    clearTimeout(timer);
    if (!pin.checked) timer = setTimeout(closeUnlessPinned, PEEK_MS);
  };
  function receive(state) {
    if (!state?.sonar || panel.hidden) return;
    const frame = state.sonar;
    const ctx = canvas.getContext('2d');
    const origin = {x: WIDTH / 2, y: 190};
    const radius = 175;
    drawGrid(ctx, frame, origin, radius);
    drawReturns(ctx, frame, origin, radius, Number(gain.value), palette.value);
    status.textContent = `${STRINGS.title} · ${frame.range_m} m · ${STRINGS.rate}`;
  }
  // The key and pad source are declared in input/bindings.js; this module supplies only the behaviour.
  function bindInput(input) {
    input.registerActions({sonarPeek: {label: STRINGS.title, run: peek}});
  }
  return {receive, bindInput};
}
