// Flight-side training session: observe telemetry, finalize a local scorecard,
// and expose export hooks on window.__training for browser smoke tests.

import {
  createSessionMetrics,
  observeState,
  recordInjection,
} from './metrics.js';
import {finalizeSession} from './records.js';
import {downloadScorecardPdf, downloadTrainingCsv, printScorecard} from './export.js';
import {listRecords} from './records.js';
import {findLesson} from './catalogue.js';
import {installTrainingFidelityGuard} from './fidelity_guard.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('training.session', {
  exportCsv: '匯出 CSV',
  exportPdf: '匯出成績單',
  printPdf: '列印成績單',
  saved: '本航次已寫入本機學員紀錄',
});

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

export function trainingLaunchParams(location = globalThis.location) {
  const query = new URLSearchParams(location.search);
  const lessonId = query.get('trainingLesson') || '';
  const enabled = query.get('training') === '1' || !!lessonId
    || query.get('mission') === 'campaign' && String(query.get('chapter') || '').startsWith('course_');
  return {enabled, lessonId: lessonId || query.get('chapter') || ''};
}

export function installTrainingSession({
  catalogue = null,
  getState = () => null,
  student = '',
} = {}) {
  const launch = trainingLaunchParams();
  if (!launch.enabled) {
    return {active: false, update() {}, dispose() {}};
  }

  const lesson = findLesson(catalogue, launch.lessonId) || {id: launch.lessonId};
  const metricsRef = {current: createSessionMetrics({lessonId: lesson.id})};
  let finalized = null;
  let banner = null;

  const style = document.createElement('style');
  style.textContent = `
    #trainingBanner{position:fixed;left:12px;bottom:12px;z-index:var(--z-notice,40);
      background:rgba(8,18,26,.78);color:#e8f1f5;padding:8px 12px;font-size:12px;
      border-left:2px solid #dfbc61;max-width:min(420px,70vw)}
    #trainingBanner.assist{border-left-color:#e07a5f}
    #trainingBanner button{margin-left:8px;font-size:11px}
  `;
  document.head.append(style);
  banner = element('div', '', '');
  banner.id = 'trainingBanner';
  document.body.append(banner);

  const guard = installTrainingFidelityGuard({
    metricsRef,
    onBanner(text, left) {
      banner.textContent = text;
      banner.classList.toggle('assist', !!left);
      if (!banner.querySelector('button')) {
        const csv = element('button', '', STRINGS.exportCsv);
        csv.type = 'button';
        csv.onclick = function exportCsv() {
          downloadTrainingCsv(listRecords());
        };
        const pdf = element('button', '', STRINGS.exportPdf);
        pdf.type = 'button';
        pdf.onclick = function exportPdf() {
          const card = finalized || finalizeNow();
          downloadScorecardPdf(card);
        };
        const print = element('button', '', STRINGS.printPdf);
        print.type = 'button';
        print.onclick = function printCard() {
          const card = finalized || finalizeNow();
          printScorecard(card);
        };
        banner.append(csv, pdf, print);
      }
    },
  });

  function finalizeNow() {
    if (finalized) return finalized;
    finalized = finalizeSession({
      metrics: metricsRef.current,
      lesson,
      student,
    });
    banner.title = STRINGS.saved;
    return finalized;
  }

  function update(state) {
    observeState(metricsRef.current, state || getState());
    if (!finalized && (state?.score?.finished || state?.score?.failed
      || state?.campaign?.status === 'completed')) {
      finalizeNow();
    }
  }

  const api = {
    active: true,
    lesson,
    metricsRef,
    update,
    finalize: finalizeNow,
    recordInjection(injection) {
      recordInjection(metricsRef.current, injection);
    },
    exportCsv() {
      downloadTrainingCsv(listRecords());
    },
    exportPdf() {
      downloadScorecardPdf(finalizeNow());
    },
    listRecords,
    get scorecard() {
      return finalized;
    },
    dispose() {
      guard.dispose();
      banner?.remove();
      style.remove();
      if (globalThis.window?.__training === api) delete globalThis.window.__training;
    },
  };
  if (globalThis.window) globalThis.window.__training = api;
  return api;
}
