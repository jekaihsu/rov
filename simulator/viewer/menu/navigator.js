// Gamepad and keyboard navigation for the launch menu and the pause menu, driven only by the `menu` context
// of input/bindings.js: focus moves spatially between the visible controls of the active screen (or of an
// open modal dialog), confirm clicks, back closes the dialog or steps back, LB/RB switch tabs and the right
// stick turns the hangar turntable. Also renders the footer button prompts for the device in use.
import { BINDINGS, bindingRow, createResolver, inputIds, keyLabel, keyRow, padLabel } from '../input/bindings.js';
import { createDevices } from '../input/devices.js';
import { deviceFamily, glyph } from '../input/glyphs.js';

const STRINGS = {
  move: '移動',
  stickNames: { a0: 'L', a1: 'L', a2: 'R', a3: 'R' },
  keyboardMove: '↑↓←→',
  padMove: '✛',
};

const MENU = new Set(['menu']);
const REPEAT_DELAY_MS = 380;
const REPEAT_MS = 140;
const STICK = 0.6;
const ROTATE_DEADZONE = 0.15;
const FOCUSABLE = 'button, a[href], input:not([type=hidden]), select, summary, [tabindex="0"]';
const MENU_PAD = Object.fromEntries(BINDINGS.filter(function menuRow(row) {
  return row.context === 'menu' && row.pad;
}).map(function padSource(row) {
  return [row.action, row.pad];
}));

export async function loadControllerDatabase() {
  try {
    const response = await fetch(new URL('../input/controller-db.json', import.meta.url));
    return await response.json();
  } catch {
    return {};
  }
}

function readCustomMappings() {
  try {
    return JSON.parse(localStorage.getItem('rov.input.v1') || '{}').custom || {};
  } catch {
    return {};
  }
}

function isText(element) {
  if (!element) return false;
  if (element.tagName === 'TEXTAREA') return true;
  return element.tagName === 'INPUT' && !['range', 'checkbox', 'radio', 'button', 'submit'].includes(element.type);
}

function visible(element) {
  if (element.disabled || element.closest('[inert]')) return false;
  if (!element.checkVisibility({ checkVisibilityCSS: true })) return false;
  const box = element.getBoundingClientRect();
  return box.width > 0 && box.height > 0;
}

// The topmost modal dialog owns navigation while it is open.
export function topDialog() {
  const open = [...document.querySelectorAll('dialog[open]')].filter(function modal(dialog) {
    return dialog.matches(':modal');
  });
  return open.at(-1) || null;
}

function centre(box) {
  return { x: box.left + box.width / 2, y: box.top + box.height / 2 };
}

// Nearest control in the pressed direction; distance across the direction counts double.
export function nearestInDirection(from, candidates, direction) {
  const origin = centre(from);
  let best = null;
  let bestScore = Infinity;
  for (const candidate of candidates) {
    const point = centre(candidate.box);
    const dx = point.x - origin.x;
    const dy = point.y - origin.y;
    const along = { left: -dx, right: dx, up: -dy, down: dy }[direction];
    const across = direction === 'left' || direction === 'right' ? Math.abs(dy) : Math.abs(dx);
    if (along <= 4) continue;
    const score = along + across * 2.2;
    if (score < bestScore) {
      bestScore = score;
      best = candidate.item;
    }
  }
  return best;
}

function capFor(action, family) {
  const row = bindingRow(action);
  if (!row) return '';
  if (family === 'keyboard') {
    const key = row.keys?.[0];
    return key ? { text: keyLabel(key) } : null;
  }
  const [id] = inputIds(row.pad);
  if (!id) return null;
  const index = Number(id.slice(1));
  if (id[0] === 'b' && index < 4) return { svg: glyph(index, family) };
  if (id[0] === 'a') return { text: STRINGS.stickNames[id] || id };
  return { text: padLabel(row.pad) };
}

function capElement(cap) {
  const node = document.createElement('span');
  node.className = 'menu-cap';
  if (cap.svg) {
    node.classList.add('menu-cap-glyph');
    node.innerHTML = cap.svg;
  } else node.textContent = cap.text;
  return node;
}

