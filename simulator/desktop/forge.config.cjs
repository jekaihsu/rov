// Package native Steamworks libraries alongside the portable backend.
const path=require('node:path');
module.exports={
  packagerConfig:{asar:{unpack:"**/*.{node,dll,so,dylib}"},extraResource:[path.resolve(__dirname,'backend')],
    ignore:[/^\/backend(?:\/|$)/,/^\/out(?:\/|$)/,/\.py$/,/vendor\.cjs$/],
    executableName:'ROV Simulator'},
  makers:[{name:'@electron-forge/maker-zip',platforms:['win32']}]
};
