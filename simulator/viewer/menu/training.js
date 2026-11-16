// Training screen: story chapters and incident drills from the campaign catalogue (category and order),
// and every scenario as a training run with its derived difficulty, as cards (menu/cards.js) with a preview,
// description, medal and best score. Chapter locks follow the local save and say what unlocks them.
import { chapterStatus, chaptersByCategory, trainingScenarios } from './catalogue.js';
import { chapterCard, scenarioCard } from './cards.js';
import { createSettingsPanel } from './settings.js';
import { readout } from './screens.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.training', {
  title: '訓練',
  tabs: { story: '劇情與教學', drills: '事故演練', scenarios: '場景訓練' },
  storyHelp: '依序解鎖；每章完成後在這台裝置保存進度。',
  drillHelp: '獨立的事故處置演練，不需要解鎖，可單獨重複練習。',
  scenarioHelp: '依洋流與能見度排出的難度；簡介說明練習重點。',
});
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

function chapterTitle(chapters, id) {
  return chapters.find(function byId(chapter) {
    return chapter.id === id;
  })?.title || '';
}

function chapterCards(ctx, category, completed) {
  return chaptersByCategory(ctx.data.chapters, category).map(function card(chapter, index) {
    const entry = category === 'incident' ? { ...chapter, requires: null } : chapter;
    return chapterCard(entry, {
      index,
      status: chapterStatus(entry, completed),
      requiredTitle: chapterTitle(ctx.data.chapters, entry.requires),
      onChoose: ctx.chooseChapter,
    });
  });
}

export function buildTraining(ctx) {
  const root = element('section', 'menu-screen');
  root.dataset.screen = 'training';
  root.setAttribute('aria-label', STRINGS.title);
  root.append(element('h2', 'menu-heading', STRINGS.title));
  const lists = [];
  function list(help, rows) {
    return function mount(container) {
      container.append(element('p', 'menu-help', help));
      const wrap = element('div', 'menu-card-grid');
      wrap.append(...rows());
      container.append(wrap);
      // Medals and unlocks change after a run; rebuild the cards whenever the screen is entered again.
      lists.push(function refresh() {
        wrap.replaceChildren(...rows());
      });
    };
  }
  const panel = createSettingsPanel({
    idPrefix: 'training',
    tabs: [
      {
        id: 'story',
        label: STRINGS.tabs.story,
        mount: list(STRINGS.storyHelp, function storyRows() {
          return chapterCards(ctx, 'story', completedChapters());
        }),
      },
      {
        id: 'drills',
        label: STRINGS.tabs.drills,
        mount: list(STRINGS.drillHelp, function drillRows() {
          return chapterCards(ctx, 'incident', []);
        }),
      },
      {
        id: 'scenarios',
        label: STRINGS.tabs.scenarios,
        mount: list(STRINGS.scenarioHelp, function scenarioRows() {
          return trainingScenarios(ctx.data.sites).map(function card(facts) {
            return scenarioCard(facts, { readout, onChoose: ctx.chooseTrainingScenario });
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
    enter() {
      for (const refresh of lists) refresh();
    },
    show(tab) {
      panel.select(tab);
    },
  };
}
