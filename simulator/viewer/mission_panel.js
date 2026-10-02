export function installMissionPanel({send,getState,readOnly=false}){
  const panel=document.createElement('section');panel.className='mission-mode-panel';
  panel.innerHTML='<h3 class="mission-mode-title"></h3><p class="mission-mode-summary"></p><ol class="mission-mode-targets"></ol><button type="button" class="mission-photo">巡檢拍照</button><p class="hint mission-mode-feedback" role="status"></p>';
  document.querySelector('.mission-tools')?.append(panel);
  const title=panel.querySelector('h3'),summary=panel.querySelector('.mission-mode-summary'),targets=panel.querySelector('ol'),photo=panel.querySelector('button'),feedback=panel.querySelector('.mission-mode-feedback');
  const style=document.createElement('style');style.textContent='.mission-mode-panel{border-top:1px solid #284048;margin-top:12px;padding-top:10px}.mission-mode-panel h3{margin:4px 0;color:#dfbc61;font-size:14px}.mission-mode-panel p{font-size:12px;line-height:1.6}.mission-mode-targets{padding-left:20px;font-size:12px;line-height:1.6}.mission-mode-targets li{margin-bottom:8px}.mission-mode-targets progress{display:block;width:100%;height:5px;accent-color:#dfbc61}.mission-photo{width:100%}';document.head.append(style);
  photo.onclick=()=>{if(readOnly)return;document.getElementById('savePhoto')?.click();feedback.textContent='正在擷取照片並確認巡檢條件…';};
  let signature='';
  function update(state){
    const mission=state?.mission;
    panel.hidden=!mission||mission.mode==='scenario_training'||mission.mode==='expedition';
    const scoreSection=document.getElementById('score')?.closest('.sec');if(scoreSection)scoreSection.hidden=!!mission&&mission.mode!=='scenario_training';
    if(panel.hidden)return;
    title.textContent=mission.label||'潛航任務';
    const cooperative=mission.mode==='inspection_coop';targets.hidden=!cooperative;photo.hidden=!cooperative||readOnly;
    photo.disabled=mission.status!=='active';
    if(!cooperative){summary.textContent='自由探索 · 無倒數與評分。可以練習操控、機械臂、攝影與表面標記。';feedback.textContent='';return;}
    const remaining=Math.max(0,Math.ceil(mission.remaining||0));
    summary.textContent=mission.status==='completed'?`全隊完成 ${mission.completed}/${mission.total} 站！`:mission.status==='expired'?`時間結束 · 完成 ${mission.completed}/${mission.total} 站`:`全隊 ${mission.completed}/${mission.total} 站 · 剩餘 ${Math.floor(remaining/60)}:${String(remaining%60).padStart(2,'0')}`;
    const key=JSON.stringify((mission.targets||[]).map(t=>[t.id,t.label,t.completed,t.completed_by,Math.round((t.own_progress||0)*100),t.ready]));
    if(key!==signature){signature=key;targets.replaceChildren(...(mission.targets||[]).map(target=>{
      const item=document.createElement('li'),label=document.createElement('span');
      label.textContent=`${target.completed?'✓ ':''}${target.label}${target.completed?` · ${target.completed_by||'隊友'} 完成`:target.ready?' · 已穩定，可拍照':''}`;
      item.append(label);if(!target.completed){const bar=document.createElement('progress');bar.max=1;bar.value=target.own_progress||0;bar.setAttribute('aria-label',target.label+' 懸停進度');item.append(bar);}return item;
    }));}
    const recentPhoto=mission.last_photo&&state.t-mission.last_photo.t<6?mission.last_photo.message:null;
    feedback.textContent=recentPhoto||(mission.ready_target?'已穩定懸停，按「巡檢拍照」完成本站。':'靠近任一站點，在 1.5 m 內以不超過 0.35 m/s 的速度穩定 3 秒，再拍照。有巡檢物時須朝向目標。');
  }
  return {update,dispose(){panel.remove();style.remove();}};
}
