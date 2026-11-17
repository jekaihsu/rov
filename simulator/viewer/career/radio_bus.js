// Career radio trigger bus: fires contract.radio.triggers once each when their `when` condition is met
// (near/done deliverable, all required done, safety/collision/overload/silt, client rush, optional window).
// Start lines stay in dive.js; this module only observes the stream and calls say(speaker, text).

import { localize } from '../i18n/core.js';

const STRINGS = localize('career.radio_bus', {
  roles: {
    ye: '葉理',
    lin: '林岑',
    zhou: '周楷',
    fang: '方晴',
    ma: '馬力',
  },
});

const NEAR_M = 3;
const SILT_TRIGGER = 0.35;
const RUSH_T = 480;

function element(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text != null) node.textContent = text;
  return node;
}

function vector(value) {
  return Array.isArray(value) && value.length >= 3 ? value.map(Number) : null;
}

function distance(a, b) {
  return Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);
}

function defaultSay(speaker, text) {
  let node = document.querySelector('.career-radio-bus');
  if (!node) {
    node = element('p', 'career-radio career-radio-bus');
    document.body.append(node);
  }
  node.replaceChildren(element('strong', '', speaker || ''), text || '');
  node.hidden = !(speaker || text);
}

function itemById(snapshot, id) {
  return (snapshot?.items || []).find(function match(item) {
    return item.id === id;
  }) || null;
}

/**
 * contract: contracts.json entry; say(speaker, text) optional caption hook.
 * Returns {observe(state, snapshot, dt), reset}.
 */
export function createRadioBus(contract, { say } = {}) {
  const triggers = Array.isArray(contract?.radio?.triggers) ? contract.radio.triggers.slice() : [];
  const fired = new Set();
  const nearSeen = new Set();
  let safetyCount = 0;
  let collisionCount = 0;
  let overloadCount = 0;
  let rushDone = false;
  const speak = typeof say === 'function' ? say : defaultSay;

  function reset() {
    fired.clear();
    nearSeen.clear();
    safetyCount = 0;
    collisionCount = 0;
    overloadCount = 0;
    rushDone = false;
  }

  function fire(trigger) {
    if (!trigger?.id || fired.has(trigger.id)) return false;
    fired.add(trigger.id);
    speak(trigger.speaker || '', trigger.text || '');
    return true;
  }

  function nearAny(state, snapshot) {
    const pos = vector(state?.pos);
    if (!pos) return false;
    for (const item of snapshot?.items || []) {
      if (!item.point || item.done || nearSeen.has(item.id)) continue;
      if (distance(pos, item.point) <= NEAR_M) {
        nearSeen.add(item.id);
        nearSeen.add('*');
        return true;
      }
    }
    return false;
  }

  function matchWhen(when, state, snapshot) {
    const key = String(when || '');
    if (key === 'start') return false;
    if (key === 'all_required_done' || key === 'all' || key === 'end') {
      return !!snapshot?.complete || (snapshot?.requiredDone > 0
        && snapshot.requiredDone >= snapshot.requiredTotal);
    }
    if (key === 'safety') {
      const n = (snapshot?.penalties || []).filter(function isSafety(entry) {
        return entry.kind === 'safety';
      }).length;
      if (n > safetyCount) {
        safetyCount = n;
        return true;
      }
      return false;
    }
    if (key === 'collision') {
      const n = (snapshot?.penalties || []).filter(function isHit(entry) {
        return entry.kind === 'contact';
      }).length;
      if (n > collisionCount) {
        collisionCount = n;
        return true;
      }
      return false;
    }
    if (key === 'overload' || key === 'tether_tight') {
      const n = (snapshot?.penalties || []).filter(function isOver(entry) {
        return entry.kind === 'overload';
      }).length;
      if (n > overloadCount) {
        overloadCount = n;
        return true;
      }
      return false;
    }
    if (key === 'silt') return Number(state?.silt) > SILT_TRIGGER;
    if (key === 'rush' || key === 'client_rush') {
      if (rushDone) return false;
      if ((Number(state?.t) || 0) > RUSH_T) {
        rushDone = true;
        return true;
      }
      return false;
    }
    if (key === 'near') return nearAny(state, snapshot);
    if (key.startsWith('near:')) {
      const id = key.slice(5);
      if (nearSeen.has(id)) return false;
      const item = itemById(snapshot, id);
      const pos = vector(state?.pos);
      if (!item?.point || !pos) return false;
      if (distance(pos, item.point) <= NEAR_M) {
        nearSeen.add(id);
        return true;
      }
      return false;
    }
    if (key.startsWith('done:')) {
      const id = key.slice(5);
      return !!itemById(snapshot, id)?.done;
    }
    if (key.startsWith('window:')) {
      const minutes = Number(key.slice(7));
      if (!Number.isFinite(minutes)) return false;
      return (Number(state?.t) || 0) >= minutes * 60;
    }
    return false;
  }

  /** Fire triggers whose `when` equals name (for contract-specific cues dive maps). */
  function signal(name) {
    const key = String(name || '');
    if (!key) return;
    for (const trigger of triggers) {
      if (fired.has(trigger.id)) continue;
      if (trigger.when === key) fire(trigger);
    }
  }

  function observe(state, snapshot, dt = 0) {
    void dt;
    if (!state || !snapshot) return;
    for (const trigger of triggers) {
      if (fired.has(trigger.id)) continue;
      if (matchWhen(trigger.when, state, snapshot)) fire(trigger);
    }
  }

  return { observe, signal, reset, roles: STRINGS.roles };
}
