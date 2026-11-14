// Validate and persist desktop display settings without changing the simulation.
const fs = require('node:fs');
function installWindowSettings(window, screen, ipcMain, trusted, filename) {
  let settings = {mode: process.env.SteamDeck === '1' ? 'fullscreen' : 'windowed',
    width: 1280, height: 800, display: 0, zoom: 1};
  try { settings = validate(JSON.parse(fs.readFileSync(filename, 'utf8'))); } catch {}
  function validate(value) {
    if (!['windowed', 'borderless', 'fullscreen'].includes(value.mode) ||
        !Number.isInteger(value.display) || value.display < 0 ||
        !Number.isInteger(value.width) || value.width < 800 || value.width > 7680 ||
        !Number.isInteger(value.height) || value.height < 600 || value.height > 4320 ||
        !Number.isFinite(value.zoom) || value.zoom < 0.75 || value.zoom > 2) throw Error('Invalid display settings');
    return {mode: value.mode, width: value.width, height: value.height, display: value.display, zoom: value.zoom};
  }
  function apply(value) {
    const display = screen.getAllDisplays()[value.display];
    if (!display) throw Error('Display unavailable');
    window.setFullScreen(false);
    window.setResizable(true);
    window.setBounds(value.mode === 'borderless' ? display.bounds :
      {x: display.workArea.x, y: display.workArea.y, width: value.width, height: value.height});
    window.setMenuBarVisibility(false);
    window.setFullScreen(value.mode === 'fullscreen');
    window.webContents.setZoomFactor(value.zoom);
  }
  apply(settings);
  ipcMain.handle('rov:display', (event, value) => {
    if (!trusted(event)) throw Error('Forbidden IPC');
    if (value) {
      const next = validate(value);
      apply(next);
      fs.writeFileSync(filename, JSON.stringify(next));
      settings = next;
    }
    return {settings, displays: screen.getAllDisplays().map(display =>
      ({id: display.id, bounds: display.bounds, refreshRate: display.displayFrequency}))};
  });
}
module.exports = {installWindowSettings};
