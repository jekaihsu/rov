// The launch flow's own screens: title, main menu, mode, vehicle hangar, dive site and briefing.
// Each builder returns {element, enter()}; navigation, data and the 3D stage come from the shared context.
// Big-picture layout (big_picture.js): the scene is the screen, one large title, a few numbers, one primary
// button, choices as image tiles; longer text waits behind 明細.
import { STICKERS } from '../vehicle_stickers.js';
import { getFidelity } from '../fidelity.js';
import { PROCEDURE_ITEM } from '../procedure/fidelity_item.js';
import { MODES, siteFacts, supportsMode, vehicleSpecs } from './catalogue.js';
import { briefingTimeLimit } from '../play/mission_text.js';
import { lengthIn, lengthUnit } from '../prefs/display.js';
import { introForLaunch } from './preferences.js';
import {
  createDetailSheet,
  createHero,
  createTileStrip,
  detailButton,
  linkButton,
  primaryButton,
  tile,
} from './big_picture.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.screens', {
  title: 'ROV Solution',
  // The player works for YX, which also issues the in-game licences (docs/design/game-plan.md §9).
  company: 'YX',
  tagline: 'YX 水下工程 · ROV 操作員',
  pressStart: '開始',
  version: '開發版 0.3',
  // [label, tooltip]: the screen shows the label only; the description is there on demand.
  entries: {
    dive: ['開始潛航', '選擇玩法、載具與海域，從水面下潛。'],
    story: ['劇情與教學', '加入 YX 工作隊：從水池練習開始，接下港灣與船殼巡檢。'],
    contracts: ['YX 委託看板', 'YX 派發的工單：碼頭、船殼、港內搜尋；交出成果領報酬、累積時數、考執照。'],
    shop: ['YX 裝備部', '用報酬添購真實配件（雷射比例尺、聲納、探針…）與機身外觀；配件讓你接更多種工單。'],
    training: ['訓練情境', '事故演練與依難度排列的場景訓練。'],
    multiplayer: ['多人', '建立或加入房間，最多三人共用同一片海域。'],
    collection: ['圖鑑與收藏', '照片、生物圖鑑與工程紀錄。'],
    settings: ['設定', '擬真程度、控制、音訊、畫質與介面。'],
  },
  quick: '快速開始',
  quickNone: '完成一次下水後，可一鍵沿用上次設定。',
  modesTitle: '選擇玩法',
  // [title, description (tooltip), players, short chips]
  modes: {
    expedition: ['海洋探索與工程', '探索海域、拍攝生物與自由接案；回收與部署需要機械臂。', '1–3', ['生態攝影', '自由接案']],
    free_explore: ['自由探索', '不計時、不扣分，練習操控、機械臂與標記。', '1–3', ['不計時', '不扣分']],
    inspection_coop: ['協作巡檢', '分工靠近三個站點，穩定懸停後拍照，12 分鐘內完成。', '1–3', ['三個站點', '限時 12 分']],
    scenario_training: ['場景訓練', '照各場景原本的訓練目標、時限與評分進行。', '1+', ['計時', '評分']],
  },
  players: '人數',
  choose: '選擇',
  hangarTitle: '載具',
  provisional: '暫定',
  provisionalHelp: '此機型參數尚未實測，數值為暫定估算，待實測補齊。',
  estimated: '工程估算',
  numbers: { mass: '質量', thrusters: '推進器', speed: '極速', arm: '機械臂' },
  units: { mass: 'kg', thrusters: '具', speed: 'kn' },
  armYes: '有',
  armNo: '無',
  bars: { speed: '速度', thrust: '總推力', yaw: '轉向', axes: '可控自由度' },
  about: '簡介',
  performance: '性能',
  sticker: '貼紙',
  next: '下一步',
  sitesTitle: '潛航海域',
  sitesCountOne: '{n} 處',
  sitesCountMany: '{n} 處',
  depth: '海床',
  visibility: '能見度',
  current: '洋流',
  notForMode: '此玩法不提供',
  briefingTitle: '下水簡報',
  tether: '纜長',
  timeLimit: '時限',
  units2: { kn: 'kn', min: '分' },
  objectives: '任務目標',
  objectiveCountOne: '目標 {n} 項',
  objectiveCount: '目標 {n} 項',
  noObjectives: '自由航行，沒有指定目標。',
  goalsTitle: '玩法',
  site: '海域',
  modeGoals: {
    free_explore: ['自由航行：不計時、不扣分。', '練習操控、機械臂與標記，隨時可以返回主選單。'],
    expedition: ['探索海域、拍攝生物登錄圖鑑。', '下水後可在任務卡接取巡檢、回收或部署委託。'],
    inspection_coop: ['分工靠近三個巡檢站點（下水後標出）。', '在站點低速穩定 3 秒後拍照。'],
  },
  hostNote: '加入既有房間時，以房主的場景與玩法為準。',
  hostChip: '以房主設定為準',
  room: '房間',
  intro: '下水動畫',
  procedure: '潛前檢查',
  procedureOff: '關閉時直接從水中開始，略過潛前檢查（擬真設定「下水流程」為完整作業時）。',
  introOff: '關閉時直接從水中開始。',
  launch: '下水',
  chapter: '章節',
  campaign: '劇情與教學',
});
// Entries drawn smaller under the main list.
const MINOR_ENTRIES = new Set(['collection', 'settings']);
// The game-rendered site picture (menu/previews) that stands for each mode on its tile.
const MODE_PREVIEW = {
  expedition: 'coral_reef',
  free_explore: 'open_water',
  inspection_coop: 'harbor_inspection',
  scenario_training: 'jacket_inspection',
};
const NAME_SEPARATOR = ' · ';
const MAX_CHIPS = 3;

