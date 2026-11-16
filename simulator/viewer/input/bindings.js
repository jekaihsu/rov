// The single default binding table for every input context, and the pure resolver that enforces it.
//
// Rule: inside one context an input (pad button, pad axis or keyboard code) belongs to at most one
// action. The only shared form is one `tap` plus one `hold` gesture on the same button. Contexts stack
// from low to high priority (CONTEXTS); while several are active, the highest one that binds an input
// owns it and the actions below it do not fire. A button claimed when it went down stays claimed until
// it is released, so a confirm press can never leak into the flight action on the same button.
import { bindingValue } from "./actions.js";

const STRINGS = {
  contexts: { flight: "飛行", orbit: "環繞視角", tool: "工具啟用中", dialogue: "對話", menu: "選單" },
  actions: {
    left_lr: "左桿左右",
    left_ud: "左桿上下",
    right_lr: "右桿左右",
    right_ud: "右桿上下",
    left_wave: "左滾輪",
    right_wave: "右滾輪",
    surge: "前進／後退",
    sway: "右移／左移",
    heave: "上升／下潛",
    yaw: "右轉／左轉",
    pitch: "抬頭／低頭",
    boost: "鍵盤全幅推桿",
    photo: "拍照",
    record: "錄影（按住）",
    depth: "定深",
    lock: "鎖定／解鎖",
    mode: "A/S/C 模式",
    engineering: "工程面板",
    light: "燈光",
    camera: "切換視角",
    assist: "輔助等級",
    profile: "飛行檔位",
    up: "任務速覽",
    left: "系統速覽",
    right: "地圖速覽",
    down: "鍵位速覽",
    arm: "手臂操作模式",
    settings: "手把設定",
    pause: "暫停選單",
    cameraGimbal: "鏡頭穩定",
    cameraPitchUp: "鏡頭上仰",
    cameraPitchDown: "鏡頭下俯",
    cameraOrbitX: "環繞水平",
    cameraOrbitY: "環繞垂直",
    paintSpray: "噴漆標記",
    sonarPeek: "聲納速覽",
    visionToggle: "AI 視覺疊圖",
    visionMark: "標記偵測目標",
    dialogueAccept: "繼續對話",
    dialogueSkip: "跳過教學",
    menuUp: "上一項",
    menuDown: "下一項",
    menuLeft: "減少／上一個選項",
    menuRight: "增加／下一個選項",
    menuStick: "移動焦點",
    menuStickX: "左右移動焦點",
    menuRotate: "旋轉展示",
    accept: "確認",
    back: "返回",
    tabPrevious: "上一分頁",
    tabNext: "下一分頁",
  },
  // What a stick channel does in the selected operation mode, positive direction first (keys list [+, −]).
  meanings: {
    surge: ["前進／後退", "後退／前進"],
    sway: ["右移／左移", "左移／右移"],
    heave: ["上升／下潛", "下潛／上升"],
    yaw: ["右轉／左轉", "左轉／右轉"],
    pitch: ["抬頭／低頭", "低頭／抬頭"],
    roll: ["右傾／左傾", "左傾／右傾"],
  },
  layouts: { console: "遙控器配置", game: "遊戲鍵位（WASD）" },
  hold: "長按",
  pad: ["A", "B", "X", "Y", "LB", "RB", "LT", "RT", "View", "Menu", "L3", "R3", "十字鍵上", "十字鍵下",
    "十字鍵左", "十字鍵右", "Home"],
  axes: ["左搖桿左右", "左搖桿上下", "右搖桿左右", "右搖桿上下"],
  keys: {
    Space: "Space",
    Tab: "Tab",
    Enter: "Enter",
    Escape: "Esc",
    KeyQ: "Q",
    KeyE: "E",
    ArrowUp: "↑",
    ArrowDown: "↓",
    ArrowLeft: "←",
    ArrowRight: "→",
    BracketLeft: "[",
    BracketRight: "]",
    ShiftLeft: "Shift",
    ShiftRight: "Shift",
    ControlLeft: "Ctrl",
    ControlRight: "右 Ctrl",
    AltLeft: "Alt",
    Backspace: "Backspace",
    Backquote: "`",
    Minus: "-",
    Equal: "=",
    Semicolon: ";",
    Quote: "'",
    Comma: ",",
    Period: ".",
    Slash: "/",
    Backslash: "\\",
  },
  separator: " · ",
};

