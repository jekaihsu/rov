// Internal instructor workbench. All inputs edit the same campaign document used by the simulator.
import {labels as L} from '../training/editor_strings.js';
import {isInternalEdition} from '../training/edition.js';
import {createMenuNavigator, loadControllerDatabase} from '../menu/navigator.js';
import {drawPreview} from './preview.js';

const root = document.querySelector('#editor');
const locales = ['zh-TW', 'en', 'zh-Hans', 'ja'];
const params = new URLSearchParams(location.search);
const status = document.createElement('output');
status.setAttribute('role', 'status');
let sites,
  courses,
  doc,
  index = 0;
function el(tag, parent, text) {
  const node = document.createElement(tag);
  if (text !== undefined) node.textContent = text;
  parent?.append(node);
  return node;
}
function box(tag, parent, cls) {
  const node = el(tag, parent);
  node.className = cls;
  return node;
}
function control(parent, label, tag) {
  return el(tag, el('label', parent, label));
}
function field(parent, label, obj, key, numeric = false, onChange = null) {
  const input = control(parent, label, 'input');
  input.name = key;
  input.type = numeric ? 'number' : 'text';
  if (numeric) input.step = 'any';
  input.value = obj[key] ?? '';
  input.oninput = function edit() {
    obj[key] = numeric ? (input.value === '' ? null : input.valueAsNumber) : input.value;
    onChange?.();
  };
}
function select(parent, label, options, value, change) {
  const node = control(parent, label, 'select');
  for (const [key, text] of options) el('option', node, text).value = key;
  node.value = value;
  node.name = label;
  node.onchange = () => {
    change(node.value);
    if (!node.isConnected) {
      [...root.querySelectorAll('select')].find(replacement => replacement.name === label)?.focus();
    }
  };
  return node;
}
function button(parent, key, fn) {
  const b = el('button', parent, L[key]);
  b.dataset.action = key;
  b.onclick = () => Promise.resolve().then(fn).catch(report);
  return b;
}
function report(error) {
  status.textContent = L.invalid + ' · ' + error.message;
}
function fresh() {
  doc = {
    id: 'custom_' + crypto.randomUUID(),
    title: L.newCourse,
    scenario: 'tutorial_pool',
    mode: 'scenario_training',
    category: 'course',
    order: 0,
    nodes: [],
    strings: Object.fromEntries(locales.map((l) => [l, {}])),
    beats: [],
    instructor: {targets: [], pass_score: 75},
  };
  setSite(doc.scenario);
  addBeat();
}
function setSite(key) {
  doc.scenario = key;
  const w = sites.find((s) => s.key === key).world;
  Object.assign(doc.instructor, {
    start_pos: [...w.start_pos],
    spool_pos: [...w.spool],
    visibility_m: Math.max(1, w.scenario.visibility_m),
    tether_length: w.scenario.tether_length,
    current_kn: w.current.surface_kn,
    current_deg: w.current.surface_dir,
  });
}
function addBeat() {
  index = doc.beats.length;
  const id = 'b' + crypto.randomUUID().slice(0, 8);
  if (index) doc.beats[index - 1].next = id;
  doc.beats.push({
    id,
    next: 'done',
    limit: 60,
    idle: 15,
    hud: [],
    radio: id + '_radio',
    hint: id + '_hint',
    reminder: id + '_reminder',
  });
  doc.instructor.targets.push({kind: 'checkpoint', point: [...doc.instructor.start_pos], radius: 2, points: 10});
  for (const key of ['radio', 'hint', 'reminder']) doc.strings['zh-TW'][id + '_' + key] = '';
}
async function api(path, body) {
  const response = await fetch(
    '/api/missions' + path,
    body ? {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)} : {},
  );
  const data = await response.json();
  if (!response.ok) throw Error(data.error || response.status);
  return data;
}
async function save() {
  await api('', doc);
  courses = await api('');
  status.textContent = L.saved;
  render();
}
function render() {
  root.replaceChildren();
  const header = el('header', root);
  el('h1', header, L.editor);
  const map = el('a', header, L.map);
  const back = new URL('../', location.href);
  back.search = params;
  back.searchParams.set('menu', 'training');
  map.href = back;
  const tools = el('nav', root);
  button(tools, 'newCourse', () => {
    fresh();
    render();
  });
  select(tools, L.load, [['', '—'], ...courses.map((c) => [c.id, c.title])], '', (key) => {
    if (!key) return;
    doc = structuredClone(courses.find((c) => c.id === key));
    index = 0;
    render();
  });
  button(tools, 'save', save).className = 'primary';
  button(tools, 'exportFile', async () => {
    await api('/validate', doc);
    const a = el('a');
    a.href = URL.createObjectURL(new Blob([JSON.stringify(doc, null, 2)], {type: 'application/json'}));
    a.download = doc.id + '.json';
    a.click();
    setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  });
  const file = control(tools, L.importFile, 'input');
  file.type = 'file';
  file.accept = '.json';
  file.onchange = async () => {
    try {
      const data = JSON.parse(await file.files[0].text());
      await api('/validate', data);
      doc = data;
      index = 0;
      render();
    } catch (error) {
      report(error);
    }
  };
  button(tools, 'play', async () => {
    await save();
    for (const [k, v] of Object.entries({
      play: 1,
      mission: 'campaign',
      training: 1,
      trainingLesson: doc.id,
      chapter: doc.id,
      room: 'editor' + Date.now(),
      scenario: doc.scenario,
      nointro: 1,
      fidelity: 'real',
    }))
      back.searchParams.set(k, v);
    back.searchParams.delete('menu');
    location.href = back;
  });
  tools.append(status);
  const grid = box('div', root, 'grid');
  const env = el('section', grid);
  el('h2', env, L.env);
  field(env, L.name, doc, 'title');
  select(
    env,
    L.site,
    sites.map((s) => [s.key, L.sites[s.key] || s.name]),
    doc.scenario,
    (key) => {
      setSite(key);
      render();
    },
  );
  const cfg = doc.instructor;
  const inputs = box('div', env, 'row');
  for (const [key, label] of Object.entries({
    current_kn: 'speed',
    current_deg: 'direction',
    visibility_m: 'visibility',
    tether_length: 'length',
    pass_score: 'pass',
  }))
    field(inputs, L[label], cfg, key, true);
  function axes(parent, label, point) {
    const group = el('fieldset', parent);
    el('legend', group, label + ' (m)');
    const row = box('div', group, 'axes');
    ['N', 'E', 'D'].forEach((axis, i) => field(row, axis, point, i, true, redraw));
  }
  axes(env, L.spawn, cfg.start_pos);
  axes(env, L.spool, cfg.spool_pos);
  const right = el('section', grid);
  el('h2', right, L.plan);
  const views = box('div', right, 'views');
  const canvases = [L.top, L.side].map((label) => {
    const figure = el('figure', views);
    el('figcaption', figure, label);
    return el('canvas', figure);
  });
  function redraw() {
    const w = sites.find((s) => s.key === doc.scenario).world;
    canvases.forEach((c, i) =>
      drawPreview(c, w, cfg, index, !!i, (point) => {
        cfg.targets[index].point = point;
        render();
      }),
    );
  }
  redraw();
  el('p', right, L.place);
  const row = box('div', right, 'row');
  select(
    row,
    L.beats,
    doc.beats.map((b, i) => [i, String(i + 1)]),
    index,
    (k) => {
      index = Number(k);
      render();
    },
  );
  button(row, 'add', () => {
    addBeat();
    render();
  });
  button(row, 'remove', () => {
    doc.beats.splice(index, 1);
    cfg.targets.splice(index, 1);
    doc.beats.forEach((b, i) => {
      b.next = doc.beats[i + 1]?.id || 'done';
    });
    index = Math.min(index, doc.beats.length - 1);
    render();
  }).disabled = doc.beats.length === 1;
  const t = cfg.targets[index];
  select(
    row,
    L.kind,
    ['target', 'photo', 'checkpoint'].map((k) => [k, L[k]]),
    t.kind,
    (k) => {
      t.kind = k;
      render();
    },
  );
  axes(right, L[t.kind], t.point);
  const settings = box('div', right, 'row');
  const beat = doc.beats[index];
  for (const key of ['radius', 'points', 'limit', 'idle']) field(settings, L[key], key in t ? t : beat, key, true);
  for (const lang of locales) {
    const details = el('details', right);
    details.open = lang === 'zh-TW';
    el('summary', details, lang);
    const fields = box('div', details, 'row');
    for (const key of ['radio', 'hint', 'reminder']) {
      beat[key] ??= beat.id + '_' + key;
      doc.strings[lang] ??= {};
      doc.strings[lang][beat[key]] ??= '';
      field(fields, L[key], doc.strings[lang], beat[key]);
    }
  }
}
if (isInternalEdition()) {
  try {
    [sites, courses] = await Promise.all([api('/sites'), api('')]);
    fresh();
    render();
    const nav = createMenuNavigator({
      database: await loadControllerDatabase(),
      handlers: {
        scope: () => root,
        adjustNumber(input, sign) {
          input.value = Math.round(((input.valueAsNumber || 0) + sign * 0.5) * 10) / 10;
          input.dispatchEvent(new Event('input', {bubbles: true}));
        },
      },
    });
    nav.setActive(true);
    nav.start();
  } catch (error) {
    root.append(status);
    report(error);
  }
} else location.replace('../');
