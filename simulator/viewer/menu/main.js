// Launch menu entry point: loads the offline catalogue, builds every screen over the live 3D stage, and runs
// the flow title → main menu → mode → hangar → dive site → briefing → launch (or the training, multiplayer
// and settings branches). Every step is a full-screen layer; back is always available. Exposes window.__menu
// for the browser checks and the desktop smoke test.
// career/boot.js runs first: it restores settings an exam forced before any module reads the fidelity store.
import '../career/boot.js';
import { installCollectionPanel } from '../collection_panel.js';
import { genericVehicle } from '../asset_config.js';
import { vehicleDetail, vehicleName, vehicleTitle } from '../fleet_names.js';
import { diveSites, supportsMode } from './catalogue.js';
import { createMenuNavigator, loadControllerDatabase, renderPrompts } from './navigator.js';
import {
  hasLastSession,
  initialChoice,
  introForLaunch,
  lastSession,
  launchUrl,
  rememberChoice,
} from './preferences.js';
import { getFidelity } from '../fidelity.js';
import { PROCEDURE_ITEM } from '../procedure/fidelity_item.js';
import { buildBriefing, buildHangar, buildMain, buildModes, buildSites, buildTitle } from './screens.js';
import { buildTraining } from './training.js';
import { buildMultiplayer } from './multiplayer.js';
import { buildLaunchSettings } from './launch_settings.js';
import { buildNewGame, hasDifficultyChosen } from './new_game.js';
import { SHOWCASE, createStage } from './stage.js';
import { createBackdrop } from './big_picture.js';
import { previewKey } from './cards.js';
import { installDisplayPrefs } from '../prefs/display.js';
import { installAudio } from '../audio/engine.js';
import { installMusic } from '../audio/music.js';
import { installCareerMenu } from '../career/menu.js';
import { installBrandMenu } from '../brand/menu_brand.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.main', {
  brand: 'ROV Solution',
  loading: {
    data: '讀取海域與載具資料…',
    scene: '建立水下場景…',
    model: '載入載具模型…',
    ready: '準備完成',
    failed: '開場資料載入失敗，請重新整理。',
  },
  modelFailed: '模型載入失敗，請重新選擇機型。',
  launching: '正在下水…',
  steps: { modes: '玩法', training: '課程', multiplayer: '房間', hangar: '載具', sites: '海域', briefing: '簡報' },
  prompts: { move: '移動', accept: '確認', back: '返回', tabs: '分頁', rotate: '旋轉', start: '開始', close: '關閉' },
  modes: {
    campaign: '劇情與教學',
    expedition: '海洋探索與工程',
    free_explore: '自由探索',
    inspection_coop: '協作巡檢',
    scenario_training: '場景訓練',
  },
});
const ROUTES = {
  dive: ['modes', 'hangar', 'sites', 'briefing'],
  join: ['multiplayer', 'hangar', 'briefing'],
  story: ['training', 'hangar', 'briefing'],
  scenario: ['training', 'hangar', 'briefing'],
};
const PREVIEW_DELAY_MS = 280;
// Screens that show the title backdrop (stage.js SHOWCASE) instead of the chosen dive site.
const SHOWCASE_SCREENS = new Set([
  'title', 'main', 'settings', 'multiplayer', 'training', 'shop', 'new_game',
]);
const music = installMusic({ engine: installAudio() });

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

const loader = document.getElementById('menuLoading');
function setLoading(fraction, text) {
  if (!loader) return;
  loader.hidden = false;
  loader.style.setProperty('--progress', String(fraction));
  const label = loader.querySelector('small');
  if (label) label.textContent = text;
}
function finishLoading() {
  loader?.classList.add('done');
  setTimeout(function hideLoader() {
    if (loader) loader.hidden = true;
  }, 400);
}

async function loadJson(path) {
  const response = await fetch(path);
  if (!response.ok) throw new Error(`${path}: ${response.status}`);
  return response.json();
}

