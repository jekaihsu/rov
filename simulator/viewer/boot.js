const query=new URLSearchParams(location.search);
if(query.get('play')==='1'||query.has('replay')||document.documentElement.dataset.replay||window.QYSIM_REPLAY){
  document.documentElement.classList.add('in-game');
  await import('./app.js');
}else{
  await import('./main_menu.js');
}
