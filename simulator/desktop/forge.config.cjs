// Package only the desktop runtime, production dependencies and native Steamworks libraries.
const fs = require('node:fs');
const path = require('node:path');
const { editionConfig } = require('./steam/edition.cjs');

const edition = editionConfig(process.env);
fs.writeFileSync(
  path.join(__dirname, 'steam', 'build_edition.json'),
  `${JSON.stringify({ edition: edition.id }, null, 2)}\n`,
);

const runtimeFiles = new Set([
  '/main.cjs',
  '/preload.cjs',
  '/collection_store.cjs',
  '/backend_lifecycle.cjs',
  '/gpu_preference.cjs',
  '/steam_service.cjs',
  '/window_settings.cjs',
  '/package.json',
  '/steam',
  '/steam/achievements.json',
  '/steam/cloud_paths.cjs',
  '/steam/edition.cjs',
  '/steam/build_edition.json',
]);

function ignore(file) {
  // Three.js is vendored into the backend viewer; only Steamworks is a Node runtime dependency.
  if (file === '' || file === '/node_modules') return false;
  if (file.startsWith('/node_modules/')) return !/^\/node_modules\/steamworks\.js(\/|$)/.test(file);
  if (file === '/steam' || file.startsWith('/steam/')) {
    return /RELEASE\.md|vdf\.example|TEMPLATE|generate_vdf|\.md$/.test(file);
  }
  return !runtimeFiles.has(file);
}

module.exports = {
  packagerConfig: {
    asar: { unpack: '**/*.{node,dll,so,dylib}' },
    extraResource: [path.resolve(__dirname, 'backend')],
    ignore,
    name: edition.productName,
    executableName: edition.executableName,
  },
  makers: [{ name: '@electron-forge/maker-zip', platforms: ['win32'] }],
};
