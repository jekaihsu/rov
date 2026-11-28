// Pure mapping from career progress to the live main-menu backdrop (scene key + place line).
// Kept free of DOM / three.js so node tests can load it.

const CHAPTER_SCENES = {
  prologue: 'tutorial_pool',
  ch1: 'harbor_inspection',
  ch2: 'aquaculture_pen',
};

export function backdropChapter(career, next) {
  const order = ['prologue', 'ch1', 'ch2'];
  let reached = Math.max(0, order.indexOf(next?.chapter));
  for (const contract of career.data.contracts) {
    if (career.save.contracts[contract.id]?.completed) {
      reached = Math.max(reached, order.indexOf(contract.chapter));
    }
  }
  return order[reached];
}

/** Scene key for the live menu shot: matches the continue assignment, else the reached chapter. */
export function backdropScene(career, next) {
  if (next?.scenario) return next.scenario;
  return CHAPTER_SCENES[backdropChapter(career, next)] || 'harbor_inspection';
}

export function backdropLocation(locations, career, next) {
  const scene = backdropScene(career, next);
  const chapter = backdropChapter(career, next);
  return locations[scene] || locations[chapter] || locations.prologue || '';
}
