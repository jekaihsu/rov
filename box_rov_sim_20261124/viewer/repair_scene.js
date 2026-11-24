import * as THREE from 'three';
import {saveResult,downloadCollectionFile} from './collection_store.js';
const P=p=>new THREE.Vector3(-p[1],-p[2],p[0]);
const roles={survey:'巡檢員',service:'維護員',verify:'復檢員'};
const css=document.createElement('style');css.textContent=`.repair-panel{padding:12px 0;border-block:1px solid #52636b}.repair-panel h2{font-size:15px;color:#ebbd65}.repair-panel p{font-size:11px;line-height:1.6;color:#b6c4cb}.repair-panel select{width:100%;margin:8px 0}.repair-panel .repair-actions{display:flex;gap:6px;flex-wrap:wrap}.repair-panel button{padding:8px;font-size:11px}.repair-panel ol{padding-left:22px;font-size:12px;line-height:1.9}.repair-panel li[data-current=true]{color:#f6c66b}.repair-panel li[data-done=true]{color:#85ceb0}.repair-panel progress{width:100%;accent-color:#e8b35a}.repair-panel .repair-status{color:#e7be79;min-height:32px}.repair-panel .repair-team{font-size:11px;border-top:1px solid #384b55;padding-top:8px}`;document.head.append(css);
export function installRepair({send,getState,focus,readOnly=false}){
 const root=document.createElement('section');root.className='repair-panel';root.hidden=true;
 root.innerHTML=`<h2>多人維修 / 共同工作區</h2><p>預設磨耗的抽象維修展示。分工合作完成保護套與復檢紀錄。</p><select aria-label="維修分工"><option value="">選擇分工</option>${Object.entries(roles).map(([v,n])=>`<option value="${v}">${n}</option>`).join('')}</select><ol></ol><progress max="1" value="0"></progress><div class="repair-actions"><button data-action="start">開始此項工作</button><button data-action="stop">暫停</button><button data-action="assist">支援照明</button><button data-action="focus">查看工作區</button></div><p class="repair-status" role="status"></p><div class="repair-team"></div><button data-action="export">匯出完成紀錄</button>`;
 document.querySelector('.rack.left').prepend(root);const $=s=>root.querySelector(s);let latest=null,signature='',saved=false;
 $('select').onchange=()=>{if($('select').value&&!readOnly)send({type:'operation',action:'repair',verb:'role',role:$('select').value});};
 root.querySelectorAll('[data-action]').forEach(b=>b.onclick=()=>{const a=b.dataset.action;if(a==='focus'){if(latest)focus(latest.point);return;}if(a==='export'){downloadCollectionFile('cooperative-repair.json',new Blob([JSON.stringify(latest,null,2)],{type:'application/json'}));return;}if(!readOnly)send({type:'operation',action:'repair',verb:a});});
 return {update(s){const r=s.repair;latest=r;root.hidden=!r;if(!r)return;
   const sig=JSON.stringify([r.phase,r.roles,r.completed]);if(signature!==sig){signature=sig;$('ol').innerHTML=r.stages.map((st,i)=>`<li data-done="${i<r.phase}" data-current="${i===r.phase}">${st.label}${i<r.phase?' ✓':''}</li>`).join('');
    const role=Object.keys(r.roles).find(k=>r.roles[k]===s.vehicle_id);$('select').value=role||'';
    root.querySelector('.repair-team').replaceChildren(...Object.entries(roles).map(([k,label])=>{const line=document.createElement('p');const vid=r.roles[k],player=s.room?.players?.find(p=>p.vehicle_id===vid);line.textContent=`${label} · ${player?.name||vid||'等待加入'}`;return line;}));}
   $('progress').value=r.completed?1:r.progress;$('.repair-status').textContent=`${r.message}${r.near?'':' · 請靠近標示工作區'}`;
   const role=r.stages[r.phase]?.role;$('[data-action=start]').disabled=readOnly||r.completed||!r.near||r.roles[role]!==s.vehicle_id||!!r.active;
   $('[data-action=stop]').disabled=readOnly||r.active!==s.vehicle_id;
   $('[data-action=assist]').disabled=readOnly||r.completed;$('[data-action=assist]').textContent=r.assisting.includes(s.vehicle_id)?'停止支援照明':'支援照明';
   $('[data-action=export]').disabled=!r.completed;
   if(r.completed&&!saved&&!readOnly){saved=true;saveResult({id:`repair-${s.room?.id||'local'}-${r.records.at(-1)?.t}`,kind:'repair',name:'多人海纜維修展示',success:true,records:r.records}).catch(()=>{saved=false;});}
  },message(m){if(m.type==='operation_result'&&m.action==='repair'&&!m.ok)$('.repair-status').textContent=m.message||'操作失敗';},root};
}
export function createRepairVisual(parent,manifest){
 if(!manifest?.repair)return {update(){},dispose(){}};
 const group=new THREE.Group();group.name='cooperative-maintenance-display';parent.add(group);
 const anchor=P([8,0,11.55]);group.position.copy(anchor);
 const yellow=new THREE.MeshStandardMaterial({color:0xbfa044,metalness:.25,roughness:.56,side:THREE.DoubleSide});
 const steel=new THREE.MeshStandardMaterial({color:0x9aa4a5,metalness:.75,roughness:.3});
 const scarMaterial=new THREE.MeshStandardMaterial({color:0x946f4b,roughness:.95});
 const scar=new THREE.Mesh(new THREE.CylinderGeometry(.126,.126,.95,48,1,true,0,Math.PI*.55),scarMaterial);scar.rotation.x=Math.PI/2;group.add(scar);
 const halves=[];
 for(let side=0;side<2;side++){
  const half=new THREE.Group();const skin=new THREE.Mesh(new THREE.CylinderGeometry(.205,.205,1.55,64,1,true,side*Math.PI,Math.PI),yellow);skin.rotation.x=Math.PI/2;half.add(skin);
  for(let j=-4;j<=4;j++){const rib=new THREE.Mesh(new THREE.TorusGeometry(.208,.013,8,40,Math.PI),yellow);rib.rotation.z=side*Math.PI;rib.position.z=j*.165;half.add(rib);}
  for(let j of [-.65,.65]){const band=new THREE.Mesh(new THREE.TorusGeometry(.23,.015,8,40,Math.PI),steel);band.rotation.z=side*Math.PI;band.position.z=j;half.add(band);}
  group.add(half);halves.push(half);
 }
 const halo=new THREE.Mesh(new THREE.TorusGeometry(1.1,.012,6,64),new THREE.MeshBasicMaterial({color:0xe7b852,transparent:true,opacity:.65}));halo.rotation.y=Math.PI/2;group.add(halo);
 let state=null,amount=0;
 return {update(s,dt=.04){state=s.repair;if(!state)return;const target=state.phase>2?1:state.phase===2?state.progress:0;amount+=Math.min(1,dt*4)*(target-amount);halves.forEach((h,i)=>{h.position.y=(i?1:-1)*(.6*(1-amount));h.visible=state.phase>=1;});scar.visible=state.phase<3;halo.visible=!state.completed;halo.material.opacity=state.active?.length ? .4:.55;},dispose(){group.traverse(o=>{o.geometry?.dispose();if(o.material)o.material.dispose();});group.removeFromParent();}};
}