// Lowest to highest priority. `menu` is exclusive: while it is active nothing below it is sampled.
export const CONTEXTS = ["flight", "orbit", "tool", "dialogue", "menu"];
export const HOLD_MS = 650;
// Bump when a default moves, so stored copies of the old default follow it (see migrateBindings).
export const BINDINGS_VERSION = 2;
const LEGACY_DEFAULTS = { profile: "b12" };

// pad: standard-mapping source (`a0`, `-a1`, `b7`, `[positive, negative]`, or a `b8+b9` chord).
// keys: KeyboardEvent.code list; for `axis` rows the pair is [positive, negative].
// gesture: `press` (default), `tap` (fires on release before HOLD_MS), `hold` (fires at HOLD_MS), `chord`.
// owner: `hud` rows are presentation keys handled by the flight HUD itself; they never reach the vehicle.
export const BINDINGS = [
  { action: "left_lr", context: "flight", pad: "a0", keys: ["KeyD", "KeyA"], axis: true },
  { action: "left_ud", context: "flight", pad: "-a1", keys: ["KeyW", "KeyS"], axis: true },
  { action: "right_lr", context: "flight", pad: "a2", keys: ["ArrowRight", "ArrowLeft"], axis: true },
  { action: "right_ud", context: "flight", pad: "-a3", keys: ["ArrowUp", "ArrowDown"], axis: true },
  { action: "left_wave", context: "flight", pad: ["b7", "b6"], keys: ["KeyE", "KeyQ"], axis: true },
  { action: "right_wave", context: "flight", pad: ["b5", "b4"], keys: ["KeyC", "KeyZ"], axis: true },
  // Pilot-axis rows: keyboard only, unbound in the console layout. The game layout binds them; the input layer turns
  // them into the stick channel that drives the axis in the current operation mode (OPERATION_AXES).
  { action: "surge", context: "flight", keys: [], axis: true, pilot: true },
  { action: "sway", context: "flight", keys: [], axis: true, pilot: true },
  { action: "heave", context: "flight", keys: [], axis: true, pilot: true },
  { action: "yaw", context: "flight", keys: [], axis: true, pilot: true },
  { action: "pitch", context: "flight", keys: [], axis: true, pilot: true },
  { action: "boost", context: "flight", keys: ["ShiftLeft", "ShiftRight"], modifier: true },
  { action: "photo", context: "flight", pad: "b0", keys: ["KeyP"] },
  { action: "record", context: "flight", pad: "b1", keys: ["KeyR"] },
  { action: "depth", context: "flight", pad: "b2", keys: ["KeyH"] },
  { action: "lock", context: "flight", pad: "b3", keys: ["Space"] },
  { action: "mode", context: "flight", pad: "b8", gesture: "tap", keys: ["KeyM"] },
  { action: "engineering", context: "flight", pad: "b8", gesture: "hold", keys: ["Tab"], owner: "hud" },
  { action: "light", context: "flight", pad: "b9", gesture: "tap", keys: ["KeyL"] },
  { action: "pause", context: "flight", pad: "b9", gesture: "hold", keys: ["Escape"] },
  { action: "camera", context: "flight", pad: "b10", keys: ["KeyV"] },
  { action: "assist", context: "flight", pad: "b11", gesture: "tap", keys: ["KeyF"] },
  { action: "profile", context: "flight", pad: "b11", gesture: "hold", keys: ["KeyG"] },
  { action: "up", context: "flight", pad: "b12", keys: ["Digit1"], owner: "hud" },
  { action: "left", context: "flight", pad: "b14", keys: ["Digit2"], owner: "hud" },
  { action: "right", context: "flight", pad: "b15", keys: ["Digit3"], owner: "hud" },
  { action: "down", context: "flight", pad: "b13", keys: ["Digit4"], owner: "hud" },
  { action: "arm", context: "flight", pad: "b16" },
  { action: "settings", context: "flight", pad: "b8+b9", gesture: "chord", keys: ["F8"], owner: "settings" },
  { action: "cameraGimbal", context: "flight", keys: ["KeyB"] },
  { action: "cameraPitchUp", context: "flight", keys: ["BracketRight"] },
  { action: "cameraPitchDown", context: "flight", keys: ["BracketLeft"] },
  { action: "sonarPeek", context: "flight", keys: ["Digit5"] },
  { action: "visionToggle", context: "flight", keys: ["KeyN"] },
  { action: "visionMark", context: "flight", keys: ["KeyK"] },
  { action: "cameraOrbitX", context: "orbit", pad: "a2" },
  { action: "cameraOrbitY", context: "orbit", pad: "a3" },
  { action: "paintSpray", context: "tool", keys: ["KeyF"] },
  { action: "dialogueAccept", context: "dialogue", pad: "b0", keys: ["Enter"] },
  { action: "dialogueSkip", context: "dialogue", pad: "b1", gesture: "hold" },
  { action: "menuUp", context: "menu", pad: "b12", keys: ["ArrowUp"] },
  { action: "menuDown", context: "menu", pad: "b13", keys: ["ArrowDown"] },
  { action: "menuLeft", context: "menu", pad: "b14", keys: ["ArrowLeft"] },
  { action: "menuRight", context: "menu", pad: "b15", keys: ["ArrowRight"] },
  { action: "menuStick", context: "menu", pad: "a1" },
  { action: "menuStickX", context: "menu", pad: "a0" },
  { action: "menuRotate", context: "menu", pad: "a2" },
  { action: "accept", context: "menu", pad: "b0", keys: ["Enter", "Space"] },
  { action: "back", context: "menu", pad: "b1", keys: ["Escape"] },
  { action: "tabPrevious", context: "menu", pad: "b4", keys: ["KeyQ"] },
  { action: "tabNext", context: "menu", pad: "b5", keys: ["KeyE"] },
];

