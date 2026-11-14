// Heading for the flight HUD: wrap-safe smoothing and the thin-line heading tape (no filled panel).
// The large current heading is DOM text above the tape so its digits use tabular figures.
import { fitCanvas, halo, font, INK, INK_DIM, ACCENT } from './canvas.js';

const CARDINALS = {0: 'N', 90: 'E', 180: 'S', 270: 'W'};
const SPAN_DEG = 60;
let displayed;

// Smooths toward the target heading along the shorter way round and returns degrees in [0, 360).
export function smoothHeading(heading, dt) {
  displayed ??= heading;
  const delta = ((heading - displayed + 540) % 360) - 180;
  displayed = (displayed + delta * (1 - Math.exp(-dt * 12)) + 360) % 360;
  return displayed;
}

export function headingLabel(degrees) {
  return String(Math.round(degrees) % 360).padStart(3, '0');
}

function tickLabel(normalized) {
  return CARDINALS[normalized] || String(normalized).padStart(3, '0');
}

// Ticks every 5°, longer every 10°, labels every 20° and at the cardinal points; pointer at the centre.
export function drawHeadingTape(canvas, heading) {
  const fitted = fitCanvas(canvas);
  if (!fitted) return;
  const {ctx, width, height} = fitted;
  const centre = width / 2;
  const scale = (width - 24) / (2 * SPAN_DEG);
  const base = 14;
  halo(ctx);
  ctx.lineWidth = 1.25;
  ctx.strokeStyle = INK_DIM;
  ctx.fillStyle = INK_DIM;
  ctx.font = font(14);
  ctx.textAlign = 'center';
  ctx.beginPath();
  ctx.moveTo(12, base);
  ctx.lineTo(width - 12, base);
  for (let angle = Math.ceil((heading - SPAN_DEG) / 5) * 5; angle <= heading + SPAN_DEG; angle += 5) {
    const x = centre + (angle - heading) * scale;
    const normalized = ((angle % 360) + 360) % 360;
    ctx.moveTo(x, base);
    ctx.lineTo(x, base + (normalized % 10 ? 5 : 10));
  }
  ctx.stroke();
  for (let angle = Math.ceil((heading - SPAN_DEG) / 10) * 10; angle <= heading + SPAN_DEG; angle += 10) {
    const normalized = ((angle % 360) + 360) % 360;
    if (normalized % 20 && !CARDINALS[normalized]) continue;
    const x = centre + (angle - heading) * scale;
    if (Math.abs(x - centre) < 22) continue;
    ctx.fillStyle = CARDINALS[normalized] ? INK : INK_DIM;
    ctx.fillText(tickLabel(normalized), x, base + 28);
  }
  ctx.fillStyle = ACCENT;
  ctx.beginPath();
  ctx.moveTo(centre, base + 2);
  ctx.lineTo(centre - 7, base - 11);
  ctx.lineTo(centre + 7, base - 11);
  ctx.closePath();
  ctx.fill();
}
