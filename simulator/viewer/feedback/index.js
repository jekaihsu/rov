// One-click playtest bug report: F8 / touchpad hold / pause-menu entry. Captures a screenshot and a
// 60-second state summary (scenario, fidelity, quality, device, FPS, server log, console errors) for
// local save only — never uploaded, never stores personal identifiers.
import { createSummaryBuffer } from './summary.js';
import { createFeedbackDialog } from './dialog.js';
import { canOpenReportsFolder, openReportsFolder, saveFeedbackReport } from './save.js';
import { localize } from '../i18n/index.js';

const STRINGS = localize('feedback.index', {
  action: '回報問題',
});

let dialogOpen = false;
let api = null;

export function feedbackOpen() {
  return dialogOpen;
}

export function openFeedbackReport() {
  return api?.show();
}

export { canOpenReportsFolder, openReportsFolder };

function qualityValue() {
  return document.getElementById('quality')?.value || null;
}

function ensureCss() {
  if (document.querySelector('link[data-rov-feedback]')) return;
  const link = document.createElement('link');
  link.rel = 'stylesheet';
  link.href = new URL('./feedback.css', import.meta.url).href;
  link.dataset.rovFeedback = '';
  document.head.append(link);
}

function canvasToPng(canvas) {
  if (!canvas) return Promise.resolve(null);
  try {
    // toDataURL is sync and reliable under software WebGL; toBlob can stall headless.
    const dataUrl = canvas.toDataURL('image/png');
    const comma = dataUrl.indexOf(',');
    if (comma < 0) return Promise.resolve(null);
    const binary = atob(dataUrl.slice(comma + 1));
    const bytes = new Uint8Array(binary.length);
    for (let i = 0; i < binary.length; i += 1) bytes[i] = binary.charCodeAt(i);
    return Promise.resolve(new Blob([bytes], { type: 'image/png' }));
  } catch {
    if (!canvas.toBlob) return Promise.resolve(null);
    return new Promise(function toBlob(resolve) {
      const timer = setTimeout(function giveUp() {
        resolve(null);
      }, 1500);
      canvas.toBlob(function done(blob) {
        clearTimeout(timer);
        resolve(blob || null);
      }, 'image/png');
    });
  }
}

// input: installInput result; capture(): WebGL canvas after an optional render; getPerformance(): {fps,...}.
export function installFeedbackReport({
  input,
  getState,
  getWorld,
  capture,
  getPerformance = null,
}) {
  ensureCss();
  const buffer = createSummaryBuffer();
  let screenshotBlob = null;

  const dialog = createFeedbackDialog({
    canOpenFolder: canOpenReportsFolder,
    onOpenFolder: openReportsFolder,
    onClose() {
      dialogOpen = false;
      screenshotBlob = null;
    },
    async onSubmit({ description, category }) {
      const report = buffer.build({
        category,
        description,
        quality: qualityValue(),
        performanceInfo: getPerformance?.() || null,
      });
      const result = await saveFeedbackReport({
        screenshotBlob,
        report,
      });
      screenshotBlob = null;
      return result;
    },
  });

  async function show() {
    if (dialog.open) return;
    dialogOpen = true;
    dialog.show();
    try {
      const canvas = capture?.();
      screenshotBlob = await canvasToPng(canvas);
    } catch {
      screenshotBlob = null;
    }
  }

  function hide() {
    dialog.hide();
  }

  function inGame() {
    return !!getState?.() && document.documentElement.classList.contains('in-game');
  }

  api = { show, hide };
  input.registerActions({
    reportBug: {
      label: STRINGS.action,
      enabled() {
        return inGame() && !dialogOpen;
      },
      run() {
        show();
      },
    },
  });

  const timer = setInterval(function sample() {
    if (!inGame()) return;
    buffer.sample({
      state: getState?.(),
      world: getWorld?.(),
      performanceInfo: getPerformance?.() || null,
      quality: qualityValue(),
    });
  }, 1000);

  return {
    show,
    hide,
    dispose() {
      clearInterval(timer);
      buffer.dispose();
      hide();
      api = null;
    },
    get open() {
      return dialogOpen;
    },
  };
}
