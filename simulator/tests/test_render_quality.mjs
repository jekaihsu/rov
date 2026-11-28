import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../viewer/render_quality.js',import.meta.url),'utf8');
const {chooseHardwareProfile,detectHardware,configureRenderQuality,updateRenderQuality,renderQualityInfo,assetTextureTier,
  automaticSceneDetail,canvasAntialias}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

assert.equal(chooseHardwareProfile({renderer:'ANGLE (Google, SwiftShader Device (Subzero))'}).tier,'software');
assert.equal(chooseHardwareProfile({renderer:'Mesa llvmpipe (LLVM 15.0)'}).floor,.5);
assert.equal(chooseHardwareProfile({renderer:'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)'}).ceiling,.85);
for(const model of ['MX110','MX250','MX330','MX450']){
  const p=chooseHardwareProfile({renderer:`NVIDIA GeForce ${model}`,deviceMemory:4});
  assert.equal(p.tier,'discrete');assert.equal(p.entryLevel,true);
  // MX1xx is startsLow (0.75); MX2xx+ stay on the entry-level 0.85 start.
  assert.equal(p.initialRatio, /\bMX1\d{2}\b/.test(model) ? .75 : .85);
}
const discrete=chooseHardwareProfile({renderer:'NVIDIA GeForce RTX 4060',deviceMemory:4});
assert.equal(discrete.initialRatio,1);assert.equal(discrete.entryLevel,false);
assert.equal(chooseHardwareProfile({renderer:'AMD Radeon RX 6600'}).tier,'discrete');
assert.equal(chooseHardwareProfile({renderer:'AMD Radeon(TM) RX 6600'}).tier,'discrete');
assert.equal(chooseHardwareProfile({renderer:'Intel Arc A750 Graphics'}).tier,'discrete');
assert.equal(chooseHardwareProfile({renderer:'AMD Radeon(TM) Graphics'}).tier,'integrated');
assert.equal(chooseHardwareProfile({renderer:'WebKit WebGL',deviceMemory:undefined}).tier,'unknown');
assert.equal(chooseHardwareProfile({}).logicalCores,null);
assert.equal(chooseHardwareProfile({deviceMemory:NaN}).memoryGB,null);
assert.equal(detectHardware({getContext(){throw Error('Context unavailable');}}).tier,'unknown');

