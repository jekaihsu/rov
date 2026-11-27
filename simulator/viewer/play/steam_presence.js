// Rich Presence helpers: map the current chapter / work order onto Steam presence tokens.
// Display strings are localized (four languages). Pure functions stay free of DOM for node --test.

import { localize } from '../i18n/index.js';

const STRINGS = localize('play.steam_presence', {
  menu: '主選單',
  diving: '下潛中',
  chapterFallback: '作業中',
  levelFallback: '自由航行',
  chapters: {
    prologue: '序章 · 見習之前',
    ch1: '第一章 · 港口與船舶',
    ch2: '第二章 · 養殖場',
  },
  levels: {
    p0_induction: '水池操作課',
    p1_pool_checkout: '水池檢查潛',
    p2_open_water: '開放水域熟悉',
    c1_pier_level1: '碼頭 Level I 巡檢',
    c1_pier_level2: '碼頭海生物量測',
    c1_hull_fouling: '船殼附著評級',
    c1_dropped_object: '港內掉落物',
    c1_quay_cp: '碼頭陰極巡測',
    c1_hull_ut: '船殼測厚',
    c1_signoff_exam: '交班前複查',
    free_explore: '自由探索',
    expedition: '探索接案',
    inspection_coop: '協作巡檢',
    scenario_training: '場景訓練',
  },
});

export function chapterLabel(chapterId) {
  return STRINGS.chapters[chapterId] || STRINGS.chapterFallback;
}

export function levelLabel(levelId) {
  return STRINGS.levels[levelId] || STRINGS.levelFallback;
}

// Build presence tokens from career / mission state. Missing fields fall back to menu copy.
export function presenceFromState(state, { careerContract = null, language = 'zh-Hant' } = {}) {
  const campaignChapter = state?.campaign?.chapter || careerContract?.chapter || null;
  const mission = state?.mission?.mode || null;
  let levelId = careerContract?.id || null;
  if (!levelId && mission && mission !== 'campaign') levelId = mission;
  if (!levelId && state?.campaign?.status === 'active') levelId = state.campaign.chapter;
  const chapter = campaignChapter ? chapterLabel(campaignChapter) : (levelId ? STRINGS.chapterFallback : STRINGS.menu);
  const level = levelId ? levelLabel(levelId) : (state?.locked === false ? STRINGS.diving : STRINGS.menu);
  return {
    chapterId: campaignChapter,
    levelId,
    language,
    chapter,
    level,
  };
}

export function installSteamPresence({ getState, getCareerContract = () => null } = {}) {
  const desktop = globalThis.window?.rovDesktop;
  let lastKey = '';
  function publish(force = false) {
    if (desktop?.edition !== 'steam' || typeof desktop?.steamPresence !== 'function') return null;
    const tokens = presenceFromState(getState?.() || null, {
      careerContract: getCareerContract?.() || null,
      language: document.documentElement?.lang || 'zh-Hant',
    });
    const key = `${tokens.language}|${tokens.chapter}|${tokens.level}`;
    if (!force && key === lastKey) return tokens;
    lastKey = key;
    desktop.steamPresence({
      chapter: tokens.chapter,
      level: tokens.level,
      language: tokens.language,
    }).catch(function presenceUnavailable(error) {
      console.warn('Steam presence not updated:', error?.message || error);
    });
    return tokens;
  }
  return { update: publish, presenceFromState };
}