const ROWS = new Map(BINDINGS.map((row) => [row.action, row]));

// Keyboard layouts. `console` is the table above: keys stand in for the real controller's sticks, so W/S is the
// left stick and its meaning follows the operation mode, exactly like the hand controller (the `real` default).
// `game` binds the pilot axes the way PC games do and moves the lock off Space, which becomes "up".
export const KEYBOARD_LAYOUTS = ["console", "game"];
const LAYOUT_KEYS = {
  console: {},
  game: {
    left_lr: [],
    left_ud: [],
    right_lr: [],
    right_ud: [],
    left_wave: [],
    right_wave: [],
    surge: ["KeyW", "KeyS"],
    sway: ["KeyD", "KeyA"],
    heave: ["Space", "KeyC"],
    yaw: ["KeyE", "KeyQ"],
    pitch: ["ArrowUp", "ArrowDown"],
    lock: ["KeyT"],
  },
};

// Pilot axis -> [channel, sign] per operation mode; mirrors qysim/rc.py _MAP (checked by test_bindings.mjs).
export const OPERATION_AXES = {
  ROV_USA: { pitch: ["left_ud", -1], yaw: ["left_lr", 1], surge: ["right_ud", 1], roll: ["right_lr", 1],
    heave: ["left_wave", 1], sway: ["right_wave", 1] },
  ROV_JPN: { surge: ["left_ud", 1], yaw: ["left_lr", 1], pitch: ["right_ud", -1], roll: ["right_lr", 1],
    heave: ["left_wave", 1], sway: ["right_wave", 1] },
  ROV_CHN: { surge: ["left_ud", 1], roll: ["left_lr", 1], pitch: ["right_ud", -1], yaw: ["right_lr", 1],
    heave: ["left_wave", 1], sway: ["right_wave", 1] },
  UAV_USA: { heave: ["left_ud", 1], yaw: ["left_lr", 1], surge: ["right_ud", 1], sway: ["right_lr", 1],
    pitch: ["left_wave", 1], roll: ["right_wave", 1] },
  UAV_JPN: { surge: ["left_ud", 1], yaw: ["left_lr", 1], heave: ["right_ud", 1], sway: ["right_lr", 1],
    pitch: ["left_wave", 1], roll: ["right_wave", 1] },
  UAV_CHN: { surge: ["left_ud", 1], sway: ["left_lr", 1], heave: ["right_ud", 1], yaw: ["right_lr", 1],
    pitch: ["left_wave", 1], roll: ["right_wave", 1] },
};

