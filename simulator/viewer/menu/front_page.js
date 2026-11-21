// The field journal shares work orders, progress and medals with the career board and dive results.
import { boardChapters, recommendedContract } from '../career/rules.js';
import { shopTitle } from '../career/shop.js';
import { medalLabel } from '../play/results_model.js';
import { chapterCardData } from '../brand/chapters.js';
import { titleCard } from '../brand/chapter_card.js';
import { replayTitle } from '../story/cold_open_menu.js';
import { createSettingsPanel, element } from './settings.js';
import { localize } from '../i18n/index.js';
import {
  backdropChapter as chapterForBackdrop,
  backdropLocation as locationForBackdrop,
  backdropScene as sceneForBackdrop,
} from './journal_backdrop.js';

const STRINGS = localize('menu.front_page', {
  resume: '繼續', story: '劇情', training: '訓練', settings: '設定', exit: '離開',
  internal: '內部工具', locked: '完成前一關',
  locations: {
    tutorial_pool: '清晨 · 室內水池',
    open_water: '日間 · 港外',
    harbor_inspection: '日間 · 港口',
    aquaculture_pen: '陰天 · 養殖場外海',
    prologue: '清晨 · 室內水池',
    ch1: '日間 · 港口',
    ch2: '陰天 · 養殖場外海',
  },
});

export function internalLabel() {
  return STRINGS.internal;
}

function journal(career) {
  return boardChapters(career.data, career.save, career.sceneKeys);
}

export function assignment(career) {
  return recommendedContract(career.data, career.save, career.sceneKeys);
}

export function backdropChapter(career, next) {
  return chapterForBackdrop(career, next);
}

export function backdropScene(career, next = assignment(career)) {
  return sceneForBackdrop(career, next);
}

export function backdropLocation(career, next = assignment(career)) {
  return locationForBackdrop(STRINGS.locations, career, next);
}

export function buildFrontPage(ctx) {
  const root = element('section', 'menu-screen field-home');
  root.dataset.screen = 'main';
  const place = element('p', 'field-location');
  const heading = element('h1', 'field-title');
  const count = element('p', 'field-progress');
  const list = element('nav', 'field-actions');
  const actions = {
    resume() { ctx.openContract(assignment(ctx.career)); },
    story() { ctx.go('story'); },
    training() { ctx.openTraining('drills'); },
    settings() { ctx.go('settings'); },
    exit() {
      if (window.rovDesktop) window.close();
      else ctx.go('title');
    },
  };
  for (const [id, action] of Object.entries(actions)) {
    const button = element('button', 'field-action', STRINGS[id]);
    button.id = 'entry-' + id;
    button.addEventListener('click', action);
    list.append(button);
  }
  root.append(place, heading, count, list);
  function enter() {
    ctx.choice.multiplayer = false;
    ctx.choice.contract = '';
    ctx.choice.exam = false;
    const target = assignment(ctx.career);
    const chapter = journal(ctx.career).find(group => group.chapter.id === target?.chapter);
    const rows = chapter?.contracts || [];
    const complete = rows.filter(row => ctx.career.save.contracts[row.contract.id]?.completed);
    place.textContent = backdropLocation(ctx.career, target);
    heading.textContent = target?.title || STRINGS.story;
    const tally = `${complete.length} / ${rows.length}`;
    count.textContent = [chapter?.chapter.title, tally].filter(Boolean).join('   ·   ');
    list.firstChild.disabled = !target;
  }
  return { element: root, pose: 'main', enter };
}

export function buildStory(ctx) {
  const root = element('section', 'menu-screen field-story');
  root.dataset.screen = 'story';
  root.append(element('h1', 'menu-heading', STRINGS.story));
  const refreshers = [];
  const tabs = journal(ctx.career).map(function chapterTab(group) {
    return {
      id: group.chapter.id,
      label: group.chapter.title.split(' · ')[0],
      mount(pane) {
        const grid = element('div', 'field-grid');
        pane.append(grid);
        function refresh() {
          const current = journal(ctx.career).find(item => item.chapter.id === group.chapter.id);
          grid.replaceChildren();
          for (const { contract, status } of current.contracts) {
            const button = element('button', 'field-order');
            button.dataset.order = contract.id;
            button.setAttribute('aria-disabled', String(!status.available));
            button.classList.toggle('is-locked', !status.available);
            const record = ctx.career.save.contracts[contract.id];
            const sub = status.available ? medalLabel(record?.medal || 'none') : STRINGS.locked;
            button.dataset.medal = record?.medal || 'none';
            button.title = status.reasons.map(reason => reason.text).join('\n');
            button.append(titleCard({
              number: contract.id.split('_')[0].toUpperCase(), client: group.chapter.title,
              symbol: {prologue: 'pool', ch1: 'harbor', ch2: 'offshore'}[group.chapter.id],
              title: contract.title, sub, scenario: contract.scenario,
            }));
            button.addEventListener('click', function openOrder() {
              if (status.available) ctx.openContract(contract);
            });
            grid.append(button);
          }
          if (group.chapter.id === 'prologue') {
            const replay = element('button', 'field-order');
            const data = chapterCardData({id: 'cold_open', title: replayTitle()});
            replay.append(titleCard(data));
            replay.addEventListener('click', ctx.replayColdOpen);
            replay.id = 'journalReplay';
            grid.append(replay);
          }
        }
        refreshers.push(refresh);
        refresh();
      },
    };
  });
  const gear = element('button', 'bp-link', shopTitle());
  gear.addEventListener('click', ctx.openShop);
  if (tabs.length) {
    const panel = createSettingsPanel({tabs, idPrefix: 'journal'});
    root.append(panel.element, gear);
    return {element: root, tabs: panel, pose: 'training', enter};
  }
  root.append(gear);
  return {element: root, pose: 'training', enter};

  function enter() {
    for (const refresh of refreshers) refresh();
  }
}
