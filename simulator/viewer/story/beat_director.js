// Pure campaign beat decisions. A condition takes precedence when it coincides with the deadline.
export function conditionMatches(condition, telemetry) {
  if (!condition) return false;
  const actual = condition.path.split('.').reduce((value, part) => value?.[part], telemetry);
  if (actual == null) return false;
  if (condition.op === 'eq') return actual === condition.value;
  if (typeof actual !== 'number') return false;
  return condition.op === 'gt' ? actual > condition.value : condition.op === 'lt' && actual < condition.value;
}

export function beatDecision(beat, elapsed, telemetry) {
  if (!beat) return null;
  if (conditionMatches(beat.condition, telemetry)) return beat.next;
  return elapsed >= beat.limit ? beat.timeout || beat.next : null;
}

export function idleReminder(key, after, idleSeconds, alreadySaid) {
  return key && !alreadySaid && idleSeconds >= after ? key : null;
}
