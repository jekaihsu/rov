// ROV-01 Simulator Steamworks Optional Bridge (Steam + Standalone B2B dual-mode)
// Attempts to initialize steamworks.js when running under the Steam Client, and falls back
// cleanly to an in-memory achievement/presence ledger when running standalone B2B.
const fs = require('fs');
const path = require('path');

const ACHIEVEMENTS = Object.freeze({
  M1_POOL_CLEAR: {
    id: 'M1_POOL_CLEAR',
    title: 'Pool Qualification Complete',
    desc: 'Complete Mission 1 6DoF Pool Qualification with all waypoints cleared.',
  },
  M2_UT_CERTIFIED: {
    id: 'M2_UT_CERTIFIED',
    title: 'UT NDT Level-II Certified',
    desc: 'Acquire valid <3 deg perpendicular Ultrasonic Thickness readings for 3.0s.',
  },
  M3_T3_FAULT_SURVIVOR: {
    id: 'M3_T3_FAULT_SURVIVOR',
    title: '5-Thruster Degraded Recovery',
    desc: 'Return ROV-01 safely to the recovery cage under T3 thruster loss and cross-current.',
  },
  M4_PIPE_GOLD: {
    id: 'M4_PIPE_GOLD',
    title: 'Subsea Pipeline Gold Inspector',
    desc: 'Complete Mission 4 Pipeline Trial with a score of 85 or higher and zero tether entanglement.',
  },
});

function readConfiguredAppId(baseDir = __dirname) {
  for (const fname of ['steam_app_id.txt', 'steam_appid.txt']) {
    const p = path.resolve(baseDir, fname);
    if (fs.existsSync(p)) {
      const raw = fs.readFileSync(p, 'utf8').trim().split(/\s+/)[0];
      const parsed = Number.parseInt(raw, 10);
      if (Number.isInteger(parsed) && parsed > 0) return parsed;
    }
  }
  return 480;
}

function createSteamBridge(options = {}) {
  const appId = options.appId || readConfiguredAppId(options.baseDir || __dirname);
  const unlocked = new Set();
  let richPresence = { status: 'In Hangar', mission: 'none', depth_m: '0.0' };
  let nativeClient = null;
  let mode = 'standalone-b2b';

  if (options.mockClient) {
    nativeClient = options.mockClient;
    mode = 'steam-mock';
  } else if (process.env.ROV01_DISABLE_STEAM !== '1') {
    try {
      // Optional native dependency: steamworks.js
      const steamworks = require('steamworks.js');
      nativeClient = steamworks.init(appId);
      mode = 'steam-native';
    } catch (_err) {
      nativeClient = null;
      mode = 'standalone-b2b';
    }
  }

  function unlockAchievement(achievementId) {
    if (!ACHIEVEMENTS[achievementId]) {
      return { ok: false, error: `Unknown achievement: ${achievementId}`, mode };
    }
    unlocked.add(achievementId);
    let steamActivated = false;
    if (nativeClient && nativeClient.achievement && typeof nativeClient.achievement.activate === 'function') {
      try {
        steamActivated = Boolean(nativeClient.achievement.activate(achievementId));
      } catch (_err) {
        steamActivated = false;
      }
    }
    return {
      ok: true,
      id: achievementId,
      mode,
      steamActivated,
      unlocked: Array.from(unlocked),
    };
  }

  function setRichPresence(keyOrMap, value) {
    const updates = typeof keyOrMap === 'object' && keyOrMap !== null ? keyOrMap : { [String(keyOrMap)]: String(value ?? '') };
    for (const [k, v] of Object.entries(updates)) {
      richPresence[k] = String(v);
      if (nativeClient && nativeClient.localplayer && typeof nativeClient.localplayer.setRichPresence === 'function') {
        try {
          nativeClient.localplayer.setRichPresence(k, String(v));
        } catch (_err) {
          // ignore native presence errors in offline/standalone mode
        }
      }
    }
    return { ok: true, mode, richPresence: { ...richPresence } };
  }

  function getStatus() {
    return {
      appId,
      mode,
      steamConnected: mode === 'steam-native' || mode === 'steam-mock',
      achievementsCatalogue: Object.keys(ACHIEVEMENTS),
      unlockedAchievements: Array.from(unlocked),
      richPresence: { ...richPresence },
    };
  }

  return {
    ACHIEVEMENTS,
    appId,
    unlockAchievement,
    setRichPresence,
    getStatus,
  };
}

module.exports = {
  ACHIEVEMENTS,
  readConfiguredAppId,
  createSteamBridge,
};
