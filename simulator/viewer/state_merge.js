// Merge negotiated state deltas (PROTOCOL.md static_once) into a retained snapshot.
// Live viewers that declare caps: ["static_once"] must run every state through here
// before StateBuffer, HUD, recording or the instructor console. Replay files store
// complete snapshots, so they do not declare the capability and need no merge.

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

function mergeVehicle(previous, incoming) {
  if (!previous) return incoming;
  const merged = {...previous, ...incoming};
  for (const field of VEHICLE_FIELDS) {
    if (!(field in incoming) && field in previous) merged[field] = previous[field];
  }
  return merged;
}

function mergeFleet(previous = [], incoming) {
  if (!Array.isArray(incoming)) return previous;
  const prior = new Map(previous.map(entry => [vehicleKey(entry), entry]));
  return incoming.map(entry => mergeVehicle(prior.get(vehicleKey(entry)), entry));
}

/** Fill omitted static_once fields from the previous complete snapshot. */
export function mergeState(previous, incoming) {
  if (!incoming || typeof incoming !== 'object') return incoming;
  if (!previous) return {...incoming};
  const merged = {...previous, ...incoming};
  for (const field of TOP_FIELDS) {
    if (!(field in incoming) && field in previous) merged[field] = previous[field];
  }
  if ('vehicles' in incoming) {
    merged.vehicles = mergeFleet(previous.vehicles, incoming.vehicles);
  }
  return merged;
}

/** Stateful merger for one WebSocket (or replay) stream. */
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
