// True while a full-screen cover hides the dive canvas (cold-open black beat or brand chapter card).
// Shader warm-up and other hitch-hiding work may run harder here; the player cannot see the hitch.

export function isIdleCover({coldOpen = null} = {}) {
  if (coldOpen?.active && globalThis.document?.body?.dataset?.coldBeat === 'black') return true;
  return !!globalThis.document?.querySelector?.('.brand-card-overlay');
}
