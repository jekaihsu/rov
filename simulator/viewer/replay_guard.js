// Keep corrupt or unsupported recordings out of the live session and provide a way back to the launcher.
import {STRINGS} from './photo_settings.js';

export function replayFailure() {
  if (document.querySelector('#replayFailure')) return;
  const dialog = document.createElement('dialog');
  dialog.id = 'replayFailure';
  const message = document.createElement('p');
  message.textContent = STRINGS.corrupt;
  const exit = document.createElement('button');
  exit.textContent = STRINGS.menu;
  exit.onclick = () => location.assign(new URL('./', location.href));
  dialog.append(message, exit);
  document.body.append(dialog);
  dialog.oncancel = event => event.preventDefault();
  dialog.showModal();
}

export function guardPlayback(frame) {
  return function replayFrame(now) {
    try {
      frame(now);
    } catch {
      replayFailure();
    }
  };
}
