// Start all three listeners as one attempt. Python announces readiness only after the last bind.
const net = require('node:net');
const { spawn } = require('node:child_process');

function freePort() {
  return new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once('error', reject);
    server.listen(0, '127.0.0.1', () => {
      const port = server.address().port;
      server.close(() => resolve(port));
    });
  });
}

async function allocatePorts() {
  const ports = new Set();
  while (ports.size < 3) ports.add(await freePort());
  return [...ports];
}

async function attemptBackend({ executable, prefix, options, onChild, record }, [http, ws, rpc]) {
  const child = spawn(executable, [...prefix, '--host', '127.0.0.1', '--http-port', String(http),
    '--ws-port', String(ws), '--rpc-port', String(rpc)], options);
  onChild(child);
  let reason = 'backend';
  const closed = new Promise(resolve => child.once('close', resolve));
  let timer;
  try {
    await new Promise((resolve, reject) => {
      const fail = () => reject(new Error(reason));
      timer = setTimeout(() => {
        reason = 'timeout';
        fail();
      }, 60000);
      child.once('error', error => {
        reason = error.code === 'ENOENT' ? 'missing' : 'backend';
        fail();
      });
      child.once('close', fail);
      let output = '';
      child.stdout.on('data', chunk => {
        output = (output + chunk).slice(-4096);
        if (output.includes('http://127.0.0.1:' + http + '/')) resolve();
      });
      let tail = '';
      child.stderr.on('data', chunk => {
        const message = tail + chunk;
        tail = message.slice(-128);
        if (/EADDRINUSE|Errno (48|98)|WinError 10048|address already in use/i.test(message)) reason = 'port';
        if (/PermissionError|WinError 10013/i.test(message)) reason = 'denied';
        if (/ModuleNotFoundError/.test(message)) reason = 'missing';
        if (/Traceback \(most recent call last\)/.test(message)) record('exception');
      });
    });
    try {
      const response = await fetch('http://127.0.0.1:' + http + '/', {
        method: 'HEAD', signal: AbortSignal.timeout(3500),
      });
      if (!response.ok) throw Error();
    } catch {
      throw Error('timeout');
    }
    if (child.exitCode !== null || child.signalCode !== null) throw Error('backend');
    return { http, ws, child };
  } catch (error) {
    child.kill();
    const forceExit = setTimeout(() => child.kill('SIGKILL'), 1500);
    try {
      await closed;
    } finally {
      clearTimeout(forceExit);
    }
    throw error;
  } finally {
    clearTimeout(timer);
  }
}

async function startBackend(config) {
  const { record, onRetry = () => {}, allocate = allocatePorts } = config;
  for (let attempt = 1; attempt <= 3; attempt++) {
    try {
      return await attemptBackend(config, await allocate());
    } catch (error) {
      let reason = error.message;
      if (error.code === 'EACCES') reason = 'denied';
      if (error.code === 'EADDRINUSE') reason = 'port';
      record(reason);
      if (attempt === 3 || !['port', 'denied', 'timeout'].includes(reason)) throw Error(reason);
      await onRetry(reason, attempt + 1);
    }
  }
}

module.exports = { startBackend, allocatePorts };
