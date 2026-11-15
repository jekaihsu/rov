// The "cannot reach the simulator" notice over the flight view. It stays hidden while a dive is starting or a
// brief drop is being retried, and only appears after a real timeout, in player words; the address, retry
// countdown and the developer command stay inside a collapsed 技術資訊 section. app.js reports connected() when
// world or state data arrives and lost() when the socket closes.

const STRINGS = {
  title: '無法連線到模擬器',
  body: '畫面會在連線恢復後自動繼續，不需要重新開始。若持續無法連線，請返回主選單後再試一次。',
  menu: '返回主選單',
  details: '技術資訊',
};
// Before the first data: the menu → game hand-off and a cold server start can take several seconds.
export const STARTUP_TIMEOUT_MS = 8000;
// After a drop: the client retries within about a second; a short blip should not flash a panel.
export const LOST_TIMEOUT_MS = 4000;

export function installConnectionNotice({ element, setTimer = setTimeout, clearTimer = clearTimeout }) {
  let timer = 0;
  let ever = false;
  function render() {
    const card = element.querySelector('.card');
    if (!card || card.dataset.player) return;
    card.dataset.player = '1';
    const title = card.querySelector('b');
    if (title) title.textContent = STRINGS.title;
    const technical = document.createElement('details');
    technical.className = 'offline-details';
    const summary = document.createElement('summary');
    summary.textContent = STRINGS.details;
    technical.append(summary, ...[...card.children].filter(function developer(child) {
      return child !== title;
    }));
    const body = document.createElement('p');
    body.className = 'offline-body';
    body.textContent = STRINGS.body;
    const menu = document.createElement('button');
    menu.type = 'button';
    menu.className = 'offline-menu';
    menu.textContent = STRINGS.menu;
    menu.addEventListener('click', function backToMenu() {
      document.getElementById('returnMenu')?.click();
    });
    card.append(body, menu, technical);
  }
  function show() {
    timer = 0;
    render();
    element.hidden = false;
  }
  function wait(ms) {
    if (timer) return;
    timer = setTimer(show, ms);
  }
  function connected() {
    ever = true;
    if (timer) clearTimer(timer);
    timer = 0;
    element.hidden = true;
  }
  function lost() {
    wait(ever ? LOST_TIMEOUT_MS : STARTUP_TIMEOUT_MS);
  }
  element.hidden = true;
  wait(STARTUP_TIMEOUT_MS);
  return {
    connected,
    lost,
    get visible() {
      return !element.hidden;
    },
  };
}
