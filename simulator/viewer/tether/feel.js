// Presentation helpers for tether load. Host `tether.warn` (rated working load) is authoritative.
export function lineLoad(tether) {
  return Math.max(tether?.tension_rov || 0, tether?.tension_spool || 0);
}

export function linePull(tether, _alreadyHigh = false) {
  return !!tether && !tether.broken && !!tether.warn;
}
