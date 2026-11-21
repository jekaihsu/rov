// CJK billboard titles must not wrap mid-word; career CSS overrides big-picture anywhere wrapping.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

test('career CSS keeps CJK titles from breaking inside words', async () => {
  const css = await readFile(new URL('../viewer/career/career.css', import.meta.url), 'utf8');
  assert.match(css, /:lang\(ja\)\s*\.bp-title/);
  assert.match(css, /:lang\(zh-Hant\)\s*\.bp-title/);
  assert.match(css, /:lang\(zh-Hans\)\s*\.bp-title/);
  assert.match(css, /word-break:\s*keep-all/);
  assert.match(css, /overflow-wrap:\s*normal/);
});
