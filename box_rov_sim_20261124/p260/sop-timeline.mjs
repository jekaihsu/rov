/** Deterministic illustrative SOP choreography. World coordinates are Z-up.
 * Distances and elapsed animation time are NOT calibrated survey measurements.
 */
export const DURATION = 140;
export const CHAPTERS = [
  { id:'prepare', title:'ROV-01 與作業準備', start:0, end:12, caption:'確認 ROV-01 雲台相機、雙 LED 照明、UT 測厚探頭與錄影設定；先看清楚本次作業設備。', sopRefs:['作業前檢查','錄影設定'] },
  { id:'approach', title:'分段與接近', start:12, end:28, caption:'先交代採集分段，再接近中段示範區；實船方位仍待確認。', sopRefs:['採集分段','距離與速度'] },
  { id:'scan', title:'分層弓字形採集', start:28, end:84, caption:'鏡頭持續朝向船體，水平側移往返，減速後下降換層。', sopRefs:['分層採集','影像重疊','平穩移動'] },
  { id:'detail', title:'重點多角度補拍', start:84, end:108, caption:'改變觀察角度補拍開口與既有甲板設備；此處為示意機件。', sopRefs:['重點區域補拍'] },
  { id:'review', title:'每層影像檢查', start:108, end:126, caption:'回看本段示範影像，檢查清晰度、遮擋、光照與相鄰畫面重疊。', sopRefs:['每層檢查','補拍記錄'] },
  { id:'handoff', title:'資料整理與交接', start:126, end:140, caption:'依採集段與層號整理原始影片、日誌及備份；畫面是交接示例。', sopRefs:['檔案命名','日誌同步','雙備份'] },
];

const clamp = (v,a,b) => Math.max(a,Math.min(b,v));
const smooth = t => t*t*t*(t*(t*6-15)+10);
const mix = (a,b,t) => a.map((v,i)=>v+(b[i]-v)*t);
const add = (a,b) => a.map((v,i)=>v+b[i]);
const scanAim = p => add(p,[0,15,-.4]);
export const SCAN_ROUTE = [
  {time:28, position:[84,-8,12], layer:1, phase:'第 1 層 · 正向側移'},
  {time:44, position:[90,-8,12], layer:1, phase:'減速 · 下降至第 2 層'},
  {time:48, position:[90,-8,10.7], layer:2, phase:'第 2 層 · 反向側移'},
  {time:64, position:[84,-8,10.7], layer:2, phase:'減速 · 下降至第 3 層'},
  {time:68, position:[84,-8,9.4], layer:3, phase:'第 3 層 · 正向側移'},
  {time:84, position:[90,-8,9.4], layer:3, phase:'完成示範三層 · 移向補拍區'},
];
export const THUMBNAIL_TIMES = [36,56,76];

const motionKeys = [
  {time:0, position:[82,-14,13], target:[84,7,11]},
  {time:12, position:[82,-14,13], target:[84,7,11]},
  ...SCAN_ROUTE.map(k=>({...k,target:scanAim(k.position)})),
  {time:90,position:[75,-8.8,10.5],target:[75.5,-4.2,9.5]},
  {time:100,position:[73.6,-8,10],target:[75.74,-3.99,8.625]},
  {time:108,position:[75.2,-8,9.6],target:[77.1875,-4.6,9.705]},
  {time:140,position:[75.2,-8,9.6],target:[77.1875,-4.6,9.705]},
];

function interpolate(keys,t,field) {
  let i=0;
  while(i<keys.length-2 && t>=keys[i+1].time)i++;
  const a=keys[i],b=keys[i+1];
  return mix(a[field],b[field],smooth(clamp((t-a.time)/(b.time-a.time),0,1)));
}

export function sampleSop(seconds=0) {
  const t=clamp(Number.isFinite(Number(seconds))?Number(seconds):0,0,DURATION);
  const chapter=CHAPTERS.find(c=>t>=c.start && t<c.end) || CHAPTERS.at(-1);
  const cameraOrigin=interpolate(motionKeys,t,'position');
  const target=interpolate(motionKeys,t,'target');
  const overview = t<12||t>28 ? 0 : t<20?smooth((t-12)/8):1-smooth((t-20)/8);
  const prepareDistance=t<=8?.55:t<12?.55+.45*smooth((t-8)/4):1;
  const external=mix(add(cameraOrigin,[-2.8,-3.2,1.6].map(v=>v*prepareDistance)),[64,-49,33],overview);
  const externalTarget=mix(add(cameraOrigin,[0,.45,-.05]),[85,-5,8],overview);
  const routeIndex=clamp(SCAN_ROUTE.findLastIndex(k=>t>=k.time),0,SCAN_ROUTE.length-1);
  const routeStep=SCAN_ROUTE[routeIndex];
  const phase=chapter.id==='scan'?routeStep.phase:chapter.id==='detail'&&t<90?'移向 A 段 · 重點補拍區':chapter.title;
  const layer=t<28?null:routeStep.layer;
  const scanTrail = t<28?[]:SCAN_ROUTE.filter(k=>k.time<=t).map(k=>[...k.position]);
  if(t>=28 && t<84)scanTrail.push([...cameraOrigin]);
  return {
    t, chapter, chapterIndex:CHAPTERS.indexOf(chapter), phase,
    progress:t/DURATION, chapterProgress:(t-chapter.start)/(chapter.end-chapter.start),
    cameraOrigin,target,external,externalTarget,layer,
    scanProgress:clamp((t-28)/56,0,1),scanTrail,
    routePoints:SCAN_ROUTE.map(k=>[...k.position]),
    thumbnailTimes:[...THUMBNAIL_TIMES],
    segment:t>=90?'A 段補拍區':'中段示範區', isIllustration:true,
    annotation:chapter.id==='scan'?'示範動作經時間壓縮；距離、速度與覆盖率非實測值。':null,
    showSegments:overview>.05, showZones:overview>.05,
    route:SCAN_ROUTE.map(k=>[...k.position]), showRoute:chapter.id==='scan',
  };
}
