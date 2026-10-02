import {COLLECTION_CATEGORIES,listCollection,getPhotoBlob,setCover,exportCollection,importCollection,downloadCollectionFile} from './collection_store.js';

const element=(tag,text,className)=>{const node=document.createElement(tag);if(text!==undefined)node.textContent=text;if(className)node.className=className;return node;};
const date=value=>{const d=new Date(value);return Number.isFinite(d.getTime())?d.toLocaleString('zh-TW',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}):'日期未記錄';};
const categoryName=value=>COLLECTION_CATEGORIES[value]||'紀念照';
const valueText=value=>typeof value==='string'||typeof value==='number'?String(value):value?.name||value?.label||'—';

export function installCollectionPanel({host=document.body,onOpen=()=>{},onClose=()=>{}}={}){
  if(!document.querySelector('link[data-rov-collection]')){const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('./collection.css',import.meta.url).href;css.dataset.rovCollection='';document.head.append(css);}
  const dialog=element('dialog',undefined,'collection-panel');dialog.setAttribute('aria-label','航行收藏');
  const header=element('header',undefined,'collection-heading'),heading=element('div');heading.append(element('h2','航行收藏'),element('p','原圖與紀錄保存在這台裝置，備份檔可帶到另一台電腦。'));
  const closeButton=element('button','×','collection-close');closeButton.type='button';closeButton.setAttribute('aria-label','關閉收藏');header.append(heading,closeButton);
  const toolbar=element('div',undefined,'collection-toolbar'),tabs=element('nav',undefined,'collection-tabs'),actions=element('div',undefined,'collection-actions');tabs.setAttribute('aria-label','收藏分類');
  const exportButton=element('button','匯出備份'),importButton=element('button','匯入備份'),file=document.createElement('input');file.type='file';file.accept='application/json,.json';file.hidden=true;actions.append(exportButton,importButton,file);toolbar.append(tabs,actions);
  const notice=element('p','', 'collection-notice');notice.setAttribute('role','status');const content=element('div',undefined,'collection-content');dialog.append(header,toolbar,notice,content);host.append(dialog);
  let tab='guides',selected=null,collection=null,pageSize=24,isOpen=false,destroyed=false,loadGeneration=0,previousFocus=null;
  const urls=new Map(),pending=new Map();
  const notify=(text,error=false)=>{notice.textContent=text;notice.dataset.error=String(error);};
  const revoke=()=>{loadGeneration++;for(const url of urls.values())URL.revokeObjectURL(url);urls.clear();pending.clear();};
  async function imageURL(id){
    if(urls.has(id))return urls.get(id);if(pending.has(id))return pending.get(id);
    const generation=loadGeneration;
    const promise=getPhotoBlob(id).then(blob=>{if(generation!==loadGeneration||!isOpen)return null;const url=URL.createObjectURL(blob);urls.set(id,url);return url;}).finally(()=>pending.delete(id));pending.set(id,promise);return promise;
  }
  function picture(id,className,alt){const image=document.createElement('img');image.className=className||'';image.alt=alt;image.loading='lazy';image.decoding='async';imageURL(id).then(url=>{if(url)image.src=url;}).catch(error=>{image.alt='原圖無法讀取';notify(error.message,true);});return image;}
  function empty(title,text){const block=element('div',undefined,'collection-empty');block.append(element('strong',title),element('p',text));content.append(block);}
  function photoCard(photo,title,subtitle){const article=element('article',undefined,'collection-card'),button=element('button',undefined,'collection-photo-button');button.type='button';button.setAttribute('aria-label',`查看${title}`);button.append(picture(photo.id,'',title));button.onclick=()=>{selected=photo.id;render();};article.append(button,element('h3',title),element('p',subtitle));return article;}
  function renderGuides(){
    const grid=element('div',undefined,'collection-grid');
    for(const [category,name]of Object.entries(COLLECTION_CATEGORIES)){
      const guide=collection.guides.find(g=>g.category===category),photo=guide&&collection.photos.find(p=>p.id===guide.photoId);
      if(photo)grid.append(photoCard(photo,name,`首次觀測 ${date(guide.unlockedAt)}`));
      else{const article=element('article',undefined,'collection-card');article.append(element('div','尚未觀測','collection-locked'),element('h3',name),element('p','切換機載視角，在有效距離內完成拍攝。'));grid.append(article);}
    }
    content.append(grid);
  }
  function renderPhotos(){
    if(!collection.photos.length){empty('把這次潛航留下來','拍攝的原圖會收進這裡。機載視角的有效生物觀測也會解鎖圖鑑；其他視角保留為紀念照。');return;}
    const photos=collection.photos.slice().sort((a,b)=>b.createdAt.localeCompare(a.createdAt)),grid=element('div',undefined,'collection-grid');
    for(const photo of photos.slice(0,pageSize))grid.append(photoCard(photo,categoryName(photo.observation?.category),date(photo.createdAt)));
    content.append(grid);if(photos.length>pageSize){const more=element('button',`顯示更多照片（${photos.length-pageSize} 張）`,'collection-more');more.onclick=()=>{pageSize+=24;render();};content.append(more);}
  }
  function renderPhoto(photo){
    const back=element('button','← 返回收藏');back.onclick=()=>{selected=null;render();};content.append(back);
    const detail=element('div',undefined,'collection-detail'),media=element('div'),info=element('section');media.append(picture(photo.id,'collection-original',categoryName(photo.observation?.category)));
    const category=photo.observation?.category;info.append(element('h3',categoryName(category)));
    const facts=element('dl');
    const row=(label,value)=>{facts.append(element('dt',label),element('dd',value));};
    row('拍攝時間',date(photo.createdAt));row('分類',category?'機載有效觀測':'紀念照');
    row('場景',valueText(photo.metadata.scenario||photo.metadata.scene));row('機型',valueText(photo.metadata.model||photo.metadata.modelId||photo.metadata.model_id||photo.metadata.vehicle));
    const position=photo.metadata.position||photo.metadata.pos||photo.metadata.pose?.pos,depth=photo.metadata.depth??(Array.isArray(position)?position[2]:null);if(Number.isFinite(depth))row('深度',`${depth.toFixed(2)} m`);
    row('原圖',`${(photo.bytes/1024/1024).toFixed(2)} MiB · ${photo.mime==='image/png'?'PNG':'JPEG'}`);info.append(facts);
    const buttons=element('div',undefined,'collection-detail-buttons');
    if(category){const cover=element('button',collection.guides.some(g=>g.category===category&&g.photoId===photo.id)?'目前圖鑑封面':'設為圖鑑封面');cover.disabled=collection.guides.some(g=>g.category===category&&g.photoId===photo.id);cover.onclick=async()=>{try{await setCover(category,photo.id);notify('已更新封面，原始拍攝資料保持不變。');await refresh();}catch(error){notify(error.message,true);}};buttons.append(cover);}
    const download=element('button','下載原圖');download.onclick=async()=>{try{downloadCollectionFile(`${photo.id}.${photo.mime==='image/png'?'png':'jpg'}`,await getPhotoBlob(photo.id));}catch(error){notify(error.message,true);}};buttons.append(download);info.append(buttons,element('p','拍攝資訊與工程結果按原始紀錄保存；選封面不會改寫照片資料。','collection-caption'));detail.append(media,info);content.append(detail);
  }
  function renderResults(){
    if(!collection.results.length){empty('工程紀錄仍是空白','完成的作業結果會保存在這裡，包含評定、完成時間與參與人員。');return;}
    for(const result of collection.results.slice().sort((a,b)=>b.createdAt.localeCompare(a.createdAt))){
      const row=element('article',undefined,'collection-result'),head=element('div',undefined,'collection-result-head');head.append(element('strong',valueText(result.title||result.label||result.name||'工程紀錄')),element('span',valueText(result.rating||result.grade||({completed:'完成',failed:'未完成'}[result.status])||(result.success===false?'未完成':'已記錄'))));row.append(head,element('p',date(result.createdAt)));
      const facts=element('dl'),field=(name,value)=>{const wrap=element('div');wrap.append(element('dt',name),element('dd',value));facts.append(wrap);};
      if(result.scenario||result.scene)field('場景',valueText(result.scenario||result.scene));
      const duration=result.duration_s??result.elapsed;if(Number.isFinite(duration))field('耗時',`${Math.floor(duration/60)} 分 ${Math.round(duration%60)} 秒`);
      const collisions=result.collisions??result.collision_count;if(Number.isFinite(collisions))field('碰撞',`${collisions} 次`);if(Number.isFinite(result.score))field('評分',String(result.score));row.append(facts);
      if(typeof result.summary==='string')row.append(element('p',result.summary));
      if(Array.isArray(result.participants)&&result.participants.length)row.append(element('p',`參與人員：${result.participants.map(p=>valueText(p.name||p.label||p.player_id||p)).join('、')}`));
      if(Array.isArray(result.checks)){const details=element('details'),list=element('ul');details.append(element('summary','作業項目'));for(const check of result.checks)list.append(element('li',`${check.passed?'✓':'—'} ${valueText(check.label||check.name)}`));details.append(list);row.append(details);}
      content.append(row);
    }
  }
  function render(){if(!isOpen||!collection)return;content.replaceChildren();for(const button of tabs.children)button.setAttribute('aria-selected',String(button.dataset.tab===tab));
    if(selected){const photo=collection.photos.find(p=>p.id===selected);if(photo){renderPhoto(photo);return;}selected=null;}
    if(tab==='guides')renderGuides();else if(tab==='photos')renderPhotos();else renderResults();
  }
  async function refresh(){const generation=loadGeneration;try{const value=await listCollection();if(generation!==loadGeneration||!isOpen)return;collection=value;render();}catch(error){notify(`收藏無法讀取：${error.message}`,true);}}
  for(const [key,label]of [['guides','圖鑑'],['photos','照片'],['results','工程紀錄']]){const button=element('button',label);button.type='button';button.dataset.tab=key;button.setAttribute('role','tab');button.onclick=()=>{tab=key;selected=null;render();};tabs.append(button);}
  exportButton.onclick=async()=>{exportButton.disabled=true;notify('正在整理原圖與紀錄…');try{downloadCollectionFile(`ROV-collection-${new Date().toISOString().slice(0,10)}.json`,await exportCollection());notify('備份已準備下載，內含完整原圖。');}catch(error){notify(error.message,true);}finally{exportButton.disabled=false;}};
  importButton.onclick=()=>file.click();file.onchange=async()=>{if(!file.files[0])return;importButton.disabled=true;notify('正在檢查備份並合併收藏…');try{const result=await importCollection(file.files[0]);notify(`已新增 ${result.addedPhotos} 張照片、${result.addedResults} 筆工程紀錄。`);await refresh();}catch(error){notify(`匯入未完成：${error.message}`,true);}finally{file.value='';importButton.disabled=false;}};
  const changed=()=>{if(isOpen)refresh();};window.addEventListener('rov:collection-changed',changed);
  function close(){if(!isOpen)return;isOpen=false;dialog.close();revoke();content.replaceChildren();onClose();previousFocus?.focus?.();}
  async function open(){if(destroyed||isOpen)return;previousFocus=document.activeElement;onOpen();isOpen=true;selected=null;notice.textContent='';dialog.showModal();await refresh();}
  closeButton.onclick=close;dialog.addEventListener('cancel',event=>{event.preventDefault();close();});
  function destroy(){close();destroyed=true;window.removeEventListener('rov:collection-changed',changed);dialog.remove();}
  return {open,close,destroy};
}
