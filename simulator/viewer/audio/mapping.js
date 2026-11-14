// Pure state-to-sound mappings; no browser or audio resources are needed.
export function clamp(value, low = 0, high = 1) {
  return Math.max(low, Math.min(high, Number.isFinite(value) ? value : low));
}
export function motorParameters(output) {
  const speed = clamp(Math.abs(output));
  return {frequency: 45 + 190 * Math.sqrt(speed), gain: speed * speed * 0.045,
    type: output < 0 ? 'triangle' : 'sawtooth'};
}
export function depthCutoff(depth) {
  return 250 + 2750 * Math.exp(-clamp(depth, 0, 1000) / 18);
}
export function detectEvents(previous, state) {
  if (!previous || state.t < previous.t || state.vehicle_id !== previous.vehicle_id) return [];
  const events = [];
  for (const key of ['locked', 'keep_depth', 'photos']) {
    if (state[key] !== previous[key]) events.push(key);
  }
  if (state.rc?.right_switch !== previous.rc?.right_switch) events.push('light');
  for (const key of ['warn', 'broken']) {
    if (state.tether?.[key] && !previous.tether?.[key]) events.push(key);
  }
  if (state.score?.finished && !previous.score?.finished) events.push('complete');
  if (state.battery <= 20 && previous.battery > 20) events.push('warn');
  const known = new Set((previous.events || []).map(eventKey));
  for (const event of state.events || []) {
    if (!known.has(eventKey(event))) events.push(event.severity);
  }
  return events;
}
function eventKey(event) {
  return JSON.stringify([event.t, event.severity, event.obstacle, event.where]);
}
