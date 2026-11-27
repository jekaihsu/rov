// Thin test helper around steam_service. Production code uses steam_service.cjs directly.
const { createSteam: createService } = require('./steam_service.cjs');

function createSteam(cloudPath, load) {
  const steam = createService(cloudPath, {
    loadSteam: typeof load === 'function' ? load : (() => require('steamworks.js')),
    env: process.env,
    logger: { warn() {} },
  });
  return {
    status() {
      const value = steam.status();
      return {
        available: value.available,
        name: value.player,
        language: value.language,
        cloudPath: value.cloudPath,
        overlayActive: value.overlayActive,
        error: value.error,
        backend: value.backend,
        edition: value.edition,
      };
    },
    event(id) {
      return steam.report(id, 1);
    },
    report: steam.report,
    setPresence: steam.setPresence,
    readMock: steam.readMock,
  };
}

module.exports = { createSteam };
