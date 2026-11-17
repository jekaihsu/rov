// Cached reads of the page's CSS custom properties (colours, fonts) for code that paints with them every frame or
// every UI tick. getPropertyValue on a live computed style recalculates styles first when the DOM changed since the
// last read, which the HUD does every frame. The cache is dropped when the display preferences change
// (colour-blind palette, UI scale, language: prefs/display.js 'rov-display-change'), the only time the values move.
const cache = new Map();
let computed = null;

function clear() {
  cache.clear();
  computed = null;
}

if (typeof document !== 'undefined') document.addEventListener('rov-display-change', clear);

// Trimmed value of a custom property on the root element, e.g. cssVariable('--warn').
export function cssVariable(name) {
  if (cache.has(name)) return cache.get(name);
  computed ||= getComputedStyle(document.documentElement);
  const value = computed.getPropertyValue(name).trim();
  cache.set(name, value);
  return value;
}
