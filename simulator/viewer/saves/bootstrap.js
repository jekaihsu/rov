// Desktop: hydrate localStorage from userData/saves/ before other modules read preferences,
// and mirror every later rov.* write back to those files (Steam Auto-Cloud syncs the folder).
// Safe to import in the browser: the bridge is a no-op when rovDesktop.saves is absent.

const KEY_PATTERN = /^rov\.[A-Za-z0-9._-]+$/;
let installed = false;

function storage() {
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

export async function hydrateDesktopSaves() {
  const bridge = globalThis.window?.rovDesktop?.saves;
  const store = storage();
  if (!bridge?.readAll || !store) return { hydrated: 0 };
  let all = {};
  try {
    all = await bridge.readAll();
  } catch {
    return { hydrated: 0 };
  }
  let hydrated = 0;
  for (const [key, text] of Object.entries(all || {})) {
    if (!KEY_PATTERN.test(key) || typeof text !== 'string') continue;
    try {
      // Desktop files win over a stale browser profile copy on the same machine.
      store.setItem(key, text);
      hydrated += 1;
    } catch {
      // Quota: leave whatever is already in localStorage.
    }
  }
  return { hydrated };
}

export function installDesktopSaveMirror() {
  if (installed) return false;
  const bridge = globalThis.window?.rovDesktop?.saves;
  const store = storage();
  if (!bridge?.write || !store?.setItem) return false;
  const original = store.setItem.bind(store);
  store.setItem = function mirroredSetItem(key, value) {
    original(key, value);
    if (typeof key === 'string' && KEY_PATTERN.test(key) && !key.endsWith('.corrupt')) {
      try {
        bridge.write(key, String(value));
      } catch {
        // File mirror is best-effort.
      }
    }
  };
  installed = true;
  return true;
}

/** Call once from app.js: hydrate then wrap writes. */
export async function installSaves() {
  await hydrateDesktopSaves();
  installDesktopSaveMirror();
}