installDisplayPrefs();
document.body.classList.add('menu-open');
const reduced = matchMedia('(prefers-reduced-motion: reduce)').matches;
const choice = initialChoice();
choice.route = 'dive';
const menu = element('main', 'launch-menu');
menu.id = 'launchMenu';
const shade = element('div', 'menu-shade');
const header = element('header', 'menu-header');
const brand = element('div', 'menu-brand', STRINGS.brand);
const steps = element('ol', 'menu-steps');
header.append(brand, steps);
const stack = element('div', 'menu-stack');
const footer = element('footer', 'menu-footer');
const prompts = element('div', 'menu-prompts');
prompts.id = 'menuPrompts';
const status = element('p', 'menu-status');
status.id = 'menuStatus';
status.setAttribute('role', 'status');
footer.append(prompts, status);
menu.append(shade, header, stack, footer);
document.body.append(menu);

setLoading(0.08, STRINGS.loading.data);
let scenes = [];
let catalogue = { vehicles: [], chapters: [] };
let database = {};
try {
  [scenes, catalogue, database] = await Promise.all([
    loadJson('scene_previews.json'),
    loadJson('menu_catalogue.json'),
    loadControllerDatabase(),
  ]);
} catch (error) {
  setLoading(0, STRINGS.loading.failed);
  console.error(error);
  throw error;
}
setLoading(0.35, STRINGS.loading.scene);
const stage = createStage(menu, { quality: choice.quality });
// The game-rendered site picture that covers the stage while it switches site (big_picture.js).
const backdrop = createBackdrop(menu, shade);
// Player-facing YX fleet names come from fleet_names.js; ?assets=generic keeps the name of the art variant
// it draws and shows its own detail line.
for (const vehicle of catalogue.vehicles) {
  vehicle.name = vehicleName(vehicle.id);
  vehicle.title = vehicleTitle(vehicle.id, null);
  vehicle.detail = vehicleDetail(vehicle.id);
  const generic = genericVehicle(vehicle.id);
  if (!generic) continue;
  vehicle.name = generic.name;
  vehicle.detail = generic.detail;
}
const data = {
  scenes,
  sites: diveSites(scenes, catalogue.chapters),
  vehicles: catalogue.vehicles,
  chapters: catalogue.chapters,
};
if (!data.vehicles.some(function known(vehicle) {
  return vehicle.id === choice.model;
})) choice.model = data.vehicles[0]?.id || 'x1';

const history = [];
const screens = {};
let current = '';
let previewTimer = 0;
let ready = false;
const collection = installCollectionPanel({});
// The collection dialog speaks the menu's prompt language too (the navigator already steers and closes it).
const collectionPrompts = element('footer', 'collection-prompts');
document.querySelector('.collection-panel')?.append(collectionPrompts);

function sceneFor(key) {
  return scenes.find(function byKey(scene) {
    return scene.key === key;
  }) || null;
}
function chapterFor(id) {
  return data.chapters.find(function byId(chapter) {
    return chapter.id === id;
  }) || null;
}
function setStatus(text) {
  status.textContent = text || '';
}
function renderSteps() {
  const route = ROUTES[choice.route] || [];
  const index = route.indexOf(current);
  steps.replaceChildren();
  steps.hidden = index < 0;
  if (index < 0) return;
  route.forEach(function step(name, position) {
    const item = element('li', '', STRINGS.steps[name]);
    if (position < index) item.className = 'done';
    if (position === index) item.setAttribute('aria-current', 'step');
    steps.append(item);
  });
}
function promptsFor(name) {
  const base = [['navigate', STRINGS.prompts.move], ['accept', STRINGS.prompts.accept]];
  // The title's own button already shows the confirm key; the footer stays empty so it is not said twice.
  if (name === 'title') return [];
  // New-game has no back on first visit; settings re-open still allows Escape via the navigator.
  if (name === 'new_game' && !hasDifficultyChosen()) {
    return [...base];
  }
  const extra = [];
  if (screens[name]?.tabs) extra.push([['tabPrevious', 'tabNext'], STRINGS.prompts.tabs]);
  if (screens[name]?.rotatable) extra.push([['menuRotate'], STRINGS.prompts.rotate]);
  return [...base, ...extra, ['back', STRINGS.prompts.back]];
}
function renderPromptsFor(family) {
  renderPrompts(prompts, promptsFor(current), family);
  renderPrompts(collectionPrompts, [['navigate', STRINGS.prompts.move], ['accept', STRINGS.prompts.accept],
    ['back', STRINGS.prompts.close]], family);
  for (const cap of menu.querySelectorAll('[data-prompt-action]')) {
    renderPrompts(cap, [[cap.dataset.promptAction, '']], family);
  }
  for (const screen of Object.values(screens)) screen.tabs?.setFamily(family);
}

