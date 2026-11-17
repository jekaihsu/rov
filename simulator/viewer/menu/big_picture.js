// Big-picture layout parts shared by the launch menu, the career screens, the pause menu and the results screen
// (styles in big_picture.css): a hero block (small category line, one very large title, a few big numbers, short
// chips, one solid primary button and text-only secondary actions), a strip of large image tiles, a one-line
// status, a details sheet opened on demand (明細), and the game-rendered backdrop image that covers the 3D stage
// while it switches to another site. DOM builders only; screens keep their own state and strings.

import { localize } from '../i18n/index.js';
const STRINGS = localize('menu.big_picture', {
  details: '明細',
  close: '關閉',
});
// Title length (in full-width character units) above which the title drops to a smaller size tier.
const TITLE_MEDIUM = 6;
const TITLE_SMALL = 12;
const REVEAL_FRAMES = 3;
// Scroll distance (px) below which a tile strip counts as resting against its edge.
const EDGE_SLACK = 4;

export const DETAILS_LABEL = STRINGS.details;

export function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

// Display width of a title: CJK and full-width characters count one, Latin letters and digits about half.
function titleUnits(text) {
  let units = 0;
  for (const character of String(text || '')) units += character.codePointAt(0) > 0x2e7f ? 1 : 0.55;
  return units;
}

/** Sets a hero title and picks its size tier, so long titles (and other languages) wrap to two lines at most. */
export function fitTitle(node, text) {
  const units = titleUnits(text);
  node.textContent = text || '';
  let size = 'l';
  if (units > TITLE_MEDIUM) size = 'm';
  if (units > TITLE_SMALL) size = 's';
  node.dataset.size = size;
}

/** One big number with a small label under it. */
export function stat(label, value, unit = '') {
  const block = element('div', 'bp-stat');
  const line = element('span', 'bp-stat-value');
  line.append(element('b', '', value));
  if (unit) line.append(element('small', '', unit));
  block.append(line, element('span', 'bp-stat-label', label));
  return block;
}

/** A short tag; state: '' (neutral), 'ok', 'missing' or 'warn'. */
export function chip(text, state = '') {
  const node = element('span', 'bp-chip', text);
  if (state) node.dataset.state = state;
  return node;
}

/** The one solid primary button of a screen. cap: show the confirm key in front (launch menu only). */
export function primaryButton(id, text, { cap = true, type = 'button' } = {}) {
  const button = element('button', 'menu-start bp-primary');
  button.type = type;
  button.id = id;
  const label = element('span', 'bp-primary-label', text);
  if (cap) {
    const key = element('span', 'menu-press-cap');
    key.dataset.promptAction = 'accept';
    button.append(key);
  }
  button.append(label);
  return { button, label };
}

/** A text-only secondary action. */
export function linkButton(id, text) {
  const button = element('button', 'bp-link', text);
  button.type = 'button';
  if (id) button.id = id;
  return button;
}

/** Hero block: kicker, title, stats, chips and actions; empty rows collapse. */
export function createHero({ titleTag = 'h2' } = {}) {
  const root = element('div', 'bp-hero');
  const kicker = element('p', 'bp-kicker');
  const title = element(titleTag, 'bp-title');
  const stats = element('div', 'bp-stats');
  const chips = element('div', 'bp-chips');
  const actions = element('div', 'bp-actions');
  root.append(kicker, title, stats, chips, actions);
  return {
    element: root,
    kicker,
    title,
    stats,
    chips,
    actions,
    setTitle(text) {
      fitTitle(title, text);
    },
    // list: [[label, value, unit]]
    setStats(list) {
      stats.replaceChildren(...list.map(function build([label, value, unit]) {
        return stat(label, value, unit);
      }));
    },
    // list: [[text, state]] or plain strings
    setChips(list) {
      chips.replaceChildren(...list.map(function build(entry) {
        return Array.isArray(entry) ? chip(entry[0], entry[1]) : chip(entry);
      }));
    },
  };
}

/** A large tile: the picture fills it, the name sits on its dark lower edge; note: one short extra line. */
export function tile({ name, image = '', note = '' }) {
  const button = element('button', 'bp-tile');
  button.type = 'button';
  const media = element('span', 'bp-tile-media');
  if (image) {
    const picture = element('img');
    picture.alt = '';
    picture.loading = 'lazy';
    picture.src = image;
    picture.addEventListener('error', function noPicture() {
      picture.remove();
    });
    media.append(picture);
  }
  const text = element('span', 'bp-tile-text');
  text.append(element('strong', 'bp-tile-name', name));
  if (note) text.append(element('small', 'bp-tile-note', note));
  button.append(media, text);
  return button;
}

/**
 * A horizontal strip of tiles. The tile under focus or the pointer is the current one (thick frame);
 * onCurrent(tile) lets the screen show it in the hero block and move the backdrop.
 */
