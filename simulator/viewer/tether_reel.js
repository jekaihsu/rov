// Tether reel controls: tender rate commands and the optional constant-tension "auto payout".
// Real small-ROV practice is a human tender on a passive or braked drum (research_notes/臍帶纜物理與收放文獻/
// shipboard_handling.md §1, §5), so automatic tension keeping is a fidelity item that is off in `real`.
// New `reel` messages are only sent once the server's state carries `tether.reel`; older servers get the
// legacy `auto_payout` / `payout` messages instead (PROTOCOL.md §tether).
import {getFidelity, registerFidelityItem} from './fidelity.js';

const STRINGS = {
  autoPayout: '自動收放纜',
  autoPayoutHelp: '恆張力纜盤（綜合推論，非廠商功能）：張力高時放纜、鬆弛時慢收。真機為助手手動收放，預設關閉。',
  legacyStep: 1
};
const LEGACY_METRES = {haul_in: -STRINGS.legacyStep, pay_out: STRINGS.legacyStep};

function isTrue(value) {
  return value === true;
}

registerFidelityItem({
  id: 'autoPayout', descriptionKey: 'autoPayoutHelp', type: 'toggle',
  defaults: {real: false, assisted: true}, exceedsReal: true, exceeds: isTrue
}, {autoPayout: STRINGS.autoPayout, autoPayoutHelp: STRINGS.autoPayoutHelp});

// Returns the reel message for a fidelity value: auto keeps tension, otherwise the drum turns freely.
export function reelCommandFor(autoPayout) {
  return {type: 'reel', command: autoPayout ? 'auto' : 'free'};
}

// Wires the auto-payout toggle and the reel buttons. `send` posts one viewer message.
export function installTetherReel({send, doc = globalThis.document, fidelity = getFidelity()}) {
  let supported = false;
  let synced = false;
  const toggle = doc?.getElementById('autoPay');

  function pushFidelity() {
    const auto = fidelity.get('autoPayout');
    if (supported) send(reelCommandFor(auto));
    else send({type: 'auto_payout', value: auto});
  }
  function onToggle() {
    fidelity.set('autoPayout', !!toggle.checked);
  }
  function onButton(event) {
    const command = event.currentTarget.dataset.reel;
    if (supported) {
      send({type: 'reel', command});
      return;
    }
    if (LEGACY_METRES[command]) send({type: 'payout', metres: LEGACY_METRES[command]});
  }
  function onFidelity(snapshot, changed) {
    if (changed.includes('autoPayout')) pushFidelity();
  }
  if (toggle) toggle.onchange = onToggle;
  for (const button of doc?.querySelectorAll('[data-reel]') || []) button.onclick = onButton;
  fidelity.subscribe(onFidelity);

  let lastTime = -Infinity;
  // Reflects the server's reel state. The first state, and the first after a scenario reset (sim time
  // jumps back), applies the fidelity value, because a new scenario starts with the default reel mode.
  return function updateTetherReel(tether = {}, simTime = 0) {
    supported = !!tether.reel;
    if (simTime < lastTime - 1) synced = false;
    lastTime = simTime;
    if (!synced && tether.length !== undefined) {
      synced = true;
      pushFidelity();
    }
    if (toggle && doc.activeElement !== toggle) toggle.checked = !!tether.auto_payout;
    const mode = tether.reel?.mode;
    for (const button of doc?.querySelectorAll('[data-reel]') || []) {
      button.classList.toggle('on', button.dataset.reel === mode);
    }
  };
}
