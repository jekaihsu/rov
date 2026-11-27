// Results screen data: medals, score breakdowns, chapter rewards, end-of-run detection and the best-score record.
import test from "node:test";
import assert from "node:assert/strict";
import {
  MEDALS,
  chapterOutcome,
  contractOutcome,
  createOutcomeWatcher,
  medalFor,
  recordFor,
  recordResult,
  scoreOutcome,
  scoreRows,
} from "../viewer/play/results_model.js";

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
  };
}

const WORLD = { scenario: { key: "open_water", name: "開放水域熟悉", time_limit_s: 600 } };

function scored(score) {
  return { t: 10, mission: { mode: "scenario_training" }, score };
}

test("medal thresholds are data and a failed run earns none", () => {
  assert.deepEqual(MEDALS.map((medal) => medal.id), ["gold", "silver", "bronze"]);
  assert.equal(medalFor(95), "gold");
  assert.equal(medalFor(90), "gold");
  assert.equal(medalFor(80), "silver");
  assert.equal(medalFor(50), "bronze");
  assert.equal(medalFor(49), "none");
  assert.equal(medalFor(100, false), "none");
});

test("the score breakdown adds up to the server score", () => {
  const score = {
    score: 55, elapsed: 125, finished: true, failed: "",
    objectives: [{ done: true }, { done: true }, { done: true }, { done: false }],
    penalties: [
      { t: 3, reason: "碰撞 pile_a（touch 0.2 m/s）", points: 5 },
      { t: 9, reason: "碰撞 pile_b（hard 0.6 m/s）", points: 15 },
      { t: 20, reason: "纜線張力過高 400 N", points: 10 },
    ],
    penalty_total: 20 + 10 + 4 + 6, procedure_penalty: 4,
  };
  const rows = scoreRows(score, 600);
  const byId = Object.fromEntries(rows.map((row) => [row.id, row]));
  assert.equal(byId.objectives.points, 75);
  assert.equal(byId.objectives.detail, "3/4");
  assert.equal(byId.contacts.points, -20);
  assert.equal(byId.tether.points, -10);
  assert.equal(byId.procedure.points, -4);
  assert.equal(byId.other.points, -6, "penalties older than the last 20 are not lost");
  assert.equal(byId.time.detail, "02:05 / 10:00");
  const total = rows.reduce((sum, row) => sum + (row.points || 0), 0);
  assert.equal(total, 35);
});

test("a scenario outcome carries the title, medal and failure reason", () => {
  const ok = scoreOutcome(scored({ score: 92, finished: true, failed: "", objectives: [{ done: true }],
    penalties: [], penalty_total: 0, elapsed: 50 }), WORLD);
  assert.equal(ok.kind, "scenario");
  assert.equal(ok.recordKey, "scenario:open_water");
  assert.equal(ok.title, "開放水域熟悉");
  assert.equal(ok.medal, "gold");
  const failed = scoreOutcome(scored({ score: 60, finished: false, failed: "超過時間限制", objectives: [],
    penalties: [], penalty_total: 0 }), WORLD);
  assert.equal(failed.success, false);
  assert.equal(failed.medal, "none");
  assert.equal(failed.reason, "超過時間限制");
  const coop = scoreOutcome({ mission: { mode: "inspection_coop", time_limit: 720 },
    score: { score: 100, finished: true, objectives: [] } }, WORLD);
  assert.equal(coop.kind, "coop");
  assert.equal(coop.limit, 720);
});

test("a chapter outcome shows the rewards and unlocks it earned and the next chapter", () => {
  const campaign = {
    chapter: "prologue", status: "completed", next_story: "harbor",
    rewards: ["first_dive"], unlocks: { stickers: ["dive"], vehicles: [] },
    results: [{ chapter: "prologue", elapsed: 101.5, collisions: 1, tether_broken: false }],
    chapters: [
      { id: "prologue", title: "序章｜水池", category: "story" },
      { id: "harbor", title: "第一章｜港灣", category: "story" },
    ],
  };
  const outcome = chapterOutcome({ campaign, start: { rewards: [], unlocks: { stickers: [], vehicles: [] } },
    overloads: 1 });
  assert.equal(outcome.kind, "chapter");
  assert.equal(outcome.score, 100 - 5 - 10);
  assert.equal(outcome.medal, "silver");
  assert.deepEqual(outcome.next, { id: "harbor", title: "第一章｜港灣" });
  assert.ok(outcome.rewards.includes("首次下潛徽章"));
  assert.ok(outcome.rewards.some((text) => text.includes("潛水旗")));
  const replayed = chapterOutcome({ campaign, start: { rewards: ["first_dive"], unlocks: campaign.unlocks } });
  assert.deepEqual(replayed.rewards, [], "a replayed chapter earns nothing new");
  const drill = chapterOutcome({ campaign: { ...campaign, chapter: "incident_silt", next_story: "harbor",
    results: [{ chapter: "incident_silt", elapsed: 30, collisions: 0, tether_broken: true }],
    chapters: [{ id: "incident_silt", title: "事故訓練", category: "incident" }] } });
  assert.equal(drill.kind, "drill");
  assert.equal(drill.next, null, "drills do not chain into the story");
  assert.equal(drill.score, 50);
  const course = chapterOutcome({
    campaign: {
      ...campaign,
      chapter: "course_b01",
      next_story: "prologue",
      results: [{ chapter: "course_b01", elapsed: 40, collisions: 0, tether_broken: false }],
      chapters: [{ id: "course_b01", title: "B01", category: "course" }],
    },
  });
  assert.equal(course.kind, "chapter");
  assert.equal(course.next, null, "company courses do not chain into the story");
});

