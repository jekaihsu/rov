// Training screen: internal course map (S6), story chapters, incident drills, and
// scenario training. The course map is hidden on the Steam edition.
import { chapterStatus, chaptersByCategory, trainingScenarios } from './catalogue.js';
import { chapterCard, scenarioCard } from './cards.js';
import { createSettingsPanel } from './settings.js';
import { readout } from './screens.js';
import { replayCard } from '../story/cold_open_menu.js';
import { isInternalEdition } from '../training/edition.js';
import { buildCourseMap } from '../training/map.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.training', {
  title: '訓練',
  tabs: {
    courses: '課程地圖',
    story: '劇情與教學',
    drills: '事故演練',
    scenarios: '場景訓練',
    collection: '收藏',
  },
  storyHelp: '依序解鎖；每章完成後在這台裝置保存進度。',
  drillHelp: '獨立的事故處置演練，不需要解鎖，可單獨重複練習。',
  scenarioHelp: '依洋流與能見度排出的難度；簡介說明練習重點。',
  coursesHelp: '內部訓練模式：入門、操作員、進階與事故處置。預設真實擬真。',
  collectionHelp: '圖鑑與收藏仍可從這裡開啟；不進入 Steam 主線。',
  openCollection: '開啟收藏',
  steamHidden: 'Steam 版不提供公司課程地圖。',
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
      lists.push(function refresh() {
        wrap.replaceChildren(...rows());
      });
    };
  }

  const tabs = [];
  if (isInternalEdition()) {
    tabs.push({
      id: 'courses',
      label: STRINGS.tabs.courses,
      mount: function mountCourses(container) {
        container.append(element('p', 'menu-help', STRINGS.coursesHelp));
        const host = element('div', 'training-map-host');
        container.append(host);
        function refresh() {
          host.replaceChildren(buildCourseMap({
            catalogue: ctx.data.training || {courses: [], incidents: []},
            onChoose: ctx.chooseTrainingLesson,
          }));
        }
        refresh();
        lists.push(refresh);
      },
    });
  }

  tabs.push(
    {
      id: 'story',
      label: STRINGS.tabs.story,
      mount: list(STRINGS.storyHelp, function storyRows() {
        const rows = chapterCards(ctx, 'story', completedChapters());
        if (ctx.replayColdOpen) rows.push(replayCard(rows.length, ctx.replayColdOpen));
        return rows;
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
  );

  if (isInternalEdition() && ctx.openCollection) {
    tabs.push({
      id: 'collection',
      label: STRINGS.tabs.collection,
      mount: function mountCollection(container) {
        container.append(element('p', 'menu-help', STRINGS.collectionHelp));
        const button = element('button', 'menu-primary', STRINGS.openCollection);
        button.type = 'button';
        button.id = 'trainingOpenCollection';
        button.onclick = function open() {
          ctx.openCollection();
        };
        container.append(button);
      },
    });
  }

  const panel = createSettingsPanel({
    idPrefix: 'training',
    tabs,
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
      const available = tabs.some(function has(entry) {
        return entry.id === tab;
      });
      panel.select(available ? tab : tabs[0].id);
    },
  };
}
