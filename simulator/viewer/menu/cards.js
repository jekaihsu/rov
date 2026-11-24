// Cards for the training screen's chapter, drill and scenario lists: a site preview (menu/previews), a short
// description, difficulty, the medal and best score this device saved on the results screen
// (play/results_model.js), and for a locked chapter the condition that unlocks it. Buttons, so the menu
// navigator moves between them spatially with the pad or keys.
import { recordFor, medalLabel } from '../play/results_model.js';
import { lengthIn, lengthUnit } from '../prefs/display.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.cards', {
  chapters: {
    prologue: '在港內淺水區認識你的 ROV：解鎖、移動、定深、照明與拍照。',
    harbor: '第一筆案子：在港內樁腳的巡檢站點穩定懸停，替船主拍清楚舊裂痕。',
    hull: '船底擦撞檢查。能見度差時放慢，不鑽進看不見的縫。',
    harbor_signoff: '交班前複查：照片要讓下一班找得到同一處，練習貼近結構與留退路。',
    offshore: '離岸風場的潮窗：迎流接近導管架、巡檢陽極塊，流太強就停工。',
    reef: '研究站換裝觀測儀：先拍生態基準照，再用機械臂回收與部署。',
    wreck: '舊貨輪殘骸的外側調查，艙內不進。',
    finale: '夜間港內：接回封存匣、部署並核實，結局取決於你帶回的證據。',
    incident_jacket: '潮流轉強、人手不足：評估中止，從開放出口退回，纜線不貼構件。',
    incident_wreck: '纜線纏住殘骸：不從水面硬拉，沿纜線回卡點反向繞開。',
    incident_silt: '觸底揚沙、影像不可用：靠深度、羅盤與纜線走向退回出發點。',
    incident_compass: '羅盤失準：退出自動定向，以目視、纜線方向和深度撤離。',
    incident_current: '流速超過能力：站位漂移時中止並收回，不滿推硬守。',
  },
  status: { done: '已完成', pending: '籌備中', open: '可遊玩', locked: '未解鎖' },
  unlock: '完成「{title}」後解鎖',
  best: '最佳 {score}',
  noRecord: '尚無成績',
  difficulty: '難度',
  current: '洋流',
  visibility: '能見度',
});
// Scenes without their own preview image use the closest site's image (same structure or seabed).
const PREVIEW_FOR = {
  incident_jacket: 'jacket_inspection',
  incident_compass: 'jacket_inspection',
  incident_wreck: 'wreck_survey',
  incident_current: 'monopile_current',
  incident_silt: 'open_water',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function chapterDescription(chapter) {
  return chapter.outline || STRINGS.chapters[chapter.id] || '';
}

export function previewKey(scene) {
  return PREVIEW_FOR[scene] || scene;
}

// The line under the title that says what the save holds for this run.
export function recordLine(record) {
  if (!record) return STRINGS.noRecord;
  return `${medalLabel(record.medal)} · ${STRINGS.best.replace('{score}', String(record.best))}`;
}

function media(scene, index) {
  const box = element('span', 'menu-site-media menu-card-media');
  box.append(element('span', 'menu-card-numeral', index));
  const image = element('img');
  image.alt = '';
  image.loading = 'lazy';
  image.src = `menu/previews/${previewKey(scene)}.jpg`;
  image.addEventListener('error', function noPreview() {
    image.remove();
  });
  box.append(image);
  return box;
}

function medalBadge(record) {
  const badge = element('span', 'menu-medal');
  badge.dataset.medal = record?.medal || 'none';
  badge.textContent = recordLine(record);
  return badge;
}

export function dots(level) {
  const group = element('span', 'menu-dots');
  group.setAttribute('aria-label', `${STRINGS.difficulty} ${level}/3`);
  for (let index = 1; index <= 3; index++) {
    const dot = element('i');
    if (index <= level) dot.className = 'on';
    group.append(dot);
  }
  return group;
}

// chapter: catalogue entry; status: chapterStatus(); requiredTitle: title of the chapter it needs.
export function chapterCard(chapter, { index, status, requiredTitle, onChoose }) {
  const card = element('button', 'menu-site menu-play-card');
  card.type = 'button';
  card.dataset.chapter = chapter.id;
  card.dataset.status = status;
  card.disabled = status === 'locked' || status === 'pending';
  const record = recordFor(`chapter:${chapter.id}`);
  card.dataset.medal = record?.medal || 'none';
  const body = element('span', 'menu-site-body');
  body.append(element('strong', 'menu-card-title', chapter.title));
  body.append(element('span', 'menu-card-line', chapterDescription(chapter)));
  const foot = element('span', 'menu-card-foot');
  if (status === 'locked') {
    foot.append(element('span', 'menu-card-lock', STRINGS.unlock.replace('{title}', requiredTitle || '')));
  } else if (status === 'pending') {
    foot.append(element('span', 'menu-card-lock', STRINGS.status.pending));
  } else {
    foot.append(element('span', 'menu-row-status', STRINGS.status[status]), medalBadge(record));
  }
  body.append(foot);
  card.append(media(chapter.scenario, String(index + 1).padStart(2, '0')), body);
  card.addEventListener('click', function choose() {
    onChoose(chapter);
  });
  return card;
}

// facts: catalogue siteFacts() with difficulty; readout: screens.js readout builder.
export function scenarioCard(facts, { readout, onChoose }) {
  const card = element('button', 'menu-site menu-play-card');
  card.type = 'button';
  card.dataset.scenario = facts.key;
  const record = recordFor(`scenario:${facts.key}`);
  card.dataset.medal = record?.medal || 'none';
  const body = element('span', 'menu-site-body');
  const level = element('span', 'menu-row-level');
  level.append(dots(facts.difficulty.level), element('small', '', facts.difficulty.label));
  body.append(level, element('strong', 'menu-card-title', facts.name));
  body.append(element('span', 'menu-card-line', facts.brief || ''));
  const numbers = element('span', 'menu-site-numbers');
  numbers.append(
    readout(STRINGS.current, facts.current.toFixed(1), 'kn'),
    readout(STRINGS.visibility, String(Math.round(lengthIn(facts.visibility ?? 0))), lengthUnit()),
  );
  const foot = element('span', 'menu-card-foot');
  foot.append(medalBadge(record));
  body.append(numbers, foot);
  card.append(media(facts.key, ''), body);
  card.addEventListener('click', function choose() {
    onChoose(facts.key);
  });
  return card;
}
