// LOTO unlock gate for hull work orders: until confirm deliverables tagged gate:"unlock" (or every confirm when
// contract.lotoBeforeUnlock is true) are done, blocksUnlock(snapshot) is true so the dive UI can refuse to unlock
// the vehicle. Confirm actions themselves stay allowed; this module is pure checklist logic.

const STRINGS = {
  pending: '待確認：{label}',
};

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

/** Ids of confirm deliverables that must finish before unlock. */
export function lotoConfirmIds(contract) {
  const list = [];
  const force = !!contract?.lotoBeforeUnlock;
  for (const def of contract?.deliverables || []) {
    if (def.kind !== 'confirm') continue;
    if (def.gate === 'unlock' || (force && (def.gate == null || def.gate === 'unlock'))) {
      list.push(def.id);
    }
  }
  return list;
}

/**
 * contract: a contracts.json entry.
 * Returns {blocksUnlock, pendingLabels, confirmAllowed}.
 */
export function createLotoGate(contract) {
  const ids = lotoConfirmIds(contract);
  const labels = new Map();
  for (const def of contract?.deliverables || []) {
    if (ids.includes(def.id)) labels.set(def.id, def.label || def.id);
  }

  function itemMap(snapshot) {
    const map = new Map();
    for (const item of snapshot?.items || []) map.set(item.id, item);
    return map;
  }

  function blocksUnlock(snapshot) {
    if (!ids.length) return false;
    const byId = itemMap(snapshot);
    return ids.some(function unfinished(id) {
      return !byId.get(id)?.done;
    });
  }

  function pendingLabels(snapshot) {
    const byId = itemMap(snapshot);
    return ids.filter(function unfinished(id) {
      return !byId.get(id)?.done;
    }).map(function label(id) {
      return format(STRINGS.pending, { label: labels.get(id) || id });
    });
  }

  return { blocksUnlock, pendingLabels, confirmAllowed: true };
}
