// YX identity marks as SVG generators: the company mark, one symbol per fleet model and one per chapter.
// Every generator is a pure function that returns an SVG string, so the launch menu, the chapter title card, the
// licence certificate, the static loading block in index.html and the key-art sheet in docs/design/key-art/ all
// draw from this single source. Nothing here touches the DOM except svgNode(), which callers use to turn a
// string into an element. Geometry follows the approved trial (docs/design/key-art/marks.html): thin ink lines,
// three or four elements per symbol, and one small orange accent.

import { localize } from '../i18n/index.js';
export const STRINGS = localize('brand.marks', {
  markLabel: 'YX',
  fleetLabel: '機型符號',
  chapterLabel: '章節符號',
});

/** Identity colours. Ink and accent equal the 60/30/10 palette (palette_631.css); paper is the print stock. */
export const BRAND_COLOURS = Object.freeze({
  ink: '#06121c',
  paper: '#efebe2',
  ice: '#eef3f0',
  accent: '#ff7a2f',
});

// Symbols are drawn in a 120-unit box; the stroke is chosen from the size it will be shown at so a symbol stays
// legible at 32 px and does not turn heavy at 600 px.
const BOX = 120;
const DEFAULT_SIZE = 120;
const SVG_NS = 'http://www.w3.org/2000/svg';

function round(value) {
  return Math.round(value * 100) / 100;
}

/** Stroke widths in box units for a symbol displayed at `size` CSS pixels: {main, fine, dot}. */
export function strokeFor(size = DEFAULT_SIZE) {
  const shown = Math.max(16, Number(size) || DEFAULT_SIZE);
  const mainPx = 1.4 + shown / 150;
  const finePx = Math.max(1.1, mainPx * 0.55);
  const scale = BOX / shown;
  return {
    main: round(mainPx * scale),
    fine: round(finePx * scale),
    dot: round(Math.max(3.4, 1.9 * mainPx * scale)),
  };
}

function attributes(values) {
  return Object.entries(values).filter(function present(entry) {
    return entry[1] !== null && entry[1] !== undefined && entry[1] !== false;
  }).map(function pair([key, value]) {
    return `${key}="${String(value).replace(/&/g, '&amp;').replace(/"/g, '&quot;')}"`;
  }).join(' ');
}

function part(name, tag, values, weight) {
  return {name, tag, values, weight};
}

function path(name, d, weight = 'main') {
  return part(name, 'path', {d}, weight);
}

function ring(name, cx, cy, r, weight = 'fine') {
  return part(name, 'circle', {cx, cy, r}, weight);
}

function block(name, x, y, width, height, rx = 0) {
  return part(name, 'rect', {x, y, width, height, rx: rx || null}, 'solid');
}

function outline(name, x, y, width, height, rx = 0) {
  return part(name, 'rect', {x, y, width, height, rx: rx || null}, 'main');
}

// ── fleet ────────────────────────────────────────────────────────────────────────────────────────────────────
// R and O are plan views (body and thrusters). V and S are side views facing right: a float block on an open
// frame, a manipulator with an open jaw reaching forward, and the tether leaving the top.
const FLEET = {
  x1: {
    letter: 'R',
    accent: [60, 60],
    parts: [
      outline('body', 38, 34, 44, 52, 15),
      path('dome', 'M49 34a11 11 0 0 1 22 0', 'fine'),
      part('thrusters', 'g', {
        children: [ring('', 28, 39, 8.5), ring('', 92, 39, 8.5), ring('', 28, 81, 8.5), ring('', 92, 81, 8.5)],
      }, 'fine'),
    ],
  },
  bluerov2_heavy: {
    letter: 'O',
    accent: [60, 60],
    parts: [
      outline('body', 27, 38, 66, 44, 9),
      part('thrusters', 'g', {
        children: [ring('', 18, 41, 8.5), ring('', 102, 41, 8.5), ring('', 18, 79, 8.5), ring('', 102, 79, 8.5)],
      }, 'fine'),
      part('lifters', 'g', {
        children: [ring('', 45, 50, 4.6), ring('', 75, 50, 4.6), ring('', 45, 70, 4.6), ring('', 75, 70, 4.6)],
      }, 'fine'),
    ],
  },
  falcon: {
    letter: 'V',
    accent: [70, 65],
    parts: [
      block('float', 22, 38, 62, 15, 3),
      path('frame', 'M30 53V82M76 53V82M17 77L24 82H84L91 77'),
      path('arm', 'M76 72L93 62L103 72M112 65L103 72L112 79'),
      path('tether', 'M33 38C33 24 23 15 8 15', 'fine'),
    ],
  },
  model_s: {
    letter: 'S',
    accent: [52, 80],
    parts: [
      block('float', 14, 31, 76, 22, 3),
      path('frame', 'M21 53V92H83V53M21 92L52 53L83 92'),
      path('arms', 'M83 63L97 56L106 64M114 58L106 64L114 71M83 83H100M109 78L100 83L109 88'),
      part('lift', 'g', {children: [path('', 'M52 31V15'), ring('', 52, 10, 5)]}, 'fine'),
    ],
  },
};

