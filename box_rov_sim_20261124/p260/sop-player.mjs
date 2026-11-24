import {CHAPTERS,DURATION,sampleSop,THUMBNAIL_TIMES} from './sop-timeline.mjs';
const $=id=>document.getElementById(id);
const focus=[
 ['看見 ROV-01 本體、雲台相機、雙 LED 與 UT 探頭','作業前檢查鏡頭是否清潔、六推進器與探頭是否正常；錄影、白平衡與補光設定需要在現場試拍確認。','來源：視頻採集表第 2–4、11–13 列；建模注意事項第 2–4 列'],
 ['先看分段，再跟著 ROV-01 接近','A 端、中段、B 端為模型幾何分段。這次完整示範中段三層採集，再移向 A 端的重點補拍區。','來源：視頻採集表第 5–7、9 列；建模注意事項第 4、7–8 列'],
 ['機頭持續面向船體，側移、減速、換層','三趟水平往返與兩次下降換層；青色線是示範路徑，不是已驗證的影像覆蓋。5 m、0.10 m/s 是 SOP 目標，動畫不當作實測回報。','來源：視頻採集表第 6–9、11 列；建模注意事項第 5–7 列'],
 ['從不同角度，把重點部位拍清楚','移向 A 端的開口與甲板設備，用不同觀察角度補拍。設備與生態沿用 05 的情境素材，不代表實船已確認的設施。','來源：視頻採集表第 10 列；建模注意事項第 8–9 列'],
 ['每層結束，回看原始畫面','下方縮圖由本次三維相機實際渲染。示範回看遮擋、亮暗與可辨識細節；重疊和畫質仍需用真實原片人工判讀，不自動宣告合格。','來源：建模注意事項第 7、9、11 列；視頻採集表第 8 列'],
 ['讓影片、日誌與備份有清楚的對應','用段號、層號和時間整理影片；另交接定位、姿態、深度與時間同步證據。檔名只是命名示例，這段動畫没有產生真實感測器日誌。','來源：視頻採集表第 14–18 列；建模注意事項第 10、12 列']
];
let scene=null,t=0,playing=false,rate=1,last=0,raf=0,lastChapter=-1,ready=false,recording=false,thumbs=[];
const fmt=s=>{const v=Math.max(0,Number(s)||0);return `${String(Math.floor(v/60)).padStart(2,'0')}:${String(Math.floor(v%60)).padStart(2,'0')}`;};
function targets(items){const host=$('step-visual');host.replaceChildren();for(const [value,label] of items){const el=document.createElement('div');el.className='target-item';const strong=document.createElement('strong');strong.textContent=value;const text=document.createElement('span');text.textContent=label;el.append(strong,text);host.append(el);}}
function chapterVisual(index){
  if(index===4){$('step-visual').replaceChildren();thumbs.forEach((url,i)=>{const fig=document.createElement('figure');fig.className='thumb';const img=document.createElement('img');img.src=url;img.alt=`中段第 ${i+1} 層的模擬相機影像`;const cap=document.createElement('figcaption');cap.textContent=`第 ${i+1} 層 · ${fmt(THUMBNAIL_TIMES[i])} · 演示影像`;fig.append(img,cap);if(i===0){const note=document.createElement('small');note.textContent='圈選肋骨後方：換角度補拍（示例）';note.style.cssText='display:block;font-size:9px;color:#e4c987';fig.style.position='relative';const ring=document.createElement('span');ring.setAttribute('aria-hidden','true');ring.style.cssText='position:absolute;left:43%;top:21%;width:26%;height:34%;border:2px dashed #e4c987;border-radius:50%;pointer-events:none';fig.append(ring,note);}$('step-visual').append(fig);});return;}
  if(index===5){const list=document.createElement('ul');list.className='file-list';for(const name of ['MID_L01_YYYYMMDD_HHMMSS.mp4','MID_L02_YYYYMMDD_HHMMSS.mp4','MID_L03_YYYYMMDD_HHMMSS.mp4','pose_log.csv / depth_log.csv','原始資料備份 A ／ 備份 B']){const li=document.createElement('li');li.textContent=name;const tag=document.createElement('small');tag.textContent='交接示例';li.append(tag);list.append(li);}$('step-visual').replaceChildren(list);return;}
  const data=[[['1080p60','原始錄影目標'],['自動','白平衡草案'],['試拍確認','清晰度與補光']],[['A → 中 → B','幾何採集分段'],['5 m','草案距離目標'],['中段','本次完整示範區']],[['3 趟 / 2 次','水平掃描 / 下降換層'],['80% / 70%','前向 / 側向示例假設'],['面向船體','保持鏡頭朝向']],[['開口','不同角度補拍'],['甲板設備','沿用 05 情境素材'],['人工判讀','確認仍有無遮擋']]];
  targets(data[index]);
}
function paint(){if(!scene)return;const state=sampleSop(t);scene.render(state);$('time').value=t;$('elapsed').textContent=fmt(t);$('camera-time').textContent=`${fmt(t)}.${Math.floor((Math.max(0,t)%1)*10)}`;$('phase').textContent=state.phase;
  $('external-mode').textContent=state.segment;
  const utEl=$('camera-ut-readout');if(utEl){if(t>=24&&t<=90){utEl.textContent='UT DIST: 0.42m | TILT: 1.4° [COUPLED]';utEl.style.color='#10B981';utEl.style.borderColor='rgba(16,185,129,0.55)';}else if(t>=16&&t<24){utEl.textContent='UT DIST: 0.68m | TILT: 3.8° [ALIGNING >3°]';utEl.style.color='#F59E0B';utEl.style.borderColor='rgba(245,158,11,0.55)';}else{utEl.textContent='UT DIST: 1.85m | TILT: 0.9° [STANDBY]';utEl.style.color='#22D3EE';utEl.style.borderColor='rgba(34,211,238,0.40)';}}
  if(lastChapter!==state.chapterIndex){lastChapter=state.chapterIndex;const c=state.chapter;const f=focus[lastChapter];$('chapter-number').textContent=`SOP ${String(lastChapter+1).padStart(2,'0')} / 06 · ROV-01 CAPTURE`;$('chapter-title').textContent=c.title;$('chapter-caption').textContent=c.caption;$('step-focus').textContent=f[0];$('step-description').textContent=f[1];$('source-ref').textContent=f[2];document.querySelectorAll('#chapters button').forEach((el,i)=>{if(i===lastChapter)el.setAttribute('aria-current','step');else el.removeAttribute('aria-current');});chapterVisual(lastChapter);}
}
function pause(){playing=false;cancelAnimationFrame(raf);$('play').textContent=t>=DURATION?'↺ 再看一次':'▶ 播放 SOP';$('play').setAttribute('aria-pressed','false');}
function tick(now){if(!playing)return;const delta=Math.max(0,Math.min((now-last)/1000,.15));last=now;t=Math.min(DURATION,t+delta*rate);paint();if(t>=DURATION){pause();return;}raf=requestAnimationFrame(tick);}
function play(){if(!ready||recording)return;if(t>=DURATION)t=0;playing=true;last=performance.now();$('play').textContent='Ⅱ 暫停';$('play').setAttribute('aria-pressed','true');raf=requestAnimationFrame(tick);}
function seek(time){pause();t=Math.max(0,Math.min(DURATION,Number(time)||0));paint();}
for(const [i,c] of CHAPTERS.entries()){const b=document.createElement('button');b.disabled=true;b.innerHTML=`<span>STEP ${String(i+1).padStart(2,'0')} · ${fmt(c.start)}</span><strong></strong>`;b.querySelector('strong').textContent=c.title;b.addEventListener('click',()=>{if(recording)return;const resume=playing;seek(c.start);if(resume)play();});$('chapters').append(b);}
$('play').addEventListener('click',()=>playing?pause():play());$('restart').addEventListener('click',()=>{if(recording)return;seek(0);play();});$('time').addEventListener('input',()=>{if(!recording)seek($('time').value);});$('rate').addEventListener('change',()=>rate=Number($('rate').value));document.addEventListener('visibilitychange',()=>{if(document.hidden&&!recording)pause();});
async function init(){
  pause();ready=false;$('loading').hidden=false;$('retry').hidden=true;document.querySelector('#loading strong').textContent='正在準備 ROV-01 與雙視角場景';document.querySelector('#loading span').textContent='首次載入需準備模型、材質與光影，請稍候。';scene?.dispose();scene=null;
  try{const {createSopScene}=await import('./sop-scene.mjs');scene=await createSopScene($('external-view'),$('camera-view'),{onStatus:()=>{}});thumbs=[];for(const time of THUMBNAIL_TIMES){scene.render(sampleSop(time));thumbs.push(scene.capture());}t=0;lastChapter=-1;paint();ready=true;$('loading').hidden=true;for(const el of document.querySelectorAll('#play,#restart,#time,#chapters button'))el.disabled=false;if(!matchMedia('(prefers-reduced-motion: reduce)').matches)play();}
  catch(e){document.querySelector('#loading strong').textContent='場景未能載入';document.querySelector('#loading span').textContent='請重新載入；也可以先查看採集規劃或 SOP 對照文件。';$('retry').hidden=false;console.error(e);}
}
$('retry').addEventListener('click',init);
function fitImage(ctx,canvas,x,y,w,h){const scale=Math.min(w/canvas.width,h/canvas.height),dw=canvas.width*scale,dh=canvas.height*scale;ctx.drawImage(canvas,x+(w-dw)/2,y+(h-dh)/2,dw,dh);}
async function recordPreview({start=12,end=60,multiplier=2,previewMultiplier=multiplier}={}){
  if(!ready||recording)throw Error('Scene not ready or recording active');pause();recording=true;
  const canvas=document.createElement('canvas');canvas.width=1280;canvas.height=720;const ctx=canvas.getContext('2d');
  const stream=canvas.captureStream(24),mime=['video/webm;codecs=vp8','video/webm;codecs=vp9','video/webm'].find(m=>MediaRecorder.isTypeSupported(m));
  const recorder=new MediaRecorder(stream,{mimeType:mime,videoBitsPerSecond:6000000}),chunks=[];
  const stopped=new Promise((resolve,reject)=>{recorder.ondataavailable=e=>{if(e.data.size)chunks.push(e.data);};recorder.onstop=()=>resolve(new Blob(chunks,{type:mime}));recorder.onerror=reject;});
  let begin=0;
  function frame(now){if(!begin)begin=now;t=Math.min(end,start+(now-begin)/1000*multiplier);paint();const state=sampleSop(t);ctx.fillStyle='#0a222d';ctx.fillRect(0,0,1280,720);ctx.fillStyle='#e0efea';ctx.font='26px Microsoft JhengHei';ctx.fillText(`ROV-01 採集 SOP / ${state.chapter.title}`,22,40);ctx.fillStyle='#83cdbf';ctx.font='16px Microsoft JhengHei';ctx.fillText('ROV-01 作業視角',22,79);ctx.fillText('ROV-01 相機視角 · 同步',654,79);fitImage(ctx,document.querySelector('#external-view canvas'),16,96,616,506);fitImage(ctx,document.querySelector('#camera-view canvas'),648,96,616,506);ctx.fillStyle='#b8d6d2';ctx.font='23px Microsoft JhengHei';ctx.fillText(state.phase,22,639);ctx.font='15px Microsoft JhengHei';ctx.fillText(`演示時間 ${fmt(t)} · ${previewMultiplier}× 預覽 · 模型未實測定標`,22,678);if(t<end)requestAnimationFrame(frame);else recorder.stop();}
  recorder.start();requestAnimationFrame(frame);
  try{const blob=await stopped;const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='ROV01_SOP_short_preview.webm';a.click();setTimeout(()=>URL.revokeObjectURL(url),3000);return {bytes:blob.size,mime,start,end,multiplier};}finally{recording=false;stream.getTracks().forEach(track=>track.stop());pause();}
}
window.sopDemo={get ready(){return ready;},get state(){return {...sampleSop(t),playing,rate,recording};},seek,play,pause,inspect:()=>scene?.inspect(),recordPreview,get thumbnails(){return [...thumbs];}};
init();
