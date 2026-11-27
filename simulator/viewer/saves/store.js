// Versioned JSON save helper for localStorage (and any getItem/setItem storage).
// Every record carries a numeric `version`. Older records run through migrate();
// corrupt, oversized or unrecoverable payloads fall back to defaults() and are
// copied to `<key>.corrupt` so a later build or support export can inspect them.
// Desktop Electron mirrors the same keys into userData/saves/ (see desktop/save_files.cjs).

export const CORRUPT_SUFFIX = '.corrupt';
export const DEFAULT_MAX_BYTES = 512 * 1024;

function byteLength(text) {
  if (typeof text !== 'string') return 0;
  if (typeof TextEncoder !== 'undefined') return new TextEncoder().encode(text).length;
  return Buffer.byteLength(text);
}

function isObject(value) {
  return !!value && typeof value === 'object' && !Array.isArray(value);
}

function resolveStorage(storage) {
  if (storage !== undefined) return storage;
  try {
    return globalThis.localStorage || null;
  } catch {
    return null;
  }
}

function backupCorrupt(storage, key, raw) {
  if (!storage || raw == null) return;
  try {
    storage.setItem(key + CORRUPT_SUFFIX, String(raw).slice(0, DEFAULT_MAX_BYTES));
  } catch {
    // Quota or private mode: the session still continues on defaults.
  }
  try {
    globalThis.window?.rovDesktop?.saves?.backup?.(key, String(raw));
  } catch {
    // Desktop bridge is optional in the browser.
  }
}

function mirrorWrite(key, text) {
  try {
    globalThis.window?.rovDesktop?.saves?.write?.(key, text);
  } catch {
    // File mirror failure must not break the in-page session.
  }
}

/**
 * @param {object} spec
 * @param {string} spec.key
 * @param {number} spec.version
 * @param {() => object} spec.defaults
 * @param {(record: object, fromVersion: number) => object} [spec.migrate]
 * @param {(record: object) => object|null} [spec.normalize]
 * @param {number} [spec.maxBytes]
 */
export function createRecordStore(spec) {
  const maxBytes = spec.maxBytes ?? DEFAULT_MAX_BYTES;
  const migrate = spec.migrate || function identity(record) {
    return record;
  };
  const normalize = spec.normalize || function pass(record) {
    return record;
  };

  function defaults() {
    const value = spec.defaults();
    if (!isObject(value)) throw new Error(`defaults for ${spec.key} must return an object`);
    return { ...value, version: spec.version };
  }

  function load(storage) {
    const store = resolveStorage(storage);
    let raw = null;
    try {
      raw = store?.getItem(spec.key);
    } catch {
      return { value: defaults(), recovered: true, reason: 'storage-read' };
    }
    if (raw == null || raw === '') {
      return { value: defaults(), recovered: false, reason: 'empty' };
    }
    if (byteLength(raw) > maxBytes) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'oversized' };
    }
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'corrupt-json' };
    }
    if (!isObject(parsed)) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'not-object' };
    }
    let fromVersion = Number(parsed.version);
    if (!Number.isFinite(fromVersion) || fromVersion < 0) fromVersion = 0;
    if (fromVersion > spec.version) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'newer-version' };
    }
    let migrated = parsed;
    try {
      if (fromVersion < spec.version) migrated = migrate({ ...parsed }, fromVersion);
    } catch {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'migrate-failed' };
    }
    if (!isObject(migrated)) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'migrate-shape' };
    }
    let normalized;
    try {
      normalized = normalize({ ...migrated, version: spec.version });
    } catch {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'normalize-failed' };
    }
    if (!isObject(normalized)) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'normalize-null' };
    }
    const value = { ...normalized, version: spec.version };
    if (fromVersion < spec.version || value.version !== parsed.version) {
      save(value, store);
    }
    return { value, recovered: false, reason: fromVersion < spec.version ? 'migrated' : 'ok' };
  }

  function save(record, storage) {
    const store = resolveStorage(storage);
    let normalized;
    try {
      normalized = normalize({ ...record, version: spec.version });
    } catch {
      return false;
    }
    if (!isObject(normalized)) return false;
    const payload = { ...normalized, version: spec.version };
    let text;
    try {
      text = JSON.stringify(payload);
    } catch {
      return false;
    }
    if (byteLength(text) > maxBytes) return false;
    try {
      store?.setItem(spec.key, text);
    } catch {
      return false;
    }
    mirrorWrite(spec.key, text);
    return true;
  }

  function reset(storage) {
    const value = defaults();
    save(value, storage);
    return value;
  }

  return {
    key: spec.key,
    version: spec.version,
    defaults,
    load,
    save,
    reset,
    maxBytes,
  };
}

/** Plain string preference with a documented schema version (value itself stays a string). */
export function createScalarStore(spec) {
  const maxBytes = spec.maxBytes ?? 4096;
  const allowed = spec.allowed || null;

  function defaults() {
    return spec.defaults();
  }

  function load(storage) {
    const store = resolveStorage(storage);
    let raw = null;
    try {
      raw = store?.getItem(spec.key);
    } catch {
      return { value: defaults(), recovered: true, reason: 'storage-read' };
    }
    if (raw == null || raw === '') {
      return { value: defaults(), recovered: false, reason: 'empty' };
    }
    if (byteLength(raw) > maxBytes) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'oversized' };
    }
    if (allowed && !allowed.includes(raw)) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'invalid' };
    }
    if (spec.validate && !spec.validate(raw)) {
      backupCorrupt(store, spec.key, raw);
      return { value: defaults(), recovered: true, reason: 'invalid' };
    }
    return { value: raw, recovered: false, reason: 'ok' };
  }

  function save(value, storage) {
    const store = resolveStorage(storage);
    const text = value == null ? defaults() : String(value);
    if (byteLength(text) > maxBytes) return false;
    if (allowed && !allowed.includes(text)) return false;
    if (spec.validate && !spec.validate(text)) return false;
    try {
      store?.setItem(spec.key, text);
    } catch {
      return false;
    }
    mirrorWrite(spec.key, text);
    return true;
  }

  return {
    key: spec.key,
    version: spec.version,
    kind: 'scalar',
    defaults,
    load,
    save,
    maxBytes,
  };
}

export function memoryStorage(seed = {}) {
  const map = new Map(Object.entries(seed));
  return {
    getItem(key) {
      return map.has(key) ? map.get(key) : null;
    },
    setItem(key, value) {
      map.set(String(key), String(value));
    },
    removeItem(key) {
      map.delete(key);
    },
    clear() {
      map.clear();
    },
    get size() {
      return map.size;
    },
    entries() {
      return map.entries();
    },
  };
}
