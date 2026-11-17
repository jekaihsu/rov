// YX 裝備部: the launch menu shop. Equipment that a real ROV carries and that opens deliverables (laser scaler,
// imaging sonar, CP probe, UT gauge, gripper) and cosmetics (stickers). Big-picture layout: items are large tiles
// with a name and a price; the tile under focus fills the hero block (name, price, how many vehicles it fits,
// whether it raises their Block number, and why it cannot be bought yet) with the one primary 購買 button. What
// the item really does, what it opens and which vehicles it fits are behind 明細. Buying takes a second press, on
// the tile or the button. No stat boosts and no real-money store.
import { createSettingsPanel } from '../menu/settings.js';
import {
  createDetailSheet,
  createHero,
  createTileStrip,
  detailButton,
  element,
  primaryButton,
  statusLine,
  tile,
} from '../menu/big_picture.js';
import { vehicleName, vehicleTitle } from '../fleet_names.js';
import { moneyText } from './board.js';
import { gradeFor, itemView } from './rules.js';
import { itemStatus, purchase } from './shop_rules.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('career.shop', {
  title: 'YX 裝備部',
  strip: '{licence} · {money} 元',
  tabs: { equipment: '作業裝備', cosmetic: '外觀' },
  help: {
    equipment: '只賣真實存在的配件：它們讓你能接更多種工單，不會讓機子變快或變強。',
    cosmetic: '機身貼紙與塗裝條紋，只影響外觀。',
  },
  price: '價格',
  moneyUnit: '元',
  priceNote: '{price} 元',
  fitsStat: '適用',
  fitsUnit: '機型',
  blockStat: 'Block',
  blockValue: '+1',
  use: '用途',
  opens: '開放',
  fits: '適用機型',
  fleet: '目前船隊',
  rule: '說明',
  owned: '已擁有',
  buy: '購買',
  confirm: '再按一次確認',
  unavailable: '無法購買',
  bought: '已購入「{item}」。',
  upgraded: '{vehicle} 升級為 Block {block}。',
});
const FLEET = ['x1', 'bluerov2_heavy', 'falcon'];

function paragraph(text) {
  return element('p', 'bp-sheet-text', text);
}

