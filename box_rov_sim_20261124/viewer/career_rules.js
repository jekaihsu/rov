// Personal, offline cosmetic progression. No real money or competitive economy.
export const CATALOG=[
  {id:'sticker_survey',kind:'sticker',value:'survey',name:'海洋調查隊',price:120,color:'#65ced2',description:'波浪與測線圖案，適合調查作業。'},
  {id:'sticker_rescue',kind:'sticker',value:'rescue',name:'水下救援',price:180,color:'#ef9458',description:'橘白救援標記，機身兩側貼花。'},
  {id:'sticker_abyss',kind:'sticker',value:'abyss',name:'深海探索者',price:240,color:'#9686dd',description:'深海星點與探索編號。'},
  {id:'livery_arctic',kind:'livery',value:'arctic',name:'極地白',price:150,color:'#dce8e9',description:'更換浮力外殼塗裝，保留鏡頭、燈具與金屬原色。'},
  {id:'livery_teal',kind:'livery',value:'teal',name:'海洋青',price:220,color:'#27b7b1',description:'浮力外殼的海洋調查配色。'},
  {id:'livery_orange',kind:'livery',value:'orange',name:'救援橘',price:300,color:'#f58b37',description:'高辨識度外殼塗裝。'},
];
export const ACHIEVEMENTS=[
  {id:'first_contract',name:'第一份委託',detail:'完成 1 次工程任務',stat:'contracts',goal:1,reward:100},
  {id:'engineer',name:'可靠工程師',detail:'完成 5 次工程任務',stat:'contracts',goal:5,reward:200},
  {id:'veteran',name:'資深潛航員',detail:'完成 10 次工程任務',stat:'contracts',goal:10,reward:300},
  {id:'observer',name:'第一眼海洋',detail:'發現 1 類海洋生物',stat:'species',goal:1,reward:50},
  {id:'naturalist',name:'海洋自然學家',detail:'收集全部 5 類生物圖鑑',stat:'species',goal:5,reward:300},
];
export const EMPTY_CAREER=()=>({version:1,revision:0,owned:[],equipped:{sticker:'none',livery:'original'}});
export function validateCareer(input){
  if(!input||input.version!==1||!Number.isSafeInteger(input.revision)||input.revision<0||!Array.isArray(input.owned)||input.owned.length>CATALOG.length||new Set(input.owned).size!==input.owned.length||input.owned.some(id=>!CATALOG.some(p=>p.id===id)))throw Error('生涯存檔格式無效');
  const value=JSON.parse(JSON.stringify(input));
  for(const kind of ['sticker','livery']){
    const equipped=value.equipped?.[kind],free=kind==='sticker'?['none','hazard','dive','number']:['original'];
    if(!free.includes(equipped)&&!CATALOG.some(p=>p.kind===kind&&p.value===equipped&&value.owned.includes(p.id)))throw Error('此外觀尚未解鎖');
  }
  return {version:1,revision:value.revision,owned:value.owned,equipped:value.equipped};
}
export function careerSummary(collection,profile=EMPTY_CAREER()){
  profile=validateCareer(profile);
  const contracts=new Map((collection.results||[]).filter(r=>r.success===true).map(r=>[r.id,r]));
  const species=new Set((collection.guides||[]).map(g=>g.category).filter(c=>['coral','seastar','seagrass','kelp','fish_school'].includes(c))).size;
  const stats={contracts:contracts.size,species,photos:(collection.photos||[]).length};
  const achievements=ACHIEVEMENTS.map(a=>({...a,current:Math.min(a.goal,stats[a.stat]),unlocked:stats[a.stat]>=a.goal}));
  const missionPoints=contracts.size*200,discoveryPoints=species*100,bonus=achievements.filter(a=>a.unlocked).reduce((n,a)=>n+a.reward,0);
  const earned=missionPoints+discoveryPoints+bonus,spent=CATALOG.filter(p=>profile.owned.includes(p.id)).reduce((n,p)=>n+p.price,0);
  return {...stats,earned,spent,balance:earned-spent,missionPoints,discoveryPoints,bonus,achievements,rank:earned>=2500?'深海專家':earned>=1000?'調查隊員':earned>=300?'潛航員':'見習探索員'};
}
export function changeCareer(profile,collection,action){
  const next=validateCareer(profile),product=CATALOG.find(p=>p.id===action.id);
  if(action.type==='buy'){
    if(!product)throw Error('找不到商品');
    if(next.owned.includes(product.id))return next;
    if(careerSummary(collection,next).balance<product.price)throw Error('點數不足，完成工程或首次生物觀測即可獲得點數');
    next.owned.push(product.id);
  }else if(action.type==='equip'){
    if(!['sticker','livery'].includes(action.kind))throw Error('外觀類型無效');
    next.equipped[action.kind]=action.value;
  }else throw Error('不支援的商店操作');
  next.revision++;return validateCareer(next);
}
