// Persist and validate desktop display preferences independently of game preferences.
const fs = require('node:fs');
function validate(value) {
  if (!value || !['windowed', 'borderless', 'fullscreen'].includes(value.mode)) throw Error('Invalid mode');
  if (!Number.isInteger(value.display) || !Number.isInteger(value.width) || !Number.isInteger(value.height)) {
    throw Error('Invalid display dimensions');
  }
  if (value.width < 640 || value.width > 7680 || value.height < 480 || value.height > 4320) {
    throw Error('Invalid resolution');
  }
  return { mode: value.mode, display: value.display, width: value.width, height: value.height };
}
function apply(window, displays, input) {
  const value = validate(input);
  const display = displays.find(item => item.id === value.display);
  if (!display) throw Error('Display unavailable');
  window.setFullScreen(false);
  window.setResizable(value.mode === 'windowed');
  const bounds = value.mode === 'borderless' ? display.bounds : {
    x: display.workArea.x, y: display.workArea.y, width: value.width, height: value.height };
  window.setMenuBarVisibility(false);
  window.setBounds(bounds);
  window.setFullScreen(value.mode === 'fullscreen');
  return value;
}
// Mode and size the settings UI should show: live window first, then the last saved file.
function readCurrent(window, displays, saved) {
  const bounds = window.getBounds();
  const match = displays.find(function byBounds(item) {
    return item.id === saved?.display;
  }) || displays.find(function covering(item) {
    const area = item.bounds;
    const cx = bounds.x + bounds.width / 2;
    const cy = bounds.y + bounds.height / 2;
    return cx >= area.x && cy >= area.y && cx < area.x + area.width && cy < area.y + area.height;
  }) || displays[0];
  let mode = 'windowed';
  if (window.isFullScreen()) mode = 'fullscreen';
  else if (!window.isResizable()) mode = 'borderless';
  else if (saved && ['windowed', 'borderless', 'fullscreen'].includes(saved.mode)) mode = saved.mode;
  return {
    mode,
    display: match?.id ?? 0,
    width: Math.round(bounds.width) || saved?.width || 1280,
    height: Math.round(bounds.height) || saved?.height || 720,
  };
}
function listDisplays(screenApi) {
  return screenApi.getAllDisplays().map(function row(item) {
    return {
      id: item.id,
      bounds: item.bounds,
      workArea: item.workArea,
      displayFrequency: item.displayFrequency,
      refreshRateMutable: false,
      vsync: true,
    };
  });
}
function snapshot(data) {
  // Preserve each launch's input before Auto-Cloud or the next launch replaces files.
  const target = require('node:path').join(data, 'local-backups', String(Date.now()));
  fs.mkdirSync(target, { recursive: true });
  for (const name of ['preferences.json', 'collection', 'window.json', 'saves']) {
    const source = require('node:path').join(data, name);
    if (fs.existsSync(source)) fs.cpSync(source, require('node:path').join(target, name), { recursive: true });
  }
}
module.exports = { validate, apply, snapshot, readCurrent, listDisplays };
