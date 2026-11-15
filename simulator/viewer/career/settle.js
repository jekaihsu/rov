// Settling a YX work order into the career save: pay (scoring.js), reputation with the client, the logbook line
// with real and assisted hours apart, contract progress, and what the dive newly opened on the board. Returns
// the summary the results screen shows. Pure over the save and the data; the caller stores the save.
import { contractStatus, gradeFor, hasLicence, licenceProgress } from './rules.js';
import { logDive } from './save.js';
import { payout, reputationGain } from './scoring.js';

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
  return { client: contract.client, label: data.clients[contract.client]?.label || contract.client,
    delta: total - before, total };
}

/**
 * dive: {snapshot (deliverables.js), submitted, id, startedAt, vehicle, block, real_s, assisted_s, duration_s,
 * examValid}. Returns {save, summary}; summary has pay, reputation, hours, licence progress, exam result and the
 * contracts and items this dive opened.
 */
export function settleDive(save, data, contract, dive, { sceneKeys = null, now = Date.now() } = {}) {
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
    title: contract.title,
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
          return { id: entry.id, title: entry.title };
        }),
        items: items.map(function label(item) {
          return { id: item.id, label: item.label };
        }),
      },
      money: save.money,
      line,
    },
  };
}

/** Licence exams settle here once the exam rules are in (career exams step); until then none is taken. */
export function examResult(save, data, contract, pay, dive) {
  void save;
  void data;
  void pay;
  void dive;
  return { taken: false, passed: false, reason: '', granted: '' };
}
