// Optional browser haptics; unsupported or disconnected devices are silent.
// Honour the padHaptics fidelity preference and the mixer-style mute in rov.input.v1.
import {padHapticsEnabled} from './haptics_fidelity.js';

// [duration ms, strong, weak]. Felt in the hand, so they stay short and distinct: a firm unlock, a light lock,
// a crisp shutter, bumps scaled by impact, a long low pull for tension and a sharp tug when the tether snags.
const PATTERNS = {
  unlock: [100, 0.3, 0.1],
  lock: [60, 0.12, 0.05],
  photo: [45, 0.1, 0.3],
  touch: [80, 0.2, 0.2],
  hard: [250, 0.8, 0.7],
  tension: [180, 0.4, 0.2],
  snag: [220, 0.6, 0.35],
  broken: [420, 1, 0.8],
};

export function createHaptics(getPad, settings, fidelity) {
  function pulse(name) {
    if (settings.haptics === false) return;
    if (!padHapticsEnabled(fidelity)) return;
    const actuator = getPad()?.vibrationActuator;
    if (!actuator?.playEffect) return;
    const [duration, strong, weak] = PATTERNS[name] || PATTERNS.touch;
    const strength = settings.strength ?? 1;
    const effect = actuator.effects?.includes('trigger-rumble') ? 'trigger-rumble' : 'dual-rumble';
    try {
      Promise.resolve(
        actuator.playEffect(effect, {
          duration,
          startDelay: 0,
          strongMagnitude: strong * strength,
          weakMagnitude: weak * strength,
          leftTrigger: strong * strength,
          rightTrigger: weak * strength,
        }),
      ).catch(function ignore() {});
    } catch {}
  }
  return {pulse};
}
