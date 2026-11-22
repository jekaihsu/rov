// Localized field guide categories and the first photograph of each site-specific find.
import {localize} from './i18n/core.js';

const STRINGS = localize('collection_categories', {
  "names": {
    "coral": "珊瑚",
    "seastar": "海星",
    "seagrass": "海草",
    "kelp": "海藻",
    "fish_school": "魚群",
    "mussels": "成簇貽貝",
    "barnacles": "藤壺群",
    "limpet": "笠螺",
    "anemones": "海葵群",
    "brittle_star": "蛇尾",
    "shell_hash": "碎貝殼層",
    "crab_molt": "蟹的蛻殼",
    "rope_offcut": "斷繩",
    "shackle": "卸扣",
    "bottle_glass": "玻璃瓶碎片",
    "ceramic_shard": "陶片",
    "net_patch": "網片",
    "rust_flake": "剝落的鏽片"
  },
  "finds": "海域發現紀錄",
  "moreFinds": "更多海域發現",
  "station": "{site} · 樣點 {point} · {depth} m"
});

export const COLLECTION_CATEGORIES = STRINGS.names;

export function siteFinds(photos) {
  const finds = new Map();
  for (const photo of photos) {
    const obs = photo.observation;
    if (typeof obs?.entity_id !== 'string' || !/^detail-[a-z0-9_]+-[0-9]+$/.test(obs.entity_id)) continue;
    if (typeof obs.scene !== 'string' || !Number.isFinite(obs.depth) || !Number.isInteger(obs.world_seed)) continue;
    const key = JSON.stringify([obs.scene, obs.world_seed, obs.entity_id]);
    const previous = finds.get(key);
    if (!previous || photo.createdAt < previous.createdAt) finds.set(key, photo);
  }
  return [...finds.values()];
}

export function findCaption(observation, site) {
  const number = Number(observation.entity_id.split('-').at(-1)) + 1;
  const location = observation.world_seed ? `${site} #${observation.world_seed}` : site;
  return STRINGS.station.replace('{site}', location).replace('{point}', String(number))
    .replace('{depth}', observation.depth.toFixed(1));
}

export const guideText = STRINGS;
