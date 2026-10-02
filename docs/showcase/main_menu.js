import * as THREE from 'three';
import {Environment} from './environment.js';
import {createVehicleModel} from './vehicle_models.js';
import {loadGLTF} from './glb.js';
import {applyVehicleSticker,STICKERS} from './vehicle_stickers.js';
import {configureRenderQuality,updateRenderQuality,renderQualityInfo} from './render_quality.js';
import {installCollectionPanel} from './collection_panel.js';
const query=new URLSearchParams(location.search),$=id=>document.getElementById(id);
const read=(key,fallback)=>{try{return localStorage.getItem(key)||fallback;}catch{return fallback;}};
const models={falcon:{name:'Falcon',detail:'五推進器作業型 ROV · 四關節機械臂'},bluerov2_heavy:{name:'BlueROV2 Heavy',detail:'八推進器 · 六自由度操控'},x1:{name:'X1',detail:'六推進器 · 緊湊型機身'}};
let selected=query.get('model')||read('rov.vehicle','falcon');if(!models[selected])selected='falcon';
let settings={};try{settings=JSON.parse(read('rov.menuSettings','{}'));}catch{}
document.body.classList.add('menu-open');
const menu=document.createElement('main');menu.className='launch-menu';menu.id='launchMenu';
menu.innerHTML=`<div class="menu-shade"></div><header class="menu-brand"><b>ROV</b> 潛航模擬器</header>
<div class="menu-title"><small>EXPLORE BELOW THE SURFACE</small><h1>準備<br>下一次潛航。</h1><p>選擇你的機器與海域。<br>從這裡開始一趟水下任務。</p></div>
<form class="launch-panel" id="launchForm"><section><h2>01 / 選擇 ROV</h2><div class="menu-models">${Object.entries(models).map(([id,m])=>`<button type="button" data-vehicle="${id}" aria-pressed="false">${m.name}</button>`).join('')}</div><p class="model-description" id="modelDescription"></p></section>
<section><h2>02 / 潛航海域</h2><label for="menuScene">場景</label><select id="menuScene"><option>正在準備場景…</option></select><p class="menu-help" id="sceneBrief"></p><p class="menu-help">加入既有房間時，以房主的場景為準。</p></section>
<details open><summary>連線與操作員</summary><div class="menu-row"><div><label for="menuName">操作員名稱</label><input id="menuName" maxlength="32" required></div><div><label for="menuRoom">房間代碼</label><input id="menuRoom" maxlength="32" pattern="[A-Za-z0-9_-]{1,32}" required></div></div><label for="menuServer">伺服器</label><input id="menuServer" type="url" required spellcheck="false"><p class="menu-help">保留本機位址即可單人遊玩；多人請填同一主機與房間。</p></details>
<details><summary>手柄與設定</summary><label for="menuPad">輸入裝置</label><select id="menuPad"><option value="auto">自動偵測手柄＋鍵盤</option><option value="keyboard">只使用鍵盤</option></select><p class="menu-help" id="menuPadInfo">連接手柄後按任一按鍵以偵測。</p><label for="menuControl">控制配置</label><select id="menuControl"><option value="UAV_CHN">ROV 雙桿：左桿前後／平移，右桿升降／轉向</option><option value="ROV_USA">X1 配置：左桿俯仰／轉向，右桿前後／橫滾</option><option value="ROV_JPN">X1 日本配置</option><option value="ROV_CHN">X1 中國配置</option></select><label for="menuQuality">畫質</label><select id="menuQuality"><option value="medium">中 · 效能優先</option><option value="high">高 · 細節優先</option></select><label class="menu-toggle">操作員小視窗<input id="menuPip" type="checkbox"></label><label class="menu-toggle">下水動畫<input id="menuIntro" type="checkbox" checked></label><label class="menu-toggle">畫面搖桿<input id="menuSticks" type="checkbox" checked></label><label class="menu-toggle">真實能見度<input id="menuFog" type="checkbox" checked></label><label class="menu-toggle">場景標籤<input id="menuLabels" type="checkbox" checked></label></details>
<p class="menu-status" id="menuStatus" role="status">正在準備 3D 預覽…</p><button class="menu-start" id="startDive" type="submit" disabled><span>開始潛航</span><span aria-hidden="true">↗</span></button></form><div class="menu-caption"><span class="menu-backdrop-label">LIVE 3D PREVIEW / 場景預覽</span><strong id="previewTitle"></strong><span id="previewScene"></span></div>`;
document.body.append(menu);
const performanceSection=document.createElement('section');performanceSection.className='menu-performance';performanceSection.innerHTML='<h2>本機效能</h2><p id="menuHardware" class="menu-help">正在偵測目前使用的顯示卡…</p><p id="menuQualityState" class="menu-help"></p>';
$('launchForm').prepend(performanceSection);performanceSection.append(document.querySelector('label[for="menuQuality"]'),$('menuQuality'));
const launchFooter=document.createElement('div');launchFooter.className='menu-launch-footer';$('startDive').setAttribute('form','launchForm');launchFooter.append($('menuStatus'),$('startDive'));menu.append(launchFooter);
const modeSection=document.createElement('section');modeSection.innerHTML='<h2>遊玩模式</h2><label for="menuMode">任務</label><select id="menuMode"><option value="expedition">海洋探索與工程 · 1～3 人自由接案</option><option value="free_explore">自由探索 · 無時間壓力</option><option value="inspection_coop">協作巡檢 · 三站穩定拍照</option><option value="scenario_training">場景訓練 · 原場景目標與評分</option></select><p id="modeBrief" class="menu-help"></p><button id="menuCollection" type="button">我的照片、圖鑑與工程紀錄</button>';
performanceSection.after(modeSection);const modeDescriptions={expedition:'探索海域、拍攝生物與自由接案。回收及部署需 Falcon 機械臂；首版工程海域為珊瑚礁、海草床與港灣。',free_explore:'自由操控、練習機械臂與噴漆，不計時也不扣分。',inspection_coop:'最多三人分工巡檢；靠近站點、穩定懸停後拍照，在 12 分鐘內完成三站。',scenario_training:'依照所選場景的既有訓練目標、時間與評分規則進行。'};
$('menuMode').value=query.get('mission')||read('rov.mission','expedition');if(!$('menuMode').value)$('menuMode').value='expedition';$('menuMode').onchange=()=>{$('modeBrief').textContent=modeDescriptions[$('menuMode').value]+' 加入既有房間時以房主設定為準。';};$('menuMode').onchange();
const collectionPanel=installCollectionPanel({});$('menuCollection').onclick=()=>collectionPanel.open();
const stickerLabel=document.createElement('label');stickerLabel.htmlFor='menuSticker';stickerLabel.textContent='機身貼紙';
const stickerSelect=document.createElement('select');stickerSelect.id='menuSticker';stickerSelect.append(...Object.entries(STICKERS).map(([id,label])=>new Option(label,id)));$('modelDescription').after(stickerLabel,stickerSelect);stickerSelect.value=query.get('sticker')||read('rov.sticker','none');
$('menuName').value=query.get('name')||read('rov.playerName','操作員');$('menuRoom').value=query.get('room')||'training';
$('menuServer').value=query.get('ws')||(location.protocol==='https:'?`wss://${location.host}/ws`:`ws://${location.hostname||'127.0.0.1'}:8765`);
$('menuControl').value=query.get('control')||settings.control||'UAV_CHN';$('menuQuality').replaceChildren(...[['auto','自動 · 依硬體調整（目標 60 FPS）'],['performance','流暢 · 降低解析度'],['medium','標準 · 原生解析度'],['high','高 · 細節優先']].map(([value,label])=>new Option(label,value)));$('menuQuality').value=query.get('quality')||read('rov.quality','auto');
for(const [id,key,fallback]of [['menuPip','pip',false],['menuIntro','intro',true],['menuSticks','sticks',true],['menuFog','fog',true],['menuLabels','labels',true]])$(id).checked=settings[key]??fallback;
const reduced=matchMedia('(prefers-reduced-motion:reduce)').matches;
const scene=new THREE.Scene();scene.background=new THREE.Color('#0c3342');scene.fog=new THREE.Fog('#0c3342',7,36);
scene.add(new THREE.HemisphereLight(0xc9eeff,0x29362b,2));
for(const [pos,power,color]of [[[3,7,6],3,0xffffff],[[-4,2,-1],2,0x64c4dc]]){const light=new THREE.DirectionalLight(color,power);light.position.set(...pos);scene.add(light);}
const renderer=new THREE.WebGLRenderer({antialias:true,powerPreference:'high-performance'});renderer.setPixelRatio(Math.min(devicePixelRatio,1.5));renderer.outputColorSpace=THREE.SRGBColorSpace;renderer.toneMapping=THREE.ACESFilmicToneMapping;menu.prepend(renderer.domElement);
function qualityStatus(){const info=renderQualityInfo(renderer);$('menuHardware').textContent=info?.hardwareLabel?`${info.hardwareLabel} · ${info.hardwareReason}`:'依畫面效能調整';$('menuQualityState').textContent=`目前渲染比例 ${info?.scale||100}% · ROV 開發版 0.3`;}
configureRenderQuality(renderer,$('menuQuality').value);qualityStatus();$('menuQuality').onchange=()=>{configureRenderQuality(renderer,$('menuQuality').value);qualityStatus();try{localStorage.setItem('rov.quality',$('menuQuality').value);}catch{}window.rovDesktop?.rememberQuality($('menuQuality').value);};setInterval(qualityStatus,1000);
const camera=new THREE.PerspectiveCamera(42,innerWidth/innerHeight,.02,5000);
let model=null,environment=null,modelTicket=0,sceneTicket=0,world=null,scenes=[],readyModel=false,readyScene=false;
const structures=new THREE.Group();scene.add(structures);const anchor=new THREE.Vector3(0,-12,0),look=new THREE.Vector3();
function ready(){ $('startDive').disabled=!(readyModel&&readyScene);$('menuStatus').textContent=readyModel&&readyScene?'已就緒 · 按「開始潛航」進入遊戲':'正在準備 3D 預覽…'; }
async function selectModel(id){
  selected=id;readyModel=false;ready();const ticket=++modelTicket;
  document.querySelectorAll('[data-vehicle]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.vehicle===id)));
  $('modelDescription').textContent=models[id].detail;$('previewTitle').textContent=models[id].name;
  try{const next=await createVehicleModel(id);if(ticket!==modelTicket){next.dispose();return;}if(next.loadError)throw next.loadError;model?.dispose();model=next;scene.add(model.root);model.root.position.copy(anchor);model.updateArm({joints:[0,-15,30,-15],grip:.7});applyVehicleSticker(model,stickerSelect.value);readyModel=true;ready();}
  catch(error){$('menuStatus').textContent='模型載入失敗，請重新選擇機型。';}
}
const P=p=>new THREE.Vector3(-p[1],-p[2],p[0]);
async function selectScene(){
  const entry=scenes.find(s=>s.key===$('menuScene').value);if(!entry)return;
  const ticket=++sceneTicket;readyScene=false;ready();world=entry.world;environment?.dispose();environment=new Environment(scene,world);
  structures.traverse(o=>{o.geometry?.dispose();if(o.material)(Array.isArray(o.material)?o.material:[o.material]).forEach(m=>m.dispose());});structures.clear();
  anchor.copy(P(world.start_pos||[0,0,0]));anchor.y=-world.seabed_depth+1.4;
  $('sceneBrief').textContent=entry.brief;$('previewScene').textContent=entry.name;
  for(const ob of world.obstacles||[]){
    if(ob.kind==='habitat')continue;
    let mesh;
    if(ob.type==='cylinder'){const a=P(ob.p0),b=P(ob.p1);mesh=new THREE.Mesh(new THREE.CylinderGeometry(ob.radius,ob.radius,a.distanceTo(b),12),new THREE.MeshStandardMaterial({color:0x647474,roughness:.9}));mesh.position.copy(a).lerp(b,.5);mesh.quaternion.setFromUnitVectors(new THREE.Vector3(0,1,0),b.sub(a).normalize());}
    else if(ob.type==='box'){mesh=new THREE.Mesh(new THREE.BoxGeometry(ob.half[1]*2,ob.half[2]*2,ob.half[0]*2),new THREE.MeshStandardMaterial({color:0x53686c}));mesh.position.copy(P(ob.center));mesh.rotation.y=-ob.yaw_deg*Math.PI/180;}
    else if(ob.type==='model'){loadGLTF(ob.model).then(g=>{if(ticket!==sceneTicket)return;const m=g.scene;m.position.copy(P(ob.origin));m.rotation.y=Math.atan2(-Math.cos(ob.heading_deg*Math.PI/180),-Math.sin(ob.heading_deg*Math.PI/180));structures.add(m);}).catch(()=>{});}
    if(mesh)structures.add(mesh);
  }
  const habitat=world.habitat?.entities||[];
  const nearby=habitat.filter(o=>['coral','seagrass','kelp'].includes(o.kind)).sort((a,b)=>Math.hypot(a.pos[0],a.pos[1])-Math.hypot(b.pos[0],b.pos[1]))[0];
  if(nearby?.pos){anchor.copy(P(nearby.pos));anchor.y+=1.5;}
  model?.root.position.copy(anchor);readyScene=true;ready();
}
document.querySelectorAll('[data-vehicle]').forEach(b=>b.onclick=()=>selectModel(b.dataset.vehicle));$('menuScene').onchange=selectScene;
stickerSelect.onchange=()=>applyVehicleSticker(model,stickerSelect.value);
let padSignature='';function pads(){const list=[...(navigator.getGamepads?.()||[])].filter(g=>g?.connected),signature=list.map(g=>g.index+g.id).join('|');if(signature===padSignature)return;padSignature=signature;const value=$('menuPad').value;while($('menuPad').options.length>2)$('menuPad').remove(2);for(const g of list){const option=new Option(g.id,String(g.index));$('menuPad').add(option);}$('menuPad').value=[...$('menuPad').options].some(o=>o.value===value)?value:'auto';$('menuPadInfo').textContent=list.length?`已偵測 ${list.length} 支手柄`:'未偵測到手柄，仍可使用鍵盤。';}
const padTimer=setInterval(pads,500);addEventListener('gamepadconnected',pads);addEventListener('gamepaddisconnected',pads);
$('launchForm').onsubmit=event=>{
  event.preventDefault();if(!readyModel||!readyScene)return;
  try{
    const server=new URL($('menuServer').value.trim());if(['https:','http:'].includes(server.protocol)){server.protocol=server.protocol==='https:'?'wss:':'ws:';if(server.pathname==='/')server.pathname='/ws';}
    if(!['ws:','wss:'].includes(server.protocol)||server.username||server.password)throw Error('請填寫有效的伺服器位址。');
    if(location.protocol==='https:'&&server.protocol!=='wss:')throw Error('安全網頁需要使用 wss:// 伺服器。');
    const url=new URL(location.href);url.searchParams.delete('replay');url.searchParams.set('play','1');url.searchParams.set('model',selected);url.searchParams.set('ws',server.href);url.searchParams.set('room',$('menuRoom').value);url.searchParams.set('name',$('menuName').value);url.searchParams.set('scenario',$('menuScene').value);url.searchParams.set('seed','42');url.searchParams.set('control',$('menuControl').value);url.searchParams.set('pad',$('menuPad').value);
    url.searchParams.set('sticker',stickerSelect.value);localStorage.setItem('rov.sticker',stickerSelect.value);
    url.searchParams.set('quality',$('menuQuality').value);window.rovDesktop?.rememberQuality($('menuQuality').value);
    url.searchParams.set('mission',$('menuMode').value);localStorage.setItem('rov.mission',$('menuMode').value);
    if($('menuIntro').checked)url.searchParams.delete('nointro');else url.searchParams.set('nointro','1');
    const settings={control:$('menuControl').value,pip:$('menuPip').checked,intro:$('menuIntro').checked,sticks:$('menuSticks').checked,fog:$('menuFog').checked,labels:$('menuLabels').checked};
    localStorage.setItem('rov.menuSettings',JSON.stringify(settings));localStorage.setItem('rov.playerName',$('menuName').value);localStorage.setItem('rov.quality',$('menuQuality').value);localStorage.setItem('rov.operatorVisible',String(settings.pip));localStorage.setItem('rov.vehicle',selected);window.rovDesktop?.rememberModel(selected);
    $('startDive').disabled=true;menu.classList.add('departing');setTimeout(()=>location.assign(url),reduced?0:450);
  }catch(error){$('menuStatus').textContent=error.message;}
};
function resize(){const height=innerWidth<850?400:innerHeight;renderer.setSize(innerWidth,height);camera.aspect=innerWidth/height;camera.updateProjectionMatrix();}resize();addEventListener('resize',resize);
let last=performance.now(),elapsed=0;function frame(now){const seconds=(now-last)/1000;const dt=Math.min(.05,seconds);last=now;updateRenderQuality(renderer,seconds,{suspended:!readyModel||!readyScene});if(!reduced)elapsed+=dt;if(model){model.root.position.copy(anchor);model.root.position.y+=Math.sin(elapsed*.6)*.07;model.root.rotation.y=.45+Math.sin(elapsed*.18)*.18;}
  const small=innerWidth<850;look.copy(anchor).add(new THREE.Vector3(small?0:1.05,small?.7:.25,0));const approach=reduced?1:1+.4*Math.exp(-elapsed*1.4);camera.position.copy(anchor).add(new THREE.Vector3(-2.7,1.65,3.2).multiplyScalar(approach));camera.lookAt(look);environment?.update(dt,camera,new THREE.Vector3(.1,0,0));renderer.render(scene,camera);requestAnimationFrame(frame);
}requestAnimationFrame(frame);
window.__menu={get model(){return selected;},get stickerMeshes(){return model?.stickerGroup?.children.length||0;},get scene(){return $('menuScene').value;},get ready(){return readyModel&&readyScene;},renderer};
addEventListener('pagehide',()=>clearInterval(padTimer));
try{scenes=await(await fetch('scene_previews.json')).json();const preferred=['coral_reef','seagrass_meadow','harbor_inspection'];scenes.sort((a,b)=>(preferred.includes(a.key)?preferred.indexOf(a.key):99)-(preferred.includes(b.key)?preferred.indexOf(b.key):99));$('menuScene').replaceChildren(...scenes.map(s=>new Option(s.name,s.key)));$('menuScene').value=query.get('scenario')||'coral_reef';if(!$('menuScene').value)$('menuScene').selectedIndex=0;await selectScene();await selectModel(selected);}catch(error){$('menuStatus').textContent='開場預覽載入失敗，請重新整理。';console.error(error);}
