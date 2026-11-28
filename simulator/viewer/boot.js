// Install the DOM recovery surface before loading any module that can fail.
import { installRecovery, bootFailure, startupWatchdog } from './recovery.js';

installRecovery();
const finished = startupWatchdog();
try {
  const { installSaves } = await import('./saves/bootstrap.js');
  await installSaves();
  const query = new URLSearchParams(location.search);
  if (query.get('play') === '1' || query.has('replay') || document.documentElement.dataset.replay || window.QYSIM_REPLAY) {
    document.documentElement.classList.add('in-game');
    await import('./app.js');
  } else {
    await import('./menu/main.js');
  }
} catch (error) {
  bootFailure(error);
} finally {
  finished();
}