/** Internal model ids that have their own symbol, in fleet order; `model_s` is the placeholder for Model S. */
export const FLEET_SYMBOL_IDS = Object.freeze(Object.keys(FLEET));

// ── chapters ─────────────────────────────────────────────────────────────────────────────────────────────────
const CHAPTERS = {
  // Training pool: the tank, the waterline, the descent line.
  pool: {
    accent: [60, 68],
    parts: [
      outline('tank', 18, 34, 84, 54),
      path('waterline', 'M18 46H102', 'fine'),
      path('descent', 'M60 20V68', 'fine'),
    ],
  },
  // Harbour: the waterline, three piles, the hull arc above them.
  harbor: {
    accent: [60, 74],
    parts: [
      path('waterline', 'M10 36H110', 'fine'),
      path('piles', 'M34 20V100M60 20V100M86 20V100'),
      path('hull', 'M10 36C32 68 88 68 110 36', 'fine'),
    ],
  },
  // Hull inspection: the waterline, the hull section, the survey pass underneath.
  hull: {
    accent: [60, 98],
    parts: [
      path('waterline', 'M6 32H114', 'fine'),
      path('hull', 'M16 32C16 92 104 92 104 32'),
      path('pass', 'M22 86C40 102 80 102 98 86', 'fine'),
    ],
  },
  // Offshore jacket: two battered legs, the horizontal frames, one cross brace.
  offshore: {
    accent: [60, 80],
    parts: [
      path('legs', 'M45 12L29 106M75 12L91 106'),
      path('frames', 'M41 36H79M36 66H84M31 96H89', 'fine'),
      path('brace', 'M41 36L84 66M79 36L36 66', 'fine'),
    ],
  },
  // Reef: the seabed swell, a branching coral, a second small one.
  reef: {
    accent: [84, 52],
    parts: [
      path('seabed', 'M8 94C26 76 40 98 58 84S88 70 112 90'),
      path('coral', 'M44 86V54M44 70L32 56M44 64L56 50', 'fine'),
      path('coral-small', 'M84 76V62M84 70L76 62M84 68L92 60', 'fine'),
    ],
  },
  // Wreck: the seabed, the listing hull, the fallen mast.
  wreck: {
    accent: [78, 58],
    parts: [
      path('seabed', 'M6 98H114', 'fine'),
      path('hull', 'M12 72L36 94H92L108 66'),
      path('mast', 'M56 94L68 38L88 48', 'fine'),
    ],
  },
  // Night recovery: the waterline, the lift line with its hook, the moon.
  night: {
    accent: [60, 88],
    parts: [
      path('waterline', 'M10 46H110', 'fine'),
      path('hook', 'M60 10V70a9 9 0 1 0 9 9'),
      ring('moon', 92, 24, 9),
    ],
  },
  // Net pen (aquaculture contracts): the float ring, the net, the hole.
  pen: {
    accent: [75, 77],
    accentRing: true,
    parts: [
      ring('float', 60, 60, 43, 'main'),
      ring('net-ring', 60, 60, 37),
      path('net', 'M34 35L86 88M46 27L94 76M26 48L74 96', 'fine'),
    ],
  },
  // Incident drill: a structure member and the tether wound round it.
  incident: {
    accent: [106, 88],
    parts: [
      path('member', 'M60 14V106'),
      path('tether', 'M10 38C44 38 80 42 80 54S40 62 40 72S78 82 106 88', 'fine'),
      path('surface', 'M10 22H110', 'fine'),
    ],
  },
  // Company course: a track through three gates.
  course: {
    accent: [106, 30],
    parts: [
      path('track', 'M12 92C38 92 36 44 60 44S84 78 106 30', 'fine'),
      path('gates', 'M27 68V92M49 34V58M83 52V76'),
      path('datum', 'M12 104H108', 'fine'),
    ],
  },
  // Any other job: the waterline and a depth axis with its marks.
  generic: {
    accent: [60, 72],
    parts: [
      path('waterline', 'M12 30H108', 'fine'),
      path('axis', 'M60 16V106'),
      path('marks', 'M52 52H68M52 72H68M52 92H68', 'fine'),
    ],
  },
};

