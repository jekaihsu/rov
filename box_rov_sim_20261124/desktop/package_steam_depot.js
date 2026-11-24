#!/usr/bin/env node
// Stages a SteamPipe-ready depot directory under desktop/dist/steam_depot_win64
// and validates VDF + Steam Input manifest files for steamcmd upload.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { readConfiguredAppId, ACHIEVEMENTS } = require('./steam_bridge');

const DESKTOP_DIR = __dirname;
const ROOT_DIR = fs.existsSync(path.resolve(DESKTOP_DIR, '..', 'box_run', 'viewer'))
  ? path.resolve(DESKTOP_DIR, '..')
  : path.resolve(DESKTOP_DIR, '..', '..');
const BOX_RUN_DIR = fs.existsSync(path.resolve(DESKTOP_DIR, '..', 'viewer'))
  ? path.resolve(DESKTOP_DIR, '..')
  : path.resolve(ROOT_DIR, 'box_run');
const OUT_DIR = path.resolve(DESKTOP_DIR, 'dist', 'steam_depot_win64');
const PIPE_OUT_DIR = path.resolve(DESKTOP_DIR, 'dist', 'steam_pipe_output');

function copyRecursive(src, dest) {
  if (!fs.existsSync(src)) return 0;
  const stat = fs.statSync(src);
  if (stat.isDirectory()) {
    const base = path.basename(src);
    if (['__pycache__', '.pytest_cache', 'node_modules', '.git'].includes(base)) return 0;
    fs.mkdirSync(dest, { recursive: true });
    let count = 0;
    for (const entry of fs.readdirSync(src)) {
      count += copyRecursive(path.join(src, entry), path.join(dest, entry));
    }
    return count;
  }
  if (/\.py[co]$/.test(src) || path.basename(src) === 'sdk_vendor_adapter.py') return 0;
  fs.mkdirSync(path.dirname(dest), { recursive: true });
  fs.copyFileSync(src, dest);
  return 1;
}

function main() {
  // This is generated output. A rebuild must not retain deleted source files,
  // cached Python bytecode or payloads from a previous release.
  fs.rmSync(OUT_DIR, { recursive: true, force: true });
  fs.mkdirSync(OUT_DIR, { recursive: true });
  fs.mkdirSync(PIPE_OUT_DIR, { recursive: true });

  const viewerFiles = copyRecursive(path.join(BOX_RUN_DIR, 'viewer'), path.join(OUT_DIR, 'viewer'));
  const simFiles = copyRecursive(path.join(BOX_RUN_DIR, 'rov01sim'), path.join(OUT_DIR, 'rov01sim'));
  // Exclude compatibility vendor adapter in official Steam release depot
  const vendorAdapter = path.join(OUT_DIR, 'rov01sim', 'sdk_vendor_adapter.py');
  if (fs.existsSync(vendorAdapter)) fs.unlinkSync(vendorAdapter);

  for (const f of ['main.js', 'steam_bridge.js', 'package.json']) {
    fs.copyFileSync(path.join(DESKTOP_DIR, f), path.join(OUT_DIR, f));
  }
  copyRecursive(path.join(DESKTOP_DIR, 'steamworks_config'), path.join(OUT_DIR, 'steamworks_config'));

  // Stage the AppID beside the executable. steamworks.js (and our own
  // readConfiguredAppId fallback) reads a file named `steam_appid.txt` at
  // runtime to initialise outside the Steam client; without it a shipped
  // build silently falls back to the Spacewar placeholder (480). Valve's
  // depot VDF still FileExcludes it from the UPLOADED depot, but the staged
  // content root must contain it so dev/standalone launches resolve the real
  // AppID. Both canonical filenames are written for compatibility.
  const stagedAppId = readConfiguredAppId(DESKTOP_DIR);
  for (const f of ['steam_appid.txt', 'steam_app_id.txt']) {
    fs.writeFileSync(path.join(OUT_DIR, f), `${stagedAppId}\n`, 'utf8');
  }

  // Fail loudly if the VDF upload scripts referenced by the manifest are
  // missing — a broken content root must not stage as "ready to upload".
  for (const vdf of ['app_build_template.vdf', 'depot_build_win64.vdf', 'steam_input_manifest.vdf']) {
    const p = path.join(OUT_DIR, 'steamworks_config', vdf);
    if (!fs.existsSync(p)) {
      throw new Error(`Steam depot staging incomplete: missing VDF ${vdf}`);
    }
  }

  function inventory(dir, prefix = '') {
    return fs.readdirSync(dir).sort().flatMap(name => {
      const file = path.join(dir, name);
      const relative = prefix + name;
      if (fs.statSync(file).isDirectory()) return inventory(file, relative + '/');
      const data = fs.readFileSync(file);
      return [{ path: relative, bytes: data.length,
        sha256: crypto.createHash('sha256').update(data).digest('hex') }];
    });
  }
  const manifest = {
    productName: 'ROV-01 Simulator',
    appId: readConfiguredAppId(DESKTOP_DIR),
    depotDir: OUT_DIR,
    viewerFiles,
    simFiles,
    achievements: Object.keys(ACHIEVEMENTS),
    vendorAdapterRemoved: !fs.existsSync(vendorAdapter),
    payloadFiles: inventory(OUT_DIR),
    vdfScripts: [
      'steamworks_config/app_build_template.vdf',
      'steamworks_config/depot_build_win64.vdf',
      'steamworks_config/steam_input_manifest.vdf',
    ],
  };
  fs.writeFileSync(path.join(OUT_DIR, 'steam_build_manifest.json'), JSON.stringify(manifest, null, 2));
  console.log(JSON.stringify(manifest));
}

if (require.main === module) {
  main();
}
module.exports = { main };
