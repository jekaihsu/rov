// The launch flow's own screens: title, main menu, mode, vehicle hangar, dive site and briefing.
// Each builder returns {element, enter()}; navigation, data and the 3D stage come from the shared context.
import { STICKERS } from '../vehicle_stickers.js';
import { getFidelity } from '../fidelity.js';
import { PROCEDURE_ITEM } from '../procedure/fidelity_item.js';
import { MODES, siteFacts, supportsMode, vehicleSpecs } from './catalogue.js';
import { briefingTimeLimit } from '../play/mission_text.js';
import { lengthIn, lengthUnit } from '../prefs/display.js';
import { introForLaunch } from './preferences.js';

const STRINGS = {
  title: 'ROV Solution',
  // The player works for YX, which also issues the in-game licences (docs/design/game-plan.md §9).
  company: 'YX',
  tagline: 'YX 水下工程 · ROV 操作員',
  pressStart: '開始',
  version: '開發版 0.3',
  entries: {
    dive: ['開始潛航', '選擇玩法、載具與海域，從水面下潛。'],
    story: ['劇情與教學', '加入 YX 工作隊：從水池練習開始，接下港灣與船殼巡檢。'],
    contracts: ['工程委託', '接 YX 派發的巡檢、回收與部署委託；下水後在右上任務卡接案。'],
    training: ['訓練情境', '事故演練與依難度排列的場景訓練。'],
    multiplayer: ['多人', '建立或加入房間，最多三人共用同一片海域。'],
    collection: ['圖鑑與收藏', '照片、生物圖鑑與工程紀錄。'],
    settings: ['設定', '擬真程度、控制、音訊、畫質與介面。'],
  },
  quick: '快速開始',
  quickNone: '完成一次下水後，可一鍵沿用上次設定。',
  modesTitle: '選擇玩法',
  modes: {
    expedition: ['海洋探索與工程', '探索海域、拍攝生物與自由接案；回收與部署需要機械臂。', '1–3 人'],
    free_explore: ['自由探索', '不計時、不扣分，練習操控、機械臂與標記。', '1–3 人'],
    inspection_coop: ['協作巡檢', '分工靠近三個站點，穩定懸停後拍照，12 分鐘內完成。', '1–3 人'],
    scenario_training: ['場景訓練', '照各場景原本的訓練目標、時限與評分進行。', '1 人起'],
  },
  hangarTitle: '載具',
  provisional: '暫定',
  provisionalHelp: '此機型參數尚未實測，數值為暫定估算，待實測補齊。',
  estimated: '工程估算',
  numbers: { mass: '質量', thrusters: '推進器', speed: '前進極速', arm: '機械臂' },
  units: { mass: 'kg', thrusters: '具', speed: 'kn' },
  armYes: '有',
  armNo: '無',
  bars: { speed: '速度', thrust: '總推力', yaw: '轉向', axes: '可控自由度' },
  sticker: '機身貼紙',
  next: '下一步',
  sitesTitle: '潛航海域',
  sitesMore: '共 {n} 處海域 · 左右移動瀏覽',
  depth: '海床',
  visibility: '能見度',
  current: '最大洋流',
  notForMode: '此玩法不提供這片海域',
  briefingTitle: '下水簡報',
  briefingNumbers: { depth: '海床深度', visibility: '能見度', current: '最大洋流', tether: '纜長', time: '時限' },
  units2: { kn: 'kn', min: '分' },
  objectives: '任務目標',
  noObjectives: '自由航行，沒有指定目標。',
  goalsTitle: '玩法',
  modeGoals: {
    free_explore: ['自由航行：不計時、不扣分。', '練習操控、機械臂與標記，隨時可以返回主選單。'],
    expedition: ['探索海域、拍攝生物登錄圖鑑。', '下水後可在任務卡接取巡檢、回收或部署委託。'],
    inspection_coop: ['分工靠近三個巡檢站點（下水後標出）。', '在站點低速穩定 3 秒後拍照。'],
  },
  hostNote: '加入既有房間時，以房主的場景與玩法為準。',
  room: '房間',
  intro: '下水動畫',
  procedure: '潛前檢查與下水流程',
  procedureOff: '關閉時直接從水中開始，略過潛前檢查（擬真設定「下水流程」為完整作業時）。',
  introOff: '關閉時直接從水中開始。',
  launch: '下水',
  chapter: '章節',
  campaign: '劇情與教學',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function screen(name, title) {
  const root = element('section', 'menu-screen');
  root.dataset.screen = name;
  root.setAttribute('aria-label', title || name);
  return root;
}

function fixed(value, digits = 1) {
  return Number.isFinite(value) ? value.toFixed(digits).replace(/\.0$/, '') : '—';
}

// A length in the unit chosen in settings (metres or feet); unknown stays unknown.
function metres(value) {
  return Number.isFinite(value) ? lengthIn(value) : value;
}

// Seabed depth as one number, or a range when the rounded ends differ.
function depthText(facts) {
  const shallow = fixed(metres(facts.shallow), 0);
  const deep = fixed(metres(facts.deep), 0);
  return shallow === deep ? deep : `${shallow}–${deep}`;
}

// A large tabular read-out: small label above, big number, small unit.
export function readout(label, value, unit = '') {
  const block = element('div', 'menu-readout');
  block.append(element('span', 'menu-label', label));
  const line = element('span', 'menu-readout-value');
  line.append(element('b', '', value));
  if (unit) line.append(element('small', '', unit));
  block.append(line);
  return block;
}

export function buildTitle(ctx) {
  const root = screen('title', STRINGS.title);
  const block = element('div', 'menu-title-block');
  block.append(element('p', 'menu-kicker', STRINGS.tagline));
  block.append(element('h1', 'menu-title', STRINGS.title));
  const start = element('button', 'menu-press');
  start.type = 'button';
  start.id = 'titleStart';
  start.dataset.autofocus = '';
  const cap = element('span', 'menu-press-cap');
  cap.dataset.promptAction = 'accept';
  start.append(cap, element('span', '', STRINGS.pressStart));
  start.addEventListener('click', function begin() {
    ctx.go('main');
  });
  block.append(start);
  root.append(block, element('p', 'menu-version', STRINGS.version));
  return { element: root, pose: 'title', prompts: [['accept', STRINGS.pressStart]] };
}

export function buildMain(ctx) {
  const root = screen('main', STRINGS.title);
  const list = element('nav', 'menu-list');
  const describe = element('p', 'menu-entry-help');
  const targets = {
    dive: function dive() {
      ctx.startRoute('dive');
    },
    story: function story() {
      ctx.openTraining('story');
    },
    contracts: function contracts() {
      ctx.openContracts();
    },
    training: function training() {
      ctx.openTraining('drills');
    },
    multiplayer: function multiplayer() {
      ctx.go('multiplayer');
    },
    collection: function collection() {
      ctx.openCollection();
    },
    settings: function settings() {
      ctx.go('settings');
    },
  };
  const ids = { collection: 'menuCollection' };
  Object.entries(STRINGS.entries).forEach(function addEntry([key, [label, help]], index) {
    const button = element('button', 'menu-entry');
    button.type = 'button';
    button.id = ids[key] || `entry-${key}`;
    button.dataset.entry = key;
    if (index === 0) button.dataset.autofocus = '';
    button.append(element('span', 'menu-entry-index', String(index + 1).padStart(2, '0')));
    button.append(element('span', 'menu-entry-label', label));
    button.addEventListener('click', targets[key]);
    for (const type of ['focus', 'pointerenter']) {
      button.addEventListener(type, function showHelp() {
        describe.textContent = help;
      });
    }
    list.append(button);
  });
  const quick = element('button', 'menu-quick');
  quick.type = 'button';
  quick.id = 'quickStart';
  const quickText = element('span', 'menu-quick-detail');
  quick.append(element('span', 'menu-label', STRINGS.quick), quickText);
  quick.addEventListener('click', function quickStart() {
    ctx.quickStart();
  });
  root.append(list, describe, quick);
  function enter() {
    ctx.choice.multiplayer = false;
    const summary = ctx.lastSummary();
    quick.disabled = !summary;
    quickText.textContent = summary || STRINGS.quickNone;
    describe.textContent = STRINGS.entries.dive[1];
  }
  return { element: root, pose: 'main', enter };
}

export function buildModes(ctx) {
  const root = screen('modes', STRINGS.modesTitle);
  root.append(element('h2', 'menu-heading', STRINGS.modesTitle));
  const grid = element('div', 'menu-cards menu-mode-cards');
  const buttons = [];
  for (const mode of MODES) {
    const [title, line, players] = STRINGS.modes[mode];
    const card = element('button', 'menu-card');
    card.type = 'button';
    card.dataset.mode = mode;
    card.append(element('span', 'menu-card-players', players));
    card.append(element('strong', 'menu-card-title', title));
    card.append(element('span', 'menu-card-line', line));
    card.addEventListener('click', function chooseMode() {
      ctx.chooseMode(mode);
    });
    buttons.push(card);
    grid.append(card);
  }
  root.append(grid);
  function enter() {
    for (const card of buttons) card.setAttribute('aria-pressed', String(card.dataset.mode === ctx.choice.mission));
  }
  return { element: root, pose: 'modes', enter };
}

function bar(label, value, text) {
  const row = element('div', 'menu-bar');
  row.append(element('span', 'menu-label', label));
  const track = element('span', 'menu-bar-track');
  const fill = element('i');
  fill.style.width = `${Math.round(Math.max(0, Math.min(1, value)) * 100)}%`;
  track.append(fill);
  row.append(track, element('span', 'menu-bar-value', text));
  return row;
}

export function buildHangar(ctx) {
  const root = screen('hangar', STRINGS.hangarTitle);
  const side = element('div', 'menu-hangar');
  side.append(element('h2', 'menu-heading', STRINGS.hangarTitle));
  const picker = element('div', 'menu-vehicles');
  picker.setAttribute('role', 'radiogroup');
  const name = element('h3', 'menu-vehicle-name');
  const marker = element('span', 'menu-provisional', STRINGS.provisional);
  marker.title = STRINGS.provisionalHelp;
  const note = element('p', 'menu-help');
  const numbers = element('div', 'menu-readouts');
  const bars = element('div', 'menu-bars');
  const stickers = element('div', 'menu-stickers');
  stickers.setAttribute('role', 'radiogroup');
  stickers.setAttribute('aria-label', STRINGS.sticker);
  for (const vehicle of ctx.data.vehicles) {
    const button = element('button', 'menu-chip');
    button.type = 'button';
    button.dataset.vehicle = vehicle.id;
    button.textContent = vehicle.name;
    button.addEventListener('click', function chooseVehicle() {
      ctx.selectModel(vehicle.id);
      render();
    });
    picker.append(button);
  }
  for (const [preset, label] of Object.entries(STICKERS)) {
    const button = element('button', 'menu-chip menu-chip-small');
    button.type = 'button';
    button.dataset.sticker = preset;
    button.textContent = label;
    button.addEventListener('click', function chooseSticker() {
      ctx.selectSticker(preset);
      render();
    });
    stickers.append(button);
  }
  const next = element('button', 'menu-next');
  next.type = 'button';
  next.id = 'hangarNext';
  next.textContent = STRINGS.next;
  next.addEventListener('click', function proceed() {
    ctx.afterHangar();
  });
  const title = element('div', 'menu-vehicle-title');
  title.append(name, marker);
  const stickerTitle = element('h3', 'menu-label', STRINGS.sticker);
  side.append(picker, title, note, numbers, bars, stickerTitle, stickers, next);
  root.append(side);
  function render() {
    const vehicle = ctx.data.vehicles.find(function chosen(entry) {
      return entry.id === ctx.choice.model;
    }) || ctx.data.vehicles[0];
    if (!vehicle) return;
    const specs = vehicleSpecs(vehicle);
    name.textContent = vehicle.title || vehicle.name;
    marker.hidden = !specs.provisional;
    const caveat = specs.provisional ? STRINGS.provisionalHelp : STRINGS.estimated;
    note.textContent = [vehicle.detail, caveat].filter(Boolean).join(' · ');
    numbers.replaceChildren(
      readout(STRINGS.numbers.mass, fixed(specs.mass, 1), STRINGS.units.mass),
      readout(STRINGS.numbers.thrusters, String(specs.thrusters), STRINGS.units.thrusters),
      readout(STRINGS.numbers.speed, fixed(specs.speedKn, 1), STRINGS.units.speed),
      readout(STRINGS.numbers.arm, specs.arm ? STRINGS.armYes : STRINGS.armNo),
    );
    bars.replaceChildren(...Object.entries(STRINGS.bars).map(function makeBar([key, label]) {
      return bar(label, specs.bars[key], specs.values[key]);
    }));
    for (const button of picker.children) {
      button.setAttribute('aria-pressed', String(button.dataset.vehicle === vehicle.id));
    }
    for (const button of stickers.children) {
      button.setAttribute('aria-pressed', String(button.dataset.sticker === ctx.choice.sticker));
    }
  }
  root.addEventListener('pointerdown', function grab(event) {
    if (event.target !== root) return;
    let x = event.clientX;
    root.setPointerCapture(event.pointerId);
    function drag(moveEvent) {
      ctx.stage.rotate((moveEvent.clientX - x) / 40, 0.05);
      x = moveEvent.clientX;
    }
    function release() {
      root.removeEventListener('pointermove', drag);
    }
    root.addEventListener('pointermove', drag);
    root.addEventListener('pointerup', release, { once: true });
  });
  return { element: root, pose: 'hangar', enter: render, rotatable: true };
}

function siteCard(scene, ctx) {
  const facts = siteFacts(scene);
  const card = element('button', 'menu-site');
  card.type = 'button';
  card.dataset.site = scene.key;
  const media = element('span', 'menu-site-media');
  const image = element('img');
  image.alt = '';
  image.loading = 'lazy';
  image.src = `menu/previews/${scene.key}.jpg`;
  image.addEventListener('error', function noPreview() {
    image.remove();
  });
  media.append(image);
  const body = element('span', 'menu-site-body');
  body.append(element('strong', 'menu-card-title', scene.name));
  const range = depthText(facts);
  const numbers = element('span', 'menu-site-numbers');
  numbers.append(
    readout(STRINGS.depth, range, lengthUnit()),
    readout(STRINGS.visibility, fixed(metres(facts.visibility), 0), lengthUnit()),
    readout(STRINGS.current, fixed(facts.current, 1), 'kn'),
  );
  body.append(numbers);
  const tags = element('span', 'menu-tags');
  for (const activity of facts.activities) tags.append(element('span', 'menu-tag', activity));
  body.append(tags);
  const unavailable = element('span', 'menu-site-note', STRINGS.notForMode);
  body.append(unavailable);
  card.append(media, body);
  card.addEventListener('click', function chooseSite() {
    ctx.chooseSite(scene.key);
  });
  card.addEventListener('focus', function previewSite() {
    ctx.previewScene(scene.key);
  });
  card.addEventListener('pointerenter', function hoverSite() {
    ctx.previewScene(scene.key);
  });
  return card;
}

export function buildSites(ctx) {
  const root = screen('sites', STRINGS.sitesTitle);
  root.append(element('h2', 'menu-heading', STRINGS.sitesTitle));
  const count = STRINGS.sitesMore.replace('{n}', String(ctx.data.sites.length));
  root.append(element('p', 'menu-help menu-site-count', count));
  const rail = element('div', 'menu-site-rail');
  const cards = [];
  root.append(rail);
  function enter() {
    // Rebuilt on entry so the numbers follow the unit setting.
    cards.splice(0, cards.length, ...ctx.data.sites.map(function makeCard(scene) {
      return siteCard(scene, ctx);
    }));
    // Sites the chosen mode offers come first; the others stay visible but disabled.
    const ordered = [...cards].sort(function availableFirst(a, b) {
      const mode = ctx.choice.mission;
      return Number(!supportsMode(ctx.sceneFor(a.dataset.site), mode))
        - Number(!supportsMode(ctx.sceneFor(b.dataset.site), mode));
    });
    rail.replaceChildren(...ordered);
    for (const card of cards) {
      const scene = ctx.sceneFor(card.dataset.site);
      const allowed = supportsMode(scene, ctx.choice.mission);
      card.disabled = !allowed;
      card.classList.toggle('unavailable', !allowed);
      card.setAttribute('aria-pressed', String(card.dataset.site === ctx.choice.scenario));
      if (card.dataset.site === ctx.choice.scenario && allowed) card.dataset.autofocus = '';
      else delete card.dataset.autofocus;
    }
  }
  return { element: root, pose: 'sites', enter };
}

export function buildBriefing(ctx) {
  const root = screen('briefing', STRINGS.briefingTitle);
  const form = element('form', 'menu-briefing');
  form.id = 'launchForm';
  form.noValidate = true;
  const kicker = element('p', 'menu-kicker');
  const heading = element('h2', 'menu-heading menu-heading-large');
  const brief = element('p', 'menu-brief');
  const numbers = element('div', 'menu-readouts');
  const objectivesTitle = element('h3', 'menu-label', STRINGS.objectives);
  const objectives = element('ol', 'menu-objectives');
  const note = element('p', 'menu-help');
  const introRow = element('label', 'menu-toggle menu-toggle-inline');
  introRow.htmlFor = 'menuIntro';
  const introText = element('span', 'menu-toggle-text');
  const introLabel = element('strong', '', STRINGS.intro);
  const introHelp = element('small', '', STRINGS.introOff);
  introText.append(introLabel, introHelp);
  // The same switch decides ?nointro, which also skips the pre-dive procedure when the fidelity item asks for it.
  function describeLaunch() {
    const full = getFidelity().get(PROCEDURE_ITEM) === 'full';
    introLabel.textContent = full ? STRINGS.procedure : STRINGS.intro;
    introHelp.textContent = full ? STRINGS.procedureOff : STRINGS.introOff;
  }
  getFidelity().subscribe(describeLaunch);
  describeLaunch();
  const intro = element('input');
  intro.type = 'checkbox';
  intro.id = 'menuIntro';
  intro.addEventListener('change', function toggleIntro() {
    ctx.choice.intro = intro.checked;
  });
  const introSwitch = element('span', 'menu-switch');
  introRow.append(introText, intro, introSwitch);
  const start = element('button', 'menu-start');
  start.type = 'submit';
  start.id = 'startDive';
  start.dataset.autofocus = '';
  const startCap = element('span', 'menu-press-cap');
  startCap.dataset.promptAction = 'accept';
  start.append(startCap, element('span', '', STRINGS.launch));
  const actions = element('div', 'menu-launch-actions');
  actions.append(introRow, start);
  const left = element('div', 'menu-briefing-main');
  left.append(kicker, heading, brief, numbers, objectivesTitle, objectives, note);
  form.append(left, actions);
  form.addEventListener('submit', function submit(event) {
    event.preventDefault();
    ctx.choice.intro = intro.checked;
    ctx.launch();
  });
  root.append(form);
  function enter() {
    const scene = ctx.sceneFor(ctx.choice.scenario);
    const facts = scene ? siteFacts(scene) : null;
    const vehicle = ctx.data.vehicles.find(function chosen(entry) {
      return entry.id === ctx.choice.model;
    });
    const chapter = ctx.choice.mission === 'campaign' ? ctx.chapterFor(ctx.choice.chapter) : null;
    const modeName = chapter ? STRINGS.campaign : STRINGS.modes[ctx.choice.mission]?.[0] || '';
    // The room code only matters to players who share one; a solo dive does not show it.
    const room = ctx.choice.multiplayer ? `${STRINGS.room} ${ctx.choice.room}` : '';
    kicker.textContent = [modeName, vehicle?.title || vehicle?.name, room].filter(Boolean).join(' · ');
    heading.textContent = chapter ? chapter.title : facts?.name || ctx.choice.scenario;
    brief.textContent = chapter?.outline || facts?.brief || '';
    numbers.replaceChildren();
    if (facts) {
      const depth = depthText(facts);
      numbers.append(
        readout(STRINGS.briefingNumbers.depth, depth, lengthUnit()),
        readout(STRINGS.briefingNumbers.visibility, fixed(metres(facts.visibility), 0), lengthUnit()),
        readout(STRINGS.briefingNumbers.current, fixed(facts.current, 1), STRINGS.units2.kn),
        readout(STRINGS.briefingNumbers.tether, fixed(metres(facts.tether), 0), lengthUnit()),
      );
      const limit = briefingTimeLimit(ctx.choice.mission, facts);
      if (limit && !chapter) {
        numbers.append(readout(STRINGS.briefingNumbers.time, fixed(limit / 60, 0), STRINGS.units2.min));
      }
    }
    // Only scenario training plays the scene's own objectives; the other modes say what the mode is about.
    const goals = chapter ? null : STRINGS.modeGoals[ctx.choice.mission];
    const labels = goals || (scene?.world?.objectives || []).map(function label(objective) {
      return objective.label;
    }).filter(Boolean).slice(0, 5);
    objectives.replaceChildren(...labels.map(function item(text) {
      return element('li', '', text);
    }));
    if (!labels.length) objectives.append(element('li', 'menu-help', STRINGS.noObjectives));
    objectivesTitle.textContent = goals ? STRINGS.goalsTitle : STRINGS.objectives;
    objectivesTitle.hidden = !!chapter;
    objectives.hidden = !!chapter;
    note.textContent = ctx.choice.multiplayer ? STRINGS.hostNote : '';
    intro.checked = introForLaunch(ctx.choice, getFidelity().get(PROCEDURE_ITEM) === 'full');
    ctx.previewScene(ctx.choice.scenario);
  }
  return { element: root, pose: 'briefing', enter };
}
