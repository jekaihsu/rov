// Optional browser haptics; unsupported or disconnected devices are silent.
// Honour the padHaptics fidelity preference (the only mute switch after I3). Strength comes from display
// preferences; motion comfort scales it down further so a comfort session stays gentle.
import { padHapticsEnabled } from './haptics_fidelity.js';
import { COMFORT_HAPTIC_SCALE, getDisplayPrefs } from '../prefs/display.js';

// Same id as prefs/camera_items.js MOTION_COMFORT_ITEM; keep the string here so this module does not
// register fidelity items just by being imported from the input layer tests.
const MOTION_COMFORT_ITEM = 'motionComfort';

// [duration ms, strong, weak]. Felt in the hand, so they stay short and distinct: a firm unlock, a light lock,
// a crisp shutter, bumps scaled by impact, a long low pull for tension and a sharp tug when the tether snags.
const PATTERNS = {
  unlock: [100, 0.3, 0.1],
  lock: [60, 0.12, 0.05],
  failsafe: [300, 0.58, 0.16],
  photo: [45, 0.1, 0.3],
  touch: [80, 0.2, 0.2],
  hard: [250, 0.8, 0.7],
  tension: [180, 0.4, 0.2],
  snag: [220, 0.6, 0.35],
  broken: [420, 1, 0.8],
};

export function hapticMagnitude(settings, fidelity, prefs = getDisplayPrefs()) {
  // The advanced controller dialog still owns `settings.strength`; the display tab mirrors it in prefs.
  let stored = 1;
  if (prefs?.get) stored = prefs.get('hapticStrength') ?? 1;
  if (Number.isFinite(settings?.strength)) stored = settings.strength;
  const comfort = !!fidelity?.get?.(MOTION_COMFORT_ITEM);
  return Math.max(0, Math.min(1, stored * (comfort ? COMFORT_HAPTIC_SCALE : 1)));
}

export function createHaptics(getPad, settings, fidelity) {
  function pulse(name) {
    if (!padHapticsEnabled(fidelity)) return;
    const actuator = getPad()?.vibrationActuator;
    if (!actuator?.playEffect) return;
    const [duration, strong, weak] = PATTERNS[name] || PATTERNS.touch;
<<<<<<< HEAD
    const strength = settings.strength ?? 1;
=======
    const strength = hapticMagnitude(settings, fidelity);
>>>>>>> origin/main
    if (strength <= 0) return;
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
  return { pulse };
}
