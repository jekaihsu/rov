// Thin-line circular minimap: obstacles, tether lay, objectives and teammates around the vehicle.
// North-up or heading-up; drawn in CSS pixels on a transparent canvas, no filled box.
import { fitCanvas, halo, font, INK, INK_DIM, ACCENT } from './canvas.js';
import { hidesTargets } from '../sonar/scenario.js';

const RING = 'rgba(190, 230, 240, .32)';
const OBSTACLE = 'rgba(200, 220, 228, .75)';
const TETHER = '#e6c84f';
const TARGET = '#f2b84b';
const PEER = '#5fd38a';
const METRES_ACROSS = 64;

function strokeRings(ctx, radius) {
  ctx.strokeStyle = RING;
  ctx.lineWidth = 1;
  for (const r of [radius, radius / 2]) {
    ctx.beginPath();
    ctx.arc(0, 0, r, 0, Math.PI * 2);
    ctx.stroke();
  }
}

function drawObstacles(ctx, obstacles, point, scale, line) {
  ctx.strokeStyle = OBSTACLE;
  ctx.lineWidth = 1.25;
  for (const ob of obstacles) {
    if (ob.p0 && ob.p1) line([ob.p0, ob.p1]);
    if (ob.type === 'cylinder' && ob.p0) {
      const [x, y] = point(ob.p0);
      ctx.beginPath();
      ctx.arc(x, y, Math.max(2, (ob.radius || 0) * scale), 0, Math.PI * 2);
      ctx.stroke();
    }
    if (ob.center && ob.half) {
      const [x, y] = point(ob.center);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate((ob.yaw_deg || 0) * Math.PI / 180);
      ctx.strokeRect(-ob.half[1] * scale, -ob.half[0] * scale, ob.half[1] * 2 * scale, ob.half[0] * 2 * scale);
      ctx.restore();
    }
    if (ob.type === 'wall') {
      const angle = ob.normal_deg * Math.PI / 180;
      const tangent = [-Math.sin(angle) * ob.width / 2, Math.cos(angle) * ob.width / 2];
      line([
        [ob.point[0] - tangent[0], ob.point[1] - tangent[1]],
        [ob.point[0] + tangent[0], ob.point[1] + tangent[1]],
      ]);
    }
  }
}

function drawNorth(ctx, radius, rotation) {
  ctx.save();
  ctx.rotate(rotation);
  ctx.fillStyle = INK_DIM;
  ctx.font = font(11, 600);
  ctx.textAlign = 'center';
  ctx.textBaseline = 'middle';
  ctx.translate(0, -radius + 9);
  ctx.rotate(-rotation);
  ctx.fillText('N', 0, 0);
  ctx.restore();
}

function drawVehicle(ctx) {
  ctx.fillStyle = ACCENT;
  ctx.strokeStyle = INK;
  ctx.lineWidth = 1;
  ctx.beginPath();
  ctx.moveTo(0, -9);
  ctx.lineTo(-6, 7);
  ctx.lineTo(0, 4);
  ctx.lineTo(6, 7);
  ctx.closePath();
  ctx.fill();
}

// s: delayed display state; w: world description; northUp: true for a north-up map.
export function drawMinimap(canvas, s, w, northUp) {
  const fitted = fitCanvas(canvas);
  if (!fitted) return;
  const {ctx, width, height} = fitted;
  const radius = Math.min(width, height) / 2 - 2;
  const scale = radius * 2 / METRES_ACROSS;
  const heading = (s.euler?.[2] || 0) * Math.PI / 180;
  const rotation = northUp ? 0 : -heading;
  ctx.save();
  ctx.translate(width / 2, height / 2);
  halo(ctx);
  strokeRings(ctx, radius);
  drawNorth(ctx, radius, rotation);
  ctx.beginPath();
  ctx.arc(0, 0, radius - 1, 0, Math.PI * 2);
  ctx.clip();
  ctx.rotate(rotation);
  function point(p) {
    return [(p[1] - s.pos[1]) * scale, -(p[0] - s.pos[0]) * scale];
  }
  function line(points, colour) {
    if (colour) ctx.strokeStyle = colour;
    ctx.beginPath();
    points.forEach(function vertex(p, i) {
      const [x, y] = point(p);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
  }
  drawObstacles(ctx, w?.obstacles || [], point, scale, line);
  ctx.lineWidth = 1.75;
  line(s.tether?.nodes || [], TETHER);
  ctx.lineWidth = 1.5;
  ctx.strokeStyle = TARGET;
  // The acoustic-search target must be found by sonar, so the map does not reveal it.
  for (const target of hidesTargets(w) ? [] : s.mission?.targets || w?.objectives || []) {
    if (!target.point) continue;
    const [x, y] = point(target.point);
    ctx.strokeRect(x - 4.5, y - 4.5, 9, 9);
  }
  ctx.fillStyle = PEER;
  for (const peer of s.vehicles || []) {
    if (!peer.pos || (peer.vehicle_id || peer.id) === s.vehicle_id) continue;
    const [x, y] = point(peer.pos);
    ctx.beginPath();
    ctx.arc(x, y, 3, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.rotate(heading);
  drawVehicle(ctx);
  ctx.restore();
}
