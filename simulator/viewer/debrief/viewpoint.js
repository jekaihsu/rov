/* Debrief camera modes: student onboard (delayed/sensed) vs god-view truth overlay. */
import {STRINGS} from './strings.js';

export const VIEW_STUDENT = 'student';
export const VIEW_GOD = 'god';

function el(tag, className, parent, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  if (parent) parent.append(node);
  return node;
}

function wrapAngle(delta) {
  return ((delta + 180) % 360 + 360) % 360 - 180;
}

export function studentDisplayTime(clipTime, frame) {
  const lag = Number(frame?.link?.video_lag_s);
  const delay = Number.isFinite(lag) && lag > 0 ? lag : 0;
  return Math.max(0, clipTime - delay);
}

export function sensorErrorSummary(state) {
  if (!state?.sensors) return null;
  const sensedDepth = state.sensors.depth;
  const truthDepth = state.pos?.[2];
  const sensedHeading = state.sensors.heading;
  const truthHeading = state.euler?.[2];
  const truthCurrent = state.current_kn;
  return {
    depthError: Number.isFinite(sensedDepth) && Number.isFinite(truthDepth)
      ? sensedDepth - truthDepth : null,
    headingError: Number.isFinite(sensedHeading) && Number.isFinite(truthHeading)
      ? wrapAngle(sensedHeading - truthHeading) : null,
    truthDepth,
    sensedDepth,
    truthHeading,
    sensedHeading,
    truthCurrent,
    dvl: state.sensors.dvl?.status || null,
  };
}

export function installViewpoint({host, setCam, onChange}) {
  let mode = VIEW_STUDENT;
  const panel = el('div', 'debrief-viewpoint', host);
  el('span', 'debrief-viewpoint-label', panel, STRINGS.viewpoint);
  const student = el('button', 'debrief-view-btn on', panel, STRINGS.studentView);
  student.type = 'button';
  student.title = STRINGS.studentHint;
  const god = el('button', 'debrief-view-btn', panel, STRINGS.godView);
  god.type = 'button';
  god.title = STRINGS.godHint;

  // Banner / compare float on the viewport so the replay bar stays short for overlay geometry.
  const viewport = document.querySelector('.viewport') || document.body;
  const banner = el('div', 'debrief-banner', viewport, STRINGS.viewpointBanner);
  banner.hidden = true;
  const compare = el('div', 'debrief-compare', viewport);
  compare.hidden = true;

  function apply(next, {notify = true} = {}) {
    mode = next;
    student.classList.toggle('on', mode === VIEW_STUDENT);
    god.classList.toggle('on', mode === VIEW_GOD);
    banner.hidden = mode !== VIEW_GOD;
    document.body.dataset.debriefView = mode;
    if (mode === VIEW_STUDENT) setCam?.('onboard');
    else setCam?.('chase');
    if (notify) onChange?.(mode);
  }

  student.addEventListener('click', function chooseStudent() { apply(VIEW_STUDENT); });
  god.addEventListener('click', function chooseGod() { apply(VIEW_GOD); });

  function updateCompare(state) {
    const summary = mode === VIEW_GOD ? sensorErrorSummary(state) : null;
    if (!summary) {
      compare.hidden = true;
      compare.replaceChildren();
      return;
    }
    compare.hidden = false;
    compare.replaceChildren();
    el('strong', '', compare, STRINGS.sensorError);
    const depth = summary.depthError == null ? STRINGS.missing
      : `${summary.depthError >= 0 ? '+' : ''}${summary.depthError.toFixed(2)} m`;
    const heading = summary.headingError == null ? STRINGS.missing
      : `${summary.headingError >= 0 ? '+' : ''}${summary.headingError.toFixed(1)}°`;
    el('span', '', compare,
      `${STRINGS.truthDepth} ${summary.truthDepth?.toFixed?.(2) ?? STRINGS.missing} / `
      + `${STRINGS.sensedDepth} ${summary.sensedDepth?.toFixed?.(2) ?? STRINGS.missing} (${depth})`);
    el('span', '', compare,
      `${STRINGS.truthHeading} ${summary.truthHeading?.toFixed?.(1) ?? STRINGS.missing}° / `
      + `${STRINGS.sensedHeading} ${summary.sensedHeading?.toFixed?.(1) ?? STRINGS.missing}° (${heading})`);
    el('span', '', compare,
      `${STRINGS.truthCurrent} ${summary.truthCurrent?.toFixed?.(2) ?? STRINGS.missing} kn · DVL `
      + `${summary.dvl || STRINGS.missing}`);
  }

  apply(VIEW_STUDENT, {notify: false});
  return {
    get mode() { return mode; },
    setMode: apply,
    updateCompare,
    studentDisplayTime,
    root: panel,
  };
}
