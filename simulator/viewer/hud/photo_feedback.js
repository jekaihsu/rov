// What the operator gets when a photo is taken: the topside App's shutter sound (topside cues are real: the operator
// hears the App, see audio/fidelity.js), a brief white flash of the picture, a 已拍照 toast and a short pad rumble
// (padHaptics preference). Presentation only; the photo itself, its evidence and scoring are unchanged.
const STRINGS = {taken: '已拍照'};
const STYLE = `
#flightShutter { inset: 0; background: #fff; opacity: 0; z-index: var(--z-hud-alert); }
#flightShutter.fire { animation: flight-shutter 220ms ease-out; }
#flightToast { left: 50%; bottom: calc(4% + 84px); transform: translateX(-50%); padding: 6px 18px;
  border-block: 1px solid var(--hud-accent); color: var(--hud-accent); font-size: 16px; font-weight: 600;
  letter-spacing: .08em; opacity: 0; transition: opacity 180ms ease-out; z-index: var(--z-notice); }
#flightToast.visible { opacity: 1; }
@keyframes flight-shutter { from { opacity: .55; } to { opacity: 0; } }
@media (prefers-reduced-motion: reduce) {
  #flightShutter.fire { animation: none; }
  #flightToast { transition: none; }
}
`;
const TOAST_MS = 1600;

function layer(id, viewport) {
  const element = document.createElement('div');
  element.id = id;
  element.className = 'flight';
  viewport.append(element);
  return element;
}

// audio: the audio engine (cue), haptics: the input layer's haptics (pulse). Both optional.
export function installPhotoFeedback({viewport, audio = null, haptics = null}) {
  const style = document.createElement('style');
  style.textContent = STYLE;
  document.head.append(style);
  const flash = layer('flightShutter', viewport);
  const toast = layer('flightToast', viewport);
  toast.setAttribute('role', 'status');
  let hideAt = 0;
  function hideToast() {
    if (performance.now() >= hideAt) toast.classList.remove('visible');
  }
  function shutter() {
    audio?.cue?.('shutter');
    haptics?.pulse?.('photo');
    flash.classList.remove('fire');
    void flash.offsetWidth;
    flash.classList.add('fire');
    toast.textContent = STRINGS.taken;
    toast.classList.add('visible');
    hideAt = performance.now() + TOAST_MS;
    setTimeout(hideToast, TOAST_MS);
  }
  return {shutter};
}
