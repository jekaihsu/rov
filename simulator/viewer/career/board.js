// YX 委託看板: the launch menu screen that lists the YX work orders by chapter. Big-picture layout: chapters are
// large tabs, the contracts of a chapter are image tiles, and the tile under focus fills the hero block (client
// and job type, title, seabed depth, current, pay, and why it is locked or how it went last time) while the 3D
// stage shows its site. A tile, or the primary button, opens the contract detail screen (contract_screen.js).
// Tiles stay focusable when locked, so a gamepad player can still read why. The last tab holds the open-sea
// expedition contracts and the career save backup. Data and rules come from the career context (career/menu.js).
import { createSettingsPanel } from '../menu/settings.js';
import { previewKey } from '../menu/cards.js';
import { siteFacts } from '../menu/catalogue.js';
import {
  createHero,
  createTileStrip,
  element,
  linkButton,
  primaryButton,
  statusLine,
  tile,
} from '../menu/big_picture.js';
import { medalLabel } from '../play/results_model.js';
import { boardChapters, clientLabel, gradeFor, jobLabel } from './rules.js';
import { exportCareer, importCareer } from './save.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('career.board', {
  title: 'YX 委託看板',
  status: { open: '可接案', locked: '未開放', done: '已完成' },
  optional: '支線',
  exam: '執照考核',
  pay: '報酬',
  current: '洋流',
  depth: '海床',
  best: '{medal} · {score} 分',
  moneyUnit: '元',
  summary: '{licence} · {money} 元',
  open: '查看工單',
  otherTab: '其他',
  otherTitle: '其他委託與存檔',
  expedition: ['海洋探索委託', '在探索海域自由接巡檢、回收與部署的小委託；下水後在右上任務卡接案。'],
  expeditionKicker: '自由接案',
  expeditionChips: ['巡檢', '回收', '部署'],
  expeditionOpen: '前往',
  backupHelp: '匯出成 JSON 備份，或從備份還原（會取代目前的職涯）。',
  exportButton: '匯出存檔',
  importButton: '匯入存檔',
  imported: '已匯入職涯存檔。',
  exported: '已匯出職涯存檔。',
});
const TITLE_SEPARATOR = ' · ';
const EXPEDITION_SCENE = 'coral_reef';
const MAX_CHIPS = 3;

/** Money as a grouped integer, e.g. 12,000. */
export function moneyText(value) {
  return Math.round(Number(value) || 0).toLocaleString('en-US');
}

function previewImage(scenario) {
  return `menu/previews/${previewKey(scenario)}.jpg`;
}

/** One work-order tile; onChoose(contract) opens its detail screen. */
export function contractTile(contract, status, { career, onChoose }) {
  const card = tile({ name: contract.title, image: previewImage(contract.scenario) });
  card.classList.add('career-card');
  card.dataset.contract = contract.id;
  card.dataset.status = status.status;
  card.dataset.medal = career.save.contracts[contract.id]?.medal || 'none';
  if (status.status === 'locked') card.setAttribute('aria-disabled', 'true');
  card.addEventListener('click', function choose() {
    onChoose(contract);
  });
  return card;
}