// English needs a singular; the other languages use the same text for both.
function objectiveChip(n) {
  const template = n === 1 ? STRINGS.objectiveCountOne : STRINGS.objectiveCount;
  return template.replace('{n}', String(n));
}

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
  root.classList.add('bp-screen');
  const list = element('nav', 'menu-list');
  const targets = {
    dive: function dive() {
      ctx.startRoute('dive');
    },
    story: function story() {
      ctx.openTraining('story');
    },
    contracts: function contracts() {
      ctx.openBoard();
    },
    shop: function shop() {
      ctx.openShop();
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
    button.title = help;
    if (MINOR_ENTRIES.has(key)) button.classList.add('menu-entry-minor');
    if (index === 0) button.dataset.autofocus = '';
    button.append(element('span', 'menu-entry-label', label));
    button.addEventListener('click', targets[key]);
    list.append(button);
  });
  // 快速開始 is a text action: its second line names the last dive it repeats.
  const quick = linkButton('quickStart', '');
  quick.classList.add('menu-quick');
  const quickText = element('span', 'menu-quick-detail');
  quick.append(element('span', 'menu-quick-label', STRINGS.quick), quickText);
  quick.addEventListener('click', function quickStart() {
    ctx.quickStart();
  });
  // The YX career as one status line and 繼續職涯 (career/summary.js), when the career data loaded.
  const career = ctx.careerSummary?.() || null;
  root.append(list);
  if (career) {
    career.actions.append(quick);
    root.append(career.element);
  } else {
    const corner = element('div', 'bp-hero bp-hero-corner');
    corner.append(quick);
    root.append(corner);
  }
  function enter() {
    career?.refresh();
    ctx.choice.multiplayer = false;
    ctx.choice.contract = '';
    ctx.choice.exam = false;
    const summary = ctx.lastSummary();
    quick.disabled = !summary;
    quick.title = summary ? '' : STRINGS.quickNone;
    quickText.textContent = summary;
  }
  return { element: root, pose: 'main', enter };
}

