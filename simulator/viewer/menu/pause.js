// Present an in-game pause surface without changing simulation or HUD rendering.
import { FRONTEND_OPEN_EVENT, finishFrontendInput } from "./state.js";
import { readMenuPad, installMenuInput } from "./input.js";
const STRINGS = {
  title: "潛航暫停",
  resume: "繼續",
  settings: "設定",
  home: "返回主選單",
  notice: "多人連線持續運行；選單鎖定自己的推進器。恢復後請先鬆開按鍵、回中，再重新解鎖。",
  quality: "畫質",
  back: "返回",
};
if (new URLSearchParams(location.search).get("play") === "1") {
  const root = document.createElement("dialog");
  root.className = "pause-menu";
  root.innerHTML = `<h1>${STRINGS.title}</h1><p>${STRINGS.notice}</p><div id="pauseActions"></div>`;
  document.body.append(root);
  const actions = root.querySelector("#pauseActions");
  let pausedByMenu = false;
  function close() {
    finishFrontendInput();
    root.close();
    if (pausedByMenu) document.getElementById("btnPause").click();
    pausedByMenu = false;
  }
  function button(label, handler) {
    const node = document.createElement("button");
    node.textContent = label;
    node.onclick = handler;
    actions.append(node);
  }
  button(STRINGS.resume, close);
  button(STRINGS.settings, function settings() {
    const quality = document.getElementById("quality");
    if (!quality) return;
    const select = quality.cloneNode(true);
    select.removeAttribute("id");
    select.value = quality.value;
    select.onchange = function changeQuality() {
      quality.value = select.value;
      quality.dispatchEvent(new Event("change"));
    };
    actions.append(select);
    select.focus();
  });
  button(STRINGS.home, () => document.getElementById("returnMenu").click());
  function open() {
    if (root.open) return close();
    const viewer = window.__viewer;
    if (!viewer) return;
    viewer.rc.rc_lock = 1;
    const fleet = viewer.S?.vehicles || [];
    if (Array.isArray(fleet) && fleet.length === 1 && !viewer.S.paused) {
      document.getElementById("btnPause").click();
      pausedByMenu = true;
    }
    root.showModal();
    dispatchEvent(new Event(FRONTEND_OPEN_EVENT));
    actions.querySelector("button").focus();
  }
  addEventListener(
    "keydown",
    function pauseKey(event) {
      if (event.code !== "Escape") return;
      event.preventDefault();
      event.stopImmediatePropagation();
      open();
    },
    true,
  );
  root.addEventListener("cancel", (event) => event.preventDefault());
  installMenuInput(root, close, () => {});
  let prior = false;
  function tick() {
    const pad = readMenuPad();
    if (pad?.start && !prior) open();
    prior = Boolean(pad?.start);
    if (root.open && window.__viewer) window.__viewer.rc.rc_lock = 1;
    requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}
