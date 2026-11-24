const {app,BrowserWindow,dialog,ipcMain,screen,shell}=require('electron');
const {spawn}=require('node:child_process');
const net=require('node:net');
const fs=require('node:fs');
const path=require('node:path');
const {CollectionStore}=require('./collection_store.cjs');
const {SaveFiles, writeSyncAtomic}=require('./save_files.cjs');
if(process.env.ROV_DESKTOP_SMOKE&&process.env.ROV_DESKTOP_SMOKE_EXPEDITION==='1'&&!process.env.ROV_DESKTOP_SMOKE_DATA)throw Error('探索收藏驗收需要獨立的 ROV_DESKTOP_SMOKE_DATA 目錄');
if(process.env.ROV_DESKTOP_SMOKE&&process.env.ROV_DESKTOP_SMOKE_DATA){
  if(!path.isAbsolute(process.env.ROV_DESKTOP_SMOKE_DATA))throw Error('ROV_DESKTOP_SMOKE_DATA 必須是絕對路徑');
  fs.mkdirSync(process.env.ROV_DESKTOP_SMOKE_DATA,{recursive:true});app.setPath('userData',process.env.ROV_DESKTOP_SMOKE_DATA);
}
const { createSteam } = require('./steam_service.cjs');
const { installBackendLifecycle } = require('./backend_lifecycle.cjs');
const displaySettings = require('./window_settings.cjs');
const { requestDiscreteGpu } = require('./gpu_preference.cjs');
requestDiscreteGpu(app);
if (!app.requestSingleInstanceLock()) app.exit(0);
app.on('second-instance', () => {
  const existing = BrowserWindow.getAllWindows()[0];
  existing?.restore();
  existing?.focus();
});
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
  displaySettings.snapshot(data);
  const steam = createSteam(data);
  const preferencesPath=path.join(data,'preferences.json');
  const saveFiles=new SaveFiles(path.join(data,'saves'));
  const modelIds=['x1','bluerov2_heavy','falcon'];
  let preferredModel='x1';
  let inputPreferences = {};
  const qualityModes=['auto','performance','medium','high'];let preferredQuality='auto';
  try{const saved=JSON.parse(fs.readFileSync(preferencesPath,'utf8'));inputPreferences=saved.input || {};if(modelIds.includes(saved.model))preferredModel=saved.model;if(qualityModes.includes(saved.quality))preferredQuality=saved.quality;}catch{}
  const savePreferences=()=>writeSyncAtomic(preferencesPath,JSON.stringify({model:preferredModel,quality:preferredQuality,input:inputPreferences}));
  const cache=path.join(data,'numba-cache');fs.mkdirSync(cache,{recursive:true});
  log=fs.createWriteStream(path.join(data,'backend.log'),{flags:'a'});
  backend=spawn(executable,app.isPackaged?args:['-X','utf8','-m','qysim.server',...args],{cwd:root,windowsHide:true,env:{...process.env,PYTHONUTF8:'1',NUMBA_CACHE_DIR:cache}});
  backend.stdout.pipe(log,{end:false});backend.stderr.pipe(log,{end:false});
  async function backendFailed(error) {
    const result = await dialog.showMessageBox({ type: 'error', title: 'ROV Simulator',
      message: '模擬服務已停止', detail: `${error}\n${path.join(data, 'backend.log')}`,
      buttons: ['重試', '結束'] });
    if (result.response === 0) app.relaunch();
    app.quit();
  }
  const lifecycle = installBackendLifecycle(app, backend, backendFailed);
  const workArea=screen.getPrimaryDisplay().workAreaSize;
  const window=new BrowserWindow({width:Math.min(1440,workArea.width),height:Math.min(900,workArea.height),minWidth:Math.min(900,workArea.width),minHeight:Math.min(600,workArea.height),show:!process.env.ROV_DESKTOP_SMOKE,backgroundColor:'#081722',autoHideMenuBar:true,webPreferences:{nodeIntegration:false,contextIsolation:true,sandbox:true,backgroundThrottling:!process.env.ROV_DESKTOP_SMOKE,preload:path.join(__dirname,'preload.cjs')}});
  lifecycle.watchWindow(window);
  const origin = `http://127.0.0.1:${http}`;
  function trusted(event) {
    return event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame &&
      event.senderFrame.url.startsWith(origin + '/');
  }
  ipcMain.handle('rov:steam', (event, method, payload) => {
    if (!trusted(event)) throw Error('Untrusted sender');
    if (method === 'status') return steam.status();
    if (method === 'event') return steam.report(payload?.event, payload?.value);
    throw Error('Unknown Steam method');
  });
  const windowFile = path.join(data, 'window.json');
  let savedWindow = null;
  try {
    savedWindow = JSON.parse(fs.readFileSync(windowFile, 'utf8'));
  } catch {
    savedWindow = null;
  }
  ipcMain.handle('rov:display', (event, value) => {
    if (!trusted(event)) throw Error('Untrusted sender');
    const displays = displaySettings.listDisplays(screen);
    if (!value) {
      return {
        displays,
        current: displaySettings.readCurrent(window, displays, savedWindow),
      };
    }
    const saved = displaySettings.apply(window, screen.getAllDisplays(), value);
    savedWindow = saved;
    writeSyncAtomic(windowFile, JSON.stringify(saved));
    return saved;
  });
  try {
    if (savedWindow) {
      displaySettings.apply(window, screen.getAllDisplays(), savedWindow);
    } else {
      throw Error('no saved window');
    }
  } catch {
    if (steam.status().deck || process.env.ROV_STEAM_DECK === '1') {
      window.setSize(1280, 800);
      window.setFullScreen(true);
      preferredQuality = 'performance';
      window.webContents.setZoomFactor(1);
    }
  }
  window.webContents.on('before-input-event', (event, input) => {
    if (input.type === 'keyDown' && input.alt && input.key === 'Enter') {
      event.preventDefault();
      const bounds = window.getBounds();
      const value = { mode: window.isFullScreen() ? 'windowed' : 'fullscreen',
        display: screen.getDisplayMatching(bounds).id, width: bounds.width, height: bounds.height };
      displaySettings.apply(window, screen.getAllDisplays(), value);
      savedWindow = value;
      writeSyncAtomic(windowFile, JSON.stringify(value));
    }
  });
  window.webContents.setWindowOpenHandler(() => ({ action: 'deny' }));
  window.webContents.on('will-navigate', (event, url) => {
    if (!url.startsWith(origin + '/')) event.preventDefault();
  });
  const viewerRoot = app.isPackaged ? path.join(root, 'rov-sim', '_internal', 'viewer') :
    path.join(root, 'viewer');
  const inlineHashes = [];
  for (const filename of ['index.html', 'model-preview.html']) {
    const html = fs.readFileSync(path.join(viewerRoot, filename), 'utf8');
    for (const match of html.matchAll(/<script\b(?![^>]*\bsrc=)[^>]*>([\s\S]*?)<\/script>/g)) {
      const hash = require('node:crypto').createHash('sha256').update(match[1]).digest('base64');
      inlineHashes.push(`'sha256-${hash}'`);
    }
  }
  // ROV_DESKTOP_BENCH=1 drops CSP so Playwright CDP can page.evaluate during GPU benches.
  // Shipping builds never set that variable; the strict policy below remains the default.
  if (!process.env.ROV_DESKTOP_BENCH) {
    window.webContents.session.webRequest.onHeadersReceived((details, callback) => {
      if (!details.url.startsWith(origin + '/')) return callback({});
      callback({ responseHeaders: { ...details.responseHeaders, 'Content-Security-Policy': [
        `default-src 'self'; script-src 'self' ${inlineHashes.join(' ')}; style-src 'self' 'unsafe-inline'; ` +
        "img-src 'self' data: blob:; connect-src 'self' ws: wss: https:; " +
        "worker-src 'self' blob:; object-src 'none'; base-uri 'none'; frame-src 'none'"
      ] } });
    });
  }
  const collection=new CollectionStore(path.join(data,'collection'));
  ipcMain.handle('rov:collection',async(event,method,payload)=>{
    let allowed=false;try{allowed=event.sender===window.webContents&&event.senderFrame===window.webContents.mainFrame&&new URL(event.senderFrame.url).origin===`http://127.0.0.1:${http}`;}catch{}
    if(!allowed||!['list','readPhoto','savePhoto','saveResult','setCover','export','import'].includes(method))return {ok:false,error:'此頁面無法存取本機收藏'};
    try{return {ok:true,value:await collection[method](payload)};}catch(error){return {ok:false,error:error.message||'收藏儲存失敗'};}
  });
  function savesTrusted(event) {
    return event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame &&
      event.senderFrame.url.startsWith(origin + '/');
  }
  ipcMain.handle('rov:saves-read-all', async (event) => {
    if (!savesTrusted(event)) return {};
    try {
      return await saveFiles.readAll();
    } catch (error) {
      log.write(`Could not read saves: ${error.message}\n`);
      return {};
    }
  });
  ipcMain.handle('rov:saves-write', async (event, key, text) => {
    if (!savesTrusted(event)) return { ok: false };
    try {
      await saveFiles.write(key, text);
      return { ok: true };
    } catch (error) {
      log.write(`Could not write save ${key}: ${error.message}\n`);
      return { ok: false, error: error.message };
    }
  });
  ipcMain.handle('rov:saves-backup', async (event, key, text) => {
    if (!savesTrusted(event)) return { ok: false };
    try {
      const destination = await saveFiles.backup(key, text);
      return { ok: true, path: destination };
    } catch (error) {
      log.write(`Could not backup save ${key}: ${error.message}\n`);
      return { ok: false, error: error.message };
    }
  });
  ipcMain.handle('rov:input-read', event => {
    if (event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame) return {};
    return inputPreferences;
  });
  ipcMain.on('rov:input-selected', (event, settings) => {
    if (event.sender !== window.webContents || event.senderFrame !== window.webContents.mainFrame) return;
    if (!settings || typeof settings !== 'object' || JSON.stringify(settings).length > 262144) return;
    try {
      inputPreferences = settings;
      savePreferences();
    } catch (error) {
      log.write(`Could not save input preference: ${error.message}\n`);
    }
  });
  ipcMain.on('rov:model-selected',(event,model)=>{
    if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!event.senderFrame.url.startsWith(`http://127.0.0.1:${http}/`)||!modelIds.includes(model)||model===preferredModel)return;
    try{preferredModel=model;savePreferences();}catch(error){log.write(`Could not save model preference: ${error.message}\n`);}
  });
  ipcMain.on('rov:quality-selected',(event,quality)=>{
    if(event.sender!==window.webContents||event.senderFrame!==window.webContents.mainFrame||!event.senderFrame.url.startsWith(`http://127.0.0.1:${http}/`)||!qualityModes.includes(quality))return;
    try{preferredQuality=quality;savePreferences();}catch(error){log.write(`Could not save quality preference: ${error.message}\n`);}
  });
  const reportsRoot = path.join(data, 'reports');
  fs.mkdirSync(reportsRoot, { recursive: true });
  function reportTrusted(event) {
    return event.sender === window.webContents && event.senderFrame === window.webContents.mainFrame &&
      event.senderFrame.url.startsWith(origin + '/');
  }
  ipcMain.handle('rov:report-save', (event, payload) => {
    // error codes are translated in viewer/feedback/save.js — keep them language-neutral here.
    if (!reportTrusted(event)) return { ok: false, code: 'untrusted' };
    const stamp = String(payload?.stamp || '').replace(/[^0-9A-Za-zT_-]/g, '').slice(0, 40);
    if (!stamp) return { ok: false, code: 'invalid_stamp' };
    const json = typeof payload?.json === 'string' ? payload.json : '';
    if (!json || json.length > 2_000_000) return { ok: false, code: 'payload_too_large' };
    try {
      const folder = path.join(reportsRoot, stamp);
      fs.mkdirSync(folder, { recursive: true });
      fs.writeFileSync(path.join(folder, 'report.json'), json, 'utf8');
      const pngBase64 = typeof payload?.pngBase64 === 'string' ? payload.pngBase64 : '';
      if (pngBase64) {
        if (pngBase64.length > 12_000_000) return { ok: false, code: 'screenshot_too_large' };
        fs.writeFileSync(path.join(folder, 'screenshot.png'), Buffer.from(pngBase64, 'base64'));
      }
      return { ok: true, path: folder };
    } catch {
      return { ok: false, code: 'save_failed' };
    }
  });
  ipcMain.handle('rov:report-open', async (event) => {
    if (!reportTrusted(event)) return { ok: false, code: 'untrusted' };
    try {
      fs.mkdirSync(reportsRoot, { recursive: true });
      const error = await shell.openPath(reportsRoot);
      if (error) return { ok: false, code: 'open_failed' };
      return { ok: true, path: reportsRoot };
    } catch {
      return { ok: false, code: 'open_failed' };
    }
  });
  await window.loadURL('data:text/html;charset=utf-8,'+encodeURIComponent('<html lang="zh-Hant"><meta charset="utf-8"><body style="margin:0;background:#081722;color:#dce8ea;font:18px system-ui;display:grid;place-content:center;height:100vh"><h1>ROV Simulator</h1><p>正在準備模擬環境，首次啟動可能需要一點時間。</p></body></html>'));
  try { await waitReady(http); } catch (error) { await lifecycle.fail(error.message); return; }
  // The launch menu decides the cinematic per dive (下水動畫 setting and the briefing switch); a ?nointro here would
  // turn it, and the pre-dive procedure, off for every desktop dive.
  await window.loadURL(`http://127.0.0.1:${http}/?ws=${encodeURIComponent(`ws://127.0.0.1:${ws}`)}&model=${preferredModel}&quality=${preferredQuality}`);
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
          await window.webContents.executeJavaScript(`(()=>{if(!window.__menu?.configure)throw Error('探索模式選單不存在');window.__menu.configure({mission:'expedition',scenario:'coral_reef'});})()`);
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