/** Names of the chapter symbols; `generic` is what an unknown name draws. */
export const CHAPTER_SYMBOL_IDS = Object.freeze(Object.keys(CHAPTERS));

function drawPart(entry, widths, ink) {
  if (entry.tag === 'g') {
    const inner = entry.values.children.map(function child(item) {
      return drawPart({...item, name: ''}, widths, ink);
    }).join('');
    return `<g ${attributes({'data-part': entry.name})}>${inner}</g>`;
  }
  const name = entry.name ? {'data-part': entry.name} : {};
  if (entry.weight === 'solid') {
    return `<${entry.tag} ${attributes({...name, ...entry.values, fill: ink, stroke: 'none'})}/>`;
  }
  const width = entry.weight === 'main' ? widths.main : widths.fine;
  return `<${entry.tag} ${attributes({...name, ...entry.values, 'stroke-width': width})}/>`;
}

function roughFilter(id, seed) {
  return `<defs><filter ${attributes({id, x: '-10%', y: '-10%', width: '120%', height: '120%'})}>`
    + `<feTurbulence type="fractalNoise" baseFrequency="0.15" numOctaves="2" seed="${seed}"/>`
    + '<feDisplacementMap in="SourceGraphic" scale="0.55"/></filter></defs>';
}

function symbolSvg(kind, id, spec, options) {
  const {
    ink = 'currentColor',
    accent = BRAND_COLOURS.accent,
    paper = 'none',
    size = DEFAULT_SIZE,
    rough = false,
    label = '',
    sized = false,
  } = options;
  const widths = strokeFor(size);
  const filterId = `yx-rough-${kind}-${id}`;
  const body = spec.parts.map(function draw(entry) {
    return drawPart(entry, widths, ink);
  }).join('');
  const [cx, cy] = spec.accent;
  const dot = spec.accentRing
    ? `<circle ${attributes({
      'data-part': 'accent', class: 'yx-accent', cx, cy, r: widths.dot * 1.5, fill: paper, stroke: accent,
      'stroke-width': widths.fine * 1.4,
    })}/>`
    : `<circle ${attributes({'data-part': 'accent', class: 'yx-accent', cx, cy, r: widths.dot, fill: accent})}/>`;
  const root = attributes({
    xmlns: SVG_NS,
    viewBox: `0 0 ${BOX} ${BOX}`,
    class: `yx-symbol yx-symbol-${kind}`,
    'data-symbol': id,
    width: sized ? size : null,
    height: sized ? size : null,
    role: label ? 'img' : null,
    'aria-label': label || null,
    'aria-hidden': label ? null : 'true',
  });
  const group = attributes({
    fill: 'none',
    stroke: ink,
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    filter: rough ? `url(#${filterId})` : null,
  });
  return `<svg ${root}>${rough ? roughFilter(filterId, 7) : ''}<g ${group}>${body}</g>${dot}</svg>`;
}

/** Symbol id drawn for a model id: the model's own, or the Model S placeholder for anything else. */
export function fleetSymbolId(modelId) {
  return Object.hasOwn(FLEET, modelId || '') ? modelId : 'model_s';
}

/** Fleet letter (R, O, V, S) of the symbol a model id draws. */
export function fleetLetter(modelId) {
  return FLEET[fleetSymbolId(modelId)].letter;
}

/**
 * SVG string of a fleet model's symbol. `modelId` is the internal id (x1, bluerov2_heavy, falcon); `model_s`
 * and unknown ids draw the Model S placeholder. Options: ink, accent, paper, size (CSS px it is shown at, used
 * to pick the stroke), sized (emit width/height), rough (print-roughened edge), label (accessible name).
 */
export function fleetSymbol(modelId, options = {}) {
  const id = fleetSymbolId(modelId);
  // The markup carries the fleet letter, not the internal id.
  return symbolSvg('fleet', FLEET[id].letter, FLEET[id], options);
}

/** Chapter symbol name that will be drawn for `symbolId`; unknown names draw `generic`. */
export function chapterSymbolId(symbolId) {
  return Object.hasOwn(CHAPTERS, symbolId || '') ? symbolId : 'generic';
}

/** SVG string of a chapter symbol by name (see CHAPTER_SYMBOL_IDS). Options as fleetSymbol(). */
export function chapterSymbol(symbolId, options = {}) {
  const id = chapterSymbolId(symbolId);
  return symbolSvg('chapter', id, CHAPTERS[id], options);
}

