// Cutscene look of the cold open: a scoped, owner-approved exception to the fidelity rules
// (docs/design/cold-open/README.md §3). While the opening is scripted and the player has no control (black
// screen, establishing shot), the picture may use the underwater beautification (sun shafts, caustics, vignette)
// whatever the player's fidelity settings say. The moment the player takes over, or the cold open ends or is
// skipped, the picture is the player's own settings again.
//
// Nothing here writes to the fidelity store: no item is set, no preset changes, nothing reaches localStorage, and
// no fidelity item is registered. The override lives in this module only and is read by the one consumer of the
// look (fx/beautify.js, beautifyEnabled()), so "restoring" is simply dropping the override. This module must stay
// free of imports: fx/beautify.js reads it, and node tests load it on its own.
//
//   const look = createCinematicLook();
//   look.set(true);     // scripted beat: beautification on for the picture
//   look.set(false);    // player in control, ended or skipped: back to the fidelity settings
//
// Music has no override here because it needs none: the cutscene cues of audio/music.js ('openingTension',
// 'flashback') already play outside the `diveMusic` fidelity item, and cold_open.js hands the music back to the
// dive rules at the handover. CINEMATIC_MUSIC names those cues for the one caller.

export const CINEMATIC_LOOK_ID = 'waterBeautify';
export const CINEMATIC_MUSIC = Object.freeze({scripted: 'openingTension', closing: 'flashback'});

const holders = new Set();

/** True while any cutscene holds the beautified look; fx/beautify.js ORs it with the fidelity item. */
export function cinematicLookActive() {
  return holders.size > 0;
}

/** Beats in which the picture is scripted and the player has no control of the vehicle. */
export function isScriptedBeat(view) {
  return !!view && !!view.cinematic && !view.ended;
}

/**
 * One holder of the look. set(true) takes it, set(false) or release() gives it back; both are idempotent, so a
 * skip, an end and a late frame can all release without counting.
 */
export function createCinematicLook() {
  const token = {};
  function set(on) {
    if (on) holders.add(token);
    else holders.delete(token);
    return holders.has(token);
  }
  return {
    set,
    release() {
      return set(false);
    },
    get active() {
      return holders.has(token);
    },
  };
}
