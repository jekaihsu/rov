// Persist only known event codes. Never serialize exceptions, URLs, device names or child output.
const fs = require('node:fs');
const path = require('node:path');
const codes = new Set(['backend', 'missing', 'denied', 'timeout', 'port', 'exception', 'renderer',
  'unresponsive', 'graphics', 'context', 'frontend', 'storage', 'offline', 'blocked']);

function makeDiagnostics(root) {
  const file = path.join(root, 'events.log');
  function record(code) {
    if (!codes.has(code)) return;
    try {
      fs.mkdirSync(root, { recursive: true });
      const entry = new Date().toISOString() + ' ' + code + '\n';
      if (fs.existsSync(file) && fs.statSync(file).size + entry.length > 65536) {
        fs.renameSync(file, file + '.1');
      }
      fs.appendFileSync(file, entry);
    } catch {
      // A full or read-only disk must still allow the recovery dialog.
    }
  }
  return record;
}

module.exports = { makeDiagnostics };
