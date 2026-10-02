// Operator tools keep the diving canvas clear; all mutations go to the server.
import {saveReplay} from './replay_store.js';
import {configureRenderQuality} from './render_quality.js';
const $ = id => document.getElementById(id);
export function downloadFile(name, blob) {
  const url = URL.createObjectURL(blob), a = document.createElement('a');
  a.href = url; a.download = name; a.click(); setTimeout(() => URL.revokeObjectURL(url), 3000);
}
export function installCockpit({send, getState, getWorld, getSession, wsUrl, canvas, renderer, capturePhoto, takePhoto, openCollection, rememberVehicle=true, readOnly=false}) {
  const rack = document.querySelector('aside');
  const section = document.createElement('div'); section.className = 'sec mission-tools';
  section.innerHTML = `<div class="session-summary"><strong id="activeVehicleName">ROV</strong><p class="hint" id="activeRoomName"></p><button id="returnMenu">返回主選單</button></div><div hidden>
    <label for="playerName">操作員名稱</label><input id="playerName" maxlength="32" placeholder="操作員">
    <label for="serverAddress">伺服器位址</label><input id="serverAddress" type="url" spellcheck="false" aria-describedby="serverHint">
    <p id="serverHint" class="hint">線上主機可填 https://網域；區域網路可填 ws://主機IP:8765。</p>
    <label for="roomCode">房間代碼</label><div class="row gap"><input id="roomCode" maxlength="32" value="training"><button id="joinRoom">加入</button></div>
    <p id="roomStatus" class="hint" aria-live="polite">正在連線</p><button id="pairController">配對 USB 遙控器</button>
    <div class="row gap"><select id="vehicleSelect" aria-label="ROV 機型"><option value="x1">X1</option><option value="bluerov2_heavy">BlueROV2 Heavy</option><option value="falcon">Falcon + 機械臂</option></select><button id="changeVehicle">換機</button></div>
    <p class="hint">換機會回到投放點並鎖定馬達。</p></div>
    <details><summary>巡檢與航線</summary>
      <div class="row gap"><input id="markerLabel" maxlength="80" placeholder="巡檢標記名稱"><button id="addMarker">標記</button></div>
      <div class="btns c2"><button id="addWaypoint">此處設航點</button><button id="clearRoute">清除航線</button></div>
      <label>覆蓋航線：寬／長／間隔（m）</label><div class="row gap"><input id="routeWidth" type="number" min="1" max="50" value="8" aria-label="航線寬度"><input id="routeLength" type="number" min="1" max="50" value="10" aria-label="航線長度"><input id="routeSpacing" type="number" min="0.5" max="10" step="0.5" value="2" aria-label="航線間距"></div>
      <button id="coverageRoute">產生覆蓋航線</button>
      <div class="btns c2"><button id="startRoute">開始巡航</button><button id="stopRoute">停止巡航</button></div>
      <div class="row gap"><input id="altitudeTarget" type="number" min="0.5" max="30" step="0.5" value="2" aria-label="定高公尺"><button id="holdAltitude">定高</button><button id="stopAltitude">取消</button></div>
      <p id="missionStatus" class="hint"></p>
    </details>
    <details id="armPanel"><summary>機械臂</summary><p class="hint">Falcon 作業臂 · 參數為訓練估算</p>
      <label class="tog">手臂操作模式<input id="armMode" type="checkbox"></label>
      <div id="armJoints"></div><div class="btns c2"><button id="gripOpen">張開</button><button id="gripClose">夾取</button></div><p id="armStatus" class="hint"></p>
    </details>
    <details><summary>紀錄與畫質</summary><div class="btns c2"><button id="savePhoto">下載照片</button><button id="saveVideo">錄製畫面</button><button id="recordFlight">開始任務紀錄</button><button id="exportMission">匯出巡檢資料</button></div>
      <label for="loadReplay">開啟任務回放</label><input id="loadReplay" type="file" accept="application/json,.json">
      <div hidden><label for="quality">畫質</label><select id="quality"><option value="auto">自動 · 優先流暢（目標 60 FPS）</option><option value="performance">流暢 · 降低解析度</option><option value="medium">標準 · 原生解析度</option><option value="high">高 · 細節優先</option></select></div>
    </details><p id="operationNotice" class="hint" role="status"></p>`;
  rack.prepend(section);
  const query = new URLSearchParams(location.search);
  const read = (key, fallback) => { try { return localStorage.getItem(key) || fallback; } catch { return fallback; } };
  $('playerName').value = read('rov.playerName', '操作員'); $('roomCode').value = query.get('room') || 'training';
  $('serverAddress').value=wsUrl;
  const modelIds=['x1','bluerov2_heavy','falcon'];
  const initialModel=query.get('model')||read('rov.vehicle','x1');
  let preferredModel=modelIds.includes(initialModel)?initialModel:'x1';
  $('vehicleSelect').value=preferredModel;
  const notify = text => { $('operationNotice').textContent = text; };
  const collectionButton=document.createElement('button');collectionButton.id='openCollection';collectionButton.textContent='照片、圖鑑與工程紀錄';collectionButton.onclick=()=>openCollection?.();document.querySelector('.session-summary').append(collectionButton);
  $('returnMenu').onclick=()=>{
    if(flight)finishFlight();
    if(recorder?.state==='recording'){notify('請先停止並下載錄影，再返回主選單。');return;}
    const url=new URL(location.href);url.searchParams.delete('play');url.searchParams.delete('replay');url.searchParams.delete('nointro');url.searchParams.set('model',preferredModel);location.assign(url);
  };
  const op = (action, extra={}) => send({type:'operation',action,...extra});
  $('joinRoom').onclick = () => {
    const url = new URL(location.href); url.searchParams.set('room', $('roomCode').value.trim() || 'training');
    url.searchParams.delete('replay');
    try {
      const address=new URL($('serverAddress').value.trim()||wsUrl);
      if(address.protocol==='https:'||address.protocol==='http:'){
        address.protocol=address.protocol==='https:'?'wss:':'ws:';
        if(address.pathname==='/')address.pathname='/ws';
      }
      if(!['ws:','wss:'].includes(address.protocol)||address.username||address.password)throw Error();
      if(location.protocol==='https:'&&address.protocol==='ws:'){notify('此安全網頁需要使用 wss:// 伺服器。');return;}
      address.hash='';url.searchParams.set('ws',address.href);
    }catch{notify('請填寫有效的 https:// 或 ws(s):// 伺服器位址。');return;}
    url.searchParams.set('model',$('vehicleSelect').value);
    try { localStorage.setItem('rov.playerName', $('playerName').value.trim() || '操作員'); } catch {}
    location.assign(url);
  };
  $('changeVehicle').onclick = () => send({type:'model',model_id:$('vehicleSelect').value});
  $('pairController').onclick=()=>{
    const session=getSession();if(!session){notify('連線後才能配對');return;}
    downloadFile('rov-controller-pairing.json',new Blob([JSON.stringify({url:wsUrl,room_id:session.room_id,resume_token:session.resume_token},null,2)],{type:'application/json'}));
    notify('在接有 Q-iRC 的電腦執行 python -m qysim.qirc_bridge --config 配對檔案路徑。');
  };
  $('addMarker').onclick = () => op('mark',{label:$('markerLabel').value});
  $('addWaypoint').onclick = () => op('waypoint');
  $('clearRoute').onclick = () => op('route_clear');
  $('coverageRoute').onclick = () => op('coverage',{width:+$('routeWidth').value,length:+$('routeLength').value,spacing:+$('routeSpacing').value});
  $('startRoute').onclick = () => op('route_start'); $('stopRoute').onclick = () => op('route_stop');
  $('holdAltitude').onclick = () => op('altitude',{metres:+$('altitudeTarget').value}); $('stopAltitude').onclick = () => op('altitude',{metres:null});
  const limits=[[-95,95],[-65,75],[-120,120],[-100,100]], names=['底座','肩部','肘部','腕部'];
  let grip=1;
  limits.forEach(([min,max],i) => {
    const label=document.createElement('label'); label.className='sl'; label.textContent=names[i];
    const input=document.createElement('input'); input.type='range'; input.min=min; input.max=max; input.step=1; input.value=[0,-15,30,-15][i]; input.id=`armJoint${i}`;
    label.append(input); $('armJoints').append(label); input.onchange=()=>op('arm',{joints:limits.map((_,j)=>+$(`armJoint${j}`).value),grip});
  });
  const setGrip=value=>{grip=value; op('arm',{grip});};
  $('gripOpen').onclick=()=>setGrip(1); $('gripClose').onclick=()=>setGrip(0);
  $('armMode').onchange=()=>{ if($('armMode').checked) notify('駕駛搖桿已回中；使用關節滑桿操作機械臂。'); };
  $('savePhoto').onclick=()=>{
    if(takePhoto){takePhoto({download:true});return;}
    const s=getState(),stamp=Date.now();
    const pose={t:s?.t,vehicle_id:s?.vehicle_id,pos:s?.pos,q:s?.q};
    capturePhoto(blob=>{
      if(!blob){notify('照片擷取失敗，請再試一次。');return;}
      if(!readOnly&&s?.mission?.mode==='inspection_coop')op('mission_photo');
      downloadFile(`ROV-${stamp}.png`,blob);
      downloadFile(`ROV-${stamp}-pose.json`,new Blob([JSON.stringify(pose,null,2)],{type:'application/json'}));
    });
  };
  let recorder=null, chunks=[];
  $('saveVideo').onclick=()=>{
    if(recorder?.state==='recording'){recorder.stop();return;}
    if(!canvas.captureStream || !window.MediaRecorder){notify('此瀏覽器不支援錄影');return;}
    const stream=canvas.captureStream(30); chunks=[];
    const mime=['video/webm;codecs=vp9','video/webm;codecs=vp8','video/webm'].find(m=>MediaRecorder.isTypeSupported(m));
    try {recorder=new MediaRecorder(stream,mime?{mimeType:mime}:{});}catch(e){stream.getTracks().forEach(t=>t.stop());notify(e.message);return;}
    recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};
    recorder.onerror=e=>{notify('錄影失敗：'+(e.error?.message||'無法擷取畫面'));stream.getTracks().forEach(t=>t.stop());$('saveVideo').textContent='錄製畫面';};
    recorder.onstop=()=>{const blob=new Blob(chunks,{type:recorder.mimeType});if(blob.size>128)downloadFile(`ROV-${Date.now()}.webm`,blob);else notify('錄製時間太短，沒有可用影像，請重新錄製。');stream.getTracks().forEach(t=>t.stop());$('saveVideo').textContent='錄製畫面';};
    recorder.start(1000); $('saveVideo').textContent='停止並下載';
  };
  let flight=null,lastRecorded=-1,flightBytes=0;
  const byteLength=value=>new TextEncoder().encode(JSON.stringify(value)).byteLength;
  function finishFlight(){
    if(!flight)return;
    downloadFile(`ROV-mission-${Date.now()}.json`,new Blob([JSON.stringify({version:2,hz:10,clips:[flight]})],{type:'application/json'}));
    flight=null;$('recordFlight').textContent='開始任務紀錄';
  }
  $('recordFlight').onclick=()=>{
    if(flight){finishFlight();return;}
    if(!getWorld()||!getState()){notify('連線後才能記錄');return;}
    flight={title:'巡檢任務',model_id:getState().model_id,world:structuredClone(getWorld()),frames:[structuredClone(getState())],script:[]};lastRecorded=getState().t;$('recordFlight').textContent='停止並下載回放';
    flightBytes=byteLength(flight);
  };
  $('exportMission').onclick=()=>{
    const s=getState(); if(!s)return;
    downloadFile(`ROV-inspection-${Date.now()}.json`,new Blob([JSON.stringify({version:1,frame:'NED',model_id:s.model_id,vehicle_id:s.vehicle_id,scenario:getWorld()?.scenario,operations:s.operations},null,2)],{type:'application/json'}));
  };
  $('loadReplay').onchange=async()=>{
    const file=$('loadReplay').files[0];if(!file)return;
    try {
      if(file.size>100*1024*1024)throw Error('回放檔案上限 100 MB');
      const text=await file.text(), data=JSON.parse(text);
      if(!data.clips?.length || !data.clips.every(c=>c.world&&c.frames?.length))throw Error('不是有效的任務回放');
      const id=await saveReplay(data);
      const page=new URL(location.href);page.searchParams.set('replay','local:'+id);page.searchParams.set('nointro','1');location.assign(page);
    }catch(e){notify(e.message);}
  };
  $('quality').value=new URLSearchParams(location.search).get('quality')||read('rov.quality','auto');
  function quality(){configureRenderQuality(renderer,$('quality').value);try{localStorage.setItem('rov.quality',$('quality').value);}catch{} window.dispatchEvent(new Event('resize'));}
  $('quality').onchange=quality; quality();
  if(readOnly){
    for(const id of ['changeVehicle','pairController','addMarker','addWaypoint','clearRoute','coverageRoute','startRoute','stopRoute','holdAltitude','stopAltitude','gripOpen','gripClose','armMode','recordFlight'])$(id).disabled=true;
    for(let i=0;i<4;i++)$(`armJoint${i}`).disabled=true;
    notify('回放模式；返回主選單後可重新開始潛航。');
  }
  let lastUI=0,armSession='',lastModel='';
  return {
    get recording(){return recorder?.state==='recording';},
    get model(){return preferredModel;},
    get name(){return $('playerName').value;},get room(){return $('roomCode').value;},get armMode(){return $('armMode').checked;},
    message(m){notify(m.message || (m.ok?'已套用':'作業指令未完成'));},
    update(s){
      if(flight && (s.t<lastRecorded || flight.model_id!==s.model_id || flight.world.scenario?.key!==getWorld()?.scenario?.key || flight.world.scenario?.seed!==getWorld()?.scenario?.seed))finishFlight();
      if(flight && s.t-lastRecorded>=.1){
        const frame=structuredClone(s),bytes=byteLength(frame);
        if(flightBytes+bytes>90*1024*1024){finishFlight();notify('任務紀錄已達檔案大小上限，已下載。');}
        else{flight.frames.push(frame);flightBytes+=bytes+1;lastRecorded=s.t;if(flight.frames.length>=18000){finishFlight();notify('任務紀錄已達 18,000 筆上限，已下載。');}}
      }
      if(performance.now()-lastUI<200)return;lastUI=performance.now();
      const room=s.room; $('roomStatus').textContent=room?`房間 ${room.id} · ${room.players?.length||s.vehicles?.length||1}/${room.capacity||3} 人`:'單機／回放';
      $('activeRoomName').textContent=readOnly?'任務回放':$('roomStatus').textContent;
      const a=s.operations?.arm;$('armPanel').hidden=!a?.available;
      const sessionKey=`${getSession()?.resume_token}:${getSession()?.generation}:${s.model_id}:${s.control_generation}`;
      if(a&&sessionKey!==armSession){armSession=sessionKey;grip=a.grip;limits.forEach((_,i)=>$(`armJoint${i}`).value=a.joints[i]);}
      $('armMode').disabled=readOnly||!!s.controller;
      if(!a?.available||s.controller)$('armMode').checked=false;
      $('armStatus').textContent=(a?.status||'')+(s.controller?' · USB 遙控器仍負責駕駛':'');
      $('missionStatus').textContent=`${s.operations?.markers?.length||0} 個標記 · ${s.operations?.waypoints?.length||0} 個航點${s.operations?.altitude!=null?` · 定高 ${s.operations.altitude} m`:''}`;
      if(s.model_id&&s.model_id!==lastModel){
        lastModel=s.model_id;preferredModel=s.model_id;$('vehicleSelect').value=s.model_id;
        $('activeVehicleName').textContent={x1:'X1',falcon:'Falcon · 機械臂',bluerov2_heavy:'BlueROV2 Heavy'}[s.model_id]||'ROV';
        if(rememberVehicle){try{
          localStorage.setItem('rov.vehicle',s.model_id);
          window.rovDesktop?.rememberModel(s.model_id);
          const url=new URL(location.href);if(url.searchParams.has('model')){url.searchParams.set('model',s.model_id);history.replaceState(null,'',url);}
        }catch{}}
      }
    }
  };
}
