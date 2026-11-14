// Optional main-process Steam adapter; training launches remain usable offline.
const manifest = require('./steam/achievements.json');
function createSteam(cloudPath, load = () => require('steamworks.js')) {
  let client = null;
  let error = null;
  try {
    const raw = process.env.STEAM_APP_ID;
    if (raw && !/^[1-9]\d*$/.test(raw)) throw Error('Invalid STEAM_APP_ID');
    client = load().init(raw ? Number(raw) : undefined);
  } catch (failure) {
    error = failure.message;
    console.warn(`Steam unavailable: ${error}`);
  }
  return {
    status() {
      return {available: !!client, name: client?.localplayer.getName() || null,
        language: client?.apps.currentGameLanguage() || null, cloudPath,
        overlayActive: null, error};
    },
    event(id) {
      if (!manifest.some(item => item.event === id)) throw Error('Unknown Steam event');
      if (!client) return false;
      const item = manifest.find(entry => entry.event === id);
      return client.achievement.activate(item.api) && client.stats.store();
    },
    stat(name, value) {
      if (name !== 'dives_completed' || !Number.isSafeInteger(value) || value < 0) {
        throw Error('Invalid Steam statistic');
      }
      return !!client && client.stats.setInt(name, value) && client.stats.store();
    }
  };
}
module.exports = {createSteam};
