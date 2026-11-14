// Ship runtime code and native Steamworks libraries, excluding release tooling.
const path = require('node:path');
function ignore(filename) {
  if (/^\/(backend|out)(\/|$)/.test(filename)) return true;
  if (/^\/steam\//.test(filename)) return filename !== '/steam/achievements.json';
  if (/^\/node_modules\//.test(filename)) {
    return !/^\/node_modules\/steamworks\.js(\/|$)/.test(filename);
  }
  return /\.py$/.test(filename) || /^\/(test_.*\.cjs|audit_.*\.cjs|vendor\.cjs|refresh_portable\.cjs)$/.test(filename) ||
    /\.(md|vdf|example)$/.test(filename);
}
module.exports = {
  packagerConfig: {
    asar: {unpack: '**/*.{node,dll,so,dylib}'},
    extraResource: [path.resolve(__dirname, 'backend')],
    ignore,
    executableName: 'ROV Simulator'
  },
  makers: [{name: '@electron-forge/maker-zip', platforms: ['win32']}]
};
