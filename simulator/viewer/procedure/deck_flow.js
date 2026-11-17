// Pure helpers of the deck pre-dive check (server: qysim/procedure.py, flow "deck"). No DOM and no three.js, so the
// node tests can load them: which step is current, which camera shot it wants, how fast a rotor turns while it is
// pulsed on deck, which begin message the context allows, and which new crew or defect events a state carries.

// Visual rotor rate (rad/s) of a thruster pulsed in air: a short-test pulse turns the prop briskly. Presentation
// only; the server's diagnostic thrust stays what it was.
export const DECK_SPIN = 26;
const SPIN_RESPONSE = 6;              // 1/s: spin-up and run-down of the prop after a pulse
const LEGACY_RATE = 40;               // rad/s per unit of normalised thrust, as the viewer always drew it

/** The current hands-on step of the deck flow ('walkaround', 'power', ...), or null outside it. */
export function deckStep(p) {
  if (p?.flow !== 'deck' || p.phase !== 'checks') return null;
  return p.order?.[p.checked?.length || 0] || null;
}

/** The walk-around station on screen: the last one looked at, -1 before the walk starts. */
export function currentStation(p) {
  const seen = p?.seen || [];
  return seen.length ? Math.max(...seen) : -1;
}

/** The next thruster still to be pulsed, or -1 when every one has been. */
export function nextThruster(p) {
  for (let index = 0; index < (p?.thrusters || 0); index++) {
    if (!p.tests?.includes(index)) return index;
  }
  return -1;
}

/** True while a found defect is still on the vehicle (or being cleared). */
export function defectPending(p) {
  return !!(p?.defect?.found && !p.defect.fixed);
}

/**
 * Camera shot key for the deck flow: {key, thruster?, station?}. 'overview' before and between steps, a station
 * during the walk-around, the pulsed thruster during the short test, 'onboard' for the camera check.
 */
export function deckShot(p) {
  if (p?.flow !== 'deck') return null;
  if (p.phase === 'launch') return {key: 'launch'};
  const step = deckStep(p);
  if (!step) return null;
  if (step === 'walkaround') {
    const station = currentStation(p);
    return station < 0 ? {key: 'overview'} : {key: 'station', station};
  }
  if (step === 'thrusters') {
    const index = p.diagnostic > 0 && Number.isInteger(p.diagnostic_index) ? p.diagnostic_index : nextThruster(p);
    return {key: 'thruster', thruster: Math.max(0, index)};
  }
  if (step === 'camera') return {key: 'onboard'};
  return {key: step};
}

/**
 * Rotor angular rate for the viewer's spin loop. Unchanged from the old inline formula unless the deck flow is
 * pulsing this thruster (the vehicle is locked on deck, so the old formula would show a still prop); then the prop
 * spins up and runs down smoothly. ``memory`` keeps the eased rate per thruster between frames.
 */
export function rotorRate(state, index, dt, memory) {
  const p = state?.procedure;
  const pulsing = !!(p?.diagnostic > 0 && p.diagnostic_index === index);
  const legacy = (state?.thrust?.[index] || 0) * LEGACY_RATE * (state?.locked ? 0 : 1);
  const previous = memory[index] || 0;
  if (!pulsing && Math.abs(previous) < .05) {
    memory[index] = 0;
    return legacy;
  }
  const target = pulsing ? DECK_SPIN : legacy;
  memory[index] = previous + (target - previous) * (1 - Math.exp(-SPIN_RESPONSE * Math.max(0, dt)));
  return memory[index];
}

/**
 * Extra fields of the procedure begin message. Defects are planted only where the context is training or career
 * (a contract, an exam, the story campaign); ``?predive_defect=<kind|none>`` forces one for authors and tests.
 */
export function beginFields(query, random = Math.random) {
  const fields = {flow: 'deck'};
  const forced = query.get('predive_defect');
  if (forced) {
    fields.defect = forced;
    return fields;
  }
  const career = query.has('contract') || query.get('exam') === '1' || query.get('mission') === 'campaign';
  if (career) {
    fields.defects = true;
    fields.seed = Math.floor(random() * 1e9);
  }
  return fields;
}

/** Events worth a radio call or a prompt: crew reports, defect found/fixed, false reports and missed faults. */
const CALL_ACTIONS = new Set(['crew', 'defect_found', 'defect_fixed', 'false_report', 'fault']);

/**
 * Remembers which events were already announced. ``fresh(events)`` returns the new ones in order; events are
 * keyed by time, action and detail, so the last-200 window the server streams can slide without repeats.
 */
export function createEventWatch() {
  const seen = new Set();
  function keyOf(event) {
    return `${event.t}|${event.action}|${event.key || event.defect || event.station || ''}`;
  }
  function fresh(events) {
    const out = [];
    for (const event of events || []) {
      if (!CALL_ACTIONS.has(event.action)) continue;
      const key = keyOf(event);
      if (seen.has(key)) continue;
      seen.add(key);
      out.push(event);
    }
    return out;
  }
  function clear() {
    seen.clear();
  }
  return {fresh, clear};
}
