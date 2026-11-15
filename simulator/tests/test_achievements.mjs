// Steam achievements: game events map onto the catalogue in desktop/steam/achievements.json, each reported once.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  GUIDE_EVENTS,
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

test("every event the viewer can report exists in the Steam catalogue", () => {
  const emitted = new Set([
    ...Object.values(GUIDE_EVENTS), "guide_complete", "first_dive", "first_photo", "untangled", "three_pilots",
    "inspection", "recovery", "deployment", "scenario", "zero_collision",
  ]);
  for (const event of emitted) assert.ok(EVENTS.has(event), event);
  for (const event of EVENTS) assert.ok(emitted.has(event), `catalogue event ${event} is never reported`);
});

test("state frames map to dive, photo, untangle, crew and guide events", () => {
  const base = { vehicle_id: "v1", locked: true, pos: [0, 0, 3], photos: 0 };
  assert.deepEqual(stateEvents(null, base), []);
  assert.deepEqual(stateEvents(null, { ...base, locked: false }), ["first_dive"]);
  assert.deepEqual(stateEvents(null, { ...base, locked: false, pos: [0, 0, 0.2] }), [], "at the surface");
  assert.deepEqual(stateEvents(base, { ...base, photos: 1 }), ["first_photo"]);
  const wrapped = { ...base, score: { objectives: [{ kind: "untangle", done: false }] } };
  const free = { ...base, score: { objectives: [{ kind: "untangle", done: true }] } };
  assert.deepEqual(stateEvents(wrapped, free), ["untangled"]);
  const crew = { ...base, room: { players: [{ connected: true }, { connected: true }, { connected: true }] } };
  assert.deepEqual(stateEvents(base, crew), ["three_pilots"]);
  const before = { ...base, expedition: { last_observation: null } };
  const fish = { ...base, expedition: { last_observation: observation("p1", "fish_school") } };
  assert.deepEqual(stateEvents(before, fish), ["guide_fish"]);
  assert.deepEqual(stateEvents(fish, fish), [], "the same photo is not counted twice");
  const teammate = { ...base, expedition: { last_observation: observation("p2", "coral", "v2") } };
  assert.deepEqual(stateEvents(before, teammate), [], "a teammate's photo is theirs");
  const coop = { ...base, mission: { mode: "inspection_coop", status: "completed" } };
  assert.deepEqual(stateEvents(base, coop), ["inspection"]);
});

test("finished runs map to training, contract and clean-run events", () => {
  assert.deepEqual(outcomeEvents({ kind: "scenario", success: true, contacts: 0 }), ["scenario", "zero_collision"]);
  assert.deepEqual(outcomeEvents({ kind: "scenario", success: false, contacts: 0 }), []);
  assert.deepEqual(outcomeEvents({ kind: "contract", id: "recover", success: true, contacts: 2 }), ["recovery"]);
  assert.deepEqual(outcomeEvents({ kind: "contract", id: "deploy", success: true, contacts: 1 }), ["deployment"]);
  assert.deepEqual(outcomeEvents({ kind: "chapter", id: "prologue", success: true, contacts: 1 }), ["first_dive"]);
});

test("each achievement is reported once, across sessions, and the five guide categories complete the guide", () => {
  const storage = memoryStorage();
  const reported = [];
  const tracker = createAchievements({ report: (event) => reported.push(event), storage });
  const base = { vehicle_id: "v1", locked: false, pos: [0, 0, 3], photos: 0, expedition: { last_observation: null } };
  tracker.observe(base);
  tracker.observe({ ...base, pos: [0, 0, 4] });
  assert.deepEqual(reported, ["first_dive"]);
  let previous = base;
  ["coral", "seastar", "kelp", "seagrass", "fish_school"].forEach((category, index) => {
    const next = { ...base, expedition: { last_observation: observation(`p${index}`, category) } };
    tracker.observe(next);
    previous = next;
  });
  tracker.observe(previous);
  assert.ok(reported.includes("guide_complete"));
  assert.equal(reported.filter((event) => event === "guide_seagrass").length, 1, "kelp and seagrass share one");
  const again = [];
  const later = createAchievements({ report: (event) => again.push(event), storage });
  later.observe(base);
  later.finished({ kind: "scenario", success: true, contacts: 0 });
  assert.deepEqual(again, ["scenario", "zero_collision"], "saved achievements are not reported again");
});
