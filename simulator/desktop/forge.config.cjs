// Package only the desktop runtime, production dependencies and native Steamworks libraries.
const path = require('node:path');
const runtimeFiles = new Set([
  '/main.cjs', '/preload.cjs', '/collection_store.cjs', '/backend_lifecycle.cjs', '/gpu_preference.cjs',
  '/steam_service.cjs', '/window_settings.cjs', '/package.json', '/steam', '/steam/achievements.json',
  '/THIRD_PARTY_NOTICES.txt'
]);
function ignore(file) {
  // Three.js is vendored into the backend viewer; only Steamworks is a Node runtime dependency.
  if (file === '' || file === '/node_modules') return false;
  if (file.startsWith('/node_modules/')) return !/^\/node_modules\/steamworks\.js(\/|$)/.test(file);
  return !runtimeFiles.has(file);
}
module.exports = {
  packagerConfig: {
    asar: { unpack: '**/*.{node,dll,so,dylib}' },
    extraResource: [path.resolve(__dirname, 'backend')],
    ignore,
    executableName: 'ROV Simulator'
  },
  makers: [{ name: '@electron-forge/maker-zip', platforms: ['win32'] }]
};
