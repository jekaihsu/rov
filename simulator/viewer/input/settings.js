// Controller setup, live shaping preview and sequential calibration; flight is suspended while open.
import "../prefs/accessibility.js";
import { CHANNELS, PRESETS, curve, radial, bindingValue } from "./actions.js";
import {
  BINDINGS, actionLabel, contextLabel, bindingRow, editablePadBindings, findCollisions, hintItems, inputIds, keyCollisions, keyLabel,
  layoutLabel,
} from "./bindings.js";
import { keyboardLayout, rowsFor, publishKeyRows } from "./keyboard_layout.js";
import { getFidelity } from "../fidelity.js";
import { getDisplayPrefs } from "../prefs/display.js";
import {
  CALIBRATION_STEPS, captureCalibrationStep, buildCustomMapping, isNeutral
} from "./calibrate.js";
import { localize } from "../i18n/core.js";
const STRINGS = localize("input.settings", {
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
  clear: "解除綁定",
  negative: "請放開，再按反方向的按鍵。",
  keyReset: "還原此配置的預設按鍵",
});
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
  let capturePad = null;
  let positiveButton = null;
  let waitRelease = true;
  function changedBindings() {
    save();
    if (onKeys) onKeys();
    else publishKeyRows(rowsFor(settings));
  }
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
    #inputSettings summary{cursor:pointer;padding:8px 0;font-weight:600}
    #inputSettings #padBindings>div{display:grid;grid-template-columns:1fr auto;align-items:center;gap:4px 12px}
    #inputSettings #padBindings label,#keyboardBindings div>div{display:flex;align-items:center;gap:8px;
      justify-content:space-between;margin:0;padding:5px 0;border-bottom:1px solid #35505c}
    #inputSettings #padBindings h3{grid-column:1/-1}
    #inputSettings #padBindings input{width:7em}
    #inputSettings details[open]>p[role=status]{position:sticky;top:0;background:#10232c;color:#b7f3ed}
    #keyboardBindings span{flex:1}
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
    if (root.open) return;
    waitRelease = true;
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
    settings.bindings = { ...editablePadBindings(), ...PRESETS[preset.value] };
    setMode(preset.value === "drone" ? "UAV_USA" : "ROV_USA");
    changedBindings();
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
  // Older profiles stored one dead zone for both sticks.
  if (Number.isFinite(settings.inner)) {
    for (const side of ["left", "right"]) getFidelity().set(side + "Deadzone", settings.inner);
    delete settings.inner;
    save();
  }
  slider(STRINGS.outer, settings, "outer", 0, 0.3, 0.01, 0.02);
  for (const channel of CHANNELS) {
    const group = element("details", "");
    element("summary", actionLabel(channel), group);
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
  for (const channel of CHANNELS) element("option", actionLabel(channel), preview).value = channel;
  const canvas = element("canvas", "");
  canvas.width = 600;
  canvas.height = 120;
  const bindings = element("details", "");
  bindings.id = "padBindings";
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
    capturePad = null;
    rows.replaceChildren();
    let context;
    for (const definition of BINDINGS) {
      const name = definition.action;
      const binding = settings.bindings[name];
      if (context !== definition.context) {
        context = definition.context;
        element("h3", contextLabel(context), rows);
      }
      const row = element("label", actionLabel(name), rows);
      const input = element("input", "", row);
      input.dataset.binding = name;
      input.value = Array.isArray(binding) ? binding.join(",") : binding;
      const clear = element("button", STRINGS.clear, rows);
      clear.onclick = function clearPad() {
        input.value = "";
        input.dispatchEvent(new Event("change"));
      };
      input.onclick = function startPadCapture() {
        capturePad = input;
        positiveButton = null;
        waitRelease = true;
        collisionNote.textContent = STRINGS.capture;
      };
      input.onchange = function rebind() {
        capturePad = null;
        const raw = input.value.trim();
        const parts = raw.split(",").map(part => part.trim());
        const chord = name === "settings" && /^b\d+\+b\d+$/.test(raw);
        const valid = !raw || chord || (parts.length <= 2 && parts.every(part => /^-?[ab]\d+~?$/.test(part)));
        const candidate = parts.length === 2 ? parts : raw;
        const conflicts = findCollisions(undefined, {...settings.bindings, [name]: candidate})
          .filter(entry => entry.actions.includes(name));
        if (!valid || conflicts.length) {
          input.value = String(settings.bindings[name]);
          collisionNote.textContent = STRINGS.keyTaken + conflicts.flatMap(c => c.actions).map(actionLabel).join(" / ");
          return;
        }
        settings.bindings[name] = candidate;
        changedBindings();
        collisionNote.textContent = STRINGS.keySaved;
      };
    }
    showCollisions();
  }
  root.addEventListener("close", function resetCapture() {
    capturePad = null;
  });
  renderBindings();
  const renderKeyboard = mountKeyboard();
  // Mute lives on padHaptics (擬真設定); strength is shared with the display tab (prefs/display.js).
  settings.strength ??= getDisplayPrefs().get("hapticStrength") ?? 1;
  const strengthRow = element("label", STRINGS.strength);
  const strengthInput = element("input", "", strengthRow);
  strengthInput.type = "range";
  strengthInput.min = 0;
  strengthInput.max = 1;
  strengthInput.step = 0.05;
  strengthInput.value = settings.strength;
  getDisplayPrefs().subscribe(function syncStrength(values, id) {
    if (id === "hapticStrength") strengthInput.value = values.hapticStrength;
  });
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
  const resetBindings = element("button", STRINGS.reset);
  close.after(resetBindings, document.getElementById("keyboardBindings"), bindings);
  resetBindings.onclick = function reset() {
    settings.bindings = editablePadBindings();
    settings.keys = {};
    changedBindings();
    renderBindings();
    renderKeyboard();
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
    const side = preview.value.startsWith("left") ? "left" : "right";
    const fidelity = getFidelity();
    function previewY(value) {
      const stick = !preview.value.endsWith("wave");
      const inner = fidelity.get(side + "Deadzone");
      const radialValue = stick ? radial(value, 0, inner, settings.outer)[0] : value;
      const shaped = stick ? curve(radialValue, {
        expo: fidelity.get(side + "Response"),
        invert: preview.value.endsWith("ud") && fidelity.get(side + "Invert"),
      }) : value;
      return 60 - curve(shaped, settings.channels[preview.value]) * 54;
    }
    const ctx = canvas.getContext("2d");
    ctx.clearRect(0, 0, 600, 120);
    ctx.strokeStyle = "#4fd1e0";
    ctx.beginPath();
    for (let x = 0; x <= 600; x++) {
      const y = previewY(x / 600);
      if (x === 0) ctx.moveTo(x, y);
      else ctx.lineTo(x, y);
    }
    ctx.stroke();
    const v = Math.abs(frame.snapshot ? bindingValue(settings.bindings[preview.value], frame.snapshot) : 0);
    ctx.beginPath();
    ctx.arc(
      v * 600,
      previewY(v),
      5,
      0,
      Math.PI * 2,
    );
    ctx.fillStyle = "#5fd38a";
    ctx.fill();
    if (!pad || !frame.snapshot.known || performance.now() - lastNavigation < 220) return;
    const b = frame.snapshot.buttons;
    const focused = document.activeElement;
    if (waitRelease) {
      if (b.some(value => value > 0.5) || frame.snapshot.axes.some(value => Math.abs(value) > 0.6)) return;
      waitRelease = false;
    }
    if (capturePad && focused === capturePad) {
      const buttonIndex = b.findIndex(value => value > 0.5);
      const axisIndex = frame.snapshot.axes.findIndex((value) => Math.abs(value) > 0.75);
      if (buttonIndex >= 0 || axisIndex >= 0) {
        const row = bindingRow(focused.dataset.binding);
        const sign = frame.snapshot.axes[axisIndex] < 0 ? "-" : "";
        const source = buttonIndex >= 0 ? `b${buttonIndex}` : `${sign}a${axisIndex}`;
        if (row.axis && buttonIndex >= 0 && positiveButton === null) {
          positiveButton = source;
          collisionNote.textContent = STRINGS.negative;
          waitRelease = true;
          return;
        }
        const buttons = b.flatMap((value, index) => value > 0.5 ? ["b" + index] : []);
        if (row.gesture === "chord" && buttons.length === 2) focused.value = buttons.join("+");
        else focused.value = positiveButton ? positiveButton + "," + source : source;
        focused.dispatchEvent(new Event("change"));
        waitRelease = true;
        lastNavigation = performance.now();
        return;
      }
      return;
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
    } else if (b[NAV.accept] > 0.5) {
      document.activeElement?.click();
      waitRelease = true;
    }
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
      const {keyAction, keyIndex} = document.activeElement?.dataset || {};
      list.replaceChildren();
      let context;
      for (const row of rows) {
        if (context !== row.context) {
          context = row.context;
          element("h3", contextLabel(context), list);
        }
        const line = element("div", "", list);
        element("span", actionLabel(row.action), line);
        const parts = (names[row.action] || "").split(/\s*[／/]\s*/);
        const slots = row.keys?.length ? row.keys : row.axis || row.context === "orbit" ? ["", ""] : [""];
        slots.forEach(function keyButton(code, index) {
          const cap = keyLabel(code) || "＋";
          const text = row.axis && parts[index] ? `${cap} · ${parts[index]}` : cap;
          const button = element("button", text || "＋", line);
          button.dataset.keyAction = row.action;
          button.dataset.keyIndex = String(index);
          button.onclick = function startCapture() {
            if (capture) capture.button.textContent = capture.caption;
            capture = { action: row.action, index, keys: [...slots], button, caption: button.textContent };
            button.textContent = STRINGS.capture;
            note.textContent = "";
          };
        });
        const clear = element("button", STRINGS.clear, line);
        clear.onclick = function clearKeys() {
          const next = overrides(layout);
          next[row.action] = [];
          settings.keys = {...settings.keys, [layout]: next};
          capture = null;
          changedBindings();
          render();
        };
      }
      if (keyAction) {
        list.querySelector(`[data-key-action="${keyAction}"][data-key-index="${keyIndex}"]`)?.focus();
      }
    }
    function captureKey(event) {
      if (!capture || !root.open) return;
      event.preventDefault();
      event.stopPropagation();
      const pending = capture;
      capture = null;
      if (event.code === "Escape" && pending.action !== "pause" && pending.action !== "back") {
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
      changedBindings();
      note.textContent = STRINGS.keySaved;
      render();
    }
    root.addEventListener("close", function cancelCapture() {
      capture = null;
      render();
    });
    root.addEventListener("keydown", captureKey, true);
    reset.onclick = function resetKeys() {
      const layout = keyboardLayout();
      if (settings.keys) delete settings.keys[layout];
      changedBindings();
      render();
    };
    getFidelity().subscribe(render);
    render();
    return render;
  }
  return {
    update,
    open: () => root.open,
    selected: () => select.value === "auto" ? "" : select.value,
  };
}
