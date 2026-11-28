// Spreads heavy presentation work across frames so a scene load or shader warm-up does not stall the main thread
// for more than a few milliseconds. Physics and controls are not queued here — only mesh builds, compiles and
// other draw-only jobs. Call update() once per animation frame; it runs jobs until the budget is spent.
//
//   const queue = createWorkQueue({budgetMs: 6});
//   queue.push(() => buildPart());
//   each frame: queue.update();

export function createWorkQueue({budgetMs = 6} = {}) {
  const jobs = [];
  let generation = 0;

  function push(job) {
    if (typeof job === 'function') jobs.push(job);
  }

  function clear() {
    jobs.length = 0;
    generation += 1;
  }

  // Returns true when the queue is empty after this turn. budgetMs 0 still runs exactly one job so a
  // caller can drain deliberately (one job per frame) without a busy spin on an empty clock slice.
  function update(now = performance.now()) {
    if (!jobs.length) return true;
    const limit = now + Math.max(0, budgetMs);
    do {
      const job = jobs.shift();
      try {
        job();
      } catch (error) {
        console.warn('[work_queue]', error);
      }
    } while (jobs.length && performance.now() < limit);
    return jobs.length === 0;
  }

  return {
    push,
    clear,
    update,
    get pending() {
      return jobs.length;
    },
    get generation() {
      return generation;
    },
  };
}
