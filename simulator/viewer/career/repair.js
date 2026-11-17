// Repair bill for a settled YX dive: reads thruster health, leak, tether and owned gear from the server state
// the dive already saw, prices them from repair_prices.json (game values), and never invents new physics.
// Pure functions; settle.js turns the bill into pay deductions and company advances.
import { localize } from '../i18n/core.js';

const STRINGS = localize('career.repair', {
  thrusterMinor: '推進器 T{n} 保養',
  thrusterMajor: '推進器 T{n} 大修',
  thrusterReplace: '推進器 T{n} 更換',
  leak: '艙體進水密封修復',
  tetherService: '纜線檢查與整理',
  tetherReplace: '臍帶纜更換',
  accessory: '遺失配件找回／補裝（{item}）',
  accessoryGeneric: '作業配件',
});

const DEFAULT_PRICES = {
  thruster: { minor: 800, major: 2500, replace: 6000, minorBelow: 0.85, majorBelow: 0.6 },
  leak: 4500,
  tether: { service: 1200, replace: 9000 },
  accessory: { recover: 1500 },
};

function money(value) {
  return Math.max(0, Math.round(Number(value) || 0));
}

function format(template, values) {
  return template.replace(/\{(\w+)\}/g, function fill(match, key) {
    return key in values ? String(values[key]) : match;
  });
}

function pricesOf(prices) {
  return prices && typeof prices === 'object' ? prices : DEFAULT_PRICES;
}

function thrusterLine(index, health, prices) {
  const table = prices.thruster || DEFAULT_PRICES.thruster;
  const level = Number(health);
  if (!Number.isFinite(level) || level >= 1) return null;
  const n = index + 1;
  if (level <= 0) {
    return { id: `thruster-${index}-replace`, label: format(STRINGS.thrusterReplace, { n }),
      amount: money(table.replace) };
  }
  if (level < (table.majorBelow ?? 0.6)) {
    return { id: `thruster-${index}-major`, label: format(STRINGS.thrusterMajor, { n }),
      amount: money(table.major) };
  }
  if (level < (table.minorBelow ?? 0.85)) {
    return { id: `thruster-${index}-minor`, label: format(STRINGS.thrusterMinor, { n }),
      amount: money(table.minor) };
  }
  return { id: `thruster-${index}-minor`, label: format(STRINGS.thrusterMinor, { n }),
    amount: money(table.minor) };
}

function gearItems(owned, catalogue) {
  if (!Array.isArray(owned) || !owned.length) return [];
  const byId = new Map((catalogue || []).map(function entry(item) {
    return [item.id, item];
  }));
  return owned.map(function id(entry) {
    return byId.get(entry);
  }).filter(function mounted(item) {
    return item && item.kind === 'equipment';
  });
}

/**
 * state: last vehicle state (health, leak, tether); snapshot: deliverables tracker snapshot (penalties,
 * tetherBroken); owned / items: career save gear and the equipment catalogue; prices: repair_prices.json.
 * Returns {items: [{id, label, amount}], total}.
 */
export function assessRepairs(state, snapshot, { owned = [], items = [], prices = null } = {}) {
  const table = pricesOf(prices);
  const bill = [];
  const health = Array.isArray(state?.health) ? state.health : [];
  health.forEach(function each(level, index) {
    const line = thrusterLine(index, level, table);
    if (line) bill.push(line);
  });
  if (state?.leak?.detected) {
    bill.push({ id: 'leak', label: STRINGS.leak, amount: money(table.leak) });
  }
  const broken = !!(snapshot?.tetherBroken || state?.tether?.broken);
  const tetherHit = (snapshot?.penalties || []).some(function tether(entry) {
    return entry.kind === 'overload' || entry.kind === 'wrap';
  });
  if (broken) {
    bill.push({ id: 'tether-replace', label: STRINGS.tetherReplace,
      amount: money(table.tether?.replace) });
    for (const gear of gearItems(owned, items)) {
      bill.push({
        id: `accessory-${gear.id}`,
        label: format(STRINGS.accessory, { item: gear.label || STRINGS.accessoryGeneric }),
        amount: money(table.accessory?.recover),
      });
    }
  } else if (tetherHit) {
    bill.push({ id: 'tether-service', label: STRINGS.tetherService,
      amount: money(table.tether?.service) });
  }
  const total = bill.reduce(function add(sum, entry) {
    return sum + entry.amount;
  }, 0);
  return { items: bill, total };
}

/**
 * Applies a repair total to this dive's pay and any company debt already on the save.
 * payNet: payout after score deductions; debtBefore: save.debt. Returns the pocketed amount, the new debt,
 * how much the company advanced, and how much of the old debt this dive repaid. Money never goes negative.
 */
export function applyRepairsAndDebt(payNet, repairTotal, debtBefore = 0) {
  const pay = money(payNet);
  const repairs = money(repairTotal);
  const owed = money(debtBefore);
  const repairFromPay = Math.min(pay, repairs);
  const advance = repairs - repairFromPay;
  const afterRepair = pay - repairFromPay;
  const repaid = Math.min(afterRepair, owed);
  const received = afterRepair - repaid;
  const debt = owed - repaid + advance;
  return { received, debt, advance, repaid, repairFromPay, repairs };
}