const navigator = createMenuNavigator({
  database,
  handlers: {
    scope() {
      return screens[current]?.element || menu;
    },
    back,
    tab(direction) {
      screens[current]?.tabs?.step(direction);
    },
    rotate(value, dt) {
      if (screens[current]?.rotatable) stage.rotate(value, dt);
    },
    family: renderPromptsFor,
    frame(frame) {
      screens.settings?.frame?.(frame);
    },
  },
});

function show(name) {
  const previous = screens[current];
  previous?.leave?.();
  if (previous) delete previous.element.dataset.active;
  current = name;
  const next = screens[name];
  next.enter?.();
  next.element.dataset.active = '';
  menu.dataset.screen = name;
  showBackdrop(name);
  music.setScreen(name);
  stage.setPose(next.pose || name);
  renderSteps();
  renderPromptsFor(navigator.family);
  setStatus('');
  requestAnimationFrame(function focusScreen() {
    navigator.focusFirst(next.element);
  });
}
// A screen with sceneKey() names the site behind it (the focused contract's); the others keep the chosen site.
function showBackdrop(name) {
  if (SHOWCASE_SCREENS.has(name)) {
    clearTimeout(previewTimer);
    backdrop.hide();
    stage.setScene(sceneFor(SHOWCASE.scene), { showcase: true });
  } else if (screens[name].sceneKey) previewScene(screens[name].sceneKey());
  else if (stage.showcase) stage.setScene(sceneFor(choice.scenario) || data.sites[0]);
}
function go(name) {
  if (current && current !== name) history.push(current);
  show(name);
}
function back() {
  if (!history.length) return;
  show(history.pop());
}

// Shows the site's preview picture at once, switches the 3D stage a moment later and then fades the picture
// away; a site this build has no scene for keeps its picture.
function previewScene(key) {
  clearTimeout(previewTimer);
  const entry = sceneFor(key);
  if (!entry || stage.showcase || stage.state.sceneKey !== key) backdrop.show(`menu/previews/${previewKey(key)}.jpg`);
  previewTimer = setTimeout(function switchScene() {
    if (!entry) return;
    stage.setScene(entry);
    backdrop.reveal();
  }, PREVIEW_DELAY_MS);
}
function selectModel(id) {
  choice.model = id;
  stage.setModel(id).catch(function failed(error) {
    setStatus(STRINGS.modelFailed);
    console.error(error);
  });
}
function selectSticker(preset) {
  choice.sticker = preset;
  stage.setSticker(preset);
}
function firstSupported(mode) {
  if (supportsMode(sceneFor(choice.scenario) || {}, mode) && data.sites.some(function listed(scene) {
    return scene.key === choice.scenario;
  })) return choice.scenario;
  return data.sites.find(function supported(scene) {
    return supportsMode(scene, mode);
  })?.key || choice.scenario;
}
function lastSummary() {
  if (!hasLastSession()) return '';
  const last = lastSession();
  const chapter = last.mission === 'campaign' ? chapterFor(last.chapter) : null;
  const site = sceneFor(last.scenario);
  const vehicle = data.vehicles.find(function byId(entry) {
    return entry.id === last.model;
  });
  return [STRINGS.modes[last.mission], chapter?.title || site?.name, vehicle?.name].filter(Boolean).join(' · ');
}
function launch() {
  let url;
  try {
    url = launchUrl(location.href, choice, location.protocol);
  } catch (error) {
    setStatus(error.message);
    return;
  }
  rememberChoice(choice);
  setStatus(STRINGS.launching);
  menu.classList.add('departing');
  stage.setPose('launch');
  music.setScreen(null);
  setTimeout(function leaveMenu() {
    location.assign(url);
  }, reduced ? 0 : 650);
}

