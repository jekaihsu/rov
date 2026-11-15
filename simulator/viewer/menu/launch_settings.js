// The launch menu's settings screen: 擬真設定, 控制, 音訊, 畫質 and 介面 tabs over the existing panels.
// Controller tuning reuses the input layer's own settings dialog (input/settings.js) with the same storage.
import { BINDINGS_VERSION, migrateBindings } from '../input/bindings.js';
import { createHaptics } from '../input/haptics.js';
import '../input/haptics_fidelity.js';
import { installSettings } from '../input/settings.js';
import { CONTROL_LAYOUTS } from '../control_layout.js';
import { renderQualityInfo } from '../render_quality.js';
import { rememberInterface, rememberQuality } from './preferences.js';
import {
  createSettingsPanel,
  element,
  field,
  mountAudio,
  mountChoices,
  mountFidelity,
  mountKeyHints,
  mountToggles,
} from './settings.js';

const STRINGS = {
  title: '設定',
  tabs: { fidelity: '擬真設定', controls: '控制', audio: '音訊', quality: '畫質', interface: '介面' },
  pad: '輸入裝置',
  padAuto: '自動偵測手把＋鍵盤',
  padKeyboard: '只使用鍵盤',
  padFound: '已偵測 {n} 支手把',
  padNone: '未偵測到手把，仍可使用鍵盤。按手把任一鍵以喚醒。',
  control: '控制配置',
  layouts: {
    ROV_USA: 'X1 配置：左桿俯仰／轉向，右桿前後／橫滾',
    ROV_JPN: 'X1 日本配置',
    ROV_CHN: 'X1 中國配置',
    UAV_USA: 'UAV_USA',
    UAV_JPN: 'UAV_JPN',
    UAV_CHN: 'ROV 雙桿：左桿前後／平移，右桿升降／轉向',
  },
  controllerSettings: '進階手把設定：死區、曲線、綁定與對應精靈',
  quality: {
    auto: ['自動', '依硬體調整，目標 60 FPS'],
    performance: ['流暢', '降低解析度'],
    medium: ['標準', '原生解析度'],
    high: ['高', '細節優先，含陰影'],
  },
  qualityState: '目前渲染比例 {scale}%',
  detecting: '正在偵測目前使用的顯示卡…',
  adaptive: '依畫面效能調整',
  interface: {
    intro: ['下水動畫', '從水面吊放到入水的開場運鏡；關閉時也略過潛前檢查流程。'],
    pip: ['操作員小視窗', '在畫面角落顯示岸上操作員。'],
    sticks: ['畫面搖桿', '只在觸控裝置上顯示。'],
    fog: ['真實能見度', '關閉後水體較清澈，超出真機影像。'],
    labels: ['場景標籤', '在結構物旁顯示名稱。'],
  },
};

async function readInputSettings() {
  let settings = {};
  try {
    settings = JSON.parse(localStorage.getItem('rov.input.v1') || '{}');
  } catch {
    settings = {};
  }
  const desktop = await window.rovDesktop?.readInput?.();
  if (desktop && Object.keys(desktop).length) settings = desktop;
  settings.custom ||= {};
  settings.bindings = migrateBindings(settings.bindings, settings.bindingsVersion);
  settings.bindingsVersion = BINDINGS_VERSION;
  settings.channels ||= {};
  return settings;
}

// The input layer's controller dialog; its button is moved into the controls tab.
async function mountControllerDialog(container, onLayout) {
  const settings = await readInputSettings();
  let pad = null;
  function save() {
    try {
      localStorage.setItem('rov.input.v1', JSON.stringify(settings));
    } catch {
      // Storage may be unavailable; the desktop shell keeps its own copy below.
    }
    window.rovDesktop?.rememberInput?.(settings);
  }
  const haptics = createHaptics(function currentPad() {
    return pad;
  }, settings);
  const panel = installSettings(settings, save, haptics, onLayout);
  const button = document.getElementById('inputSettingsButton');
  button.textContent = STRINGS.controllerSettings;
  button.className = 'menu-next menu-wide';
  container.append(button);
  return {
    update(frame) {
      pad = frame.pad;
      panel.update(frame);
      button.textContent = STRINGS.controllerSettings;
    },
    bindings: settings.bindings,
  };
}

