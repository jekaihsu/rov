// RC heartbeat scheduling regressions on a fake clock: page-side throttle, worker-side hold and sequence ownership.
import test from "node:test";
import assert from "node:assert/strict";
import {
  RC_TIMING,
  createSampleSchedule,
  createHoldSchedule,
  createRcWire,
  isStateText,
} from "../viewer/input/rc_scheduler.js";

function fakeSocket() {
  const socket = { sent: [], closed: false };
  socket.send = function send(text) {
    socket.sent.push(JSON.parse(text));
  };
  socket.close = function close() {
    socket.closed = true;
    socket.onclose?.();
  };
  return socket;
}
function openWire() {
  const socket = fakeSocket();
  const events = [];
  const wire = createRcWire({
    openSocket: () => socket,
    emit: (event, data) => events.push([event, data]),
  });
  wire.open("ws://example.invalid");
  socket.onopen();
  return { wire, socket, events };
}
function rc(lock, seq = 99) {
  return JSON.stringify({ type: "rc", rc: { right_ud: 1800, rc_lock: lock }, seq });
}
// Advance the worker timer the way setInterval would, returning the times at which a repeat went out.
function runTicks(wire, from, to) {
  const repeats = [];
  for (let now = from; now <= to; now += RC_TIMING.workerTickMs) {
    if (wire.tick(now)) repeats.push(now);
  }
  return repeats;
}

test("timing meets the protocol: 30 Hz sampling and a heartbeat no slower than 150 ms", () => {
  assert.ok(RC_TIMING.sampleMs <= 34);
  assert.ok(RC_TIMING.heartbeatMs <= 150);
  assert.ok(RC_TIMING.renewMs < RC_TIMING.heartbeatMs);
  assert.ok(RC_TIMING.holdMs > RC_TIMING.heartbeatMs);
});

test("page schedule sends changes at once and renews unchanged input", () => {
  const schedule = createSampleSchedule();
  assert.equal(schedule.decide("a", 0, true), "send");
  schedule.sent("a", 0);
  assert.equal(schedule.decide("a", 33, true), "skip");
  assert.equal(schedule.decide("b", 33, true), "send");
  schedule.sent("b", 33);
  assert.equal(schedule.decide("b", 33 + RC_TIMING.renewMs - 1, true), "skip");
  assert.equal(schedule.decide("b", 33 + RC_TIMING.renewMs, true), "send");
});

test("page schedule releases the hold once when input stops being live", () => {
  const schedule = createSampleSchedule();
  assert.equal(schedule.decide("a", 0, false), "skip");
  schedule.sent("a", 0);
  assert.equal(schedule.decide("a", 33, false), "release");
  assert.equal(schedule.decide("a", 66, false), "skip");
  assert.equal(schedule.decide("a", 99, true), "skip");
  schedule.reset();
  assert.equal(schedule.decide("a", 100, true), "send");
});

test("an unsent packet is offered again", () => {
  const schedule = createSampleSchedule();
  assert.equal(schedule.decide("a", 0, true), "send");
  assert.equal(schedule.decide("a", 33, true), "send");
});

test("hold schedule is silent without a hold and after it expires", () => {
  const schedule = createHoldSchedule();
  assert.equal(schedule.due(1000), false);
  schedule.hold(0);
  assert.equal(schedule.due(50), false);
  assert.equal(schedule.due(RC_TIMING.heartbeatMs), true);
  assert.equal(schedule.active(RC_TIMING.holdMs - 1), true);
  assert.equal(schedule.due(RC_TIMING.holdMs), false);
  schedule.hold(0, RC_TIMING.holdMs * 10);
  assert.equal(schedule.active(RC_TIMING.holdMs), false);
});

test("worker repeats a held packet within 150 ms while the page is stalled", () => {
  const { wire, socket } = openWire();
  wire.send(rc(0), RC_TIMING.holdMs, 0);
  const repeats = runTicks(wire, RC_TIMING.workerTickMs, 1200);
  const times = [0, ...repeats];
  for (let i = 1; i < times.length; i += 1) assert.ok(times[i] - times[i - 1] <= 150, `gap ${times[i] - times[i - 1]}`);
  assert.ok(repeats.length >= 8);
  assert.deepEqual(socket.sent.at(-1).rc, { right_ud: 1800, rc_lock: 0 });
});

test("worker stops repeating when the page stays silent past the hold, so the server failsafe can engage", () => {
  const { wire, socket } = openWire();
  wire.send(rc(0), RC_TIMING.holdMs, 0);
  runTicks(wire, RC_TIMING.workerTickMs, RC_TIMING.holdMs + 2000);
  const count = socket.sent.length;
  assert.equal(runTicks(wire, RC_TIMING.holdMs + 2025, RC_TIMING.holdMs + 5000).length, 0);
  assert.equal(socket.sent.length, count);
});

test("worker does not repeat while the page keeps sending", () => {
  const { wire, socket } = openWire();
  for (let now = 0; now <= 1000; now += 25) {
    if (now % 100 === 0) wire.send(rc(0), RC_TIMING.holdMs, now);
    else assert.equal(wire.tick(now), false);
  }
  assert.equal(socket.sent.length, 11);
});

