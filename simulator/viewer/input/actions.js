// Pure binding resolution and output shaping; PWM conversion stays with the transport.
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
export const BUTTONS = {
  photo: "b0",
  record: "b1",
  depth: "b2",
  lock: "b3",
  mode: "b8",
  light: "b9",
  camera: "b10",
  assist: "b11",
  profile: "b12",
  up: "b12",
  down: "b13",
  left: "b14",
  right: "b15",
  accept: "b0",
  back: "b1",
  arm: "b16",
};
export function bindingValue(binding, snapshot) {
  if (Array.isArray(binding)) return bindingValue(binding[0], snapshot) - bindingValue(binding[1], snapshot);
  const match = /^(-?)([ab])(\d+)(~?)$/.exec(binding || "");
  if (!match) return 0;
  const value = (match[2] === "a" ? snapshot.axes : snapshot.buttons)[Number(match[3])] || 0;
  return (match[1] ? -1 : 1) * (match[4] ? (value > 0.5 ? 1 : 0) : value);
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
