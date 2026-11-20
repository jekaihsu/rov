// Presentation threshold from the cold open. The host's independent working-load warning always takes priority.
export function lineLoad(tether) {
  return Math.max(tether?.tension_rov || 0, tether?.tension_spool || 0);
}

export function linePull(tether, alreadyHigh = false) {
  return !!tether && !tether.broken && (tether.warn || lineLoad(tether) > (alreadyHigh ? 25 : 40));
}
