// Centred attitude reference for the line-style HUD: side arcs, horizon bars that rotate with roll and shift
// with pitch, a ±10°/±20° pitch ladder, and a fixed vehicle symbol. Thin lines only; never fills a panel.
import { fitCanvas, halo, font, INK, INK_DIM, ACCENT, WARN } from './canvas.js';

// Geometry is designed on a 680 × 300 box and scaled uniformly into the canvas.
const DESIGN_WIDTH = 680;
const DESIGN_HEIGHT = 300;
const PX_PER_DEG = 7;
const LADDER = [-20, -10, 10, 20];
const STEEP_ROLL_DEG = 20;

function drawArcs(ctx) {
  ctx.strokeStyle = INK;
  ctx.globalAlpha = 0.8;
  ctx.lineWidth = 1.5;
  ctx.beginPath();
  ctx.arc(0, 0, 176, Math.PI - 0.55, Math.PI + 0.55);
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(0, 0, 176, -0.55, 0.55);
  ctx.stroke();
  ctx.globalAlpha = 1;
}

function drawLadder(ctx, pitch) {
  ctx.strokeStyle = INK_DIM;
  ctx.fillStyle = INK_DIM;
  ctx.lineWidth = 1.25;
  ctx.font = font(12);
  ctx.textAlign = 'left';
  ctx.setLineDash([6, 8]);
  for (const degree of LADDER) {
    const y = (pitch - degree) * PX_PER_DEG;
    if (Math.abs(y) > 128) continue;
    const half = Math.abs(degree) === 10 ? 70 : 50;
    ctx.beginPath();
    ctx.moveTo(-half, y);
    ctx.lineTo(half, y);
    ctx.stroke();
    ctx.fillText(String(degree), half + 12, y + 4);
  }
  ctx.setLineDash([]);
}

function drawHorizon(ctx, pitch, steep) {
  const y = Math.max(-140, Math.min(140, pitch * PX_PER_DEG));
  ctx.strokeStyle = steep ? WARN : ACCENT;
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.moveTo(-330, y);
  ctx.lineTo(-196, y);
  ctx.moveTo(196, y);
  ctx.lineTo(330, y);
  ctx.stroke();
}

function drawVehicleSymbol(ctx) {
  ctx.strokeStyle = INK;
  ctx.lineWidth = 1.75;
  ctx.beginPath();
  ctx.moveTo(-18, 0);
  ctx.lineTo(-7, 0);
  ctx.lineTo(0, 8);
  ctx.lineTo(7, 0);
  ctx.lineTo(18, 0);
  ctx.stroke();
}

// euler: [roll, pitch, yaw] in degrees, as in the simulator state.
export function drawFlightAttitude(canvas, euler) {
  const fitted = fitCanvas(canvas);
  if (!fitted) return;
  const {ctx, width, height} = fitted;
  const [roll = 0, pitch = 0] = euler || [];
  const scale = Math.min(width / DESIGN_WIDTH, height / DESIGN_HEIGHT);
  halo(ctx);
  ctx.save();
  ctx.translate(width / 2, height / 2);
  ctx.scale(scale, scale);
  drawArcs(ctx);
  ctx.save();
  ctx.rotate(-roll * Math.PI / 180);
  drawLadder(ctx, pitch);
  drawHorizon(ctx, pitch, Math.abs(roll) > STEEP_ROLL_DEG);
  ctx.restore();
  drawVehicleSymbol(ctx);
  ctx.restore();
}
