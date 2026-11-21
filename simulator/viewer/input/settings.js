// Controller setup, live shaping preview and sequential calibration; flight is suspended while open.
import { CHANNELS, PRESETS, curve, radial, bindingValue } from "./actions.js";
import {
  actionLabel, bindingRow, defaultPadBindings, findCollisions, hintItems, inputIds, keyCollisions, keyLabel,
  keyRebindable, layoutLabel,
} from "./bindings.js";
import { keyboardLayout, rowsFor } from "./keyboard_layout.js";
import { getFidelity } from "../fidelity.js";
import { getDisplayPrefs } from "../prefs/display.js";
import {
  CALIBRATION_STEPS, captureCalibrationStep, buildCustomMapping, isNeutral
} from "./calibrate.js";
const STRINGS = {
  title: "手把設定",
  close: "返回",
  auto: "自動選擇",
  current: "現行配置",
  drone: "空拍機式",
  inner: "內圈死區",
  outer: "外圈死區",
  expo: "Expo",
  sensitivity: "靈敏度",
  invert: "反向",
  reset: "重設",
  test: "震動測試",
  strength: "震動強度",
  wizard: "對應精靈",
  prompt: "依序操作指定軸或按鍵，放回中立後再繼續：",
  skip: "略過此鍵",
  done: "映射已儲存",
  bind: "綁定（a0、-a1、b0、b7~；以逗號分隔正負來源）",
  unknown: "未知裝置，請先完成對應精靈",
  collision: "同一情境內有按鍵重複：",
  keyboard: "鍵盤按鍵",
  keyboardHelp: "目前配置：{layout}。點選按鍵後按下新的按鍵，Esc 取消。",
  capture: "請按下新按鍵…",
  keyTaken: "按鍵已被使用，未變更：",
  keySaved: "已儲存",
  keyReset: "還原此配置的預設按鍵",
};
// Fixed menu navigation, read from the menu rows of the binding table.
function menuSource(action) {
  return Number(inputIds(bindingRow(action).pad)[0].slice(1));
}
const NAV = {
  up: menuSource("menuUp"),
  down: menuSource("menuDown"),
  left: menuSource("menuLeft"),
  right: menuSource("menuRight"),
  stick: menuSource("menuStick"),
  accept: menuSource("accept"),
  back: menuSource("back"),
};
// onKeys: called after the player rebinds a keyboard key, so the input layer can pick up the new rows.
export function installSettings(settings, save, haptics, setMode, onKeys = null) {
  const featureActions = new Map();
  const button = document.createElement("button");
  button.textContent = STRINGS.title;
  button.id = "inputSettingsButton";
  (document.querySelector("aside") || document.body).append(button);
  const root = document.createElement("dialog");
  root.id = "inputSettings";
  root.style.cssText =
    "background:rgba(8,18,26,.96);color:#e8f1f5;border:1px solid #4fd1e0;" +
    "border-radius:10px;max-height:84vh;width:640px;overflow:auto;padding:24px";
  root.innerHTML = `<style>#inputSettings label{display:block;margin:12px 0}
    #inputSettings :focus-visible{outline:3px solid #4fd1e0}#inputSettings input{max-width:240px}
    #inputSettings canvas{width:100%;height:120px}</style>`;
  document.body.append(root);
  function element(tag, text, parent = root) {
    const el = document.createElement(tag);
    el.textContent = text;
    parent.append(el);
    return el;
  }
  element("h2", STRINGS.title);
  const close = element("button", STRINGS.close);
  close.onclick = function closeSettings() {
    root.close();
  };
  button.onclick = function openSettings() {
    root.showModal();
  };
  const select = element("select", "");
  const automatic = element("option", STRINGS.auto, select);
  automatic.value = "auto";
  const live = element("pre", "");
  live.style.cssText = "white-space:pre-wrap;max-height:96px;overflow:auto;font:12px monospace";
  const preset = element("select", "");
  for (const key of Object.keys(PRESETS)) element("option", STRINGS[key], preset).value = key;
  preset.onchange = function changePreset() {
    settings.bindings = { ...defaultPadBindings(), ...PRESETS[preset.value] };
    setMode(preset.value === "drone" ? "UAV_USA" : "ROV_USA");
    save();
    renderBindings();
  };
  function slider(label, object, key, min, max, step, fallback) {
    const row = element("label", label);
    const input = element("input", "", row);
    input.type = "range";
    input.min = min;
    input.max = max;
    input.step = step;
    input.value = object[key] ?? fallback;
    input.oninput = function changeSetting() {
      object[key] = +input.value;
      save();
    };
  }
  slider(STRINGS.inner, settings, "inner", 0, 0.5, 0.01, 0.08);
  slider(STRINGS.outer, settings, "outer", 0, 0.3, 0.01, 0.02);
  for (const channel of CHANNELS) {
    const group = element("details", "");
    element("summary", channel, group);
    settings.channels[channel] ||= {};
    // Channel controls use the same persistence path as global shaping.
    for (const [key, max, fallback] of [
      ["expo", 1, 0],
      ["sensitivity", 2, 1],
    ]) {
      const row = element("label", STRINGS[key], group);
      const input = element("input", "", row);
      input.type = "range";
      input.min = 0;
      input.max = max;
      input.step = 0.01;
      input.value = settings.channels[channel][key] ?? fallback;
      input.oninput = function channelChange() {
        settings.channels[channel][key] = +input.value;
        save();
      };
    }
    const row = element("label", STRINGS.invert, group);
    const invert = element("input", "", row);
    invert.type = "checkbox";
    invert.checked = !!settings.channels[channel].invert;
    invert.onchange = function invertChange() {
      settings.channels[channel].invert = invert.checked;
      save();
    };
  }
  const preview = element("select", "");
  for (const channel of CHANNELS) element("option", channel, preview).value = channel;
  const canvas = element("canvas", "");
  canvas.width = 600;
  canvas.height = 120;
  const bindings = element("details", "");
  element("summary", STRINGS.bind, bindings);
  const collisionNote = element("p", "", bindings);
  collisionNote.setAttribute("role", "status");
  const rows = element("div", "", bindings);
  function showCollisions() {
    const collisions = findCollisions(undefined, settings.bindings);
    collisionNote.textContent = collisions.length
      ? STRINGS.collision + collisions.map((entry) => entry.actions.map(actionLabel).join(" / ")).join("；")
      : "";
  }
  function renderBindings() {
    for (const [name, action] of featureActions) settings.bindings[name] ??= action.binding ?? "";
    rows.replaceChildren();
    for (const [name, binding] of Object.entries(settings.bindings)) {
      const row = element("label", featureActions.get(name)?.label || actionLabel(name), rows);
      const input = element("input", "", row);
      input.dataset.binding = name;
      input.value = Array.isArray(binding) ? binding.join(",") : binding;
      input.onchange = function rebind() {
        if (featureActions.has(name) && !input.value.trim()) {
          settings.bindings[name] = "";
          save();
          showCollisions();
          return;
        }
        const parts = input.value.split(",").map((p) => p.trim());
        if (!parts.every((p) => /^-?[ab]\d+~?$/.test(p))) return;
        settings.bindings[name] = parts.length > 1 ? parts.slice(0, 2) : parts[0];
        save();
        showCollisions();
      };
    }
    showCollisions();
  }
  renderBindings();
  mountKeyboard();
  // Mute lives on padHaptics (擬真設定); strength is shared with the display tab (prefs/display.js).
  settings.strength ??= getDisplayPrefs().get("hapticStrength") ?? 1;
  const strengthRow = element("label", STRINGS.strength);
  const strengthInput = element("input", "", strengthRow);
  strengthInput.type = "range";
  strengthInput.min = 0;
  strengthInput.max = 1;
  strengthInput.step = 0.05;
  strengthInput.value = settings.strength;
  strengthInput.oninput = function changeStrength() {
    settings.strength = +strengthInput.value;
    getDisplayPrefs().set("hapticStrength", settings.strength);
    save();
  };
  element("button", STRINGS.test).onclick = function test() {
    haptics.pulse("hard");
  };
  let wizard = null;
  let release = false;
  let pad = null;
  const prompt = element("p", "");
  function next(binding) {
    wizard.values.push(binding);
    prompt.dataset.step = wizard.values.length;
    release = true;
    prompt.dataset.ready = "false";
    if (wizard.values.length === CALIBRATION_STEPS.length) {
      settings.custom[pad.id] = buildCustomMapping(wizard.values);
      wizard = null;
      save();
      prompt.textContent = STRINGS.done;
    }
  }
  element("button", STRINGS.wizard).onclick = function startWizard() {
    if (!pad) return;
    wizard = { values: [], baseline: [...pad.axes] };
    release = false;
  };
  element("button", STRINGS.skip).onclick = function skip() {
    if (wizard) next("");
  };
  element("button", STRINGS.reset).onclick = function reset() {
    localStorage.removeItem("rov.input.v1");
    window.rovDesktop?.rememberInput?.({});
    location.reload();
  };
  let lastNavigation = 0;
  function update(frame) {
    pad = frame.pad;
    button.textContent = pad && !frame.snapshot.known ? STRINGS.unknown : STRINGS.title;
    const signature = frame.devices.map((p) => `${p.index}:${p.id}`).join("|");
    if (select.dataset.signature !== signature) {
      select.dataset.signature = signature;
      while (select.options.length > 1) select.remove(1);
      for (const p of frame.devices) element("option", p.id, select).value = p.index;
    }
    if (!root.open) return;
    live.textContent = JSON.stringify(frame.snapshot || {});
    if (pad && wizard) {
      prompt.textContent = STRINGS.prompt + CALIBRATION_STEPS[wizard.values.length];
      const axes = pad.axes.map((v, i) => v - (wizard.baseline[i] || 0));
      const pressed = pad.buttons.findIndex((b) => b.pressed);
      if (release) {
        if (isNeutral(axes, pressed)) {
          release = false;
          prompt.dataset.ready = "true";
        }
      } else {
        const captured = captureCalibrationStep(wizard.values.length, axes, pressed);
        if (captured) next(captured);
      }
      return;
    }
    if (pad && !frame.snapshot.known) prompt.textContent = STRINGS.unknown;
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, 600, 120);
    ctx.strokeStyle = "#4fd1e0";
    ctx.beginPath();
    for (let x = 0; x <= 600; x++) {
      const y =
        110 -
        curve(radial(x / 600, 0, settings.inner ?? 0.08, settings.outer ?? 0.02)[0], settings.channels[preview.value]) *
          100;
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    const v = Math.abs(frame.snapshot ? bindingValue(settings.bindings[preview.value], frame.snapshot) : 0);
    ctx.beginPath();
    ctx.arc(
      v * 600,
      110 -
        curve(radial(v, 0, settings.inner ?? 0.08, settings.outer ?? 0.02)[0], settings.channels[preview.value]) * 100,
      5,
      0,
      Math.PI * 2,
    );
    ctx.fillStyle = "#5fd38a";
    ctx.fill();
    if (!pad || !frame.snapshot.known || performance.now() - lastNavigation < 220) return;
    const b = frame.snapshot.buttons;
    const focused = document.activeElement;
    if (focused?.dataset.binding) {
      const buttonIndex = b.findIndex((value, index) => index < 12 && value > 0.5);
      const axisIndex = frame.snapshot.axes.findIndex((value) => Math.abs(value) > 0.75);
      if (buttonIndex >= 0 || axisIndex >= 0) {
        focused.value =
          buttonIndex >= 0 ? `b${buttonIndex}` : `${frame.snapshot.axes[axisIndex] < 0 ? "-" : ""}a${axisIndex}`;
        focused.dispatchEvent(new Event("change"));
        close.focus();
        lastNavigation = performance.now();
        return;
      }
    }
    if (focused?.tagName === "SELECT" && (b[NAV.left] > 0.5 || b[NAV.right] > 0.5)) {
      focused.selectedIndex =
        (focused.selectedIndex + (b[NAV.right] > 0.5 ? 1 : -1) + focused.options.length) % focused.options.length;
      focused.dispatchEvent(new Event("change"));
      lastNavigation = performance.now();
      return;
    }

    const stick = frame.snapshot.axes[NAV.stick];
    const direction = b[NAV.down] > 0.5 || stick > 0.6 ? 1 : b[NAV.up] > 0.5 || stick < -0.6 ? -1 : 0;
    if (direction) {
      const controls = [...root.querySelectorAll("button,select,input,summary")].filter((e) => e.checkVisibility());
      const index = controls.indexOf(document.activeElement);
      controls[(index + direction + controls.length) % controls.length]?.focus();
    } else if (b[NAV.accept] > 0.5) document.activeElement?.click();
    else if (b[NAV.back] > 0.5) root.close();
    else if (document.activeElement?.type === "range" && (b[NAV.left] > 0.5 || b[NAV.right] > 0.5)) {
      const input = document.activeElement;
      input.value = +input.value + (b[NAV.right] > 0.5 ? 1 : -1) * +input.step;
      input.dispatchEvent(new Event("input"));
    } else return;
    lastNavigation = performance.now();
  }
  // Keyboard rebinding: action -> key capture, saved per layout in settings.keys; a key already used by another
  // action in the same context is refused (bindings.js keyCollisions), so the table stays unique.
  function mountKeyboard() {
    const group = element("details", "");
    group.id = "keyboardBindings";
    element("summary", STRINGS.keyboard, group);
    const help = element("p", "", group);
    const note = element("p", "", group);
    note.setAttribute("role", "status");
    const list = element("div", "", group);
    const reset = element("button", STRINGS.keyReset, group);
    let capture = null;
    function overrides(layout) {
      return { ...(settings.keys?.[layout] || {}) };
    }
    function labels(rows) {
      const result = {};
      for (const item of hintItems({ axes: true, contexts: ["flight"], rows })) result[item.action] = item.label;
      return result;
    }
    function render() {
      const layout = keyboardLayout();
      const rows = rowsFor(settings);
      const names = labels(rows);
      help.textContent = STRINGS.keyboardHelp.replace("{layout}", layoutLabel(layout));
      list.replaceChildren();
      for (const row of rows) {
        if (!keyRebindable(row) || !row.keys.length) continue;
        const line = element("div", "", list);
        element("span", `${names[row.action] || actionLabel(row.action)} `, line);
        const parts = (names[row.action] || "").split("／");
        row.keys.forEach(function keyButton(code, index) {
          const text = row.axis && parts[index] ? `${keyLabel(code)}（${parts[index]}）` : keyLabel(code);
          const button = element("button", text, line);
          button.dataset.keyAction = row.action;
          button.dataset.keyIndex = String(index);
          button.onclick = function startCapture() {
            capture = { action: row.action, index, keys: [...row.keys] };
            button.textContent = STRINGS.capture;
            note.textContent = "";
          };
        });
      }
    }
    function captureKey(event) {
      if (!capture || !root.open) return;
      event.preventDefault();
      event.stopPropagation();
      const pending = capture;
      capture = null;
      if (event.code === "Escape") {
        render();
        return;
      }
      const layout = keyboardLayout();
      const next = overrides(layout);
      const keys = [...pending.keys];
      keys[pending.index] = event.code;
      next[pending.action] = keys;
      const collisions = keyCollisions(layout, next);
      if (collisions.length) {
        note.textContent = STRINGS.keyTaken + keyLabel(event.code) + " · "
          + collisions.map((entry) => entry.actions.map(actionLabel).join(" / ")).join("；");
        render();
        return;
      }
      settings.keys = { ...(settings.keys || {}), [layout]: next };
      save();
      onKeys?.();
      note.textContent = STRINGS.keySaved;
      render();
    }
    root.addEventListener("keydown", captureKey, true);
    reset.onclick = function resetKeys() {
      const layout = keyboardLayout();
      if (settings.keys) delete settings.keys[layout];
      save();
      onKeys?.();
      render();
    };
    getFidelity().subscribe(render);
    render();
  }
  function registerActions(definitions) {
    for (const [name, action] of Object.entries(definitions)) featureActions.set(name, action);
    renderBindings();
  }
  return { registerActions, update, open: () => root.open, selected: () => (select.value === "auto" ? "" : select.value) };
}
