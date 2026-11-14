// Reuse the shared T02 device mapping and settings without installing flight controls in the frontend.
import { createDevices } from '../input/devices.js';
import { createHaptics } from '../input/haptics.js';
import { installSettings } from '../input/settings.js';
const database = await fetch(new URL('../input/controller-db.json', import.meta.url)).then(readDatabase);
function readDatabase(response) {
  return response.json();
}
let settings = {};
try {
  settings = JSON.parse(localStorage.getItem('rov.input.v1') || '{}');
} catch {}
const desktopSettings = await window.rovDesktop?.readInput?.();
if (desktopSettings && Object.keys(desktopSettings).length) settings = desktopSettings;
settings.custom ||= {};
const devices = createDevices(database, settings.custom);
let frame = {};
let panel = null;
export function pollMenuDevices() {
  frame = devices.poll(panel?.selected() || 'auto');
  panel?.update(frame);
  return frame;
}
function saveSettings() {
  try {
    localStorage.setItem('rov.input.v1', JSON.stringify(settings));
  } catch {}
  window.rovDesktop?.rememberInput?.(settings);
}
function setControlMode(value) {
  const control = document.getElementById('menuControl');
  control.value = value;
  control.dispatchEvent(new Event('change'));
}
export function installMenuControls(parent) {
  const haptics = createHaptics(() => frame.pad, settings);
  panel = installSettings(settings, saveSettings, haptics, setControlMode);
  parent.append(document.getElementById('inputSettingsButton'));
}
