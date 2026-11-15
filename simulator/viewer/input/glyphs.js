// Text-only geometric SVG button caps, with no trademark artwork.
// Face labels follow the Standard Gamepad *position*: index 0 is the bottom face button.
// Switch-family pads print different letters on those positions (B/A/Y/X), so the labels swap.
const LABELS = {
  generic: ['1', '2', '3', '4'],
  xbox: ['A', 'B', 'X', 'Y'],
  playstation: ['×', '○', '□', '△'],
  switch: ['B', 'A', 'Y', 'X'],
};

export function deviceFamily(id = '') {
  if (/054c|dual|playstation|sony/i.test(id)) return 'playstation';
  if (/057e|switch|nintendo/i.test(id)) return 'switch';
  if (/045e|xbox|xinput|microsoft/i.test(id)) return 'xbox';
  return id ? 'generic' : 'keyboard';
}

export function faceLabels(family = 'generic') {
  return LABELS[family] || LABELS.generic;
}

export function glyph(index, family = 'generic', key = '') {
  const label = family === 'keyboard'
    ? key.replace(/[<>&"]/g, '')
    : faceLabels(family)[index] || String(index + 1);
  return (
    `<svg width="36" height="24" viewBox="0 0 36 24" role="img" aria-label="${label}">` +
    `<rect x="1" y="1" width="34" height="22" rx="7" fill="none" stroke="currentColor"/>` +
    `<text x="18" y="17" text-anchor="middle" fill="currentColor" font-size="13">${label}</text></svg>`
  );
}
