// Identity marks on the launch menu, added from outside so menu/screens.js keeps its structure:
// the YX mark on the title screen and in the header, the fleet symbol beside the hangar's vehicle title and on
// each vehicle chip, a small symbol in the briefing kicker, and the hidden ?brandDemo component sheet.
// menu/main.js calls installBrandMenu() once after the screens are built; everything else follows the DOM.
import {fleetSymbol, svgNode, yxMark} from './marks.js';
import { localize } from '../i18n/index.js';

export const STRINGS = localize('brand.menu_brand', {
  demoClose: '關閉',
  demoLabel: 'YX 識別元件',
});

const TITLE_MARK_SIZE = 120;
const HANGAR_SYMBOL_SIZE = 64;
const CHIP_SYMBOL_SIZE = 20;
const KICKER_SYMBOL_SIZE = 20;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function symbolHolder(modelId, size, className) {
  const holder = element('span', `brand-fleet-symbol ${className}`);
  holder.dataset.model = modelId;
  holder.append(svgNode(fleetSymbol(modelId, {size})));
  return holder;
}

function decorateTitle(menu) {
  const block = menu.querySelector('.menu-title-block');
  if (!block || block.querySelector('.brand-lockup')) return;
  const lockup = element('div', 'brand-lockup');
  lockup.append(svgNode(yxMark({variant: 'tether', misregister: false, size: TITLE_MARK_SIZE})));
  block.prepend(lockup);
}

function decorateHeader(menu) {
  const brand = menu.querySelector('.menu-brand');
  if (!brand || brand.querySelector('.yx-mark')) return;
  brand.classList.add('brand-header');
  brand.prepend(svgNode(yxMark({variant: 'compact'})));
}

function decorateHangar(menu) {
  const picker = menu.querySelector('.menu-vehicles');
  const title = menu.querySelector('.menu-vehicle-title');
  if (!picker || !title) return;
  for (const chip of picker.querySelectorAll('[data-vehicle]')) {
    chip.classList.add('brand-chip');
    chip.prepend(symbolHolder(chip.dataset.vehicle, CHIP_SYMBOL_SIZE, 'brand-fleet-symbol-chip'));
  }
  function showChosen() {
    const chosen = picker.querySelector('[data-vehicle][aria-pressed=true]')?.dataset.vehicle;
    const current = title.querySelector('.brand-fleet-symbol');
    if (!chosen || current?.dataset.model === chosen) return;
    current?.remove();
    title.prepend(symbolHolder(chosen, HANGAR_SYMBOL_SIZE, 'brand-fleet-symbol-title'));
  }
  new MutationObserver(showChosen).observe(picker, {
    attributes: true, subtree: true, attributeFilter: ['aria-pressed'],
  });
  showChosen();
}

// The briefing rewrites its kicker text on entry; the symbol is put back in front of it each time.
function decorateBriefing(menu, getModel) {
  const kicker = menu.querySelector('.menu-briefing-main .menu-kicker');
  if (!kicker) return;
  function addSymbol() {
    const model = getModel();
    const current = kicker.querySelector('.brand-fleet-symbol');
    if (current?.dataset.model === model || !kicker.textContent) return;
    current?.remove();
    kicker.classList.add('brand-kicker');
    kicker.prepend(symbolHolder(model, KICKER_SYMBOL_SIZE, 'brand-fleet-symbol-kicker'));
  }
  new MutationObserver(addSymbol).observe(kicker, {childList: true});
  addSymbol();
}

async function openDemo() {
  const {buildBrandDemo} = await import('./demo.js');
  const overlay = element('div', 'brand-demo-overlay');
  overlay.id = 'brandDemo';
  overlay.setAttribute('role', 'dialog');
  overlay.setAttribute('aria-label', STRINGS.demoLabel);
  const close = element('button', 'brand-demo-close', STRINGS.demoClose);
  close.type = 'button';
  close.addEventListener('click', function closeDemo() {
    overlay.remove();
  });
  overlay.append(close, buildBrandDemo());
  document.body.append(overlay);
}

/**
 * Decorate the launch menu. menu: the menu root element; getModel: returns the chosen model id;
 * search: the page query (defaults to the current one), where `brandDemo` opens the component sheet.
 */
export function installBrandMenu({menu, getModel, search = location.search}) {
  decorateTitle(menu);
  decorateHeader(menu);
  decorateHangar(menu);
  decorateBriefing(menu, getModel);
  if (new URLSearchParams(search).has('brandDemo')) {
    openDemo().catch(function demoFailed(error) {
      console.error(error);
    });
  }
}
