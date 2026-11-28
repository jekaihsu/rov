// Orthographic plan and oblique projections share one NED placement plane at the selected depth.
export function drawPreview(canvas, world, cfg, active, oblique, move) {
  const ctx = canvas.getContext('2d');
  const size = 480;
  canvas.width = canvas.height = size;
  const extent = Math.min(
    500,
    Math.max(
      20,
      world.seabed_depth,
      ...[cfg.start_pos, cfg.spool_pos, ...cfg.targets.map((t) => t.point)].flat().map((v) => Math.abs(v) || 0),
    ),
  );
  const scale = size / (3.5 * extent);
  function project([n, e, d]) {
    return oblique
      ? [240 + (e + n) * 0.7 * scale, 180 + ((e - n) * 0.35 + d) * scale]
      : [240 + e * scale, 240 - n * scale];
  }
  function line(a, b, color, width = 1) {
    ctx.strokeStyle = color;
    ctx.lineWidth = width;
    ctx.beginPath();
    ctx.moveTo(...project(a));
    ctx.lineTo(...project(b));
    ctx.stroke();
  }
  for (let k = -extent; k <= extent; k += 5) {
    line([k, -extent, world.seabed_depth], [k, extent, world.seabed_depth], '#25444a');
    line([-extent, k, world.seabed_depth], [extent, k, world.seabed_depth], '#25444a');
  }
  function marker(pos, color, label) {
    const [x, y] = project(pos);
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.arc(x, y, 5, 0, 2 * Math.PI);
    ctx.fill();
    ctx.font = '16px system-ui';
    ctx.fillText(label, x + 8, y - 4);
  }
  function outline(origin, lo, hi, yaw = 0) {
    const a = (yaw * Math.PI) / 180;
    const points = Array.from({length: 8}, (_, i) => {
      const n = (i & 1 ? hi : lo)[0];
      const e = (i & 2 ? hi : lo)[1];
      return [
        origin[0] + n * Math.cos(a) - e * Math.sin(a),
        origin[1] + e * Math.cos(a) + n * Math.sin(a),
        (origin[2] || 0) + (i & 4 ? hi : lo)[2],
      ];
    });
    points.forEach((p, i) => {
      for (const mask of [1, 2, 4]) if (!(i & mask)) line(p, points[i | mask], '#65898b', 1.5);
    });
  }
  for (const o of world.obstacles) {
    if (o.p0) line(o.p0, o.p1, '#69878b', Math.max(2, 2 * o.radius * scale));
    else if (o.half)
      outline(
        o.center,
        o.half.map((x) => -x),
        o.half,
        o.yaw_deg,
      );
    else if (o.bounds_local) outline(o.origin, ...o.bounds_local, o.heading_deg);
    else if (o.type === 'wall') {
      outline(
        [o.point[0], o.point[1], 0],
        [0, -o.width / 2, o.top],
        [0, o.width / 2, world.seabed_depth],
        o.normal_deg,
      );
    } else if (o.type === 'ship_hull') {
      outline(
        o.center,
        [-o.length / 2, -o.beam / 2, o.top],
        [o.length / 2, o.beam / 2, o.top + o.draft],
        o.yaw_deg,
      );
    } else marker(o.point, '#647f81', '');
  }
  line(cfg.spool_pos, cfg.start_pos, '#9fb6b9');
  marker(cfg.spool_pos, '#c1d5e1', 'S');
  marker(cfg.start_pos, '#88d3c0', 'ROV');
  cfg.targets.forEach((t, i) => marker(t.point, i === active ? '#ffd584' : '#edf3ef', String(i + 1)));
  canvas.onclick = function place(event) {
    const rect = canvas.getBoundingClientRect();
    const x = (((event.clientX - rect.left) * size) / rect.width - 240) / scale;
    const y = (((event.clientY - rect.top) * size) / rect.height - (oblique ? 180 : 240)) / scale;
    const d = cfg.targets[active].point[2];
    const n = oblique ? (x / 0.7 - (y - d) / 0.35) / 2 : -y;
    const e = oblique ? x / 0.7 - n : x;
    move([Math.round(n * 10) / 10, Math.round(e * 10) / 10, d]);
  };
}