/** The shop screen. ctx.career: career/menu.js context. */
export function buildShop(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen bp-screen career-board career-shop');
  root.dataset.screen = 'shop';
  root.setAttribute('aria-label', STRINGS.title);
  const summary = statusLine('shopSummary');
  const hero = createHero();
  hero.element.id = 'shopHero';
  const { button: buyButton, label: buyLabel } = primaryButton('shopBuy', STRINGS.buy);
  const sheet = createDetailSheet(STRINGS.title);
  const strips = new Map();
  const refreshers = [];
  let activeTab = 'equipment';
  let armed = '';

  function itemFor(id) {
    const item = career.data.items.find(function byId(entry) {
      return entry.id === id;
    }) || null;
    return item ? itemView(item) : null;
  }
  function currentItem() {
    return itemFor(strips.get(activeTab)?.current?.dataset.item);
  }
  function fleetLine() {
    return FLEET.map(function title(id) {
      return vehicleTitle(id, career.save);
    }).join(' ／ ');
  }
  function fillSheet() {
    const item = currentItem();
    sheet.clear();
    if (!item) return;
    sheet.setTitle(item.label);
    sheet.section(STRINGS.use, paragraph(item.use));
    if (item.unlocks) sheet.section(STRINGS.opens, paragraph(item.unlocks));
    sheet.section(STRINGS.fits, paragraph(item.vehicles.map(vehicleName).join('、')));
    const fleet = paragraph(fleetLine());
    fleet.id = 'shopFleet';
    sheet.section(STRINGS.fleet, fleet);
    sheet.section(STRINGS.rule, paragraph(STRINGS.help[item.kind] || ''));
  }
  function showItem(card) {
    const item = itemFor(card.dataset.item);
    if (!item) return;
    const status = itemStatus(item, career.save, career.data);
    hero.kicker.textContent = [STRINGS.title, STRINGS.tabs[item.kind]].filter(Boolean).join(' · ');
    hero.setTitle(item.label);
    const stats = [
      [STRINGS.price, moneyText(item.price), STRINGS.moneyUnit],
      [STRINGS.fitsStat, String(item.vehicles.length), STRINGS.fitsUnit],
    ];
    if (item.block) stats.push([STRINGS.blockStat, STRINGS.blockValue, '']);
    hero.setStats(stats);
    const chips = [];
    if (status.owned) chips.push([STRINGS.owned, 'ok']);
    else if (!status.available) chips.push([status.reason, 'missing']);
    hero.setChips(chips);
    buyButton.disabled = !status.available;
    let label = armed === item.id ? STRINGS.confirm : STRINGS.buy;
    if (status.owned) label = STRINGS.owned;
    else if (!status.available) label = STRINGS.unavailable;
    buyLabel.textContent = label;
    buyButton.dataset.confirming = String(armed === item.id);
  }
  function renderSummary() {
    summary.textContent = STRINGS.strip.replace('{money}', moneyText(career.save.money))
      .replace('{licence}', gradeFor(career.data, career.save.licence).label);
  }
  function refresh() {
    renderSummary();
    for (const render of refreshers) render();
    const card = strips.get(activeTab)?.current;
    if (card) showItem(card);
  }
  function buy(item) {
    const result = purchase(career.save, career.data, item.id);
    armed = '';
    if (!result.ok) {
      ctx.setStatus(result.error);
      refresh();
      return;
    }
    career.commit();
    const lines = [STRINGS.bought.replace('{item}', item.label)];
    for (const change of result.blocks) {
      lines.push(STRINGS.upgraded.replace('{vehicle}', vehicleName(change.vehicle)).replace('{block}', change.after));
    }
    ctx.setStatus(lines.join(' '));
    refresh();
  }
  // First press arms the purchase, the second one buys; focus stays on the item's tile.
  function press(item) {
    if (!itemStatus(item, career.save, career.data).available) return;
    if (armed !== item.id) {
      armed = item.id;
      refresh();
    } else buy(item);
    root.querySelector(`[data-item="${item.id}"]`)?.focus({ preventScroll: true });
  }
  function itemTile(item) {
    const status = itemStatus(item, career.save, career.data);
    const note = status.owned ? STRINGS.owned : STRINGS.priceNote.replace('{price}', moneyText(item.price));
    const card = tile({ name: item.label, note });
    card.classList.add('career-card', 'career-item');
    card.dataset.item = item.id;
    card.dataset.status = status.owned ? 'owned' : status.available ? 'open' : 'locked';
    if (!status.available && !status.owned) card.setAttribute('aria-disabled', 'true');
    card.addEventListener('click', function choose() {
      press(item);
    });
    return card;
  }
  function pane(kind) {
    return {
      id: kind,
      label: STRINGS.tabs[kind],
      title: STRINGS.help[kind],
      mount(container) {
        const strip = createTileStrip(showItem);
        strips.set(kind, strip);
        container.append(strip.element);
        function render() {
          const keep = strip.current?.dataset.item;
          const cards = career.data.items.filter(function ofKind(item) {
            return item.kind === kind;
          }).map(itemView).map(itemTile);
          strip.fill(cards, cards.find(function kept(card) {
            return card.dataset.item === keep;
          }));
        }
        render();
        refreshers.push(render);
      },
    };
  }
  function selected(id) {
    activeTab = id;
    armed = '';
    const card = strips.get(id)?.current;
    if (card) showItem(card);
  }
  buyButton.addEventListener('click', function buyCurrent() {
    const item = currentItem();
    if (!item) return;
    press(item);
    buyButton.focus({ preventScroll: true });
  });
  hero.actions.append(buyButton, detailButton('shopDetails', sheet, fillSheet));
  const panel = createSettingsPanel({
    idPrefix: 'shop',
    tabs: [pane('equipment'), pane('cosmetic')],
    onSelect: selected,
  });
  root.append(summary, panel.element, hero.element);
  return {
    element: root,
    pose: 'shop',
    tabs: panel,
    enter() {
      armed = '';
      refresh();
    },
  };
}
