// Link worker: holds the simulator socket off the page's thread so RC heartbeats keep their cadence while
// rendering stalls the page. All decisions live in rc_scheduler.js; this file only wires browser objects to it.
import { RC_TIMING, createRcWire } from "./rc_scheduler.js";

function emit(event, data) {
  self.postMessage({ event, data });
}
function openSocket(url) {
  return new WebSocket(url);
}
const wire = createRcWire({ openSocket, emit });

self.onmessage = function command(message) {
  const { op, url, text, holdMs } = message.data;
  if (op === "open") wire.open(url);
  else if (op === "send") wire.send(text, holdMs, performance.now());
  else if (op === "release") wire.release();
  else if (op === "ack") wire.acknowledge();
  else if (op === "close") wire.close();
};
setInterval(function heartbeat() {
  wire.tick(performance.now());
}, RC_TIMING.workerTickMs);
emit("ready");
