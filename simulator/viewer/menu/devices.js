// Reuse the shared T02 device mapping and settings without installing flight controls in the frontend.
import { PRESETS, BUTTONS } from "../input/actions.js";
import { createDevices } from "../input/devices.js";
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
      const custom = JSON.parse(saved || "{}").custom || {};
      for (const key of Object.keys(settings.custom)) delete settings.custom[key];
      Object.assign(settings.custom, custom);
      savedMapping = saved;
    }
  } catch {}
  frame = devices.poll(panel?.selected() || "auto");
  if (panel) {
    const open = panel.open();
    if (open && !panelWasOpen) waitingForPanelRelease = true;
    if (!frame.snapshot?.buttons.some(value => value > 0.5)) waitingForPanelRelease = false;
    if (!waitingForPanelRelease) panel.update(frame);
    panelWasOpen = open;
  }
  return frame;
}
function saveSettings() {
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
  parent.append(document.getElementById("inputSettingsButton"));
}