function axesOf(mode) {
  return OPERATION_AXES[mode] || OPERATION_AXES.ROV_USA;
}

export function layoutLabel(layout) {
  return STRINGS.layouts[layout] || STRINGS.layouts.console;
}

// The pilot axis a stick channel drives in an operation mode: {axis, sign}, or null.
export function channelAxis(channel, mode) {
  for (const [axis, [name, sign]] of Object.entries(axesOf(mode))) {
    if (name === channel) return { axis, sign };
  }
  return null;
}

// The stick channel and sign that drive a pilot axis in an operation mode, or null.
export function axisChannel(axis, mode) {
  const entry = axesOf(mode)[axis];
  return entry ? { channel: entry[0], sign: entry[1] } : null;
}

// Keyboard rows the player may rebind: flight actions handled by the input layer (not HUD, settings or modifiers).
export function keyRebindable(row) {
  return row.context === "flight" && !row.owner && !row.modifier && row.action !== "pause" && !!row.keys;
}

function sameKeys(a, b) {
  return a.length === b.length && a.every((code, index) => code === b[index]);
}

// The binding table with the keys of a layout and the player's own key choices applied. overrides: action -> codes.
export function keyboardRows(layout = "console", overrides = {}) {
  const layoutKeys = LAYOUT_KEYS[layout] || LAYOUT_KEYS.console;
  return BINDINGS.map(function withKeys(row) {
    if (!keyRebindable(row)) return row;
    const chosen = overrides?.[row.action] ?? layoutKeys[row.action];
    if (!Array.isArray(chosen) || sameKeys(chosen, row.keys)) return row;
    return { ...row, keys: [...chosen] };
  });
}

// Key collisions (same key, same context, two actions) of a layout plus overrides; empty when the choice is valid.
export function keyCollisions(layout = "console", overrides = {}) {
  return findCollisions(keyboardRows(layout, overrides)).filter((entry) => entry.input.startsWith("key:"));
}

// Key captions [positive, negative] that move a pilot axis with these rows in an operation mode; [] when unbound.
export function pilotAxisKeys(axis, rows = BINDINGS, mode = "ROV_USA") {
  const own = rows.find((row) => row.action === axis && row.pilot);
  if (own?.keys?.length === 2) return own.keys.map(keyLabel);
  const drive = axisChannel(axis, mode);
  const channel = drive && rows.find((row) => row.action === drive.channel);
  if (channel?.keys?.length !== 2) return [];
  const keys = channel.keys.map(keyLabel);
  return drive.sign < 0 ? [keys[1], keys[0]] : keys;
}

// First key caption bound to an action in these rows, or "" when it has none.
export function actionKey(action, rows = BINDINGS) {
  const code = rows.find((row) => row.action === action)?.keys?.[0];
  return code ? keyLabel(code) : "";
}

export function bindingRow(action) {
  return ROWS.get(action) || null;
}

export function actionLabel(action) {
  return STRINGS.actions[action] || action;
}

export function contextLabel(context) {
  return STRINGS.contexts[context] || context;
}

// Physical sources named by a binding, without sign or threshold decoration.
export function inputIds(binding) {
  const parts = Array.isArray(binding) ? binding : [binding];
  const ids = [];
  for (const part of parts) {
    const match = /^-?([ab]\d+)~?$/.exec(part || "");
    if (match) ids.push(match[1]);
  }
  return ids;
}

export function chordIds(binding) {
  if (typeof binding !== "string" || !binding.includes("+")) return [];
  return binding.split("+").map((part) => part.trim());
}

function claims(row, binding) {
  if (row.gesture === "chord") return [{ input: `pad:${binding}`, gesture: "chord" }];
  return inputIds(binding).map((id) => ({ input: `pad:${id}`, gesture: row.gesture || "press" }));
}

function conflicting(users) {
  if (users.length < 2) return false;
  if (users.length > 2) return true;
  const gestures = users.map((user) => user.gesture).sort();
  return !(gestures[0] === "hold" && gestures[1] === "tap");
}

