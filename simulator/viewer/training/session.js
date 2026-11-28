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
import {createPhotoMarker} from './photo_marker.js';
import {labels as editorLabels} from './editor_strings.js';
import {getLanguage, localize} from '../i18n/index.js';

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

// Campaign courses (tutorial_pool etc.) often have score.finished immediately; wait for
// campaign.status === 'completed' so the scorecard covers the whole lesson.
export function shouldFinalizeTraining(state) {
  if (!state) return false;
  const campaign = state.campaign;
  if (campaign && (campaign.chapter || campaign.status)) {
    return campaign.status === 'completed';
  }
  return !!(state.score?.finished || state.score?.failed);
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
  THREE = null,
  scene = null,
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
  let readout = null;
  const marker = createPhotoMarker(THREE, scene);

  const style = document.createElement('style');
  style.textContent = `
    #trainingBanner{position:fixed;left:12px;bottom:12px;z-index:var(--z-notice);
      background:rgba(8,18,26,.78);color:#e8f1f5;padding:8px 12px;font-size:12px;
      border-left:2px solid #dfbc61;max-width:min(420px,70vw)}
    #trainingObjective{position:fixed;top:18%;left:1rem;background:#102127;color:white;
      padding:.6rem;z-index:var(--z-notice);max-width:min(32rem,80vw);overflow-wrap:anywhere}
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
    const snapshot = state || getState();
    const active = snapshot?.campaign?.status === 'active' && snapshot.campaign.chapter === lesson.id;
    marker.update(active ? snapshot.campaign.instructor?.target : null);
    if (lesson.id.startsWith('custom_') && snapshot?.campaign?.chapter !== lesson.id) {
      readout?.remove();
      readout = null;
      return;
    }
    if (finalized && lesson.id.startsWith('custom_') && snapshot.campaign.status === 'active') {
      finalized = null;
      metricsRef.current = createSessionMetrics({lessonId:lesson.id});
    }
    observeState(metricsRef.current, snapshot);
    const custom = snapshot?.campaign?.instructor;
    if (custom && snapshot.campaign.chapter === lesson.id) {
      lesson.title = custom.title;
      metricsRef.current.elapsedS = snapshot.t;
      metricsRef.current.objectivesDone = custom.done;
      metricsRef.current.objectivesTotal = custom.total;
      if (!readout) {
        readout = element('div');
        readout.id = 'trainingObjective';
        banner.after(readout);
      }
      const lines = custom.lines || {};
      const local = lines[getLanguage()] || [];
      const target = custom.target;
      const text = (lines['zh-TW'] || []).map((line,i) => local[i] || line).filter(Boolean);
      if (target) text.unshift(editorLabels[target.kind] + ' · N/E/D ' + target.point.join(' / ') + ' m');
      if (snapshot.campaign.status === 'completed') {
        metricsRef.current.finished = true;
        metricsRef.current.score = custom.score;
        lesson.instructorPassed = custom.passed;
        text.push(editorLabels[custom.passed ? 'passLabel' : 'failLabel'] + ' · ' + custom.score + '%');
      }
      readout.textContent = text.join(' · ');
    }
    if (!finalized && shouldFinalizeTraining(snapshot)) {
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
      marker.dispose();
      guard.dispose();
      readout?.remove();
      banner?.remove();
      style.remove();
      if (globalThis.window?.__training === api) delete globalThis.window.__training;
    },
  };
  if (globalThis.window) globalThis.window.__training = api;
  if (!catalogue) hydrateLessonFromCatalogue(api);
  return api;
}
