// Browser smoke fixture: reserve the first HTTP port, then allow a real Python backend to recover.
const { once } = require('node:events');
const net = require('node:net');
const readline = require('node:readline');
const { allocatePorts, startBackend } = require('../desktop/backend_start.cjs');

async function run() {
  const occupied = net.createServer(socket => socket.destroy());
  occupied.listen(0, '127.0.0.1');
  await once(occupied, 'listening');
  const first = occupied.address().port;
  let attempts = 0;
  let child;
  let ports;
  async function allocate() {
    if (ports) return ports;
    const fresh = await allocatePorts();
    if (++attempts === 1) fresh[0] = first;
    else ports = fresh;
    return fresh;
  }
  async function start() {
    const result = await startBackend({
      executable: process.argv[2], prefix: ['-m', 'qysim.server'], options: { cwd: process.argv[3] },
      allocate, onChild: proc => { child = proc; }, record: code => console.log(code),
    });
    console.log(JSON.stringify({ http: result.http, ws: result.ws, attempts }));
  }
  try {
    await start();
    for await (const command of readline.createInterface({ input: process.stdin })) {
      if (command === 'stop') {
        const closed = once(child, 'close');
        child.kill();
        await closed;
        console.log('stopped');
      } else if (command === 'start') await start();
    }
  } finally {
    child?.kill();
    occupied.close();
  }
}
run().catch(error => {
  console.error(error);
  process.exitCode = 1;
});
