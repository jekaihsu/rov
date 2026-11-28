// Replay controls for the story menu reuse the menu's preview grid and focus navigation.
import {element} from '../beat_stage.js';
import {STRINGS} from './copy.js';
import {playBoard} from './player.js';

export function replayFilms() {
  return ['harbor', 'strait'].map(function film(id) {
    const button = element('button', 'menu-site menu-play-card');
    button.type = 'button';
    button.dataset.chapter = 'film-' + id;
    const media = element('span', 'menu-site-media menu-card-media');
    const image = element('img');
    image.loading = 'lazy';
    image.alt = '';
    image.src = new URL(id + '-preview.jpg', import.meta.url).href;
    media.append(image);
    const body = element('span', 'menu-site-body');
    body.append(element('strong', 'menu-card-title', STRINGS[id]));
    button.append(media, body);
    button.onclick = () => playBoard(id, {menu: true});
    return button;
  });
}