// Every input shared by more than one action inside the same context. An empty list is the invariant.
export function findCollisions(rows = BINDINGS, bindings = null) {
  const collisions = [];
  for (const context of CONTEXTS) {
    const users = new Map();
    function use(input, action, gesture) {
      if (!users.has(input)) users.set(input, []);
      users.get(input).push({ action, gesture });
    }
    for (const row of rows) {
      if (row.context !== context) continue;
      const binding = bindings && row.action in bindings ? bindings[row.action] : row.pad;
      for (const claim of claims(row, binding)) use(claim.input, row.action, claim.gesture);
      for (const code of row.keys || []) use(`key:${code}`, row.action, "press");
    }
    for (const [input, list] of users) {
      if (conflicting(list)) collisions.push({ context, input, actions: list.map((user) => user.action) });
    }
  }
  return collisions;
}

function rebindable(row) {
  return row.context !== "menu" && row.gesture !== "chord" && !row.modifier && !row.pilot;
}

// Rebindable gamepad defaults: every action outside the fixed menu navigation; "" means keyboard only.
export function defaultPadBindings() {
  const result = {};
  for (const row of BINDINGS) {
    if (!rebindable(row)) continue;
    result[row.action] = Array.isArray(row.pad) ? [...row.pad] : row.pad || "";
  }
  return result;
}

// Fixed menu-context pad sources (not rebindable, so absent from the stored bindings). The flight input layer adds
// them so a feature module's menu-context actions (the deck checklist) see the pad.
export function menuPadBindings() {
  const result = {};
  for (const row of BINDINGS) {
    if (row.context === "menu" && row.pad) result[row.action] = row.pad;
  }
  return result;
}

// Stored bindings keep the user's choices; unknown actions and stale copies of moved defaults are dropped.
export function migrateBindings(stored = {}, version = 1) {
  const result = defaultPadBindings();
  for (const [action, binding] of Object.entries(stored || {})) {
    if (!(action in result)) continue;
    if (version < BINDINGS_VERSION && LEGACY_DEFAULTS[action] === binding) continue;
    result[action] = binding;
  }
  return result;
}

// The row that owns a keyboard code in the highest active context, or null.
export function keyRow(code, active, rows = BINDINGS) {
  let best = null;
  for (const row of rows) {
    if (!row.keys?.includes(code) || !active.has(row.context)) continue;
    if (!best || CONTEXTS.indexOf(row.context) > CONTEXTS.indexOf(best.context)) best = row;
  }
  return best;
}

export function axisKeys(rows = BINDINGS) {
  const result = {};
  for (const row of rows) {
    if (row.axis) result[row.action] = row.keys;
  }
  return result;
}

function level(context) {
  return CONTEXTS.indexOf(context);
}

function rawValue(id, snapshot) {
  const list = id[0] === "a" ? snapshot.axes : snapshot.buttons;
  return list?.[Number(id.slice(1))] || 0;
}

