// Rolling recording of the current flight for the results screen's 講評回放: keeps the received states at a few
// hertz (the same frame format as the drawer's 任務紀錄 and the replay loader in app.js), restarts when the
// scenario changes or the simulation time runs backwards (reset, chapter start), and hands the run to the
// debrief replay through replay_store.js. Read-only: it never sends anything to the simulator.
import {createDiveRecord} from '../debrief/dive_record.js';
import {isInternalEdition} from '../training/edition.js';
import { saveReplay } from '../replay_store.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.flight_log', {
  title: '本次潛航',
  empty: '還沒有可回放的航段。',
});
const INTERVAL_S = 0.2;
const MAX_FRAMES = 3000;

export function createFlightLog({ getWorld }) {
  const internal = isInternalEdition();
  let evidence;
  let latest;
  let interval = INTERVAL_S;
  let frames = [];
  let world = null;
  let signature = '';
  let last = -Infinity;
  function restart(current) {
    frames = [];
    evidence = internal ? createDiveRecord(current) : null;
    interval = INTERVAL_S;
    world = structuredClone(current);
    last = -Infinity;
  }
  function update(state, measurements) {
    const current = getWorld();
    if (!state || !current || state === latest) return;
    const next = [current.scenario?.key, current.scenario?.seed, state.model_id,
      state.vehicle_id, state.campaign?.chapter].join('|');
    if (!latest || next !== signature || state.t < latest.t ||
        (state.campaign?.status === 'active' && latest.campaign?.status === 'completed')) {
      restart(current);
      signature = next;
    }
    latest = state;
    evidence?.observe(state, measurements);
    if (state.t - last < interval) return;
    last = state.t;
    frames.push(structuredClone(state));
    if (frames.length > MAX_FRAMES) {
      if (internal) {
        frames = frames.filter((_, index) => index % 2 === 0);
        interval *= 2;
      } else frames.shift();
    }
  }
  function snapshot(title = STRINGS.title) {
    if (!frames.length || !world) return null;
    const replay = [...frames];
    if (latest.t > last) replay.push(structuredClone(latest));
    if (replay.length < 2) return null;
    return {
      version: 2,
      hz: 1 / interval,
      clips: [{ title, model_id: frames[0].model_id, world, frames: replay, script: [],
        dive: evidence?.snapshot() }],
    };
  }
  // Save locally before navigating away from the completed dive.
  async function openDebrief(title, data = snapshot(title)) {
    if (!data) throw new Error(STRINGS.empty);
    const id = await saveReplay(data);
    const page = new URL(location.href);
    page.searchParams.set('replay', `local:${id}`);
    page.searchParams.set('nointro', '1');
    page.searchParams.set('diveReport', '1');
    location.assign(page);
    return true;
  }
  return {
    update,
    snapshot,
    openDebrief,
    get frames() {
      return frames.length;
    },
  };
}
