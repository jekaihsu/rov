// Generate Steam upload descriptors without storing account-specific IDs in source.
const fs = require('node:fs');
const path = require('node:path');
function generate(env, directory) {
  for (const name of ['STEAM_APP_ID', 'STEAM_DEPOT_ID']) {
    if (!/^[1-9][0-9]*$/.test(env[name] || '')) throw Error(`Missing or invalid ${name}`);
  }
  fs.mkdirSync(directory, { recursive: true });
  for (const name of ['app_build', 'depot_build']) {
    const template = fs.readFileSync(path.join(__dirname, name + '.vdf.example'), 'utf8');
    const value = template.replaceAll('REPLACE_WITH_APP_ID', env.STEAM_APP_ID)
      .replaceAll('REPLACE_WITH_DEPOT_ID', env.STEAM_DEPOT_ID);
    fs.writeFileSync(path.join(directory, name + '.vdf'), value);
  }
}
if (require.main === module) generate(process.env, process.argv[2] || __dirname);
module.exports = { generate };
