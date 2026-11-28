// About / credits tab for the launch and pause settings panels: a scrollable production roll and the
// full third-party notices text. Sections are focusable so the menu navigator (pad D-pad / arrows) can
// walk the list; LB/RB still switch tabs. Notices load from viewer/legal/THIRD_PARTY_NOTICES.txt.
import { createDetailSheet } from './big_picture.js';
import { element } from './settings.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.credits', {
  tab: '關於',
  title: '製作名單與授權',
  open: '開啟製作名單與授權',
  openHelp: '可捲動的製作名單與第三方授權全文；手把可用方向鍵或左搖桿移動焦點。',
  studio: '製作',
  studioBody: 'ROV Solution 由 YX 專案團隊製作。模擬器以真實遙控潛水器操作為體驗基準，並提供可關閉的訓練輔助。',
  disclaimer: '免責聲明',
  disclaimerBody:
    '本模擬器僅供娛樂與訓練輔助，不是真實遙控潛水器操作認證、職業資格或任何官方考照。遊戲內考照與進度僅適用於本作品。',
  ai: 'AI 生成內容',
  aiBody:
    '無線電語音以文字轉語音合成預先製作。部分魚類模型貼圖取自第三方 CC0 素材包，該包貼圖為預先以 AI 圖像生成，並非實拍；執行時不會再生成。詳見商店 AI 揭露說明。',
  privacy: '隱私',
  privacyBody:
    '遊戲本身不收集個人資料。內部版支援區域網路多人遊戲。進度與收藏保存在本機，並可透過 Steam 雲端同步（若啟用）。',
  assets: '第三方資產',
  assetsBody:
    '場景模型、掃描材質、音樂與手把對應資料的名稱、版本、授權與來源見下方授權全文。',
  licenses: '第三方授權全文',
  licensesLoading: '正在載入授權清單…',
  licensesMissing: '找不到授權清單檔案。請確認已執行 simulator/tools/third_party_notices.py。',
});

const NOTICES_URL = new URL('../legal/THIRD_PARTY_NOTICES.txt', import.meta.url);

function section(sheet, label, body) {
  const text = element('p', 'bp-sheet-text', body);
  return sheet.section(label, text);
}

function fillSheet(sheet, noticesText) {
  sheet.clear();
  sheet.setTitle(STRINGS.title);
  section(sheet, STRINGS.studio, STRINGS.studioBody);
  section(sheet, STRINGS.disclaimer, STRINGS.disclaimerBody);
  section(sheet, STRINGS.ai, STRINGS.aiBody);
  section(sheet, STRINGS.privacy, STRINGS.privacyBody);
  section(sheet, STRINGS.assets, STRINGS.assetsBody);
  const block = element('pre', 'menu-credits-notices', noticesText || STRINGS.licensesMissing);
  block.tabIndex = 0;
  sheet.section(STRINGS.licenses, block);
}

let sharedSheet = null;
let noticesCache = null;
let noticesPromise = null;

function loadNotices() {
  if (noticesCache != null) return Promise.resolve(noticesCache);
  if (noticesPromise) return noticesPromise;
  noticesPromise = fetch(NOTICES_URL)
    .then(function response(res) {
      if (!res.ok) throw new Error(String(res.status));
      return res.text();
    })
    .then(function text(body) {
      noticesCache = body;
      return body;
    })
    .catch(function failed() {
      noticesCache = '';
      return '';
    });
  return noticesPromise;
}

function getSheet() {
  if (sharedSheet) return sharedSheet;
  sharedSheet = createDetailSheet(STRINGS.title);
  sharedSheet.element.classList.add('menu-credits-sheet');
  sharedSheet.element.setAttribute('aria-label', STRINGS.title);
  return sharedSheet;
}

export async function openCreditsSheet() {
  const sheet = getSheet();
  fillSheet(sheet, STRINGS.licensesLoading);
  sheet.open();
  const text = await loadNotices();
  if (sheet.element.open) fillSheet(sheet, text);
  return sheet;
}

/** Mount the About tab: short summary plus a button that opens the scrollable credits sheet. */
export function mountCredits(pane) {
  pane.classList.add('menu-credits');
  pane.append(element('p', 'menu-help', STRINGS.studioBody));
  pane.append(element('p', 'menu-help', STRINGS.disclaimerBody));
  const button = element('button', 'menu-next menu-wide', STRINGS.open);
  button.type = 'button';
  button.id = 'menuCreditsOpen';
  button.title = STRINGS.openHelp;
  button.addEventListener('click', function open() {
    openCreditsSheet();
  });
  pane.append(button, element('p', 'menu-help', STRINGS.openHelp));
  // Inline focusable summaries so pad users can scroll the tab without opening the sheet first.
  for (const [label, body] of [
    [STRINGS.ai, STRINGS.aiBody],
    [STRINGS.privacy, STRINGS.privacyBody],
    [STRINGS.assets, STRINGS.assetsBody],
  ]) {
    const block = element('section', 'menu-credits-block');
    block.tabIndex = 0;
    block.append(element('h3', 'menu-label', label));
    block.append(element('p', 'menu-help', body));
    pane.append(block);
  }
  return pane;
}

export { STRINGS as CREDITS_STRINGS };
