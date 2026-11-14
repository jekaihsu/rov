// Settings section for the fidelity profile: preset selector plus one row per registered item.
// Purely a view over fidelity.js; it holds no state of its own and never sends vehicle controls.
import {getFidelity, fidelityText, PRESET_NAMES} from './fidelity.js';
const STRINGS = {
  title: '擬真設定',
  intro: '真實模式與真機一致；輔助項目超出真機能力，可逐項開關。',
  presets: {real: '真實', assisted: '輔助', custom: '自訂'},
  presetGroup: '擬真預設',
  exceeds: '超出真機',
  exceedsHint: '此項目啟用後超出真機能力',
  fromUrl: '網址指定'
};
let serial = 0;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}
function choiceControl(item, fidelity) {
  const select = element('select');
  for (const option of item.options) {
    select.append(new Option(fidelityText(option.labelKey), String(option.value)));
  }
  select.addEventListener('change', function choose() {
    fidelity.set(item.id, select.value);
  });
  return {
    node: select,
    show(value) {
      select.value = String(value);
    }
  };
}
function toggleControl(item, fidelity) {
  const input = element('input');
  input.type = 'checkbox';
  input.addEventListener('change', function toggle() {
    fidelity.set(item.id, input.checked);
  });
  return {
    node: input,
    show(value) {
      input.checked = value;
    }
  };
}
function rangeControl(item, fidelity) {
  const wrap = element('span', 'fidelity-range');
  const input = element('input');
  const output = element('output');
  input.type = 'range';
  input.min = item.min;
  input.max = item.max;
  input.step = item.step ?? 1;
  input.addEventListener('input', function slide() {
    fidelity.set(item.id, Number(input.value));
  });
  wrap.append(input, output);
  return {
    node: wrap,
    input,
    show(value) {
      input.value = value;
      output.textContent = `${value} ${item.unitKey ? fidelityText(item.unitKey) : ''}`.trim();
    }
  };
}
function buildRow(item, fidelity, prefix) {
  const row = element('div', 'fidelity-item');
  row.dataset.fidelityItem = item.id;
  const label = element('label', 'fidelity-label', fidelityText(item.labelKey));
  const builders = {choice: choiceControl, toggle: toggleControl, range: rangeControl};
  const control = builders[item.type](item, fidelity);
  const field = control.input || control.node;
  field.id = `${prefix}-${item.id}`;
  label.htmlFor = field.id;
  const head = element('div', 'fidelity-head');
  head.append(label);
  let badge = null;
  if (item.exceedsReal) {
    badge = element('span', 'fidelity-badge', STRINGS.exceeds);
    badge.title = STRINGS.exceedsHint;
    head.append(badge);
  }
  const source = element('span', 'fidelity-source', STRINGS.fromUrl);
  head.append(source, control.node);
  row.append(head);
  if (item.descriptionKey) row.append(element('p', 'fidelity-help', fidelityText(item.descriptionKey)));
  function show() {
    control.show(fidelity.get(item.id));
    source.hidden = !fidelity.fromUrl(item.id);
    if (badge) badge.classList.toggle('active', fidelity.exceeds(item.id));
  }
  return {row, show};
}
// Mounts the section into `parent` and keeps it in step with the store. Returns the section element.
export function installFidelityPanel(parent, fidelity = getFidelity()) {
  const prefix = `fidelity${serial++}`;
  const section = element('details', 'fidelity-panel');
  section.open = true;
  section.append(element('summary', '', STRINGS.title));
  section.append(element('p', 'fidelity-help', STRINGS.intro));
  const presets = element('div', 'fidelity-presets');
  presets.setAttribute('role', 'group');
  presets.setAttribute('aria-label', STRINGS.presetGroup);
  const buttons = {};
  function addPreset(name) {
    const button = element('button', '', STRINGS.presets[name]);
    button.type = 'button';
    button.dataset.fidelityPreset = name;
    if (name === 'custom') button.disabled = true;
    else button.addEventListener('click', function choosePreset() {
      fidelity.setPreset(name);
    });
    buttons[name] = button;
    presets.append(button);
  }
  for (const name of [...PRESET_NAMES, 'custom']) addPreset(name);
  section.append(presets);
  const list = element('div', 'fidelity-items');
  section.append(list);
  let rows = [];
  let built = '';
  function render() {
    const items = fidelity.items();
    const signature = items.map(function itemId(item) {
      return item.id;
    }).join('|');
    if (signature !== built) {
      built = signature;
      rows = items.map(function build(item) {
        return buildRow(item, fidelity, prefix);
      });
      list.replaceChildren(...rows.map(function rowNode(entry) {
        return entry.row;
      }));
    }
    const preset = fidelity.preset;
    for (const [name, button] of Object.entries(buttons)) {
      button.setAttribute('aria-pressed', String(name === preset));
    }
    for (const entry of rows) entry.show();
  }
  fidelity.subscribe(render);
  render();
  parent.append(section);
  return section;
}
