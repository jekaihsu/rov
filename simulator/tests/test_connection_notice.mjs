// The connection notice only appears after a real timeout, never while a dive is starting or a blip is retried.
import test from "node:test";
import assert from "node:assert/strict";
import {
  LOST_TIMEOUT_MS,
  STARTUP_TIMEOUT_MS,
  installConnectionNotice,
} from "../viewer/play/connection_notice.js";

function fakeTimers() {
  let now = 0;
  const pending = new Map();
  let next = 1;
  return {
    setTimer(callback, ms) {
      pending.set(next, { at: now + ms, callback });
      return next++;
    },
    clearTimer(id) {
      pending.delete(id);
    },
    advance(ms) {
      now += ms;
      for (const [id, timer] of [...pending]) {
        if (timer.at <= now) {
          pending.delete(id);
          timer.callback();
        }
      }
    },
  };
}

function notice() {
  const timers = fakeTimers();
  const element = { hidden: false, querySelector: () => null };
  const api = installConnectionNotice({ element, ...timers });
  return { element, api, timers };
}

test("the notice stays hidden through start-up and shows after the start-up timeout", () => {
  const { element, timers } = notice();
  assert.equal(element.hidden, true, "hidden from the first frame");
  timers.advance(STARTUP_TIMEOUT_MS - 1);
  assert.equal(element.hidden, true);
  timers.advance(1);
  assert.equal(element.hidden, false);
});

test("a short drop after connecting does not flash the notice", () => {
  const { element, api, timers } = notice();
  api.connected();
  api.lost();
  timers.advance(LOST_TIMEOUT_MS - 100);
  api.connected();
  timers.advance(10 * LOST_TIMEOUT_MS);
  assert.equal(element.hidden, true);
  api.lost();
  api.lost();
  timers.advance(LOST_TIMEOUT_MS);
  assert.equal(element.hidden, false, "a lasting drop shows it");
  api.connected();
  assert.equal(element.hidden, true);
});