/** Names of the drawn elements of a symbol, without the accent: three or four per symbol. */
export function symbolParts(kind, id) {
  const spec = kind === 'fleet' ? FLEET[fleetSymbolId(id)] : CHAPTERS[chapterSymbolId(id)];
  return spec.parts.map(function name(entry) {
    return entry.name;
  });
}

// ── company mark ─────────────────────────────────────────────────────────────────────────────────────────────
// Y's arms meet at a point and its stem runs on as the tether; X is the two thruster axes crossing at a hub.
export const MARK_PATHS = Object.freeze({
  yArms: 'M40 40L140 180L240 40',
  yStem: 'M140 180V340',
  tether: 'M140 180V340C140 430 300 400 380 450S560 470 610 420',
  xRise: 'M330 340L530 40',
  xFall: 'M330 40L530 340',
});
const MARK_VIEW = {tether: '0 0 660 500', compact: '16 16 538 348'};
const MARK_STROKE = {tether: 16, compact: 20};

/**
 * SVG string of the YX mark.
 * variant 'tether': the full mark, Y's stem continuing as a tether arc. With `misregister` (default) both X
 *   strokes are ink over an offset accent print; without it one X stroke takes the accent.
 * variant 'compact': Y and X only, for small sizes; the accent is on one X stroke only.
 * Other options: ink, accent, paper (fill of the hub), size and sized (emit width/height), label.
 */
export function yxMark(options = {}) {
  const {
    variant = 'tether',
    ink = 'currentColor',
    accent = BRAND_COLOURS.accent,
    paper = 'none',
    misregister = variant === 'tether',
    size = null,
    sized = false,
    label = STRINGS.markLabel,
  } = options;
  const kind = variant === 'compact' ? 'compact' : 'tether';
  const stroke = MARK_STROKE[kind];
  const [, , boxWidth, boxHeight] = MARK_VIEW[kind].split(' ').map(Number);
  const root = attributes({
    xmlns: SVG_NS,
    viewBox: MARK_VIEW[kind],
    class: `yx-mark yx-mark-${kind}`,
    width: sized && size ? round(size * boxWidth / boxHeight) : null,
    height: sized && size ? size : null,
    role: 'img',
    'aria-label': label,
  });
  const group = attributes({
    fill: 'none', stroke: ink, 'stroke-width': stroke, 'stroke-linecap': 'round', 'stroke-linejoin': 'round',
  });
  const accentStroke = attributes({'data-part': 'x-rise', class: 'yx-accent', d: MARK_PATHS.xRise, stroke: accent});
  const inkRise = `<path ${attributes({'data-part': 'x-rise', d: MARK_PATHS.xRise})}/>`;
  const fall = `<path ${attributes({'data-part': 'x-fall', d: MARK_PATHS.xFall})}/>`;
  const arms = `<path ${attributes({'data-part': 'y-arms', d: MARK_PATHS.yArms})}/>`;
  if (kind === 'compact') {
    const stem = `<path ${attributes({'data-part': 'y-stem', d: MARK_PATHS.yStem})}/>`;
    return `<svg ${root}><g ${group}>${arms}${stem}${fall}<path ${accentStroke}/></g></svg>`;
  }
  const tether = `<path ${attributes({'data-part': 'tether', d: MARK_PATHS.tether, 'stroke-width': 6})}/>`;
  const shadow = misregister
    ? `<path ${attributes({
      'data-part': 'misregister', class: 'yx-accent', d: `${MARK_PATHS.xFall}${MARK_PATHS.xRise}`,
      stroke: accent, transform: 'translate(8 -5)',
    })}/>`
    : '';
  const rise = misregister ? inkRise : `<path ${accentStroke}/>`;
  const hub = `<circle ${attributes({
    'data-part': 'hub', cx: 430, cy: 190, r: 15, fill: paper, stroke: ink, 'stroke-width': 5,
  })}/>`;
  const end = `<circle ${attributes({'data-part': 'tether-end', cx: 610, cy: 420, r: 9, fill: ink, stroke: 'none'})}/>`;
  return `<svg ${root}><g ${group}>${shadow}${arms}${tether}${fall}${rise}</g>${hub}${end}</svg>`;
}

/** The mark inlined in index.html's static loading block; tests keep the two identical. */
export function loadingMark() {
  return yxMark({variant: 'compact', ink: 'currentColor', accent: BRAND_COLOURS.accent});
}

/** Turn an SVG string from this module into an element of `doc` (the page's document by default). */
export function svgNode(markup, doc = globalThis.document) {
  const holder = doc.createElement('span');
  holder.innerHTML = markup;
  return holder.firstElementChild;
}
