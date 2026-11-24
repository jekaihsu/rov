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

// Behaviour of the title wrap cascade: keep-all + normal wrap means CJK words stay intact.
function allowsMidWordBreak(decls) {
  if (decls['word-break'] === 'keep-all') return false;
  if (decls['overflow-wrap'] === 'anywhere') return true;
  return decls['overflow-wrap'] !== 'normal';
}

test('career CSS CJK title rule disables mid-word wrapping', async () => {
  const css = await readFile(new URL('../viewer/career/career.css', import.meta.url), 'utf8');
  for (const lang of CJK_LANGS) {
    assert.match(css, new RegExp(`:lang\\(${lang}\\)`));
  }
  const decls = declarationsFrom(
    css,
    /:lang\(ja\)\s*\.bp-title[\s\S]*?\{([^}]+)\}/,
  );
  assert.equal(decls['word-break'], 'keep-all');
  assert.equal(decls['overflow-wrap'], 'normal');
  assert.equal(decls['line-break'], 'strict');
  assert.equal(allowsMidWordBreak(decls), false);
});

test('big-picture default still allows anywhere wrap for Latin titles', async () => {
  const css = await readFile(new URL('../viewer/menu/big_picture.css', import.meta.url), 'utf8');
  const decls = declarationsFrom(css, /\.bp-title\s*\{([^}]+)\}/);
  assert.equal(decls['overflow-wrap'], 'anywhere');
  assert.equal(allowsMidWordBreak(decls), true);
});
