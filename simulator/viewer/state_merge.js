// Merge negotiated state deltas (PROTOCOL.md static_once) into a retained snapshot.
// Live viewers that declare caps: ["static_once"] must run every state through here
// (including states that arrive before the session reply) before StateBuffer, HUD,
// recording or the instructor console. Only states marked delta:true omit fields;
// unmarked states are complete. Replay files store complete merged snapshots.

const DELTA_KEY = 'delta';

const TOP_FIELDS = new Set([
  'vehicle', 'campaign',
  'appearance', 'paint_marks', 'room', 'mission', 'expedition', 'operation_mode', 'turbidity',
  'power', 'thermal', 'flow_field', 'link', 'leak', 'assist', 'health', 'nav', 'log',
  'events', 'damage', 'photos', 'recording', 'remote_control', 'input_latched',
  'control_generation', 'owner_id', 'vehicle_id', 'model_id', 'paused', 'battery',
  'keep_depth', 'ctrl_mode', 'locked', 'depth_hold',
]);

const VEHICLE_FIELDS = new Set([
  'vehicle', 'power', 'thermal', 'appearance', 'paint_marks', 'link', 'leak', 'assist',
  'health', 'nav', 'log', 'events', 'damage', 'photos', 'mission', 'expedition',
  'operation_mode', 'turbidity', 'recording', 'remote_control', 'input_latched',
  'control_generation', 'owner_id', 'vehicle_id', 'model_id', 'paused', 'battery',
  'keep_depth', 'ctrl_mode', 'locked', 'depth_hold',
]);

function vehicleKey(entry) {
  return entry?.vehicle_id ?? entry?.id;
}

// Only allowlisted fields that the delta omitted come from the retained entry.
// Every other key follows the incoming message, so removed keys stay removed.
function fillOmitted(previous, incoming, fields) {
  const merged = {...incoming};
  if (!previous) return merged;
  for (const field of fields) {
    if (!(field in incoming) && field in previous) merged[field] = previous[field];
  }
  return merged;
}

function mergeFleet(previous = [], incoming) {
  if (!Array.isArray(incoming)) return incoming;
  const prior = new Map(previous.map(entry => [vehicleKey(entry), entry]));
  return incoming.map(entry => fillOmitted(prior.get(vehicleKey(entry)), entry, VEHICLE_FIELDS));
}

/**
 * Fill omitted static_once fields from the previous merged snapshot.
 * States without ``delta: true`` are complete and replace the retained snapshot.
 */
export function mergeState(previous, incoming) {
  if (!incoming || typeof incoming !== 'object') return incoming;
  if (incoming[DELTA_KEY] !== true || !previous) {
    const complete = {...incoming};
    delete complete[DELTA_KEY];
    return complete;
  }
  const merged = fillOmitted(previous, incoming, TOP_FIELDS);
  delete merged[DELTA_KEY];
  if ('vehicles' in incoming) merged.vehicles = mergeFleet(previous.vehicles, incoming.vehicles);
  return merged;
}

/** Stateful merger for one WebSocket stream. Reset only when a new socket opens. */
export function createStateMerger() {
  let previous = null;
  return {
    reset() {
      previous = null;
    },
    merge(message) {
      if (!message || message.type !== 'state') return message;
      const merged = mergeState(previous, message);
      previous = merged;
      return merged;
    },
  };
}

export const STATIC_ONCE_CAP = 'static_once';
export const VIEWER_CAPS = [STATIC_ONCE_CAP];
