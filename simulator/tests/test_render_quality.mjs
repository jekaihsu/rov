import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../viewer/render_quality.js',import.meta.url),'utf8');
const {chooseHardwareProfile,detectHardware,configureRenderQuality,updateRenderQuality,renderQualityInfo}=await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`);

assert.equal(chooseHardwareProfile({renderer:'ANGLE (Google, SwiftShader Device (Subzero))'}).tier,'software');
assert.equal(chooseHardwareProfile({renderer:'Mesa llvmpipe (LLVM 15.0)'}).floor,.5);
assert.equal(chooseHardwareProfile({renderer:'ANGLE (Intel, Intel(R) UHD Graphics 620 Direct3D11)'}).ceiling,.9);
for(const model of ['MX110','MX250','MX330','MX450']){
  const p=chooseHardwareProfile({renderer:`NVIDIA GeForce ${model}`,deviceMemory:4});
  assert.equal(p.tier,'discrete');assert.equal(p.entryLevel,true);assert.equal(p.initialRatio,.85);
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
  for(let i=0;i<900;i++)updateRenderQuality(r,1/30);
  assert.ok(Math.abs(r.ratio-s.floor)<1e-9);
  const low=r.ratio;
  for(let i=0;i<1200;i++)updateRenderQuality(r,1/60,{suspended:true});
  assert.equal(r.ratio,low);
  for(let i=0;i<4800;i++)updateRenderQuality(r,1/60);
  assert.ok(Math.abs(r.ratio-s.ceiling)<1e-9);
  assert.equal(renderQualityInfo(r).hardwareTier,s.hardware.tier);
  configureRenderQuality(r,'high');const fixed=r.ratio;
  for(let i=0;i<900;i++)updateRenderQuality(r,1/30);
  assert.equal(r.ratio,fixed);
}
const r=renderer('Intel UHD Graphics 620'),s=configureRenderQuality(r,'auto');
for(let i=0;i<60;i++)updateRenderQuality(r,1);
assert.equal(r.ratio,s.floor,'Sustained 1 FPS must still reduce pixel workload');
configureRenderQuality(r,'auto');
r.domElement.clientWidth=3840;r.domElement.clientHeight=2160;
for(let i=0;i<300;i++)updateRenderQuality(r,1/60);
assert.ok(r.ratio<=.5);assert.ok(r.ratio*r.ratio*3840*2160<=s.hardware.pixelBudget+1);
console.log('Hardware hints, privacy fallback, viewport budget, measured FPS recovery and recording suspension passed.');
