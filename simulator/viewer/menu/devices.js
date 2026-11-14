// Reuse the shared T02 device mapping and settings without installing flight controls in the frontend.
import { PRESETS, BUTTONS, bindingValue } from "../input/actions.js";
import { createDevices, normalize } from "../input/devices.js";
import { createHaptics } from "../input/haptics.js";
import { installSettings } from "../input/settings.js";
const database = await fetch(new URL("../input/controller-db.json", import.meta.url)).then(readDatabase);
function readDatabase(response) {
  return response.json();
}
let settings = {};
try {
  settings = JSON.parse(localStorage.getItem("rov.input.v1") || "{}");
} catch {}
const desktopSettings = await window.rovDesktop?.readInput?.();
if (desktopSettings && Object.keys(desktopSettings).length) settings = desktopSettings;
if (!settings || typeof settings !== "object" || Array.isArray(settings)) settings = {};
settings.custom ||= {};
settings.channels ||= {};
settings.bindings = { ...PRESETS.current, ...BUTTONS, ...settings.bindings };
const standardBindings = new Set(Object.keys({ ...PRESETS.current, ...BUTTONS }));
const featureBindings = new Map();
function preserveFeatureBindings() {
  for (const [name, binding] of Object.entries(settings.bindings)) {
    if (!standardBindings.has(name)) featureBindings.set(name, binding);
  }
  settings.bindings = { ...settings.bindings, ...Object.fromEntries(featureBindings) };
}
preserveFeatureBindings();
const devices = createDevices(database, settings.custom);
let frame = {};
let panel = null;
let panelWasOpen = false;
let waitingForPanelRelease = false;
let savedMapping = null;
try {
  savedMapping = localStorage.getItem("rov.input.v1");
} catch {}
export function pollMenuDevices() {
  try {
    const saved = localStorage.getItem("rov.input.v1");
    if (saved !== savedMapping) {
      const profile = JSON.parse(saved || "{}");
      const custom = profile.custom || {};
      settings.bindings = { ...PRESETS.current, ...BUTTONS, ...profile.bindings };
      for (const key of Object.keys(settings.custom)) delete settings.custom[key];
      Object.assign(settings.custom, custom);
      savedMapping = saved;
    }
  } catch {}
  frame = devices.poll(panel?.selected() || "auto");
  if (panel) {
    const open = panel.open();
    if (open && !panelWasOpen) waitingForPanelRelease = true;
    if (!frame.snapshot?.buttons.some((value) => value > 0.5)) waitingForPanelRelease = false;
    if (!waitingForPanelRelease) panel.update(frame);
    panelWasOpen = open;
  }
  return frame;
}
function saveSettings() {
  preserveFeatureBindings();
  try {
    localStorage.setItem("rov.input.v1", JSON.stringify(settings));
  } catch {}
  window.rovDesktop?.rememberInput?.(settings);
}
function setControlMode(value) {
  const control = document.getElementById("menuControl");
  control.value = value;
  control.dispatchEvent(new Event("change"));
}
export function installMenuControls(parent) {
  const haptics = createHaptics(() => frame.pad, settings);
  panel = installSettings(settings, saveSettings, haptics, setControlMode);
  panel.registerActions?.(
    Object.fromEntries([...featureBindings].map(([name, binding]) => [name, { label: name, binding }])),
  );
  parent.append(document.getElementById("inputSettingsButton"));
}

export function menuBindingValue(name, fallback) {
  const { snapshot } = pollMenuDevices();
  return snapshot ? bindingValue(settings.bindings[name] ?? fallback, snapshot) : 0;
}

export function menuDevicesActive() {
  const { devices: attached } = pollMenuDevices();
  return attached.some(function held(pad) {
    const snapshot = normalize(pad, database, settings.custom);
    return (
      snapshot.buttons.some((value) => value > 0.5) || snapshot.axes.slice(0, 4).some((value) => Math.abs(value) > 0.2)
    );
  });
}
