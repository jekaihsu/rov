// YX 裝備部: the launch menu shop. Equipment that a real ROV carries and that opens deliverables (laser scaler,
// imaging sonar, CP probe, UT gauge, gripper) and cosmetics (stickers). Each card says what the item really does,
// what it opens, which vehicles it fits and what it costs; buying takes a second press, and equipment raises the
// Block number of the vehicles it fits. No stat boosts and no real-money store.
import { createSettingsPanel } from '../menu/settings.js';
import { readout } from '../menu/screens.js';
import { vehicleName, vehicleTitle } from '../fleet_names.js';
import { moneyText } from './board.js';
import { gradeFor } from './rules.js';
import { itemStatus, purchase } from './shop_rules.js';

const STRINGS = {
  title: 'YX 裝備部',
  strip: '資金 {money} 元 · {licence}',
  tabs: { equipment: '作業裝備', cosmetic: '外觀' },
  help: {
    equipment: '只賣真實存在的配件：它們讓你能接更多種工單，不會讓機子變快或變強。',
    cosmetic: '機身貼紙與塗裝條紋，只影響外觀。',
  },
  price: '價格',
  moneyUnit: '元',
  opens: '開放：{text}',
  fits: '適用：{list}',
  block: '裝上後 Block +1',
  buy: '購買',
  confirm: '再按一次確認購買',
  bought: '已購入「{item}」。',
  upgraded: '{vehicle} 升級為 Block {block}。',
};

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

/** The shop screen. ctx.career: career/menu.js context. */
export function buildShop(ctx) {
  const career = ctx.career;
  const root = element('section', 'menu-screen career-board career-shop');
  root.dataset.screen = 'shop';
  root.setAttribute('aria-label', STRINGS.title);
  const head = element('div', 'career-board-head');
  const strip = element('p', 'career-strip');
  strip.id = 'shopSummary';
  head.append(element('h2', 'menu-heading', STRINGS.title), strip);
  root.append(head);
  const refreshers = [];
  let armed = '';

  function renderStrip() {
    strip.textContent = STRINGS.strip.replace('{money}', moneyText(career.save.money))
      .replace('{licence}', gradeFor(career.data, career.save.licence).label);
  }
  function refresh() {
    renderStrip();
    for (const render of refreshers) render();
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
  function itemCard(item) {
    const status = itemStatus(item, career.save, career.data);
    const card = element('button', 'menu-site menu-play-card career-card career-item');
    card.type = 'button';
    card.dataset.item = item.id;
    card.dataset.status = status.owned ? 'owned' : status.available ? 'open' : 'locked';
    if (!status.available) card.setAttribute('aria-disabled', 'true');
    const body = element('span', 'menu-site-body');
    body.append(element('strong', 'menu-card-title', item.label));
    body.append(element('span', 'menu-card-line', item.use));
    if (item.unlocks) body.append(element('span', 'career-item-line', STRINGS.opens.replace('{text}', item.unlocks)));
    const fits = item.vehicles.map(vehicleName).join('、');
    const fitLine = [STRINGS.fits.replace('{list}', fits)];
    if (item.block) fitLine.push(STRINGS.block);
    body.append(element('span', 'career-item-line', fitLine.join(' · ')));
    const numbers = element('span', 'menu-site-numbers');
    numbers.append(readout(STRINGS.price, moneyText(item.price), STRINGS.moneyUnit));
    body.append(numbers);
    const foot = element('span', 'menu-card-foot');
    let action = status.reason;
    if (status.available) action = armed === item.id ? STRINGS.confirm : STRINGS.buy;
    const label = element('span', status.available ? 'menu-row-status career-buy' : 'menu-card-lock', action);
    foot.append(label);
    body.append(foot);
    card.append(body);
    card.addEventListener('click', function choose() {
      if (!itemStatus(item, career.save, career.data).available) return;
      if (armed !== item.id) {
        armed = item.id;
        refresh();
        root.querySelector(`[data-item="${item.id}"]`)?.focus({ preventScroll: true });
        return;
      }
      buy(item);
      root.querySelector(`[data-item="${item.id}"]`)?.focus({ preventScroll: true });
    });
    return card;
  }
  function pane(kind) {
    return {
      id: kind,
      label: STRINGS.tabs[kind],
      mount(container) {
        container.append(element('p', 'menu-help', STRINGS.help[kind]));
        const grid = element('div', 'menu-card-grid');
        container.append(grid);
        function render() {
          grid.replaceChildren(...career.data.items.filter(function ofKind(item) {
            return item.kind === kind;
          }).map(itemCard));
        }
        render();
        refreshers.push(render);
      },
    };
  }
  const panel = createSettingsPanel({ idPrefix: 'shop', tabs: [pane('equipment'), pane('cosmetic')] });
  const fleet = element('p', 'career-strip career-fleet');
  fleet.id = 'shopFleet';
  root.append(panel.element);
  root.append(fleet);
  refreshers.push(function renderFleet() {
    fleet.textContent = ['x1', 'bluerov2_heavy', 'falcon'].map(function title(id) {
      return vehicleTitle(id, career.save);
    }).join(' ／ ');
  });
  return {
    element: root,
    pose: 'training',
    tabs: panel,
    enter() {
      armed = '';
      refresh();
    },
  };
}
