// PlayStation (DualShock 4 / DualSense) pads that the browser reports without the standard mapping.
//
// Chromium maps every pad listed in SONY_PRODUCTS to the standard layout itself (mapping "standard", 17 buttons
// plus the touchpad click at index 17), on USB and Bluetooth alike. This module only covers the raw fallback
// (mapping ""): a browser or driver that does not know the product. The raw order then depends on the platform,
// not on the pad, so it is chosen from the id format instead of the SDL database (whose Linux records for these
// products disagree with each other):
// - HID usage order (Chromium on Windows and macOS, id "Name (Vendor: 054c Product: 0ce6)"): buttons
//   □ ✕ ○ △ L1 R1 L2 R2 Share Options L3 R3 PS touchpad; axes LX LY RX L2 R2 RY, hat switch on axis 9.
// - Linux evdev order (id "054c-0ce6-Name"): buttons ✕ ○ △ □ L1 R1 L2 R2 Share Options PS L3 R3; axes
//   LX LY L2 RX RY R2, hat as axes 6 (x) and 7 (y). The touchpad is a separate input device there.
// Triggers arrive as full-range axes (-1 released, +1 pressed) and are scaled to 0..1 like the standard mapping.

export const SONY_VENDOR = '054c';
// DualShock 4 (two revisions and the USB wireless adaptor), DualSense, DualSense Edge.
export const SONY_PRODUCTS = new Set(['05c4', '09cc', '0ba0', '0ce6', '0df2']);
const HAT_AXIS = 9;
const STANDARD_BUTTONS = 18;

// The Windows/macOS hat switch is one axis stepping clockwise from up (-1) in 2/7 steps; released reads above 1.
// Thresholds copied from Chromium's DpadFromAxis (device/gamepad/gamepad_standard_mappings.cc).
export function hatFromAxis(value) {
  const direction = {up: false, right: false, down: false, left: false};
  if (!Number.isFinite(value) || value === 0 || value > 1 || value < -1) return direction;
  direction.up = value < -0.7 || value >= 0.95;
  direction.right = value >= -0.75 && value < -0.1;
  direction.down = value >= -0.2 && value < 0.45;
  direction.left = value >= 0.4;
  return direction;
}

// A full-range trigger axis as a 0..1 button value. Exactly 0 is what an axis reads before the pad's first report,
// so it counts as released rather than half pressed.
export function triggerFromAxis(value) {
  if (!Number.isFinite(value) || value === 0) return 0;
  return Math.max(0, Math.min(1, (value + 1) / 2));
}

// The vendor:product pair and id style ("hid" for Chromium's "(Vendor: … Product: …)", "evdev" for "vvvv-pppp-").
export function sonyLayout(id = '') {
  const hid = /Vendor:\s*([0-9a-f]{4})\s+Product:\s*([0-9a-f]{4})/i.exec(id);
  if (hid) return SONY_PRODUCTS.has(hid[2].toLowerCase()) && hid[1].toLowerCase() === SONY_VENDOR ? 'hid' : null;
  const evdev = /^([0-9a-f]{4})-([0-9a-f]{4})-/i.exec(id);
  if (evdev && evdev[1].toLowerCase() === SONY_VENDOR && SONY_PRODUCTS.has(evdev[2].toLowerCase())) return 'evdev';
  return null;
}

function values(pad) {
  return {
    axes: Array.from(pad.axes, Number),
    buttons: Array.from(pad.buttons, function buttonValue(button) {
      return button?.value || +!!button?.pressed;
    }),
  };
}

function hidSnapshot(raw) {
  const b = raw.buttons;
  const a = raw.axes;
  const hat = hatFromAxis(a[HAT_AXIS]);
  const buttons = [b[1], b[2], b[0], b[3], b[4], b[5], triggerFromAxis(a[3]), triggerFromAxis(a[4]), b[8], b[9],
    b[10], b[11], +hat.up, +hat.down, +hat.left, +hat.right, b[12], b[13]];
  return {axes: [a[0], a[1], a[2], a[5]], buttons};
}

function evdevSnapshot(raw) {
  const b = raw.buttons;
  const a = raw.axes;
  const x = a[6] || 0;
  const y = a[7] || 0;
  const buttons = [b[0], b[1], b[3], b[2], b[4], b[5], triggerFromAxis(a[2]), triggerFromAxis(a[5]), b[8], b[9],
    b[11], b[12], +(y < -0.5), +(y > 0.5), +(x < -0.5), +(x > 0.5), b[10], 0];
  return {axes: [a[0], a[1], a[3], a[4]], buttons};
}

// Standard-layout snapshot for a raw Sony pad, or null when the pad is standard already or not a known product.
export function normalizePlayStation(pad) {
  if (!pad || pad.mapping === 'standard') return null;
  const layout = sonyLayout(pad.id);
  if (!layout) return null;
  const raw = values(pad);
  const snapshot = layout === 'hid' ? hidSnapshot(raw) : evdevSnapshot(raw);
  snapshot.axes = snapshot.axes.map(function axis(value) {
    return Number.isFinite(value) ? value : 0;
  });
  snapshot.buttons = Array.from({length: STANDARD_BUTTONS}, function button(_, index) {
    const value = snapshot.buttons[index];
    return Number.isFinite(value) ? value : 0;
  });
  return {known: true, ...snapshot};
}
