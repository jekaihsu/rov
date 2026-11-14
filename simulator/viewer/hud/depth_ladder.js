// Vertical depth ladder for the line-style HUD: a fixed scale from the surface to the seabed with a pointer
// that moves with the vehicle's depth, the depth-hold set point and the seabed line. The large depth and
// altitude numbers are DOM text beside the ladder (tabular figures), so this only draws lines and labels.
import { fitCanvas, halo, font, INK_DIM, ACCENT, WARN } from './canvas.js';

const PAD = 10;
const LINE_X = 38;

// A tick step that keeps labels at least ~36 px apart.
function labelStep(pixelsPerMetre) {
  for (const step of [1, 2, 5, 10, 20, 50, 100]) {
    if (step * pixelsPerMetre >= 36) return step;
  }
  return 200;
}

function drawSeabed(ctx, y) {
  ctx.strokeStyle = INK_DIM;
  ctx.lineWidth = 1.25;
  ctx.beginPath();
  ctx.moveTo(LINE_X - 26, y);
  ctx.lineTo(LINE_X + 6, y);
  for (let x = LINE_X - 24; x <= LINE_X + 4; x += 6) {
    ctx.moveTo(x, y);
    ctx.lineTo(x - 5, y + 6);
  }
  ctx.stroke();
}

function drawPointer(ctx, y, colour) {
  ctx.fillStyle = colour;
  ctx.beginPath();
  ctx.moveTo(LINE_X + 2, y);
  ctx.lineTo(LINE_X + 14, y - 8);
  ctx.lineTo(LINE_X + 14, y + 8);
  ctx.closePath();
  ctx.fill();
}

function drawHoldMark(ctx, y) {
  ctx.strokeStyle = ACCENT;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(LINE_X - 10, y);
  ctx.lineTo(LINE_X, y);
  ctx.stroke();
}

// depth and seabed in metres (positive down); seabed may be null when the world is not known yet.
// hold: the depth-hold set point or null. warn: draw the pointer in the caution colour.
export function drawDepthLadder(canvas, {depth, seabed = null, hold = null, warn = false}) {
  const fitted = fitCanvas(canvas);
  if (!fitted) return;
  const {ctx, height} = fitted;
  const bottom = seabed > 0 ? seabed : Math.max(10, Math.ceil((depth + 5) / 5) * 5);
  const scale = (height - 2 * PAD) / bottom;
  const toY = metres => PAD + Math.max(0, Math.min(bottom, metres)) * scale;
  const step = labelStep(scale);
  halo(ctx);
  ctx.strokeStyle = INK_DIM;
  ctx.fillStyle = INK_DIM;
  ctx.lineWidth = 1.25;
  ctx.font = font(12);
  ctx.textAlign = 'right';
  ctx.beginPath();
  ctx.moveTo(LINE_X, PAD);
  ctx.lineTo(LINE_X, toY(bottom));
  const minor = step / (step >= 5 ? 5 : 2);
  for (let metres = 0; metres <= bottom + 1e-6; metres += minor) {
    const major = Math.abs(metres / step - Math.round(metres / step)) < 1e-6;
    ctx.moveTo(LINE_X - (major ? 10 : 5), toY(metres));
    ctx.lineTo(LINE_X, toY(metres));
  }
  ctx.stroke();
  for (let metres = 0; metres < bottom - step / 2; metres += step) {
    ctx.fillText(String(metres), LINE_X - 14, toY(metres) + 4);
  }
  if (seabed > 0) drawSeabed(ctx, toY(seabed));
  if (hold != null) drawHoldMark(ctx, toY(hold));
  drawPointer(ctx, toY(depth), warn ? WARN : ACCENT);
}
