// YX 委託看板: the launch menu screen that lists the YX work orders by chapter as cards (client, site, job type,
// what is required, pay, best medal, conditions) and, on the last tab, the open-sea expedition contracts and the
// career save backup. A card opens the contract detail screen (contract_screen.js). Cards stay focusable when
// locked, so a gamepad player can still read why. Data and rules come from the career context (career/menu.js).
import { createSettingsPanel } from '../menu/settings.js';
import { readout } from '../menu/screens.js';
import { previewKey } from '../menu/cards.js';
import { siteFacts } from '../menu/catalogue.js';
import { medalLabel } from '../play/results_model.js';
import { boardChapters, clientLabel, gradeFor, jobLabel } from './rules.js';
import { exportCareer, importCareer, realHours } from './save.js';

const STRINGS = {
  title: 'YX 委託看板',
  status: { open: '可接案', locked: '未開放', done: '已完成 · 可再接' },
  optional: '支線',
  exam: '執照考核',
  pay: '報酬',
  current: '洋流',
  visibility: '能見度',
  best: '{medal} · 最佳 {score}',
  noRecord: '尚無成績',
  moneyUnit: '元',
  summary: '{licence} · 資金 {money} 元 · 真實時數 {hours} h',
  otherTab: '其他委託與存檔',
  expedition: ['海洋探索委託', '在探索海域自由接巡檢、回收與部署的小委託；下水後在右上任務卡接案。'],
  backupTitle: '職涯存檔',
  backupHelp: '匯出成 JSON 備份，或從備份還原（會取代目前的職涯）。',
  exportButton: '匯出職涯',
  importButton: '匯入職涯',
  imported: '已匯入職涯存檔。',
  exported: '已匯出職涯存檔。',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** Money as a grouped integer, e.g. 12,000. */
export function moneyText(value) {
  return Math.round(Number(value) || 0).toLocaleString('en-US');
}

function cardMedia(contract, index) {
  const box = element('span', 'menu-site-media menu-card-media');
  box.append(element('span', 'menu-card-numeral', String(index + 1).padStart(2, '0')));
  const image = element('img');
  image.alt = '';
  image.loading = 'lazy';
  image.src = `menu/previews/${previewKey(contract.scenario)}.jpg`;
  image.addEventListener('error', function noPreview() {
    image.remove();
  });
  box.append(image);
  return box;
}

function recordText(record) {
  if (!record?.completed) return STRINGS.noRecord;
  return STRINGS.best.replace('{medal}', medalLabel(record.medal)).replace('{score}', String(record.best));
}

/** One work-order card; onChoose(contract) opens its detail screen. */
export function contractCard(contract, status, { career, index, onChoose }) {
  const { data, save } = career;
  const card = element('button', 'menu-site menu-play-card career-card');
  card.type = 'button';
  card.dataset.contract = contract.id;
  card.dataset.status = status.status;
  if (status.status === 'locked') card.setAttribute('aria-disabled', 'true');
  const body = element('span', 'menu-site-body');
  const kicker = [clientLabel(data, contract.client), jobLabel(data, contract.job)];
  if (contract.exam) kicker.push(STRINGS.exam);
  else if (contract.optional) kicker.push(STRINGS.optional);
  body.append(element('span', 'career-card-kicker', kicker.join(' · ')));
  body.append(element('strong', 'menu-card-title', contract.title));
  body.append(element('span', 'menu-card-line', contract.summary));
  const numbers = element('span', 'menu-site-numbers');
  numbers.append(readout(STRINGS.pay, moneyText(contract.pay), STRINGS.moneyUnit));
  const scene = career.sceneFor(contract.scenario);
  if (scene) {
    const facts = siteFacts(scene);
    numbers.append(readout(STRINGS.current, (contract.currentKn ?? facts.current).toFixed(1), 'kn'));
    numbers.append(readout(STRINGS.visibility, String(Math.round(facts.visibility ?? 0)), 'm'));
  }
  body.append(numbers);
  const foot = element('span', 'menu-card-foot');
  if (status.status === 'locked') {
    foot.append(element('span', 'menu-card-lock', status.reasons.map(function reason(entry) {
      return entry.text;
    }).join('；')));
  } else {
    const record = save.contracts[contract.id];
    const medal = element('span', 'menu-medal', recordText(record));
    medal.dataset.medal = record?.medal || 'none';
    foot.append(element('span', 'menu-row-status', STRINGS.status[status.status]), medal);
  }
  body.append(foot);
  card.append(cardMedia(contract, index), body);
  card.addEventListener('click', function choose() {
    onChoose(contract);
  });
  return card;
}

function backupPane(career, container) {
  container.append(element('h3', 'menu-label', STRINGS.backupTitle));
  container.append(element('p', 'menu-help', STRINGS.backupHelp));
  const row = element('div', 'career-backup');
  const exportButton = element('button', 'menu-next', STRINGS.exportButton);
  exportButton.type = 'button';
  exportButton.id = 'careerExport';
  const importButton = element('button', 'menu-next', STRINGS.importButton);
  importButton.type = 'button';
  importButton.id = 'careerImport';
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
  container.append(row);
}

/** The board screen. ctx.career: career/menu.js context; ctx.openContracts(): the expedition route. */
export function buildBoard(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen career-board');
  root.dataset.screen = 'board';
  root.setAttribute('aria-label', STRINGS.title);
  const head = element('div', 'career-board-head');
  const strip = element('p', 'career-strip');
  strip.id = 'boardSummary';
  head.append(element('h2', 'menu-heading', STRINGS.title), strip);
  root.append(head);
  const refreshers = [];
  const chapters = boardChapters(career.data, career.save, career.sceneKeys);
  const tabs = chapters.map(function chapterTab(entry) {
    return {
      id: entry.chapter.id,
      label: entry.chapter.title,
      mount(container) {
        container.append(element('p', 'menu-help', entry.chapter.summary));
        const grid = element('div', 'menu-card-grid');
        container.append(grid);
        function render() {
          const current = boardChapters(career.data, career.save, career.sceneKeys).find(function byId(item) {
            return item.chapter.id === entry.chapter.id;
          });
          grid.replaceChildren(...(current?.contracts || []).map(function card(item, index) {
            return contractCard(item.contract, item.status, { career, index, onChoose: ctx.openContract });
          }));
        }
        render();
        refreshers.push(render);
      },
    };
  });
  tabs.push({
    id: 'other',
    label: STRINGS.otherTab,
    mount(container) {
      const grid = element('div', 'menu-card-grid');
      const card = element('button', 'menu-site menu-play-card career-card');
      card.type = 'button';
      card.id = 'boardExpedition';
      const body = element('span', 'menu-site-body');
      body.append(element('strong', 'menu-card-title', STRINGS.expedition[0]));
      body.append(element('span', 'menu-card-line', STRINGS.expedition[1]));
      card.append(body);
      card.addEventListener('click', function expedition() {
        ctx.openContracts();
      });
      grid.append(card);
      container.append(grid);
      backupPane(career, container);
    },
  });
  const panel = createSettingsPanel({ idPrefix: 'board', tabs });
  root.append(panel.element);
  function renderStrip() {
    const save = career.save;
    strip.textContent = STRINGS.summary
      .replace('{licence}', gradeFor(career.data, save.licence).label)
      .replace('{money}', moneyText(save.money))
      .replace('{hours}', realHours(save).toFixed(1));
  }
  return {
    element: root,
    pose: 'training',
    tabs: panel,
    enter() {
      renderStrip();
      for (const refresh of refreshers) refresh();
    },
    show(tab) {
      panel.select(tab);
    },
  };
}
