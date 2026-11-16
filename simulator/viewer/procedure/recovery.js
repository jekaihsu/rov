// When recovery can be called during a dive, and when to remind the pilot of it. Pure functions with no DOM, so
// the node tests can load them. The server owns the gate (qysim/procedure.py: surfaced to 0.8 m and locked);
// these only mirror it so the pause-menu entry can say why it is not available yet.

// Depth (m) the server accepts for recovery, and the depth that counts as having been on a dive.
export const RECOVERY_DEPTH = 0.8;
export const DIVE_DEPTH = 2;

/** 'ready', 'depth' (too deep) or 'lock' (unlocked); null when the procedure is not in its dive phase. */
export function recoveryReadiness(state) {
  if (!state?.procedure?.active || state.procedure.phase !== 'diving') return null;
  const depth = Number(state.pos?.[2]);
  if (!(depth <= RECOVERY_DEPTH)) return 'depth';
  if (!state.locked) return 'lock';
  return 'ready';
}

/**
 * Follows one dive and reports when a surfacing reminder is due: once the vehicle has been below DIVE_DEPTH and
 * comes back within RECOVERY_DEPTH, and again after each later descent. update(state) returns 'surfaced' on the
 * frame the reminder becomes due, otherwise null.
 */
export function createSurfaceWatch() {
  let dived = false;
  function update(state) {
    const p = state?.procedure;
    if (!p?.active || p.phase !== 'diving') {
      dived = false;
      return null;
    }
    const depth = Number(state.pos?.[2]);
    if (depth > DIVE_DEPTH) dived = true;
    if (dived && depth <= RECOVERY_DEPTH) {
      dived = false;
      return 'surfaced';
    }
    return null;
  }
  return {update};
}
