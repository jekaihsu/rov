// Shared canvas helpers for the line-style flight instruments: crisp sizing and the HUD palette, and element sizes
// that never force a synchronous layout.
export const INK = '#eaf4f7';
export const INK_DIM = 'rgba(234, 244, 247, .58)';
export const ACCENT = '#5fe0d0';
export const WARN = '#f2b84b';
export const DANGER = '#ff5a52';
export const FONT = 'Inter, "Noto Sans TC", system-ui, sans-serif';

// CSS size of each instrument canvas, kept by a ResizeObserver. Reading clientWidth every frame after the HUD has
// written text forced a synchronous layout per instrument per frame; the observer reads the size once layout is
// done anyway, so a frame never waits for layout here.
const sizes = new WeakMap();
const observer = typeof ResizeObserver === 'function' ? new ResizeObserver(function resized(entries) {
  for (const entry of entries) {
    sizes.set(entry.target, {width: entry.target.clientWidth, height: entry.target.clientHeight});
  }
}) : null;

// {width, height} of an element as clientWidth / clientHeight report them, without forcing a layout after the first
// call. Also used for the stick and wheel indicators of the engineering panel.
export function elementSize(element) {
  let size = sizes.get(element);
  if (size && observer) return size;
  size = {width: element.clientWidth, height: element.clientHeight};
  if (observer) {
    sizes.set(element, size);
    observer.observe(element);
  }
  return size;
}

// Matches the backing store to the element's CSS size and device pixel ratio, then returns a context that
// draws in CSS pixels. Returns null while the canvas is not laid out (hidden or display: none).
export function fitCanvas(canvas) {
  const {width, height} = elementSize(canvas);
  if (!width || !height) return null;
  const ratio = Math.min(globalThis.devicePixelRatio || 1, 3);
  const pixelWidth = Math.round(width * ratio);
  const pixelHeight = Math.round(height * ratio);
  if (canvas.width !== pixelWidth) canvas.width = pixelWidth;
  if (canvas.height !== pixelHeight) canvas.height = pixelHeight;
  const ctx = canvas.getContext('2d');
  ctx.setTransform(ratio, 0, 0, ratio, 0, 0);
  ctx.clearRect(0, 0, width, height);
  return {ctx, width, height};
}

// A tight dark halo keeps thin lines and labels legible over a bright silt white-out or a lit structure without
// a filled panel; on dark water it barely shows.
export function halo(ctx) {
  ctx.shadowColor = 'rgba(0, 0, 0, .8)';
  ctx.shadowBlur = 2;
  ctx.shadowOffsetY = 0.5;
}

export function font(size, weight = 400) {
  return `${weight} ${size}px ${FONT}`;
}
