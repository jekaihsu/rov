// Launch-menu data: dive sites, vehicles, story chapters, incident drills and training scenarios.
// Pure functions over the exported scene_previews.json and menu_catalogue.json (tools/build_menu_previews.py),
// so the menu can show everything before it opens any connection. No DOM and no three.js here.
import { localize } from '../i18n/index.js';

const STRINGS = localize('menu.catalogue', {
  activities: {
    photo: '生態攝影',
    inspect: '結構巡檢',
    station: '抗流懸停',
    tether: '纜線脫困',
    route: '航線檢查點',
    free: '自由探索',
    coop: '協作巡檢',
    expedition: '探索接案',
  },
  difficulty: ['入門', '進階', '困難'],
});

const KNOT = 0.514444;
// Engineering sites with an expedition contract set (qysim/expedition.py work areas).
const EXPEDITION_BIOMES = new Set(['reef', 'seagrass', 'harbor']);

export const MODES = ['expedition', 'free_explore', 'inspection_coop', 'scenario_training'];

export function maxCurrentKn(world) {
  const current = world?.current || {};
  return Math.max(current.surface_kn || 0, current.mid_kn || 0, current.bottom_kn || 0);
}

// Seabed depth range under the site from its terrain grid; flat sites report one value.
export function depthRange(world) {
  const rows = world?.terrain?.depths;
  const values = Array.isArray(rows) ? rows.flat().filter(Number.isFinite) : [];
  if (!values.length) return [world?.seabed_depth ?? 0, world?.seabed_depth ?? 0];
  return [Math.min(...values), Math.max(...values)];
}

export function visibility(world) {
  return world?.scenario?.visibility_m ?? null;
}

// Strong current and poor visibility are what make a site hard (docs/reference/real-rov-research.md,
// Fletcher & Roberts 1998). The tiers are a menu presentation choice, not a training standard.
export function difficulty(world) {
  const current = maxCurrentKn(world);
  const seeing = visibility(world) ?? 12;
  let points = 0;
  if (current >= 0.5) points += 1;
  if (current >= 1.0) points += 1;
  if (current >= 1.5) points += 1;
  if (seeing < 12) points += 1;
  if (seeing < 8) points += 1;
  if (seeing < 5) points += 1;
  const level = points <= 1 ? 1 : points <= 3 ? 2 : 3;
  return { level, label: STRINGS.difficulty[level - 1], current, visibility: seeing };
}

export function activities(scene) {
  const world = scene.world || {};
  const kinds = new Set((world.objectives || []).map(function kind(objective) {
    return objective.kind;
  }));
  const found = [];
  if (kinds.has('inspect')) found.push(STRINGS.activities.inspect);
  if (kinds.has('station_keep')) found.push(STRINGS.activities.station);
  if (kinds.has('checkpoint')) found.push(STRINGS.activities.route);
  if (kinds.has('untangle')) found.push(STRINGS.activities.tether);
  if (world.biome === 'reef' || world.biome === 'seagrass') found.push(STRINGS.activities.photo);
  if (EXPEDITION_BIOMES.has(world.biome)) found.push(STRINGS.activities.expedition);
  found.push(STRINGS.activities.coop, STRINGS.activities.free);
  return [...new Set(found)];
}

export function supportsMode(scene, mode) {
  if (mode !== 'expedition') return true;
  return EXPEDITION_BIOMES.has(scene.world?.biome);
}

// Scenes reserved for the campaign (incident drills, the directed prologue site, and the company
// training pool used by courses) are not free dive sites.
export function diveSites(scenes, chapters = []) {
  const reserved = new Set(['tutorial_pool']);
  for (const chapter of chapters) {
    if (chapter.category === 'incident') reserved.add(chapter.scenario);
  }
  const story = chapters.filter(function isStory(chapter) {
    return chapter.category === 'story';
  });
  if (story.length) reserved.add(story[0].scenario);
  return scenes.filter(function isSite(scene) {
    return !reserved.has(scene.key);
  });
}

export function siteFacts(scene) {
  const world = scene.world || {};
  const [shallow, deep] = depthRange(world);
  return {
    key: scene.key,
    name: scene.name,
    brief: scene.brief,
    shallow,
    deep,
    visibility: visibility(world),
    current: maxCurrentKn(world),
    tether: world.scenario?.tether_length ?? null,
    timeLimit: world.scenario?.time_limit_s ?? null,
    activities: activities(scene),
    difficulty: difficulty(world),
  };
}

// Training list: every catalogue scene with its derived difficulty, easiest first, then by name.
export function trainingScenarios(scenes) {
  return scenes
    .filter(function playable(scene) {
      return scene.key !== 'random';
    })
    .map(siteFacts)
    .sort(function byDifficulty(a, b) {
      return a.difficulty.level - b.difficulty.level || a.current - b.current;
    });
}

export function chaptersByCategory(chapters, category) {
  return chapters
    .filter(function inCategory(chapter) {
      return (chapter.category || 'story') === category;
    })
    .sort(function byOrder(a, b) {
      return (a.order ?? 0) - (b.order ?? 0);
    });
}

// locked: the chapter it requires is not completed in the local save; pending: placeholder chapter.
export function chapterStatus(chapter, completed = []) {
  if (chapter.placeholder) return 'pending';
  if (completed.includes(chapter.id)) return 'done';
  if (chapter.requires && !completed.includes(chapter.requires)) return 'locked';
  return 'open';
}

// Fixed bar scales so a bar means the same on every vehicle (menu presentation, not a rating).
const BAR_SCALE = { speed: 2.5, thrust: 1200, yaw: Math.PI, axes: 6 };

function share(value, scale) {
  return Math.max(0, Math.min(1, value / scale));
}

// Headline numbers and 0..1 capability bars on fixed scales.
export function vehicleSpecs(vehicle) {
  const surge = vehicle.vmax?.[0] ?? 0;
  const yaw = vehicle.wmax?.[2] ?? 0;
  const thrust = (vehicle.thruster_max ?? 0) * (vehicle.thrusters ?? 0);
  const axes = vehicle.capabilities?.length ?? 0;
  return {
    mass: vehicle.mass,
    thrusters: vehicle.thrusters,
    speedKn: surge / KNOT,
    arm: !!vehicle.arm,
    axes,
    bars: {
      speed: share(surge, BAR_SCALE.speed),
      thrust: share(thrust, BAR_SCALE.thrust),
      yaw: share(yaw, BAR_SCALE.yaw),
      axes: share(axes, BAR_SCALE.axes),
    },
    values: {
      speed: `${surge.toFixed(1)} m/s`,
      thrust: `${Math.round(thrust)} N`,
      yaw: `${Math.round(yaw * 180 / Math.PI)}°/s`,
      axes: `${axes}/6`,
    },
    provisional: (vehicle.provisional || []).length > 0,
  };
}
