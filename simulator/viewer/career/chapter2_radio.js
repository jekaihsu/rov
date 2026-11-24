// Triggered radio cues for Chapter 2 aquaculture work orders (翁慈 / YX crew).
// Presentation only: when a deliverable completes or a light/speed hazard fires, show a short caption
// through the same story-radio layer style. Does not change physics or protocol.
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.chapter2_radio', {
  fallbackSpeaker: '向潮－指揮',
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

let styleReady = false;

function ensureStyle() {
  if (styleReady || typeof document === 'undefined') return;
  styleReady = true;
  const style = document.createElement('style');
  style.textContent = `
    .c2-radio{position:fixed;left:max(15%,220px);top:max(15%,calc(3% + 108px));width:31%;max-width:45%;
      padding:12px 18px;background:rgba(8,18,26,.72);backdrop-filter:blur(14px);
      border-left:2px solid #4fd1e0;color:#e8f1f5;z-index:var(--z-story);pointer-events:none}
    .c2-radio[hidden]{display:none}
    .c2-radio strong{color:#4fd1e0;font-size:12px;letter-spacing:.1em;display:block}
    .c2-radio p{font-size:16px;line-height:1.5;margin:6px 0 0}
    .c2-radio[data-urgent="true"]{border-left-color:#f05a28}
    @media(max-width:720px){.c2-radio{left:4%;top:60px;width:58%;max-width:58%;padding:8px 12px}
      .c2-radio p{font-size:14px}}
  `;
  document.head.append(style);
}

function campaignTalking() {
  return [...document.querySelectorAll('.story-radio')].some(function shown(node) {
    return !node.hidden;
  });
}

/**
 * cues: [{id, speaker, text, when:{deliverable,done}|{lamps:true}|{speed_gt}, urgent?}]
 * Returns {observe(state, snapshot), dispose()}.
 */
export function installChapter2Radio(cues = []) {
  if (!cues.length || typeof document === 'undefined') {
    return { observe() {}, dispose() {} };
  }
  ensureStyle();
  const root = element('section', 'c2-radio');
  root.hidden = true;
  const speaker = element('strong', '');
  const text = element('p', '');
  root.append(speaker, text);
  document.body.append(root);
  const fired = new Set();
  let until = 0;

  function show(cue) {
    speaker.textContent = cue.speaker || STRINGS.fallbackSpeaker;
    text.textContent = cue.text || '';
    root.dataset.urgent = String(!!cue.urgent);
    root.hidden = false;
    until = performance.now() + (cue.urgent ? 7000 : 5000);
  }

  function lampsOn(state) {
    return (Number(state?.rc?.right_switch) || 0) > 0;
  }

  function speedOf(state) {
    const vel = state?.vel;
    if (!Array.isArray(vel) || vel.length < 3) return 0;
    return Math.hypot(vel[0], vel[1], vel[2]);
  }

  function matches(cue, state, snapshot) {
    const when = cue.when || {};
    if (when.deliverable) {
      const item = (snapshot?.items || []).find(function find(entry) {
        return entry.id === when.deliverable;
      });
      if (!item) return false;
      if (Object.hasOwn(when, 'done')) return when.done ? !!item.done : !item.done;
      return !!item.done;
    }
    if (when.lamps) return lampsOn(state);
    if (when.speed_gt != null) return speedOf(state) > Number(when.speed_gt);
    return false;
  }

  function observe(state, snapshot) {
    if (campaignTalking()) {
      root.hidden = true;
      return;
    }
    if (performance.now() > until) root.hidden = true;
    for (const cue of cues) {
      const key = cue.id || `${cue.speaker}:${cue.text}`;
      if (fired.has(key)) continue;
      if (!matches(cue, state, snapshot)) continue;
      fired.add(key);
      show(cue);
      break;
    }
  }

  function dispose() {
    root.remove();
  }

  return { observe, dispose, root };
}
