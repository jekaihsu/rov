// Snapshot all attached devices and normalize known mappings without assuming axis/button counts.
import { bindingValue } from "./actions.js";
export function deviceKey(id) {
  const match = /(?:vendor:\s*)?([0-9a-f]{4})[- :]+(?:product:\s*)?([0-9a-f]{4})/i.exec(id);
  return match ? `${match[1]}:${match[2]}`.toLowerCase() : id;
}
export function normalize(pad, database, custom = {}) {
  const raw = { axes: Array.from(pad.axes), buttons: Array.from(pad.buttons, (b) => b.value || +b.pressed) };
  const mapping = custom[pad.id] || database[deviceKey(pad.id)];
  const known = pad.mapping === "standard" || !!mapping;
  if (pad.mapping === "standard" || !mapping) return { ...raw, known };
  return {
    known,
    axes: mapping.axes.map((b) => bindingValue(b, raw)),
    buttons: mapping.buttons.map((b) => bindingValue(b, raw)),
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
