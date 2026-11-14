// Distinguish deliberate desktop shutdown from unexpected backend termination.
function watchBackend(app, window, backend, reportFailure) {
  let stopping = false;
  let reported = false;
  function stop() {
    stopping = true;
  }
  function failed(reason) {
    if (stopping || reported) return;
    reported = true;
    reportFailure(reason);
  }
  app.on('before-quit', stop);
  window.on('closed', stop);
  backend.on('error', failed);
  backend.on('exit', (code, signal) => failed(`Backend exit: ${code}, signal: ${signal}`));
}
module.exports = {watchBackend};
