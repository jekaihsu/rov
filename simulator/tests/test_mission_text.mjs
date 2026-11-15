// Free exploration never shows a time limit, objectives or "目標 0/0"; scored modes keep their numbers.
import test from "node:test";
import assert from "node:assert/strict";
import {
  briefingTimeLimit,
  missionTimeLimit,
  objectiveSummary,
  scoreSummary,
  scoreValue,
} from "../viewer/play/mission_text.js";
import { restartMessages } from "../viewer/play/restart.js";

const WORLD = { scenario: { time_limit_s: 900 } };
const EMPTY = { score: 0, elapsed: 12, objectives: [], penalties: [], penalty_total: 0 };

test("free exploration and the expedition sea are untimed and unscored", () => {
  for (const mode of ["free_explore", "expedition"]) {
    const state = { mission: { mode }, score: EMPTY };
    assert.equal(missionTimeLimit(state, WORLD), null, mode);
    assert.equal(scoreValue(state), "—", mode);
    assert.doesNotMatch(scoreSummary(state), /0\/0/, mode);
    assert.equal(briefingTimeLimit(mode, { timeLimit: 900 }), null, mode);
  }
  assert.match(scoreSummary({ mission: { mode: "free_explore" }, score: EMPTY }), /不計時/);
  const contract = { mission: { mode: "expedition" }, expedition: { active: { label: "巡檢三個站點" } } };
  assert.equal(scoreSummary(contract), "委託：巡檢三個站點");
});

test("scenario training and co-op keep their limit, score and objective count", () => {
  const score = { score: 80, objectives: [{ done: true }, { done: false }], penalty_total: 5 };
  const training = { mission: { mode: "scenario_training" }, score };
  assert.equal(missionTimeLimit(training, WORLD), 900);
  assert.equal(scoreValue(training), 80);
  assert.equal(scoreSummary(training), "目標 1/2 · 扣分 5");
  assert.equal(scoreSummary({ ...training, score: { ...score, failed: "超過時間限制" } }), "失敗：超過時間限制");
  const coop = { mission: { mode: "inspection_coop", time_limit: 720 }, score };
  assert.equal(missionTimeLimit(coop, WORLD), 720);
  assert.equal(briefingTimeLimit("inspection_coop", { timeLimit: 900 }), 720);
  assert.equal(briefingTimeLimit("scenario_training", { timeLimit: 900 }), 900);
});

test("a running chapter shows its own objective", () => {
  const state = { mission: { mode: "free_explore" }, campaign: { status: "active", objective: "解除馬達鎖定" } };
  assert.equal(scoreSummary(state), "解除馬達鎖定");
});

test("the pause menu summary names the current objective per mode", () => {
  const training = { mission: { mode: "scenario_training" },
    score: { objectives: [{ label: "A", done: true }, { label: "B", done: false }], penalty_total: 0 } };
  assert.deepEqual(objectiveSummary(training), ["下一步：B", "目標 1/2 · 扣分 0"]);
  const chapter = { campaign: { status: "active", chapter: "harbor", objective: "穩定懸停並拍照",
    chapters: [{ id: "harbor", title: "第一章｜港灣" }] } };
  assert.deepEqual(objectiveSummary(chapter), ["第一章｜港灣", "穩定懸停並拍照"]);
  const sea = { mission: { mode: "expedition" }, expedition: { active: null } };
  assert.equal(objectiveSummary(sea).length, 2);
  assert.deepEqual(objectiveSummary({ mission: { mode: "free_explore" } }), ["自由探索 · 不計時、不扣分"]);
});

test("restart repeats the chapter, or resets the scene and restores its play mode", () => {
  assert.deepEqual(restartMessages({ campaign: { status: "active", chapter: "hull" } }),
    [{ type: "operation", action: "campaign_start", chapter: "hull" }]);
  assert.deepEqual(restartMessages({ mission: { mode: "scenario_training" } }), [{ type: "reset" }]);
  assert.deepEqual(restartMessages({ mission: { mode: "free_explore" } }),
    [{ type: "reset" }, { type: "operation", action: "mission_mode", mode: "free_explore" }]);
});
