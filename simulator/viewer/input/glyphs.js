// Text-only geometric SVG button caps, with no trademark artwork.
// Face labels follow the Standard Gamepad *position*: index 0 is the bottom face button.
// Switch-family pads print different letters on those positions (B/A/Y/X), so the labels swap.
const LABELS = {
  generic: ['1', '2', '3', '4'],
  xbox: ['A', 'B', 'X', 'Y'],
  playstation: ['×', '○', '□', '△'],
  switch: ['B', 'A', 'Y', 'X'],
};

// Vendor 054c, or the product name these pads report over Bluetooth ("Wireless Controller"). A bare "dual" is not
// enough: the Logitech D-mode pad reports "Dual Action" and is a generic pad.
export function deviceFamily(id = '') {
  if (/054c|playstation|sony|^wireless controller\b/i.test(id)) return 'playstation';
  if (/057e|switch|nintendo/i.test(id)) return 'switch';
  if (/045e|xbox|xinput|microsoft/i.test(id)) return 'xbox';
  return id ? 'generic' : 'keyboard';
}

// Captions printed on the other standard buttons (4..15, 17) per family. Families without an entry, the Home
// button (16) and anything unnamed keep the caller's generic captions.
const STRINGS = {
  buttons: {
    playstation: ['L1', 'R1', 'L2', 'R2', 'Share／Create', 'Options', 'L3', 'R3'],
    switch: ['L', 'R', 'ZL', 'ZR', '−', '+', 'L3', 'R3'],
  },
  touchpad: '觸控板',
};

// Captions for standard button indices 0..17 of a family (sparse), or null when the generic captions apply.
export function padNames(family = 'generic') {
  const others = STRINGS.buttons[family];
  if (!others) return null;
  const names = [...faceLabels(family), ...others];
  if (family === 'playstation') names[17] = STRINGS.touchpad;
  return names;
}

export function faceLabels(family = 'generic') {
  return LABELS[family] || LABELS.generic;
}

export function glyph(index, family = 'generic', key = '') {
  const label = family === 'keyboard'
    ? key.replace(/[<>&"]/g, '')
    : faceLabels(family)[index] || String(index + 1);
  // Long key names (Space, Enter) widen the cap so the caption never spills onto the text beside it.
  const width = Math.max(36, Math.round(String(label).length * 8 + 16));
  return (
    `<svg width="${width}" height="24" viewBox="0 0 ${width} 24" role="img" aria-label="${label}">` +
    `<rect x="1" y="1" width="${width - 2}" height="22" rx="7" fill="none" stroke="currentColor"/>` +
    `<text x="${width / 2}" y="17" text-anchor="middle" fill="currentColor" font-size="13">${label}</text></svg>`
  );
}
