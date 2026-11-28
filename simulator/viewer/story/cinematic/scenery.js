// Painted depth planes for the story camera. Coordinates are in a 1600 × 900 gate.
const hulls = {
  repair: 'M-161 -34 H153 L128 0 H-130 Z M-106 -35 V-65 H-43 V-35 M-96 -65 V-83 '
    + 'H-55 V-65 M61 -34 V-91 H70 L100 -34 H94 L67 -77 V-34',
  fishing: 'M-63 -18 H60 L44 0 H-46 Z M-30 -18 V-42 H4 V-18 M15 -18 V-64 L42 -24 Z',
  cargo: 'M-198 -34 H207 L183 0 H-170 Z M-160 -34 V-79 H-121 V-34 M-86 -34 V-56 '
    + 'H-22 V-34 M-14 -34 V-56 H51 V-34 M59 -34 V-56 H125 V-34',
  patrol: 'M-88 -19 L88 -26 L66 0 H-70 Z M-38 -19 L-27 -43 H17 L37 -21 M-5 -42 V-63 H-2 V-42',
  buoy: 'M-12 -4 L-7 -16 H7 L12 -4 L7 0 H-7 Z M-4 -15 V-41 H4 V-15',
  rov: 'M-31 -19 H31 V7 H-31 Z M-37 -25 H37 V-19 H-37 Z M-37 8 H37 V13 H-37 Z',
  tether: 'M-120 -84 Q-82 59 0 0 L0 2 Q-84 65 -122 -84 Z',
};
const paths = Object.fromEntries(Object.entries(hulls).map(([name, path]) => [name, new Path2D(path)]));

export function drawActor(ctx, actor, x, y, time) {
  ctx.save();
  ctx.translate(x, y + 1.2 * Math.sin(time + x / 100));
  ctx.scale(actor.scale || 1, actor.scale || 1);
  ctx.fillStyle = actor.color || '#142d39';
  const shape = paths[actor.kind];
  ctx.fill(shape);
  if (!['rov', 'tether'].includes(actor.kind)) {
    ctx.save();
    ctx.scale(1, -.33);
    ctx.globalAlpha = .16;
    ctx.fill(shape);
    ctx.restore();
  }
  if (actor.kind === 'repair') {
    ctx.fillStyle = '#f2d5a2';
    for (let i = 0; i < 6; i++) ctx.fillRect(-93 + 7 * i, -79, 4, 5);
    ctx.fillStyle = '#263f4a';
    ctx.fillRect(-81, -100, 3, 18);
    ctx.fillRect(-88, -96, 17, 2);
    ctx.fillRect(-39, -53, 12, 18);
    ctx.fillRect(-142, -28, 276, 2);
    ctx.strokeStyle = '#71848a';
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.arc(19, -40, 14, 0, 2 * Math.PI);
    ctx.stroke();
  }
  ctx.restore();
}

export function harbor(ctx, night, time, blackout) {
  const horizon = 490;
  const sky = ctx.createLinearGradient(0, 70, 0, 850);
  const colors = night ? ['#09182d', '#445873', '#1c3648', '#081528']
    : ['#798ca6', '#f6c599', '#859698', '#253f50'];
  for (const [i, stop] of [0, .53, .54, 1].entries()) sky.addColorStop(stop, colors[i]);
  ctx.fillStyle = sky;
  ctx.fillRect(-400, -250, 2400, 1400);
  ctx.fillStyle = night ? '#bacad5' : '#ffe5b9';
  ctx.beginPath();
  ctx.arc(1150, night ? 240 : 412, night ? 13 : 43, 0, Math.PI * 2);
  ctx.fill();
  ctx.fillStyle = night ? '#26364b' : '#aa9e9c';
  ctx.beginPath();
  ctx.moveTo(-400, horizon);
  for (let x = -400; x <= 2000; x += 16) {
    const ridge = 38 + 28 * Math.sin(x / 147) + 21 * Math.cos(x / 85) + 5 * Math.cos(x / 25);
    ctx.lineTo(x, horizon - ridge);
  }
  ctx.lineTo(2000, horizon);
  ctx.fill();
  ctx.strokeStyle = night ? '#334555' : '#7d8589';
  ctx.lineWidth = 4;
  for (const x of [190, 267, 1430]) {
    ctx.beginPath();
    ctx.moveTo(x, horizon);
    ctx.lineTo(x + 12, horizon - 89);
    ctx.lineTo(x + 50, horizon - 64);
    ctx.lineTo(x - 35, horizon - 64);
    ctx.lineTo(x + 12, horizon - 89);
    ctx.lineTo(x + 23, horizon);
    ctx.stroke();
  }
  for (let i = -12; i < 85; i++) {
    const h = 14 + Math.abs(Math.sin(i * 5.7) * Math.cos(i * .08)) * 76;
    const x = i * 25;
    ctx.fillStyle = night ? '#192b40' : '#79868b';
    ctx.fillRect(x, horizon - h, 23, h);
    if (night && x / 1600 > blackout) {
      ctx.fillStyle = '#efcd8c';
      for (let y = 7; y < h; y += 11) ctx.fillRect(x + 7, horizon - y, 7, 2);
    }
  }
  ctx.fillStyle = night ? '#2a4655' : '#bdc0b3';
  for (let i = 0; i < 180; i++) {
    const x = ((i * 283 + time * (1 + i % 4)) % 2200) - 300;
    const y = horizon + 3 + (i * 107) % 480;
    ctx.fillRect(x, y, 10 + (y - horizon) / 8, 1.2);
  }
}

