// Steam achievements: game events map onto the catalogue in desktop/steam/achievements.json, each reported once.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  CHAPTER1_CONTRACTS,
  GUIDE_EVENTS,
  chapterAllGold,
  createAchievements,
  outcomeEvents,
  stateEvents,
} from "../viewer/play/achievements.js";

const catalogue = JSON.parse(await readFile(new URL("../desktop/steam/achievements.json", import.meta.url), "utf8"));
const EVENTS = new Set(catalogue.map((entry) => entry.event));

function memoryStorage() {
  const data = new Map();
  return {
    getItem: (key) => (data.has(key) ? data.get(key) : null),
    setItem: (key, value) => data.set(key, String(value)),
  };
}

function observation(id, category, photographer = "v1") {
  return { photo_id: id, accepted: true, entry: { category, photographer } };
}

test("catalogue stays within 15–25 skill events and matches what the viewer can report", () => {
  assert.ok(catalogue.length >= 15 && catalogue.length <= 25);
  const emitted = new Set([
    ...Object.values(GUIDE_EVENTS),
    "first_dive",
    "harbor_clean",
    "murk_measure",
    "tether_retrace",
    "chapter1_gold",
    "pool_gold",
    "open_water_clean",
    "hull_loto",
    "sonar_find",
    "cp_survey",
    "ut_survey",
    "grade2_exam",
    "real_exam",
    "cable_discipline",
    "zero_collision",
    "prologue_done",
    "untangled",
    "inspection_coop",
    "recovery_work",
    "deployment_work",
    "evidence_photo",
    "pier_measure",
  ]);
  for (const event of emitted) assert.ok(EVENTS.has(event), event);
  for (const event of EVENTS) assert.ok(emitted.has(event), `catalogue event ${event} is never reported`);
});

test("state frames map to dive, tether retrace, coop and evidence events", () => {
  const base = { vehicle_id: "v1", locked: true, pos: [0, 0, 3], photos: 0 };
  assert.deepEqual(stateEvents(null, base), []);
  assert.deepEqual(stateEvents(null, { ...base, locked: false }), ["first_dive"]);
  assert.deepEqual(stateEvents(null, { ...base, locked: false, pos: [0, 0, 0.2] }), [], "at the surface");
  const wrapped = { ...base, score: { objectives: [{ kind: "untangle", done: false }] } };
  const free = { ...base, score: { objectives: [{ kind: "untangle", done: true }] } };
  assert.deepEqual(stateEvents(wrapped, free), ["untangled"]);
  const snagged = { ...base, tether_ops: { result: null } };
  const cleared = { ...base, tether_ops: { result: { correct: true, returned: true, score: 80 } } };
  assert.deepEqual(stateEvents(snagged, cleared), ["untangled", "tether_retrace"]);
  const coop = { ...base, mission: { mode: "inspection_coop", status: "completed" } };
  assert.deepEqual(stateEvents(base, coop), ["inspection_coop"]);
  const before = { ...base, expedition: { last_observation: null } };
  const fish = { ...base, expedition: { last_observation: observation("p1", "fish_school") } };
  assert.deepEqual(stateEvents(before, fish), ["evidence_photo"]);
});

test("finished runs map to skill-based career and contract events", () => {
  assert.deepEqual(outcomeEvents({ kind: "scenario", success: true, contacts: 0 }), ["zero_collision"]);
  assert.deepEqual(outcomeEvents({ kind: "scenario", success: false, contacts: 0 }), []);
  assert.deepEqual(outcomeEvents({ kind: "contract", id: "recover", success: true, contacts: 2 }), ["recovery_work"]);
  assert.deepEqual(outcomeEvents({ kind: "contract", id: "deploy", success: true, contacts: 1 }), ["deployment_work"]);
  assert.deepEqual(
    outcomeEvents({
      kind: "career",
      id: "c1_pier_level1",
      success: true,
      contacts: 0,
      medal: "gold",
      contracts: {},
    }),
    ["zero_collision", "harbor_clean"],
  );
  assert.deepEqual(
    outcomeEvents({
      kind: "career",
      id: "c1_pier_level2",
      success: true,
      contacts: 1,
      medal: "silver",
      measured: true,
      visibility_m: 1.2,
      contracts: {},
    }),
    ["pier_measure", "murk_measure"],
  );
  assert.deepEqual(
    outcomeEvents({
      kind: "career",
      id: "p1_pool_checkout",
      success: true,
      contacts: 0,
      medal: "gold",
      contracts: {},
    }),
    ["zero_collision", "pool_gold"],
  );
  assert.ok(CHAPTER1_CONTRACTS.length === 7);
  const medals = Object.fromEntries(CHAPTER1_CONTRACTS.map((id) => [id, { medal: "gold" }]));
  assert.equal(chapterAllGold(medals), true);
  assert.deepEqual(
    outcomeEvents({
      kind: "career",
      id: "c1_signoff_exam",
      success: true,
      contacts: 0,
      medal: "gold",
      examPassed: true,
      examValid: true,
      contracts: medals,
    }).sort(),
    ["chapter1_gold", "grade2_exam", "real_exam", "zero_collision"].sort(),
  );
});

test("each achievement is reported once, and internal builds can disable reporting", () => {
  const storage = memoryStorage();
  const reported = [];
  const tracker = createAchievements({ report: (event) => reported.push(event), storage });
  const base = { vehicle_id: "v1", locked: false, pos: [0, 0, 3], photos: 0, expedition: { last_observation: null } };
  tracker.observe(base);
  tracker.observe({ ...base, pos: [0, 0, 4] });
  assert.deepEqual(reported, ["first_dive"]);
  tracker.finished({ kind: "contract", id: "recover", success: true, contacts: 0 });
  assert.ok(reported.includes("recovery_work"));
  assert.ok(reported.includes("zero_collision"));
  const again = [];
  const later = createAchievements({ report: (event) => again.push(event), storage });
  later.observe(base);
  later.finished({ kind: "contract", id: "recover", success: true, contacts: 0 });
  assert.deepEqual(again, [], "saved achievements are not reported again");
  const disabled = createAchievements({
    report: () => assert.fail("should not report"),
    storage: memoryStorage(),
    enabled: false,
  });
  assert.deepEqual(disabled.observe(base), []);
  assert.equal(disabled.enabled, false);
});
