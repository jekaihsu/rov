// Identity marks on the launch menu, added from outside so menu/screens.js keeps its structure:
// the YX mark on the title screen and in the header.
// menu/main.js calls installBrandMenu() once after the screens are built; everything else follows the DOM.
import {svgNode, yxMark} from './marks.js';

const TITLE_MARK_SIZE = 120;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
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

/** Decorate the launch menu. menu: the menu root element. */
export function installBrandMenu({menu}) {
  decorateTitle(menu);
  decorateHeader(menu);
}
