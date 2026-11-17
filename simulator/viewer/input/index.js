// Own keyboard, touch and gamepad input; app retains transport and simulator authority guards.
import { CHANNELS as CH, radial, curve } from "./actions.js";
import {
  BINDINGS_VERSION,
  CONTEXTS,
  actionKey,
  axisChannel,
  axisKeys,
  bindingRow,
  chordIds,
  createResolver,
  keyRow,
  menuPadBindings,
  migrateBindings,
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
const database = await fetch(new URL("./controller-db.json", import.meta.url)).then((r) => r.json());
const clamp = (v, a, b) => Math.max(a, Math.min(b, v));
const desktopSettings = await window.rovDesktop?.readInput?.();
export function installInput({ blocked, camera, tick, preferred, gain, setMode, arm }) {
  const $ = (id) => document.getElementById(id);
  let settings = {};
  try {
    settings = JSON.parse(localStorage.getItem("rov.input.v1") || "{}");
  } catch {}
  if (desktopSettings && Object.keys(desktopSettings).length) settings = desktopSettings;
  settings.custom ||= {};
  settings.bindings = migrateBindings(settings.bindings, settings.bindingsVersion);
  settings.bindingsVersion = BINDINGS_VERSION;
  settings.channels ||= {};
  const features = createFeatureActions((name, fallback) => settings.bindings[name] ?? fallback);
  const resolver = createResolver();
  const registered = new Map();
  const everyContext = new Set(CONTEXTS);
  const settingsChord = chordIds(bindingRow("settings").pad).map((id) => Number(id.slice(1)));
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
  if (migratePadHapticsFromInput(settings, fidelity)) {
    try {
      localStorage.setItem("rov.input.v1", JSON.stringify(settings));
    } catch {}
    window.rovDesktop?.rememberInput?.(settings);
  }
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
  const keys = new Set();
  // Keyboard rows of the active layout (console sticks or game pilot axes) with the player's rebound keys.
  let rows = rowsFor(settings, fidelity);
  let keyboardAxes = axisKeys(rows);
  let operationMode = "ROV_USA";
  let rowsSignature = "";
  function refreshRows() {
    const next = rowsFor(settings, fidelity);
    const signature = JSON.stringify(next.map((row) => row.keys || []));
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
  addEventListener("keydown", (e) => {
    if (blocked() || document.getElementById("inputSettings")?.open) return;
    if (isText(e.target) || e.ctrlKey || e.metaKey || e.altKey) return;
    document.dispatchEvent(new CustomEvent("rov-input-device", { detail: "" }));
    if (e.code.startsWith("Shift")) keys.add(e.code);
    // The table decides which action owns this key in the contexts that are active right now.
    const row = keyRow(e.code, activeContexts(), rows);
    if (!row || row.owner || row.modifier) return;
    e.preventDefault();
    if (e.repeat) return;
    keys.add(e.code);
    if (!row.axis) {
      if (keyHandlers[row.action]) keyHandlers[row.action]();
      else features.run(row.action);
    }
    tick();
  });
  addEventListener("keyup", (e) => {
    keys.delete(e.code);
    const row = keyRow(e.code, everyContext, rows);
    if (row?.action === "photo") hold.photo.delete("kb");
    if (row?.action === "record") hold.record.delete("kb");
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

  function save() {
    try {
      localStorage.setItem("rov.input.v1", JSON.stringify(settings));
    } catch {}
    window.rovDesktop?.rememberInput?.(settings);
  }
  addEventListener("keydown", function openSettings(e) {
    if (e.code === "F8") document.getElementById("inputSettingsButton").click();
  });
  const panel = installSettings(settings, save, haptics, setMode, refreshRows);
  refreshRows();
  function readPad() {
    const now = performance.now();
    const featureDt = Math.min(.25, (now - featureTime) / 1000);
    featureTime = now;
    hudActions = {};
    frame = devices.poll(panel.selected() || preferred());
    panel.update(frame);
    const padId = frame.pad ? `${frame.pad.index}:${frame.pad.id}` : "";
    if (padId !== lastPadId) previous = {};
    lastPadId = padId;
    if (settingsChord.every((index) => frame.snapshot?.buttons[index] > 0.5)) {
      if (!previous.settings) document.getElementById("inputSettingsButton").click();
      resolver.block(frame.snapshot);
      previous.settings = true;
    } else previous.settings = false;
    if (!frame.pad || !frame.snapshot.known || blocked() || panel.open()) {
      features.sample(null, 0);
      // Buttons held while a panel owns the pad must be released before flight sees them again.
      resolver.block(frame.snapshot);
      previous = { settings: previous.settings };
      hold.photo.delete("pad");
      hold.record.delete("pad");
      return null;
    }
    const snapshot = { ...frame.snapshot, axes: [...frame.snapshot.axes] };
    for (const offset of [0, 2]) {
      const pair = radial(
        snapshot.axes[offset] || 0,
        snapshot.axes[offset + 1] || 0,
        settings.inner ?? 0.08,
        settings.outer ?? 0.02,
      );
      snapshot.axes.splice(offset, 2, ...pair);
    }
    // Menu rows are fixed, so they are not in the stored bindings; without them a feature module's menu actions
    // (deck checklist focus and confirm) would never see the pad.
    const sources = { ...menuPadBindings(), ...settings.bindings };
    const actions = resolver.resolve(sources, snapshot, activeContexts(), now);
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
    previous = { ...actions, settings: previous.settings };
    const values = JSON.stringify(snapshot);
    if (values !== lastPadValues) {
      document.dispatchEvent(new CustomEvent("rov-input-device", { detail: frame.pad.id }));
      lastPadValues = values;
    }
    return { ...Object.fromEntries(CH.map((c) => [c, actions[c] || 0])), id: frame.pad.id };
  }
  function keyAxis(name) {
    const [positive, negative] = keyboardAxes[name] || [];
    return +keys.has(positive) - +keys.has(negative);
  }
  // Game-layout pilot axes drive the stick channel that moves that axis in the current operation mode.
  function pilotChannels() {
    const result = Object.fromEntries(CH.map((c) => [c, 0]));
    for (const row of rows) {
      if (!row.pilot || !row.keys?.length) continue;
      const drive = axisChannel(row.action, operationMode);
      if (drive) result[drive.channel] += drive.sign * keyAxis(row.action);
    }
    return result;
  }
  function sample() {
    const pad = readPad();
    const g = keys.has("ShiftLeft") || keys.has("ShiftRight") ? 1 : gain();
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
    panel.registerActions(resolved);
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
