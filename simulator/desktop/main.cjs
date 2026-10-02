const {app,BrowserWindow,dialog,ipcMain,screen}=require('electron');
const {spawn}=require('node:child_process');
const net=require('node:net');
const fs=require('node:fs');
const path=require('node:path');
const {CollectionStore}=require('./collection_store.cjs');
if(process.env.ROV_DESKTOP_SMOKE&&process.env.ROV_DESKTOP_SMOKE_EXPEDITION==='1'&&!process.env.ROV_DESKTOP_SMOKE_DATA)throw Error('探索收藏驗收需要獨立的 ROV_DESKTOP_SMOKE_DATA 目錄');
if(process.env.ROV_DESKTOP_SMOKE&&process.env.ROV_DESKTOP_SMOKE_DATA){
  if(!path.isAbsolute(process.env.ROV_DESKTOP_SMOKE_DATA))throw Error('ROV_DESKTOP_SMOKE_DATA 必須是絕對路徑');
  fs.mkdirSync(process.env.ROV_DESKTOP_SMOKE_DATA,{recursive:true});app.setPath('userData',process.env.ROV_DESKTOP_SMOKE_DATA);
}
let backend=null,log=null;
async function freePort(){return new Promise((resolve,reject)=>{const s=net.createServer();s.once('error',reject);s.listen(0,'127.0.0.1',()=>{const port=s.address().port;s.close(()=>resolve(port));});});}
async function waitReady(port){for(let i=0;i<1200;i++){if(backend.exitCode!==null || backend.signalCode!==null)throw Error('模擬服務啟動失敗，請查看 backend.log');try{const r=await fetch(`http://127.0.0.1:${port}/`,{signal:AbortSignal.timeout(1000)});if(r.ok)return;}catch{}await new Promise(r=>setTimeout(r,100));}throw Error('模擬服務啟動逾時');}
app.whenReady().then(async()=>{
  const root=app.isPackaged?path.join(process.resourcesPath,'backend'):path.resolve(__dirname,'..');
  const bundled=path.join(root,'rov-sim','rov-sim.exe');
  const ports=new Set();while(ports.size<3)ports.add(await freePort());
  const [http,ws,rpc]=[...ports];
  const args=['--host','127.0.0.1','--http-port',String(http),'--ws-port',String(ws),'--rpc-port',String(rpc)];
  const executable=app.isPackaged?bundled:(process.env.ROV_PYTHON||'python');
  const data=app.getPath('userData');fs.mkdirSync(data,{recursive:true});
  const preferencesPath=path.join(data,'preferences.json');
  const modelIds=['x1','bluerov2_heavy','falcon'];
  let preferredModel='x1';
  const qualityModes=['auto','performance','medium','high'];let preferredQuality='auto';
  try{const saved=JSON.parse(fs.readFileSync(preferencesPath,'utf8'));if(modelIds.includes(saved.model))preferredModel=saved.model;if(qualityModes.includes(saved.quality))preferredQuality=saved.quality;}catch{}
  const savePreferences=()=>fs.writeFileSync(preferencesPath,JSON.stringify({model:preferredModel,quality:preferredQuality}));
  const cache=path.join(data,'numba-cache');fs.mkdirSync(cache,{recursive:true});
  log=fs.createWriteStream(path.join(data,'backend.log'),{flags:'a'});
  backend=spawn(executable,app.isPackaged?args:['-X','utf8','-m','qysim.server',...args],{cwd:root,windowsHide:true,env:{...process.env,PYTHONUTF8:'1',NUMBA_CACHE_DIR:cache}});
  backend.stdout.pipe(log,{end:false});backend.stderr.pipe(log,{end:false});
  backend.on('error',e=>{dialog.showErrorBox('模擬器無法啟動',e.message);app.quit();});
  const workArea=screen.getPrimaryDisplay().workAreaSize;
  const window=new BrowserWindow({width:Math.min(1440,workArea.width),height:Math.min(900,workArea.height),minWidth:Math.min(900,workArea.width),minHeight:Math.min(600,workArea.height),show:!process.env.ROV_DESKTOP_SMOKE,backgroundColor:'#081722',autoHideMenuBar:true,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:!process.env.ROV_DESKTOP_SMOKE,preload:path.join(__dirname,'preload.cjs')}});
  const collection=new CollectionStore(path.join(data,'collection'));
  ipcMain.handle('rov:collection',async(event,method,payload)=>{
    let allowed=false;try{allowed=event.sender===window.webContents&&event.senderFrame===window.webContents.mainFrame&&new URL(event.senderFrame.url).origin===`http://127.0.0.1:${http}`;}catch{}
    if(!allowed||!['list','readPhoto','savePhoto','saveResult','setCover','export','import'].includes(method))return {ok:false,error:'此頁面無法存取本機收藏'};
    try{return {ok:true,value:await collection[method](payload)};}catch(error){return {ok:false,error:error.message||'收藏儲存失敗'};}
  });
  ipcMain.on('rov:model-selected',(event,model)=>{
    if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!event.senderFrame.url.startsWith(`http://127.0.0.1:${http}/`)||!modelIds.includes(model)||model===preferredModel)return;
    try{preferredModel=model;savePreferences();}catch(error){log.write(`Could not save model preference: ${error.message}\n`);}
  });
  ipcMain.on('rov:quality-selected',(event,quality)=>{
    if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!event.senderFrame.url.startsWith(`http://127.0.0.1:${http}/`)||!qualityModes.includes(quality))return;
    try{preferredQuality=quality;savePreferences();}catch(error){log.write(`Could not save quality preference: ${error.message}\n`);}
  });
  await window.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<html lang="zh-Hant"><meta charset="utf-8"><body style="margin:0;background:#081722;color:#dce8ea;font:18px system-ui;display:grid;place-content:center;height:100vh"><h1>ROV Simulator</h1><p>正在準備模擬環境，首次啟動可能需要一點時間。</p></body></html>'));
  await waitReady(http);
  window.webContents.setWindowOpenHandler(({url})=>{
    if(url.startsWith(`http://127.0.0.1:${http}/`))return {action:'allow',overrideBrowserWindowOptions:{webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true}}};
    return {action:'deny'};
  });
  window.webContents.on('will-navigate',(event,url)=>{if(!url.startsWith(`http://127.0.0.1:${http}/`))event.preventDefault();});
  await window.loadURL(`http://127.0.0.1:${http}/?ws=${encodeURIComponent(`ws://127.0.0.1:${ws}`)}&nointro&model=${preferredModel}&quality=${preferredQuality}`);
  if(process.env.ROV_DESKTOP_SMOKE){
    setTimeout(async()=>{
      try {
        let result;
        let menuReady=false;
        for(let i=0;i<90;i++){
          menuReady=await window.webContents.executeJavaScript(`!!window.__menu?.ready`);
          if(menuReady)break;await new Promise(resolve=>setTimeout(resolve,1000));
        }
        if(!menuReady)throw Error('開場選單預覽未就緒');
        const testModel=process.env.ROV_DESKTOP_SMOKE_MODEL;
        if(modelIds.includes(testModel)){
          await window.webContents.executeJavaScript(`document.querySelector('[data-vehicle="${testModel}"]').click()`);
          for(let i=0;i<60;i++){
            if(await window.webContents.executeJavaScript(`!!window.__menu?.ready`))break;
            await new Promise(resolve=>setTimeout(resolve,1000));
          }
        }
        if(process.env.ROV_DESKTOP_SMOKE_EXPEDITION==='1'){
          await window.webContents.executeJavaScript(`(()=>{const mode=document.getElementById('menuMode'),scene=document.getElementById('menuScene');if(!mode||!scene)throw Error('探索模式選單不存在');mode.value='expedition';mode.dispatchEvent(new Event('change',{bubbles:true}));scene.value='coral_reef';scene.dispatchEvent(new Event('change',{bubbles:true}));})()`);
          for(let i=0;i<60;i++){if(await window.webContents.executeJavaScript(`!!window.__menu?.ready&&window.__menu.scene==='coral_reef'`))break;await new Promise(resolve=>setTimeout(resolve,1000));}
        }
        await window.webContents.executeJavaScript(`new Promise(resolve=>requestAnimationFrame(()=>requestAnimationFrame(resolve)))`);
        const menuCapture=await window.webContents.capturePage();fs.writeFileSync(`${process.env.ROV_DESKTOP_SMOKE}.menu.png`,menuCapture.toPNG());
        const navigation=new Promise(resolve=>window.webContents.once('did-finish-load',resolve));
        await window.webContents.executeJavaScript(`document.getElementById('menuIntro').checked=false;document.getElementById('launchForm').requestSubmit()`);
        await navigation;
        for(let i=0;i<120;i++){
          result=await window.webContents.executeJavaScript(`({title:document.title,modelLoaded:!!window.__modelLoaded,loadedModel:window.__loadedModelId,canvas:!!document.querySelector('canvas.gl'),state:!!window.__viewer?.S,model:window.__viewer?.S?.model_id,rotors:window.__viewer?.rotors?.length})`);
          if(result.modelLoaded&&result.state&&result.loadedModel===result.model)break;
          await new Promise(resolve=>setTimeout(resolve,1000));
        }
        result.menuReady=menuReady;
        result.savedModel=preferredModel;
        result.windowBounds=window.getBounds();result.displayWorkArea=workArea;
        // Exclude model compilation/startup from the displayed frame sample.
        await new Promise(resolve=>setTimeout(resolve,10000));
        result.renderQuality=await window.webContents.executeJavaScript(`window.__viewer?.performance?.()`);
        if(process.env.ROV_DESKTOP_SMOKE_EXPEDITION==='1'){
          for(let i=0;i<60;i++){if(await window.webContents.executeJavaScript(`window.__viewer?.S?.mission?.mode==='expedition'`))break;await new Promise(resolve=>setTimeout(resolve,100));}
          const collectionResult=await window.webContents.executeJavaScript(`(async()=>{
            if(!window.rovDesktop?.collection)throw Error('Desktop collection IPC unavailable');
            if(window.__viewer?.S?.mission?.mode!=='expedition')throw Error('Expedition mode not applied');
            const store=await import('./collection_store.js'),before=await store.listCollection();
            if(before.photos.length===0){
              window.__viewer.setCam('chase');
              if(typeof window.__viewer.takePhoto!=='function')throw Error('Game photo pipeline unavailable');
              await window.__viewer.takePhoto();
            }
            const after=await store.listCollection();
            if(after.photos.length!==1||after.guides.length!==0||after.photos[0].observation!==null)throw Error('Souvenir collection mismatch');
            const saved=await store.getPhotoBlob(after.photos[0].id);
            if(saved.size<100||after.photos[0].metadata.cameraMode!=='chase')throw Error('Original game photo missing');
            return {expedition:true,collectionBefore:before,collectionAfter:after,collectionOriginalBytes:saved.size};
          })()`);
          Object.assign(result,collectionResult,{httpPort:http,wsPort:ws});
        }
        fs.writeFileSync(process.env.ROV_DESKTOP_SMOKE,JSON.stringify(result));
        await window.webContents.executeJavaScript(`new Promise(resolve=>{window.__viewer?.setCam('orbit');requestAnimationFrame(()=>requestAnimationFrame(()=>setTimeout(resolve,200)));})`);
        const capture=await window.webContents.capturePage();fs.writeFileSync(`${process.env.ROV_DESKTOP_SMOKE}.png`,capture.toPNG());
        if(process.env.ROV_DESKTOP_SMOKE_EXPEDITION==='1'){
          await window.webContents.executeJavaScript(`document.getElementById('openCollection').click();document.querySelector('.collection-panel[open] [data-tab="photos"]').click()`);
          for(let i=0;i<30;i++){if(await window.webContents.executeJavaScript(`!!document.querySelector('.collection-panel[open] img')?.naturalWidth`))break;await new Promise(resolve=>setTimeout(resolve,200));}
          result.collectionPanel=await window.webContents.executeJavaScript(`({open:!!document.querySelector('.collection-panel[open]'),photos:document.querySelectorAll('.collection-panel[open] .collection-photo-button').length,imageLoaded:!!document.querySelector('.collection-panel[open] img')?.naturalWidth})`);
          const collectionCapture=await window.webContents.capturePage();fs.writeFileSync(`${process.env.ROV_DESKTOP_SMOKE}.collection.png`,collectionCapture.toPNG());
          fs.writeFileSync(process.env.ROV_DESKTOP_SMOKE,JSON.stringify(result));
        }
      } catch(error){fs.writeFileSync(process.env.ROV_DESKTOP_SMOKE,JSON.stringify({error:error.message}));}
      app.quit();
    },2000);
  }
}).catch(e=>{dialog.showErrorBox('ROV 模擬器',e.message);app.quit();});
app.on('before-quit',()=>{backend?.stdout?.unpipe(log);backend?.stderr?.unpipe(log);backend?.kill();log?.end();});
app.on('window-all-closed',()=>app.quit());