export function createTileStrip(onCurrent) {
  const strip = element('div', 'bp-tiles');
  let current = null;
  function mark(node) {
    if (!node || node === current) return;
    current?.removeAttribute('data-current');
    current = node;
    node.dataset.current = '';
    onCurrent(node);
  }
  function fromEvent(event) {
    mark(event.target.closest?.('.bp-tile'));
  }
  // data-more (left, right, both) tells the styles which edge fades out because more tiles lie beyond it.
  function updateEdges() {
    const left = strip.scrollLeft > EDGE_SLACK;
    const right = strip.scrollLeft + strip.clientWidth < strip.scrollWidth - EDGE_SLACK;
    let more = '';
    if (left && right) more = 'both';
    else if (left) more = 'left';
    else if (right) more = 'right';
    strip.dataset.more = more;
  }
  strip.addEventListener('focusin', fromEvent);
  strip.addEventListener('pointerover', fromEvent);
  strip.addEventListener('scroll', updateEdges, { passive: true });
  new ResizeObserver(updateEdges).observe(strip);
  return {
    element: strip,
    get current() {
      return current;
    },
    // preferred: the tile to start on; without one the first enabled tile is current.
    fill(nodes, preferred = null) {
      strip.replaceChildren(...nodes);
      current = null;
      const first = nodes.find(function enabled(node) {
        return !node.disabled;
      });
      mark(preferred || first || nodes[0]);
      updateEdges();
    },
  };
}

/** One-line status at the top right of a screen (licence · money). */
export function statusLine(id) {
  const line = element('p', 'bp-status');
  if (id) line.id = id;
  return line;
}

/**
 * Details on demand: a solid sheet over the right side of the screen, opened by a 明細 action. A modal
 * <dialog>, so the menu navigator scopes focus to it and its back action closes it. Every section is focusable,
 * so a pad or the arrow keys scroll a long sheet by moving through its sections.
 */
export function createDetailSheet(title) {
  const dialog = element('dialog', 'bp-sheet');
  dialog.setAttribute('aria-label', title || STRINGS.details);
  const head = element('header', 'bp-sheet-head');
  const heading = element('h2', 'bp-sheet-title', title || STRINGS.details);
  const close = linkButton('', STRINGS.close);
  close.classList.add('bp-sheet-close');
  close.dataset.autofocus = '';
  head.append(heading, close);
  const body = element('div', 'bp-sheet-body');
  dialog.append(head, body);
  document.body.append(dialog);
  close.addEventListener('click', function closeSheet() {
    dialog.close();
  });
  dialog.addEventListener('click', function outside(event) {
    if (event.target === dialog) dialog.close();
  });
  return {
    element: dialog,
    body,
    setTitle(text) {
      heading.textContent = text;
    },
    clear() {
      body.replaceChildren();
    },
    // heading: small label of the section (may be empty); nodes: its content.
    section(label, ...nodes) {
      const block = element('section', 'bp-sheet-section');
      block.tabIndex = 0;
      if (label) block.append(element('h3', 'bp-sheet-label', label));
      block.append(...nodes.filter(Boolean));
      body.append(block);
      return block;
    },
    open() {
      if (dialog.open) return;
      dialog.showModal();
      body.scrollTop = 0;
      close.focus({ preventScroll: true });
    },
    close() {
      if (dialog.open) dialog.close();
    },
  };
}

/** A 明細 text action that opens the sheet; fill() runs first so the sheet shows the current selection. */
export function detailButton(id, sheet, fill) {
  const button = linkButton(id, STRINGS.details);
  button.addEventListener('click', function openDetails() {
    fill?.();
    sheet.open();
  });
  return button;
}

/**
 * The game-rendered preview picture (menu/previews) shown full-bleed with a slow push-in while the 3D stage
 * switches site, and left in place when the stage has no such scene. host: the launch menu element.
 */
export function createBackdrop(host, before) {
  const layer = element('div', 'bp-backdrop');
  const picture = element('img');
  picture.alt = '';
  layer.append(picture);
  host.insertBefore(layer, before);
  let ticket = 0;
  picture.addEventListener('error', function noPicture() {
    layer.classList.remove('on');
  });
  function hide() {
    ticket += 1;
    layer.classList.remove('on');
  }
  return {
    element: layer,
    // source: the preview image URL of the site being shown.
    show(source) {
      ticket += 1;
      if (picture.getAttribute('src') !== source) {
        picture.src = source;
        // Restart the push-in for the new picture.
        picture.style.animation = 'none';
        picture.getBoundingClientRect();
        picture.style.animation = '';
      }
      layer.classList.add('on');
    },
    hide,
    // The stage has the scene now: let it draw a few frames, then fade the picture away.
    reveal() {
      const mine = ++ticket;
      let left = REVEAL_FRAMES;
      function wait() {
        if (mine !== ticket) return;
        left -= 1;
        if (left > 0) requestAnimationFrame(wait);
        else layer.classList.remove('on');
      }
      requestAnimationFrame(wait);
    },
  };
}