const ctx = {
  choice,
  data,
  stage,
  go,
  back,
  sceneFor,
  chapterFor,
  setStatus,
  previewScene,
  selectModel,
  selectSticker,
  lastSummary,
  launch,
  startRoute(route) {
    choice.route = route;
    if (route === 'join') {
      go('hangar');
      return;
    }
    go('modes');
  },
  openTraining(tab) {
    screens.training.show(tab);
    choice.route = tab === 'story' ? 'story' : 'scenario';
    go('training');
  },
  openCollection() {
    collection.open();
  },
  openNewGame() {
    go('new_game');
  },
  onDifficultyChosen() {
    // Settings re-open returns there; the first-run path (title → new_game) continues to main.
    if (history.at(-1) === 'settings') {
      back();
      return;
    }
    history.length = 0;
    show('main');
  },
  // Expedition contracts as their own entry: the expedition sea, then vehicle and site as usual.
  openContracts() {
    choice.route = 'dive';
    ctx.chooseMode('expedition');
  },
  chooseMode(mode) {
    if (mode === 'scenario_training') {
      screens.training.show('scenarios');
      choice.route = 'scenario';
      go('training');
      return;
    }
    choice.mission = mode;
    choice.chapter = '';
    choice.scenario = firstSupported(mode);
    go('hangar');
  },
  chooseChapter(chapter) {
    choice.mission = 'campaign';
    choice.chapter = chapter.id;
    choice.scenario = chapter.scenario;
    choice.route = 'story';
    previewScene(chapter.scenario);
    go('hangar');
  },
  chooseTrainingScenario(key) {
    choice.mission = 'scenario_training';
    choice.chapter = '';
    choice.scenario = key;
    choice.route = 'scenario';
    previewScene(key);
    go('hangar');
  },
  afterHangar() {
    go(choice.route === 'dive' ? 'sites' : 'briefing');
  },
  chooseSite(key) {
    choice.scenario = key;
    go('briefing');
  },
  quickStart() {
    Object.assign(choice, lastSession());
    choice.intro = introForLaunch(choice, getFidelity().get(PROCEDURE_ITEM) === 'full');
    launch();
  },
};

const careerMenu = await installCareerMenu(ctx, screens);
screens.title = buildTitle(ctx);
screens.new_game = buildNewGame(ctx);
screens.main = buildMain(ctx);
screens.modes = buildModes(ctx);
screens.hangar = buildHangar(ctx);
screens.sites = buildSites(ctx);
screens.briefing = buildBriefing(ctx);
screens.training = buildTraining(ctx);
screens.multiplayer = buildMultiplayer(ctx);
screens.settings = buildLaunchSettings(ctx);
Object.assign(screens, careerMenu.buildScreens());
for (const screen of Object.values(screens)) stack.append(screen.element);
installBrandMenu({ menu, getModel: () => choice.model });

stage.setScene(sceneFor(SHOWCASE.scene) || sceneFor(choice.scenario) || data.sites[0], { showcase: true });
stage.setSticker(choice.sticker);
setLoading(0.6, STRINGS.loading.model);
try {
  await stage.setModel(choice.model);
} catch (error) {
  setStatus(STRINGS.modelFailed);
  console.error(error);
}
setLoading(1, STRINGS.loading.ready);
ready = true;
finishLoading();
show('title');
openRequestedScreen();
navigator.setActive(true);
navigator.start();

// ?menu=training&tab=scenarios|drills|story opens a list directly (the results screen's 其他訓練 link);
// ?menu=board opens the YX contract board (the results screen's 下一張委託).
function openRequestedScreen() {
  const query = new URLSearchParams(location.search);
  const requested = query.get('menu');
  if (requested === 'shop') {
    go('main');
    ctx.openShop();
    return;
  }
  if (requested === 'board') {
    go('main');
    ctx.openBoard(query.get('tab') || '');
    return;
  }
  if (requested !== 'training') return;
  go('main');
  ctx.openTraining(query.get('tab') || 'story');
}

window.__menu = {
  get ready() {
    return ready && stage.state.modelReady && stage.state.sceneReady;
  },
  get model() {
    return choice.model;
  },
  get scene() {
    return stage.state.sceneKey;
  },
  get mission() {
    return choice.mission;
  },
  get screen() {
    return current;
  },
  get choice() {
    return { ...choice };
  },
  get career() {
    return ctx.career?.save || null;
  },
  get stickerMeshes() {
    return stage.stickerMeshes;
  },
  renderer: stage.renderer,
  go,
  back,
  launch,
  // Site card images (tools/capture_site_previews.py): frame the site without the menu's offsets.
  pose(name) {
    stage.setPose(name);
  },
  // Desktop and browser checks: apply choices without walking the screens.
  configure(values) {
    Object.assign(choice, values);
    if (values.model) selectModel(values.model);
    if (values.sticker) selectSticker(values.sticker);
    if (values.scenario) stage.setScene(sceneFor(values.scenario));
    screens[current]?.enter?.();
  },
};