function backupRow(career) {
  const row = element('div', 'career-backup');
  row.title = STRINGS.backupHelp;
  const exportButton = linkButton('careerExport', STRINGS.exportButton);
  const importButton = linkButton('careerImport', STRINGS.importButton);
  const file = element('input');
  file.type = 'file';
  file.accept = 'application/json,.json';
  file.hidden = true;
  exportButton.addEventListener('click', function download() {
    const blob = new Blob([exportCareer(career.save)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const link = element('a');
    link.href = url;
    link.download = 'rov-solution-career.json';
    link.click();
    setTimeout(function release() {
      URL.revokeObjectURL(url);
    }, 5000);
    career.setStatus(STRINGS.exported);
  });
  importButton.addEventListener('click', function choose() {
    file.click();
  });
  file.addEventListener('change', async function load() {
    const chosen = file.files?.[0];
    file.value = '';
    if (!chosen) return;
    try {
      career.replace(importCareer(await chosen.text()));
      career.setStatus(STRINGS.imported);
    } catch (error) {
      career.setStatus(error.message);
    }
  });
  row.append(exportButton, importButton, file);
  return row;
}

/** The board screen. ctx.career: career/menu.js context; ctx.openContracts(): the expedition route. */
export function buildBoard(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen bp-screen career-board');
  root.dataset.screen = 'board';
  root.setAttribute('aria-label', STRINGS.title);
  const summary = statusLine('boardSummary');
  const hero = createHero();
  hero.element.id = 'boardHero';
  const { button: open, label: openLabel } = primaryButton('boardOpen', STRINGS.open);
  hero.actions.append(open);
  const strips = new Map();
  const refreshers = [];
  let activeTab = '';

  function contractFor(id) {
    return career.data.contracts.find(function byId(contract) {
      return contract.id === id;
    }) || null;
  }
  function statusChips(contract, status) {
    if (status.status === 'locked') {
      return status.reasons.slice(0, MAX_CHIPS).map(function reason(entry) {
        return [entry.text, 'missing'];
      });
    }
    const chips = [[STRINGS.status[status.status], status.status === 'done' ? 'ok' : '']];
    const record = career.save.contracts[contract.id];
    if (record?.completed) {
      chips.push(STRINGS.best.replace('{medal}', medalLabel(record.medal)).replace('{score}', String(record.best)));
    }
    return chips;
  }
  function showContract(contract) {
    const { data, save } = career;
    const status = boardChapters(data, save, career.sceneKeys).flatMap(function list(entry) {
      return entry.contracts;
    }).find(function same(entry) {
      return entry.contract.id === contract.id;
    })?.status || { status: 'open', reasons: [] };
    const kicker = [clientLabel(data, contract.client), jobLabel(data, contract.job)];
    if (contract.exam) kicker.push(STRINGS.exam);
    else if (contract.optional) kicker.push(STRINGS.optional);
    hero.kicker.textContent = kicker.join(TITLE_SEPARATOR);
    hero.setTitle(contract.title);
    const stats = [];
    const scene = career.sceneFor(contract.scenario);
    if (scene) {
      const facts = siteFacts(scene);
      stats.push([STRINGS.depth, String(Math.round(facts.deep ?? 0)), 'm']);
      stats.push([STRINGS.current, (contract.currentKn ?? facts.current).toFixed(1), 'kn']);
    }
    stats.push([STRINGS.pay, moneyText(contract.pay), STRINGS.moneyUnit]);
    hero.setStats(stats);
    hero.setChips(statusChips(contract, status));
    hero.element.dataset.status = status.status;
    openLabel.textContent = STRINGS.open;
  }
  function showExpedition() {
    hero.kicker.textContent = STRINGS.expeditionKicker;
    hero.setTitle(STRINGS.expedition[0]);
    hero.setStats([]);
    hero.setChips(STRINGS.expeditionChips);
    hero.element.dataset.status = 'open';
    openLabel.textContent = STRINGS.expeditionOpen;
  }
  function sceneOf(card) {
    if (!card) return '';
    const contract = contractFor(card.dataset.contract);
    return contract ? contract.scenario : EXPEDITION_SCENE;
  }
  // The tile under focus fills the hero block and, while the board is on screen, moves the 3D backdrop.
  function showTile(card) {
    const contract = contractFor(card.dataset.contract);
    if (contract) showContract(contract);
    else showExpedition();
    if (root.dataset.active !== undefined) ctx.previewScene(sceneOf(card));
  }
  function activeStrip() {
    return strips.get(activeTab) || null;
  }
  const chapters = boardChapters(career.data, career.save, career.sceneKeys);
  const tabs = chapters.map(function chapterTab(entry) {
    return {
      id: entry.chapter.id,
      label: entry.chapter.title.split(TITLE_SEPARATOR)[0],
      title: [entry.chapter.title, entry.chapter.summary].join('\n'),
      mount(container) {
        const strip = createTileStrip(showTile);
        strips.set(entry.chapter.id, strip);
        container.append(strip.element);
        function render() {
          const current = boardChapters(career.data, career.save, career.sceneKeys).find(function byId(item) {
            return item.chapter.id === entry.chapter.id;
          });
          const keep = strip.current?.dataset.contract;
          const cards = (current?.contracts || []).map(function card(item) {
            return contractTile(item.contract, item.status, { career, onChoose: ctx.openContract });
          });
          const preferred = cards.find(function kept(card) {
            return card.dataset.contract === keep;
          }) || cards.find(function available(card) {
            return card.dataset.status === 'open';
          });
          strip.fill(cards, preferred);
        }
        render();
        refreshers.push(render);
      },
    };
  });
  tabs.push({
    id: 'other',
    label: STRINGS.otherTab,
    title: STRINGS.otherTitle,
    mount(container) {
      const strip = createTileStrip(showTile);
      strips.set('other', strip);
      const card = tile({ name: STRINGS.expedition[0], image: previewImage(EXPEDITION_SCENE) });
      card.classList.add('career-card');
      card.id = 'boardExpedition';
      card.title = STRINGS.expedition[1];
      card.addEventListener('click', function expedition() {
        ctx.openContracts();
      });
      container.append(backupRow(career), strip.element);
      strip.fill([card]);
    },
  });
  function selected(id) {
    activeTab = id;
    const card = activeStrip()?.current;
    if (card) showTile(card);
  }
  const panel = createSettingsPanel({ idPrefix: 'board', tabs, onSelect: selected });
  open.addEventListener('click', function openCurrent() {
    activeStrip()?.current?.click();
  });
  root.append(summary, panel.element, hero.element);
  function renderSummary() {
    const save = career.save;
    summary.textContent = STRINGS.summary
      .replace('{licence}', gradeFor(career.data, save.licence).label)
      .replace('{money}', moneyText(save.money));
  }
  return {
    element: root,
    pose: 'modes',
    tabs: panel,
    // The site the 3D stage shows behind the board: the focused contract's.
    sceneKey() {
      return sceneOf(activeStrip()?.current);
    },
    enter() {
      renderSummary();
      for (const refresh of refreshers) refresh();
      const card = activeStrip()?.current;
      if (card) showTile(card);
    },
    show(tab) {
      panel.select(tab);
    },
  };
}
