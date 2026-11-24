// Career work-order radio: captions on the checklist card plus voice clips via audio/voice.js.
// Lines come from contracts.json `radio.lines` (when/speaker/text). Missing clips fall back to caption only.
// `when`: start | done | partial | licence | <deliverable id>. Pure helpers stay DOM-free for node tests.
import {installVoice} from '../audio/voice.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('career.radio', {
  sep: '：',
});

const LINE_MS = 4200;
const GAP_MS = 280;

/** Lines for a trigger; falls back to legacy speaker/start/done/partial fields. */
export function linesFor(radio, when) {
  if (!radio) return [];
  const listed = Array.isArray(radio.lines)
    ? radio.lines.filter(function match(line) {
      return line && line.when === when && line.speaker && line.text;
    }).map(function copy(line) {
      return {speaker: String(line.speaker), text: String(line.text)};
    })
    : [];
  if (listed.length) return listed;
  if (when === 'start' && radio.start) {
    return [{speaker: String(radio.speaker || ''), text: String(radio.start)}];
  }
  if (when === 'done' && radio.done) {
    return [{speaker: String(radio.speaker || ''), text: String(radio.done)}];
  }
  if (when === 'partial' && radio.partial) {
    return [{speaker: String(radio.speaker || ''), text: String(radio.partial)}];
  }
  return [];
}

/**
 * Caption + voice queue for one contract dive.
 * mount(parent): attaches the caption element. play(when): queues lines for that trigger (once per id).
 */
export function createCareerRadio({voice = null} = {}) {
  const radioVoice = voice || installVoice();
  const root = document.createElement('p');
  root.className = 'career-radio';
  root.hidden = true;
  const speaker = document.createElement('strong');
  const text = document.createTextNode('');
  root.append(speaker, text);
  const queue = [];
  const played = new Set();
  let radio = null;
  let timer = null;
  let busyUntil = 0;

  function showLine(line) {
    speaker.textContent = line.speaker ? `${line.speaker}${STRINGS.sep}` : '';
    text.textContent = line.text || '';
    root.hidden = !line.text;
    Promise.resolve(radioVoice.playLine({
      speaker: line.speaker,
      text: line.text,
      language: 'zh-TW',
    })).catch(function ignoreVoiceErrors() {});
  }

  function drain() {
    timer = null;
    if (!queue.length) {
      busyUntil = 0;
      return;
    }
    const line = queue.shift();
    showLine(line);
    busyUntil = performance.now() + LINE_MS;
    timer = setTimeout(drain, LINE_MS + GAP_MS);
  }

  function play(when) {
    const key = String(when || '');
    if (!key || played.has(key)) return;
    const batch = linesFor(radio, key);
    if (!batch.length) return;
    played.add(key);
    queue.push(...batch);
    if (!timer) drain();
  }

  function bind(next) {
    radio = next || null;
    played.clear();
    queue.length = 0;
    if (timer) clearTimeout(timer);
    timer = null;
    busyUntil = 0;
    root.hidden = true;
    speaker.textContent = '';
    text.textContent = '';
  }

  function mount(parent) {
    parent?.append?.(root);
    return root;
  }

  function stop() {
    if (timer) clearTimeout(timer);
    timer = null;
    queue.length = 0;
    radioVoice.stop?.();
  }

  return {
    element: root,
    bind,
    play,
    mount,
    stop,
    get busy() {
      return performance.now() < busyUntil || queue.length > 0;
    },
  };
}
