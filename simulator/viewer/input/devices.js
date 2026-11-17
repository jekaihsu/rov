// Snapshot all attached devices and normalize known mappings without assuming axis/button counts.
// Order: standard mapping as reported, a calibrated custom profile, the PlayStation raw layouts (playstation.js),
// then the SDL-derived database, whose hat (`h0.1`) and full-range trigger axes are decoded here.
import { bindingValue } from "./actions.js";
import { hatFromAxis, normalizePlayStation, triggerFromAxis } from "./playstation.js";

const TRIGGER_SLOTS = new Set([6, 7]);
const HAT_MASKS = { 1: "up", 2: "right", 4: "down", 8: "left" };
const HID_HAT_AXIS = 9;

// Highest raw axis index a record names, so Linux hat axes (reported after the plain axes) can be located.
function lastNamedAxis(mapping) {
  let last = -1;
  for (const binding of [...mapping.axes, ...mapping.buttons]) {
    const match = /^[+-]?a(\d+)/.exec(binding || "");
    if (match) last = Math.max(last, Number(match[1]));
  }
  return last;
}

// SDL hat notation `hN.M` (M: 1 up, 2 right, 4 down, 8 left). Chromium on Windows/macOS reports hat 0 as one
// stepped axis at index 9; on Linux every hat is an x/y axis pair after the plain axes.
function hatValue(binding, raw, mapping, id) {
  const match = /^h(\d+)\.(\d+)$/.exec(binding);
  const direction = match && HAT_MASKS[match[2]];
  if (!direction) return 0;
  const hat = Number(match[1]);
  if (/Vendor:/i.test(id) && hat === 0 && raw.axes.length > HID_HAT_AXIS) {
    return +hatFromAxis(raw.axes[HID_HAT_AXIS])[direction];
  }
  const base = lastNamedAxis(mapping) + 1 + hat * 2;
  const x = raw.axes[base] || 0;
  const y = raw.axes[base + 1] || 0;
  const pressed = { up: y < -0.5, down: y > 0.5, left: x < -0.5, right: x > 0.5 };
  return +pressed[direction];
}

// One standard button from a database or custom record. A bare full-range axis on a trigger slot is scaled to 0..1
// (SDL semantics), so a released trigger reads 0 instead of -1.
function recordButton(binding, index, raw, mapping, id) {
  if (!binding) return 0;
  if (binding[0] === "h") return hatValue(binding, raw, mapping, id);
  if (TRIGGER_SLOTS.has(index) && /^a\d+$/.test(binding)) return triggerFromAxis(bindingValue(binding, raw));
  return bindingValue(binding, raw);
}
export function deviceKey(id) {
  const match = /(?:vendor:\s*)?([0-9a-f]{4})[- :]+(?:product:\s*)?([0-9a-f]{4})/i.exec(id);
  return match ? `${match[1]}:${match[2]}`.toLowerCase() : id;
}
export function normalize(pad, database, custom = {}) {
  const raw = { axes: Array.from(pad.axes), buttons: Array.from(pad.buttons, (b) => b.value || +b.pressed) };
  const mapping = custom[pad.id] || database[deviceKey(pad.id)];
  if (pad.mapping === "standard") return { ...raw, known: true };
  if (!custom[pad.id]) {
    const sony = normalizePlayStation(pad);
    if (sony) return sony;
  }
  if (!mapping) return { ...raw, known: false };
  return {
    known: true,
    axes: mapping.axes.map((b) => bindingValue(b, raw)),
    buttons: mapping.buttons.map(function mappedButton(binding, index) {
      return recordButton(binding, index, raw, mapping, pad.id);
    }),
  };
}
export function createDevices(database, custom) {
  let active = null;
  const previous = new Map();
  function poll(preferred = "auto") {
    const devices = Array.from(navigator.getGamepads?.() || []).filter((p) => p?.connected);
    for (const pad of devices) {
      const values = [...pad.axes, ...pad.buttons.map((b) => b.value || +b.pressed)];
      const old = previous.get(pad.index);
      if (values.some((v, i) => Math.abs(v - (old?.[i] || 0)) > 0.12)) active = pad.index;
      previous.set(pad.index, values);
    }
    for (const index of previous.keys()) {
      if (!devices.some((p) => p.index === index)) previous.delete(index);
    }
    const pad =
      preferred === "keyboard"
        ? null
        : devices.find((p) => String(p.index) === preferred) ||
          devices.find((p) => p.index === active) ||
          (preferred === "auto" ? devices[0] : null);
    return { devices, pad: pad || null, snapshot: pad ? normalize(pad, database, custom) : null };
  }
  return { poll };
}
