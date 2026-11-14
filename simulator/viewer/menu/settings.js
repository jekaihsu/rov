// Tabbed settings surface shared by the launch menu and the in-game pause menu, plus the small builders the
// tabs are made of. Existing panels are mounted as they are: the fidelity profile (fidelity_panel.js), the
// audio mixer (audio/engine.js) and the binding table hints (input/bindings.js); nothing here keeps state.
import { installFidelityPanel } from '../fidelity_panel.js';
import { installAudio, installAudioSettings } from '../audio/engine.js';
import { hintItems } from '../input/bindings.js';
import { renderPrompts } from './navigator.js';

const STRINGS = {
  hintsTitle: '目前鍵位',
  action: '動作',
  keys: '鍵盤',
  pad: '手把',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

// tabs: [{id, label, mount(container)}]; each tab is built the first time it is shown.
export function createSettingsPanel({ tabs, idPrefix = 'settings' }) {
  const root = element('section', 'menu-settings');
  const bar = element('div', 'menu-tabs');
  bar.setAttribute('role', 'tablist');
  const previousCap = element('span', 'menu-tab-cap');
  const nextCap = element('span', 'menu-tab-cap');
  const body = element('div', 'menu-tab-body');
  const buttons = new Map();
  const panes = new Map();
  let current = '';
  bar.append(previousCap);
  for (const tab of tabs) {
    const button = element('button', 'menu-tab', tab.label);
    button.type = 'button';
    button.id = `${idPrefix}-tab-${tab.id}`;
    button.dataset.tab = tab.id;
    button.setAttribute('role', 'tab');
    button.addEventListener('click', function chooseTab() {
      select(tab.id);
    });
    buttons.set(tab.id, button);
    bar.append(button);
  }
  bar.append(nextCap);
  root.append(bar, body);
  function select(id) {
    const tab = tabs.find(function byId(entry) {
      return entry.id === id;
    }) || tabs[0];
    current = tab.id;
    if (!panes.has(tab.id)) {
      const pane = element('div', 'menu-tab-pane');
      pane.dataset.pane = tab.id;
      pane.setAttribute('role', 'tabpanel');
      tab.mount(pane);
      body.append(pane);
      panes.set(tab.id, pane);
    }
    for (const [key, pane] of panes) pane.hidden = key !== tab.id;
    for (const [key, button] of buttons) button.setAttribute('aria-selected', String(key === tab.id));
  }
  function step(direction) {
    const index = tabs.findIndex(function byId(entry) {
      return entry.id === current;
    });
    select(tabs[(index + direction + tabs.length) % tabs.length].id);
    buttons.get(current).focus({ preventScroll: true });
  }
  function setFamily(family) {
    renderPrompts(previousCap, [['tabPrevious', '']], family);
    renderPrompts(nextCap, [['tabNext', '']], family);
  }
  select(tabs[0].id);
  setFamily('keyboard');
  return {
    element: root,
    select,
    step,
    setFamily,
    get current() {
      return current;
    },
  };
}

export function mountFidelity(container) {
  const section = installFidelityPanel(container);
  section.classList.add('menu-embedded');
  return section;
}

export function mountAudio(container) {
  installAudioSettings(installAudio(), container);
  const section = container.lastElementChild;
  section.open = true;
  section.classList.add('menu-embedded', 'menu-audio');
  return section;
}

// options: [[value, label, detail]]; one is pressed at a time.
export function mountChoices(container, { title, options, value, onChange, name }) {
  const group = element('div', 'menu-choices');
  group.setAttribute('role', 'radiogroup');
  if (title) group.setAttribute('aria-label', title);
  const buttons = [];
  function show(selected) {
    for (const button of buttons) button.setAttribute('aria-pressed', String(button.dataset.value === selected));
  }
  for (const [optionValue, label, detail] of options) {
    const button = element('button', 'menu-choice');
    button.type = 'button';
    button.dataset.value = optionValue;
    if (name) button.dataset[name] = optionValue;
    button.append(element('strong', '', label));
    if (detail) button.append(element('small', '', detail));
    button.addEventListener('click', function choose() {
      show(optionValue);
      onChange(optionValue);
    });
    buttons.push(button);
    group.append(button);
  }
  show(value);
  container.append(group);
  return { group, show };
}

// items: [{id, label, help, checked, onChange}] rendered as switch rows backed by real checkboxes.
export function mountToggles(container, items) {
  const list = element('div', 'menu-toggles');
  for (const item of items) {
    const row = element('label', 'menu-toggle');
    row.htmlFor = item.id;
    const text = element('span', 'menu-toggle-text');
    text.append(element('strong', '', item.label));
    if (item.help) text.append(element('small', '', item.help));
    const input = element('input');
    input.type = 'checkbox';
    input.id = item.id;
    input.checked = !!item.checked;
    input.addEventListener('change', function toggled() {
      item.onChange(input.checked);
    });
    const state = element('span', 'menu-switch');
    state.setAttribute('aria-hidden', 'true');
    row.append(text, input, state);
    list.append(row);
  }
  container.append(list);
  return list;
}

// A readable table of the flight bindings, generated from the table so it cannot drift from the real keys.
export function mountKeyHints(container, bindings) {
  const section = element('section', 'menu-hints');
  section.append(element('h3', 'menu-label', STRINGS.hintsTitle));
  const table = element('table');
  const head = element('tr');
  for (const text of [STRINGS.action, STRINGS.keys, STRINGS.pad]) head.append(element('th', '', text));
  table.append(head);
  for (const item of hintItems({ axes: true, contexts: ['flight', 'tool', 'dialogue'], bindings })) {
    const row = element('tr');
    const label = item.note ? `${item.label}（${item.note}）` : item.label;
    row.append(element('td', '', label), element('td', '', item.keys.join(' ')), element('td', '', item.pad));
    table.append(row);
  }
  section.append(table);
  container.append(section);
  return section;
}

export function field(container, { id, label, help, control }) {
  const row = element('div', 'menu-field');
  const caption = element('label', 'menu-label', label);
  caption.htmlFor = id;
  control.id = id;
  row.append(caption, control);
  if (help) row.append(element('p', 'menu-help', help));
  container.append(row);
  return row;
}

export { element };
