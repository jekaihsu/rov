// Compose one focused screen per launch step while retaining the established form contract.
import { installAudio, installAudioSettings } from "../audio/engine.js";
import { installMenuControls } from "./devices.js";
import { CAMPAIGN_MENU_STRINGS } from "../story/campaign.js";
import { installMenuInput } from "./input.js";
const STRINGS = {
  title: "深藍之下，開始探索。",
  enter: "進入主選單",
  home: "主選單",
  mode: "選擇玩法",
  vehicle: "載具機庫",
  sea: "選擇海域",
  brief: "潛航簡報",
  multiplayer: "多人連線",
  settings: "設定",
  collection: "圖鑑與收藏",
  quit: "離開",
  back: "返回",
  next: "下一步",
  quick: "快速開始",
  start: "開始潛航",
  tabs: ["畫質", "控制", "音訊", "介面", "語言"],
  modes: ["探索與工程 · 1–3 人", "自由探索 · 1–3 人", "協作巡檢 · 1–3 人", "訓練 · 1 人"],
  tips: [
    "自由接案、探索生態與工程作業。",
    "沒有時間壓力，熟悉水下操控。",
    "分工巡檢，穩定拍攝三個站點。",
    "練習懸停、巡檢與精密操作。",
  ],
  loading: "正在準備場景與載具，請稍候…",
  ready: "出航檢查",
  specs: "以下是模擬器暫定參數，不是真機實測規格；緊湊型資料待實測。",
  pending: "未分級",
  training: "訓練情境 / 練習重點",
  checklist: "潛前確認：檢查纜線與連線、確認洋流與能見度；入水及人員離開後才解鎖，回收前先上鎖。",
  unknown: "待實測",
  no: "無",
  yes: "有",

  language: "繁體中文",
  room: "加入前尚無房內玩家；連線後以房主海域與任務為準。",
  quitHelp: "瀏覽器請關閉分頁以離開。",
};
export function installFlow(menu) {
  const $ = (id) => document.getElementById(id);
  const form = $("launchForm");
  const sections = [...form.children];
  const stage = document.createElement("div");
  stage.className = "menu-stage";
  menu.append(stage);
  const screens = {};
  function screen(key, title) {
    const node = document.createElement("section");
    node.className = "menu-screen";
    node.innerHTML = `<small>ROV / ${key.toUpperCase()}</small><h1>${title}</h1>`;
    stage.append(node);
    screens[key] = node;
    return node;
  }
  function button(parent, text, action) {
    const node = document.createElement("button");
    node.type = "button";
    node.textContent = text;
    node.onclick = action;
    parent.append(node);
    return node;
  }
  let current = "title";
  const history = [];
  function show(key, remember = true) {
    if (remember) history.push(current);
    current = key;
    menu.dataset.screen = key;
    for (const [name, node] of Object.entries(screens)) node.hidden = name !== key;
    $("startDive").hidden = key !== "brief";
    screens[key].querySelector("button,input,select")?.focus();
    if (key === "brief") {
      summary.textContent = [
        $("menuMode").selectedOptions[0]?.text,
        $("previewTitle").textContent,
        $("menuScene").selectedOptions[0]?.text,
        $("sceneBrief").textContent,
      ].join(" / ");
    }
  }
  function back() {
    show(history.pop() || "home", false);
  }
  const title = screen("title", STRINGS.title);
  button(title, STRINGS.enter, () => show("home"));
  const home = screen("home", STRINGS.home);
  button(home, STRINGS.start, () => show("mode"));
  button(home, STRINGS.quick, () => form.requestSubmit());
  button(home, STRINGS.multiplayer, () => show("multiplayer"));
  button(home, STRINGS.collection, () => $("menuCollection").click());
  button(home, STRINGS.settings, () => show("settings"));
  button(home, STRINGS.quit, () => {
    if (window.rovDesktop) window.close();
    else $("menuStatus").textContent = STRINGS.quitHelp;
  });
  const mode = screen("mode", STRINGS.mode);
  mode.append(sections[1]);
  sections[1].hidden = true;
  const modes = document.createElement("div");
  modes.className = "menu-cards";
  for (const [index, option] of [...$("menuMode").options].entries()) {
    button(
      modes,
      option.value === "campaign"
        ? `${CAMPAIGN_MENU_STRINGS.title} — ${CAMPAIGN_MENU_STRINGS.brief}`
        : `${STRINGS.modes[index - 1]} — ${STRINGS.tips[index - 1]}`,
      () => {
        $("menuMode").value = option.value;
        $("menuMode").dispatchEvent(new Event("change"));
        show("vehicle");
      },
    );
  }
  mode.append(modes);
  const training = document.createElement("details");
  const trainingTitle = document.createElement("summary");
  trainingTitle.textContent = STRINGS.training;
  training.append(trainingTitle);
  mode.append(training);
  fetch("scene_previews.json")
    .then((response) => response.json())
    .then(function trainingScenarios(entries) {
      for (const [index, entry] of entries.entries()) {
        button(training, `${STRINGS.pending} · ${entry.name} · ${entry.brief}`, () => {
          $("menuMode").value = "scenario_training";
          $("menuScene").value = entry.key;
          $("menuScene").dispatchEvent(new Event("change"));
          show("vehicle");
        });
      }
    });
  const vehicle = screen("vehicle", STRINGS.vehicle);
  vehicle.append(sections[2]);
  const specs = document.createElement("div");
  specs.className = "vehicle-specs";

  vehicle.append(specs);
  const specsData = {
    falcon: [60, 5, 1.5, true],
    bluerov2_heavy: [13.5, 8, 1.5, false],
    x1: [null, 6, null, false],
  };
  function updateSpecs() {
    const id = document.querySelector("[data-vehicle][aria-pressed=true]")?.dataset.vehicle || "falcon";
    const [mass, count, speed, arm] = specsData[id];
    specs.replaceChildren();
    const values = document.createElement("p");
    values.textContent = `${mass ?? STRINGS.unknown} kg · ${count} 推進器 · ${speed ?? STRINGS.unknown} m/s · 機械臂 ${arm ? STRINGS.yes : STRINGS.no}`;
    specs.append(values);
    const note = document.createElement("small");
    note.textContent = STRINGS.specs;
    specs.append(note);
  }
  new MutationObserver(updateSpecs).observe(vehicle, {
    subtree: true,
    attributes: true,
    attributeFilter: ["aria-pressed"],
  });
  updateSpecs();
  button(vehicle, STRINGS.next, () => show("sea"));
  const sea = screen("sea", STRINGS.sea);
  sea.append(sections[3]);
  const cards = document.createElement("div");
  cards.className = "menu-cards sea-cards";
  sea.append(cards);
  fetch("scene_previews.json")
    .then((response) => response.json())
    .then(function populate(entries) {
      for (const entry of entries) {
        const card = button(cards, `${entry.name} · ${entry.brief}`, () => {
          $("menuScene").value = entry.key;
          $("menuScene").dispatchEvent(new Event("change"));
        });
      }
    });
  button(sea, STRINGS.next, () => show("brief"));
  const brief = screen("brief", STRINGS.brief);
  const summary = document.createElement("p");
  brief.append(summary);
  const checklist = document.createElement("p");
  checklist.textContent = STRINGS.checklist;
  brief.append(checklist);
  const multiplayer = screen("multiplayer", STRINGS.multiplayer);
  sections[4].open = true;
  multiplayer.append(sections[4]);
  const room = document.createElement("p");
  room.textContent = STRINGS.room;
  multiplayer.append(room);
  button(multiplayer, "建立房間", () => show("mode"));
  button(multiplayer, "加入房間", () => show("brief"));
  const settings = screen("settings", STRINGS.settings);
  const tabs = document.createElement("nav");
  settings.append(tabs);
  const panels = STRINGS.tabs.map(function makeTab(label, index) {
    const panel = document.createElement("div");
    panel.className = "settings-panel";
    panel.dataset.mount = ["quality", "controls", "audio", "interface", "language"][index];
    settings.append(panel);
    button(tabs, label, () => selectTab(index));
    return panel;
  });
  panels[0].append(sections[0]);
  sections[5].open = true;
  panels[1].append(sections[5]);
  installMenuControls(panels[1]);
  installAudioSettings(installAudio(), panels[2]);
  panels[2].querySelector("details").open = true;
  panels[4].textContent = STRINGS.language;
  for (const id of ["menuPip", "menuIntro", "menuSticks", "menuFog", "menuLabels"]) {
    panels[3].append($(id).closest("label"));
  }
  let tabIndex = 0;
  function selectTab(index) {
    tabIndex = (index + panels.length) % panels.length;
    panels.forEach((panel, i) => {
      panel.hidden = i !== tabIndex;
    });
    [...tabs.children].forEach((node, i) => node.setAttribute("aria-pressed", String(i === tabIndex)));
  }
  selectTab(0);
  const footer = document.createElement("footer");
  footer.className = "menu-navigation";
  button(footer, STRINGS.back, back);
  const hints = document.createElement("span");
  hints.id = "inputHints";
  hints.textContent = "方向鍵 移動 · Enter 確認 · Esc 返回";
  footer.append(hints);
  menu.append(footer);
  let dragging = false;
  menu.querySelector("canvas").addEventListener("pointerdown", () => {
    dragging = true;
  });
  addEventListener("pointerup", () => {
    dragging = false;
  });
  addEventListener("pointermove", (event) => {
    if (dragging) menu.dataset.rotation = Number(menu.dataset.rotation || 0) + event.movementX * 0.01;
  });
  installMenuInput(menu, back, (direction) => {
    if (current === "settings") selectTab(tabIndex + direction);
  });
  show("title", false);
}
