// Own keyboard, touch and gamepad input; app retains transport and simulator authority guards.
import { CHANNELS as CH, PRESETS, BUTTONS, bindingValue, radial, curve } from "./actions.js";
import {createFeatureActions} from "./feature_actions.js";
import { createDevices } from "./devices.js";
import { createHaptics } from "./haptics.js";
import { installSettings } from "./settings.js";
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
  settings.bindings = { ...PRESETS.current, ...BUTTONS, ...settings.bindings };
  settings.channels ||= {};
  const features = createFeatureActions((name, fallback) => settings.bindings[name] ?? fallback);
  let featureTime = performance.now();
  const devices = createDevices(database, settings.custom);
  let frame = { devices: [], pad: null };
  let previous = {};
  let hudActions = {};
  let lastPadValues = "";
  let lastPadId = "";
  const stickStyle = document.createElement("style");
  stickStyle.textContent = "@media (pointer:fine){#sticks{visibility:hidden}}";
  document.head.append(stickStyle);
  document.addEventListener("rov-input-device", function devicePresentation(event) {
    if (event.detail !== "touch") document.getElementById("sticks").style.visibility = "hidden";
    else document.getElementById("sticks").style.visibility = "visible";
  });
  const haptics = createHaptics(() => frame.pad, settings);
  const rc = { rc_lock: 1, keep_depth: 0, left_switch: 0, right_switch: 0, assist: 2, profile: "normal" };
  const hold = { photo: new Set(), record: new Set() };
  const keys = new Set();
  const touch = Object.fromEntries(CH.map((c) => [c, 0]));
  const out = Object.fromEntries(CH.map((c) => [c, 0])); // combined −1..1

  const toggleLock = () => {
    rc.rc_lock = rc.rc_lock ? 0 : 1;
    haptics.pulse("unlock");
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

  const FLIGHT = new Set([
    "KeyW",
    "KeyS",
    "KeyA",
    "KeyD",
    "ArrowUp",
    "ArrowDown",
    "ArrowLeft",
    "ArrowRight",
    "KeyQ",
    "KeyE",
    "KeyZ",
    "KeyC",
    "Space",
    "KeyH",
    "KeyP",
    "KeyR",
    "KeyM",
    "KeyL",
    "KeyV",
    "KeyF",
    "KeyG",
  ]);
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
    if (features.key(e)) {
      e.preventDefault();
      tick();
      return;
    }
    if (!FLIGHT.has(e.code)) return;
    e.preventDefault();
    if (e.repeat) return;
    keys.add(e.code);
    switch (e.code) {
      case "Space":
        toggleLock();
        break;
      case "KeyH":
        toggleDepth();
        break;
      case "KeyM":
        cycleMode();
        break;
      case "KeyL":
        cycleLed();
        break;
      case "KeyF":
        rc.assist = (rc.assist + 1) % 3;
        break;
      case "KeyG":
        rc.profile = ["cine", "normal", "sport"][(["cine", "normal", "sport"].indexOf(rc.profile) + 1) % 3];
        break;
      case "KeyV":
        camera();
        break;
      case "KeyP":
        hold.photo.add("kb");
        break;
      case "KeyR":
        hold.record.add("kb");
        break;
    }
    tick();
  });
  addEventListener("keyup", (e) => {
    keys.delete(e.code);
    if (e.code === "KeyP") hold.photo.delete("kb");
    if (e.code === "KeyR") hold.record.delete("kb");
    if (FLIGHT.has(e.code) && !isText(e.target)) e.preventDefault();
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
  const panel = installSettings(settings, save, haptics, setMode);
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
    if (frame.snapshot?.buttons[8] > 0.5 && frame.snapshot?.buttons[9] > 0.5) {
      if (!previous.settings) document.getElementById("inputSettingsButton").click();
      previous.settings = true;
    } else previous.settings = false;
    if (!frame.pad || !frame.snapshot.known || blocked() || panel.open()) {
      features.sample(null, 0);
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
    const actions = Object.fromEntries(
      Object.entries(settings.bindings).map(([k, b]) => [k, bindingValue(b, snapshot)]),
    );
    const consumed = features.sample(snapshot, featureDt);
    for (const channel of consumed) actions[channel] = 0;
    hudActions = actions;
    const handlers = {
      lock: toggleLock,
      depth: toggleDepth,
      mode: cycleMode,
      light: cycleLed,
      camera,
      arm,
      assist: () => {
        rc.assist = (rc.assist + 1) % 3;
      },
      profile: () => {
        rc.profile = ["cine", "normal", "sport"][(["cine", "normal", "sport"].indexOf(rc.profile) + 1) % 3];
      },
    };
    for (const [name, handler] of Object.entries(handlers)) {
      if (actions[name] > 0.5 && !(previous[name] > 0.5)) handler();
    }
    for (const name of ["photo", "record"]) {
      if (actions[name] > 0.5) hold[name].add("pad");
      else hold[name].delete("pad");
    }
    if (actions.photo > 0.5 && !(previous.photo > 0.5)) haptics.pulse("photo");
    previous = { ...actions, settings: previous.settings };
    const values = JSON.stringify(snapshot);
    if (values !== lastPadValues) {
      document.dispatchEvent(new CustomEvent("rov-input-device", { detail: frame.pad.id }));
      lastPadValues = values;
    }
    return { ...Object.fromEntries(CH.map((c) => [c, actions[c] || 0])), id: frame.pad.id };
  }
  function sample() {
    const pad = readPad();
    const g = keys.has("ShiftLeft") || keys.has("ShiftRight") ? 1 : gain();
    const bindings = [
      ["KeyW", "KeyS"],
      ["KeyD", "KeyA"],
      ["ArrowUp", "ArrowDown"],
      ["ArrowRight", "ArrowLeft"],
      ["KeyE", "KeyQ"],
      ["KeyC", "KeyZ"],
    ];
    CH.forEach((c, i) => {
      const [positive, negative] = bindings[i];
      const value =
        blocked() || panel.open() ? 0 : (+keys.has(positive) - +keys.has(negative)) * g + touch[c] + (pad?.[c] || 0);
      out[c] = curve(clamp(value, -1, 1), settings.channels[c]);
    });
    return pad;
  }
  let lastImpact = "";
  let tensionHigh = false;
  function feedback(state) {
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
    };
  }
  function registerActions(definitions) {
    features.register(definitions);
    panel.registerActions(definitions);
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
  };
}
