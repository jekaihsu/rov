// Shared canvas helpers for the line-style flight instruments: crisp sizing and the HUD palette.
export const INK = '#eaf4f7';
export const INK_DIM = 'rgba(234, 244, 247, .58)';
export const ACCENT = '#5fe0d0';
export const WARN = '#f2b84b';
export const DANGER = '#ff5a52';
export const FONT = 'Inter, "Noto Sans TC", system-ui, sans-serif';

// Matches the backing store to the element's CSS size and device pixel ratio, then returns a context that
// draws in CSS pixels. Returns null while the canvas is not laid out (hidden or display: none).
export function fitCanvas(canvas) {
  const width = canvas.clientWidth;
  const height = canvas.clientHeight;
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
