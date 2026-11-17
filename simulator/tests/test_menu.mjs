// Launch menu data and launch URL: what the cards show and what the game receives.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import {
  chapterStatus,
  chaptersByCategory,
  depthRange,
  difficulty,
  diveSites,
  siteFacts,
  supportsMode,
  trainingScenarios,
  vehicleSpecs,
} from "../viewer/menu/catalogue.js";
import { introForLaunch, launchUrl, normaliseServer } from "../viewer/menu/preferences.js";
import { nearestInDirection } from "../viewer/menu/navigator.js";

const VIEWER = new URL("../viewer/", import.meta.url);
const scenes = JSON.parse(await readFile(new URL("scene_previews.json", VIEWER), "utf8"));
const catalogue = JSON.parse(await readFile(new URL("menu_catalogue.json", VIEWER), "utf8"));

test("the exported catalogue matches the backend vehicles and chapters", async () => {
  const vehicles = await readFile(new URL("../qysim/vehicles.py", import.meta.url), "utf8");
  for (const vehicle of catalogue.vehicles) assert.match(vehicles, new RegExp(`"${vehicle.id}"`));
  const x1 = catalogue.vehicles.find((vehicle) => vehicle.id === "x1");
  assert.ok(x1.provisional.length > 0, "X1 values are provisional until measured");
  assert.ok(vehicleSpecs(x1).provisional);
  const falcon = catalogue.vehicles.find((vehicle) => vehicle.id === "falcon");
  assert.equal(falcon.arm, true);
  assert.equal(vehicleSpecs(falcon).provisional, false);
  for (const chapter of catalogue.chapters) assert.ok(["story", "incident"].includes(chapter.category));
  for (const vehicle of catalogue.vehicles) {
    const bars = Object.values(vehicleSpecs(vehicle).bars);
    for (const value of bars) assert.ok(value >= 0 && value <= 1);
  }
});

test("dive sites exclude incident drills and the onboarding pool", () => {
  const sites = diveSites(scenes, catalogue.chapters).map((scene) => scene.key);
  for (const chapter of chaptersByCategory(catalogue.chapters, "incident")) {
    assert.equal(sites.includes(chapter.scenario), false, chapter.id);
  }
  assert.equal(sites.includes("tutorial_pool"), false);
  assert.ok(sites.includes("coral_reef"));
  const reef = scenes.find((scene) => scene.key === "coral_reef");
  assert.ok(supportsMode(reef, "expedition"));
  assert.equal(supportsMode(scenes.find((scene) => scene.key === "open_water"), "expedition"), false);
});

test("site cards show depth range, visibility, current and activities", () => {
  const reef = siteFacts(scenes.find((scene) => scene.key === "coral_reef"));
  assert.ok(reef.shallow < reef.deep);
  assert.equal(reef.visibility, 18);
  assert.equal(reef.current, 0.55);
  assert.ok(reef.activities.length >= 2);
  assert.deepEqual(depthRange({ seabed_depth: 20 }), [20, 20]);
});

test("difficulty grows with current and falls with visibility", () => {
  assert.equal(difficulty({ current: { surface_kn: 0.2 }, scenario: { visibility_m: 20 } }).level, 1);
  assert.equal(difficulty({ current: { surface_kn: 0.8 }, scenario: { visibility_m: 9 } }).level, 2);
  assert.equal(difficulty({ current: { surface_kn: 1.8 }, scenario: { visibility_m: 4 } }).level, 3);
  const list = trainingScenarios(scenes);
  for (let index = 1; index < list.length; index++) {
    assert.ok(list[index - 1].difficulty.level <= list[index].difficulty.level);
  }
});

test("chapters are ordered by order field and locked by the local save", () => {
  const story = chaptersByCategory(catalogue.chapters, "story");
  const orders = story.map((chapter) => chapter.order);
  assert.deepEqual(orders, [...orders].sort((a, b) => a - b));
  assert.equal(story[0].id, "prologue");
  assert.equal(chapterStatus(story[0], []), "open");
  assert.equal(chapterStatus(story[1], []), "locked");
  assert.equal(chapterStatus(story[1], ["prologue"]), "open");
  assert.equal(chapterStatus(story[0], ["prologue"]), "done");
  assert.equal(chapterStatus({ id: "x", placeholder: true }, []), "pending");
});

test("the launch URL keeps foreign parameters and the URL contract of the game", () => {
  const choice = {
    model: "falcon",
    server: "http://127.0.0.1:8765/",
    room: "training",
    name: " ",
    scenario: "coral_reef",
    control: "ROV_USA",
    pad: "auto",
    sticker: "hazard",
    quality: "auto",
    mission: "campaign",
    chapter: "incident_jacket",
    intro: false,
  };
  const url = launchUrl("http://host/?fidelity=real&cam=chase&replay=x.json", choice);
  const params = url.searchParams;
  assert.equal(params.get("play"), "1");
  assert.equal(params.get("fidelity"), "real");
  assert.equal(params.get("cam"), "chase");
  assert.equal(params.has("replay"), false);
  assert.equal(params.get("ws"), "ws://127.0.0.1:8765/ws");
  assert.equal(params.get("chapter"), "incident_jacket");
  assert.equal(params.get("nointro"), "1");
  assert.equal(params.get("name"), "操作員");
  const free = launchUrl(url.href, { ...choice, mission: "expedition", intro: true });
  assert.equal(free.searchParams.has("chapter"), false);
  assert.equal(free.searchParams.has("nointro"), false);
  assert.throws(() => launchUrl("http://host/", { ...choice, room: "bad room" }));
  assert.throws(() => normaliseServer("ws://127.0.0.1:1", "https:"));
  assert.throws(() => normaliseServer("ftp://x"));
  const fromBoat = launchUrl("http://host/?menuStage=boat&sky=dusk&fidelity=real", choice);
  assert.equal(fromBoat.searchParams.has("menuStage"), false);
  assert.equal(fromBoat.searchParams.get("fidelity"), "real");
});

test("focus moves to the nearest control in the pressed direction", () => {
  const box = (x, y) => ({ left: x, top: y, width: 10, height: 10 });
  const items = [
    { item: "right", box: box(100, 0) },
    { item: "below", box: box(0, 60) },
    { item: "far-diagonal", box: box(60, 90) },
  ];
  assert.equal(nearestInDirection(box(0, 0), items, "right"), "right");
  assert.equal(nearestInDirection(box(0, 0), items, "down"), "below");
  assert.equal(nearestInDirection(box(0, 0), items, "left"), null);
});

test("the launch cinematic plays on the first dive only, unless kept on or the full procedure runs", () => {
  assert.equal(introForLaunch({ introPreference: true, introSeen: false }), true);
  assert.equal(introForLaunch({ introPreference: true, introSeen: true }), false);
  assert.equal(introForLaunch({ introPreference: true, introSeen: true, alwaysIntro: true }), true);
  assert.equal(introForLaunch({ introPreference: true, introSeen: true }, true), true, "real pre-dive procedure");
  assert.equal(introForLaunch({ introPreference: false, introSeen: false }), false);
});

test("menu and tab parameters of the results screen do not leak into the game URL", () => {
  const url = launchUrl("http://h/?menu=training&tab=drills", {
    model: "x1", server: "ws://h:1/ws", room: "r", name: "n", scenario: "open_water", control: "UAV_CHN",
    pad: "auto", sticker: "none", quality: "auto", mission: "free_explore", intro: false,
  });
  assert.equal(url.searchParams.has("menu"), false);
  assert.equal(url.searchParams.has("tab"), false);
});
