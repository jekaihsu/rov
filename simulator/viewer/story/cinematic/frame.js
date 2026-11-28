// Resolve a storyboard timestamp into a camera, its depth planes and broadcast graphics.
import {interpolateVector} from '../../trailer/camera_path.js';
import {drawActor, harbor, chart} from './scenery.js';
import {STRINGS} from './copy.js';

function label(ctx, key, x, y, size, color = '#f1f1df', weight = 500) {
  ctx.fillStyle = color;
  ctx.font = weight + ' ' + size + 'px system-ui, sans-serif';
  ctx.fillText(STRINGS[key], x, y);
}

function broadcast(ctx, keys, t) {
  ctx.fillStyle = '#122e3e';
  ctx.fillRect(80, 618, 440, 73);
  ctx.fillStyle = '#9addc8';
  ctx.fillRect(80, 618, 6, 73);
  label(ctx, keys[0], 104, 647, 15, '#9addc8', 700);
  label(ctx, keys[1], 104, 677, 26);
  ctx.save();
  ctx.beginPath();
  ctx.rect(80, 695, 1440, 36);
  ctx.clip();
  ctx.fillStyle = '#d7ddce';
  ctx.fillRect(80, 695, 1440, 36);
  for (let x = 90 - (t * 52) % 490; x < 1530; x += 490) label(ctx, keys[2], x, 720, 17, '#173640');
  ctx.restore();
}

export function drawFrame(ctx, board, time) {
  let t = time;
  let shot = board.shots[0];
  for (shot of board.shots) {
    if (t < shot.duration) break;
    if (shot !== board.shots.at(-1)) t -= shot.duration;
  }
  const [x, y] = interpolateVector(shot.camera.path, 'position', t);
  ctx.save();
  ctx.translate(800, 450);
  const zoom = shot.camera.focalLength / 36;
  ctx.scale(zoom, zoom);
  ctx.translate(-x, -y);
  if (shot.scene === 'chart') chart(ctx, t, shot.map);
  else harbor(ctx, shot.scene === 'night', t, shot.blackout ? Math.floor(t / 2) / 7 : -1);
  for (const actor of shot.actors || []) {
    if (t < (actor.start ?? 0) || t >= (actor.end ?? Infinity)) continue;
    const [ax, ay] = interpolateVector(actor.path, 'position', t);
    const depth = actor.depth || 1;
    const blur = Math.abs(depth - shot.camera.focus);
    ctx.filter = blur ? 'blur(' + blur + 'px)' : 'none';
    drawActor(ctx, actor, ax + (x - 800) * (1 - 1 / depth), ay, t);
  }
  ctx.restore();
  ctx.fillStyle = '#07121b';
  ctx.fillRect(0, 0, 1600, shot.bars);
  ctx.fillRect(0, 900 - shot.bars, 1600, shot.bars);
  if (shot.location || shot.date) drawCard(ctx, shot);
  if (shot.news) broadcast(ctx, shot.news, t);
  if (shot.subtitle) drawSubtitle(ctx, shot.subtitle);
  const fade = shot.fade || 0;
  const opacity = fade ? 1 - Math.min(1, t / fade, (shot.duration - t) / fade) : 0;
  ctx.fillStyle = 'rgba(0,0,0,' + opacity + ')';
  ctx.fillRect(0, 0, 1600, 900);
  return shot;
}

function drawCard(ctx, shot) {
  ctx.fillStyle = '#0f2637d9';
  ctx.fillRect(78, 117, 395, 125);
  ctx.fillStyle = '#d6c398';
  ctx.fillRect(78, 117, 4, 125);
  if (shot.date) label(ctx, shot.date, 108, 158, 20, '#a9ccce');
  if (shot.location) label(ctx, shot.location, 108, 212, 40, '#fff3df', 650);
}

function drawSubtitle(ctx, [speaker, words]) {
  ctx.fillStyle = '#102535e8';
  ctx.fillRect(80, 685, 820, 87);
  label(ctx, speaker, 105, 715, 17, '#90dbc8', 700);
  label(ctx, words, 105, 751, 26);
}
