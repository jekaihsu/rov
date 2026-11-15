// The YX mark inlined in index.html's static loading block (it cannot import a module before the page loads)
// is byte-for-byte the output of the generator in viewer/brand/marks.js, and the brand stylesheet is linked.
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import {test} from 'node:test';
import {loadingMark} from '../viewer/brand/marks.js';

const VIEWER = new URL('../viewer/', import.meta.url);

test('the loading mark inlined in index.html is the generator output', async function () {
  const html = await readFile(new URL('index.html', VIEWER), 'utf8');
  const match = html.match(/<span class="brand-loading-mark" id="brandLoadingMark">(.*?)<\/span>/s);
  assert.ok(match, 'index.html has the brand loading mark');
  assert.equal(match[1], loadingMark());
  assert.ok(html.includes('<link rel="stylesheet" href="brand/brand.css">'));
});
