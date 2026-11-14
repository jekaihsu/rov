/* Top-down NED chart with bounded live trails, world geometry and pointer/keyboard zoom. */
import {STRINGS as S} from './strings.js';
export function createMap(canvas) {
  const ctx = canvas.getContext('2d');
  const trails = new Map();
  let world = {};
  let vehicles = [];
  let selected = '';
  let center = [0, 0];
  let scale = 8;
  let drag;
  let fitted = false;
  function point(p) {
    return [canvas.clientWidth / 2 + (p[1] - center[1]) * scale,
      canvas.clientHeight / 2 - (p[0] - center[0]) * scale];
  }
  function line(points, color, dash = []) {
    if (!points?.length) return;
    ctx.strokeStyle = color;
    ctx.setLineDash(dash);
    ctx.beginPath();
    points.forEach(function vertex(p, i) {
      const [x, y] = point(p);
      if (i) ctx.lineTo(x, y);
      else ctx.moveTo(x, y);
    });
    ctx.stroke();
    ctx.setLineDash([]);
  }
  function circle(p, radius, color) {
    const [x, y] = point(p);
    ctx.strokeStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, Math.max(2, radius * scale), 0, Math.PI * 2);
    ctx.stroke();
  }
  function obstaclePoints(o) {
    if (o.type === 'box') {
      return [[o.center[0] - o.half[0], o.center[1] - o.half[1]],
        [o.center[0] + o.half[0], o.center[1] + o.half[1]]];
    }
    if (o.type === 'wall') {
      const a = o.normal_deg * Math.PI / 180;
      return [-1, 1].map(function endpoint(sign) {
        return [o.point[0] - sign * Math.sin(a) * o.width / 2,
          o.point[1] + sign * Math.cos(a) * o.width / 2];
      });
    }
    if (o.type === 'model') {
      const a = (o.heading_deg || 0) * Math.PI / 180;
      const [lo, hi] = o.bounds_local;
      return [[lo[0], lo[1]], [lo[0], hi[1]], [hi[0], hi[1]], [hi[0], lo[1]], [lo[0], lo[1]]]
        .map(function corner(p) {
          return [o.origin[0] + p[0] * Math.cos(a) - p[1] * Math.sin(a),
            o.origin[1] + p[0] * Math.sin(a) + p[1] * Math.cos(a)];
        });
    }
    return [o.p0, o.p1].filter(Boolean);
  }
  function fit() {
    const points = [...vehicles.map(v => v.pos), ...(world.objectives || []).map(o => o.point),
      ...(world.obstacles || []).filter(o => o.kind !== 'habitat').flatMap(obstaclePoints)].filter(Boolean);
    if (!points.length) return;
    const ns = points.map(p => p[0]);
    const es = points.map(p => p[1]);
    center = [(Math.min(...ns) + Math.max(...ns)) / 2, (Math.min(...es) + Math.max(...es)) / 2];
    scale = Math.max(.3, Math.min(30, canvas.clientWidth / (Math.max(...es) - Math.min(...es) + 12),
      canvas.clientHeight / (Math.max(...ns) - Math.min(...ns) + 12)));
    fitted = true;
    draw();
  }
  function draw() {
    const w = canvas.clientWidth;
    const h = canvas.clientHeight;
    const dpr = window.devicePixelRatio || 1;
    if (canvas.width !== Math.round(w * dpr) || canvas.height !== Math.round(h * dpr)) {
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
    }
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.clearRect(0, 0, w, h);
    ctx.lineWidth = 1;
    ctx.font = '11px monospace';
    const grid = 10 ** Math.ceil(Math.log10(45 / scale));
    for (let n = Math.floor((center[0] - h / scale / 2) / grid) * grid; n < center[0] + h / scale / 2; n += grid) {
      line([[n, center[1] - w / scale], [n, center[1] + w / scale]], '#a0cde514');
    }
    for (let e = Math.floor((center[1] - w / scale / 2) / grid) * grid; e < center[1] + w / scale / 2; e += grid) {
      line([[center[0] - h / scale, e], [center[0] + h / scale, e]], '#a0cde514');
    }
    for (const o of world.obstacles || []) {
      if (o.type === 'wall' || o.type === 'model') {
        line(obstaclePoints(o), '#718b9688');
      } else if (o.p0 && o.p1) {
        ctx.lineWidth = Math.max(1, (o.radius || .1) * scale * 2);
        line([o.p0, o.p1], '#718b9655');
        ctx.lineWidth = 1;
        circle(o.p0, o.radius || .1, '#718b9688');
        circle(o.p1, o.radius || .1, '#718b9688');
      } else if (o.center && o.half) {
        const angle = (o.yaw_deg || 0) * Math.PI / 180;
        const corners = [[-1, -1], [-1, 1], [1, 1], [1, -1], [-1, -1]].map(function corner(p) {
          const n = p[0] * o.half[0];
          const e = p[1] * o.half[1];
          return [o.center[0] + n * Math.cos(angle) - e * Math.sin(angle),
            o.center[1] + n * Math.sin(angle) + e * Math.cos(angle)];
        });
        line(corners, '#718b9688');
      }
    }
    const activeVehicle = vehicles.find(v => v.id === selected);
    const objectives = activeVehicle?.score?.objectives || world.objectives || [];
    for (const [i, objective] of objectives.entries()) {
      if (!objective.point) continue;
      circle(objective.point, objective.radius || 1, objective.done ? '#5fd38a' : '#f2b84b');
      const [x, y] = point(objective.point);
      ctx.fillStyle = '#c4b584';
      const label = i === activeVehicle?.score?.current_index ? objective.label || '' : '';
      ctx.fillText(`${String(i + 1).padStart(2, '0')} ${label}`, x + 10, y - 10);
    }
    for (const v of vehicles) {
      const color = v.id === selected ? '#4fd1e0' : '#8fa6b2';
      line(trails.get(v.id), `${color}80`, [3, 5]);
      line(v.tether?.nodes, v.tether?.warn || v.tether?.broken ? '#ff5a52' : '#5fd38a88');
      const [x, y] = point(v.pos);
      ctx.save();
      ctx.translate(x, y);
      ctx.rotate((v.euler?.[2] || 0) * Math.PI / 180);
      ctx.strokeStyle = color;
      ctx.lineWidth = 2;
      ctx.beginPath();
      ctx.moveTo(0, -10);
      ctx.lineTo(7, 8);
      ctx.lineTo(0, 4);
      ctx.lineTo(-7, 8);
      ctx.closePath();
      ctx.stroke();
      ctx.restore();
      ctx.fillStyle = color;
      ctx.fillText(v.id, x + 12, y + 16);
    }
    ctx.fillStyle = '#8fa6b2';
    ctx.fillText(`${S.north} ↑`, w - 40, 24);
    ctx.fillText(`${grid} ${S.metres}`, 20, h - 20);
    ctx.strokeStyle = '#8fa6b2';
    ctx.beginPath();
    ctx.moveTo(20, h - 35);
    ctx.lineTo(20 + grid * scale, h - 35);
    ctx.stroke();
  }
  function zoom(factor) {
    scale = Math.max(.3, Math.min(80, scale * factor));
    draw();
  }
  canvas.addEventListener('wheel', function wheel(event) {
    event.preventDefault();
    zoom(event.deltaY < 0 ? 1.15 : 1 / 1.15);
  }, {passive: false});
  canvas.addEventListener('pointerdown', function down(event) {
    drag = [event.clientX, event.clientY, ...center];
    canvas.setPointerCapture(event.pointerId);
  });
  canvas.addEventListener('pointermove', function move(event) {
    if (!drag) return;
    center = [drag[2] + (event.clientY - drag[1]) / scale, drag[3] - (event.clientX - drag[0]) / scale];
    draw();
  });
  canvas.addEventListener('pointerup', function up() { drag = null; });
  canvas.addEventListener('pointercancel', function cancel() { drag = null; });
  new ResizeObserver(draw).observe(canvas);
  return {
    zoom, fit,
    reset() {
      trails.clear();
      vehicles = [];
      world = {};
      fitted = false;
      draw();
    },
    world(value) {
      world = value;
      if (!fitted) fit();
      else draw();
    },
    update(value, id) {
      vehicles = value;
      selected = id;
      for (const v of vehicles) {
        const trail = trails.get(v.id) || [];
        const last = trail.at(-1);
        if (!last || Math.hypot(last[0] - v.pos[0], last[1] - v.pos[1]) > .15) trail.push(v.pos.slice());
        if (trail.length > 1200) trail.shift();
        trails.set(v.id, trail);
      }
      for (const key of trails.keys()) if (!vehicles.some(v => v.id === key)) trails.delete(key);
      draw();
    },
  };
}
