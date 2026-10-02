const path=require('node:path');
module.exports={
  packagerConfig:{asar:true,extraResource:[path.resolve(__dirname,'backend')],
    ignore:[/^\/backend(?:\/|$)/,/^\/out(?:\/|$)/,/^\/node_modules(?:\/|$)/,/^\/steam(?:\/|$)/,/\.py$/,/vendor\.cjs$/],
    executableName:'ROV Simulator'},
  makers:[{name:'@electron-forge/maker-zip',platforms:['win32']}]
};
