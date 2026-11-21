// Resolves the desktop build edition: Steam player build vs internal training build.
// Packaged apps read steam/build_edition.json (written by forge.config when ROV_BUILD_EDITION=steam).
const fs = require('node:fs');
const path = require('node:path');

const EDITIONS = Object.freeze({
  internal: {
    id: 'internal',
    productName: 'ROV Simulator',
    executableName: 'ROV Simulator',
    showAchievements: false,
  },
  steam: {
    id: 'steam',
    productName: 'ROV Solution',
    executableName: 'ROV Solution',
    showAchievements: true,
  },
});

function readBakedEdition() {
  try {
    const file = path.join(__dirname, 'build_edition.json');
    const baked = JSON.parse(fs.readFileSync(file, 'utf8'));
    if (baked?.edition === 'steam') return 'steam';
  } catch {
    // Missing bake file means a source checkout or an older package.
  }
  return null;
}

function resolveEdition(env = process.env) {
  if (env.ROV_BUILD_EDITION === 'steam') return 'steam';
  if (env.ROV_BUILD_EDITION === 'internal') return 'internal';
  return readBakedEdition() || 'internal';
}

function editionConfig(env = process.env) {
  return EDITIONS[resolveEdition(env)];
}

module.exports = { EDITIONS, resolveEdition, editionConfig };
