// Repair bills, company advances and reputation penalties for YX work orders
// (viewer/career/repair.js, scoring.js, settle.js, save.js).
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { careerDataFrom } from '../viewer/career/data.js';
import { assessRepairs, applyRepairsAndDebt } from '../viewer/career/repair.js';
import { contractById } from '../viewer/career/rules.js';
import { defaultSave, normalizeSave } from '../viewer/career/save.js';
import {
  REPUTATION_ABORT,
  REPUTATION_ABORT_UNSAFE,
  REPUTATION_FACILITY,
  REPUTATION_FALSE_DELIVERY,
  REPUTATION_ON_TIME,
  REPUTATION_PARTIAL,
  reputationGain,
} from '../viewer/career/scoring.js';
import { settleDive } from '../viewer/career/settle.js';

const CAREER = new URL('../viewer/career/', import.meta.url);

async function json(name) {
  return JSON.parse(await readFile(new URL(name, CAREER), 'utf8'));
}

async function careerData() {
  return careerDataFrom({
    contractsFile: await json('contracts.json'),
    licencesFile: await json('licences.json'),
    equipmentFile: await json('equipment.json'),
    repairPricesFile: await json('repair_prices.json'),
  });
}

function snapshot(overrides = {}) {
  return {
    items: [],
    done: 6,
    total: 6,
    requiredDone: 5,
    requiredTotal: 5,
    complete: true,
    penalties: [],
    tetherBroken: false,
    ...overrides,
  };
}

const CONTRACT = {
  id: 'test',
  pay: 10000,
  reputation: 10,
  client: 'harbor',
  title: 'test',
  scenario: 'harbor_inspection',
};

test('repair prices file is game values and covers thruster / leak / tether / accessory', async () => {
  const prices = await json('repair_prices.json');
  assert.match(prices.note, /遊戲設定值/);
  assert.ok(prices.thruster.replace > prices.thruster.major);
  assert.ok(prices.tether.replace > prices.tether.service);
  assert.ok(prices.accessory.recover > 0);
});

test('assessRepairs prices thruster health, leak, wraps and lost gear without inventing physics', async () => {
  const prices = await json('repair_prices.json');
  const items = (await json('equipment.json')).items;
  const healthy = assessRepairs({ health: [1, 1, 1, 1, 1, 1], leak: { detected: false } },
    snapshot(), { prices });
  assert.equal(healthy.total, 0);
  const dented = assessRepairs({
    health: [0.9, 0.4, 0, 1, 1, 1],
    leak: { detected: true },
    tether: { broken: false, wraps: { pile: 1.2 } },
  }, snapshot({
    penalties: [{ kind: 'wrap', label: 'wrap', points: 10 }],
  }), { prices });
  assert.ok(dented.items.some((entry) => entry.id === 'thruster-0-minor'));
  assert.ok(dented.items.some((entry) => entry.id === 'thruster-1-major'));
  assert.ok(dented.items.some((entry) => entry.id === 'thruster-2-replace'));
  assert.ok(dented.items.some((entry) => entry.id === 'leak'));
  assert.ok(dented.items.some((entry) => entry.id === 'tether-service'));
  const lost = assessRepairs({ health: [1], leak: { detected: false }, tether: { broken: true } },
    snapshot({ tetherBroken: true }), {
      owned: ['laser_scaler', 'sticker_yx_logo'],
      items,
      prices,
    });
  assert.ok(lost.items.some((entry) => entry.id === 'tether-replace'));
  assert.ok(lost.items.some((entry) => entry.id === 'accessory-laser_scaler'));
  assert.equal(lost.items.some((entry) => entry.id === 'accessory-sticker_yx_logo'), false);
});

test('company advances when pay cannot cover repairs; later pay repays debt first', () => {
  const short = applyRepairsAndDebt(1000, 4500, 0);
  assert.equal(short.received, 0);
  assert.equal(short.advance, 3500);
  assert.equal(short.debt, 3500);
  const repay = applyRepairsAndDebt(5000, 0, 3500);
  assert.equal(repay.repaid, 3500);
  assert.equal(repay.received, 1500);
  assert.equal(repay.debt, 0);
  const both = applyRepairsAndDebt(2000, 800, 500);
  assert.equal(both.repairFromPay, 800);
  assert.equal(both.repaid, 500);
  assert.equal(both.received, 700);
  assert.equal(both.debt, 0);
});

