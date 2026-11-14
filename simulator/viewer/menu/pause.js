// Present an in-game pause surface without changing simulation or HUD rendering.
import { FRONTEND_OPEN_EVENT, FRONTEND_PAUSE_EVENT, finishFrontendInput } from "./state.js";
import { readMenuPad, installMenuInput } from "./input.js";
const STRINGS = {
  title: "潛航暫停",
  resume: "繼續",
  settings: "設定",
  home: "返回主選單",
  notice: "仿真持續運行；選單只將自己的操控回中並上鎖。恢復後請先鬆開按鍵、回中，再重新解鎖。",
  quality: "畫質",
  pauseSimulation: "訓練輔助：單人選單暫停仿真",
  nextOpen: "下次開啟選單生效",
  paused: "仿真目前暫停；恢復後請先鬆開按鍵、回中，再重新解鎖。",
  back: "返回",
  lights: "燈光（循環 0 / 1 / 2）",
  external: "目前由外部控制器或 SDK 操作；此選單不接管控制或暫停仿真。",
};
function readPausePreference() {
  try {
    return JSON.parse(localStorage.getItem("rov.menuSettings") || "{}")?.pauseSimulation === true;
  } catch {
    return false;
  }
}
if (new URLSearchParams(location.search).get("play") === "1") {
  const root = document.createElement("dialog");
  root.className = "pause-menu";
  root.innerHTML = `<h1>${STRINGS.title}</h1><p>${STRINGS.notice}</p><div id="pauseActions"></div>`;
  document.body.append(root);
  const actions = root.querySelector("#pauseActions");
  let pausedByMenu = false;
  let startCanClose = false;
  let settingsPanel = null;
  let lightControl = null;
  function close() {
    finishFrontendInput();
    root.close();
    if (pausedByMenu) document.getElementById("btnPause").click();
    pausedByMenu = false;
  }
  function button(label, handler, parent = actions) {
    const node = document.createElement("button");
    node.textContent = label;
    node.onclick = handler;
    parent.append(node);
    return node;
  }
  button(STRINGS.resume, close);
  button(STRINGS.settings, function settings() {
    if (settingsPanel) {
      settingsPanel.querySelector("select")?.focus();
      return;
    }
    const quality = document.getElementById("quality");
    if (!quality) return;
    const select = quality.cloneNode(true);
    select.removeAttribute("id");
    select.value = quality.value;
    select.onchange = function changeQuality() {
      quality.value = select.value;
      quality.dispatchEvent(new Event("change"));
    };
    settingsPanel = document.createElement("section");
    const label = document.createElement("label");
    label.textContent = STRINGS.quality;
    label.append(select);
    settingsPanel.append(label);
    actions.append(settingsPanel);
    lightControl = button(
      STRINGS.lights,
      function cycleLights() {
        document.getElementById("bLed")?.click();
      },
      settingsPanel,
    );
    const pauseLabel = document.createElement("label");
    pauseLabel.textContent = STRINGS.pauseSimulation;
    const pauseToggle = document.createElement("input");
    pauseToggle.type = "checkbox";
    pauseToggle.checked = readPausePreference();
    pauseToggle.addEventListener("change", function changeTrainingPause() {
      try {
        const settings = JSON.parse(localStorage.getItem("rov.menuSettings") || "{}");
        settings.pauseSimulation = pauseToggle.checked;
        localStorage.setItem("rov.menuSettings", JSON.stringify(settings));
      } catch {}
    });
    const help = document.createElement("small");
    help.textContent = STRINGS.nextOpen;
    pauseLabel.append(pauseToggle, help);
    settingsPanel.append(pauseLabel);
    select.focus();
  });
  button(STRINGS.home, function returnHome() {
    close();
    document.getElementById("returnMenu").click();
  });
  function open() {
    if (root.open) return close();
    const viewer = window.__viewer;
    if (!viewer) return;
    viewer.rc.rc_lock = 1;
    const fleet = viewer.S?.vehicles || [];
    if (
      readPausePreference() &&
      !viewer.S?.controller &&
      !viewer.S?.remote_control &&
      Array.isArray(fleet) &&
      fleet.length === 1 &&
      !viewer.S.paused
    ) {
      document.getElementById("btnPause").click();
      pausedByMenu = true;
    }
    startCanClose = false;
    root.showModal();
    dispatchEvent(new Event(FRONTEND_OPEN_EVENT));
    actions.querySelector("button").focus();
  }
  addEventListener(
    "keydown",
    function pauseKey(event) {
      if (event.code !== "Escape") return;
      const dialog = document.querySelector("dialog[open]");
      if (dialog && dialog !== root) return;
      event.preventDefault();
      event.stopImmediatePropagation();
      open();
    },
    true,
  );
  root.addEventListener("cancel", (event) => event.preventDefault());
  installMenuInput(root, close, () => {});
  addEventListener(FRONTEND_PAUSE_EVENT, open);
  function tick() {
    const pad = root.open ? readMenuPad() : null;
    if (!pad?.start) startCanClose = true;
    if (root.open && pad?.start && startCanClose) close();
    if (root.open && window.__viewer) {
      const state = window.__viewer.S;
      const external = Boolean(state?.controller || state?.remote_control);
      window.__viewer.rc.rc_lock = 1;
      root.querySelector("p").textContent = external
        ? STRINGS.external
        : state?.paused
          ? STRINGS.paused
          : STRINGS.notice;
      if (lightControl) {
        lightControl.disabled = external;
        lightControl.textContent = `${STRINGS.lights} · ${state?.rc?.right_switch ?? 0}`;
      }
    }
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
