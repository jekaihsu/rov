// DOM-only recovery stays usable without a WebGL context or game modules.
import { resolveLanguage } from './i18n/core.js';

const STRINGS = {
  en: ['Safe mode · low quality, effects off', 'Graphics unavailable. Update the graphics driver, then retry.',
    'The display connection was lost.', 'Loading failed. Retry to reload the game files.',
    'Retry', 'Main menu', 'Open log folder', 'Copy error summary', 'Dismiss',
    'Hardware graphics acceleration is unavailable.'],
  ja: ['セーフモード · 最低画質、効果オフ', '描画できません。ドライバーを更新して再試行してください。',
    '描画コンテキストが失われました。', '読み込みに失敗しました。ゲームファイルを再読み込みしてください。',
    '再試行', 'メインメニュー', 'ログフォルダーを開く', 'エラー概要をコピー', '閉じる',
    'ハードウェア描画アクセラレーションが利用できません。'],
  'zh-Hant': ['安全模式 · 最低畫質，已關閉後處理', '無法建立繪圖環境，請更新顯示驅動程式後重試。',
    '繪圖環境已中斷。', '載入失敗，請重試以重新載入遊戲檔案。', '重試', '主選單', '開啟紀錄資料夾', '複製錯誤摘要', '關閉',
    '系統無法啟用顯卡加速。'],
  'zh-Hans': ['安全模式 · 最低画质，已关闭后处理', '无法创建绘图环境，请更新显示驱动程序后重试。',
    '绘图环境已中断。', '加载失败，请重试以重新载入游戏文件。', '重试', '主菜单', '打开日志文件夹', '复制错误摘要', '关闭',
    '系统无法启用显卡加速。'],
};

function labels() {
  let stored;
  try {
    stored = JSON.parse(localStorage.getItem('rov.display.v1') || '{}').language;
  } catch { /* Recovery also works when storage is unavailable. */ }
  const language = resolveLanguage({ query: new URLSearchParams(location.search).get('lang'),
    stored, browser: navigator.languages });
  const [safe, graphics, context, frontend, retry, menu, logs, copy, dismiss, blocked] = STRINGS[language];
  return { safe, graphics, context, frontend, retry, menu, logs, copy, dismiss, blocked };
}

function button(host, label, action) {
  const control = document.createElement('button');
  control.type = 'button';
  control.textContent = label;
  control.addEventListener('click', action);
  host.append(control);
}

export function diagnosticActions(host, code) {
  const text = labels();
  if (window.rovDesktop?.openLogs) button(host, text.logs, () => window.rovDesktop.openLogs());
  const detail = code === 'offline' ? host.querySelector('.offline-body')?.textContent : text[code] || text.frontend;
  const summary = ['ROV Solution', code, detail].filter(Boolean).join(' · ');
  button(host, text.copy, async function copySummary() {
    try {
      await navigator.clipboard.writeText(summary);
    } catch {
      const field = document.createElement('input');
      field.readOnly = true;
      field.value = summary;
      host.append(field);
      field.select();
    }
  });
}

function recover(code) {
  const url = new URL(location.href);
  const graphics = ['graphics', 'context'].includes(code);
  window.rovDesktop?.record?.(code);
  if (graphics && !url.searchParams.has('safe')) {
    url.searchParams.set('safe', '1');
    url.searchParams.set('recovery', code);
    location.replace(url);
    return;
  }
  const previous = document.getElementById('recoveryPanel');
  if (previous?.open && previous.dataset.code !== 'timeout') return;
  previous?.remove();
  const panel = document.createElement('dialog');
  panel.id = 'recoveryPanel';
  panel.dataset.code = code;
  const text = labels();
  const detail = document.createElement('p');
  detail.textContent = text[code] || text.frontend;
  panel.append(detail);
  button(panel, text.retry, () => location.reload());
  button(panel, text.menu, () => {
    for (const key of ['play', 'replay', 'menu', 'recovery']) url.searchParams.delete(key);
    location.assign(url);
  });
  diagnosticActions(panel, code);
  panel.addEventListener('cancel', event => event.preventDefault());
  document.body.append(panel);
  panel.showModal();
}

export function installRecovery() {
  const query = new URLSearchParams(location.search);
  addEventListener('webglcontextlost', event => {
    if (!event.target.matches?.('canvas.gl,canvas.menu-canvas')) return;
    event.preventDefault();
    recover('context');
  }, true);
  addEventListener('error', event => {
    if (event.error) recover('frontend');
  });
  addEventListener('unhandledrejection', () => recover('frontend'));
  if (query.has('safe')) {
    const banner = document.createElement('aside');
    banner.id = 'safeNotice';
    const text = labels();
    const reason = query.get('recovery');
    const knownReason = ['graphics', 'context', 'blocked'].includes(reason);
    banner.textContent = knownReason ? text[reason] + ' ' + text.safe : text.safe;
    if (knownReason) diagnosticActions(banner, reason);
    button(banner, text.dismiss, () => banner.remove());
    document.body.append(banner);
  }
}

export function bootFailure(error) {
  recover(/webgl|creating.*context/i.test(error?.message || '') ? 'graphics' : 'frontend');
}

export function startupWatchdog() {
  const timer = setTimeout(() => recover('timeout'), 60000);
  return function finished() {
    clearTimeout(timer);
    document.querySelector('#recoveryPanel[data-code="timeout"]')?.remove();
  };
}
