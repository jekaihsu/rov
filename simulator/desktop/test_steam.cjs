// Exercise offline fallback, event allowlists and stat validation without Steam.
const assert = require('node:assert/strict');
const {createSteam} = require('./steam_bridge.cjs');
const manifest = require('./steam/achievements.json');
const offline = createSteam('/tmp/cloud', () => { throw Error('offline fixture'); });
assert.equal(offline.status().available, false);
assert.equal(offline.event('first_dive'), false);
assert.throws(() => offline.event('../unknown'));
assert.throws(() => offline.stat('dives_completed', -1));
const calls = [];
const online = createSteam('/tmp/cloud', () => ({init: () => ({
  achievement: {activate: id => { calls.push(id); return true; }},
  stats: {store: () => true, setInt: () => true}
})}));
for (const item of manifest) assert.equal(online.event(item.event), true);
assert.equal(new Set(calls).size, 15);
assert.equal(online.stat('dives_completed', 3), true);
console.log('Steam adapter: offline, 15 achievements and stat validation passed');
