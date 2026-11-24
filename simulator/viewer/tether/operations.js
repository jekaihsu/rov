// Cable tender radio calls and the twist read-out on the HUD system card, from the optional state.tether_ops.
// Servers without tether_ops are ignored. The radio sits where the campaign radio does, on the same story layer
// (hud/tokens.css --z-story), and stays silent while campaign dialogue is on screen, so the two never overlap.
import { getFidelity } from '../fidelity.js';
const STRINGS = {
  speaker: '甲板 · 纜線手',
  length: '已放纜',
  launch: '從作業區上游下水，保持視線，僅放出所需纜線。',
  structure: '纜線接近結構，留意纜線走向並減少多餘放纜。',
  twist: '扭轉超過兩圈，請反向解開。',
  tension: '張力超過額定工作負載，停止硬拉並評估纜線。',
  snag: '纜線卡住或纏繞。不要拉纜，掉頭沿纜線回到卡點，再反向解開。',
  released: '脫困程序已記錄。',
  stall: '收纜受阻停止，可能卡纜，請勿硬拉。',
  reel: {
    free: '纜盤放開，纜線隨載具拉出。',
    hold: '纜盤剎住，長度固定。',
    pay_out: '手動放纜中。',
    haul_in: '收纜中，注意張力。',
    auto: '自動恆張力收放。',
  },
  turns: '淨扭轉圈數',
  unwind: '請反向解開扭轉',
  score: '脫困評分',
  discipline: '放纜紀律',
};
const SHOW_MS = 6000;
const SYSTEM_CARD = '1';
let radio = null;
let lastId = 0;
let until = 0;

const STYLE = `
  .tether-radio{position:fixed;left:max(15%,220px);top:max(15%,calc(3% + 108px));width:31%;max-width:45%;
    box-sizing:border-box;padding:12px 20px;background:rgba(8,18,26,.72);backdrop-filter:blur(14px);border-left:2px solid #4fd1e0;
    color:#e8f1f5;z-index:var(--z-story);pointer-events:none}
  .tether-radio[hidden]{display:none}
  .tether-radio strong{color:#4fd1e0;font-size:12px;letter-spacing:.1em}
  .tether-radio p{font-size:16px;line-height:1.5;margin:6px 0 0}
  @media(max-width:720px){.tether-radio{left:4%;top:60px;width:58%;max-width:58%;padding:8px 12px}
    .tether-radio p{font-size:14px}}
`;

function createRadio() {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
  const section = document.createElement('section');
  section.className = 'tether-radio';
  section.setAttribute('role', 'status');
  section.hidden = true;
  document.body.append(section);
  return section;
}

function campaignTalking() {
  return [...document.querySelectorAll('.story-radio')].some(function shown(element) {
    return !element.hidden;
  });
}

function eventText(event) {
  if (event.code === 'length') return `${STRINGS.length} ${event.metres} m · ${STRINGS.launch}`;
  if (event.code === 'reel') return STRINGS.reel[event.mode] || '';
  const text = STRINGS[event.code];
  return typeof text === 'string' ? text : STRINGS.snag;
}

function showRadio(event) {
  const speaker = document.createElement('strong');
  speaker.textContent = STRINGS.speaker;
  const text = document.createElement('p');
  text.textContent = eventText(event);
  radio.replaceChildren(speaker, text);
  until = performance.now() + SHOW_MS * (getFidelity().get("radioDuration") ?? 1);
}

function systemCardText(ops) {
  const warn = ops.twist_warning ?? Math.abs(ops.turns) > 2;
  const lines = [`${STRINGS.turns} ${ops.turns}${warn ? ` · ${STRINGS.unwind}` : ''}`];
  if (ops.discipline_score != null) lines.push(`${STRINGS.discipline} ${ops.discipline_score}/100`);
  if (ops.result) lines.push(`${STRINGS.score} ${ops.result.score}/100`);
  return lines.join('\n');
}

// Called once per frame after the flight HUD has rewritten its peek card.
export function updateTetherOperations(state) {
  const ops = state?.tether_ops;
  if (!ops) return;
  radio ||= createRadio();
  const events = ops.events || [];
  // A scenario reload restarts the server's event ids.
  if (events.length && events.at(-1).id < lastId) lastId = 0;
  const fresh = events.filter(function unseen(item) {
    return item.id > lastId;
  });
  if (fresh.length) {
    lastId = fresh.at(-1).id;
    showRadio(fresh.at(-1));
  }
  radio.hidden = campaignTalking() || performance.now() > until;
  const card = document.getElementById('flightPeek');
  const body = card?.querySelector('p');
  if (card?.dataset.card === SYSTEM_CARD && body) body.textContent += `\n${systemCardText(ops)}`;
}
