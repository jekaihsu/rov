// YX equipment department rules: what an item costs, whether this save may buy it (licence, money, already
// owned), the purchase itself, and the Block level of each vehicle (1 + the Block-raising equipment owned that
// fits it). Equipment only opens deliverables and work orders; no item changes a physical value. Pure functions.
import { gradeFor, hasLicence } from './rules.js';
import { FLEET } from './save.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('career.shop_rules', {
  owned: '已擁有',
  licence: '需要「{licence}」執照',
  money: '資金不足（還差 {missing} 元）',
  unknown: '找不到這個品項。',
});

/** Block level of a vehicle for a save: 1 plus each owned Block-raising item that fits it. */
export function blockLevel(save, data, modelId) {
  return 1 + data.items.filter(function raises(item) {
    return item.block && item.vehicles.includes(modelId) && save.owned.includes(item.id);
  }).length;
}

/** Writes every vehicle's Block level into the save (fleet_names.js blockFor() reads it). */
export function updateBlocks(save, data) {
  for (const id of FLEET) save.vehicles[id] = { block: blockLevel(save, data, id) };
  return save.vehicles;
}

/** {owned, available, reason} for one item. */
export function itemStatus(item, save, data) {
  if (save.owned.includes(item.id)) return { owned: true, available: false, reason: STRINGS.owned };
  if (!hasLicence(save, data, item.licence || 'none')) {
    return { owned: false, available: false,
      reason: STRINGS.licence.replace('{licence}', gradeFor(data, item.licence).label) };
  }
  if (save.money < item.price) {
    return { owned: false, available: false,
      reason: STRINGS.money.replace('{missing}', (item.price - save.money).toLocaleString('en-US')) };
  }
  return { owned: false, available: true, reason: '' };
}

/**
 * Buys an item: money down, the item owned, Block levels updated. Returns {ok, error, blocks: [{vehicle, before,
 * after}]} listing the vehicles whose Block went up.
 */
export function purchase(save, data, itemId) {
  const item = data.items.find(function byId(entry) {
    return entry.id === itemId;
  });
  if (!item) return { ok: false, error: STRINGS.unknown, blocks: [] };
  const status = itemStatus(item, save, data);
  if (!status.available) return { ok: false, error: status.reason, blocks: [] };
  const before = Object.fromEntries(FLEET.map(function level(id) {
    return [id, save.vehicles[id]?.block || 1];
  }));
  save.money -= item.price;
  save.owned.push(item.id);
  updateBlocks(save, data);
  const blocks = FLEET.filter(function raised(id) {
    return save.vehicles[id].block > before[id];
  }).map(function change(id) {
    return { vehicle: id, before: before[id], after: save.vehicles[id].block };
  });
  return { ok: true, error: '', item, blocks };
}

/** Whether a sticker preset may be chosen: the free ones always, a shop cosmetic once owned. */
export function stickerAvailable(save, data, preset) {
  const item = data.items.find(function bySticker(entry) {
    return entry.sticker === preset;
  });
  return !item || save.owned.includes(item.id);
}
