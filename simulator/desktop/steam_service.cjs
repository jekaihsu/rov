// Optional Steamworks boundary: only catalogued events and integer statistics cross IPC.
const fs = require('node:fs');
const path = require('node:path');
const catalog = require('./steam/achievements.json');
function createSteam(data, logger = console) {
  let client = null;
  try {
    let id = process.env.STEAM_APP_ID;
    const file = path.join(path.dirname(process.execPath), 'steam_appid.txt');
    if (!id && fs.existsSync(file)) id = fs.readFileSync(file, 'utf8').trim();
    if (id && !/^[1-9][0-9]*$/.test(id)) throw Error('Invalid STEAM_APP_ID');
    const steam = require('steamworks.js');
    client = id ? steam.init(Number(id)) : steam.init();
    steam.electronEnableSteamOverlay();
  } catch (error) {
    logger.warn('Steam unavailable; offline training remains available:', error.message);
  }
  function status() {
    return { available: !!client, player: client?.localplayer.getName() ?? null,
      language: client?.apps.currentGameLanguage() ?? null, cloudPath: data,
      deck: client?.utils.isSteamRunningOnSteamDeck() ?? false,
      overlayActive: null, overlayDetection: 'unsupported-by-steamworks.js' };
  }
  function report(event, value = 1) {
    const entry = catalog.find(item => item.event === event);
    if (!entry || !Number.isSafeInteger(value) || value < 0 || value > 2147483647) {
      throw Error('Invalid Steam event');
    }
    if (!client) return false;
    const previous = client.stats.getInt('STAT_' + event.toUpperCase()) ?? 0;
    const saved = client.stats.setInt('STAT_' + event.toUpperCase(), Math.max(previous, value));
    const unlocked = client.achievement.activate(entry.api);
    return saved && unlocked && client.stats.store();
  }
  return { status, report };
}
module.exports = { createSteam };