function renderer(name){
  return {domElement:{clientWidth:1366,clientHeight:768},shadowMap:{},info:{render:{calls:10,triangles:100}},ratio:null,
    setPixelRatio(ratio){this.ratio=ratio;},
    getContext(){return {RENDERER:1,VENDOR:2,getExtension(){return {UNMASKED_RENDERER_WEBGL:3,UNMASKED_VENDOR_WEBGL:4};},getParameter(key){return key===3?name:'vendor';}};}};
}
for(const name of ['SwiftShader','Intel UHD 620','NVIDIA GeForce MX110','NVIDIA GeForce RTX 4060','WebKit WebGL']){
  const r=renderer(name),s=configureRenderQuality(r,'auto');
  assert.ok(r.ratio<=s.ceiling&&r.ratio>=s.floor);
  // Low-end ladder targets ≥30 fps (slowFps 28): force a drop with 20 fps samples. Mainstream still uses 50.
  const slowSample = s.hardware.startsLow || s.hardware.tier === 'software' ? 1 / 20 : 1 / 30;
  for(let i=0;i<900;i++)updateRenderQuality(r,slowSample);
  assert.ok(Math.abs(r.ratio-s.floor)<1e-9);
  const low=r.ratio;
  for(let i=0;i<1200;i++)updateRenderQuality(r,1/60,{suspended:true});
  assert.equal(r.ratio,low);
  // Low-end raiseHold is 10 s per step; give enough 60 fps windows to climb floor → ceiling.
  for(let i=0;i<9000;i++)updateRenderQuality(r,1/60);
  assert.ok(Math.abs(r.ratio-s.ceiling)<1e-9);
  assert.equal(renderQualityInfo(r).hardwareTier,s.hardware.tier);
  configureRenderQuality(r, 'medium');
  assert.equal(r.shadowMap.enabled, !(s.hardware.startsLow || s.hardware.tier === 'software'));
  configureRenderQuality(r,'high');const fixed=r.ratio;
  assert.equal(r.shadowMap.enabled, true);
  for(let i=0;i<900;i++)updateRenderQuality(r,1/30);
  assert.equal(r.ratio,fixed);
}
// UHD 620 at a steady 30 fps must not keep cutting: that is already the S2 success bar.
{
  const uhd=renderer('ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)'),state=configureRenderQuality(uhd,'auto');
  const start=uhd.ratio;
  for(let i=0;i<400;i++)updateRenderQuality(uhd,1/30);
  assert.equal(uhd.ratio,start,'stable 30 fps holds the scale on the low-end ladder');
  assert.equal(state.slowFps,28);
  assert.equal(state.fastFps,36);
}
const r=renderer('Intel UHD Graphics 620'),s=configureRenderQuality(r,'auto');
for(let i=0;i<60;i++)updateRenderQuality(r,1);
assert.equal(r.ratio,s.floor,'Sustained 1 FPS must still reduce pixel workload');
configureRenderQuality(r,'auto');
r.domElement.clientWidth=3840;r.domElement.clientHeight=2160;
for(let i=0;i<300;i++)updateRenderQuality(r,1/60);
assert.ok(r.ratio<=.5);assert.ok(r.ratio*r.ratio*3840*2160<=s.hardware.pixelBudget+1);
// Software GL in automatic quality starts with the underwater screen effects off; real GPUs start with them on.
assert.equal(configureRenderQuality(renderer('SwiftShader'),'auto').effectsSuppressed,true);
assert.equal(configureRenderQuality(renderer('NVIDIA GeForce RTX 4060'),'auto').effectsSuppressed,false);
assert.equal(configureRenderQuality(renderer('SwiftShader'),'medium').effectsSuppressed,false);
// Large-asset texture tier: full-resolution files only for the explicit "high" mode, standard otherwise.
assert.equal(assetTextureTier('high'),'high');
for(const mode of ['auto','performance','medium','bogus'])assert.equal(assetTextureTier(mode),'standard');
configureRenderQuality(renderer('NVIDIA GeForce RTX 4060'),'high');
assert.equal(assetTextureTier(),'high');
configureRenderQuality(renderer('NVIDIA GeForce RTX 4060'),'auto');
assert.equal(assetTextureTier(),'standard');
// The minimum-spec class (15 W laptop: Intel UHD 620 or GeForce MX110) starts on the low look and low scene detail;
// mainstream and unknown GPUs start with the optics.
for(const name of ['ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11 vs_5_0 ps_5_0, D3D11)',
  'ANGLE (NVIDIA, NVIDIA GeForce MX110 Direct3D11 vs_5_0 ps_5_0, D3D11)']){
  assert.equal(configureRenderQuality(renderer(name),'auto').effectsSuppressed,true,name);
  assert.equal(automaticSceneDetail(renderer(name)),'low',name);
  assert.equal(configureRenderQuality(renderer(name),'medium').effectsSuppressed,false,'explicit tiers are kept');
}
for(const name of ['NVIDIA GeForce RTX 4060','WebKit WebGL','ANGLE (Intel, Intel(R) Iris(R) Xe Graphics Direct3D11)',
  'NVIDIA GeForce MX450','Apple M1']){
  assert.equal(configureRenderQuality(renderer(name),'auto').effectsSuppressed,false,name);
  assert.equal(automaticSceneDetail(renderer(name)),'medium',name);
}
assert.equal(automaticSceneDetail(renderer('SwiftShader')),'low');
assert.equal(chooseHardwareProfile({renderer:'ANGLE (Intel, Intel(R) HD Graphics 520 Direct3D11)'}).startsLow,true);
// A multisampled canvas only for the low tiers, and never on the msaa-is-slow Intel class.
assert.equal(canvasAntialias('medium',{renderer:'NVIDIA GeForce RTX 4060'}),false);
assert.equal(canvasAntialias('performance',{renderer:'NVIDIA GeForce RTX 4060'}),true);
assert.equal(canvasAntialias('performance',{renderer:'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)'}),false);
assert.equal(canvasAntialias('auto',{renderer:'NVIDIA GeForce RTX 4060'}),false);
// Automatic quality lowers the render scale first; the screen effects go only once the scale is at its floor.
{
  const gpu=renderer('NVIDIA GeForce RTX 4060'),state=configureRenderQuality(gpu,'auto');
  const start=gpu.ratio;
  for(let i=0;i<90+50;i++)updateRenderQuality(gpu,1/30);
  assert.ok(gpu.ratio<start,'the first slow window lowers the scale');
  assert.equal(state.effectsSuppressed,false,'effects stay while the scale can still drop');
  for(let i=0;i<900;i++)updateRenderQuality(gpu,1/30);
  assert.ok(Math.abs(gpu.ratio-state.floor)<1e-9);
  assert.equal(state.effectsSuppressed,true,'still slow at the floor: effects are dropped');
}
// What automatic quality learned in the game view is where the next page's game view starts (same GPU only).
{
  const store=new Map();
  globalThis.localStorage={getItem:key=>store.get(key)??null,setItem:(key,value)=>store.set(key,String(value))};
  const first=renderer('AMD Radeon RX 6600');
  const learned=configureRenderQuality(first,'auto',{learn:true});
  for(let i=0;i<900;i++)updateRenderQuality(first,1/30);
  assert.equal(learned.effectsSuppressed,true);
  const saved=JSON.parse(store.get('rov.quality.learned.v1'));
  assert.equal(saved.version, 1);
  assert.equal(saved.slowFps, 50);
  assert.equal(saved.effectsSuppressed,true);
  assert.ok(Math.abs(saved.ratio-learned.floor)<1e-9);
  const source=await readFile(new URL('../viewer/render_quality.js',import.meta.url),'utf8');
  const fresh=await import(`data:text/javascript;base64,${Buffer.from(source+'\n//fresh').toString('base64')}`);
  const next=fresh.configureRenderQuality(renderer('AMD Radeon RX 6600'),'auto',{learn:true});
  assert.equal(next.effectsSuppressed,true);
  assert.ok(Math.abs(next.ratio-next.floor)<1e-9);
  const again=fresh.configureRenderQuality(renderer('AMD Radeon RX 6600'),'auto',{learn:true});
  assert.equal(again.effectsSuppressed,false,'only the first game view of a page starts from what was learned');
  const other=await import(`data:text/javascript;base64,${Buffer.from(source+'\n//other').toString('base64')}`);
  const otherGpu=other.configureRenderQuality(renderer('NVIDIA GeForce RTX 4060'),'auto',{learn:true});
  assert.equal(otherGpu.effectsSuppressed,false);
  const menu=await import(`data:text/javascript;base64,${Buffer.from(source+'\n//menu').toString('base64')}`);
  assert.equal(menu.configureRenderQuality(renderer('AMD Radeon RX 6600'),'auto').effectsSuppressed,false,
    'the menu backdrop neither reads nor writes what the game learned');
  delete globalThis.localStorage;
}
console.log('Hardware hints, privacy fallback, viewport budget, measured FPS recovery and recording suspension passed.');
