// C1-4 big-event presentation for contract id c1_signoff_exam: skippable intro radio sequence (鏡頭1), a mid-dive
// choice when two of three anomaly photos are done (continue vs note-only for the unlisted crack), and outro lines
// on settle by branch. Music is cued via data-music-cue on documentElement; dive wires startIntro/update/onSettle.

import { localize } from '../i18n/core.js';

const STRINGS = localize('career.chapter_event', {
  skip: '跳過',
  continueShot: '繼續拍未列裂縫',
  noteOnly: '只交三點，筆記備註',
  choiceLead: '旁邊多一條縫。拍下來，還是只交三點？',
});

export const SIGNOFF_CONTRACT = 'c1_signoff_exam';
const ANOMALY_IDS = ['a2_crack', 'b3_spall', 'quay_chip'];

const INTRO_LINES = [
  { speaker: '葉理', text: '交班前我要檔案。' },
  { speaker: '林岑', text: '窗口短。先停。' },
  { speaker: '周楷', text: '線我備短放。' },
  { speaker: '方晴', text: '還有二十。我報時。' },
  { speaker: '馬力', text: '慢就是快。別瞎衝。' },
  { speaker: '林岑', text: 'R-1，只打三點異常。' },
];

const OUTRO_COMPLETE = [
  { speaker: '林岑', text: '三點齊。回收。' },
  { speaker: '葉理', text: '檔案到。我去交班。' },
  { speaker: '馬力', text: '準時不代表乾淨。你自己知。' },
];

const OUTRO_ABORT = [
  { speaker: '林岑', text: '中止。窗不夠。' },
  { speaker: '周楷', text: '收線。人機優先。' },
  { speaker: '葉理', text: '……寫待複查。我延交班。' },
  { speaker: '林岑', text: '岸台，謝你。' },
  { speaker: '馬力', text: '這趟你做得對。' },
];

const LINE_MS = 3200;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function setMusicCue(value) {
  if (typeof document === 'undefined') return;
  document.documentElement.dataset.musicCue = value || '';
  document.dispatchEvent(new CustomEvent('career-music-cue', { detail: { cue: value || '' } }));
}

function anomalyDone(snapshot) {
  const done = new Set((snapshot?.items || []).filter(function finished(item) {
    return item.done && ANOMALY_IDS.includes(item.id);
  }).map(function id(item) {
    return item.id;
  }));
  return done.size;
}

/**
 * contractId: only c1_signoff_exam activates; onChoice('continue'|'note').
 * Returns {startIntro, update, onSettle, skip}.
 */
export function installChapterEvent({ contractId, onChoice } = {}) {
  const active = contractId === SIGNOFF_CONTRACT;
  const root = element('div', 'chapter-event');
  root.hidden = true;
  const caption = element('p', 'chapter-event-caption');
  const speaker = element('strong', 'chapter-event-speaker');
  const line = element('span', 'chapter-event-line');
  caption.append(speaker, line);
  const skipBtn = element('button', 'chapter-event-skip', STRINGS.skip);
  skipBtn.type = 'button';
  const choice = element('div', 'chapter-event-choice');
  choice.hidden = true;
  const lead = element('p', 'chapter-event-choice-lead', STRINGS.choiceLead);
  const actions = element('div', 'chapter-event-choice-actions');
  const continueBtn = element('button', 'chapter-event-continue', STRINGS.continueShot);
  continueBtn.type = 'button';
  const noteBtn = element('button', 'chapter-event-note', STRINGS.noteOnly);
  noteBtn.type = 'button';
  actions.append(continueBtn, noteBtn);
  choice.append(lead, actions);
  root.append(caption, skipBtn, choice);
  if (typeof document !== 'undefined') document.body.append(root);

  let introIndex = -1;
  let introTimer = 0;
  let introPlaying = false;
  let choiceOffered = false;
  let branch = '';

  function showLine(entry) {
    root.hidden = false;
    choice.hidden = true;
    skipBtn.hidden = !introPlaying;
    caption.hidden = false;
    speaker.textContent = entry?.speaker || '';
    line.textContent = entry?.text || '';
  }

  function endIntro() {
    introPlaying = false;
    introIndex = INTRO_LINES.length;
    skipBtn.hidden = true;
    caption.hidden = true;
    root.hidden = choiceOffered ? false : true;
    setMusicCue('dive');
  }

  function advanceIntro() {
    introIndex += 1;
    if (introIndex >= INTRO_LINES.length) {
      endIntro();
      return;
    }
    showLine(INTRO_LINES[introIndex]);
    introTimer = LINE_MS;
  }

  function startIntro() {
    if (!active) return;
    introPlaying = true;
    introIndex = -1;
    choiceOffered = false;
    branch = '';
    setMusicCue('signoff_intro');
    advanceIntro();
  }

  function skip() {
    if (!introPlaying) return;
    endIntro();
  }

  skipBtn.addEventListener('click', skip);

  function offerChoice() {
    if (choiceOffered) return;
    choiceOffered = true;
    root.hidden = false;
    caption.hidden = true;
    skipBtn.hidden = true;
    choice.hidden = false;
    setMusicCue('signoff_choice');
    showLine({ speaker: '林岑', text: STRINGS.choiceLead });
    caption.hidden = false;
  }

  function pick(kind) {
    branch = kind;
    choice.hidden = true;
    onChoice?.(kind);
    setMusicCue(kind === 'continue' ? 'signoff_rush' : 'signoff_calm');
  }

  continueBtn.addEventListener('click', function onContinue() {
    pick('continue');
  });
  noteBtn.addEventListener('click', function onNote() {
    pick('note');
  });

  function update(snapshot, state, dt = 0) {
    if (!active) return;
    if (introPlaying) {
      introTimer -= Math.max(0, dt) * 1000;
      if (introTimer <= 0) advanceIntro();
    }
    if (!choiceOffered && !introPlaying && anomalyDone(snapshot) >= 2) offerChoice();
    void state;
  }

  function onSettle(outcome) {
    if (!active) return;
    const aborted = outcome?.pay?.outcome === 'aborted'
      || outcome?.outcome === 'aborted'
      || branch === 'note';
    const lines = aborted ? OUTRO_ABORT : OUTRO_COMPLETE;
    setMusicCue(aborted ? 'signoff_outro_abort' : 'signoff_outro');
    let i = 0;
    function next() {
      if (i >= lines.length) {
        root.hidden = true;
        return;
      }
      showLine(lines[i]);
      skipBtn.hidden = true;
      choice.hidden = true;
      i += 1;
      setTimeout(next, LINE_MS);
    }
    next();
  }

  return { startIntro, update, onSettle, skip, branch: function current() {
    return branch;
  } };
}
