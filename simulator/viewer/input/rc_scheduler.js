// RC send scheduling, free of browser globals so it runs in the page, in the link worker and under node tests.
// The page samples controls on its own timer and forwards a packet when it changes or the renew period passes.
// The link worker owns the socket and repeats the last held packet while the page's thread is stalled by slow
// rendering, but only for a bounded hold time so a frozen page still lets the server failsafe engage.
import { coalesceStateText } from "../state_merge.js";

export const RC_TIMING = Object.freeze({
  sampleMs: 33, // control sampling period on the page timer (30 Hz while input changes)
  renewMs: 100, // unchanged input is forwarded again this often, renewing the worker hold
  heartbeatMs: 150, // longest allowed silence on the wire while a hold is valid
  holdMs: 2000, // how long the worker may repeat a packet without hearing from the page
  workerTickMs: 25, // worker heartbeat check period
});

// Page side: decides whether the freshly sampled packet should be forwarded now.
export function createSampleSchedule(timing = RC_TIMING) {
  let lastText = "";
  let lastAt = -Infinity;
  let holding = false;
  function decide(text, now, live) {
    if (!live) {
      const action = holding ? "release" : "skip";
      holding = false;
      return action;
    }
    if (text !== lastText) return "send";
    if (now - lastAt >= timing.renewMs) return "send";
    return "skip";
  }
  function sent(text, now) {
    lastText = text;
    lastAt = now;
    holding = true;
  }
  function reset() {
    lastText = "";
    lastAt = -Infinity;
    holding = false;
  }
  return { decide, sent, reset };
}

// Worker side: tracks the held packet's validity and when the wire has been silent for too long.
export function createHoldSchedule(timing = RC_TIMING) {
  let heldUntil = -Infinity;
  let lastWireAt = -Infinity;
  function hold(now, holdMs = timing.holdMs) {
    heldUntil = now + Math.min(holdMs, timing.holdMs);
    lastWireAt = now;
  }
  function release() {
    heldUntil = -Infinity;
  }
  function repeated(now) {
    lastWireAt = now;
  }
  function due(now) {
    if (now >= heldUntil) return false;
    // The worker checks every workerTickMs, so fire one check early to keep wire silence within heartbeatMs.
    return now - lastWireAt >= timing.heartbeatMs - timing.workerTickMs;
  }
  function active(now) {
    return now < heldUntil;
  }
  return { hold, release, repeated, due, active };
}

// Worker side: RC sequence numbers must rise strictly on one socket, whoever originated the packet.
export function createSequence() {
  let value = 0;
  function next() {
    value += 1;
    return value;
  }
  function reset() {
    value = 0;
  }
  return { next, reset };
}

// A page that cannot keep up only needs the newest snapshot. Snapshots marked delta:true (static_once)
// omit unchanged fields, so a skipped one is folded into its successor instead of being dropped.
const STATE_PREFIX = /^\s*\{\s*"type"\s*:\s*"state"/;
export function isStateText(text) {
  return typeof text === "string" && STATE_PREFIX.test(text);
}

// Worker side: owns the socket. `openSocket(url)` returns a WebSocket-like object and `emit(event, data)` reports
// to the page. Every RC packet gets its sequence number here because both page packets and repeats share the wire.
// Incoming state snapshots are emitted as "state" one at a time: the next goes out only after the page calls
// `acknowledge()`, and snapshots that arrive meanwhile are coalesced into one (complete ones replace).
// Without this a stalled page would queue every snapshot and fall ever further behind, because the worker
// removes the socket's own back-pressure.
// Any other message flushes the waiting snapshot first, so the page still sees everything in server order.
export function createRcWire({ openSocket, emit, timing = RC_TIMING }) {
  const schedule = createHoldSchedule(timing);
  const sequence = createSequence();
  let socket = null;
  let ready = false;
  let held = null;
  let awaiting = false;
  let waiting = null;
  function deliver(text) {
    if (!isStateText(text)) {
      if (waiting !== null) emit("message", waiting);
      waiting = null;
      emit("message", text);
      return;
    }
    if (awaiting) {
      waiting = coalesceStateText(waiting, text);
      return;
    }
    awaiting = true;
    emit("state", text);
  }
  function acknowledge() {
    awaiting = false;
    if (waiting === null) return;
    const text = waiting;
    waiting = null;
    awaiting = true;
    emit("state", text);
  }
  function drop() {
    held = null;
    schedule.release();
  }
  function open(url) {
    sequence.reset();
    drop();
    ready = false;
    awaiting = false;
    waiting = null;
    socket = openSocket(url);
    socket.onopen = function opened() {
      ready = true;
      emit("open");
    };
    socket.onmessage = function received(event) {
      deliver(event.data);
    };
    socket.onerror = function failed() {
      emit("error");
    };
    socket.onclose = function closed() {
      ready = false;
      drop();
      waiting = null;
      emit("close");
    };
  }
  function parse(text) {
    try {
      return JSON.parse(text);
    } catch {
      return null;
    }
  }
  function send(text, holdMs, now) {
    if (!socket || !ready) return;
    const packet = parse(text);
    if (packet?.type !== "rc") {
      socket.send(text);
      return;
    }
    packet.seq = sequence.next();
    socket.send(JSON.stringify(packet));
    if (holdMs > 0) {
      held = packet;
      schedule.hold(now, holdMs);
    } else drop();
  }
  function tick(now) {
    if (!socket || !ready || !held) return false;
    if (!schedule.active(now)) {
      drop();
      return false;
    }
    if (!schedule.due(now)) return false;
    held.seq = sequence.next();
    socket.send(JSON.stringify(held));
    schedule.repeated(now);
    return true;
  }
  function close() {
    drop();
    socket?.close();
  }
  return { open, send, release: drop, tick, close, acknowledge };
}
