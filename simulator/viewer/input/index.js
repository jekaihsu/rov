// Own keyboard, touch and gamepad input; app retains transport and simulator authority guards.
import { CHANNELS as CH, shapeStick, curve } from "./actions.js";
import {
  actionKey,
  axisChannel,
  axisKeys,
  bindingRow,
  chordIds,
  createResolver,
  keyRow,
} from "./bindings.js";
import { publishKeyRows, rowsFor } from "./keyboard_layout.js";
import {createFeatureActions} from "./feature_actions.js";
import { createDevices } from "./devices.js";
import { renderKeyHints } from "./hints.js";
import { installTouchSticks } from "./touch_sticks.js";
import { createHaptics } from "./haptics.js";
import { migratePadHapticsFromInput } from "./haptics_fidelity.js";
import { installSettings } from "./settings.js";
import { getFidelity } from "../fidelity.js";
import { inputPreferences as settings, saveInputPreferences as save } from './preferences.js';
const database = await fetch(new URL("./controller-db.json", import.meta.url)).then((r) => r.json());
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
export function installInput({ blocked, camera, tick, preferred, gain, setMode, arm }) {
  const $ = (id) => document.getElementById(id);
  const features = createFeatureActions((name, fallback) => settings.bindings[name] ?? fallback);
  const resolver = createResolver();
  const registered = new Map();

  // A context above flight is active while any action registered for it reports itself enabled.
  function activeContexts() {
    const active = new Set(["flight"]);
    for (const [name, action] of registered) {
      const context = bindingRow(name).context;
      if (context !== "flight" && action.enabled?.() !== false) active.add(context);
    }
    return active;
  }
  let featureTime = performance.now();
  const devices = createDevices(database, settings.custom);
  let frame = { devices: [], pad: null };
  let previous = {};
  let hudActions = {};
  let lastPadValues = "";
  let lastPadId = "";
  installTouchSticks({ element: $("sticks"), preference: $("optSticks") });
  // Assist level, flight profile and pad haptics belong to the fidelity profile.
  const fidelity = getFidelity();
  if (migratePadHapticsFromInput(settings, fidelity)) save();
  const haptics = createHaptics(() => frame.pad, settings, fidelity);
  const rc = { rc_lock: 1, keep_depth: 0, left_switch: 0, right_switch: 0 };
  function mirrorFidelity() {
    rc.assist = fidelity.get("assistLevel");
    rc.profile = fidelity.get("flightProfile");
  }
  mirrorFidelity();
  fidelity.subscribe(mirrorFidelity);
  function cycleAssist() {
    fidelity.set("assistLevel", (rc.assist + 1) % 3);
  }
  function cycleProfile() {
    const profiles = ["cine", "normal", "sport"];
    fidelity.set("flightProfile", profiles[(profiles.indexOf(rc.profile) + 1) % 3]);
  }
  const hold = { photo: new Set(), record: new Set() };
  const keys = new Map();
  // Keyboard rows of the active layout (console sticks or game pilot axes) with the player's rebound keys.
  let rows = rowsFor(settings, fidelity);
  let keyboardAxes = axisKeys(rows);
  let operationMode = "ROV_USA";
  let rowsSignature = "";
  function refreshRows() {
    const next = rowsFor(settings, fidelity);
    const signature = JSON.stringify(next.map((row) => [row.keys, row.pad]));
    if (signature !== rowsSignature) {
      // A held key may now mean something else; release everything rather than leave a stuck axis.
      rowsSignature = signature;
      rows = next;
      keyboardAxes = axisKeys(rows);
      keys.clear();
    }
    publishKeyRows(rows, operationMode);
    renderKeyHints(document.getElementById("keyHints"), { bindings: settings.bindings, rows, operationMode });
  }
  fidelity.subscribe(refreshRows);
  const touch = Object.fromEntries(CH.map((c) => [c, 0]));
  const out = Object.fromEntries(CH.map((c) => [c, 0])); // combined −1..1

  // The rumble follows the vehicle's confirmed lock state in feedback(), not the key press, so a refused unlock
  // (deck procedure, failsafe latch) does not feel like one.
  const toggleLock = () => {
    rc.rc_lock = rc.rc_lock ? 0 : 1;
  };
  const toggleDepth = () => {
    rc.keep_depth = rc.keep_depth ? 0 : 1;
  };
  const cycleMode = () => {
    rc.left_switch = (rc.left_switch + 1) % 3;
  };
  const cycleLed = () => {
    rc.right_switch = (rc.right_switch + 1) % 3;
  };

  const keyHandlers = {
    lock: toggleLock,
    depth: toggleDepth,
    mode: cycleMode,
    light: cycleLed,
    assist: cycleAssist,
    profile: cycleProfile,
    camera,
    arm,
    photo: function holdPhotoKey() {
      hold.photo.add("kb");
    },
    record: function holdRecordKey() {
      hold.record.add("kb");
    },
  };
  const isText = (el) =>
    el &&
    (el.tagName === "SELECT" ||
      el.tagName === "TEXTAREA" ||
      (el.tagName === "INPUT" && !["range", "checkbox"].includes(el.type)));
  function resolveKey(code) {
    if (blocked() || document.getElementById("inputSettings")?.open) return null;
    return keyRow(code, activeContexts(), rows);
  }
  addEventListener("keydown", (e) => {
    if (isText(e.target)) return;
    const modifierKey = /^(Control|Meta|Alt)(Left|Right)$/.test(e.code);
    if (!modifierKey && (e.ctrlKey || e.metaKey || e.altKey)) return;
    // The table decides which action owns this key in the contexts that are active right now.
    const row = resolveKey(e.code);
    if (!row) return;
    document.dispatchEvent(new CustomEvent("rov-input-device", { detail: "" }));
    if (row.owner === "hud") return;
    e.preventDefault();
    if (e.repeat) return;
    keys.set(e.code, row.action);
    if (row.owner === "settings") {
      document.getElementById("inputSettingsButton").click();
      return;
    }
    if (!row.axis) {
      if (keyHandlers[row.action]) keyHandlers[row.action]();
      else features.run(row.action);
    }
    tick();
  });
  addEventListener("keyup", (e) => {
    const action = keys.get(e.code);
    keys.delete(e.code);
    const row = bindingRow(action);
    hold[action]?.delete("kb");
    if (row && !row.owner && !row.modifier && !isText(e.target)) e.preventDefault();
  });
  addEventListener("blur", () => {
    keys.clear();
    hold.photo.clear();
    hold.record.clear();
    CH.forEach(function neutral(channel) {
      touch[channel] = 0;
      out[channel] = 0;
    });
    rc.rc_lock = 1;
  });
  // on-screen sticks and wheels
  function bindStick(el, chUD, chLR) {
    let id = null;
    const set = (e) => {
      const r = el.getBoundingClientRect(),
        R = r.width / 2;
      let x = (e.clientX - r.left - R) / (R * 0.8),
        y = -(e.clientY - r.top - R) / (R * 0.8);
      const m = Math.hypot(x, y);
      if (m > 1) {
        x /= m;
        y /= m;
      }
      touch[chLR] = x;
      touch[chUD] = y;
    };
    el.addEventListener("pointerdown", (e) => {
      document.dispatchEvent(new CustomEvent("rov-input-device", { detail: "touch" }));
      id = e.pointerId;
      el.setPointerCapture(id);
      set(e);
      e.preventDefault();
    });
    el.addEventListener("pointermove", (e) => {
      if (e.pointerId === id) set(e);
    });
    const end = (e) => {
      if (e.pointerId !== id) return;
      id = null;
      touch[chLR] = 0;
      touch[chUD] = 0;
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("lostpointercapture", end);
  }
  function bindWheel(el, ch) {
    let id = null;
    const set = (e) => {
      const r = el.getBoundingClientRect();
      touch[ch] = clamp(((e.clientX - r.left) / r.width - 0.5) * 2.3, -1, 1);
    };
    el.addEventListener("pointerdown", (e) => {
      document.dispatchEvent(new CustomEvent("rov-input-device", { detail: "touch" }));
      id = e.pointerId;
      el.setPointerCapture(id);
      set(e);
      e.preventDefault();
    });
    el.addEventListener("pointermove", (e) => {
      if (e.pointerId === id) set(e);
    });
    const end = (e) => {
      if (e.pointerId !== id) return;
      id = null;
      touch[ch] = 0;
    };
    el.addEventListener("pointerup", end);
    el.addEventListener("pointercancel", end);
    el.addEventListener("lostpointercapture", end);
  }
  bindStick($("stickL"), "left_ud", "left_lr");
  bindStick($("stickR"), "right_ud", "right_lr");
  bindWheel($("wheelL"), "left_wave");
  bindWheel($("wheelR"), "right_wave");

  // panel buttons
  $("bLock").onclick = () => {
    toggleLock();
    tick();
  };
  $("bDepth").onclick = () => {
    toggleDepth();
    tick();
  };
  $("bMode").onclick = () => {
    cycleMode();
    tick();
  };
  $("bLed").onclick = () => {
    cycleLed();
    tick();
  };
  for (const [id, k] of [
    ["bPhoto", "photo"],
    ["bRec", "record"],
  ]) {
    const b = $(id);
    b.addEventListener("pointerdown", (e) => {
      b.setPointerCapture(e.pointerId);
      hold[k].add("ui");
      tick();
    });
    const up = () => {
      hold[k].delete("ui");
      tick();
    };
    b.addEventListener("pointerup", up);
    b.addEventListener("pointercancel", up);
  }

  const panel = installSettings(settings, save, haptics, setMode, refreshRows);
  refreshRows();
  function readPad() {
    const now = performance.now();
    const featureDt = Math.min(.25, (now - featureTime) / 1000);
    featureTime = now;
    hudActions = {};
    frame = devices.poll(panel.selected() || preferred());
    const editing = panel.open();
    panel.update(frame);
    const padId = frame.pad ? `${frame.pad.index}:${frame.pad.id}` : "";
    if (padId !== lastPadId) previous = {};
    lastPadId = padId;
    const settingsSource = settings.bindings.settings;
    const chord = chordIds(settingsSource);
    const openSettings = chord.length && chord.every(id => frame.snapshot?.buttons[Number(id.slice(1))] > 0.5);
    if (!editing && !panel.open() && openSettings) {
      if (!previous.chord) document.getElementById("inputSettingsButton").click();
      resolver.block(frame.snapshot);
      previous.chord = true;
    } else previous.chord = false;
    if (editing || panel.open()) {
      keys.clear();
      hold.photo.delete("kb");
      hold.record.delete("kb");
    }
    if (blocked() || editing || panel.open()) {
      features.sample(null, 0);
      // Buttons held while a panel owns the pad must be released before flight sees them again.
      resolver.block(frame.snapshot);
      previous = { chord: previous.chord };
      hold.photo.delete("pad");
      hold.record.delete("pad");
      return null;
    }
    // Keyboard-bound orbit controls, like their analog equivalents, act for the sampled duration.
    for (const [name, action] of registered) {
      if (!action.continuous || action.enabled?.() === false) continue;
      const row = rows.find(row => row.action === name);
      const direction = Number(keys.get(row.keys?.[0]) === name) - Number(keys.get(row.keys?.[1]) === name);
      if (direction) action.run(direction, featureDt);
    }
    if (!frame.pad || !frame.snapshot.known) {
      features.sample(null, 0);
      previous = {};
      hold.photo.delete("pad");
      hold.record.delete("pad");
      return null;
    }
    const snapshot = { ...frame.snapshot, axes: [...frame.snapshot.axes] };
    for (const offset of [0, 2]) {
      const side = offset === 0 ? "left" : "right";
      const pair = shapeStick(snapshot.axes[offset] || 0, snapshot.axes[offset + 1] || 0, {
        inner: fidelity.get(side + "Deadzone"), outer: settings.outer,
        expo: fidelity.get(side + "Response"), invert: fidelity.get(side + "Invert"),
      });
      snapshot.axes.splice(offset, 2, ...pair);
    }
    const actions = resolver.resolve(settings.bindings, snapshot, activeContexts(), now);
    if (actions.settings > 0.5 && !(previous.settings > 0.5)) {
      document.getElementById("inputSettingsButton").click();
      resolver.block(snapshot);
      return null;
    }
    for (const row of rows) {
      if (!row.pilot || !actions[row.action]) continue;
      const drive = axisChannel(row.action, operationMode);
      actions[drive.channel] = (actions[drive.channel] || 0) + drive.sign * actions[row.action];
    }
    const consumed = features.sample(snapshot, featureDt, actions);
    for (const channel of consumed) actions[channel] = 0;
    hudActions = actions;
    const handlers = {
      lock: toggleLock,
      depth: toggleDepth,
      mode: cycleMode,
      light: cycleLed,
      camera,
      arm,
      assist: cycleAssist,
      profile: cycleProfile,
    };
    for (const [name, handler] of Object.entries(handlers)) {
      if (actions[name] > 0.5 && !(previous[name] > 0.5)) handler();
    }
    for (const name of ["photo", "record"]) {
      if (actions[name] > 0.5) hold[name].add("pad");
      else hold[name].delete("pad");
    }
    previous = { ...actions, chord: previous.chord };
    const values = JSON.stringify(snapshot);
    if (values !== lastPadValues) {
      document.dispatchEvent(new CustomEvent("rov-input-device", { detail: frame.pad.id }));
      lastPadValues = values;
    }
    return { ...Object.fromEntries(CH.map((c) => [c, actions[c] || 0])), id: frame.pad.id };
  }
  function keyAxis(name) {
    const [positive, negative] = keyboardAxes[name] || [];
    return Number(keys.get(positive) === name) - Number(keys.get(negative) === name);
  }
  // Game-layout pilot axes drive the stick channel that moves that axis in the current operation mode.
  function pilotChannels() {
    const result = Object.fromEntries(CH.map((c) => [c, 0]));
    for (const row of rows) {
      if (!row.pilot) continue;
      const drive = axisChannel(row.action, operationMode);
      if (drive) result[drive.channel] += drive.sign * keyAxis(row.action);
    }
    return result;
  }
  function sample() {
    const pad = readPad();
    const boost = rows.find(row => row.modifier);
    const g = boost.keys.some(code => keys.get(code) === "boost") || hudActions.boost > 0.5 ? 1 : gain();
    const pilot = pilotChannels();
    CH.forEach((c) => {
      const keyboard = (keyAxis(c) + pilot[c]) * g;
      const value = blocked() || panel.open() ? 0 : keyboard + touch[c] + (pad?.[c] || 0);
      out[c] = curve(clamp(value, -1, 1), settings.channels[c]);
    });
    return pad;
  }
  let lastImpact = "";
  let tensionHigh = false;
  let snagged = false;
  let broken = false;
  let locked = null;
  function edgePulses(state) {
    const nowLocked = state?.locked;
    const changed = locked !== null && nowLocked !== undefined && nowLocked !== locked;
    if (changed) haptics.pulse(nowLocked ? "lock" : "unlock");
    if (nowLocked !== undefined) locked = nowLocked;
    const snag = !!state?.tether?.snagged_on?.length;
    if (snag && !snagged) haptics.pulse("snag");
    snagged = snag;
    const cut = !!state?.tether?.broken;
    if (cut && !broken) haptics.pulse("broken");
    broken = cut;
  }
  function feedback(state) {
    edgePulses(state);
    if (state?.operation_mode && state.operation_mode !== operationMode) {
      operationMode = state.operation_mode;
      refreshRows();
    }
    const impact = state?.events?.at?.(-1);
    if (impact && JSON.stringify(impact) !== lastImpact) {
      lastImpact = JSON.stringify(impact);
      haptics.pulse(impact.severity === "touch" ? "touch" : "hard");
    }
    const high = !!state?.tether?.warn;
    if (high && !tensionHigh) haptics.pulse("tension");
    tensionHigh = high;
  }
  function hudState() {
    return {
      actions: hudActions,
      active:
        !!frame.snapshot?.known &&
        (frame.snapshot.axes.some((value) => Math.abs(value) > 0.15) ||
          frame.snapshot.buttons.some((value) => value > 0.5)),
      pulse: haptics.pulse,
      bindings: settings.bindings,
      keyRows: rows,
      resolveKey,
      operationMode,
    };
  }
  // Feature modules supply behaviour only; the default key, pad source and context come from the table.
  function registerActions(definitions) {
    const resolved = {};
    for (const [name, action] of Object.entries(definitions)) {
      const row = bindingRow(name);
      if (!row) throw new Error(`Input action "${name}" has no row in input/bindings.js`);
      resolved[name] = { ...action, keys: row.keys || [], binding: row.pad || "" };
      registered.set(name, resolved[name]);
    }
    features.register(resolved);
  }
  return {
    rc,
    hold,
    keys,
    touch,
    out,
    toggleLock,
    toggleDepth,
    cycleMode,
    cycleLed,
    sample,
    haptics,
    feedback,
    hudState,
    registerActions,
    keyRows: () => rows,
    keyFor: (action) => actionKey(action, rows),
  };
}