// items: [[action or 'navigate', label], …]; actions without a source on this device are left out.
export function renderPrompts(container, items, family) {
  container.replaceChildren();
  for (const [action, label] of items) {
    const caps = action === 'navigate'
      ? [{ text: family === 'keyboard' ? STRINGS.keyboardMove : STRINGS.padMove }]
      : [].concat(action).map(function cap(name) {
        return capFor(name, family);
      });
    if (caps.some(function missing(cap) {
      return !cap;
    })) continue;
    const item = document.createElement('span');
    item.className = 'menu-prompt';
    item.dataset.action = [].concat(action).join(' ');
    for (const cap of caps) item.append(capElement(cap));
    const text = document.createElement('span');
    text.textContent = label;
    item.append(text);
    container.append(item);
  }
}

// handlers: scope() → element whose controls are navigable; back(); tab(direction); rotate(value, dt);
// family(name) when the device in use changes; frame(frame) with every polled device frame.
export function createMenuNavigator({ database = {}, handlers, root = document.documentElement }) {
  const devices = createDevices(database, readCustomMappings());
  const resolver = createResolver();
  let active = false;
  let previous = {};
  let heldDirection = '';
  let nextRepeat = 0;
  let family = 'keyboard';
  let lastTime = performance.now();
  let lastSignature = '';
  let loop = 0;

  function setFamily(name) {
    if (name === family) return;
    family = name;
    handlers.family?.(name);
  }
  function setInputKind(kind) {
    root.dataset.menuInput = kind;
  }
  function scope() {
    return topDialog() || handlers.scope?.() || document.body;
  }
  function controls(container) {
    return [...container.querySelectorAll(FOCUSABLE)].filter(visible);
  }
  function focus(element) {
    if (!element) return;
    element.focus({ preventScroll: true });
    element.scrollIntoView({ block: 'nearest', inline: 'nearest' });
  }
  function focusFirst(container = scope()) {
    const list = controls(container);
    const preferred = list.find(function marked(element) {
      return element.matches('[data-autofocus], [aria-pressed=true], [aria-selected=true]');
    });
    focus(preferred || list[0]);
  }
  function stepValue(element, direction) {
    const sign = direction === 'right' ? 1 : -1;
    if (element.tagName === 'SELECT' && element.options.length) {
      const count = element.options.length;
      element.selectedIndex = (element.selectedIndex + sign + count) % count;
      element.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
    if (element.type === 'range') {
      const step = Number(element.step) || 1;
      element.value = String(Number(element.value) + sign * step);
      element.dispatchEvent(new Event('input', { bubbles: true }));
      element.dispatchEvent(new Event('change', { bubbles: true }));
      return true;
    }
    return false;
  }
  function move(direction) {
    const container = scope();
    const current = document.activeElement;
    if (!current || current === document.body || !container.contains(current) || !visible(current)) {
      focusFirst(container);
      return;
    }
    if ((direction === 'left' || direction === 'right') && stepValue(current, direction)) return;
    const candidates = controls(container).filter(function other(element) {
      return element !== current;
    }).map(function measured(element) {
      return { item: element, box: element.getBoundingClientRect() };
    });
    focus(nearestInDirection(current.getBoundingClientRect(), candidates, direction));
  }
  function accept() {
    const container = scope();
    const current = document.activeElement;
    if (!current || !container.contains(current) || current === container) {
      focusFirst(container);
      return;
    }
    if (current.tagName === 'SELECT') {
      stepValue(current, 'right');
      return;
    }
    if (isText(current)) {
      current.select?.();
      return;
    }
    current.click();
  }
  function back() {
    const dialog = topDialog();
    if (dialog) {
      const cancel = new Event('cancel', { cancelable: true });
      dialog.dispatchEvent(cancel);
      if (!cancel.defaultPrevented && dialog.open) dialog.close();
      return;
    }
    handlers.back?.();
  }
  function run(action) {
    if (action === 'menuUp') move('up');
    else if (action === 'menuDown') move('down');
    else if (action === 'menuLeft') move('left');
    else if (action === 'menuRight') move('right');
    else if (action === 'accept') accept();
    else if (action === 'back') back();
    else if (action === 'tabPrevious') handlers.tab?.(-1);
    else if (action === 'tabNext') handlers.tab?.(1);
  }
  function foreignPanel() {
    return !!document.getElementById('inputSettings')?.open;
  }
  function onKey(event) {
    if (!active || event.defaultPrevented || event.ctrlKey || event.metaKey || event.altKey) return;
    if (foreignPanel()) return;
    const row = keyRow(event.code, MENU);
    if (!row || row.context !== 'menu') return;
    setFamily('keyboard');
    setInputKind('key');
    const text = isText(event.target);
    if (text && !['menuUp', 'menuDown', 'back'].includes(row.action)) return;
    event.preventDefault();
    if (event.repeat && !row.action.startsWith('menu')) return;
    if (text && row.action === 'back') {
      event.target.blur();
      focus(event.target);
      return;
    }
    run(row.action);
  }
  function directionOf(values) {
    if (values.menuUp > 0.5 || values.menuStick < -STICK) return 'up';
    if (values.menuDown > 0.5 || values.menuStick > STICK) return 'down';
    if (values.menuLeft > 0.5 || values.menuStickX < -STICK) return 'left';
    if (values.menuRight > 0.5 || values.menuStickX > STICK) return 'right';
    return '';
  }
  function sample(now) {
    const dt = Math.min(0.1, (now - lastTime) / 1000);
    lastTime = now;
    const frame = devices.poll('auto');
    handlers.frame?.(frame);
    if (!active || !frame.pad || !frame.snapshot?.known || foreignPanel()) {
      if (frame.snapshot) resolver.block(frame.snapshot);
      previous = {};
      heldDirection = '';
      return;
    }
    const values = resolver.resolve(MENU_PAD, frame.snapshot, MENU, now);
    const signature = frame.snapshot.buttons.map(function pressed(value) {
      return value > 0.5 ? 1 : 0;
    }).join('') + frame.snapshot.axes.map(function moved(value) {
      return Math.abs(value) > 0.3 ? 1 : 0;
    }).join('');
    if (signature !== lastSignature && signature.includes('1')) {
      setFamily(deviceFamily(frame.pad.id));
      setInputKind('pad');
    }
    lastSignature = signature;
    const direction = directionOf(values);
    if (direction && (direction !== heldDirection || now >= nextRepeat)) {
      nextRepeat = now + (direction === heldDirection ? REPEAT_MS : REPEAT_DELAY_MS);
      move(direction);
    }
    heldDirection = direction;
    for (const action of ['accept', 'back', 'tabPrevious', 'tabNext']) {
      if (values[action] > 0.5 && !(previous[action] > 0.5)) run(action);
    }
    if (Math.abs(values.menuRotate || 0) > ROTATE_DEADZONE) handlers.rotate?.(values.menuRotate, dt);
    previous = values;
  }
  function tick(now) {
    sample(now);
    loop = requestAnimationFrame(tick);
  }
  // Buttons already down when the menu takes over (the press that opened it) stay ignored until released.
  function setActive(value) {
    if (value === active) return;
    active = value;
    previous = {};
    heldDirection = '';
    const frame = devices.poll('auto');
    if (frame.snapshot) resolver.block(frame.snapshot);
  }
  function start() {
    if (!loop) loop = requestAnimationFrame(tick);
  }
  function stop() {
    cancelAnimationFrame(loop);
    loop = 0;
  }
  addEventListener('keydown', onKey);
  addEventListener('pointerdown', function pointer(event) {
    if (event.pointerType === 'mouse') setInputKind('pointer');
  });
  setInputKind('pointer');
  return {
    setActive,
    start,
    stop,
    focusFirst,
    move,
    accept,
    back,
    get family() {
      return family;
    },
    get active() {
      return active;
    },
  };
}
