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
import {findLesson, normalizeCourse} from './catalogue.js';
import {installTrainingFidelityGuard} from './fidelity_guard.js';
import {isInternalEdition} from './edition.js';
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

// Steam builds must not enter training mode, even via ?training=1.
export function trainingLaunchParams(location = globalThis.location, host = globalThis) {
  if (!isInternalEdition(host)) {
    return {enabled: false, lessonId: ''};
  }
  const query = new URLSearchParams(location.search);
  const lessonId = query.get('trainingLesson') || '';
  const enabled = query.get('training') === '1' || !!lessonId
    || query.get('mission') === 'campaign' && String(query.get('chapter') || '').startsWith('course_');
  return {enabled, lessonId: lessonId || query.get('chapter') || ''};
}

function hydrateLessonFromCatalogue(session) {
  if (!session?.active || !globalThis.fetch) return Promise.resolve(session);
  return fetch('training/courses.json').then(function loadCourses(response) {
    return response.ok ? response.json() : null;
  }).then(function applyCatalogue(catalogue) {
    if (!catalogue || !session.active) return session;
    const lessonId = session.lesson?.id;
    const match = [...(catalogue.courses || []), ...(catalogue.incidents || [])]
      .find(function byId(entry) { return entry.id === lessonId; });
    const normalized = normalizeCourse(match);
    if (normalized) Object.assign(session.lesson, normalized);
    return session;
  }).catch(function ignore() {
    return session;
  });
}

export function installTrainingSession({
  catalogue = null,
  getState = () => null,
  student = '',
  location = globalThis.location,
  host = globalThis,
} = {}) {
  const launch = trainingLaunchParams(location, host);
  if (!launch.enabled) {
    return {active: false, update() {}, dispose() {}};
  }

  const lesson = findLesson(catalogue, launch.lessonId) || {id: launch.lessonId};
  const metricsRef = {current: createSessionMetrics({lessonId: lesson.id})};
  let finalized = null;
  let banner = null;

  const style = document.createElement('style');
  style.textContent = `
    #trainingBanner{position:fixed;left:12px;bottom:12px;z-index:var(--z-notice);
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
    hydrateLesson: function hydrateLesson() {
      return hydrateLessonFromCatalogue(api);
    },
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
  if (!catalogue) hydrateLessonFromCatalogue(api);
  return api;
}
