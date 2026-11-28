// Session-local timing and field records. Only successfully stored photos count towards the dive log.
export function divePhase(elapsedMs) {
  return {opening: elapsedMs < 4000, progress: Math.min(1, elapsedMs / 4000), radioDue: elapsedMs >= 60000};
}

export function diveLog(site) {
  const known = new Set();
  const fresh = new Set();
  function restore(photos) {
    for (const photo of photos) {
      if (photo.metadata?.scene === site && photo.observation) known.add(photo.observation.category);
    }
  }
  function record(category) {
    if (!known.has(category)) fresh.add(category);
    known.add(category);
  }
  return {known, fresh, restore, record};
}