// Stateful per-frame resolution of gamepad values: context ownership, press latching and gestures.
export function createResolver(rows = BINDINGS) {
  const owner = new Map();
  const downAt = new Map();
  function claimButtons(top, snapshot) {
    for (const id of [...owner.keys()]) {
      if (id[0] === "b" && rawValue(id, snapshot) <= 0.5) owner.delete(id);
    }
    for (const [id, context] of top) {
      if (id[0] === "a") owner.set(id, context);
      else if (rawValue(id, snapshot) > 0.5 && !owner.has(id)) owner.set(id, context);
    }
  }
  function ownedBy(id, context, top) {
    return (owner.get(id) ?? top.get(id)) === context;
  }
  function partValue(part, context, top, snapshot) {
    const [id] = inputIds(part);
    if (!id || !ownedBy(id, context, top)) return 0;
    return bindingValue(part, snapshot);
  }
  function gestureValue(row, value, owned, shared, now) {
    const gesture = row.gesture || "press";
    if (gesture === "press" || (gesture === "tap" && !shared)) return value;
    const pressed = owned && value > 0.5;
    if (pressed) {
      if (!downAt.has(row.action)) downAt.set(row.action, now);
      return gesture === "hold" && now - downAt.get(row.action) >= HOLD_MS ? 1 : 0;
    }
    const started = downAt.get(row.action);
    downAt.delete(row.action);
    return gesture === "tap" && owned && started != null && now - started < HOLD_MS ? 1 : 0;
  }
  // bindings: action → pad source. active: Set of context names. Returns action → resolved value.
  function resolve(bindings, snapshot, active, now) {
    const live = rows.filter((row) => active.has(row.context) && row.gesture !== "chord" && bindings[row.action]);
    const top = new Map();
    const holds = new Set();
    for (const row of live) {
      for (const id of inputIds(bindings[row.action])) {
        if (!top.has(id) || level(row.context) > level(top.get(id))) top.set(id, row.context);
        if (row.gesture === "hold") holds.add(`${row.context}:${id}`);
      }
    }
    claimButtons(top, snapshot);
    const values = {};
    for (const row of live) {
      const binding = bindings[row.action];
      const ids = inputIds(binding);
      const value = Array.isArray(binding)
        ? partValue(binding[0], row.context, top, snapshot) - partValue(binding[1], row.context, top, snapshot)
        : partValue(binding, row.context, top, snapshot);
      const owned = ids.every((id) => ownedBy(id, row.context, top));
      const shared = ids.some((id) => holds.has(`${row.context}:${id}`));
      values[row.action] = gestureValue(row, value, owned, shared, now);
    }
    return values;
  }
  // Hand every button that is down to the exclusive menu context until it is released.
  function block(snapshot) {
    downAt.clear();
    (snapshot?.buttons || []).forEach(function claimPressed(value, index) {
      if (value > 0.5) owner.set(`b${index}`, "menu");
    });
  }
  return { resolve, block };
}

export function keyLabel(code) {
  if (STRINGS.keys[code]) return STRINGS.keys[code];
  return code.replace(/^Key|^Digit/, "");
}

// faces: captions of the active controller family by standard index: the four face buttons, or a longer list
// (glyphs.js padNames) that also names the shoulders, triggers and menu buttons. Gaps fall back to STRINGS.pad.
export function padLabel(binding, faces = STRINGS.pad.slice(0, 4)) {
  const chord = chordIds(binding);
  if (chord.length) return chord.map((part) => padLabel(part, faces)).join(" + ");
  const names = inputIds(binding).map(function sourceName(id) {
    const index = Number(id.slice(1));
    if (id[0] === "a") return STRINGS.axes[index] || id;
    return faces?.[index] || STRINGS.pad[index] || id;
  });
  return names.join(" / ");
}

// A stick channel is named by what it does in the operation mode (前進／後退), not by the stick it is on.
function rowLabel(row, mode) {
  if (!row.axis || row.pilot) return actionLabel(row.action);
  const meaning = channelAxis(row.action, mode);
  if (!meaning) return actionLabel(row.action);
  return STRINGS.meanings[meaning.axis][meaning.sign < 0 ? 1 : 0];
}

// One entry per action for on-screen help: every key and pad source that the table declares.
// rows: the binding table with the active keyboard layout (keyboardRows); operationMode names the stick channels.
export function hintItems({
  contexts = ["flight", "tool", "dialogue"], axes = false, faces, bindings, rows = BINDINGS,
  operationMode = "ROV_USA",
} = {}) {
  const items = [];
  for (const row of rows) {
    if (!contexts.includes(row.context) || (!axes && row.axis)) continue;
    const keys = [...new Set((row.keys || []).map(keyLabel))];
    const source = bindings && row.action in bindings ? bindings[row.action] : row.pad;
    let pad = source ? padLabel(source, faces) : "";
    if (pad && row.gesture === "hold") pad = `${STRINGS.hold} ${pad}`;
    if (!keys.length && !pad) continue;
    const note = row.context === "flight" ? "" : contextLabel(row.context);
    const label = rowLabel(row, operationMode);
    items.push({ action: row.action, context: row.context, label, keys, pad, note });
  }
  return items;
}

// Compact plain text for the HUD help card and other text-only surfaces.
export function hintText(options = {}) {
  return hintItems(options)
    .map(function itemText(item) {
      const sources = [item.keys.join(" "), item.pad].filter(Boolean).join(" / ");
      const label = item.note ? `${item.label}（${item.note}）` : item.label;
      return `${sources} ${label}`;
    })
    .join(STRINGS.separator);
}
