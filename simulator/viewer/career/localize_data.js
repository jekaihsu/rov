// Resolve career data display text through career.copy keys. Keeps JSON ids and wire fields unchanged;
// falls back to the Traditional Chinese value on the data object when a key is missing.
import { COPY } from './copy.js';

function pick(bucket, id, field, fallback) {
  const value = COPY[bucket]?.[id]?.[field];
  return typeof value === 'string' && value ? value : fallback;
}

export function localizedClientLabel(data, id) {
  return pick('clients', id, 'label', data.clients?.[id]?.label || id);
}

export function localizedJobLabel(data, id) {
  const value = COPY.jobs?.[id];
  return typeof value === 'string' && value ? value : (data.jobs?.[id] || id);
}

export function localizedGrade(grade) {
  if (!grade) return grade;
  const id = grade.id;
  return {
    ...grade,
    label: pick('grades', id, 'label', grade.label),
    short: pick('grades', id, 'short', grade.short),
    opens: pick('grades', id, 'opens', grade.opens),
  };
}

export function localizedItem(item) {
  if (!item) return item;
  const id = item.id;
  return {
    ...item,
    label: pick('items', id, 'label', item.label),
    use: pick('items', id, 'use', item.use),
    unlocks: pick('items', id, 'unlocks', item.unlocks),
  };
}

export function localizedChapter(chapter) {
  if (!chapter) return chapter;
  const id = chapter.id;
  return {
    ...chapter,
    title: pick('chapters', id, 'title', chapter.title),
    summary: pick('chapters', id, 'summary', chapter.summary),
  };
}

export function localizedEndorsement(entry) {
  if (!entry) return entry;
  return {
    ...entry,
    label: pick('endorsements', entry.id, 'label', entry.label),
  };
}

/** Contract view with translated title/brief/radio/deliverable labels; ids unchanged. */
export function localizedContract(contract) {
  if (!contract) return contract;
  const id = contract.id;
  const src = COPY.contracts?.[id];
  let radio = contract.radio;
  if (contract.radio) {
    const radioCopy = src?.radio || {};
    radio = {
      ...contract.radio,
      speaker: radioCopy.speaker || contract.radio.speaker,
      start: radioCopy.start || contract.radio.start,
      done: radioCopy.done || contract.radio.done,
    };
    if (contract.radio.partial != null) {
      radio.partial = radioCopy.partial || contract.radio.partial;
    }
  }
  const deliverables = (contract.deliverables || []).map(function mapDeliverable(entry) {
    const label = src?.deliverables?.[entry.id] || entry.label;
    return { ...entry, label };
  });
  return {
    ...contract,
    title: pick('contracts', id, 'title', contract.title),
    clientName: pick('contracts', id, 'clientName', contract.clientName),
    summary: pick('contracts', id, 'summary', contract.summary),
    brief: pick('contracts', id, 'brief', contract.brief),
    radio,
    deliverables,
  };
}
