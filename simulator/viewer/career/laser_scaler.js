// Presentation overlay for a real laser scale (two parallel spots at a fixed baseline). When the career save
// owns laser_scaler and a measure deliverable is nearby in onboard view, the overlay draws the spots, shows the
// thickness inferred from on-screen separation versus the 0.10 m baseline, and lets the pilot pick soft/hard
// growth. Dive wires setMeasureResult from reading(); this module never writes physics.

import { localize } from '../i18n/core.js';

const STRINGS = localize('career.laser_scaler', {
  title: '雷射比例尺',
  baseline: '基準距 {cm} cm',
  thickness: '厚度 {cm} cm',
  soft: '軟附著',
  hard: '硬附著',
  pick: '選附著類型',
  needOnboard: '請切回機載畫面量測',
});

export const LASER_BASELINE_M = 0.10;
const NEAR_M = 3;
const FEATURE_FRAC = 0.35;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function vector(value) {
  return Array.isArray(value) && value.length >= 3 ? value.map(Number) : null;
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

/** Thickness in cm from feature vs baseline pixel separation. */
export function thicknessCmFromSeparation(featurePx, baselinePx, baseline_m = LASER_BASELINE_M) {
  const base = Number(baselinePx);
  const feature = Number(featurePx);
  const meters = Number(baseline_m);
  if (!(base > 0) || !(feature >= 0) || !(meters > 0)) return null;
  return (feature / base) * meters * 100;
}

function activeMeasure(snapshot, state) {
  const pos = vector(state?.pos);
  if (!pos || !snapshot?.items) return null;
  let best = null;
  let bestGap = Infinity;
  for (const item of snapshot.items) {
    if (item.kind !== 'measure' || item.done || !item.point) continue;
    const gap = distance(pos, item.point);
    if (gap > NEAR_M || gap >= bestGap) continue;
    best = item;
    bestGap = gap;
  }
  return best;
}

/**
 * getState/getWorld/getCamMode: dive hooks; owned: career save item ids; onGrowthPick(kind, reading).
 * Returns {update, pickGrowth, reading, dispose}.
 */
export function installLaserScaler({ getState, getWorld, getCamMode, owned = [], onGrowthPick } = {}) {
  const root = element('div', 'laser-scaler');
  root.hidden = true;
  const dots = element('div', 'laser-scaler-dots');
  const left = element('span', 'laser-scaler-dot laser-scaler-dot-a');
  const right = element('span', 'laser-scaler-dot laser-scaler-dot-b');
  dots.append(left, right);
  const panel = element('div', 'laser-scaler-panel');
  const title = element('p', 'laser-scaler-title', STRINGS.title);
  const baselineLine = element('p', 'laser-scaler-baseline');
  const thicknessLine = element('p', 'laser-scaler-thickness');
  const pickLabel = element('p', 'laser-scaler-pick', STRINGS.pick);
  const actions = element('div', 'laser-scaler-actions');
  const softBtn = element('button', 'laser-scaler-soft', STRINGS.soft);
  softBtn.type = 'button';
  const hardBtn = element('button', 'laser-scaler-hard', STRINGS.hard);
  hardBtn.type = 'button';
  actions.append(softBtn, hardBtn);
  panel.append(title, baselineLine, thicknessLine, pickLabel, actions);
  root.append(dots, panel);
  document.body.append(root);

  let growth = '';
  let thickness_cm = null;
  let targetId = '';
  let featurePx = 0;
  let baselinePx = 0;

  function hasScaler() {
    return Array.isArray(owned) && owned.includes('laser_scaler');
  }

  function applyReading(cm) {
    thickness_cm = cm;
    const shown = cm == null ? '—' : cm.toFixed(1);
    thicknessLine.textContent = format(STRINGS.thickness, { cm: shown });
    baselineLine.textContent = format(STRINGS.baseline, {
      cm: (LASER_BASELINE_M * 100).toFixed(0),
    });
  }

  function pickGrowth(kind) {
    if (kind !== 'soft' && kind !== 'hard') return null;
    growth = kind;
    softBtn.dataset.on = kind === 'soft' ? 'true' : 'false';
    hardBtn.dataset.on = kind === 'hard' ? 'true' : 'false';
    const current = reading();
    onGrowthPick?.(kind, current);
    return current;
  }

  softBtn.addEventListener('click', function onSoft() {
    pickGrowth('soft');
  });
  hardBtn.addEventListener('click', function onHard() {
    pickGrowth('hard');
  });

  function reading() {
    if (thickness_cm == null || !targetId) return null;
    return { thickness_cm, growth: growth || '', baseline_m: LASER_BASELINE_M, id: targetId };
  }

  function layoutDots(gapM) {
    const width = Math.max(160, root.clientWidth || window.innerWidth || 800);
    const scale = Math.max(0.15, Math.min(0.9, 1.2 / Math.max(0.4, gapM)));
    baselinePx = Math.max(24, width * 0.08 * scale);
    const truth = Number(getWorld?.()?.careerTruthCm);
    const truthCm = Number.isFinite(truth) ? truth : null;
    if (truthCm != null) {
      featurePx = (truthCm / 100) / LASER_BASELINE_M * baselinePx;
    } else {
      featurePx = baselinePx * FEATURE_FRAC;
    }
    const mid = width * 0.5;
    left.style.left = `${mid - baselinePx / 2}px`;
    right.style.left = `${mid + baselinePx / 2}px`;
    applyReading(thicknessCmFromSeparation(featurePx, baselinePx));
  }

  function update(state, snapshot) {
    const live = state || getState?.();
    const cam = getCamMode?.() || 'onboard';
    const item = hasScaler() ? activeMeasure(snapshot, live) : null;
    if (!item || cam !== 'onboard') {
      root.hidden = true;
      if (!item) {
        targetId = '';
        thickness_cm = null;
      }
      return;
    }
    targetId = item.id;
    root.hidden = false;
    const pos = vector(live.pos);
    const gap = pos && item.point ? distance(pos, item.point) : 1;
    const truthField = item.truth_cm ?? item.readingTruthCm;
    if (Number.isFinite(Number(truthField))) {
      const cm = Number(truthField);
      const width = Math.max(160, root.clientWidth || window.innerWidth || 800);
      const scale = Math.max(0.15, Math.min(0.9, 1.2 / Math.max(0.4, gap)));
      baselinePx = Math.max(24, width * 0.08 * scale);
      featurePx = (cm / 100) / LASER_BASELINE_M * baselinePx;
      left.style.left = `${width * 0.5 - baselinePx / 2}px`;
      right.style.left = `${width * 0.5 + baselinePx / 2}px`;
      applyReading(cm);
      return;
    }
    layoutDots(gap);
  }

  function dispose() {
    softBtn.replaceWith(softBtn.cloneNode(true));
    hardBtn.replaceWith(hardBtn.cloneNode(true));
    root.remove();
  }

  return { update, pickGrowth, reading, dispose };
}
