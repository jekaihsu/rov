// Distinguish application shutdown from unexpected backend exits, including exit code zero.
function installBackendLifecycle(app, backend, reportFailure) {
  let stopping = false;
  let reported = false;
  function stop() {
    stopping = true;
  }
  function fail(reason) {
    if (stopping || reported) return;
    reported = true;
    return reportFailure(reason);
  }
  function watchWindow(window) {
    // 'closed' cannot be cancelled; 'close' can be cancelled by a renderer beforeunload handler.
    window.once('closed', stop);
  }
  app.on('before-quit', stop);
  app.on('window-all-closed', stop);
  backend.on('error', fail);
  backend.on('exit', function backendExited(code, signal) {
    fail(`Backend exit: ${code}, signal: ${signal}`);
  });
  return { fail, watchWindow };
}
module.exports = { installBackendLifecycle };
