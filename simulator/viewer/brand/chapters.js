// Chapter title card data: one row per campaign chapter id → the symbol it draws and its index, client and sub
// lines. Pure data and lookups (no DOM), so node tests can check that every chapter in simulator/campaign/ has a
// row. The big title itself comes from the chapter's own title in the campaign data; contracts and other jobs
// pass their own lines to the card (brand/chapter_card.js) and do not need a row here.
// Client names are fictional roles, never real organisations (AGENTS.md rule 8).

export const STRINGS = {
  // Shown under the card while it can be skipped.
  skip: '按任意鍵繼續',
  cardLabel: '章節標題',
  generic: {number: '任務', client: 'YX', sub: 'DIVE BRIEF'},
  cards: {
    prologue: {number: '序章 / 00', client: 'YX 海事服務 · 訓練', sub: 'CHECKOUT DIVE · TRAINING POOL'},
    harbor: {number: '第一章 / 01', client: '港務單位', sub: 'PILES · CRACK SURVEY'},
    hull: {number: '第一章 / 02', client: '船東', sub: 'HULL · IN-WATER SURVEY'},
    harbor_signoff: {number: '第一章 / 03', client: '港務單位 · 交班', sub: 'PILES · RE-INSPECTION'},
    offshore: {number: '第二章 / 04', client: '離岸平台業主', sub: 'JACKET · MEMBER INSPECTION'},
    reef: {number: '第三章 / 05', client: '海洋研究單位', sub: 'REEF · PHOTO TRANSECT'},
    wreck: {number: '第四章 / 06', client: '水下文化資產調查', sub: 'WRECK · SITE SURVEY'},
    finale: {number: '終章 / 07', client: '港務單位 · 夜間', sub: 'NIGHT RECOVERY'},
    incident_jacket: {number: '事故訓練 / E1', client: 'YX · 事故演練', sub: 'DRILL · TRAPPED IN JACKET'},
    incident_wreck: {number: '事故訓練 / E2', client: 'YX · 事故演練', sub: 'DRILL · TETHER SNAG'},
    incident_silt: {number: '事故訓練 / E3', client: 'YX · 事故演練', sub: 'DRILL · ZERO VISIBILITY'},
    incident_compass: {number: '事故訓練 / E4', client: 'YX · 事故演練', sub: 'DRILL · COMPASS DEVIATION'},
    incident_current: {number: '事故訓練 / E5', client: 'YX · 事故演練', sub: 'DRILL · CURRENT OVER LIMIT'},
    course_b01: {number: '初級課程 / B01', client: 'YX · 訓練中心', sub: 'COURSE · CONTROLS AND LAUNCH GATE'},
    course_b02: {number: '初級課程 / B02', client: 'YX · 訓練中心', sub: 'COURSE · TRACK AND DRIFT'},
    course_b03: {number: '初級課程 / B03', client: 'YX · 訓練中心', sub: 'COURSE · HARBOUR SURVEY'},
    course_b04: {number: '初級課程 / B04', client: 'YX · 訓練中心', sub: 'COURSE · FULL SORTIE'},
    course_i01: {number: '中級課程 / I01', client: 'YX · 訓練中心', sub: 'COURSE · HULL DATA QUALITY'},
    course_i02: {number: '中級課程 / I02', client: 'YX · 訓練中心', sub: 'COURSE · STATION KEEPING'},
    course_i03: {number: '中級課程 / I03', client: 'YX · 訓練中心', sub: 'COURSE · LOW VISIBILITY EXIT'},
    course_i04: {number: '中級課程 / I04', client: 'YX · 訓練中心', sub: 'COURSE · COMPASS FAILURE'},
    course_a01: {number: '進階課程 / A01', client: 'YX · 訓練中心', sub: 'COURSE · ABORT DECISION'},
    course_a02: {number: '進階課程 / A02', client: 'YX · 訓練中心', sub: 'COURSE · SNAG RECOVERY'},
    course_a03: {number: '進階課程 / A03', client: 'YX · 訓練中心', sub: 'COURSE · STRONG CURRENT EXIT'},
    course_a04: {number: '進階課程 / A04', client: 'YX · 訓練中心', sub: 'COURSE · FINAL ASSESSMENT'},
  },
};

