// Optional sonar instrument: pinned window or keyboard peek without interrupting piloting.
const STRINGS = {title: '聲納', range: '量程 m', gain: '增益', palette: '色表',
  amber: '琥珀', cyan: '青色', pin: '固定', hint: '5：聲納速覽', waiting: '等待掃描'};
export function createSonar(send) {
  const panel = document.createElement('section');
  panel.style.cssText = 'position:fixed;right:4%;bottom:12%;width:320px;background:rgba(8,18,26,.82);' +
    'color:#e8f1f5;border:1px solid #8fa6b2;border-radius:10px;padding:8px;z-index:25';
  panel.hidden = true;
  const title = document.createElement('strong');
  title.textContent = STRINGS.title;
  panel.append(title);
  function select(label, values) {
    const wrapper = document.createElement('label');
    wrapper.textContent = label;
    const input = document.createElement('select');
    for (const [value, text] of values) input.add(new Option(text, value));
    wrapper.append(input);
    panel.append(wrapper);
    return input;
  }
  const range = select(STRINGS.range, [10, 20, 30, 50].map(v => [v, v]));
  const gain = select(STRINGS.gain, [1, 2, 4].map(v => [v, v]));
  const palette = select(STRINGS.palette, [['amber', STRINGS.amber], ['cyan', STRINGS.cyan]]);
  const pin = document.createElement('input');
  pin.type = 'checkbox';
  const label = document.createElement('label');
  label.textContent = STRINGS.pin;
  label.append(pin);
  panel.append(label);
  const canvas = document.createElement('canvas');
  canvas.width = 304;
  canvas.height = 200;
  canvas.style.width = '100%';
  panel.append(canvas);
  range.value = '30';
  const status = document.createElement('div');
  status.textContent = STRINGS.waiting;
  panel.append(status);
  const button = document.createElement('button');
  button.textContent = STRINGS.hint;
  button.style.cssText = 'position:fixed;right:4%;bottom:8%;z-index:25';
  document.body.append(panel, button);
  let timer;
  function subscribe(enabled) {
    send({type: 'operation', action: 'sonar_subscribe', enabled, range_m: Number(range.value)});
  }
  function peek() {
    panel.hidden = !panel.hidden;
    subscribe(!panel.hidden);
    clearTimeout(timer);
    if (!panel.hidden) timer = setTimeout(() => {
      if (!pin.checked) {
        panel.hidden = true;
        subscribe(false);
      }
    }, 3000);
  }
  button.onclick = peek;
  range.onchange = () => subscribe(true);
  window.addEventListener('keydown', event => {
    if (event.code === 'Digit5' && !event.repeat && !/INPUT|SELECT|TEXTAREA/.test(event.target.tagName)) peek();
  });
  return {receive(state) {
    if (!state.sonar || panel.hidden) return;
    const frame = state.sonar;
    const ctx = canvas.getContext('2d');
    ctx.fillStyle = '#04090d';
    ctx.fillRect(0, 0, 304, 200);
    const radius = 175;
    const ox = 152;
    const oy = 190;
    ctx.strokeStyle = '#52616a';
    ctx.fillStyle = '#8fa6b2';
    ctx.font = '11px monospace';
    for (let ring = 1; ring <= 4; ring++) {
      ctx.beginPath();
      ctx.arc(ox, oy, radius * ring / 4, -5 * Math.PI / 6, -Math.PI / 6);
      ctx.stroke();
      ctx.fillText(`${frame.range_m * ring / 4}m`, ox + 3, oy - radius * ring / 4);
    }
    for (const degree of [-60, -30, 0, 30, 60]) {
      const a = degree * Math.PI / 180;
      ctx.fillText(`${degree}°`, ox + Math.sin(a) * radius - 10, oy - Math.cos(a) * radius);
    }
    for (let i = 0; i < frame.beams; i++) {
      const a = (-60 + 120 * i / (frame.beams - 1)) * Math.PI / 180;
      const intensity = Math.min(255, frame.intensity[i] * Number(gain.value));
      ctx.fillStyle = palette.value === 'amber' ? `rgb(${intensity},${intensity * .7},0)` :
        `rgb(0,${intensity * .85},${intensity})`;
      const r = frame.distance_m[i] / frame.range_m * radius;
      if (frame.distance_m[i] < frame.range_m) ctx.fillRect(ox + Math.sin(a) * r, oy - Math.cos(a) * r, 3, 3);
      if (frame.ghost_m[i] < frame.range_m) {
        const ghost = frame.ghost_m[i] / frame.range_m * radius;
        ctx.globalAlpha = .2;
        ctx.fillRect(ox + Math.sin(a) * ghost, oy - Math.cos(a) * ghost, 2, 2);
        ctx.globalAlpha = 1;
      }
    }
    status.textContent = `${STRINGS.title} · ${frame.range_m} m · 5 Hz`;
  }};
}
