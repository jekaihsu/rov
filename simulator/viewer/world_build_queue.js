// Spreads Environment.finishHeavy (habitat, fish, surface props) across animation frames so a scenario
// switch does not stall the main thread for >0.2 s. Presentation only — physics and controls are untouched.
//
//   const queue = createWorldBuildQueue({budgetMs: 8});
//   queue.beginBuild();
//   queue.scheduleFinishHeavy(env, () => { seabed.visible = false; });
//   each frame: queue.update(now);

import { createWorkQueue } from './work_queue.js';

export function createWorldBuildQueue({budgetMs = 8} = {}) {
  const queue = createWorkQueue({budgetMs});
  let buildGen = 0;

  function beginBuild() {
    buildGen += 1;
    queue.clear();
    return buildGen;
  }

  function scheduleFinishHeavy(env, onDone = null) {
    if (!env) return;
    const gen = buildGen;
    queue.push(() => {
      if (gen !== buildGen) return;
      env.finishHeavy();
      if (typeof onDone === 'function') onDone();
    });
  }

  return {
    beginBuild,
    scheduleFinishHeavy,
    update: (now) => queue.update(now),
    clear: () => queue.clear(),
    get pending() {
      return queue.pending;
    },
    get generation() {
      return buildGen;
    },
  };
}