test('reputation: safe abort is mild, facility damage and false delivery hit harder, gold on-time bonuses', () => {
  assert.equal(reputationGain(CONTRACT, { outcome: 'aborted', medal: 'none' }, {
    snapshot: snapshot({ complete: false, tetherBroken: false }),
  }), REPUTATION_ABORT);
  assert.equal(reputationGain(CONTRACT, { outcome: 'aborted', medal: 'none' }, {
    snapshot: snapshot({ complete: false, tetherBroken: true }),
  }), REPUTATION_ABORT_UNSAFE);
  const facility = reputationGain(CONTRACT, { outcome: 'complete', medal: 'bronze' }, {
    snapshot: snapshot({
      penalties: [{ kind: 'safety', severity: 'hard', label: 'LOTO', points: 25 }],
    }),
    duration_s: 600,
  });
  assert.equal(facility, Math.round(10 * 1) + REPUTATION_FACILITY);
  const gold = reputationGain(CONTRACT, { outcome: 'complete', medal: 'gold' }, {
    snapshot: snapshot(),
    duration_s: 900,
  });
  assert.equal(gold, Math.round(10 * 1.5) + REPUTATION_ON_TIME);
  const late = reputationGain(CONTRACT, { outcome: 'complete', medal: 'gold' }, {
    snapshot: snapshot(),
    duration_s: 2000,
  });
  assert.equal(late, Math.round(10 * 1.5));
  const thin = reputationGain(CONTRACT, { outcome: 'partial', medal: 'none' }, {
    snapshot: snapshot({ complete: false, requiredDone: 3, requiredTotal: 5 }),
  });
  assert.equal(thin, REPUTATION_PARTIAL + REPUTATION_FALSE_DELIVERY);
});

test('settling with damage deducts a repair bill, can create debt, and never blocks the next job', async () => {
  const data = await careerData();
  const save = defaultSave();
  save.owned.push('laser_scaler');
  const contract = contractById(data, 'p1_pool_checkout');
  const wrecked = settleDive(save, data, contract, {
    snapshot: snapshot({
      done: 7,
      total: 7,
      requiredDone: 6,
      requiredTotal: 6,
      tetherBroken: true,
      complete: false,
      penalties: [{ kind: 'contact', severity: 'severe', label: 'hit', points: 30 }],
    }),
    submitted: true,
    duration_s: 400,
    real_s: 400,
    assisted_s: 0,
    vehicle: 'x1',
    block: 1,
    state: {
      health: [0, 1, 1, 1, 1, 1],
      leak: { detected: true },
      tether: { broken: true },
    },
  });
  assert.ok(wrecked.summary.repairs.total > wrecked.summary.pay.net);
  assert.equal(wrecked.summary.received, 0);
  assert.ok(wrecked.summary.debt.after > 0);
  assert.equal(save.money, 0);
  assert.equal(save.debt, wrecked.summary.debt.after);
  assert.ok(save.owned.includes('laser_scaler'), 'company replaces gear; ownership stays');
  const again = settleDive(save, data, contract, {
    snapshot: snapshot({ done: 7, total: 7, requiredDone: 6, requiredTotal: 6 }),
    duration_s: 500,
    real_s: 500,
    assisted_s: 0,
    vehicle: 'x1',
    block: 1,
    state: { health: [1, 1, 1, 1, 1, 1], leak: { detected: false } },
  });
  assert.ok(again.summary.debt.repaid > 0);
  assert.ok(again.summary.received >= 0);
  assert.equal(save.debt, again.summary.debt.after);
  assert.ok(save.money >= 0);
});

test('old career saves without debt still load and default debt to zero', () => {
  const legacy = normalizeSave({
    money: 1200,
    licence: 'trainee',
    reputation: { harbor: 8 },
    owned: ['laser_scaler'],
    logbook: [{ outcome: 'complete', medal: 'gold', pay: 4000 }],
  });
  assert.equal(legacy.debt, 0);
  assert.equal(legacy.money, 1200);
  assert.equal(legacy.logbook[0].repair, 0);
});
