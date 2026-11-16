// Rolling recording of the current flight for the results screen's 講評回放: keeps the received states at a few
// hertz (the same frame format as the drawer's 任務紀錄 and the replay loader in app.js), restarts when the
// scenario changes or the simulation time runs backwards (reset, chapter start), and hands the run to the
// debrief replay through replay_store.js. Read-only: it never sends anything to the simulator.
import { saveReplay } from '../replay_store.js';

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.flight_log', {
  title: '本次潛航',
  empty: '還沒有可回放的航段。',
});
const INTERVAL_S = 0.2;
const MAX_FRAMES = 3000;

export function createFlightLog({ getWorld }) {
  let frames = [];
  let world = null;
  let signature = '';
  let last = -Infinity;
  function restart(state, current) {
    frames = [];
    world = current ? structuredClone(current) : null;
    signature = `${current?.scenario?.key}:${current?.scenario?.seed}:${state.model_id}`;
    last = -Infinity;
  }
  function update(state) {
    const current = getWorld();
    if (!state || !current) return;
    const next = `${current.scenario?.key}:${current.scenario?.seed}:${state.model_id}`;
    if (next !== signature || state.t < last - 0.5) restart(state, current);
    if (state.t - last < INTERVAL_S) return;
    last = state.t;
    frames.push(structuredClone(state));
    if (frames.length > MAX_FRAMES) frames.splice(0, frames.length - MAX_FRAMES);
  }
  function snapshot(title = STRINGS.title) {
    if (frames.length < 2 || !world) return null;
    return {
      version: 2,
      hz: Math.round(1 / INTERVAL_S),
      clips: [{ title, model_id: frames[0].model_id, world, frames: [...frames], script: [] }],
    };
  }
  // Saves the run and opens it in the debrief replay page; resolves false when nothing was recorded.
  async function openDebrief(title) {
    const data = snapshot(title);
    if (!data) throw new Error(STRINGS.empty);
    const id = await saveReplay(data);
    const page = new URL(location.href);
    page.searchParams.set('replay', `local:${id}`);
    page.searchParams.set('nointro', '1');
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
