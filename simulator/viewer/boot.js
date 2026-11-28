// Entry: hydrate desktop file saves, then open the launch menu or jump straight into a dive.
import { installSaves } from './saves/bootstrap.js';
import { steamEdition } from './menu/edition.js';

if (steamEdition) document.documentElement.dataset.edition = 'steam';
await installSaves();

const query = new URLSearchParams(location.search);
if (query.get('play') === '1' || query.has('replay') || document.documentElement.dataset.replay || window.QYSIM_REPLAY) {
  document.documentElement.classList.add('in-game');
  await import('./app.js');
} else {
  await import('./menu/main.js');
}
