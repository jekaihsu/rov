// Rich Presence tokens: chapter and level labels stay localized and free of vendor names.
import test from "node:test";
import assert from "node:assert/strict";
import { chapterLabel, levelLabel, presenceFromState } from "../viewer/play/steam_presence.js";

test("presence falls back to the main menu when nothing is active", () => {
  const tokens = presenceFromState(null);
  assert.match(tokens.chapter, /主選單/);
  assert.match(tokens.level, /主選單/);
});

test("career contract maps to chapter and level labels", () => {
  const tokens = presenceFromState(
    { locked: false, campaign: { chapter: "ch1", status: "active" }, mission: { mode: "campaign" } },
    { careerContract: { id: "c1_pier_level1", chapter: "ch1" }, language: "zh-Hant" },
  );
  assert.equal(tokens.chapterId, "ch1");
  assert.equal(tokens.levelId, "c1_pier_level1");
  assert.equal(tokens.chapter, chapterLabel("ch1"));
  assert.equal(tokens.level, levelLabel("c1_pier_level1"));
  assert.doesNotMatch(tokens.chapter, /BlueROV|Falcon|QY|深之蓝/i);
  assert.doesNotMatch(tokens.level, /BlueROV|Falcon|QY|深之蓝/i);
});

test("mission modes without a career contract still produce a level token", () => {
  const tokens = presenceFromState({ locked: false, mission: { mode: "expedition" } });
  assert.equal(tokens.levelId, "expedition");
  assert.equal(tokens.level, levelLabel("expedition"));
});
