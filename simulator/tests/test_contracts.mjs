// Contract board data for the objective card and the pause menu.
import test from "node:test";
import assert from "node:assert/strict";
import { acceptContract, contractBoard } from "../viewer/play/contracts.js";

const AVAILABLE = [
  { kind: "inspect", label: "定點巡檢", enabled: true, reason: "" },
  { kind: "recover", label: "海底物件回收", enabled: false, reason: "需要機械臂" },
];

test("the board offers contracts outside an active one, only in the expedition sea", () => {
  assert.equal(contractBoard({ mission: { mode: "free_explore" }, expedition: {} }), null);
  const board = contractBoard({ mission: { mode: "expedition" }, expedition: { available: AVAILABLE } });
  assert.equal(board.active, null);
  assert.deepEqual(board.offers.map((offer) => [offer.kind, offer.enabled]), [["inspect", true], ["recover", false]]);
  assert.match(board.offers[0].help, /三個站點/);
  assert.equal(board.offers[1].reason, "需要機械臂");
  const guest = contractBoard({ mission: { mode: "expedition" }, expedition: { available: AVAILABLE } }, false);
  assert.ok(guest.offers.every((offer) => !offer.enabled), "only the host accepts");
});

test("an active contract lists its steps with progress and distance", () => {
  const state = {
    mission: { mode: "expedition" }, pos: [0, 0, 5],
    expedition: { active: { id: "c1", label: "定點巡檢", steps: [
      { id: "s1", label: "巡檢站 1", completed: true, point: [3, 4, 5] },
      { id: "s2", label: "巡檢站 2", completed: false, own_progress: 0.5, point: [3, 4, 5] },
    ] } },
  };
  const board = contractBoard(state);
  assert.equal(board.active.label, "定點巡檢");
  assert.deepEqual(board.active.steps.map((step) => [step.done, step.distance, step.progress]),
    [[true, null, null], [false, 5, 0.5]]);
});

test("accepting sends the drawer's expedition_start operation", () => {
  const sent = [];
  assert.equal(acceptContract((message) => sent.push(message) > 0, "inspect"), "");
  assert.equal(sent[0].action, "expedition_start");
  assert.equal(sent[0].contract, "inspect");
  assert.ok(sent[0].request_id);
  assert.match(acceptContract(() => false, "inspect"), /離線/);
});
