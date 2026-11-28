// Adjust only pixel workload; physics, controls and canvas CSS size stay fixed.
const profiles=new WeakMap();
let lastMode=null;
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
  // The minimum-spec class: Intel HD / UHD Graphics (Gen9-era, e.g. UHD 620 in a 15 W i5-8250U laptop, where Chrome
  // renders even when a GeForce MX110 is present) and GeForce MX1xx. They cannot hold the underwater optics at 60 fps
  // even at a reduced scale: automatic quality starts them on the low look and low scene rather than discovering it
  // after seconds of stutter and a full shader rebuild (docs/design/performance/). Iris Xe, Radeon and Apple
  // integrated GPUs keep the optics and adapt by measured frame rate.
  const lowIntel = /intel/i.test(name) && /\bu?hd\b/i.test(name) && !/\biris\b|\barc\b/i.test(name);
  const startsLow = tier !== 'software' && (lowIntel || /\bmx\s*1\d{2}\b/i.test(name));
  return {tier,entryLevel,label,reason,renderer,vendor,logicalCores,memoryGB,initialRatio,floor,ceiling,pixelBudget,
    startsLow};
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
// Automatic quality ladder, judged on the measured frame rate in 1.5 s windows (after a 3 s warm-up):
// 1. below SLOW_FPS the render scale drops by SCALE_STEP per window down to the floor (dynamic resolution);
// 2. only when it is already at the floor and still below SLOW_FPS for SUPPRESS_WINDOWS windows are the
//    underwater screen effects dropped (the legacy look, which recompiles every material once);
// 3. above FAST_FPS for 8 s the scale climbs back by RAISE_STEP up to the ceiling (effects stay off this session).
// Resolution goes first because it costs the least to look at and is undone smoothly.
const SLOW_FPS = 50;
const FAST_FPS = 58;
const SCALE_STEP = .1;
const RAISE_STEP = .05;
const SUPPRESS_WINDOWS = 2;
// What automatic quality learned on this GPU in an earlier dive: the next dive starts there instead of starting
// high, stuttering for several seconds and stepping down again (first launch still starts from the hints above).
const LEARNED_KEY = 'rov.quality.learned.v1';
let learnedApplied = false;

function readLearned(hardware) {
  // Inline parse so this file stays free of relative imports (data-URL unit tests).
  try {
    const raw = globalThis.localStorage?.getItem(LEARNED_KEY);
    if (!raw) return null;
    if (raw.length > 8192) {
      try {
        globalThis.localStorage?.setItem(LEARNED_KEY + '.corrupt', raw.slice(0, 8192));
      } catch {
        /* ignore */
      }
      return null;
    }
    const value = JSON.parse(raw);
    if (!value || typeof value !== 'object' || value.renderer !== hardware.renderer) return null;
    if (!Number.isFinite(value.ratio)) return null;
    return {
      renderer: value.renderer,
      ratio: value.ratio,
      effectsSuppressed: !!value.effectsSuppressed,
      version: 1,
    };
  } catch {
    try {
      const raw = globalThis.localStorage?.getItem(LEARNED_KEY);
      if (raw) globalThis.localStorage?.setItem(LEARNED_KEY + '.corrupt', raw.slice(0, 8192));
    } catch {
      /* ignore */
    }
    return null;
  }
}

function writeLearned(state) {
  if (!state.learn) return;
  const value = {
    version: 1,
    renderer: state.hardware.renderer,
    ratio: state.ratio,
    effectsSuppressed: state.effectsSuppressed,
  };
  try {
    globalThis.localStorage?.setItem(LEARNED_KEY, JSON.stringify(value));
  } catch {
    /* Private browsing: start from the hints next time. */
  }
}

// learn: the game view (not the menu backdrop) remembers what automatic quality settled on for this GPU and the
// first such call in a page starts from it.
export function configureRenderQuality(renderer,mode='auto',{learn=false}={}){
  const requested = new URLSearchParams(globalThis.location?.search || '').get('quality');
  if (!mode && ['low', 'ultra'].includes(requested)) mode = requested;
  if(!['auto','performance','low','medium','high','ultra'].includes(mode))mode='auto';
  const safe = new URLSearchParams(globalThis.location?.search).has('safe');
  if (safe) mode = 'low';
  const hardware=detectHardware(renderer),dpr=positive(globalThis.devicePixelRatio)||1;
  const limits=mode==='auto'?bounds(renderer,hardware):{ceiling:Math.min(dpr,['high','ultra'].includes(mode)?2:1),floor:Math.min(dpr,.6)};
  let ratio = limits.ceiling;
  if (mode === 'auto') ratio = Math.min(limits.ceiling, hardware.initialRatio);
  else if (['performance', 'low'].includes(mode)) ratio = Math.min(dpr, .75);
  // Automatic quality on software GL, integrated and entry-level GPUs starts without the underwater screen effects
  // (optics); software GL has no frame budget for them, the others lose 60 fps (see startsLow).
  let effectsSuppressed = safe || mode === 'auto' && (hardware.tier === 'software' || hardware.startsLow);
  const learned = mode === 'auto' && learn && !learnedApplied ? readLearned(hardware) : null;
  if (learn) learnedApplied = true;
  if (learned) {
    ratio = Math.max(limits.floor, Math.min(limits.ceiling, learned.ratio));
    effectsSuppressed = effectsSuppressed || learned.effectsSuppressed === true;
  }
  const state = {mode, ...limits, hardware, ratio, elapsed: 0, frames: 0, stable: 0, warmup: 3, effectsSuppressed,
    slowAtFloor: 0, learn};
  lastMode=mode;
  profiles.set(renderer,state);renderer.shadowMap.enabled=['medium','high','ultra'].includes(mode);renderer.setPixelRatio(ratio);
  return state;
}

