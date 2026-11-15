// Page-side inbox for the viewer WebSocket. Complete state snapshots coalesce to the newest one so a
// main thread stalled by software WebGL cannot queue every 30 Hz frame ahead of control replies
// (host_only, operation_result, session, …). Non-state messages flush any pending snapshot first and
// run immediately — the same ordering rule the RC worker already applies on its side.
//
// State is scheduled onto a macrotask (not only rAF): background tabs throttle animation frames, but
// still need room/host updates. Call flush() from the animation loop so a visible page stays current.

export function createLinkInbox(handlers) {
  let latestState = null;
  let scheduled = false;
  let timer = null;

  function flushState() {
    if (timer !== null) {
      clearTimeout(timer);
      timer = null;
    }
    scheduled = false;
    const message = latestState;
    latestState = null;
    if (message) handlers.onState(message);
  }

  function scheduleFlush() {
    if (scheduled) return;
    scheduled = true;
    timer = setTimeout(flushState, 0);
  }

  function receive(message) {
    if (message?.type === "state") {
      latestState = message;
      scheduleFlush();
      return;
    }
    flushState();
    if (message?.type === "world") handlers.onWorld?.(message);
    else if (message?.type === "session") handlers.onSession?.(message);
    else handlers.onOther?.(message);
  }

  function dispose() {
    if (timer !== null) clearTimeout(timer);
    timer = null;
    scheduled = false;
    latestState = null;
  }

  return { receive, flush: flushState, dispose };
}
