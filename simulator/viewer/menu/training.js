// Training screen: story chapters and incident drills from the campaign catalogue (category and order),
// and every scenario as a training run with its derived difficulty. Chapter locks follow the local save.
import { chapterStatus, chaptersByCategory, trainingScenarios } from './catalogue.js';
import { createSettingsPanel } from './settings.js';
import { readout } from './screens.js';

const STRINGS = {
  title: '訓練',
  tabs: { story: '劇情與教學', drills: '事故演練', scenarios: '場景訓練' },
  storyHelp: '依序解鎖；每章完成後在這台裝置保存進度。',
  drillHelp: '獨立的事故處置演練，不需要解鎖，可單獨重複練習。',
  scenarioHelp: '依洋流與能見度排出的難度；簡介說明練習重點。',
  status: { done: '已完成', locked: '先完成前一章', pending: '籌備中', open: '' },
  difficulty: '難度',
  current: '洋流',
  visibility: '能見度',
};
const SAVE_KEY = 'rov.campaign.v1';

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function completedChapters() {
  try {
    const save = JSON.parse(localStorage.getItem(SAVE_KEY) || '{}');
    return Array.isArray(save?.completed) ? save.completed : [];
  } catch {
    return [];
  }
}

function chapterRow(chapter, index, completed, ctx) {
  const status = chapterStatus(chapter, completed);
  const row = element('button', 'menu-row');
  row.type = 'button';
  row.dataset.chapter = chapter.id;
  row.dataset.status = status;
  row.disabled = status === 'locked' || status === 'pending';
  row.append(element('span', 'menu-row-index', String(index + 1).padStart(2, '0')));
  const text = element('span', 'menu-row-text');
  text.append(element('strong', '', chapter.title));
  if (chapter.outline) text.append(element('small', '', chapter.outline));
  row.append(text);
  row.append(element('span', 'menu-row-status', STRINGS.status[status]));
  row.addEventListener('click', function chooseChapter() {
    ctx.chooseChapter(chapter);
  });
  return row;
}

function dots(level) {
  const group = element('span', 'menu-dots');
  group.setAttribute('aria-label', `${STRINGS.difficulty} ${level}/3`);
  for (let index = 1; index <= 3; index++) {
    const dot = element('i');
    if (index <= level) dot.className = 'on';
    group.append(dot);
  }
  return group;
}

function scenarioRow(facts, ctx) {
  const row = element('button', 'menu-row');
  row.type = 'button';
  row.dataset.scenario = facts.key;
  const text = element('span', 'menu-row-text');
  text.append(element('strong', '', facts.name), element('small', '', facts.brief));
  const numbers = element('span', 'menu-row-numbers');
  numbers.append(
    readout(STRINGS.current, facts.current.toFixed(1), 'kn'),
    readout(STRINGS.visibility, String(Math.round(facts.visibility ?? 0)), 'm'),
  );
  const level = element('span', 'menu-row-level');
  level.append(dots(facts.difficulty.level), element('small', '', facts.difficulty.label));
  row.append(level, text, numbers);
  row.addEventListener('click', function chooseScenario() {
    ctx.chooseTrainingScenario(facts.key);
  });
  return row;
}

export function buildTraining(ctx) {
  const root = element('section', 'menu-screen');
  root.dataset.screen = 'training';
  root.setAttribute('aria-label', STRINGS.title);
  root.append(element('h2', 'menu-heading', STRINGS.title));
  function list(help, rows) {
    return function mount(container) {
      container.append(element('p', 'menu-help', help));
      const wrap = element('div', 'menu-rows');
      wrap.append(...rows());
      container.append(wrap);
    };
  }
  const panel = createSettingsPanel({
    idPrefix: 'training',
    tabs: [
      {
        id: 'story',
        label: STRINGS.tabs.story,
        mount: list(STRINGS.storyHelp, function storyRows() {
          const completed = completedChapters();
          return chaptersByCategory(ctx.data.chapters, 'story').map(function row(chapter, index) {
            return chapterRow(chapter, index, completed, ctx);
          });
        }),
      },
      {
        id: 'drills',
        label: STRINGS.tabs.drills,
        mount: list(STRINGS.drillHelp, function drillRows() {
          return chaptersByCategory(ctx.data.chapters, 'incident').map(function row(chapter, index) {
            return chapterRow({ ...chapter, requires: null }, index, [], ctx);
          });
        }),
      },
      {
        id: 'scenarios',
        label: STRINGS.tabs.scenarios,
        mount: list(STRINGS.scenarioHelp, function scenarioRows() {
          return trainingScenarios(ctx.data.sites).map(function row(facts) {
            return scenarioRow(facts, ctx);
          });
        }),
      },
    ],
  });
  root.append(panel.element);
  return {
    element: root,
    pose: 'training',
    tabs: panel,
    show(tab) {
      panel.select(tab);
    },
  };
}
