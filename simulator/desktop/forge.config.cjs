// Package only the desktop runtime, production dependencies and native Steamworks libraries.
const path = require('node:path');
const runtimeFiles = new Set([
  '/main.cjs', '/preload.cjs', '/collection_store.cjs', '/backend_lifecycle.cjs',
  '/steam_service.cjs', '/window_settings.cjs', '/package.json', '/steam', '/steam/achievements.json'
]);
function ignore(file) {
  // Keep dependency licenses and native libraries; Electron Packager prunes devDependencies.
  if (file === '' || file === '/node_modules' || file.startsWith('/node_modules/')) return false;
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
