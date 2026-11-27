// CJK billboard titles must not wrap mid-word; career CSS overrides big-picture anywhere wrapping.
import test from 'node:test';
import assert from 'node:assert/strict';
import { readFile } from 'node:fs/promises';

const CJK_LANGS = ['ja', 'zh-Hant', 'zh-Hans'];

function declarationsFrom(css, blockMatcher) {
  const match = css.match(blockMatcher);
  assert.ok(match, 'expected CSS rule block');
  const decls = {};
  for (const part of match[1].split(';')) {
    const trimmed = part.trim();
    if (!trimmed) continue;
    const colon = trimmed.indexOf(':');
    if (colon < 0) continue;
    decls[trimmed.slice(0, colon).trim()] = trimmed.slice(colon + 1).trim();
  }
  return decls;
}

// keep-all prefers intact CJK phrases; break-word (not anywhere) is only the overflow fallback.
function prefersIntactCjk(decls) {
  return decls['word-break'] === 'keep-all' && decls['overflow-wrap'] !== 'anywhere';
}

test('career CSS CJK title rule prefers intact words with an overflow fallback', async () => {
  const css = await readFile(new URL('../viewer/career/career.css', import.meta.url), 'utf8');
  for (const lang of CJK_LANGS) {
    assert.match(css, new RegExp(`:lang\\(${lang}\\)`));
  }
  const decls = declarationsFrom(
    css,
    /:lang\(ja\)\s*\.bp-title[\s\S]*?\{([^}]+)\}/,
  );
  assert.equal(decls['word-break'], 'keep-all');
  assert.equal(decls['overflow-wrap'], 'break-word');
  assert.equal(decls['line-break'], 'strict');
  assert.equal(prefersIntactCjk(decls), true);
});

test('big-picture default still allows anywhere wrap for Latin titles', async () => {
  const css = await readFile(new URL('../viewer/menu/big_picture.css', import.meta.url), 'utf8');
  const decls = declarationsFrom(css, /\.bp-title\s*\{([^}]+)\}/);
  assert.equal(decls['overflow-wrap'], 'anywhere');
  assert.equal(prefersIntactCjk(decls), false);
});
