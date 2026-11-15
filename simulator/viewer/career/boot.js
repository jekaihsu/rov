// First module the launch menu evaluates (imported before anything reads the fidelity store): returning from a
// contract dive, it removes the career launch parameters (?contract, ?exam and the exam's ?fidelity=real) from
// the address, puts back the fidelity settings an exam stashed, and closes a dive that ended without a result
// (page closed, returned to the menu) into the logbook so its hours are never lost.
import { STORAGE_KEY as FIDELITY_KEY } from '../fidelity.js';
import { closeAbandonedDive } from './rules.js';
import { loadCareer, storeCareer } from './save.js';

export const CAREER_PARAMS = ['contract', 'exam'];

/** The address without career launch parameters; an exam also drops the forced fidelity preset. */
export function cleanLaunchUrl(href) {
  const url = new URL(href);
  if (url.searchParams.get('exam') === '1') url.searchParams.delete('fidelity');
  for (const name of CAREER_PARAMS) url.searchParams.delete(name);
  return url;
}

/** Writes an exam's stashed fidelity record back ('' means there was none). Returns true when it did. */
export function restoreFidelity(save, storage) {
  if (save.fidelityStash === null) return false;
  try {
    if (save.fidelityStash) storage?.setItem(FIDELITY_KEY, save.fidelityStash);
    else storage?.removeItem?.(FIDELITY_KEY);
  } catch {
    // Storage refused: the player's settings stay as the exam left them.
  }
  save.fidelityStash = null;
  return true;
}

function run() {
  const host = globalThis.window;
  if (!host?.location) return;
  const clean = cleanLaunchUrl(host.location.href);
  if (clean.href !== host.location.href) host.history?.replaceState(host.history.state, '', clean);
  let storage = null;
  try {
    storage = host.localStorage;
  } catch {
    storage = null;
  }
  const save = loadCareer({ storage });
  const restored = restoreFidelity(save, storage);
  const closed = closeAbandonedDive(save);
  if (restored || closed) storeCareer(save, { storage });
}

run();
