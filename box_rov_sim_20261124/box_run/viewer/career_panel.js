import {CATALOG} from './career_rules.js';
import {loadCareer,updateCareer} from './career_store.js';
export function installCareerPanel({onPreview=()=>{},onEquip=()=>{},readOnly=false}={}){
  const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('./career.css',import.meta.url);document.head.append(css);
  const dialog=document.createElement('dialog');dialog.className='career-panel';dialog.setAttribute('aria-label','補給商店與生涯');
  dialog.innerHTML=`<header><div><small>OCEAN SUPPLY</small><h2>補給商店</h2></div><button type="button" data-close aria-label="關閉商店">×</button></header>
  <div class="career-wallet"><strong data-balance>—</strong><span>探索點數<br><small>遊玩獲得 · 僅購買外觀</small></span></div>
  <nav aria-label="商店分類"><button data-tab="shop" type="button">外觀商店</button><button data-tab="career" type="button">生涯與成就</button><button data-tab="guide" type="button">潛航指南</button></nav>
  <p class="career-notice" role="status" aria-live="polite"></p><main></main><footer>自動儲存於本機 · 配色不影響 ROV 性能</footer>`;
  document.body.append(dialog);const content=dialog.querySelector('main'),notice=dialog.querySelector('[role=status]');let data,tab='shop',selected=CATALOG[0],confirm=false,busy=false,previous;
  const el=(tag,text)=>{const n=document.createElement(tag);n.textContent=text;return n;};
  function preview(){if(data)onPreview({...data.profile.equipped,[selected.kind]:selected.value});}
  function render(){
    if(!data)return;dialog.querySelector('[data-balance]').textContent=data.summary.balance.toLocaleString();
    dialog.querySelectorAll('[data-tab]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.tab===tab)));
    content.replaceChildren();
    if(tab==='shop'){
      const list=el('div','');list.className='career-products';
      for(const p of CATALOG){const button=el('button','');button.type='button';button.dataset.product=p.id;button.setAttribute('aria-pressed',String(selected.id===p.id));
        const swatch=el('span',p.kind==='sticker'?'≈':'');swatch.className='career-swatch';swatch.style.background=p.color;swatch.setAttribute('aria-hidden','true');
        const label=el('span',p.name),price=el('small',data.profile.owned.includes(p.id)?'已擁有':`${p.price} 點`);label.append(price);button.append(swatch,label);
        button.onclick=()=>{selected=p;confirm=false;notice.textContent='機庫正在預覽；購買後可套用。';render();preview();dialog.querySelector(`[data-product="${p.id}"]`).focus();};list.append(button);
      }content.append(list);
      const detail=el('section','');detail.className='career-detail';detail.append(el('small',selected.kind==='sticker'?'機身貼紙':'外殼配色'),el('h3',selected.name),el('p',selected.description));
      const owned=data.profile.owned.includes(selected.id),equipped=data.profile.equipped[selected.kind]===selected.value;
      const action=el('button',owned?(equipped?'已套用':'套用外觀'):(confirm?`確認購買 · ${selected.price} 點`:`購買 · ${selected.price} 點`));action.type='button';action.className='career-primary';action.dataset.purchase='';
      action.disabled=busy||readOnly||equipped||(!owned&&data.summary.balance<selected.price);
      action.onclick=async()=>{if(!owned&&!confirm){confirm=true;render();dialog.querySelector('[data-purchase]').focus();return;}busy=true;render();try{
        data=await updateCareer(owned?{type:'equip',kind:selected.kind,value:selected.value}:{type:'buy',id:selected.id});
        notice.textContent=owned?'外觀已套用並儲存。':'購買成功，可按「套用外觀」裝備。';confirm=false;if(owned)onEquip(data.profile.equipped);
      }catch(error){notice.textContent=error.message;}finally{busy=false;render();}};
      detail.append(action);if(!owned&&data.summary.balance<selected.price)detail.append(el('p',`還需要 ${selected.price-data.summary.balance} 點。完成工程 +200；首次生物發現 +100。`));
      const reset=el('button','恢復原廠配色');reset.type='button';reset.disabled=busy||readOnly;reset.onclick=async()=>{try{data=await updateCareer({type:'equip',kind:'livery',value:'original'});onEquip(data.profile.equipped);notice.textContent='已恢復原廠配色。';render();}catch(e){notice.textContent=e.message;}};detail.append(reset);content.append(detail);
    }else if(tab==='career'){
      const s=data.summary;content.append(el('h3',s.rank),el('p',`工程完成 ${s.contracts} 次 · 圖鑑 ${s.species}/5 · 照片 ${s.photos} 張`),el('p',`累積獲得 ${s.earned} 點 · 已使用 ${s.spent} 點`));
      for(const a of s.achievements){const row=el('section','');row.className='career-achievement';row.append(el('strong',`${a.unlocked?'✓ ':''}${a.name}`),el('p',`${a.detail} · ${a.current}/${a.goal} · 獎勵 ${a.reward} 點`));const progress=document.createElement('progress');progress.max=a.goal;progress.value=a.current;progress.setAttribute('aria-label',a.name);row.append(progress);content.append(row);}
      content.append(el('p','報酬自動入帳。相同任務紀錄與同類圖鑑只計算一次；成就獎勵不需手動領取。'));
    }else{
      const steps=[['01 / 準備','選擇海洋探索與工程模式。回收與部署任務請使用 ROV-01-PRO；先確認手柄配置和畫質。'],['02 / 探索','切換機載視角，靠近珊瑚、海星、海草、海藻或魚群拍照。有效觀測解鎖圖鑑，首次每類 +100 點。'],['03 / 接案','由房主接取工程委託。跟隨任務步驟完成巡檢、回收或部署，每次完成 +200 點；取消不給獎勵。'],['04 / 收藏與外觀','成就會自動加發點數。回到主選單選購、預覽與套用外觀；原本的機型和貼紙仍可直接使用。']];
      for(const [title,text]of steps){content.append(el('h3',title),el('p',text));}
      content.append(el('p','生涯保存在這台裝置。瀏覽器版依網站來源分開儲存；桌面版在重新啟動後保留。收藏匯出目前備份照片與工程紀錄，不包含商店購買紀錄。'));
    }
  }
  async function refresh(){try{data=await loadCareer();if(dialog.open)render();return data;}catch(error){notice.textContent=`無法讀取生涯：${error.message}`;}}
  const close=()=>{if(busy)return;dialog.close();if(data)onPreview(data.profile.equipped);previous?.focus();};dialog.querySelector('[data-close]').onclick=close;
  dialog.addEventListener('cancel',e=>{e.preventDefault();close();});
  dialog.querySelectorAll('[data-tab]').forEach(b=>b.onclick=()=>{tab=b.dataset.tab;confirm=false;notice.textContent='';if(data)onPreview(data.profile.equipped);render();});
  return {async open(){previous=document.activeElement;dialog.showModal();notice.textContent='正在讀取生涯…';await refresh();if(data){notice.textContent=readOnly?'展示模式僅供預覽。':'選擇商品可在機庫預覽。';if(tab==='shop')preview();}},refresh};
}
