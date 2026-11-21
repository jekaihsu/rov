// Developer readout for the Steam mock backend: shown in the engineering drawer so local JSON unlocks
// and Rich Presence can be inspected without a Steam App ID. Hidden on Steam player builds when Steamworks
// is connected; always available while the mock backend is active.

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.steam_dev_panel', {
  title: 'Steam 假後端',
  empty: '尚無本機 mock 資料。',
  refresh: '重新整理',
  backend: '後端：{backend}',
  path: '檔案：{path}',
  earned: '已解鎖',
  presence: '狀態列',
  none: '（無）',
});

function line(label, value) {
  const row = document.createElement('p');
  row.className = 'steam-dev-line';
  row.textContent = `${label}${value}`;
  return row;
}

export function installSteamDevPanel(host) {
  const desktop = globalThis.window?.rovDesktop;
  if (!host || typeof desktop?.steamStatus !== 'function') return null;

  const section = document.createElement('section');
  section.className = 'steam-dev-panel';
  section.hidden = true;
  const title = document.createElement('strong');
  title.textContent = STRINGS.title;
  const meta = document.createElement('div');
  const body = document.createElement('pre');
  body.className = 'steam-dev-json';
  const refresh = document.createElement('button');
  refresh.type = 'button';
  refresh.textContent = STRINGS.refresh;
  section.append(title, meta, body, refresh);
  host.append(section);

  async function render() {
    let status;
    try {
      status = await desktop.steamStatus();
    } catch {
      section.hidden = true;
      return;
    }
    const show = status?.backend === 'mock' || status?.edition !== 'steam';
    section.hidden = !show;
    if (!show) return;
    meta.replaceChildren(
      line('', STRINGS.backend.replace('{backend}', status.backend || '—')),
      line('', STRINGS.path.replace('{path}', status.mockPath || status.cloudPath || '—')),
    );
    let mock = null;
    try {
      mock = await desktop.steamMock?.();
    } catch {
      mock = null;
    }
    if (!mock) {
      body.textContent = STRINGS.empty;
      return;
    }
    body.textContent = JSON.stringify(mock, null, 2) || STRINGS.empty;
  }

  refresh.onclick = function onRefresh() {
    render();
  };
  render();
  return { update: render, root: section };
}
