// Settling a YX work order into the career save: pay (scoring.js), reputation with the client, the logbook line
// with real and assisted hours apart, contract progress, and what the dive newly opened on the board. Returns
// the summary the results screen shows, and the licence exam (a pass needs the whole dive at the real preset).
// Pure over the save and the data; the caller stores the save.
import {
  clientLabel, contractStatus, contractView, gradeFor, gradeIndex, hasLicence, itemView, licenceProgress,
} from './rules.js';
import { localizedEndorsement } from './localize_data.js';
import { logDive } from './save.js';
import { payout, reputationGain } from './scoring.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.settle', {
  examAssisted: '考核期間開啟了超出真機的設定（或未以考核模式下水）。',
  examIncomplete: '必要交付項目沒有全部完成。',
  examScore: '分數未達銅牌門檻。',
});
const MEDAL_RANK = { none: 0, bronze: 1, silver: 2, gold: 3 };

function openContracts(save, data, sceneKeys) {
  return new Set(data.contracts.filter(function open(contract) {
    return contractStatus(contract, save, data, sceneKeys).available;
  }).map(function id(contract) {
    return contract.id;
  }));
}

/** Whether an item can be bought by this save's licence (money aside); used to list newly opened items. */
export function itemOpen(item, save, data) {
  return hasLicence(save, data, item.licence || 'none');
}

function openItems(save, data) {
  return new Set(data.items.filter(function open(item) {
    return !save.owned.includes(item.id) && itemOpen(item, save, data);
  }).map(function id(item) {
    return item.id;
  }));
}

function updateRecord(save, contract, pay) {
  const record = save.contracts[contract.id] || { completed: 0, attempts: 0, best: 0, medal: 'none' };
  record.attempts += 1;
  if (pay.outcome === 'complete') record.completed += 1;
  if (pay.outcome !== 'aborted') {
    record.best = Math.max(record.best, pay.score);
    if (MEDAL_RANK[pay.medal] > MEDAL_RANK[record.medal]) record.medal = pay.medal;
  }
  save.contracts[contract.id] = record;
  return record;
}

function updateReputation(save, data, contract, pay) {
  const delta = reputationGain(contract, pay);
  const before = save.reputation[contract.client] || 0;
  const total = Math.max(0, before + delta);
  save.reputation[contract.client] = total;
  return { client: contract.client, label: clientLabel(data, contract.client),
    delta: total - before, total };
}

/**
 * dive: {snapshot (deliverables.js), submitted, id, startedAt, vehicle, block, real_s, assisted_s, duration_s,
 * examValid}. Returns {save, summary}; summary has pay, reputation, hours, licence progress, exam result and the
 * contracts and items this dive opened.
 */
export function settleDive(save, data, contract, dive, { sceneKeys = null, now = Date.now() } = {}) {
  const shown = contractView(contract);
  const contractsBefore = openContracts(save, data, sceneKeys);
  const itemsBefore = openItems(save, data);
  const licenceBefore = save.licence;
  const repeat = (save.contracts[contract.id]?.completed || 0) > 0;
  const pay = payout(contract, dive.snapshot, { repeat, submitted: !!dive.submitted });
  updateRecord(save, contract, pay);
  save.money += pay.net;
  const reputation = updateReputation(save, data, contract, pay);
  const exam = examResult(save, data, contract, pay, dive);
  const line = logDive(save, {
    id: dive.id,
    date: dive.startedAt || new Date(now).toISOString(),
    contract: contract.id,
    title: shown.title,
    site: contract.scenario,
    vehicle: dive.vehicle,
    block: dive.block,
    duration_s: dive.duration_s,
    real_s: dive.real_s,
    assisted_s: dive.assisted_s,
    outcome: pay.outcome,
    medal: pay.medal,
    score: pay.score,
    pay: pay.net,
    deliverables: dive.snapshot.items,
    exam: !!contract.exam,
    examPassed: exam.passed,
  });
  save.activeDive = null;
  const contractsAfter = openContracts(save, data, sceneKeys);
  const itemsAfter = openItems(save, data);
  const opened = data.contracts.filter(function fresh(entry) {
    return contractsAfter.has(entry.id) && !contractsBefore.has(entry.id);
  });
  const items = data.items.filter(function fresh(item) {
    return itemsAfter.has(item.id) && !itemsBefore.has(item.id);
  });
  return {
    save,
    summary: {
      contract: contract.id,
      pay,
      reputation,
      hours: { real_s: line.real_s, assisted_s: line.assisted_s, total_real_s: save.hours.real_s,
        total_assisted_s: save.hours.assisted_s },
      exam,
      licence: { before: licenceBefore, after: save.licence, label: gradeFor(data, save.licence).label,
        progress: licenceProgress(save, data) },
      unlocks: {
        contracts: opened.map(function title(entry) {
          const view = contractView(entry);
          return { id: entry.id, title: view.title };
        }),
        items: items.map(function label(item) {
          const view = itemView(item);
          return { id: item.id, label: view.label };
        }),
      },
      money: save.money,
      line,
    },
  };
}

/**
 * Licence exam of a contract: it passes only when the job is complete with at least a bronze medal and the whole
 * dive stayed at the real preset (dive.examValid); a pass grants the licence grade or endorsement. A failed exam
 * can always be taken again.
 */
export function examResult(save, data, contract, pay, dive) {
  if (!contract.exam) return { taken: false, passed: false, reason: '', granted: '' };
  let reason = '';
  if (!dive.examValid) reason = STRINGS.examAssisted;
  else if (pay.outcome !== 'complete') reason = STRINGS.examIncomplete;
  else if (pay.medal === 'none') reason = STRINGS.examScore;
  if (reason) return { taken: true, passed: false, reason, granted: '' };
  const granted = [];
  const grade = contract.exam.grants;
  if (grade) {
    if (gradeIndex(data, grade) > gradeIndex(data, save.licence)) save.licence = grade;
    granted.push(gradeFor(data, grade).label);
  }
  const endorsement = contract.exam.endorsement;
  if (endorsement) {
    if (!save.endorsements.includes(endorsement)) save.endorsements.push(endorsement);
    const entry = data.endorsements.find(function byId(row) {
      return row.id === endorsement;
    });
    granted.push(localizedEndorsement(entry)?.label || endorsement);
  }
  return { taken: true, passed: true, reason: '', granted: granted.join('、') };
}
