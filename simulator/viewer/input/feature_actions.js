// Route optional feature actions through the input layer's existing focus and device guards.
import {bindingValue} from './actions.js';

export function createFeatureActions(getBinding) {
  const actions = new Map();
  const previous = new Map();
  function register(definitions) {
    for (const [name, action] of Object.entries(definitions)) actions.set(name, action);
  }
  function key(event) {
    for (const action of actions.values()) {
      if (!action.keys?.includes(event.code) || action.enabled?.() === false) continue;
      if (!event.repeat) action.run(1, 0);
      return true;
    }
    return false;
  }
  function sample(snapshot, dt) {
    const consumed = new Set();
    for (const [name, action] of actions) {
      const value = snapshot ? bindingValue(getBinding(name, action.binding), snapshot) : 0;
      if (action.enabled?.() !== false && snapshot) {
        if (action.continuous || (value > .5 && !(previous.get(name) > .5))) action.run(value, dt);
        for (const channel of action.consume || []) consumed.add(channel);
      }
      previous.set(name, value);
    }
    return consumed;
  }
  return {register, key, sample};
}
