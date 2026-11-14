// One stacking scale: z-index values come from hud/tokens.css, never from literals scattered in modules.
import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir } from "node:fs/promises";

const VIEWER = new URL("../viewer/", import.meta.url);
// Listed lowest to highest, as documented next to the tokens.
const SCALE = [
  "--z-scene-mark",
  "--z-hud",
  "--z-hud-alert",
  "--z-pip",
  "--z-subtitle",
  "--z-story",
  "--z-notice",
  "--z-controls",
  "--z-banner",
  "--z-drawer",
  "--z-blocker",
  "--z-menu",
  "--z-toast",
];

async function sources(directory = "") {
  const found = [];
  for (const entry of await readdir(new URL(directory, VIEWER), { withFileTypes: true })) {
    const path = directory + entry.name;
    if (entry.isDirectory() && entry.name !== "vendor") found.push(...(await sources(path + "/")));
    else if (/\.(css|js|html)$/.test(entry.name)) found.push(path);
  }
  return found;
}

async function tokens() {
  const text = await readFile(new URL("hud/tokens.css", VIEWER), "utf8");
  const values = new Map();
  for (const match of text.matchAll(/(--z-[a-z-]+):\s*(\d+);/g)) values.set(match[1], Number(match[2]));
  return values;
}

test("the stacking scale is complete and ascending", async () => {
  const values = await tokens();
  for (const name of SCALE) assert.ok(values.has(name), `missing ${name}`);
  assert.deepEqual([...values.keys()].sort(), [...SCALE, "--z-raised"].sort());
  for (let i = 1; i < SCALE.length; i++) {
    assert.ok(values.get(SCALE[i - 1]) < values.get(SCALE[i]), `${SCALE[i - 1]} must be below ${SCALE[i]}`);
  }
});

test("no viewer source writes a literal z-index", async () => {
  const known = await tokens();
  for (const path of await sources()) {
    const text = await readFile(new URL(path, VIEWER), "utf8");
    for (const match of text.matchAll(/z-index\s*:\s*([^;}`"']+)|zIndex\s*[:=]\s*['"]?([^,;'"}]+)/g)) {
      const value = (match[1] ?? match[2]).trim();
      assert.match(value, /^(var\(--z-[a-z-]+\)|calc\(var\(--z-[a-z-]+\) \+ \d+\))$/, `${path}: z-index ${value}`);
      const name = /--z-[a-z-]+/.exec(value)[0];
      assert.ok(known.has(name), `${path}: unknown token ${name}`);
    }
  }
});

test("the layers named by the audit use the scale", async () => {
  const hud = await readFile(new URL("hud/hud.css", VIEWER), "utf8");
  const style = await readFile(new URL("style.css", VIEWER), "utf8");
  const story = await readFile(new URL("story/campaign.js", VIEWER), "utf8");
  const menu = await readFile(new URL("menu.css", VIEWER), "utf8");
  assert.match(hud, /#engineering \{[^}]*z-index: var\(--z-drawer\)/);
  assert.match(hud, /body \.hud, \.flight \{ z-index: var\(--z-hud\)/);
  assert.match(style, /\.viewport \.replay\{[^}]*z-index:var\(--z-controls\)/);
  assert.match(style, /\.viewport \.subtitle\{[^}]*z-index:var\(--z-subtitle\);pointer-events:none/);
  assert.match(story, /z-index:var\(--z-story\)/);
  assert.match(menu, /\.launch-menu\{[^}]*z-index:var\(--z-menu\)/);
});
