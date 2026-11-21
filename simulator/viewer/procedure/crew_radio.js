// Deck crew radio during the pre-dive check: routine items (trim, compass and depth zero, communication, tender
// ready) are reported by the crew instead of being clicked, and the crew answers a defect report, a fix or a false
// alarm. A missed defect is called by the supervisor once its fault shows up in the dive. Characters follow
// docs/story/bible.md (周楷 tether hand, 方晴 deck, 林岑 supervisor). Lines play through the shared radio voice
// (audio/voice.js: clip if generated, otherwise text with the radio click) and show as a caption on the story layer;
// the caption waits while campaign dialogue is on screen, so the two never overlap.
import {installVoice} from '../audio/voice.js';
import { getLanguage, localize } from '../i18n/index.js';

const STRINGS = localize('procedure.crew_radio', {
  speakers: {tender: '周楷', deck: '方晴', supervisor: '林岑'},
  roles: {tender: '纜線手', deck: '甲板', supervisor: '督導'},
  crew: {
    trim: ['deck', '配重和配平看過了，跟上次一樣，水平、微正浮。'],
    instruments: ['deck', '深度歸零了，羅盤跟船艏對過。'],
    communication: ['tender', '通訊正常，遙測跟影像都在跳。'],
    tender: ['tender', '纜理好了，線還夠。隨時可以放。'],
  },
  found: ['deck', '看到了。先處理掉再下水。'],
  falseReport: ['deck', '我看了一下，這裡沒問題。'],
  fixed: {
    line_fouled: ['tender', '繩子剪掉了，護罩裡乾淨。'],
    guard_cracked: ['deck', '護罩換了一個新的，鎖好了。'],
    oring_debris: ['deck', 'O 形環擦乾淨、重新上油裝回去了。'],
    connector_unlocked: ['tender', '固定環轉到底，鎖上了。'],
  },
  faults: {
    line_fouled: 'T{n} 推力掉了。下水前護罩上那段繩子沒清，被捲進去了。',
    guard_cracked: 'T{n} 停了。裂掉的護罩碎片卡進螺旋槳。',
    oring_debris: '漏水警報。密封面上的沙沒清，馬上上浮回收。',
    connector_unlocked: '影像斷斷續續。纜線接頭固定環沒鎖到底。',
  },
});
const LINE_MS = 5200;                 // how long one call stays on screen
const GAP_MS = 400;
const OPEN_ATTRIBUTE = 'data-open';

function campaignTalking() {
  return [...document.querySelectorAll('.story-radio')].some(function shown(element) {
    return !element.hidden;
  });
}

/** Text of a missed-defect fault, for the dive prompt; null for faults of the legacy checklist. */
export function faultText(event) {
  const template = STRINGS.faults[event?.defect];
  if (!template) return null;
  return template.replace('{n}', String((event.thruster ?? 0) + 1));
}

/** [role, text] of the call an event triggers, or null. */
export function callFor(event) {
  if (event.action === 'crew') return STRINGS.crew[event.key] || null;
  if (event.action === 'defect_found') return STRINGS.found;
  if (event.action === 'false_report') return STRINGS.falseReport;
  if (event.action === 'defect_fixed') return STRINGS.fixed[event.defect] || null;
  if (event.action === 'fault') {
    const text = faultText(event);
    return text ? ['supervisor', text] : null;
  }
  return null;
}

export function createCrewRadio() {
  const voice = installVoice();
  const root = document.createElement('section');
  root.className = 'crew-radio';
  root.id = 'crewRadio';
  root.setAttribute('role', 'status');
  root.hidden = true;
  const speaker = document.createElement('strong');
  const text = document.createElement('p');
  root.append(speaker, text);
  document.body.append(root);
  const queue = [];
  let timer = null;
  let busyUntil = 0;
  let flight = false;
  function showNext() {
    timer = null;
    flight = false;
    if (!queue.length) {
      root.hidden = true;
      root.removeAttribute(OPEN_ATTRIBUTE);
      return;
    }
    if (campaignTalking()) {
      timer = setTimeout(showNext, 500);
      return;
    }
    const [role, line, localRate] = queue.shift();
    root.toggleAttribute('data-flight', !!localRate);
    const name = STRINGS.speakers[role];
    speaker.textContent = `${name} · ${STRINGS.roles[role]}`;
    text.textContent = line;
    root.dataset.role = role;
    root.hidden = false;
    root.setAttribute(OPEN_ATTRIBUTE, '');
    const locale = localRate ? getLanguage() : 'zh-Hant';
    const language = {'zh-Hant': 'zh-TW', 'zh-Hans': 'zh-CN'}[locale] || locale;
    Promise.resolve(voice.playLine({speaker: name, text: line, language, localRate})).catch(function ignore() {});
    busyUntil = performance.now() + LINE_MS;
    timer = setTimeout(showNext, LINE_MS + (queue.length ? GAP_MS : 0));
  }
  function say(call) {
    if (!call) return;
    queue.push(call);
    if (!timer && performance.now() >= busyUntil) showNext();
  }
  function clear() {
    queue.length = 0;
    clearTimeout(timer);
    timer = null;
    busyUntil = 0;
    root.hidden = true;
    root.removeAttribute(OPEN_ATTRIBUTE);
  }
  /** The text on screen and the calls waiting behind it (browser checks). */
  function debug() {
    return {open: !root.hidden, speaker: speaker.textContent, text: text.textContent, queued: queue.length};
  }
  function busy() {
    return !!timer || campaignTalking();
  }
  function sayFlight(call) {
    if (busy()) return;
    const [role, text] = call;
    say([role, text, {supervisor: 0.92, tender: 1.06, deck: 1}[role]]);
    flight = true;
  }
  function clearFlight() {
    if (!flight) return;
    voice.stop();
    clearTimeout(timer);
    busyUntil = 0;
    showNext();
  }
  return {say, clear, debug, busy, sayFlight, clearFlight};
}
