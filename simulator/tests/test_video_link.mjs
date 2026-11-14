// Simulated vehicle link presentation: lag added to the video delay, frozen picture, gated telemetry.
import test from "node:test";
import assert from "node:assert/strict";
import { createRenderState } from "../viewer/state_buffer.js";
import { createLinkPresenter, createTelemetryGate, linkEffect } from "../viewer/video_link.js";

test("a healthy or absent link has no effect", () => {
  assert.equal(linkEffect(null), null);
  assert.equal(linkEffect({}), null);
  assert.equal(linkEffect({ state: "healthy", video_lag_s: 0 }), null);
  const effect = linkEffect({ state: "degraded", video_lag_s: 3.2, artefact: 0.7, telemetry_hz: 4,
    video_frozen: false });
  assert.deepEqual(effect, { state: "degraded", lost: false, frozen: false, extraDelay: 3.2, artefact: 0.7,
    telemetryHz: 4 });
  assert.equal(linkEffect({ state: "lost", video_frozen: true, telemetry_hz: 0 }).telemetryHz, 0);
});

test("the telemetry gate releases packets at the link rate and holds them while lost", () => {
  const gate = createTelemetryGate();
  assert.equal(gate({ t: 1 }, null, 10), null, "no gating on a healthy link");
  const degraded = { telemetryHz: 2 };
  assert.deepEqual(gate({ t: 2 }, degraded, 10.1), { t: 1 }, "keeps the last packet until the period ends");
  assert.deepEqual(gate({ t: 3 }, degraded, 10.6), { t: 3 });
  const lost = { telemetryHz: 0 };
  assert.deepEqual(gate({ t: 4 }, lost, 20), { t: 3 }, "nothing new arrives while lost");
});

function rig(delayMs = 150) {
  const poses = [];
  const render = createRenderState({
    rovG: { position: {}, quaternion: {} },
    P(pos) { poses.push(pos[2]); },
    Q() {},
    fleet: { ingest() {} },
    updateTether() {},
    fidelity: { get: () => delayMs },
    link: createLinkPresenter(),
  });
  return { render, poses };
}

function feed(render, link, from = 0, to = 300) {
  for (let i = from; i <= to; i++) {
    const t = i * 0.05;
    render.ingest({ t, pos: [0, 0, t], q: [1, 0, 0, 0], speed_kn: t, link }, false, 100 + t);
  }
}

test("link lag is added to the video delay", () => {
  const { render } = rig();
  feed(render, { state: "degraded", video_lag_s: 4, video_frozen: false, telemetry_hz: 4 });
  render.update(null, false, 115);
  assert.ok(Math.abs(render.state.pos[2] - (15 - 4.15)) < 1e-6, `picture at ${render.state.pos[2]}`);
});

test("a frozen link holds the last picture, then jumps forward", () => {
  const { render } = rig();
  feed(render, { state: "healthy" }, 0, 200);
  render.update(null, false, 110);
  const before = render.state.pos[2];
  feed(render, { state: "lost", video_frozen: true, telemetry_hz: 0 }, 201, 260);
  render.update(null, false, 113);
  assert.equal(render.state.pos[2], before, "the picture does not move while frozen");
  const shown = render.display({ t: 13, pos: [0, 0, 13], speed_kn: 13, locked: true });
  assert.equal(shown.locked, true, "the pilot's own switches stay current");
  feed(render, { state: "healthy" }, 261, 280);
  render.update(null, false, 114);
  assert.ok(render.state.pos[2] > 13.5, "recovery jumps to the live picture");
});

test("without a link presenter the render state ignores the field", () => {
  const render = createRenderState({
    rovG: { position: {}, quaternion: {} }, P() {}, Q() {}, fleet: { ingest() {} }, updateTether() {},
    fidelity: { get: () => 150 },
  });
  feed(render, { state: "lost", video_frozen: true, telemetry_hz: 0 }, 0, 100);
  render.update(null, false, 105);
  assert.ok(Math.abs(render.state.pos[2] - 4.85) < 1e-6);
  assert.equal(render.linkEffect, null);
});
