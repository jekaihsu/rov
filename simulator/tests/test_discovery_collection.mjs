// Multiple photographs of a find resolve to one field record without merging neighbouring finds.
import assert from 'node:assert/strict';
import {test} from 'node:test';
import {siteFinds} from '../viewer/collection_categories.js';

function photo(date, scene, seed, index) {
  return {
    createdAt: date,
    observation: {category: 'mussels', entity_id: 'detail-' + scene + '-' + index, scene, world_seed: seed, depth: 8}
  };
}

test('finds keep the first photograph of each site, seed and station in a restored archive', function () {
  const first = photo('2026-01-01', 'hull_inspection', 4, 0);
  const other = photo('2026-01-01', 'hull_inspection', 4, 5);
  const newLayout = photo('2026-01-01', 'hull_inspection', 3, 0);
  const newSite = photo('2026-01-01', 'cold_open_jacket', 4, 0);
  const repeat = photo('2026-02-02', 'hull_inspection', 4, 0);
  const unrelated = [{observation: {category: 'kelp'}}, {observation: {entity_id: 7}}, {observation: null}];
  const photos = [repeat, other, newLayout, first, newSite, ...unrelated];
  assert.deepEqual(siteFinds(photos), [first, other, newLayout, newSite]);
});
