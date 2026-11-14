// Cable teammate radio feedback and system-card readout; old servers remain supported.
const STRINGS = {
  structure: '纜線接近結構，留意纜線走向並減少多餘放纜。',
  twist: '扭轉超過兩圈，請反向解開。',
  speaker: '甲板 · 纜線手', length: '已放纜', tension: '張力升高，停止硬拉並評估纜線。',
  snag: '纜線接近結構。不要拉纜，掉頭沿纜線回到卡點，再反向解開。',
  released: '脫困程序已記錄。', launch: '從作業區上游下水，保持視線，僅放出所需纜線。',
  turns: '淨扭轉圈數', unwind: '請反向解開扭轉', score: '脫困評分',
};
let radio;
let last = 0;
let until = 0;
export function updateTetherOperations(state) {
  const ops = state?.tether_ops;
  if (!ops) return;
  if (!radio) {
    radio = document.createElement('section');
    radio.className = 'story-radio';
    radio.setAttribute('role', 'status');
    radio.style.pointerEvents = 'none';
    document.body.append(radio);
  }
  const events = ops.events || [];
  if (events.length && events.at(-1).id < last) last = 0;
  const event = events.filter(item => item.id > last).at(-1);
  if (event) {
    last = event.id;
    const speaker = document.createElement('strong');
    speaker.textContent = STRINGS.speaker;
    const text = document.createElement('p');
    text.textContent = event.code === 'length' ? `${STRINGS.length} ${event.metres} m · ${STRINGS.launch}`
      : STRINGS[event.code] || STRINGS.snag;
    radio.replaceChildren(speaker, text);
    until = performance.now() + 6000;
  }
  radio.hidden = performance.now() > until;
  const card = document.querySelector('#flightPeek');
  if (card?.querySelector('strong')?.textContent === '載具系統') {
    const line = document.createElement('span');
    line.textContent = `\n${STRINGS.turns} ${ops.turns} · ${Math.abs(ops.turns) > 2 ? STRINGS.unwind : ''}`
      + (ops.result ? `\n${STRINGS.score} ${ops.result.score}/100` : '');
    card.querySelector('p').append(line);
  }
}
