// Self-contained SVG plots in physical units, shared by replay and printable report.
import {channels} from './dive_record.js';
import {STRINGS as S} from './dive_strings.js';

const units = ['m', '°', 'm/s', 'N', 'm'];
const blue = '#1475a4';
const ns = 'http://www.w3.org/2000/svg';

function svg(tag, attrs) {
  const node = document.createElementNS(ns, tag);
  for (const [key, value] of Object.entries(attrs)) node.setAttribute(key, value);
  return node;
}

function extent(values) {
  let lo = Infinity;
  let hi = -Infinity;
  for (const v of values) {
    lo = Math.min(lo, v);
    hi = Math.max(hi, v);
  }
  return Number.isFinite(lo) ? [lo, hi] : [0, 1];
}

function plotLine(chart, points, stroke, width = 2) {
  chart.append(svg('polyline', {points: points.join(' '), stroke, 'stroke-width': width, fill: 'none'}));
}

function label(parent, tag, text) {
  const node = document.createElement(tag);
  node.textContent = text;
  parent.append(node);
  return node;
}

export function drawPlots(parent, record, world) {
  const {samples, cable} = record;
  const start = samples[0]?.t ?? 0;
  const duration = (samples.at(-1)?.t ?? start) - start;
  const grid = document.createElement('section');
  grid.className = 'dive-plots';
  parent.append(grid);
  channels.forEach(function channel(key, i) {
    const figure = document.createElement('figure');
    grid.append(figure);
    let previous = null;
    const series = samples.map(function ordinate(row) {
      let value = row[key];
      if (!Number.isFinite(value)) return null;
      // Use a continuous bearing through north; the CSV keeps the recorded compass bearing.
      if (key === 'heading' && previous != null) value += 360 * Math.round((previous - value) / 360);
      previous = value;
      return value;
    });
    const values = series.filter(Number.isFinite);
    const [lo, hi] = extent(values);
    const range = values.length ? lo.toFixed(1) + '–' + hi.toFixed(1) + ' ' + units[i] : S.noData;
    label(figure, 'figcaption', S[key] + ' · ' + range);
    const chart = svg('svg', {viewBox: '0 0 240 52', role: 'img', 'aria-label': S[key]});
    figure.append(chart);
    plotLine(chart, ['2,2', '2,50', '238,50'], '#a7b9bd', 1);
    let segment = [];
    for (const [index, row] of samples.entries()) {
      if (Number.isFinite(series[index])) {
        const x = 2 + 236 * (row.t - start) / (duration || 1);
        const y = 48 - 44 * (series[index] - lo) / (hi - lo || 1);
        segment.push(x.toFixed(2) + ',' + y.toFixed(2));
      } else {
        plotLine(chart, segment, blue);
        segment = [];
      }
    }
    plotLine(chart, segment, blue);
    label(figure, 'small', S.time + ' · 0–' + duration.toFixed(1) + ' s');
  });
  const map = document.createElement('figure');
  grid.append(map);
  label(map, 'figcaption', S.map);
  const track = samples.map(row => row.pos).filter(Boolean);
  const route = cable || [];
  const structures = world?.obstacles || [];
  const points = [...track, ...route];
  if (!points.length) {
    for (const ob of structures) points.push(...[ob.p0, ob.p1, ob.center, ob.point].filter(Boolean));
  }
  const [west, east] = extent(points.map(p => p[1]));
  const [south, north] = extent(points.map(p => p[0]));
  const scale = Math.min(210 / (east - west + 6), 80 / (north - south + 6));
  const xy = p => [120 + (p[1] - (east + west) / 2) * scale, 52 - (p[0] - (north + south) / 2) * scale];
  const chart = svg('svg', {viewBox: '0 0 240 104', role: 'img', 'aria-label': S.map});
  map.append(chart);
  for (const ob of structures) {
    if (ob.p0 && ob.p1) {
      const ends = [xy(ob.p0), xy(ob.p1)];
      const radius = Math.max(0.7, (ob.radius || 0) * scale);
      plotLine(chart, ends, '#9eaaad', 2 * radius);
      chart.append(svg('circle', {cx: ends[0][0], cy: ends[0][1], r: radius, fill: '#9eaaad'}));
    } else if (ob.point && ob.width) {
      const angle = ob.normal_deg * Math.PI / 180;
      const ends = [-0.5, 0.5].map(k => xy([ob.point[0] - k * ob.width * Math.sin(angle),
        ob.point[1] + k * ob.width * Math.cos(angle)]));
      plotLine(chart, ends, '#9eaaad');
    } else if (ob.type === 'snag' && ob.point) {
      const [cx, cy] = xy(ob.point);
      chart.append(svg('circle', {cx, cy, r: Math.max(1, ob.radius * scale), fill: '#9eaaad'}));
    } else if (ob.type === 'ship_hull' && ob.center) {
      const [x, y] = xy(ob.center);
      chart.append(svg('ellipse', {rx: ob.beam * scale / 2, ry: ob.length * scale / 2,
        transform: `translate(${x} ${y}) rotate(${ob.yaw_deg || 0})`, fill: '#9eaaad'}));
    } else if (ob.center && ob.half) {
      const [x, y] = xy(ob.center);
      const w = ob.half[1] * scale;
      const h = ob.half[0] * scale;
      chart.append(svg('rect', {x: -w, y: -h, width: 2*w, height: 2*h,
        transform: `translate(${x} ${y}) rotate(${ob.yaw_deg || 0})`, fill: '#9eaaad'}));
    }
  }
  plotLine(chart, route.map(xy), '#c4771c');
  plotLine(chart, track.map(xy), blue);
  const northLabel = svg('text', {x: 4, y: 14, fill: '#193943', 'font-size': 12});
  northLabel.textContent = '↑ N';
  chart.append(northLabel);
  label(map, 'small', S.legend);
}
