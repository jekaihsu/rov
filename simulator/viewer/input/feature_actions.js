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
  // Run one action by name for an input that the caller has already resolved.
  function run(name) {
    const action = actions.get(name);
    if (!action || action.enabled?.() === false) return false;
    action.run(1, 0);
    return true;
  }
  // values: optional action → value map resolved by the binding table; without it bindings are read directly.
  function sample(snapshot, dt, values = null) {
    const consumed = new Set();
    for (const [name, action] of actions) {
      let value = 0;
      if (snapshot && values) value = values[name] || 0;
      else if (snapshot) value = bindingValue(getBinding(name, action.binding), snapshot);
      if (action.enabled?.() !== false && snapshot) {
        if (action.continuous || (value > .5 && !(previous.get(name) > .5))) action.run(value, dt);
        for (const channel of action.consume || []) consumed.add(channel);
      }
      previous.set(name, value);
    }
    return consumed;
  }
  return {register, key, run, sample};
}
