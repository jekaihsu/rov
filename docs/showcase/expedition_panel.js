export function installExpeditionPanel({send,getSession,takePhoto,openCollection,setOnboard,readOnly=false}){
  const panel=document.createElement('section');panel.className='expedition-panel';panel.hidden=true;
  panel.innerHTML=`<div class="expedition-title"><strong>海洋探索與工程</strong><button type="button" class="exp-collection">收藏</button></div>
    <p class="exp-summary">自由探索海域，也能接取工程委託。</p>
    <details class="exp-contracts" open><summary>工程委託</summary><div class="exp-available"></div><div class="exp-active"></div></details>
    <div class="exp-camera-actions"><button type="button" class="exp-onboard">機載視角</button><button type="button" class="exp-photo">拍攝觀測照</button></div>
    <p class="exp-hint">機載相機拍到清楚、未受遮擋的生物，即可登錄個人圖鑑。</p>
    <details><summary>本次發現與隊伍標記 <span class="exp-count"></span></summary><ul class="exp-discoveries"></ul></details>
    <p class="exp-feedback" role="status"></p>`;
  document.querySelector('.session-summary')?.after(panel);
  const css=document.createElement('style');css.textContent=`.expedition-panel{border-block:1px solid #284048;padding:12px 0;margin:12px 0;color:#dce8ea}.expedition-title{display:flex;align-items:center;justify-content:space-between;gap:10px}.expedition-title strong{color:#dfbc61;font-size:14px}.expedition-title button{width:auto}.expedition-panel p,.expedition-panel li{font-size:12px;line-height:1.65}.expedition-panel p{margin:7px 0}.exp-summary,.exp-hint{color:#9aacb7}.expedition-panel details{margin-block:10px}.expedition-panel summary{cursor:pointer}.exp-available label{font-size:12px}.exp-available select{width:100%;margin-block:8px}.exp-available button,.exp-active>button{width:100%}.exp-active ol{padding-left:22px}.exp-active progress{display:block;width:100%;height:4px;accent-color:#dfbc61}.exp-camera-actions{display:grid;grid-template-columns:1fr 1.2fr;gap:7px}.exp-discoveries{padding-left:18px;max-height:170px;overflow:auto}.exp-discoveries button{font-size:11px;margin-left:6px;padding:3px 7px}.exp-feedback{color:#dfbc61;min-height:1.6em}.expedition-panel button:disabled{opacity:.5}.expedition-panel details[open]>div{animation:exp-reveal .16s ease-out}@keyframes exp-reveal{from{opacity:0;transform:translateY(-3px)}to{opacity:1;transform:none}}@media(prefers-reduced-motion:reduce){.expedition-panel details[open]>div{animation:none}}`;
  document.head.append(css);
  const find=s=>panel.querySelector(s),feedback=find('.exp-feedback');
  find('.exp-collection').onclick=openCollection;find('.exp-photo').onclick=()=>takePhoto();find('.exp-onboard').onclick=()=>setOnboard();
  let signature='',discoverySignature='',selected='inspect',lastDive='',lastResult='',lastUpdate=0;
  const command=(action,extra={})=>{
    if(readOnly)return;
    const request_id=globalThis.crypto?.randomUUID?.()||`request-${Date.now()}-${Math.random().toString(36).slice(2)}`;
    if(!send({type:'operation',action,request_id,...extra}))feedback.textContent='目前離線，請等待重新連線。';
  };
  function update(s){
    if(performance.now()-lastUpdate<200)return;lastUpdate=performance.now();
    const exp=s?.expedition;panel.hidden=s?.mission?.mode!=='expedition'||!exp;if(panel.hidden)return;
    const host=!!getSession()?.is_host;
    if(exp.dive_id!==lastDive){lastDive=exp.dive_id;lastResult='';signature='';discoverySignature='';feedback.textContent='';}
    const active=exp.active;
    find('.exp-summary').textContent=active?`${active.label} · 全隊共享進度`:'沒有進行中的委託 · 可繼續探索、拍照或接案';
    find('.exp-photo').disabled=readOnly;find('.exp-onboard').disabled=false;
    const key=JSON.stringify([host,active?.id,(active?.steps||[]).map(step=>[step.id,step.completed,step.own_progress??step.progress,step.ready,step.point&&s.pos?Math.round(Math.hypot(...step.point.map((v,i)=>v-s.pos[i]))*2):null]),exp.available]);
    if(key!==signature){
      signature=key;const available=find('.exp-available'),body=find('.exp-active');available.replaceChildren();body.replaceChildren();
      if(active){
        const list=document.createElement('ol');
        for(const step of active.steps||[]){
          const li=document.createElement('li');li.textContent=`${step.completed?'✓ ':''}${step.label}${step.ready?' · 可拍照':''}`;
          if(!step.completed&&step.point&&s.pos){const d=Math.hypot(...step.point.map((v,i)=>v-s.pos[i]));li.textContent+=` · ${d.toFixed(1)} m`;}
          if(!step.completed&&Number.isFinite(step.own_progress??step.progress)){const bar=document.createElement('progress');bar.max=1;bar.value=step.own_progress??step.progress;li.append(bar);}
          list.append(li);
        }
        body.append(list);const cancel=document.createElement('button');cancel.textContent='取消這項委託';cancel.disabled=!host||readOnly;cancel.onclick=()=>command('expedition_cancel');body.append(cancel);
      }else{
        const select=document.createElement('select');select.setAttribute('aria-label','工程委託種類');
        for(const item of exp.available||[]){const option=new Option(item.label,item.kind);select.add(option);}
        select.value=selected;if(!select.value)select.selectedIndex=0;
        const reason=document.createElement('p'),start=document.createElement('button');start.textContent=host?'接取委託':'等待房主接案';
        const choose=()=>{selected=select.value;const entry=(exp.available||[]).find(x=>x.kind===selected);reason.textContent=entry?.reason||({inspect:'穩定停靠三個站點，以機載相機完成巡檢。',recover:'拍攝目標，使用機械臂帶回交付區並釋放。',deploy:'從補給區取得感測器，放置到指定海床並拍照。'}[selected]||'');start.disabled=readOnly||!host||!entry?.enabled;};
        select.onchange=choose;start.onclick=()=>command('expedition_start',{contract:selected});choose();available.append(select,reason,start);
      }
    }
    const discoveries=exp.discoveries||[],markers=exp.markers||[];
    find('.exp-count').textContent=`(${discoveries.length} / ${markers.length})`;
    const dkey=JSON.stringify([discoveries,markers]);
    if(discoverySignature!==dkey){
      discoverySignature=dkey;const list=find('.exp-discoveries');list.replaceChildren();
      for(const item of discoveries){const li=document.createElement('li');li.textContent=`${item.label||item.category||'觀測'} · ${item.photographer||item.vehicle_id||'隊友'}`;const mark=document.createElement('button');mark.textContent=markers.some(m=>m.entity_id===item.entity_id)?'已標記':'共享位置';mark.disabled=readOnly;mark.onclick=()=>command('expedition_mark',{entity_id:item.entity_id});li.append(mark);list.append(li);}
      if(!discoveries.length){const li=document.createElement('li');li.textContent='隊友的新發現會顯示在這裡。';list.append(li);}
    }
    const result=(exp.results||[]).at(-1);
    if(result&&result.id!==lastResult){lastResult=result.id;feedback.textContent=`${result.label||'工程委託'} · ${result.grade||result.rating||'已完成'}。可繼續探索或接下一項。`;}
  }
  return {update,notify(text){feedback.textContent=text;},dispose(){panel.remove();css.remove();}};
}