export function buildModes(ctx) {
  const root = screen('modes', STRINGS.modesTitle);
  root.classList.add('bp-screen');
  const hero = createHero();
  const { button: choose } = primaryButton('modeChoose', STRINGS.choose);
  hero.actions.append(choose);
  function showMode(card) {
    const [title, , players, chips] = STRINGS.modes[card.dataset.mode];
    hero.kicker.textContent = STRINGS.modesTitle;
    hero.setTitle(title);
    hero.setStats([[STRINGS.players, players, '']]);
    hero.setChips(chips);
  }
  const strip = createTileStrip(showMode);
  const cards = MODES.map(function modeTile(mode) {
    const [title, line] = STRINGS.modes[mode];
    const card = tile({ name: title, image: `menu/previews/${MODE_PREVIEW[mode]}.jpg` });
    card.dataset.mode = mode;
    card.title = line;
    card.addEventListener('click', function chooseMode() {
      ctx.chooseMode(mode);
    });
    return card;
  });
  choose.addEventListener('click', function chooseCurrent() {
    const mode = strip.current?.dataset.mode;
    if (mode) ctx.chooseMode(mode);
  });
  root.append(strip.element, hero.element);
  function enter() {
    for (const card of cards) card.setAttribute('aria-pressed', String(card.dataset.mode === ctx.choice.mission));
    strip.fill(cards, cards.find(function chosen(card) {
      return card.dataset.mode === ctx.choice.mission;
    }));
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

// "YX Model R · Block 1" as a large name and a smaller Block line; the text content stays the whole title.
function renderVehicleName(node, title) {
  const [name, ...rest] = String(title || '').split(NAME_SEPARATOR);
  node.replaceChildren(element('span', '', name));
  node.dataset.size = name.length > 12 ? 's' : 'm';
  if (!rest.length) return;
  node.append(element('span', 'menu-vehicle-separator', NAME_SEPARATOR));
  node.append(element('small', '', rest.join(NAME_SEPARATOR)));
}

function chipButton(className, text) {
  const button = element('button', `menu-chip ${className}`.trim(), text);
  button.type = 'button';
  return button;
}

export function buildHangar(ctx) {
  const root = screen('hangar', STRINGS.hangarTitle);
  root.classList.add('bp-screen');
  const hero = createHero({ titleTag: 'h3' });
  hero.title.classList.add('menu-vehicle-name');
  hero.kicker.classList.add('menu-vehicle-title');
  const role = element('span', '');
  const marker = element('span', 'menu-provisional', STRINGS.provisional);
  marker.title = STRINGS.provisionalHelp;
  hero.kicker.append(role, marker);
  const picker = element('div', 'menu-vehicles');
  picker.setAttribute('role', 'radiogroup');
  picker.setAttribute('aria-label', STRINGS.hangarTitle);
  const stickers = element('div', 'menu-stickers');
  stickers.setAttribute('role', 'radiogroup');
  stickers.setAttribute('aria-label', STRINGS.sticker);
  const stickerLabel = element('span', 'bp-row-label', STRINGS.sticker);
  const sheet = createDetailSheet(STRINGS.hangarTitle);
  const detail = element('p', 'bp-sheet-text');
  detail.id = 'hangarDetail';
  const caveat = element('p', 'bp-sheet-text');
  const bars = element('div', 'menu-bars');
  sheet.section(STRINGS.about, detail, caveat);
  sheet.section(STRINGS.performance, bars);
  for (const vehicle of ctx.data.vehicles) {
    const button = chipButton('', vehicle.name);
    button.dataset.vehicle = vehicle.id;
    button.addEventListener('click', function chooseVehicle() {
      ctx.selectModel(vehicle.id);
      render();
    });
    picker.append(button);
  }
  stickers.append(stickerLabel);
  for (const [preset, label] of Object.entries(STICKERS)) {
    const button = chipButton('menu-chip-small', label);
    button.dataset.sticker = preset;
    button.addEventListener('click', function chooseSticker() {
      ctx.selectSticker(preset);
      render();
    });
    stickers.append(button);
  }
  const { button: next } = primaryButton('hangarNext', STRINGS.next, { cap: false });
  next.addEventListener('click', function proceed() {
    ctx.afterHangar();
  });
  hero.chips.replaceWith(picker, stickers);
  hero.actions.append(next, detailButton('hangarDetails', sheet));
  root.append(hero.element);
  function render() {
    const vehicle = ctx.data.vehicles.find(function chosen(entry) {
      return entry.id === ctx.choice.model;
    }) || ctx.data.vehicles[0];
    if (!vehicle) return;
    const specs = vehicleSpecs(vehicle);
    renderVehicleName(hero.title, ctx.titleFor?.(vehicle) || vehicle.title || vehicle.name);
    role.textContent = String(vehicle.detail || '').split(NAME_SEPARATOR)[0] || STRINGS.hangarTitle;
    marker.hidden = !specs.provisional;
    sheet.setTitle(vehicle.name);
    detail.textContent = vehicle.detail || '';
    caveat.textContent = specs.provisional ? STRINGS.provisionalHelp : STRINGS.estimated;
    hero.setStats([
      [STRINGS.numbers.mass, fixed(specs.mass, 1), STRINGS.units.mass],
      [STRINGS.numbers.thrusters, String(specs.thrusters), STRINGS.units.thrusters],
      [STRINGS.numbers.speed, fixed(specs.speedKn, 1), STRINGS.units.speed],
      [STRINGS.numbers.arm, specs.arm ? STRINGS.armYes : STRINGS.armNo, ''],
    ]);
    bars.replaceChildren(...Object.entries(STRINGS.bars).map(function makeBar([key, label]) {
      return bar(label, specs.bars[key], specs.values[key]);
    }));
    for (const button of picker.children) {
      button.setAttribute('aria-pressed', String(button.dataset.vehicle === vehicle.id));
    }
    for (const button of stickers.querySelectorAll('[data-sticker]')) {
      button.hidden = ctx.stickerAvailable ? !ctx.stickerAvailable(button.dataset.sticker) : false;
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

function siteTile(scene, ctx) {
  const card = tile({ name: scene.name, image: `menu/previews/${scene.key}.jpg` });
  card.dataset.site = scene.key;
  card.addEventListener('click', function chooseSite() {
    ctx.chooseSite(scene.key);
  });
  return card;
}

export function buildSites(ctx) {
  const root = screen('sites', STRINGS.sitesTitle);
  root.classList.add('bp-screen');
  const hero = createHero();
  const n = ctx.data.sites.length;
  const count = (n === 1 ? STRINGS.sitesCountOne : STRINGS.sitesCountMany).replace('{n}', String(n));
  const { button: choose } = primaryButton('siteChoose', STRINGS.choose);
  hero.actions.append(choose);
  function showSite(card) {
    const scene = ctx.sceneFor(card.dataset.site);
    if (!scene) return;
    const facts = siteFacts(scene);
    hero.kicker.textContent = [STRINGS.sitesTitle, count].join(NAME_SEPARATOR);
    hero.setTitle(scene.name);
    hero.setStats([
      [STRINGS.depth, depthText(facts), lengthUnit()],
      [STRINGS.visibility, fixed(metres(facts.visibility), 0), lengthUnit()],
      [STRINGS.current, fixed(facts.current, 1), STRINGS.units2.kn],
    ]);
    const allowed = supportsMode(scene, ctx.choice.mission);
    hero.setChips(allowed ? facts.activities.slice(0, MAX_CHIPS) : [[STRINGS.notForMode, 'warn']]);
    choose.disabled = !allowed;
    ctx.previewScene(scene.key);
  }
  const strip = createTileStrip(showSite);
  choose.addEventListener('click', function chooseCurrent() {
    const key = strip.current?.dataset.site;
    if (key) ctx.chooseSite(key);
  });
  root.append(strip.element, hero.element);
  function enter() {
    // Rebuilt on entry so the numbers follow the unit setting.
    const cards = ctx.data.sites.map(function makeCard(scene) {
      return siteTile(scene, ctx);
    });
    // Sites the chosen mode offers come first; the others stay visible but disabled.
    const ordered = [...cards].sort(function availableFirst(a, b) {
      const mode = ctx.choice.mission;
      return Number(!supportsMode(ctx.sceneFor(a.dataset.site), mode))
        - Number(!supportsMode(ctx.sceneFor(b.dataset.site), mode));
    });
    let preferred = null;
    for (const card of cards) {
      const scene = ctx.sceneFor(card.dataset.site);
      const allowed = supportsMode(scene, ctx.choice.mission);
      card.disabled = !allowed;
      card.classList.toggle('unavailable', !allowed);
      card.setAttribute('aria-pressed', String(card.dataset.site === ctx.choice.scenario));
      if (card.dataset.site !== ctx.choice.scenario || !allowed) continue;
      card.dataset.autofocus = '';
      preferred = card;
    }
    strip.fill(ordered, preferred);
  }
  return { element: root, pose: 'sites', enter };
}

function paragraph(text) {
  return element('p', 'bp-sheet-text', text);
}

function numbered(labels) {
  const list = element('ol', 'menu-objectives');
  list.append(...labels.map(function item(text) {
    return element('li', '', text);
  }));
  return list;
}

export function buildBriefing(ctx) {
  const root = screen('briefing', STRINGS.briefingTitle);
  root.classList.add('bp-screen');
  const form = element('form', 'menu-briefing');
  form.id = 'launchForm';
  form.noValidate = true;
  const hero = createHero();
  hero.element.classList.add('menu-briefing-main');
  hero.kicker.classList.add('menu-kicker');
  const sheet = createDetailSheet(STRINGS.briefingTitle);
  const introRow = element('label', 'menu-toggle menu-toggle-inline');
  introRow.htmlFor = 'menuIntro';
  const introLabel = element('strong', '', STRINGS.intro);
  // The same switch decides ?nointro, which also skips the pre-dive procedure when the fidelity item asks for it.
  function describeLaunch() {
    const full = getFidelity().get(PROCEDURE_ITEM) === 'full';
    introLabel.textContent = full ? STRINGS.procedure : STRINGS.intro;
    introRow.title = full ? STRINGS.procedureOff : STRINGS.introOff;
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
  introRow.append(introLabel, intro, introSwitch);
  const { button: start } = primaryButton('startDive', STRINGS.launch, { type: 'submit' });
  start.dataset.autofocus = '';
  hero.actions.append(start, detailButton('briefingDetails', sheet), introRow);
  form.append(hero.element);
  form.addEventListener('submit', function submit(event) {
    event.preventDefault();
    ctx.choice.intro = intro.checked;
    ctx.launch();
  });
  root.append(form);
  function stats(facts, chapter) {
    if (!facts) return [];
    const list = [
      [STRINGS.depth, depthText(facts), lengthUnit()],
      [STRINGS.visibility, fixed(metres(facts.visibility), 0), lengthUnit()],
      [STRINGS.current, fixed(facts.current, 1), STRINGS.units2.kn],
    ];
    const limit = briefingTimeLimit(ctx.choice.mission, facts);
    if (limit && !chapter) list.push([STRINGS.timeLimit, fixed(limit / 60, 0), STRINGS.units2.min]);
    else list.push([STRINGS.tether, fixed(metres(facts.tether), 0), lengthUnit()]);
    return list;
  }
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
    hero.kicker.textContent = [modeName, vehicle?.title || vehicle?.name, room].filter(Boolean)
      .join(NAME_SEPARATOR);
    const heading = chapter ? chapter.title : facts?.name || ctx.choice.scenario;
    hero.setTitle(heading);
    hero.setStats(stats(facts, chapter));
    // Only scenario training plays the scene's own objectives; the other modes say what the mode is about.
    const goals = chapter ? null : STRINGS.modeGoals[ctx.choice.mission];
    const labels = goals || (scene?.world?.objectives || []).map(function label(objective) {
      return objective.label;
    }).filter(Boolean).slice(0, 5);
    const chips = [];
    if (goals) chips.push(...(STRINGS.modes[ctx.choice.mission]?.[3] || []));
    else if (labels.length && !chapter) chips.push(objectiveChip(labels.length));
    if (ctx.choice.multiplayer) chips.push([STRINGS.hostChip, 'warn']);
    hero.setChips(chips.slice(0, MAX_CHIPS));
    // 明細: the site or chapter brief, the objectives and the host note.
    sheet.setTitle(heading);
    sheet.clear();
    const brief = chapter?.outline || facts?.brief || '';
    if (brief) sheet.section(chapter ? STRINGS.chapter : STRINGS.site, paragraph(brief));
    if (!chapter) {
      const list = labels.length ? numbered(labels) : paragraph(STRINGS.noObjectives);
      sheet.section(goals ? STRINGS.goalsTitle : STRINGS.objectives, list);
    }
    if (ctx.choice.multiplayer) sheet.section(STRINGS.room, paragraph(STRINGS.hostNote));
    sheet.section(introLabel.textContent, paragraph(introRow.title));
    intro.checked = introForLaunch(ctx.choice);
    ctx.previewScene(ctx.choice.scenario);
  }
  return { element: root, pose: 'briefing', enter };
}
