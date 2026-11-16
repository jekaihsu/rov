// Browser locale bootstrap. All selected dictionaries load before importing modules render their STRINGS.
import {
  labelSnapshot, getLanguage, localize, registerTranslations, resolveLanguage, setLanguage, subscribe,
} from './core.js';
import { refreshLabels } from './dom.js';
export { getLanguage, localize, setLanguage, subscribe } from './core.js';

const STRINGS = localize('i18n.index', {
  changed: '語言已切換；尚未更新的畫面會在返回主選單後生效。',
});
let preference;
let query;

async function loadLanguage(language) {
  if (language === 'zh-Hant') return;
  const response = await fetch(new URL('./namespaces.json', import.meta.url));
  const namespaces = await response.json();
  await Promise.all(namespaces.map(async function load(namespace) {
    try {
      const response = await fetch(new URL(`./locales/${language}/${namespace}.json`, import.meta.url));
      if (response.ok) registerTranslations(language, namespace, await response.json());
    } catch {
      // An unavailable dictionary falls back to the module's Traditional Chinese source.
    }
  }));
}

if (typeof document !== 'undefined') {
  query = new URLSearchParams(globalThis.location?.search).get('lang');
  try {
    preference = JSON.parse(localStorage.getItem('rov.display.v1') || '{}').language;
  } catch {
    // Storage can be disabled in private windows.
  }
  let steam;
  try {
    steam = (await globalThis.rovDesktop?.steamStatus?.())?.language;
  } catch {
    // Steam is optional and can be offline.
  }
  const language = resolveLanguage({ query, stored: preference,
    steam, browser: navigator.languages || [navigator.language] });
  try {
    await loadLanguage(language);
  } catch {
    // Offline first launch still has the source strings.
  }
  setLanguage(language);
  document.documentElement.lang = language;
  const style = document.createElement('link');
  style.rel = 'stylesheet';
  style.href = new URL('./i18n.css', import.meta.url).href;
  document.head.append(style);
  let revision = 0;
  document.addEventListener('rov-display-change', async function changed(event) {
    const stored = event.detail.language;
    if (event.detail.changed !== 'language') {
      document.documentElement.lang = getLanguage();
      return;
    }
    preference = stored;
    const current = ++revision;
    const next = resolveLanguage({ query, stored });
    await loadLanguage(next).catch(function unavailable() {});
    if (current !== revision) return;
    const before = labelSnapshot();
    setLanguage(next);
    refreshLabels(before, labelSnapshot());
    document.documentElement.lang = next;
    const selector = document.getElementById('displayLanguage');
    if (selector) selector.value = next;
    let notice = document.getElementById('i18nNotice');
    if (!notice) {
      notice = document.createElement('p');
      notice.id = 'i18nNotice';
      notice.setAttribute('role', 'status');
      document.body.append(notice);
    }
    notice.textContent = STRINGS.changed;
  });
}
