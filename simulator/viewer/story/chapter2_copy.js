// Chapter 2 radio and location strings (docs/story/lines.csv C21–C23). Presentation only.
import {localize} from '../i18n/index.js';

export const STRINGS = localize('story.chapter2_copy', {
  site: '折帆灣',
  netSub: '三號圈入口',
  mortSub: '三號圈網底',
  escapeSub: '三號圈外緣',
  stamp: '青灣箱網',
  sep: '：',
  speakers: {
    weng: '翁慈',
    lin: '林岑',
    zhou: '周楷',
    fang: '方晴',
    ma: '馬力',
  },
  hints: {
    move: '前進',
    photo: '拍照',
    clearance: '留距離',
    slow: '慢近',
    grip: '輕夾',
    hold: '監看',
  },
  c21Open: '網台－翁。三號圈，例行網衣。',
  c21Crew: '燈別太亮，魚會瘋。',
  c21Task: 'R-1，貼網但不吸網。',
  c21Billow: 'R-1，這段網往外鼓。留點距離。',
  c21Snag: '張力。可能掛繩。',
  c21Report: '方位報出來。',
  c21Idle: 'R-1，白浮框算十二點。',
  c21Timeout: '未查網段留白，我註明範圍。',
  c21Done: '回收。破洞兩處已記。',
  c22Open: '底層有死魚。夾上來。',
  c22Crew: '夾穩再抬。配平會變。',
  c22Task: '線跟你走。別拖地。',
  c22Silt: '等清。用輪廓找。',
  c22Grip: '對準。輕夾。',
  c22Idle: 'R-1，從籃口看回最後那一尾。',
  c22Timeout: '收籃。剩下的數量交場方。',
  c22Done: '回收夾爪。洗手。',
  c23Open: '密度掉了！快！',
  c23Crew: '先停。聽我說。流在升。十二分窗口。',
  c23Task: 'R-1，先找洞，別追魚。',
  c23Found: '那裡。對正。方位報。深度報。',
  c23Watch: '補網組出動。你盯著。',
  c23Idle: 'R-1，先看網線在哪裡斷。',
  c23Timeout: '窗口關了。已查範圍交網台。',
  c23Relief: '補網到位。你們可收。',
  c23Ending: '見習到此。你會開了。',
  c23Schedule: '八月二十八日 · 風場試單 · C 腿｜平潮還剩二十分鐘',
  c23Continue: '待續',
  gold: '洞位準。監看到位。',
  silver: '主洞有了。窗口判斷得當。',
  bronze: '座標勉強。嚇到魚群。',
  abort: '對。人機網都還在。',
});

const SPEAKER_BY_LINE = Object.freeze({
  c21Open: 'weng',
  c21Crew: 'weng',
  c21Task: 'lin',
  c21Billow: 'weng',
  c21Snag: 'zhou',
  c21Report: 'weng',
  c21Idle: 'lin',
  c21Timeout: 'lin',
  c21Done: 'lin',
  c22Open: 'weng',
  c22Crew: 'lin',
  c22Task: 'zhou',
  c22Silt: 'lin',
  c22Grip: 'lin',
  c22Idle: 'lin',
  c22Timeout: 'lin',
  c22Done: 'lin',
  c23Open: 'weng',
  c23Crew: 'lin',
  c23Task: 'lin',
  c23Found: 'lin',
  c23Watch: 'weng',
  c23Idle: 'lin',
  c23Timeout: 'lin',
  c23Relief: 'weng',
  c23Ending: 'lin',
});

export function speakerFor(lineId) {
  const key = SPEAKER_BY_LINE[lineId] || 'lin';
  return STRINGS.speakers[key] || STRINGS.speakers.lin;
}

export function locationFor(contractId) {
  if (contractId === 'c2_mort_recovery') return [STRINGS.site, STRINGS.mortSub];
  if (contractId === 'c2_escape_event') return [STRINGS.site, STRINGS.escapeSub];
  return [STRINGS.site, STRINGS.netSub];
}