function nextRatio(s, fps) {
  if (fps < SLOW_FPS) {
    s.stable = 0;
    if (s.ratio > s.floor + .001) {
      s.slowAtFloor = 0;
      return s.ratio - SCALE_STEP;
    }
    s.slowAtFloor++;
    if (!s.effectsSuppressed && s.slowAtFloor >= SUPPRESS_WINDOWS) {
      s.effectsSuppressed = true;
      s.slowAtFloor = 0;
      writeLearned(s);
    }
    return s.ratio;
  }
  s.slowAtFloor = 0;
  if (fps <= FAST_FPS) {
    s.stable = 0;
    return s.ratio;
  }
  s.stable += s.elapsed;
  if (s.stable < 8) return s.ratio;
  s.stable = 0;
  return s.ratio + RAISE_STEP;
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
  const applied=s.ratio;
  // The viewport (and so the pixel budget) may have changed: judge from the clamped scale.
  s.ratio=Math.max(s.floor,Math.min(s.ceiling,s.ratio));
  const fps=s.frames/s.elapsed;
  const next=Math.max(s.floor,Math.min(s.ceiling,nextRatio(s,fps)));
  s.ratio=applied;
  s.elapsed=0;s.frames=0;
  if(Math.abs(next-s.ratio)>.001){s.ratio=next;renderer.setPixelRatio(next);writeLearned(s);}
}
export function renderQualityInfo(renderer){
  const s=profiles.get(renderer);return s?{mode:s.mode,effectsSuppressed:s.effectsSuppressed,scale:Math.round(s.ratio*100),drawCalls:renderer.info.render.calls,triangles:renderer.info.render.triangles,
    hardwareLabel:s.hardware.label,hardwareReason:s.hardware.reason,hardwareTier:s.hardware.tier,hardwareRenderer:s.hardware.renderer,
    hardwareProfile:{initialRatio:s.hardware.initialRatio,floor:s.floor,ceiling:s.ceiling,pixelBudget:s.hardware.pixelBudget,entryLevel:s.hardware.entryLevel}}:null;
}

// Internal scene consumers avoid allocating a diagnostic object for every frame.
export function renderQualityState(renderer) {
  return profiles.get(renderer);
}

// Texture tier for large assets (e.g. the work boat): the full-resolution "high" files only when the user chose
// the "high" quality mode; every other mode, including the default "auto", loads the standard files.
// Without an explicit mode it uses the last configured mode, else the same URL / stored choice the menus use.
export function assetTextureTier(mode = lastMode ?? storedQualityMode()) {
  return ['high', 'ultra'].includes(mode) ? 'high' : 'standard';
}

// Whether the game canvas needs its own multisampling. The optics tiers draw the scene into the pipeline's
// half-float target (fx/pipeline.js) and only a full-screen quad reaches the canvas, so a multisampled canvas there
// costs memory and a resolve every frame for nothing. Only the low tiers draw the scene straight to the canvas.
// The context's antialias flag is fixed at creation; a tier changed in flight keeps the canvas it started with.
// The low class (startsLow: Intel HD / UHD, whose drivers Chrome flags msaa_is_slow) never gets a multisampled
// canvas either. hints: chooseHardwareProfile hints; by default read from a throwaway WebGL context.
export function canvasAntialias(mode = storedQualityMode(), hints = null) {
  if (new URLSearchParams(globalThis.location?.search).has('safe')) return false;
  if (!['performance', 'low'].includes(mode)) return false;
  return !chooseHardwareProfile(hints ?? probeHints()).startsLow;
}

function probeHints() {
  try {
    const canvas = globalThis.document?.createElement('canvas');
    const gl = canvas?.getContext('webgl2') || canvas?.getContext('webgl');
    if (!gl) return {};
    const extension = gl.getExtension('WEBGL_debug_renderer_info');
    const hints = {
      renderer: gl.getParameter(extension ? extension.UNMASKED_RENDERER_WEBGL : gl.RENDERER) || '',
      vendor: gl.getParameter(extension ? extension.UNMASKED_VENDOR_WEBGL : gl.VENDOR) || '',
    };
    gl.getExtension('WEBGL_lose_context')?.loseContext();
    return hints;
  } catch {
    return {};
  }
}

// Scene detail for automatic quality on this renderer's GPU: the low scene (structures, seabed, habitat) wherever
// automatic quality starts on the low look.
export function automaticSceneDetail(renderer) {
  const hardware = detectHardware(renderer);
  return hardware.tier === 'software' || hardware.startsLow ? 'low' : 'medium';
}

function storedQualityMode() {
  if (new URLSearchParams(globalThis.location?.search).has('safe')) return 'low';
  const fromUrl = new URLSearchParams(globalThis.location?.search || '').get('quality');
  if (fromUrl) return fromUrl;
  try {
    return globalThis.localStorage?.getItem('rov.quality') || 'auto';
  } catch {
    return 'auto';
  }
}
