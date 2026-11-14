// Generate upload descriptors locally; identifiers never enter tracked templates.
const fs = require('node:fs');
const path = require('node:path');
function generate(env, directory) {
  for (const key of ['STEAM_APP_ID', 'STEAM_DEPOT_ID']) {
    if (!/^[1-9]\d*$/.test(env[key] || '')) throw Error(`Missing or invalid ${key}`);
  }
  fs.mkdirSync(directory, {recursive: true});
  for (const name of ['app_build', 'depot_build']) {
    const template = fs.readFileSync(path.join(__dirname, `${name}.vdf.example`), 'utf8');
    const output = template.replaceAll('REPLACE_WITH_APP_ID', env.STEAM_APP_ID)
      .replaceAll('REPLACE_WITH_DEPOT_ID', env.STEAM_DEPOT_ID);
    fs.writeFileSync(path.join(directory, `${name}.vdf`), output);
  }
}
if (require.main === module) generate(process.env, path.resolve(__dirname, '../out/steam'));
module.exports = {generate};
