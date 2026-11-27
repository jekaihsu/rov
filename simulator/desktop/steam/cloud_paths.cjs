// Steam Auto-Cloud / local save folder layout for the desktop shell.
// TODO(S3): when task/S3-stability-saves lands, point ROOT_REL and INCLUDE at the versioned save folder
// documented in docs/design/saves.md and keep Auto-Cloud in sync (see docs/store/steam/cloud.md).

const path = require('node:path');

// Subdirectory of Electron userData that Steam Auto-Cloud should mirror.
const ROOT_REL = '.';
const INCLUDE = Object.freeze([
  'preferences.json',
  'window.json',
  'collection/**',
  // TODO(S3): career/progress save files once the desktop file store exists.
  'steam-mock/**',
]);
const EXCLUDE = Object.freeze([
  'backend.log',
  'numba-cache/**',
  'local-backups/**',
  'reports/**',
]);

// Suggested Steamworks Auto-Cloud quotas (photos dominate). Not enforced in-process.
const QUOTA = Object.freeze({
  bytesPerUser: 1 * 1024 * 1024 * 1024,
  filesPerUser: 10000,
});

function cloudPaths(userData) {
  const root = path.resolve(userData);
  return {
    root,
    rootRel: ROOT_REL,
    include: INCLUDE.slice(),
    exclude: EXCLUDE.slice(),
    quota: { ...QUOTA },
    // Absolute paths for the developer page / tests.
    preferences: path.join(root, 'preferences.json'),
    window: path.join(root, 'window.json'),
    collection: path.join(root, 'collection'),
    mockState: path.join(root, 'steam-mock', 'state.json'),
  };
}

module.exports = { ROOT_REL, INCLUDE, EXCLUDE, QUOTA, cloudPaths };