// Chapter id → symbol name in brand/marks.js (CHAPTER_SYMBOL_IDS).
const SYMBOLS = {
  prologue: 'pool',
  harbor: 'harbor',
  hull: 'hull',
  harbor_signoff: 'harbor',
  offshore: 'offshore',
  reef: 'reef',
  wreck: 'wreck',
  finale: 'night',
};
const PREFIX_SYMBOLS = [['incident_', 'incident'], ['course_', 'course']];
// Chapter id → scenario key whose plate (brand/plates/<key>.jpg) fills the photo half. The server's campaign state
// does not carry the scenario, so the card keeps its own copy; tests compare it with simulator/campaign/*.json.
const SCENES = {
  prologue: 'tutorial_pool',
  harbor: 'harbor_inspection',
  hull: 'hull_inspection',
  harbor_signoff: 'harbor_inspection',
  offshore: 'jacket_inspection',
  reef: 'coral_reef',
  wreck: 'wreck_survey',
  finale: 'harbor_inspection',
  incident_jacket: 'incident_jacket',
  incident_wreck: 'incident_wreck',
  incident_silt: 'incident_silt',
  incident_compass: 'incident_compass',
  incident_current: 'incident_current',
  course_b01: 'tutorial_pool',
  course_b02: 'open_water',
  course_b03: 'harbor_inspection',
  course_b04: 'open_water',
  course_i01: 'hull_inspection',
  course_i02: 'monopile_current',
  course_i03: 'incident_silt',
  course_i04: 'incident_compass',
  course_a01: 'incident_jacket',
  course_a02: 'incident_wreck',
  course_a03: 'incident_current',
  course_a04: 'incident_current',
};
// Scenarios that share another site's plate (the drills run at the same structures).
const PLATE_ALIASES = {
  incident_jacket: 'jacket_inspection',
  incident_wreck: 'wreck_survey',
  incident_compass: 'harbor_inspection',
  incident_current: 'monopile_current',
};
const TITLE_SEPARATOR = '｜';

/** File stem of the plate in brand/plates/ for a scenario key. */
export function plateFor(scenario) {
  return Object.hasOwn(PLATE_ALIASES, scenario || '') ? PLATE_ALIASES[scenario] : scenario || '';
}

function symbolFor(chapterId) {
  if (Object.hasOwn(SYMBOLS, chapterId)) return SYMBOLS[chapterId];
  const match = PREFIX_SYMBOLS.find(function byPrefix([prefix]) {
    return chapterId.startsWith(prefix);
  });
  return match ? match[1] : 'generic';
}

function buildTable() {
  const table = {};
  for (const [id, lines] of Object.entries(STRINGS.cards)) {
    table[id] = Object.freeze({
      symbol: symbolFor(id),
      scenario: SCENES[id] || '',
      number: lines.number,
      client: lines.client,
      sub: lines.sub,
    });
  }
  return Object.freeze(table);
}

/** Chapter id → {symbol, scenario, number, client, sub}. */
export const CHAPTER_CARDS = buildTable();

/** True when a chapter id has its own row; other ids get the generic card. */
export function hasChapterCard(chapterId) {
  return Object.hasOwn(CHAPTER_CARDS, chapterId || '');
}

/** The big title of a card from a campaign title such as "第一章｜港灣" or "A01｜進階｜導管架中止決策". */
export function cardTitle(title) {
  const text = String(title || '');
  return text.split(TITLE_SEPARATOR).at(-1).trim();
}

/**
 * Everything the title card shows for a chapter. `chapter` is the campaign entry ({id, title, scenario}); an
 * unknown id gets the generic symbol and lines, with whatever the title's own prefix says as its index line.
 */
export function chapterCardData(chapter) {
  const id = chapter?.id || '';
  const title = String(chapter?.title || '');
  const row = hasChapterCard(id) ? CHAPTER_CARDS[id] : null;
  const prefix = title.includes(TITLE_SEPARATOR) ? title.split(TITLE_SEPARATOR)[0].trim() : '';
  return {
    id,
    symbol: row?.symbol || 'generic',
    number: row?.number || prefix || STRINGS.generic.number,
    client: row?.client || STRINGS.generic.client,
    sub: row?.sub || STRINGS.generic.sub,
    title: cardTitle(title) || id,
    scenario: chapter?.scenario || row?.scenario || '',
  };
}
