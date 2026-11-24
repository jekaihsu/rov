// Adjust only pixel workload; physics, controls and canvas CSS size stay fixed.
const profiles=new WeakMap();
const positive=value=>Number.isFinite(Number(value))&&Number(value)>0?Number(value):null;
const clean=value=>typeof value==='string'?value.replace(/[\u0000-\u001f]/g,' ').trim().slice(0,256):'';

// These are conservative starting hints, not benchmark scores. Browser memory
// is coarse and may be privacy-rounded; it never downgrades a discrete GPU.
export function chooseHardwareProfile(hints={}){
  const renderer=clean(hints.renderer),vendor=clean(hints.vendor),name=`${renderer} ${vendor}`;
  const logicalCores=positive(hints.hardwareConcurrency),memoryGB=positive(hints.deviceMemory);
  let tier='unknown',entryLevel=false,label='未辨識的繪圖裝置',initialRatio=1,floor=.6,ceiling=1,pixelBudget=2560*1440;
  let reason='瀏覽器未提供可辨識的 GPU 資訊；依實際 FPS 自動調整。';
  if(/swiftshader|llvmpipe|softpipe|software raster|microsoft basic render|swrast|\bwarp\b|gdi generic/i.test(name)){
    tier='software';label='軟體繪圖';initialRatio=.6;floor=.5;ceiling=.75;pixelBudget=1280*720;
    reason='目前 WebGL 使用軟體繪圖；先降低像素負載，再依實際 FPS 調整。';
  }else if(/\b(?:geforce|nvidia|quadro|rtx|gtx)\b|radeon(?:\s*\(tm\))?\s+(?:rx\b|pro\b|r[579]\b)|intel.*\barc\s+a\d{3}\b/i.test(name)){
    tier='discrete';label='獨立顯示晶片';
    entryLevel=/\bmx\s*[1-4]\d{2}\b/i.test(name);
    if(entryLevel){label='入門獨立顯示晶片';initialRatio=.85;pixelBudget=1920*1080;}
    reason=entryLevel?'偵測到 GeForce MX 系列；先採較低解析度，依實際 FPS 回升或下降。':'偵測到獨立顯示晶片；由原生解析度開始，仍以實際 FPS 為準。';
  }else if(/intel|\biris\b|\buhd\b|\bhd graphics\b|radeon.*(?:graphics|vega)|apple.*(?:gpu|m\d)|\bmali\b|\badreno\b|powervr/i.test(name)){
    tier='integrated';label='整合式／行動顯示晶片';initialRatio=.85;ceiling=.9;pixelBudget=1920*1080;
    reason='偵測到整合式或行動 GPU；先降低像素負載，依實際 FPS 調整。';
    if((logicalCores!==null&&logicalCores<=2)||(memoryGB!==null&&memoryGB<=2)){initialRatio=.75;reason+=' 瀏覽器回報資源較少，採保守起始值。';}
  }
  return {tier,entryLevel,label,reason,renderer,vendor,logicalCores,memoryGB,initialRatio,floor,ceiling,pixelBudget};
}

export function detectHardware(renderer){
  let gpu='',vendor='';
  try{
    const gl=renderer.getContext(),extension=gl.getExtension('WEBGL_debug_renderer_info');
    gpu=gl.getParameter(extension?extension.UNMASKED_RENDERER_WEBGL:gl.RENDERER)||'';
    vendor=gl.getParameter(extension?extension.UNMASKED_VENDOR_WEBGL:gl.VENDOR)||'';
  }catch{/* Privacy controls/context loss can hide GPU details. */}
  const navigator=globalThis.navigator;
  return chooseHardwareProfile({renderer:gpu,vendor,hardwareConcurrency:navigator?.hardwareConcurrency,deviceMemory:navigator?.deviceMemory});
}

function bounds(renderer,hardware){
  const canvas=renderer.domElement;
  let width=canvas?.clientWidth,height=canvas?.clientHeight;
  // Before the first resize, a new canvas still has its default 300x150 size.
  if(!width||!height||(width===300&&height===150)){width=globalThis.innerWidth||1280;height=globalThis.innerHeight||720;}
  const dpr=positive(globalThis.devicePixelRatio)||1;
  const ceiling=Math.min(dpr,hardware.ceiling,Math.sqrt(hardware.pixelBudget/(width*height)));
  return {ceiling,floor:Math.min(ceiling,hardware.floor)};
}
export function configureRenderQuality(renderer,mode='auto'){
  if(!['auto','performance','medium','high'].includes(mode))mode='auto';
  const hardware=detectHardware(renderer),dpr=positive(globalThis.devicePixelRatio)||1;
  const limits=mode==='auto'?bounds(renderer,hardware):{ceiling:Math.min(dpr,mode==='high'?2:1),floor:Math.min(dpr,.6)};
  const ratio=mode==='auto'?Math.min(limits.ceiling,hardware.initialRatio):mode==='performance'?Math.min(dpr,.75):limits.ceiling;
  const state={mode,...limits,hardware,ratio,elapsed:0,frames:0,stable:0,warmup:3};
  profiles.set(renderer,state);renderer.shadowMap.enabled=mode==='high';renderer.setPixelRatio(ratio);
  return state;
}
export function updateRenderQuality(renderer,seconds,{suspended=false}={}){
  const s=profiles.get(renderer);if(!s||s.mode!=='auto')return;
  if(suspended||globalThis.document?.hidden||!Number.isFinite(seconds)||seconds<=0){s.elapsed=0;s.frames=0;s.stable=0;return;}
  // Sustained 1–2 FPS must still trigger downscaling. Bound a long sample so a
  // single window-resume stall cannot consume the whole adaptation interval.
  seconds=Math.min(seconds,.5);
  if(s.warmup>0){s.warmup-=seconds;return;}
  s.elapsed+=seconds;s.frames++;
  if(s.elapsed<1.5)return;
  Object.assign(s,bounds(renderer,s.hardware));
  const fps=s.frames/s.elapsed;let next=Math.max(s.floor,Math.min(s.ceiling,s.ratio));
  if(fps<50){next=Math.max(s.floor,s.ratio-.1);s.stable=0;}
  else if(fps>58){s.stable+=s.elapsed;if(s.stable>=8){next=Math.min(s.ceiling,s.ratio+.05);s.stable=0;}}
  else s.stable=0;
  s.elapsed=0;s.frames=0;
  next=Math.max(s.floor,Math.min(s.ceiling,next));
  if(Math.abs(next-s.ratio)>.001){s.ratio=next;renderer.setPixelRatio(next);}
}
export function renderQualityInfo(renderer){
  const s=profiles.get(renderer);return s?{mode:s.mode,scale:Math.round(s.ratio*100),drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,
    hardwareLabel:s.hardware.label,hardwareReason:s.hardware.reason,hardwareTier:s.hardware.tier,hardwareRenderer:s.hardware.renderer,
    hardwareProfile:{initialRatio:s.hardware.initialRatio,floor:s.floor,ceiling:s.ceiling,pixelBudget:s.hardware.pixelBudget,entryLevel:s.hardware.entryLevel}}:null;
}
