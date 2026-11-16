// Screen areas the flight instruments occupy, so marks drawn over the picture (AI boxes, objective rings) step
// aside instead of printing over a read-out. Rectangles are read from the live layout, cached briefly, and given
// in the coordinates of the element they are asked for. Pure presentation: nothing here reaches the simulator.
const INSTRUMENTS = [
  '#flightDepth', '#flightMapBox', '#flightMission', '#flightTools', '#flightPeek.visible', '.hud.tl', '.hud.tc',
  '.hud.bc', '#flightOsd .osd-block', '#flightOsd .osd-heading', '#flightOsd .osd-lock',
];
const READOUTS = ['.hud.bc', '#flightOsd .osd-bl', '#flightOsd .osd-br', '#flightOsd .osd-lock'];
const CACHE_MS = 250;
const PAD = 6;
const caches = new Map();

function visibleRect(element) {
  if (!element.checkVisibility?.({opacityProperty: true, visibilityProperty: true})) return null;
  const rect = element.getBoundingClientRect();
  if (rect.width < 1 || rect.height < 1) return null;
  return rect;
}

function measure(selectors) {
  const rects = [];
  for (const element of document.querySelectorAll(selectors.join(','))) {
    const rect = visibleRect(element);
    if (rect) rects.push(rect);
  }
  return rects;
}

function cached(key, selectors, now) {
  const entry = caches.get(key);
  if (entry && now - entry.at < CACHE_MS) return entry.rects;
  const rects = measure(selectors);
  caches.set(key, {at: now, rects});
  return rects;
}

// Instrument rectangles relative to `origin` (a DOMRect of the canvas being drawn), padded a little.
export function instrumentRects(origin, now = performance.now()) {
  return cached('instruments', INSTRUMENTS, now).map(function relative(rect) {
    return {x: rect.left - origin.left - PAD, y: rect.top - origin.top - PAD,
      w: rect.width + 2 * PAD, h: rect.height + 2 * PAD};
  });
}

// Clip a 2D context to everything except the instruments; call ctx.restore() after drawing.
export function clipOutsideInstruments(ctx, origin, width, height, now) {
  ctx.save();
  ctx.beginPath();
  ctx.rect(0, 0, width, height);
  for (const rect of instrumentRects(origin, now)) ctx.rect(rect.x, rect.y, rect.w, rect.h);
  ctx.clip('evenodd');
}

// 0..1 opacity factor for a world mark whose screen centre is (x, y) in viewport pixels with an apparent radius r:
// marks that would sit on the bottom read-outs fade back so the numbers stay readable.
export function readoutFade(x, y, r = 0, now = performance.now()) {
  for (const rect of cached('readouts', READOUTS, now)) {
    const inside = x + r > rect.left && x - r < rect.right && y + r > rect.top - PAD && y - r < rect.bottom + PAD;
    if (inside) return 0.2;
  }
  return 1;
}
