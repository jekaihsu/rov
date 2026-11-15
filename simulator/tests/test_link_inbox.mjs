// Page-side link inbox: state snapshots coalesce; control replies stay ahead of a backlog.
import test from "node:test";
import assert from "node:assert/strict";
import { createLinkInbox } from "../viewer/input/link_inbox.js";

function collect() {
  const events = [];
  const inbox = createLinkInbox({
    onState: (m) => events.push(["state", m.t]),
    onWorld: (m) => events.push(["world", m.key]),
    onSession: (m) => events.push(["session", m.player_id]),
    onOther: (m) => events.push(["other", m.code || m.type]),
  });
  return { events, inbox };
}

test("a burst of state snapshots applies only the newest one", async () => {
  const { events, inbox } = collect();
  for (let t = 1; t <= 5; t += 1) inbox.receive({ type: "state", t });
  assert.deepEqual(events, []);
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(events, [["state", 5]]);
  inbox.dispose();
});

test("host_only flushes the pending snapshot then runs immediately", async () => {
  const { events, inbox } = collect();
  inbox.receive({ type: "state", t: 1 });
  inbox.receive({ type: "state", t: 2 });
  inbox.receive({ type: "error", code: "host_only" });
  inbox.receive({ type: "state", t: 3 });
  await new Promise((resolve) => setTimeout(resolve, 0));
  assert.deepEqual(events, [
    ["state", 2],
    ["other", "host_only"],
    ["state", 3],
  ]);
  inbox.dispose();
});

test("world and session keep order around coalesced state", () => {
  const { events, inbox } = collect();
  inbox.receive({ type: "state", t: 1 });
  inbox.receive({ type: "world", key: "reef" });
  inbox.receive({ type: "session", player_id: "p1" });
  assert.deepEqual(events, [
    ["state", 1],
    ["world", "reef"],
    ["session", "p1"],
  ]);
  inbox.dispose();
});

test("flush applies a pending snapshot without waiting for the timer", () => {
  const { events, inbox } = collect();
  inbox.receive({ type: "state", t: 9 });
  inbox.flush();
  assert.deepEqual(events, [["state", 9]]);
  inbox.dispose();
});
