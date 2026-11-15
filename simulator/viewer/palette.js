// 配色開關：預設是 palette_631.css 的 60/30/10 配色（強調色為安全橘）。
// ?palette=classic 回到舊的青色配色；?accent=violet|pink|lime|orange 可比較其他強調色。
// 只影響選單、結算等介面的呈現色，不存檔、不影響飛行 HUD 的警示色。
const PALETTES = ['classic'];
// ink：強調色按鈕上的文字用深色（dark）或白色（light）。
const ACCENTS = {
  orange: {color: '#ff7a2f', ink: 'dark'},
  violet: {color: '#8b5cf6', ink: 'light'},
  pink: {color: '#ff4f8b', ink: 'light'},
  lime: {color: '#c8f53c', ink: 'dark'},
};

function requestedPalette(search) {
  const value = new URLSearchParams(search).get('palette');
  return PALETTES.includes(value) ? value : null;
}

function requestedAccent(search) {
  return ACCENTS[new URLSearchParams(search).get('accent')] || null;
}

function applyPalette() {
  const root = document.documentElement;
  const palette = requestedPalette(location.search);
  if (palette) {
    root.dataset.palette = palette;
    return;
  }
  const accent = requestedAccent(location.search);
  if (!accent) return;
  root.style.setProperty('--color-accent', accent.color);
  root.dataset.accentInk = accent.ink;
}

applyPalette();
