// Locale parity, interpolation safety, lazy nested reads, source precedence and subscriptions.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';
import { localize, registerTranslations, resolveLanguage, setLanguage, subscribe } from '../viewer/i18n/core.js';

function leaves(value, path = '') {
  if (!value || typeof value !== 'object') return { [path]: value };
  return Object.fromEntries(Object.entries(value).flatMap(function child([key, entry]) {
    return Object.entries(leaves(entry, `${path}.${key}`));
  }));
}

function parameters(text) {
  return String(text).match(/\{[^{}]+\}/g)?.sort() || [];
}

async function json(path) {
  return JSON.parse(await readFile(new URL(path, import.meta.url), 'utf8'));
}

test('fallback, nested arrays and retained references read the current language', function lazy() {
  const source = { label: '原文 {n}', nested: { list: ['第一', '第二'] } };
  const view = localize('test', source);
  const retained = view.nested.list;
  registerTranslations('en', 'test', { label: 'Source {n}', nested: { list: ['First'] } });
  setLanguage('en');
  assert.equal(view.label.replace('{n}', '2'), 'Source 2');
  assert.deepEqual([...retained], ['First', '第二']);
  assert.equal(Array.isArray(retained), true);
  assert.deepEqual(Object.keys(view), Object.keys(source));
  setLanguage('ja');
  assert.equal(view.label, source.label);
  assert.deepEqual([...retained], source.nested.list);
  setLanguage('zh-Hant');
});

test('language priority, aliases and unsupported sources', function priority() {
  assert.equal(resolveLanguage({ query: 'ja', stored: 'en', steam: 'schinese' }), 'ja');
  assert.equal(resolveLanguage({ query: 'xx', stored: 'en', steam: 'japanese' }), 'en');
  assert.equal(resolveLanguage({ steam: 'schinese', browser: ['en-US'] }), 'zh-Hans');
  assert.equal(resolveLanguage({ browser: ['xx', 'zh-TW'] }), 'zh-Hant');
  assert.equal(resolveLanguage({ browser: ['ja-JP'] }), 'ja');
  assert.equal(resolveLanguage(), 'zh-Hant');
});

test('subscribers can unsubscribe and identical language does not notify', function subscriptions() {
  let calls = 0;
  setLanguage('zh-Hant');
  const unsubscribe = subscribe(function changed() { calls += 1; });
  setLanguage('en');
  setLanguage('en');
  unsubscribe();
  setLanguage('zh-Hant');
  assert.equal(calls, 1);
});

test('all integrated dictionaries have identical keys and preserve every placeholder', async function parity() {
  const namespaces = await json('../viewer/i18n/namespaces.json');
  for (const namespace of namespaces) {
    const base = leaves(await json(`../viewer/i18n/locales/zh-Hant/${namespace}.json`));
    for (const language of ['en', 'ja', 'zh-Hans']) {
      const translated = leaves(await json(`../viewer/i18n/locales/${language}/${namespace}.json`));
      assert.deepEqual(Object.keys(translated).sort(), Object.keys(base).sort(), `${language}/${namespace}`);
      for (const key of Object.keys(base)) {
        assert.equal(typeof translated[key], typeof base[key]);
        assert.deepEqual(parameters(translated[key]), parameters(base[key]), `${language}/${namespace}:${key}`);
      }
    }
  }
});
