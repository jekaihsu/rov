// Persist a playtest report locally: desktop writes userData/reports/<stamp>/; browser downloads a ZIP.
import { zipStore } from './zip.js';

function stampName(date = new Date()) {
  return date.toISOString().replace(/[:.]/g, '-').replace(/Z$/, 'Z');
}

async function blobToBytes(blob) {
  const buffer = await blob.arrayBuffer();
  return new Uint8Array(buffer);
}

function bytesToBase64(bytes) {
  const chunk = 0x8000;
  let binary = '';
  for (let i = 0; i < bytes.length; i += chunk) {
    binary += String.fromCharCode(...bytes.subarray(i, i + chunk));
  }
  return btoa(binary);
}

function downloadBlob(name, blob) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = name;
  link.click();
  setTimeout(function revoke() {
    URL.revokeObjectURL(url);
  }, 5000);
}

export function canOpenReportsFolder() {
  return typeof globalThis.window?.rovDesktop?.openReportsFolder === 'function';
}

export async function openReportsFolder() {
  const desktop = globalThis.window?.rovDesktop;
  if (!desktop?.openReportsFolder) throw Error('僅桌面版可開啟回報資料夾');
  const result = await desktop.openReportsFolder();
  if (!result?.ok) throw Error(result?.error || '無法開啟回報資料夾');
  return result.path || null;
}

// screenshotBlob: image/png Blob; report: plain object. Returns { mode, path?, filename? }.
export async function saveFeedbackReport({ screenshotBlob, report }) {
  const stamp = stampName();
  const jsonText = `${JSON.stringify(report, null, 2)}\n`;
  const jsonBytes = new TextEncoder().encode(jsonText);
  const pngBytes = screenshotBlob ? await blobToBytes(screenshotBlob) : new Uint8Array();
  const desktop = globalThis.window?.rovDesktop;
  if (typeof desktop?.saveReport === 'function') {
    const pngBase64 = screenshotBlob ? bytesToBase64(pngBytes) : '';
    const result = await desktop.saveReport({
      stamp,
      json: jsonText,
      pngBase64,
    });
    if (!result?.ok) throw Error(result?.error || '桌面版儲存失敗');
    return { mode: 'desktop', path: result.path, stamp };
  }
  const files = [{ name: 'report.json', bytes: jsonBytes }];
  if (pngBytes.length) files.unshift({ name: 'screenshot.png', bytes: pngBytes });
  const zip = zipStore(files);
  const filename = `rov-report-${stamp}.zip`;
  downloadBlob(filename, zip);
  return { mode: 'browser', filename, stamp };
}