test("a contract outcome grades by contacts", () => {
  const clean = contractOutcome({ id: "c1", kind: "inspect", label: "巡檢委託", grade: "精準完成", elapsed: 80,
    collision_count: 0 });
  assert.equal(clean.medal, "gold");
  assert.equal(clean.recordKey, "contract:inspect");
  assert.equal(contractOutcome({ kind: "recover", collision_count: 3 }).score, 85);
});

test("the watcher fires once on the frame a run ends, never for a run already over at connect", () => {
  const watcher = createOutcomeWatcher();
  const done = { score: 80, finished: true, failed: "", objectives: [{ done: true }], penalties: [] };
  assert.equal(watcher.observe(scored(done), WORLD), null, "already finished when the page connected");
  assert.equal(watcher.observe(scored(done), WORLD), null);
  const running = { score: 0, finished: false, failed: "", objectives: [{ done: false }], penalties: [] };
  assert.equal(watcher.observe(scored(running), WORLD), null, "reset");
  const ended = watcher.observe(scored(done), WORLD);
  assert.equal(ended?.kind, "scenario");
  assert.equal(watcher.observe(scored(done), WORLD), null, "only once");
  const free = createOutcomeWatcher();
  free.observe({ mission: { mode: "free_explore" }, score: running }, WORLD);
  assert.equal(free.observe({ mission: { mode: "free_explore" }, score: done }, WORLD), null);
});

test("the watcher reports chapters over the scenario they run in, and new contracts", () => {
  const watcher = createOutcomeWatcher();
  const chapters = [{ id: "harbor", title: "第一章｜港灣", category: "story" }];
  const base = { mission: { mode: "inspection_coop" }, score: { finished: false, objectives: [] } };
  watcher.observe({ ...base, campaign: { status: "idle", rewards: [], unlocks: {} } }, WORLD);
  watcher.observe({ ...base, campaign: { status: "active", chapter: "harbor", rewards: [], unlocks: {} } }, WORLD);
  watcher.observe({ ...base, tether: { warn: true },
    campaign: { status: "active", chapter: "harbor", rewards: [], unlocks: {} } }, WORLD);
  const inChapter = watcher.observe({ ...base, score: { finished: true, score: 100, objectives: [] },
    campaign: { status: "active", chapter: "harbor", rewards: [], unlocks: {} } }, WORLD);
  assert.equal(inChapter, null, "the scenario score is not a separate result inside a chapter");
  const finished = watcher.observe({ ...base, score: { finished: true, score: 100, objectives: [] },
    campaign: { status: "completed", chapter: "harbor", rewards: ["harbor_badge"], unlocks: {}, chapters,
      results: [{ chapter: "harbor", elapsed: 300, collisions: 0 }] } }, WORLD);
  assert.equal(finished.kind, "chapter");
  assert.equal(finished.score, 90, "one overload episode");
  assert.deepEqual(finished.rewards, ["港灣巡檢徽章"]);
  const contracts = createOutcomeWatcher();
  const exp = (results) => ({ mission: { mode: "expedition" }, expedition: { results } });
  contracts.observe(exp([{ id: "old", kind: "inspect" }]), WORLD);
  assert.equal(contracts.observe(exp([{ id: "old", kind: "inspect" }]), WORLD), null);
  const contract = contracts.observe(exp([{ id: "old", kind: "inspect" }, { id: "new", kind: "recover",
    collision_count: 0 }]), WORLD);
  assert.equal(contract.kind, "contract");
  assert.equal(contract.id, "recover");
});

test("a scene with no objectives, or a freshly loaded scene, is never a finished run", () => {
  const watcher = createOutcomeWatcher();
  const running = { score: 0, finished: false, failed: "", objectives: [{ done: false }], penalties: [] };
  watcher.observe(scored(running), WORLD);
  const pool = { scenario: { key: "tutorial_pool", seed: 42, name: "水池" } };
  const empty = { score: 0, finished: true, failed: "", objectives: [], penalties: [] };
  assert.equal(watcher.observe(scored(empty), pool), null, "new scene");
  assert.equal(watcher.observe(scored(running), WORLD), null, "back to a scene that is still running");
  const other = createOutcomeWatcher();
  other.observe(scored({ ...empty, finished: false }), pool);
  assert.equal(other.observe(scored(empty), pool), null, "no objectives, nothing to report");
});

test("the best score is kept per run and only replaced by a better successful run", () => {
  const storage = memoryStorage();
  const run = (score, success = true) => ({ recordKey: "scenario:open_water", score, success,
    medal: medalFor(score, success) });
  assert.deepEqual(recordResult(run(70), storage), { best: 70, previous: null, isBest: true });
  assert.deepEqual(recordResult(run(60), storage), { best: 70, previous: 70, isBest: false });
  assert.deepEqual(recordResult(run(99, false), storage), { best: 70, previous: 70, isBest: false });
  assert.deepEqual(recordResult(run(91), storage), { best: 91, previous: 70, isBest: true });
  assert.equal(recordFor("scenario:open_water", storage).medal, "gold");
  assert.equal(recordFor("scenario:other", storage), null);
});
