import * as THREE from 'three';
import {OrbitControls} from './vendor/three/examples/jsm/controls/OrbitControls.js';
import {createTool} from './tool_visuals.js';
import {createVehicleModel} from './vehicle_models.js';
import {toolCatalogue,toolsById,getLoadout,getPresets,checkLoadout,saveLoadout} from './loadout_store.js';
const css=document.createElement('link');css.rel='stylesheet';css.href='tool_showroom.css';document.head.append(css);
const esc=s=>String(s).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
let instance;
export function openToolShowroom(model='rov01_pro'){instance??=createShowroom();return instance.open(model);}
function createShowroom(){
 const dialog=document.createElement('dialog');dialog.className='equipment';dialog.setAttribute('aria-label','工具庫與動態展間');
 dialog.innerHTML=`<header class="eq-head"><strong>ROV / 工具庫</strong><small>24 類工具 · 動態展間</small><span class="eq-badge">外觀參考重建</span><button class="eq-close" aria-label="關閉工具庫">關閉</button></header><div class="eq-body"><nav class="eq-rail" aria-label="工具清單"><input id="eqSearch" placeholder="搜尋工具或廠牌" aria-label="搜尋工具"><select id="eqCategory" aria-label="工具分類"><option value="">全部工具</option>${[...new Set(toolCatalogue.tools.map(t=>t.category))].map(c=>`<option>${c}</option>`).join('')}</select><div class="eq-list" role="listbox"></div></nav><section class="eq-stage"><canvas class="eq-canvas"></canvas><div class="eq-stage-label"><h2 id="eqTitle"></h2><p id="eqProduct"></p></div><div class="eq-modes"><button data-view="tool">工具特寫</button><button data-view="vehicle">掛載預覽</button><button id="eqAuto">暫停展示</button><select id="eqAngle" aria-label="檢視角度"><option value="orbit">自由視角</option><option value="front">正面</option><option value="back">背面</option><option value="left">左側</option><option value="right">右側</option><option value="top">頂部</option><option value="bottom">底部</option></select></div></section><aside class="eq-inspector"><p id="eqDesc"></p><div class="eq-metrics" id="eqSpecs"></div><div class="eq-readout" id="eqReadout"></div><label>動作預覽<input id="eqMotion" type="range" min="0" max="1" step=".01" value=".5"></label><p id="eqDemoHint">展間示範數值；下水後改用任務中的即時資料。</p><h3>安裝工具</h3><select id="eqMount" aria-label="選擇掛點"></select><button id="eqInstall" class="primary">安裝到 ROV</button><h3>目前配置</h3><div class="eq-slots"></div><p id="eqBudget"></p><label>配置名稱<input id="eqPresetName" maxlength="40" placeholder="例如：海纜巡檢"></label><select id="eqPresets" aria-label="已儲存配置"><option value="">載入已儲存配置</option></select><p><a id="eqSource" target="_blank" rel="noreferrer">原廠參考資料 ↗</a></p><p id="eqProvenance"></p></aside></div><footer class="eq-foot"><span class="eq-status" role="status">準備模型…</span><button id="eqDefault">標準配置</button><button id="eqSave" class="primary">儲存並套用</button></footer>`;
 document.body.append(dialog);const $=s=>dialog.querySelector(s);
 $('.eq-stage').insertAdjacentHTML('beforeend','<div class="eq-markers" aria-label="掛載位置"></div><p class="eq-mount-caption"></p>');
 $('.eq-modes').insertAdjacentHTML('beforeend','<button id="eqLocate">定位已裝工具</button><button id="eqWhole">整機視角</button><button id="eqGhost" aria-pressed="false">機身透視</button>');
 $('#eqProvenance').insertAdjacentHTML('afterend','<p id="eqMountReference"></p>');
 const scene=new THREE.Scene();scene.background=new THREE.Color('#141f27');
 scene.add(new THREE.HemisphereLight(0xe6f4ff,0x374149,2.4));
 for(const [p,c,i]of [[[2,4,5],0xffeee0,3],[[-3,1,-2],0x8ec8e0,3]]){const l=new THREE.DirectionalLight(c,i);l.position.set(...p);scene.add(l);}
 const renderer=new THREE.WebGLRenderer({canvas:$('.eq-canvas'),antialias:true,alpha:false});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.toneMapping=THREE.ACESFilmicToneMapping;
 const camera=new THREE.PerspectiveCamera(38,1,.001,100);const controls=new OrbitControls(camera,renderer.domElement);controls.enableDamping=true;controls.autoRotateSpeed=.7;
 const grid=new THREE.GridHelper(4,40,0x42515d,0x26343f);grid.position.y=-.3;scene.add(grid);
 let vehicleId='rov01_pro',loadout=[],selected='hydraulic_arm',mode='tool',tool=null,vehicle=null,ticket=0,playing=true,last=0,time=0,lastStatus='',loadError=false;
 let ghost=false,pendingFocus=false,focusMove=null,markers=[];
 const hullMaterials=new Map(),selectionBox=new THREE.Box3Helper(new THREE.Box3(),0xedb64e);
 selectionBox.material.depthTest=false;selectionBox.material.transparent=true;selectionBox.renderOrder=100;selectionBox.visible=false;scene.add(selectionBox);
 function mountReference(){
   const blue=vehicleId.startsWith('rov02');
   const ref=blue&&selected==='gripper'?['Newton 安裝指南','local://docs/rov-payloads','原廠位置：前部底板、電池筒旁；模型座標為近似重建。']:blue&&selected==='ping360'?['Ping360 安裝指南','local://docs/rov-payloads',vehicleId.includes('heavy')?'原廠位置：Heavy 側框中段支架；模型座標為近似重建。':'原廠位置：側框前部支架；模型座標為近似重建。']:null;
   $('#eqMountReference').innerHTML=ref?`${esc(ref[2])} <a href="${ref[1]}" target="_blank" rel="noreferrer">${ref[0]} ↗</a>`:'配置位置示意；此工具的轉接支架與實機安裝位置待確認。';
 }
 function pause(){playing=false;$('#eqAuto').textContent='播放展示';}
 function clearMounts(){markers=[];$('.eq-markers').replaceChildren();selectionBox.visible=false;hullMaterials.clear();focusMove=null;}
 function buildMarkers(){
   $('.eq-markers').replaceChildren();markers=toolCatalogue.vehicles[vehicleId].mounts.map((mount,index)=>{
     const item=loadout.find(i=>i.slot===mount.id),button=document.createElement('button');
     button.className='eq-marker';button.dataset.slot=mount.id;button.textContent=String(index+1).padStart(2,'0');button.title=`${mount.name} · ${item?toolsById.get(item.tool).name:'未配置'}`;button.setAttribute('aria-label',button.title);button.classList.toggle('occupied',!!item);
     const label=document.createElement('span');label.textContent=`${mount.name} · ${item?toolsById.get(item.tool).name:'未配置'}`;button.append(label);
     button.onclick=()=>{if(item){mode='vehicle';select(item.tool,false);pendingFocus=true;}else status(`${mount.name}：未配置 · 掛載座標為示意`);};
     $('.eq-markers').append(button);return {mount,item,button};
   });
   vehicle.root.traverse(o=>{if(o.isMesh&&!o.userData.tool)for(const m of Array.isArray(o.material)?o.material:[o.material])if(!hullMaterials.has(m))hullMaterials.set(m,{opacity:m.opacity,transparent:m.transparent,depthWrite:m.depthWrite});});
   applyGhost();
 }
 function applyGhost(){for(const [m,original]of hullMaterials){m.opacity=ghost?Math.min(original.opacity,.16):original.opacity;m.transparent=ghost||original.transparent;m.depthWrite=ghost?false:original.depthWrite;m.needsUpdate=true;}$('#eqGhost').setAttribute('aria-pressed',String(ghost));}
 function focusInstalled(){const root=vehicle?.payload.items.get(selected)?.root;if(!root)return false;root.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(root),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()).length();const direction=camera.position.clone().sub(controls.target).normalize();focusMove={target:center,position:center.clone().add(direction.multiplyScalar(Math.max(.45,size*2.4)))};pause();return true;}
 function updateMounts(){
   const active=mode==='vehicle'&&!!vehicle;$('.eq-markers').hidden=!active;$('#eqGhost').disabled=!active;$('#eqWhole').disabled=!active;$('#eqLocate').disabled=!loadout.some(i=>i.tool===selected);selectionBox.visible=false;
   if(!active){$('.eq-mount-caption').textContent='';return;}
   const root=vehicle.payload.items.get(selected)?.root;
   if(root){root.updateMatrixWorld(true);selectionBox.box.setFromObject(root);selectionBox.visible=true;}
   if(pendingFocus&&focusInstalled())pendingFocus=false;
   const width=$('.eq-stage').clientWidth,height=$('.eq-stage').clientHeight;
   for(const {mount,item,button}of markers){const p=new THREE.Vector3(-mount.position[1],-mount.position[2],mount.position[0]);vehicle.root.localToWorld(p);p.project(camera);const x=(p.x+1)*width/2,y=(1-p.y)*height/2;button.hidden=p.z<-1||p.z>1||x<16||x>width-16||y<145||y>height-125;button.style.left=`${x}px`;button.style.top=`${y}px`;button.classList.toggle('selected',item?.tool===selected);const label=button.firstElementChild;label.style.left=x>width/2?'auto':'34px';label.style.right=x>width/2?'34px':'auto';label.style.maxWidth=`${Math.max(70,Math.min(230,(x>width/2?x:width-x)-50))}px`;}
   const installed=loadout.find(i=>i.tool===selected),mount=markers.find(m=>m.mount.id===installed?.slot);
   $('.eq-mount-caption').textContent=mount?`已裝：${toolsById.get(selected).name} → ${mount.mount.name} · 琥珀框為工具外廓`:'選擇「定位」查看已安裝工具；編號為示意掛載位置';
   if(vehicle.payload.errors.length)status(`部分工具載入失敗：${vehicle.payload.errors.join('；')}`,true);
 }
 const observer=new ResizeObserver(()=>{const box=$('.eq-stage').getBoundingClientRect();if(!box.width||!box.height)return;renderer.setSize(box.width,box.height,false);camera.aspect=box.width/box.height;camera.updateProjectionMatrix();});observer.observe($('.eq-stage'));
 function status(text,error=false){$('.eq-status').textContent=text;$('.eq-status').classList.toggle('eq-error',error);}
 function list(){const q=$('#eqSearch').value.toLowerCase(),cat=$('#eqCategory').value;$('.eq-list').innerHTML=toolCatalogue.tools.filter(t=>(!cat||t.category===cat)&&`${t.name} ${t.product}`.toLowerCase().includes(q)).map(t=>`<button role="option" aria-selected="${t.id===selected}" data-tool="${t.id}">${esc(t.name)}<small>${esc(t.product)}</small></button>`).join('');$('.eq-list').querySelectorAll('button').forEach(b=>b.onclick=()=>select(b.dataset.tool));}
 function slots(){
   const def=toolCatalogue.vehicles[vehicleId];
   $('.eq-slots').innerHTML=def.mounts.map((m,index)=>{const item=loadout.find(i=>i.slot===m.id);return `<div class="eq-slot"><span>${String(index+1).padStart(2,'0')} · ${esc(m.name)}<small>${item?esc(toolsById.get(item.tool).name):'未配置'}</small></span>${item?`<button data-locate="${item.tool}" aria-label="定位 ${esc(toolsById.get(item.tool).name)}">定位</button><button aria-label="卸下 ${esc(toolsById.get(item.tool).name)}" data-remove="${m.id}">×</button>`:''}</div>`;}).join('');
   $('.eq-slots').querySelectorAll('[data-locate]').forEach(b=>b.onclick=()=>{mode='vehicle';pendingFocus=true;pause();select(b.dataset.locate,!vehicle);});
   $('.eq-slots').querySelectorAll('[data-remove]').forEach(b=>b.onclick=()=>{loadout=loadout.filter(i=>i.slot!==b.dataset.remove);pendingFocus=false;slots();if(mode==='vehicle')loadPreview();});
   const mass=loadout.reduce((s,i)=>s+toolsById.get(i.tool).mass_kg,0),power=loadout.reduce((s,i)=>s+toolsById.get(i.tool).power_w,0);$('#eqBudget').textContent=`搭載 ${mass.toFixed(2)} / ${def.payload_kg} kg · 工具 ${power} / ${def.power_budget_w} W`;const error=checkLoadout(vehicleId,loadout);$('#eqSave').disabled=!!error;if(error)status(error,true);
 }
 function fit(root){root.updateMatrixWorld(true);const box=new THREE.Box3().setFromObject(root),center=box.getCenter(new THREE.Vector3()),size=box.getSize(new THREE.Vector3()).length();controls.target.copy(center);camera.position.copy(center).add(new THREE.Vector3(-.8,.55,1).normalize().multiplyScalar(Math.max(.18,size)*1.55));controls.minDistance=.03;controls.maxDistance=Math.max(4,size*8);grid.position.y=box.min.y-.015;controls.update();}
 async function loadPreview(){const id=++ticket;clearMounts();dialog.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===mode)));tool?.dispose();tool=null;vehicle?.dispose();vehicle=null;loadError=false;status('正在載入 3D 模型…');try{if(mode==='tool'){const t=await createTool(selected);if(id!==ticket){t.dispose();return;}tool=t;scene.add(t.root);fit(t.root);}else{const v=await createVehicleModel(vehicleId);if(id!==ticket){v.dispose();return;}vehicle=v;scene.add(v.root);v.updatePayload(loadout,{}, {joints:[0,-15,30,-15],grip:.6},0);fit(v.root);buildMarkers();}status('拖曳旋轉 · 滾輪縮放 · 可手動操作工具');}catch(e){if(id!==ticket)return;loadError=true;status(`模型載入失敗：${e.message}`,true);}}
 function select(id,reload=true){selected=id;const t=toolsById.get(id);$('#eqTitle').textContent=t.name;$('#eqProduct').textContent=t.product;$('#eqDesc').textContent=t.description;$('#eqSpecs').innerHTML=`<span>外廓 L × W × H</span><b>${t.dimensions_m.map(n=>Math.round(n*1000)).join(' × ')} mm</b><span>空氣中重量</span><b>${t.mass_kg} kg</b><span>工具功率預算</span><b>${t.power_w} W</b>`;$('#eqSource').href=t.source;$('#eqProvenance').textContent=t.uncertainty;const mounts=toolCatalogue.vehicles[vehicleId].mounts.filter(m=>m.kind===t.slot_kind&&t.models.includes(vehicleId));$('#eqMount').replaceChildren(...(mounts.length?mounts.map(m=>new Option(m.name,m.id)):[new Option('此機型不支援此工具','')]));$('#eqInstall').disabled=!mounts.length;mountReference();list();slots();if(reload)loadPreview();}
 $('#eqLocate').onclick=()=>{pendingFocus=true;pause();if(mode!=='vehicle'){mode='vehicle';loadPreview();}};$('#eqWhole').onclick=()=>{pendingFocus=false;focusMove=null;pause();if(vehicle)fit(vehicle.root);};$('#eqGhost').onclick=()=>{ghost=!ghost;applyGhost();};
 $('#eqSearch').oninput=list;$('#eqCategory').onchange=list;
 $('#eqInstall').onclick=()=>{const slot=$('#eqMount').value,t=toolsById.get(selected);let next=loadout.filter(i=>i.slot!==slot&&i.tool!==selected);next.push({slot,tool:selected});for(const dep of t.requires){if(!next.some(i=>i.tool===dep)){const mount=toolCatalogue.vehicles[vehicleId].mounts.find(m=>m.kind===toolsById.get(dep).slot_kind&&!next.some(i=>i.slot===m.id));if(mount)next.push({slot:mount.id,tool:dep});}}const error=checkLoadout(vehicleId,next);if(error){status(error,true);return;}loadout=next;slots();mode='vehicle';pendingFocus=true;pause();loadPreview();};
 $('#eqDefault').onclick=()=>{loadout=structuredClone(toolCatalogue.vehicles[vehicleId].default_loadout);slots();loadPreview();};
 $('#eqSave').onclick=async()=>{try{await saveLoadout(vehicleId,loadout,$('#eqPresetName').value.trim());status('配置已儲存；開始潛航時套用。');refreshPresets();}catch(e){status(e.message,true);}};
 function refreshPresets(){$('#eqPresets').replaceChildren(new Option('載入已儲存配置',''),...Object.keys(getPresets(vehicleId)).map(n=>new Option(n,n)));}
 $('#eqPresets').onchange=()=>{const l=getPresets(vehicleId)[$('#eqPresets').value];if(l){loadout=l;slots();loadPreview();}};
 $('.eq-close').onclick=()=>dialog.close();dialog.addEventListener('close',()=>{playing=false;});
 dialog.querySelectorAll('[data-view]').forEach(b=>b.onclick=()=>{mode=b.dataset.view;pendingFocus=false;loadPreview();});
 $('#eqAuto').onclick=()=>{playing=!playing;$('#eqAuto').textContent=playing?'暫停展示':'播放展示';};
 $('#eqMotion').oninput=()=>{playing=false;$('#eqAuto').textContent='播放展示';};
 $('#eqAngle').onchange=()=>{const axis={front:[0,0,1],back:[0,0,-1],left:[-1,0,0],right:[1,0,0],top:[0,1,.001],bottom:[0,-1,.001]}[$('#eqAngle').value];if(axis){playing=false;const distance=camera.position.distanceTo(controls.target);camera.position.copy(controls.target).add(new THREE.Vector3(...axis).multiplyScalar(distance));controls.update();}};
 function frame(now){const dt=Math.min(.05,(now-last)/1000||0);last=now;if(dialog.open){if(playing)time+=dt;const f=playing?(Math.sin(time*.8)+1)/2:Number($('#eqMotion').value);if(playing)$('#eqMotion').value=f;const demo={enabled:true,level:.15+.85*f,progress:f,grip:f,phase:time,joints:[Math.sin(time*.3)*25,-15+f*30,30-f*45,-15]};const arm={grip:f,joints:demo.joints};tool?.update(demo,arm);if(vehicle){const states=Object.fromEntries(loadout.map(i=>[i.tool,demo]));vehicle.updatePayload(loadout,states,arm,time);}controls.autoRotate=playing;if(focusMove){const ease=1-Math.exp(-dt*10);camera.position.lerp(focusMove.position,ease);controls.target.lerp(focusMove.target,ease);if(camera.position.distanceTo(focusMove.position)<.001)focusMove=null;}controls.update();updateMounts();renderer.render(scene,camera);const t=toolsById.get(selected);$('#eqReadout').textContent=t.id==='hpu'?`${(12+55*f).toFixed(1)} bar`:t.id==='hydraulic_arm'?`${demo.joints[1].toFixed(0)}° / ${Math.round(f*100)}%`:`${Math.round(f*100)}% · 動態預覽`;window.__toolShowroom={model:vehicleId,selected,mode,loadout,loaded:!!(tool||vehicle)&&!loadError,installedLoaded:vehicle?.payload.items.size||0,ghost,highlighted:selectionBox.visible,meshCount:(()=>{let n=0;(tool?.root||vehicle?.root)?.traverse(o=>{if(o.isMesh)n++;});return n;})};}requestAnimationFrame(frame);}requestAnimationFrame(frame);
 return {open(model){vehicleId=model;loadout=getLoadout(model);selected=loadout[0]?.tool||toolCatalogue.tools.find(t=>t.models.includes(model))?.id||selected;mode=loadout.length?'vehicle':'tool';pendingFocus=false;pause();dialog.showModal();slots();refreshPresets();select(selected);return dialog;}};
}
