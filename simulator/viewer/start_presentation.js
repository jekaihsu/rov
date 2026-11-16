// How a dive begins in the assisted presentation: start a few metres short of the first work point instead of at
// the surface (server: qysim/start_point.py, `{"type":"start","point":"near_target"}`), and arm depth hold so a
// positively buoyant vehicle does not drift back up while the player finds the controls.
// Both are fidelity items that are off in `real`: there the dive starts at the surface with depth hold off, exactly
// as before, and the deployment procedure (procedure/index.js) governs the launch. The story campaign keeps its own
// scripted start and teaches depth hold itself, so neither applies there. Nothing changes the vehicle dynamics.
import {registerFidelityItem, getFidelity} from './fidelity.js';

export const NEAR_START_ITEM = 'nearStart';
export const DEPTH_HOLD_START_ITEM = 'depthHoldStart';

registerFidelityItem({
  id: NEAR_START_ITEM,
  labelKey: NEAR_START_ITEM,
  descriptionKey: 'nearStartHelp',
  type: 'toggle',
  defaults: {real: false, assisted: true},
  exceedsReal: true,
}, {
  nearStart: '從作業點附近開始',
  nearStartHelp: '真實作業從水面下潛；開啟後直接從第一個作業點前方幾公尺開始。下次載入場景時生效。',
});

registerFidelityItem({
  id: DEPTH_HOLD_START_ITEM,
  labelKey: DEPTH_HOLD_START_ITEM,
  descriptionKey: 'depthHoldStartHelp',
  type: 'toggle',
  defaults: {real: false, assisted: true},
}, {
  depthHoldStart: '下潛時先開定深',
  depthHoldStartHelp: '每次下潛開始時自動按下定深，鬆桿後維持深度；之後可隨時用定深鍵關閉。',
});

function storyMission() {
  return new URLSearchParams(location.search).get('mission') === 'campaign';
}

function solo(state) {
  return (state.room?.players?.length || 1) <= 1;
}

// send: the viewer's WebSocket sender. rc: the input layer's RC levels (keep_depth is written here).
export function installStartPresentation({send, rc, readOnly = false}) {
  const fidelity = getFidelity();
  let startGeneration;
  let holdGeneration;
  function wantsNearStart() {
    return !readOnly && !storyMission() && fidelity.get(NEAR_START_ITEM) === true;
  }
  function wantsDepthHold() {
    return !readOnly && !storyMission() && fidelity.get(DEPTH_HOLD_START_ITEM) === true;
  }
  // The point the launch intro descends to: the near-target start when it will be requested, else the scenario's.
  function introStart(world, fallback) {
    if (wantsNearStart() && world?.near_start?.pos) return world.near_start.pos;
    return world?.start_pos || fallback;
  }
  function requestNearStart(state, world) {
    if (startGeneration === state.control_generation) return;
    startGeneration = state.control_generation;
    if (!wantsNearStart() || !world?.near_start || state.procedure?.active) return;
    if (!state.locked || !solo(state) || state.t > 2) return;
    send({type: 'start', point: 'near_target'});
  }
  // Pressed once per dive; the server's RC echo confirms it, after which the player owns the switch.
  function armDepthHold(state) {
    if (holdGeneration === state.control_generation) return;
    if (!wantsDepthHold() || state.procedure?.active || state.remote_control) {
      holdGeneration = state.control_generation;
      return;
    }
    if (state.rc?.keep_depth) {
      holdGeneration = state.control_generation;
      return;
    }
    rc.keep_depth = 1;
  }
  function update(state, world) {
    if (readOnly || !state || state.control_generation == null) return;
    requestNearStart(state, world);
    armDepthHold(state);
  }
  return {update, introStart};
}
