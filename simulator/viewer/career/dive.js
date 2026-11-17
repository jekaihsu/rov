// Career runtime of a contract dive (the game page with ?contract=<id>): tracks the work order's deliverables
// (deliverables.js) from the state stream and photo events, counts real and assisted pilot time apart, keeps the
// dive open in the save (so a closed page still logs its hours), shows the checklist on the in-flight objective
// card and the pause menu, and settles the dive into the career when the job is done, handed in early or, for a
// story-chapter contract, when the chapter ends. The results screen then shows the career outcome. An exam
// (?exam=1) checks the whole time that nothing beyond the real vehicle is on; if something is, the exam is void.
import { getFidelity } from '../fidelity.js';
import { blockFor } from '../fleet_names.js';
import { formatTime } from '../play/results_model.js';
import { loadCareerData } from './data.js';
import { createTracker } from './deliverables.js';
import { PHOTO_VERDICT_ITEM } from './fidelity_item.js';
import { contractById, itemLabel } from './rules.js';
import { loadCareer, storeCareer } from './save.js';
import { partialAccepted, payout, DELIVERABLE_KIND_LABELS } from './scoring.js';
import { settleDive } from './settle.js';

const STRINGS = {
  card: 'YX 工單',
  meters: '{d} m',
  submit: '提前交件',
  submitPartial: '再按一次：部分交件（約 {pay} 元）',
  submitAbort: '再按一次：中止作業（不支付報酬）',
  confirm: '確認：{label}',
  penalties: '扣分項目 {n}',
  examOn: '執照考核中 · 真實模式',
  examVoid: '考核期間開啟了超出真機的設定，本次不計入執照。',
  photoSaved: '照片已存檔，交件後由客戶審閱。',
  outcome: { complete: '委託完成', partial: '部分交件', aborted: '中止作業' },
  aborted: '未達部分交件門檻，這次沒有報酬；時數已記入日誌。',
  broken: '纜線斷裂，載具回收失敗。',
  partial: '已交出部分成果，按比例支付。',
  examPassed: '考核通過：{label}',
  examFailed: '考核未通過：{reason}',
  rows: { deliverables: '交付項目', time: '作業時間' },
};
const PERSIST_MS = 5000;
const MAX_STEP_S = 1;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function uniqueId() {
  return globalThis.crypto?.randomUUID?.() || `dive-${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

/** True while nothing beyond the real vehicle is on: every fidelity item at real, no server flight assist. */
export function realNow(fidelity, state) {
  const beyond = fidelity.items().some(function exceeds(item) {
    return item.exceedsReal && fidelity.exceeds(item.id);
  });
  return !beyond && !(Number(state?.assist?.level) > 0) && !state?.remote_control;
}

function noop() {
  return null;
}

const INERT = {
  active: false,
  update: noop,
  photo: noop,
  panel: noop,
  pauseActions() {
    return [];
  },
  decorate(outcome) {
    return outcome;
  },
  retry: noop,
};

/**
 * send: socket sender; getWorld(): the world message; getCamMode(): current view; showResult(outcome): open the
 * results screen. Returns {update(state), photo(), panel(state), pauseActions(), decorate(outcome), retry()}.
 */
export function installCareerDive({ send, getWorld, getCamMode, showResult, readOnly = false,
  search = globalThis.location?.search || '' }) {
  const params = new URLSearchParams(search);
  const contractId = params.get('contract');
  if (!contractId || readOnly) return INERT;
  const fidelity = getFidelity();
  const examLaunch = params.get('exam') === '1';
  let data = null;
  let contract = null;
  let save = null;
  let tracker = null;
  let dive = null;
  let settled = false;
  let lastT = null;
  let lastPersist = 0;
  let examVoid = false;
  let confirmSubmit = false;
  let feedback = '';
  let lastState = null;
  const node = element('div', 'career-checklist');
  const radio = element('p', 'career-radio');
  const subhead = element('p', 'objective-subhead');
  const list = element('ol', 'objective-steps career-steps');
  const status = element('p', 'career-status');
  const actions = element('div', 'career-card-actions');
  const note = element('p', 'objective-feedback');
  note.setAttribute('role', 'status');
  node.append(radio, subhead, list, status, actions, note);

  loadCareerData().then(function ready(loaded) {
    data = loaded;
    save = loadCareer();
    contract = contractById(data, contractId);
    if (contract) start();
  }).catch(function noCareer(error) {
    console.error(error);
  });

  function exam() {
    return !!contract?.exam && examLaunch;
  }
  function start() {
    tracker = createTracker(contract, {
      owned: save.owned,
      itemLabel(id) {
        return itemLabel(data, id);
      },
    });
    settled = false;
    lastT = null;
    examVoid = false;
    confirmSubmit = false;
    feedback = '';
    dive = null;
    radio.replaceChildren(element('strong', '', contract.radio?.speaker || ''), contract.radio?.start || '');
    radio.hidden = !contract.radio?.start;
  }
  function openDive(state) {
    const model = state.model_id || 'x1';
    dive = {
      id: uniqueId(),
      contract: contract.id,
      title: contract.title,
      site: contract.scenario,
      startedAt: new Date().toISOString(),
      vehicle: model,
      block: blockFor(model, save),
      exam: exam(),
      real_s: 0,
      assisted_s: 0,
      duration_s: 0,
      deliverables: [],
    };
    save.activeDive = { ...dive };
    storeCareer(save, { mirror: false });
  }
  function inScene(state) {
    const world = getWorld();
    if (world?.scenario?.key !== (contract.launchScenario || contract.scenario)) return false;
    if (contract.runtime !== 'chapter') return true;
    return state.campaign?.chapter === contract.campaignChapter && state.campaign?.status === 'active';
  }
  function countTime(state) {
    const t = Number(state.t) || 0;
    if (lastT === null || t < lastT - 0.5) {
      lastT = t;
      return 0;
    }
    const dt = state.paused ? 0 : Math.min(MAX_STEP_S, Math.max(0, t - lastT));
    lastT = t;
    if (!dt) return 0;
    dive.duration_s += dt;
    if (realNow(fidelity, state)) dive.real_s += dt;
    else {
      dive.assisted_s += dt;
      if (exam()) examVoid = true;
    }
    return dt;
  }
  function persist(force = false) {
    const now = performance.now();
    if (!force && now - lastPersist < PERSIST_MS) return;
    lastPersist = now;
    save.activeDive = { ...dive, deliverables: tracker.snapshot().items };
    storeCareer(save, { mirror: false });
  }
  function update(state) {
    lastState = state;
    if (!contract || settled || !state || !inScene(state)) return;
    if (!dive) openDive(state);
    const dt = countTime(state);
    tracker.observe(state, dt);
    persist();
    if (contract.runtime === 'chapter') return;
    const snapshot = tracker.snapshot();
    if (snapshot.tetherBroken) settle(true);
    else if (snapshot.complete) settle(false);
  }
  function visibility(state) {
    const measured = Number(state?.turbidity?.visibility_m);
    return Number.isFinite(measured) ? measured : Number(getWorld()?.scenario?.visibility_m) || 12;
  }
  function photo() {
    if (!tracker || settled || !lastState || !dive) return null;
    const result = tracker.photo(lastState, { view: getCamMode(), visibility: visibility(lastState) });
    const verdict = fidelity.get(PHOTO_VERDICT_ITEM) === true;
    feedback = verdict ? result.message : STRINGS.photoSaved;
    return result;
  }
  function settle(submitted, chapterOutcome = null) {
    if (settled || !dive) return null;
    settled = true;
    const snapshot = tracker.snapshot();
    if (chapterOutcome) Object.assign(snapshot, chapterSnapshot(chapterOutcome));
    const catalogue = getWorld()?.catalogue || [];
    const sceneKeys = catalogue.length ? new Set(catalogue.map(function key(entry) {
      return entry.key;
    })) : null;
    const result = settleDive(save, data, contract, {
      ...dive, snapshot, submitted, examValid: exam() && !examVoid, state: lastState,
    }, { sceneKeys });
    save = result.save;
    storeCareer(save);
    const outcome = careerOutcome(result.summary, snapshot, chapterOutcome);
    if (!chapterOutcome) showResult?.(outcome);
    return outcome;
  }
  function chapterSnapshot(outcome) {
    const lost = Math.max(0, 100 - (Number(outcome.score) || 0));
    return {
      items: [{ id: 'chapter', kind: 'state', label: outcome.title, required: true, done: true, reading: '' }],
      done: 1, total: 1, requiredDone: 1, requiredTotal: 1, complete: !!outcome.success,
      penalties: lost ? [{ kind: 'contact', label: STRINGS.rows.deliverables, points: lost }] : [],
      tetherBroken: false,
    };
  }
  function reasonFor(summary) {
    const pay = summary.pay;
    const parts = [];
    if (pay.outcome === 'aborted') parts.push(tracker.snapshot().tetherBroken ? STRINGS.broken : STRINGS.aborted);
    if (pay.outcome === 'partial') parts.push(STRINGS.partial);
    if (summary.exam.taken && summary.exam.passed) {
      parts.push(STRINGS.examPassed.replace('{label}', summary.exam.granted));
    } else if (summary.exam.taken && summary.exam.reason) {
      parts.push(STRINGS.examFailed.replace('{reason}', summary.exam.reason));
    }
    return parts.join(' ');
  }
  function careerOutcome(summary, snapshot, chapterOutcome) {
    const pay = summary.pay;
    const rows = [{ id: 'deliverables', label: STRINGS.rows.deliverables, detail: `${snapshot.done}/${snapshot.total}`,
      points: Math.round(100 * snapshot.done / Math.max(1, snapshot.total)) }];
    for (const penalty of snapshot.penalties) {
      rows.push({ id: penalty.kind, label: penalty.label, detail: '', points: -penalty.points });
    }
    rows.push({ id: 'time', label: STRINGS.rows.time, detail: formatTime(dive.duration_s), points: null });
    return {
      ...(chapterOutcome || {}),
      kind: 'career',
      id: contract.id,
      recordKey: `career:${contract.id}`,
      title: contract.title,
      heading: STRINGS.outcome[pay.outcome],
      success: pay.outcome !== 'aborted',
      reason: reasonFor(summary),
      score: pay.score,
      medal: pay.medal,
      elapsed: dive.duration_s,
      limit: null,
      rows: chapterOutcome?.rows || rows,
      contacts: snapshot.penalties.filter(function contact(entry) {
        return entry.kind === 'contact';
      }).length,
      rewards: chapterOutcome?.rewards || [],
      next: null,
      chapter: contract.runtime === 'chapter' ? contract.campaignChapter : null,
      career: summary,
    };
  }
  function submit() {
    if (!tracker || settled || !dive) return;
    if (!confirmSubmit) {
      confirmSubmit = true;
      return;
    }
    settle(true);
  }
  function confirmItem(id) {
    tracker?.confirm(id);
  }
  function distanceText(item, state) {
    const pos = state?.pos;
    if (!item.point || item.done || !Array.isArray(pos)) return '';
    const gap = Math.hypot(pos[0] - item.point[0], pos[1] - item.point[1], pos[2] - item.point[2]);
    return STRINGS.meters.replace('{d}', gap.toFixed(1));
  }
  function submitLabel(snapshot) {
    if (!confirmSubmit) return STRINGS.submit;
    if (!partialAccepted(contract, snapshot)) return STRINGS.submitAbort;
    const estimate = payout(contract, snapshot, { submitted: true,
      repeat: (save.contracts[contract.id]?.completed || 0) > 0 });
    return STRINGS.submitPartial.replace('{pay}', estimate.net.toLocaleString('en-US'));
  }
  function renderItems(snapshot, state) {
    list.replaceChildren(...snapshot.items.map(function line(item) {
      const row = element('li', '', `${DELIVERABLE_KIND_LABELS[item.kind] || ''} · ${item.label}`);
      row.dataset.complete = String(item.done);
      row.dataset.item = item.id;
      if (!item.required) row.dataset.optional = 'true';
      const detail = item.reading || item.note || distanceText(item, state);
      if (detail) row.append(element('small', '', detail));
      if (!item.done && item.progress > 0) {
        const bar = element('progress');
        bar.max = 1;
        bar.value = item.progress;
        row.append(bar);
      }
      return row;
    }));
  }
  function renderActions(snapshot) {
    const buttons = snapshot.items.filter(function confirmable(item) {
      return item.confirmable;
    }).map(function confirmButton(item) {
      const button = element('button', 'objective-accept', STRINGS.confirm.replace('{label}', item.label));
      button.type = 'button';
      button.dataset.confirm = item.id;
      button.addEventListener('click', function confirmClick() {
        confirmItem(item.id);
      });
      return button;
    });
    if (contract.runtime !== 'chapter') {
      const button = element('button', 'objective-link', submitLabel(snapshot));
      button.type = 'button';
      button.id = 'careerSubmit';
      button.addEventListener('click', submit);
      buttons.push(button);
    }
    actions.replaceChildren(...buttons);
  }
  // Objective card section: {title, count, node} while a contract dive runs, else null.
  function panel(state) {
    if (!contract || !tracker || settled || !contract.deliverables.length) return null;
    const snapshot = tracker.snapshot();
    subhead.textContent = contract.title;
    renderItems(snapshot, state);
    const lines = [];
    if (snapshot.penalties.length) lines.push(STRINGS.penalties.replace('{n}', String(snapshot.penalties.length)));
    if (exam()) lines.push(examVoid ? STRINGS.examVoid : STRINGS.examOn);
    status.textContent = lines.join(' · ');
    status.dataset.warn = String(examVoid);
    renderActions(snapshot);
    note.textContent = feedback;
    return { title: STRINGS.card, count: `${snapshot.done}/${snapshot.total}`, node };
  }
  // Pause-menu buttons (gamepad reachable): confirmations and the early hand-in.
  function pauseActions() {
    if (!contract || !tracker || settled || !dive) return [];
    const snapshot = tracker.snapshot();
    const list = snapshot.items.filter(function confirmable(item) {
      return item.confirmable;
    }).map(function confirmAction(item) {
      return { id: `confirm-${item.id}`, label: STRINGS.confirm.replace('{label}', item.label), run() {
        confirmItem(item.id);
      } };
    });
    if (contract.runtime !== 'chapter') {
      list.push({ id: 'careerSubmit', label: submitLabel(snapshot), keepOpen: !confirmSubmit, run: submit });
    }
    return list;
  }
  // Story-chapter contracts end with the chapter's own results; settle them into the career on the way.
  function decorate(outcome) {
    if (!contract || contract.runtime !== 'chapter' || settled) return outcome;
    if (outcome?.kind !== 'chapter' || outcome.id !== contract.campaignChapter) return outcome;
    return settle(false, outcome) || outcome;
  }
  function retry() {
    if (!contract) return;
    if (contract.runtime === 'chapter') {
      send({ type: 'operation', action: 'campaign_start', chapter: contract.campaignChapter });
    } else {
      send({ type: 'reset' });
    }
    save = loadCareer();
    start();
  }
  const api = {
    get active() {
      return !!contract;
    },
    get contract() {
      return contract;
    },
    update,
    photo,
    panel,
    pauseActions,
    decorate,
    retry,
    // Browser checks drive the tracker with scripted states (tools/browser_career_smoke.py).
    observe(state) {
      update(state);
    },
    photoAt(state) {
      lastState = state;
      return photo();
    },
    get exam() {
      return exam();
    },
    get real() {
      return realNow(fidelity, lastState);
    },
    snapshot() {
      return tracker?.snapshot() || null;
    },
    submit,
    get settled() {
      return settled;
    },
  };
  window.__career = api;
  return api;
}
