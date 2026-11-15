// Pure binding resolution and output shaping; PWM conversion stays with the transport.
// Default bindings for every action and context live in bindings.js.
export const CHANNELS = ["left_ud", "left_lr", "right_ud", "right_lr", "left_wave", "right_wave"];
export const PRESETS = {
  current: {
    left_lr: "a0",
    left_ud: "-a1",
    right_lr: "a2",
    right_ud: "-a3",
    left_wave: ["b7", "b6"],
    right_wave: ["b5", "b4"],
  },
  drone: {
    left_lr: "a0",
    left_ud: "-a1",
    right_lr: "a2",
    right_ud: "-a3",
    left_wave: ["b7", "b6"],
    right_wave: ["b5", "b4"],
  },
};
export function bindingValue(binding, snapshot) {
  if (Array.isArray(binding)) return bindingValue(binding[0], snapshot) - bindingValue(binding[1], snapshot);
  // Optional leading "+" is SDL half-axis notation and matches an unsigned axis/button read.
  const match = /^([+-]?)([ab])(\d+)(~?)$/.exec(binding || "");
  if (!match) return 0;
  const value = (match[2] === "a" ? snapshot.axes : snapshot.buttons)[Number(match[3])] || 0;
  const sign = match[1] === "-" ? -1 : 1;
  return sign * (match[4] ? (value > 0.5 ? 1 : 0) : value);
}
export function radial(x, y, inner = 0.08, outer = 0.02) {
  const length = Math.hypot(x, y);
  if (length <= inner) return [0, 0];
  const scale = Math.min(1, (length - inner) / Math.max(0.01, 1 - inner - outer)) / length;
  return [x * scale, y * scale];
}
export function curve(value, { expo = 0, sensitivity = 1, invert = false } = {}) {
  const magnitude = Math.min(1, Math.abs(value));
  return Math.max(
    -1,
    Math.min(1, Math.sign(value) * ((1 - expo) * magnitude + expo * magnitude ** 3) * sensitivity * (invert ? -1 : 1)),
  );
}

// Capability is advertised by telemetry, never inferred from the client defaults.
export function assistFields(state, controls) {
  const assist = state?.assist;
  if (!assist || typeof assist !== "object" || Array.isArray(assist)) return {};
  return { assist: controls.assist, profile: controls.profile };
}
