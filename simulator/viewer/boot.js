import { steamEdition } from './menu/edition.js';
if (steamEdition) document.documentElement.dataset.edition = 'steam';
const query=new URLSearchParams(location.search);
if(query.get('play')==='1'||query.has('replay')||document.documentElement.dataset.replay||window.QYSIM_REPLAY){
  document.documentElement.classList.add('in-game');
  await import('./app.js');
}else{
  await import('./menu/main.js');
}