const west = new Path2D('M-500 -100 H585 L560 140 498 204 519 248 441 301 405 '
    + '364 320 392 315 441 220 506 178 578 95 604 43 697 -40 737 -90 1000 H-500 Z');
const east = new Path2D('M2200 -100 H1510 L1450 103 1381 168 1320 194 1290 260 '
    + '1220 306 1210 390 1150 453 1108 561 1113 650 1058 754 1040 1000 H2200 Z');
const cables = new WeakMap();
export function chart(ctx, t, map) {
  ctx.fillStyle = '#102a37';
  ctx.fillRect(-400, -200, 2400, 1400);
  for (const land of [west, east]) {
    ctx.strokeStyle = '#1a3945';
    for (const w of [150, 105, 60]) {
      ctx.lineWidth = w;
      ctx.stroke(land);
      ctx.strokeStyle = w === 150 ? '#22434d' : '#30505a';
    }
    ctx.fillStyle = '#486467';
    ctx.fill(land);
    ctx.lineWidth = 2;
    ctx.strokeStyle = '#a3b9ac';
    ctx.stroke(land);
  }
  ctx.lineWidth = 1;
  ctx.strokeStyle = '#b4d2d022';
  ctx.beginPath();
  for (let x = -320; x < 2000; x += 80) {
    ctx.moveTo(x, -200);
    ctx.lineTo(x, 1100);
  }
  for (let y = -160; y < 1100; y += 80) {
    ctx.moveTo(-400, y);
    ctx.lineTo(2000, y);
  }
  ctx.stroke();
  if (!map) return;
  if (!cables.has(map)) cables.set(map, new Path2D(map.cable));
  const [origin, bend, destination] = map.track;
  ctx.strokeStyle = '#ecd38e';
  ctx.lineWidth = 4;
  ctx.setLineDash([Math.max(1, t * 115), 1800]);
  ctx.stroke(cables.get(map));
  ctx.setLineDash([8, 9]);
  ctx.lineDashOffset = -t * 12;
  ctx.strokeStyle = '#84cfcc';
  ctx.beginPath();
  ctx.moveTo(...origin);
  ctx.quadraticCurveTo(...bend, ...destination);
  ctx.stroke();
  ctx.setLineDash([]);
  const u = Math.min(1, t / map.arrival);
  const v = 1 - u;
  const px = v * v * origin[0] + 2 * v * u * bend[0] + u * u * destination[0];
  const py = v * v * origin[1] + 2 * v * u * bend[1] + u * u * destination[1];
  ctx.fillStyle = '#d0eeea';
  ctx.beginPath();
  ctx.moveTo(px + 8, py + 5);
  ctx.lineTo(px - 8, py + 2);
  ctx.lineTo(px - 3, py - 7);
  ctx.fill();
  if (map.breakPoint && t > map.breakAt) {
    ctx.strokeStyle = '#ffaa81';
    ctx.beginPath();
    ctx.arc(...map.breakPoint, 11 + (t % 2) * 7, 0, Math.PI * 2);
    ctx.stroke();
    ctx.fillStyle = '#ffad85';
    ctx.fillRect(map.breakPoint[0] - 4, map.breakPoint[1] - 4, 8, 8);
  }
}
