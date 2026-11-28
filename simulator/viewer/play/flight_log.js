// Record merged local telemetry at 5 Hz. Thin older samples together under a byte budget
// so even long dives retain their start, finish, vehicle pose and tether geometry.
import {saveDive} from '../replay_store.js';
import {extractEventsFromFrames} from '../debrief/events.js';
import {localize} from '../i18n/index.js';

const STRINGS = localize('play.flight_log', {title: '本次潛航', empty: '還沒有可回放的航段。'});
const BUDGET = 32 * 1024 * 1024;
export function createFlightLog({getWorld}) {
  let frames = [];
  let latest;
  let events = [];
  let completed;
  let signature = '';
  let last = -Infinity;
  let interval = .2;
  let bytes = 0;
  let world;
  function mark(kind, t, detail = '', fields = {}) {
    if (!Number.isFinite(t)) return;
    events.push({kind, t, detail, ...fields});
    if (events.length > 2048) events.shift();
  }
  let snagged = false;
  let collision = -Infinity;
  function update(state) {
    const current = getWorld();
    if (!state || !current) return;
    const scenario = current.scenario;
    const next = JSON.stringify([scenario?.key, scenario?.seed, state.model_id, state.campaign?.chapter]);
    if (next !== signature || state.t < latest?.t - .5) {
      archive().catch(() => {});
      completed = null;
      frames = [];
      events = [];
      signature = next;
      last = collision = -Infinity;
      world = structuredClone(current);
      interval = .2;
      bytes = 0;
      snagged = false;
    }
    latest = state;
    const names = state.tether?.snagged_on || [];
    if (names.length && !snagged) mark('tether_snag', state.t, names.join(', '));
    snagged = !!names.length;
    const contacts = (state.events || []).filter(contact => contact?.t > collision);
    for (const contact of contacts) {
      const {obstacle, severity} = contact;
      mark('collision', contact.t, [obstacle, severity].filter(Boolean).join(' · '), {obstacle, severity});
      collision = Math.max(collision, contact.t);
    }
    if (state.t - last < interval) return;
    last = state.t;
    const size = new Blob([JSON.stringify(state)]).size;
    frames.push({frame:state, size});
    bytes += size;
    if (bytes > BUDGET || frames.length > 3000) {
      frames = frames.filter((_, index) => index % 2 === 0 || index === frames.length - 1);
      bytes = frames.reduce((sum, item) => sum + item.size, 0);
      interval *= 2;
    }
  }
  function snapshot(title = STRINGS.title, training) {
    if (frames.length < 2 || !world) return null;
    const samples = frames.map(item => item.frame);
    if (latest.t > samples.at(-1).t) samples.push(latest);
    const markers = extractEventsFromFrames(samples).filter(event =>
      !events.some(saved => saved.kind === event.kind && saved.t === event.t));
    markers.push(...events);
    markers.sort((a,b) => a.t - b.t);
    const clip = {title, model_id:samples[0].model_id, world, frames:samples, script:[], debrief:{events:markers}};
    return {version:2, hz:1 / interval, clips:[clip], training};
  }
  async function persist(title, training) {
    const data = snapshot(title, training);
    if (!data) throw Error(STRINGS.empty);
    const pending = saveDive(data);
    completed = pending;
    try {
      return await pending;
    } catch (error) {
      if (completed === pending) completed = null;
      throw error;
    }
  }
  async function archive() {
    if (completed) return completed;
    if (frames.length >= 2) return persist();
  }
  return {update, snapshot, persist, archive, photo:t => mark('photo', t), get frames() { return frames.length; }};
}