export function buildLaunchSettings(ctx) {
  const root = element('section', 'menu-screen');
  root.dataset.screen = 'settings';
  root.setAttribute('aria-label', STRINGS.title);
  root.append(element('h2', 'menu-heading', STRINGS.title));
  let controller = null;
  let padSelect = null;
  let padInfo = null;
  let padSignature = '';
  let hardware = null;
  let qualityState = null;
  function controls(pane) {
    padSelect = element('select');
    padSelect.append(new Option(STRINGS.padAuto, 'auto'), new Option(STRINGS.padKeyboard, 'keyboard'));
    padSelect.value = ctx.choice.pad === 'keyboard' ? 'keyboard' : 'auto';
    padSelect.addEventListener('change', function choosePad() {
      ctx.choice.pad = padSelect.value;
    });
    field(pane, { id: 'menuPad', label: STRINGS.pad, control: padSelect });
    padInfo = element('p', 'menu-help', STRINGS.padNone);
    pane.append(padInfo);
    const layout = element('select');
    for (const value of CONTROL_LAYOUTS) layout.append(new Option(STRINGS.layouts[value] || value, value));
    layout.value = ctx.choice.control;
    layout.addEventListener('change', function chooseLayout() {
      ctx.choice.control = layout.value;
    });
    field(pane, { id: 'menuControl', label: STRINGS.control, control: layout });
    const dialogSlot = element('div', 'menu-field');
    pane.append(dialogSlot);
    mountControllerDialog(dialogSlot, function setLayout(mode) {
      layout.value = mode;
      ctx.choice.control = mode;
    }).then(function ready(mounted) {
      controller = mounted;
      mountKeyHints(pane, mounted.bindings);
    });
  }
  function quality(pane) {
    mountChoices(pane, {
      name: 'quality',
      options: Object.entries(STRINGS.quality).map(function option([value, [label, detail]]) {
        return [value, label, detail];
      }),
      value: ctx.choice.quality,
      onChange(value) {
        ctx.choice.quality = value;
        ctx.stage.configureQuality(value);
        rememberQuality(value);
        showQuality();
      },
    });
    hardware = element('p', 'menu-help', STRINGS.detecting);
    hardware.id = 'menuHardware';
    qualityState = element('p', 'menu-help');
    qualityState.id = 'menuQualityState';
    pane.append(hardware, qualityState);
    showQuality();
  }
  function showQuality() {
    if (!hardware) return;
    const info = renderQualityInfo(ctx.stage.renderer);
    hardware.textContent = info?.hardwareLabel ? `${info.hardwareLabel} · ${info.hardwareReason}` : STRINGS.adaptive;
    qualityState.textContent = STRINGS.qualityState.replace('{scale}', String(info?.scale || 100));
  }
  function interfaceTab(pane) {
    const ids = {
      intro: 'menuIntroSetting',
      pip: 'menuPip',
      sticks: 'menuSticks',
      fog: 'menuFog',
      labels: 'menuLabels',
    };
    mountToggles(pane, Object.entries(STRINGS.interface).map(function toggle([key, [label, help]]) {
      return {
        id: ids[key],
        label,
        help,
        checked: ctx.choice[key],
        onChange(value) {
          ctx.choice[key] = value;
          rememberInterface(ctx.choice);
        },
      };
    }));
  }
  const panel = createSettingsPanel({
    idPrefix: 'menuSettings',
    tabs: [
      { id: 'fidelity', label: STRINGS.tabs.fidelity, mount: mountFidelity },
      { id: 'controls', label: STRINGS.tabs.controls, mount: controls },
      { id: 'audio', label: STRINGS.tabs.audio, mount: mountAudio },
      { id: 'quality', label: STRINGS.tabs.quality, mount: quality },
      { id: 'interface', label: STRINGS.tabs.interface, mount: interfaceTab },
    ],
  });
  root.append(panel.element);
  setInterval(showQuality, 1000);
  function updatePads(frame) {
    controller?.update(frame);
    if (!padSelect) return;
    const signature = frame.devices.map(function id(pad) {
      return `${pad.index}:${pad.id}`;
    }).join('|');
    if (signature === padSignature) return;
    padSignature = signature;
    const value = padSelect.value;
    while (padSelect.options.length > 2) padSelect.remove(2);
    for (const pad of frame.devices) padSelect.add(new Option(pad.id, String(pad.index)));
    padSelect.value = [...padSelect.options].some(function kept(option) {
      return option.value === value;
    }) ? value : 'auto';
    padInfo.textContent = frame.devices.length
      ? STRINGS.padFound.replace('{n}', String(frame.devices.length))
      : STRINGS.padNone;
  }
  return { element: root, pose: 'settings', tabs: panel, frame: updatePads };
}
