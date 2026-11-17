// Deliverable-based scoring of YX work orders: what each deliverable kind is called, the score of a dive from its
// checklist and penalties, the medal, the payout (base × quality − penalties) with the "abort but pass" path, and
// reputation deltas (safe abort vs facility damage / false delivery, gold and on-time). Progress is never locked.
// Pure functions, no DOM; the numbers are game values, not an industry standard.
import { medalFor } from '../play/results_model.js';

export const DELIVERABLE_KIND_LABELS = {
  state: '程序',
  checkpoint: '到點',
  station_keep: '懸停',
  inspect: '目視',
  photo: '照片',
  measure: '量測',
  probe: '探測',
  confirm: '確認',
  lift: '回收',
  surface: '回收',
};

// Repeating a contract already completed pays this share of its base pay.
export const REPEAT_RATE = 0.75;
// Quality multiplier on the base pay per medal of a completed contract.
export const QUALITY = { gold: 1.3, silver: 1.15, bronze: 1, none: 0.85 };
// A completed contract never pays less than this share of its gross, whatever the deductions.
export const PAY_FLOOR = 0.25;
// "Abort but pass": share of the base pay for the required work delivered.
export const PARTIAL_RATE = 0.4;
// Default share of required deliverables a partial submission needs to be accepted.
export const PARTIAL_MIN = 0.5;
// Reputation earned per medal (× the contract's reputation), for a partial job, and lost for an abandoned one.
export const REPUTATION_MEDAL = { gold: 1.5, silver: 1.2, bronze: 1, none: 0.8 };
export const REPUTATION_PARTIAL = 2;
export const REPUTATION_ABORT = -2;
// Safe abort (no tether break, no client-facility hit) vs damaging facilities / false delivery / broken tether.
export const REPUTATION_ABORT_UNSAFE = -8;
export const REPUTATION_FACILITY = -6;
export const REPUTATION_FALSE_DELIVERY = -5;
// Gold already multiplies the base; on-time (under the soft budget) adds a flat bonus.
export const REPUTATION_ON_TIME = 2;
// Soft "on time" budget when a contract has no time_budget_s: 25 minutes (game-plan §11).
export const DEFAULT_TIME_BUDGET_S = 1500;
const ROUND_TO = 10;

function roundMoney(value) {
  return Math.max(0, Math.round(value / ROUND_TO) * ROUND_TO);
}

function penaltyPoints(penalties) {
  return penalties.reduce(function add(total, entry) {
    return total + (Number(entry.points) || 0);
  }, 0);
}

/**
 * Score of a dive from the tracker snapshot (deliverables.js): the share of all deliverables delivered (optional
 * ones are the way to gold) minus the penalty points; 0–100. Medal only for a complete job.
 */
export function scoreDive(snapshot) {
  const base = 100 * snapshot.done / Math.max(1, snapshot.total);
  const points = penaltyPoints(snapshot.penalties);
  const score = Math.max(0, Math.min(100, Math.round(base - points)));
  const complete = !!snapshot.complete && !snapshot.tetherBroken;
  return { score, medal: medalFor(score, complete), complete, points };
}

/** Whether an early submission is accepted as partial work. */
export function partialAccepted(contract, snapshot) {
  const share = snapshot.requiredDone / Math.max(1, snapshot.requiredTotal);
  return !snapshot.tetherBroken && share >= (contract.partial ?? PARTIAL_MIN);
}

/**
 * Payout of a dive. submitted: the player handed in before finishing (partial when enough is delivered, else
 * aborted). repeat: the contract was completed before. Returns {outcome, base, rate, quality, gross, penalties,
 * deduction, net} with the deductions itemised (each penalty point costs 1 % of the base).
 */
export function payout(contract, snapshot, { repeat = false, submitted = false } = {}) {
  const scored = scoreDive(snapshot);
  const rate = repeat ? REPEAT_RATE : 1;
  const base = Math.round((contract.pay || 0) * rate);
  let outcome = 'aborted';
  if (scored.complete && !submitted) outcome = 'complete';
  else if (scored.complete || partialAccepted(contract, snapshot)) outcome = 'partial';
  const share = snapshot.requiredDone / Math.max(1, snapshot.requiredTotal);
  let quality = 0;
  let gross = 0;
  if (outcome === 'complete') {
    quality = QUALITY[scored.medal] ?? QUALITY.none;
    gross = roundMoney(base * quality);
  } else if (outcome === 'partial') {
    quality = PARTIAL_RATE * share;
    gross = roundMoney(base * quality);
  }
  const penalties = outcome === 'aborted' ? [] : snapshot.penalties.map(function cost(entry) {
    return { label: entry.label, points: entry.points, amount: roundMoney(base * entry.points / 100) };
  });
  const asked = penalties.reduce(function add(total, entry) {
    return total + entry.amount;
  }, 0);
  const floor = outcome === 'complete' ? roundMoney(gross * PAY_FLOOR) : 0;
  const net = Math.max(floor, gross - asked);
  return {
    outcome,
    score: outcome === 'aborted' ? 0 : scored.score,
    medal: outcome === 'complete' ? scored.medal : 'none',
    base,
    rate,
    repeat,
    quality,
    gross,
    penalties,
    deduction: gross - net,
    net,
  };
}

function facilityDamaged(snapshot) {
  return (snapshot?.penalties || []).some(function hit(entry) {
    return entry.kind === 'safety' || (entry.kind === 'contact' && (entry.severity === 'hard'
      || entry.severity === 'severe'));
  });
}

/**
 * Reputation change with the contract's client for a settled dive.
 * context: {snapshot, duration_s} from the dive; facility damage and false delivery hit harder than a safe abort.
 */
export function reputationGain(contract, pay, context = {}) {
  const snapshot = context.snapshot || null;
  const facility = facilityDamaged(snapshot);
  if (pay.outcome === 'complete') {
    let delta = Math.round((contract.reputation ?? 10) * (REPUTATION_MEDAL[pay.medal] ?? 1));
    if (facility) delta += REPUTATION_FACILITY;
    const budget = Number(contract.time_budget_s);
    const limit = Number.isFinite(budget) && budget > 0 ? budget : DEFAULT_TIME_BUDGET_S;
    const duration = Number(context.duration_s);
    if (pay.medal === 'gold' && Number.isFinite(duration) && duration > 0 && duration <= limit) {
      delta += REPUTATION_ON_TIME;
    }
    return delta;
  }
  if (pay.outcome === 'partial') {
    // A thin partial that barely clears the gate counts as shaky delivery when quality is poor.
    const share = snapshot
      ? snapshot.requiredDone / Math.max(1, snapshot.requiredTotal)
      : 1;
    let delta = REPUTATION_PARTIAL;
    if (share < 0.75) delta += REPUTATION_FALSE_DELIVERY;
    if (facility) delta += REPUTATION_FACILITY;
    return delta;
  }
  if (snapshot?.tetherBroken || facility) return REPUTATION_ABORT_UNSAFE;
  return REPUTATION_ABORT;
}
