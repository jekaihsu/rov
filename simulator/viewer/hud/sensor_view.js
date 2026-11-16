// Pilot instrument readings: what the HUD may show for the current fidelity profile.
// In the real preset the HUD shows only what the vehicle's own sensors report (`state.sensors`): estimated
// heading and depth, altimeter altitude, DVL ground speed while bottom lock holds, and no water current.
// The `truthTelemetry` fidelity item (exceeds the real vehicle) restores the simulator's ground truth.
// Servers that predate `state.sensors` keep the previous truth-based presentation.
import {getFidelity, registerFidelityItem} from '../fidelity.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('hud.sensor_view', {
  truthTelemetry: '模擬真值儀表',
  truthTelemetryHelp: '顯示真機沒有的資訊：實際洋流、對水速度、平坦海床離底高度與真實航向深度；'
    + '關閉時只顯示感測器估計值。'
});
// Proximity readout range of the HUD's forward-range text, metres (same as the geometric estimate).
const FORWARD_SHOWN_M = 5;

function isTrue(value) {
  return value === true;
}
registerFidelityItem({
  id: 'truthTelemetry', descriptionKey: 'truthTelemetryHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true, exceeds: isTrue
}, STRINGS);

export function formatKnots(value) {
  return value == null ? '—' : value.toFixed(2);
}

export function showsTruth(state, fidelity = getFidelity()) {
  return !state?.sensors || fidelity.get('truthTelemetry') === true;
}

function truthReadings(state, world) {
  return {
    truth: true,
    depth: state.pos[2],
    heading: state.euler?.[2] || 0,
    altitude: world ? world.seabed_depth - state.pos[2] : null,
    speedKn: state.speed_kn ?? 0,
    currentKn: state.current_kn ?? 0,
    range: undefined,
    dvlLost: false
  };
}

function sensorRange(sensors) {
  const range = sensors.range;
  if (range == null || range > FORWARD_SHOWN_M) return null;
  return range;
}

// Returns {truth, depth, heading, altitude, speedKn, currentKn, range, dvlLost}. `null` means "no reading";
// `range` is undefined in truth mode so the caller keeps its own geometric estimate.
export function pilotReadings(state, world, fidelity = getFidelity()) {
  if (showsTruth(state, fidelity)) return truthReadings(state, world);
  const sensors = state.sensors;
  const dvl = sensors.dvl || {};
  return {
    truth: false,
    depth: sensors.depth,
    heading: sensors.heading,
    altitude: sensors.altitude ?? null,
    speedKn: dvl.status === 'lost' ? null : dvl.ground_speed_kn ?? null,
    currentKn: null,
    range: sensorRange(sensors),
    dvlLost: dvl.status === 'lost'
  };
}
