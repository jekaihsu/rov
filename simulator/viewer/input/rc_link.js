// Page side of the RC link. `openRcLink` returns a WebSocket-shaped object whose socket lives in rc_worker.js,
// so heartbeats survive a page thread stalled by slow rendering; it falls back to a plain page socket when
// module workers are unavailable. `createRcPump` owns the send throttle that used to sit in app.js.
import { RC_TIMING, createSampleSchedule } from "./rc_scheduler.js";

function directLink(url) {
  const socket = new WebSocket(url);
  const link = { onopen: null, onmessage: null, onclose: null, onerror: null, worker: false };
  socket.onopen = function opened() {
    link.onopen?.();
  };
  socket.onmessage = function received(event) {
    link.onmessage?.(event);
  };
  socket.onclose = function closed() {
    link.onclose?.();
  };
  socket.onerror = function failed() {
    link.onerror?.();
  };
  link.send = function send(text) {
    socket.send(text);
  };
  link.release = function release() {};
  link.close = function close() {
    socket.close();
  };
  return link;
}

function workerLink(url) {
  const worker = new Worker(new URL("./rc_worker.js", import.meta.url), { type: "module" });
  const link = { onopen: null, onmessage: null, onclose: null, onerror: null, worker: true };
  let started = false;
  let fallback = null;
  function adopt(direct) {
    fallback = direct;
    link.worker = false;
    direct.onopen = function opened() {
      link.onopen?.();
    };
    direct.onmessage = function received(event) {
      link.onmessage?.(event);
    };
    direct.onclose = function closed() {
      link.onclose?.();
    };
    direct.onerror = function failed() {
      link.onerror?.();
    };
  }
  worker.onmessage = function report(message) {
    const { event, data } = message.data;
    started = true;
    if (event === "open") link.onopen?.();
    else if (event === "message") link.onmessage?.({ data });
    else if (event === "state") {
      try {
        link.onmessage?.({ data });
      } finally {
        worker.postMessage({ op: "ack" });
      }
    }
    else if (event === "error") link.onerror?.();
    else if (event === "close") {
      worker.terminate();
      link.onclose?.();
    }
  };
  worker.onerror = function broken(event) {
    event.preventDefault?.();
    worker.terminate();
    if (started) {
      // The socket died with the worker; report a normal close so the page reconnects.
      link.onclose?.();
      return;
    }
    try {
      adopt(directLink(url));
    } catch {
      link.onclose?.();
    }
  };
  link.send = function send(text, holdMs = 0) {
    if (fallback) fallback.send(text);
    else worker.postMessage({ op: "send", text, holdMs });
  };
  link.release = function release() {
    if (!fallback) worker.postMessage({ op: "release" });
  };
  link.close = function close() {
    if (fallback) {
      fallback.close();
      return;
    }
    try {
      worker.postMessage({ op: "close" });
    } catch {
      // Worker may already be gone.
    }
    // Ensure the worker cannot outlive a reconnect that opens a new link immediately.
    setTimeout(function terminateWorker() {
      try {
        worker.terminate();
      } catch {
        // ignore
      }
    }, 250);
  };
  worker.postMessage({ op: "open", url });
  return link;
}

// A replaced WebSocket constructor means the page (a test harness or tooling) wants to observe or drive the
// socket itself; a worker socket would bypass it, so stay on the page in that case.
function nativeSocket() {
  return Function.prototype.toString.call(WebSocket).includes("[native code]");
}

export function openRcLink(url) {
  // Validate on the page first so a malformed address still throws synchronously, as `new WebSocket` did.
  const parsed = new URL(url);
  if (!["ws:", "wss:"].includes(parsed.protocol)) throw new SyntaxError(`Unsupported socket address: ${url}`);
  if (typeof Worker === "undefined" || !nativeSocket()) return directLink(url);
  try {
    return workerLink(url);
  } catch {
    return directLink(url);
  }
}

// `transport()` returns the open link or null; `sequence()` returns the next page-side sequence number, used
// as-is by the fallback socket and renumbered by the worker.
export function createRcPump({ transport, sequence, timing = RC_TIMING, now = () => performance.now() }) {
  const schedule = createSampleSchedule(timing);
  function offer(rc, { live, generation }) {
    const text = JSON.stringify(rc);
    const at = now();
    const action = schedule.decide(text, at, live);
    const link = transport();
    if (action === "release") link?.release?.();
    if (action !== "send" || !link) return false;
    try {
      link.send(JSON.stringify({ type: "rc", rc, seq: sequence(), controller_generation: generation }), timing.holdMs);
    } catch {
      return false;
    }
    schedule.sent(text, at);
    return true;
  }
  function hidden() {
    // A hidden page must stop commanding at once; do not wait for its throttled timer to notice.
    if (document.hidden) transport()?.release?.();
  }
  function start(sample) {
    document.addEventListener("visibilitychange", hidden);
    return setInterval(sample, timing.sampleMs);
  }
  return { offer, reset: schedule.reset, start };
}
