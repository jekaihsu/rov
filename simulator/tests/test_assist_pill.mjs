// The HUD mode pill shows what the pilot requested and, separately, whether the simulator honours it.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import { assistPill } from "../viewer/hud/assist_pill.js";

const hold = { level: 2, profile: "normal" };
function serverAssist(level, extra = {}) {
  return { level, profile: "normal", holding: false, limited: false, ...extra };
}

test("assisted preset with motors locked shows the requested level, not the server's zero", () => {
  const pill = assistPill({ locked: true, assist: serverAssist(0) }, hold);
  assert.equal(pill.text, "定點輔助 · 標準");
  assert.equal(pill.status, "解鎖後生效");
  assert.equal(pill.tone, "pending");
});

test("once unlocked and honoured the status clears or reports holding", () => {
  assert.deepEqual(assistPill({ locked: false, assist: serverAssist(2) }, hold).status, "");
  const holding = assistPill({ locked: false, assist: serverAssist(2, { holding: true }) }, hold);
  assert.equal(holding.status, "定點中");
  assert.equal(holding.tone, "ok");
});

test("a server without assist support is called out", () => {
  const pill = assistPill({ locked: false }, hold);
  assert.equal(pill.text, "定點輔助 · 標準");
  assert.equal(pill.status, "伺服器不支援輔助");
  assert.equal(pill.tone, "warn");
});

test("refused, saturated, remote and autopilot states are distinguished", () => {
  const refused = assistPill({ locked: false, assist: serverAssist(0) }, hold);
  assert.equal(refused.status, "未生效");
  assert.equal(refused.tone, "warn");
  assert.match(refused.help, /DVL/);
  assert.equal(assistPill({ locked: false, assist: serverAssist(2, { limited: true }) }, hold).status, "推力飽和");
  const remote = assistPill({ locked: false, remote_control: true, assist: serverAssist(0) }, hold);
  assert.equal(remote.status, "SDK 控制中停用");
  const route = assistPill({ locked: false, nav: { mode: "ROUTE" }, assist: serverAssist(0) }, hold);
  assert.equal(route.status, "自動航線中停用");
  const profile = assistPill({ locked: false, assist: serverAssist(2) }, { level: 2, profile: "sport" });
  assert.equal(profile.text, "定點輔助 · 運動");
  assert.equal(profile.status, "未生效");
});

test("manual shows no profile and no status in the real preset", () => {
  const manual = { level: 0, profile: "normal" };
  assert.deepEqual(assistPill({ locked: true, assist: serverAssist(0) }, manual), {
    text: "手動",
    status: "",
    tone: "ok",
    help: "",
  });
  assert.equal(assistPill({ locked: false }, manual).status, "");
  assert.equal(assistPill({ locked: false, assist: serverAssist(2) }, manual).tone, "pending");
});

test("the HUD reads the request from the fidelity profile, not from state.assist", async () => {
  const hud = await readFile(new URL("../viewer/hud/flight_hud.js", import.meta.url), "utf8");
  assert.match(hud, /assistPill\(s, \{level: fidelity\.get\('assistLevel'\), profile: fidelity\.get\('flightProfile'\)\}\)/);
  assert.equal(/s\.assist\.level/.test(hud), false);
});
