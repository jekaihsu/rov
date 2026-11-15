// Optional browser haptics; unsupported or disconnected devices are silent.
// Honour the padHaptics fidelity preference (the only mute switch after I3).
import {padHapticsEnabled} from './haptics_fidelity.js';

const PATTERNS = {
  unlock: [100, 0.3, 0.1],
  photo: [45, 0.1, 0.3],
  touch: [80, 0.2, 0.2],
  hard: [250, 0.8, 0.7],
  tension: [180, 0.4, 0.2],
};

export function createHaptics(getPad, settings, fidelity) {
  function pulse(name) {
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
