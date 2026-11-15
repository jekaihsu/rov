// Career rules over the save (save.js) and the career data (data.js): which YX work orders are on the board and
// why one is locked, licence grades and progress, and the recommended next contract. Pure functions, no DOM, so
// node --test can load them. Licences only open job types; nothing here changes how a vehicle flies.
import { logDive, realHours } from './save.js';

const STRINGS = {
  needLicence: '需要「{licence}」執照',
  needContract: '先完成「{title}」',
  needEquipment: '需要裝備「{item}」（YX 裝備部）',
  needReputation: '需要{client}聲譽 {need}（目前 {have}）',
  needHours: '需要真實模式時數 {need} h（目前 {have} h）',
  unknownItem: '{id}',
};

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

/** Position of a grade id in the ladder (unknown ids count as no licence). */
export function gradeIndex(data, id) {
  return Math.max(0, data.grades.findIndex(function byId(grade) {
    return grade.id === id;
  }));
}

export function gradeFor(data, id) {
  return data.grades[gradeIndex(data, id)] || { id: 'none', label: id, short: id, realHours: 0 };
}

export function hasLicence(save, data, id) {
  return gradeIndex(data, save.licence) >= gradeIndex(data, id || 'none');
}

export function contractById(data, id) {
  return data.contracts.find(function byId(contract) {
    return contract.id === id;
  }) || null;
}

export function itemById(data, id) {
  return data.items.find(function byId(item) {
    return item.id === id;
  }) || null;
}

export function itemLabel(data, id) {
  return itemById(data, id)?.label || format(STRINGS.unknownItem, { id });
}

export function clientLabel(data, id) {
  return data.clients[id]?.label || id;
}

export function jobLabel(data, id) {
  return data.jobs[id] || id;
}

/** Real-mode hours a licence grade asks for before its exam. */
export function examHours(data, contract) {
  const grants = contract?.exam?.grants;
  return grants ? gradeFor(data, grants).realHours || 0 : 0;
}

function roundHours(hours) {
  return Math.floor(hours * 100) / 100;
}

/** A chapter is shown when it needs no special scene, or its scene exists on this build (sceneKeys). */
export function chapterVisible(chapter, sceneKeys) {
  return !chapter?.scenario || !sceneKeys || sceneKeys.has(chapter.scenario);
}

/**
 * Where a contract stands for this save: hidden when its scene is not on this build; locked with every reason
 * that keeps it closed; open; or done (completed at least once, and still repeatable for pay).
 */
export function contractStatus(contract, save, data, sceneKeys = null) {
  const chapter = data.chapters.find(function byId(entry) {
    return entry.id === contract.chapter;
  });
  const visible = (!sceneKeys || sceneKeys.has(contract.scenario)) && chapterVisible(chapter, sceneKeys);
  const reasons = [];
  if (!hasLicence(save, data, contract.licence)) {
    const licence = gradeFor(data, contract.licence).label;
    reasons.push({ kind: 'licence', text: format(STRINGS.needLicence, { licence }) });
  }
  for (const id of contract.requires || []) {
    if ((save.contracts[id]?.completed || 0) > 0) continue;
    const title = contractById(data, id)?.title || id;
    reasons.push({ kind: 'contract', text: format(STRINGS.needContract, { title }) });
  }
  for (const id of contract.equipment || []) {
    if (save.owned.includes(id)) continue;
    reasons.push({ kind: 'equipment', id, text: format(STRINGS.needEquipment, { item: itemLabel(data, id) }) });
  }
  const need = contract.minReputation || 0;
  const have = save.reputation[contract.client] || 0;
  if (have < need) {
    const client = clientLabel(data, contract.client);
    reasons.push({ kind: 'reputation', text: format(STRINGS.needReputation, { client, need, have }) });
  }
  const hours = examHours(data, contract);
  if (hours > 0 && realHours(save) < hours) {
    const held = roundHours(realHours(save));
    reasons.push({ kind: 'hours', text: format(STRINGS.needHours, { need: hours, have: held }) });
  }
  const completed = save.contracts[contract.id]?.completed || 0;
  let status = 'open';
  if (reasons.length) status = 'locked';
  else if (completed > 0) status = 'done';
  return { visible, available: visible && !reasons.length, status, reasons, repeat: completed > 0 };
}

/** The board: visible chapters in order, each with its visible contracts and their status. */
export function boardChapters(data, save, sceneKeys = null) {
  return data.chapters.filter(function shown(chapter) {
    return chapterVisible(chapter, sceneKeys);
  }).map(function withContracts(chapter) {
    const contracts = data.contracts.filter(function inChapter(contract) {
      return contract.chapter === chapter.id;
    }).map(function withStatus(contract) {
      return { contract, status: contractStatus(contract, save, data, sceneKeys) };
    }).filter(function visible(entry) {
      return entry.status.visible;
    });
    return { chapter, contracts };
  }).filter(function nonEmpty(entry) {
    return entry.contracts.length > 0;
  });
}

/** The next contract to offer under 繼續職涯: the first open main-line job, else the first open one. */
export function recommendedContract(data, save, sceneKeys = null) {
  const entries = boardChapters(data, save, sceneKeys).flatMap(function list(chapter) {
    return chapter.contracts;
  });
  const fresh = entries.find(function mainLine(entry) {
    return entry.status.status === 'open' && !entry.contract.optional;
  });
  const open = entries.find(function anyOpen(entry) {
    return entry.status.status === 'open';
  });
  const repeat = entries.find(function repeatable(entry) {
    return entry.status.available;
  });
  return (fresh || open || repeat)?.contract || null;
}

/** Licence ladder position: the grade held, the next one, its real-hour requirement and exam contract. */
export function licenceProgress(save, data) {
  const index = gradeIndex(data, save.licence);
  const current = data.grades[index] || data.grades[0];
  const next = data.grades[index + 1] || null;
  const hours = realHours(save);
  const required = next?.realHours || 0;
  const exam = next?.exam ? contractById(data, next.exam) : null;
  const hoursFraction = required > 0 ? Math.min(1, hours / required) : 1;
  return {
    current,
    next,
    realHours: hours,
    requiredHours: required,
    hoursFraction,
    exam,
    // Half the bar is hours, half is the exam (passing it grants the grade, so it is never half done here).
    fraction: next ? hoursFraction * (exam ? 0.5 : 1) : 1,
  };
}

/**
 * A dive that left no result (page closed, back to the menu without submitting) enters the logbook as aborted:
 * no pay, but its real and assisted hours count. Returns the logbook line, or null when nothing was open.
 */
export function closeAbandonedDive(save) {
  const active = save.activeDive;
  if (!active) return null;
  save.activeDive = null;
  const record = save.contracts[active.contract] || { completed: 0, attempts: 0, best: 0, medal: 'none' };
  record.attempts += 1;
  save.contracts[active.contract] = record;
  return logDive(save, {
    id: active.id,
    date: active.startedAt,
    contract: active.contract,
    title: active.title,
    site: active.site,
    vehicle: active.vehicle,
    block: active.block,
    duration_s: active.duration_s,
    real_s: active.real_s,
    assisted_s: active.assisted_s,
    outcome: 'aborted',
    deliverables: active.deliverables,
    exam: active.exam,
  });
}