test("sequence numbers rise strictly across page packets and repeats and restart per socket", () => {
  const { wire, socket } = openWire();
  wire.send(rc(1, 7), RC_TIMING.holdMs, 0);
  runTicks(wire, 25, 400);
  wire.send(rc(0, 8), RC_TIMING.holdMs, 410);
  runTicks(wire, 425, 800);
  const sequence = socket.sent.map((packet) => packet.seq);
  assert.equal(sequence[0], 1);
  for (let i = 1; i < sequence.length; i += 1) assert.equal(sequence[i], sequence[i - 1] + 1);
  const next = fakeSocket();
  const rewire = createRcWire({ openSocket: () => next, emit: () => {} });
  rewire.open("ws://example.invalid");
  next.onopen();
  rewire.send(rc(1, 500), 0, 0);
  assert.equal(next.sent[0].seq, 1);
});

test("an explicit RC packet without a hold, a release, or a close ends the repeats", () => {
  for (const stop of ["packet", "release", "close"]) {
    const { wire, socket } = openWire();
    wire.send(rc(0), RC_TIMING.holdMs, 0);
    if (stop === "packet") wire.send(rc(1), 0, 10);
    else if (stop === "release") wire.release();
    else wire.close();
    const count = socket.sent.length;
    assert.equal(runTicks(wire, 25, 1500).length, 0, stop);
    assert.equal(socket.sent.length, count, stop);
    if (stop === "packet") assert.equal(socket.sent.at(-1).rc.rc_lock, 1);
  }
});

test("other messages pass through untouched and nothing is sent before the socket opens", () => {
  const socket = fakeSocket();
  const events = [];
  const wire = createRcWire({ openSocket: () => socket, emit: (event, data) => events.push([event, data]) });
  wire.open("ws://example.invalid");
  wire.send(rc(0), RC_TIMING.holdMs, 0);
  assert.equal(socket.sent.length, 0);
  assert.equal(runTicks(wire, 25, 500).length, 0);
  socket.onopen();
  wire.send(JSON.stringify({ type: "join", room_id: "training" }), 0, 0);
  assert.deepEqual(socket.sent, [{ type: "join", room_id: "training" }]);
  socket.onmessage({ data: "{}" });
  assert.deepEqual(events, [["open", undefined], ["message", "{}"]]);
});

test("state snapshots are recognised by their leading type field only", () => {
  assert.equal(isStateText('{"type":"state","t":1}'), true);
  assert.equal(isStateText('{ "type": "state", "t": 1 }'), true);
  assert.equal(isStateText('{"type":"world","note":"\\"type\\":\\"state\\""}'), false);
  assert.equal(isStateText('{"t":1,"type":"state"}'), false);
  assert.equal(isStateText(new ArrayBuffer(4)), false);
});

test("a stalled page receives only the newest state snapshot, one at a time", () => {
  const { wire, socket, events } = openWire();
  events.length = 0;
  for (let t = 1; t <= 5; t += 1) socket.onmessage({ data: `{"type":"state","t":${t}}` });
  assert.deepEqual(events, [["state", '{"type":"state","t":1}']]);
  wire.acknowledge();
  assert.deepEqual(events.at(-1), ["state", '{"type":"state","t":5}']);
  assert.equal(events.length, 2);
  wire.acknowledge();
  assert.equal(events.length, 2);
  socket.onmessage({ data: '{"type":"state","t":6}' });
  assert.deepEqual(events.at(-1), ["state", '{"type":"state","t":6}']);
});

test("other messages are never dropped and keep server order around a waiting snapshot", () => {
  const { wire, socket, events } = openWire();
  events.length = 0;
  socket.onmessage({ data: '{"type":"state","t":1}' });
  socket.onmessage({ data: '{"type":"state","t":2}' });
  socket.onmessage({ data: '{"type":"world","key":"reef"}' });
  socket.onmessage({ data: '{"type":"operation_result","ok":true}' });
  socket.onmessage({ data: '{"type":"state","t":3}' });
  assert.deepEqual(events, [
    ["state", '{"type":"state","t":1}'],
    ["message", '{"type":"state","t":2}'],
    ["message", '{"type":"world","key":"reef"}'],
    ["message", '{"type":"operation_result","ok":true}'],
  ]);
  wire.acknowledge();
  assert.deepEqual(events.at(-1), ["state", '{"type":"state","t":3}']);
});

test("a stalled page keeps the fields of skipped delta snapshots", () => {
  const { wire, socket, events } = openWire();
  events.length = 0;
  socket.onmessage({ data: '{"type":"state","t":1,"locked":false,"vehicle":{"id":"x1"}}' });
  socket.onmessage({ data: '{"type":"state","t":2,"locked":true,"control_generation":2,"delta":true}' });
  socket.onmessage({ data: '{"type":"state","t":3,"delta":true}' });
  wire.acknowledge();
  assert.equal(events.length, 2);
  assert.deepEqual(JSON.parse(events[1][1]), {
    type: "state", t: 3, locked: true, control_generation: 2, delta: true,
  });
  socket.onmessage({ data: '{"type":"state","t":4,"delta":true}' });
  socket.onmessage({ data: '{"type":"state","t":5,"locked":false}' });
  wire.acknowledge();
  assert.deepEqual(events.at(-1), ["state", '{"type":"state","t":5,"locked":false}']);
});
