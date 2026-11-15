// 配色試作開關：網址加 ?palette=631 時，在 <html> 標上 data-palette，啟用 palette_631.css。
// 只影響選單、結算等介面的呈現色，不存檔、不影響飛行 HUD 的警示色。
const PALETTES = ['631'];

function requestedPalette(search) {
  const value = new URLSearchParams(search).get('palette');
  return PALETTES.includes(value) ? value : null;
}

function applyPalette() {
  const palette = requestedPalette(location.search);
  if (palette) document.documentElement.dataset.palette = palette;
}

applyPalette();
