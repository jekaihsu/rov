// Lazy translation views preserve the source shape, array operations and existing placeholder replacement.
const tables = new Map();
const sources = new Map();
const listeners = new Set();
let language = 'zh-Hant';

export function normalizeLanguage(value) {
  const tag = String(value || '').toLowerCase().replaceAll('_', '-');
  if (tag === 'tchinese' || /^zh-(?:hant|tw|hk|mo)(?:-|$)/.test(tag)) return 'zh-Hant';
  if (['schinese', 'zh'].includes(tag) || /^zh-(?:hans|cn|sg)(?:-|$)/.test(tag)) return 'zh-Hans';
  if (tag === 'japanese' || /^ja(?:-|$)/.test(tag)) return 'ja';
  if (tag === 'english' || /^en(?:-|$)/.test(tag)) return 'en';
  return null;
}

export function resolveLanguage({ query, stored, steam, browser = [] } = {}) {
  return [query, stored, steam, ...browser].map(normalizeLanguage).find(Boolean) || 'zh-Hant';
}

export function registerTranslations(locale, namespace, strings) {
  tables.set(`${locale}/${namespace}`, strings);
}

export function getLanguage() {
  return language;
}

export function setLanguage(value) {
  const next = normalizeLanguage(value) || 'zh-Hant';
  if (next === language) return;
  language = next;
  for (const listener of listeners) listener(language);
}

export function subscribe(listener) {
  listeners.add(listener);
  return function unsubscribe() {
    listeners.delete(listener);
  };
}

export function localize(namespace, source) {
  sources.set(namespace, source);
  function view(base, path) {
    const children = new Map();
    return new Proxy(base, {
      get(target, key, receiver) {
        const original = Reflect.get(target, key, receiver);
        if (!Object.hasOwn(target, key) || typeof key === 'symbol') return original;
        if (original && typeof original === 'object') {
          if (!children.has(key)) children.set(key, view(original, [...path, key]));
          return children.get(key);
        }
        if (typeof original !== 'string') return original;
        let translated = tables.get(`${language}/${namespace}`);
        for (const part of [...path, key]) translated = translated?.[part];
        return typeof translated === 'string' ? translated : original;
      },
    });
  }
  return view(source, []);
}

// Snapshot source strings and current translations for already-mounted static labels.
export function labelSnapshot() {
  const labels = new Map();
  function visit(base, translated, path) {
    for (const [key, value] of Object.entries(base)) {
      if (value && typeof value === 'object') visit(value, translated?.[key], `${path}.${key}`);
      else if (typeof value === 'string' && /[\u3400-\u9fff]/.test(value)) {
        labels.set(`${path}.${key}`, typeof translated?.[key] === 'string' ? translated[key] : value);
      }
    }
  }
  for (const [namespace, source] of sources) visit(source, tables.get(`${language}/${namespace}`), namespace);
  return labels;
}
