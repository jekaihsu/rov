// Tether load helpers for presentation. Host `tether.warn` (rated working load) always wins.
// PRESENTATION_PULL_N / RELEASE_N are narrative early-call thresholds shared with cold_open_model
// TIMING.pullTension / near stoppedTension — not X1 measurements (assumption; see game-feel-r7 README).
export const PRESENTATION_PULL_N = 40;
export const PRESENTATION_RELEASE_N = 25;

export function lineLoad(tether) {
  return Math.max(tether?.tension_rov || 0, tether?.tension_spool || 0);
}

export function linePull(tether, alreadyHigh = false) {
  if (!tether || tether.broken) return false;
  if (tether.warn) return true;
  return lineLoad(tether) > (alreadyHigh ? PRESENTATION_RELEASE_N : PRESENTATION_PULL_N);
}
