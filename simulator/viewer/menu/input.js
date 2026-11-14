// Adapt shared T02 device snapshots into frontend navigation actions.
import { pollMenuDevices, menuBindingValue } from "./devices.js";
import { deviceFamily } from "../input/glyphs.js";
const STRINGS = {
  keyboard: "方向鍵 移動 · Enter 確認 · Esc 返回",
  playstation: "方向鍵 移動 · × 確認 · ○ 返回 · L1 / R1 分頁",
  switch: "方向鍵 移動 · B 確認 · A 返回 · L / R 分頁",
  xbox: "方向鍵 移動 · A 確認 · B 返回 · LB / RB 分頁",
  generic: "方向鍵 移動 · 1 確認 · 2 返回 · 5 / 6 分頁",
};
let waitingForSettingsRelease = false;
export function readMenuPad() {
  const wasSettingsOpen = Boolean(document.getElementById("inputSettings")?.open);
  const { pad, snapshot } = pollMenuDevices();
  if (wasSettingsOpen || document.getElementById("inputSettings")?.open) {
    waitingForSettingsRelease = true;
    return null;
  }
  if (waitingForSettingsRelease) {
    if (snapshot?.buttons.some((value) => value > 0.5)) return null;
    waitingForSettingsRelease = false;
  }
  if (!pad) return null;
  const pressed = (index) => (snapshot.buttons[index] || 0) > 0.5;
  return {
    up: pressed(12) || snapshot.axes[1] < -0.6,
    down: pressed(13) || snapshot.axes[1] > 0.6,
    left: pressed(14) || snapshot.axes[0] < -0.6,
    right: pressed(15) || snapshot.axes[0] > 0.6,
    start: menuBindingValue("frontendPause", "b9") > 0.5,
    confirm: pressed(0),
    back: pressed(1),
    previous: pressed(4),
    next: pressed(5),
    rotate: snapshot.axes[2] || 0,
    family: deviceFamily(pad.id),
  };
}

export function installMenuInput(root, back, tab) {
  let prior = {};
  let lastDevice = "keyboard";
  let repeat = 0;
  function controls() {
    return [...(document.querySelector("dialog[open]") || root).querySelectorAll("button,input,select,summary")].filter(
      (node) => node.getClientRects().length && !node.disabled,
    );
  }
  function move(direction) {
    const items = controls();
    const index = items.indexOf(document.activeElement);
    items[(index + direction + items.length) % items.length]?.focus();
  }
  function change(direction) {
    const node = document.activeElement;
    if (node?.type === "range") {
      node.stepUp(direction);
      node.dispatchEvent(new Event("input"));
      return;
    }
    if (node?.tagName !== "SELECT") return move(direction);
    node.selectedIndex = (node.selectedIndex + direction + node.length) % node.length;
    node.dispatchEvent(new Event("change"));
  }
  function confirm() {
    const node = document.activeElement;
    if (node?.tagName !== "INPUT" || ["checkbox", "range"].includes(node.type)) {
      node?.click();
      return;
    }
    const dialog = document.createElement("dialog");
    dialog.className = "menu-keyboard";
    const preview = document.createElement("p");
    preview.textContent = node.value;
    dialog.append(preview);
    for (const key of "abcdefghijklmnopqrstuvwxyz0123456789-_:/ .⌫✓") {
      const button = document.createElement("button");
      button.textContent = key;
      button.onclick = function typeCharacter() {
        if (key === "✓") {
          dialog.close();
          return;
        }
        node.value = key === "⌫" ? node.value.slice(0, -1) : node.value + key;
        preview.textContent = node.value;
      };
      dialog.append(button);
    }
    dialog.addEventListener("close", function restoreFocus() {
      dialog.remove();
      node.focus();
    });
    dialog.showModal();
    dialog.querySelector("button").focus();
  }
  function tick(now) {
    const pad = root.tagName === "DIALOG" && !root.open ? null : readMenuPad();
    if (pad) {
      const hints = root.querySelector("#inputHints");
      if (Object.values(pad).some((value) => value === true) || Math.abs(pad.rotate) > 0.15) {
        lastDevice = pad.family;
      }
      if (hints) hints.textContent = STRINGS[lastDevice] || STRINGS.generic;
      for (const action of ["up", "down", "left", "right", "confirm", "back", "previous", "next"]) {
        if (!pad[action] || (prior[action] && (now < repeat || !["up", "down", "left", "right"].includes(action))))
          continue;
        repeat = now + 220;
        if (action === "up") move(-1);
        if (action === "down") move(1);
        if (action === "left") change(-1);
        if (action === "right") change(1);
        if (action === "confirm") confirm();
        if (action === "back") {
          const dialog = document.querySelector("dialog[open]");
          if (dialog && dialog !== root) {
            const cancel = new Event("cancel", { cancelable: true });
            if (dialog.dispatchEvent(cancel)) dialog.close();
          } else back();
        }
        if (action === "previous") tab(-1);
        if (action === "next") tab(1);
      }
      root.dataset.rotation = Number(root.dataset.rotation || 0) + pad.rotate * 0.025;
      prior = pad;
    }
    requestAnimationFrame(tick);
  }
  root.addEventListener("pointerdown", function onPointer() {
    lastDevice = "keyboard";
    const hints = root.querySelector("#inputHints");
    if (hints) hints.textContent = STRINGS.keyboard;
  });
  root.addEventListener("keydown", function onKey(event) {
    lastDevice = "keyboard";
    const hints = root.querySelector("#inputHints");
    if (hints) hints.textContent = STRINGS.keyboard;
    if (event.key === "Escape") back();
    if (event.key.startsWith("Arrow") && !["INPUT", "SELECT"].includes(event.target.tagName)) {
      event.preventDefault();
      move(["ArrowUp", "ArrowLeft"].includes(event.key) ? -1 : 1);
    }
  });
  requestAnimationFrame(tick);
}
