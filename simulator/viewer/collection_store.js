export const COLLECTION_CATEGORIES={coral:'珊瑚',seastar:'海星',seagrass:'海草',kelp:'海藻',fish_school:'魚群'};
export const COLLECTION_LIMITS={image:12*1024*1024,total:80*1024*1024,index:4*1024*1024,archive:128*1024*1024,photos:500,results:2000};
const categories=Object.keys(COLLECTION_CATEGORIES),empty=()=>({version:1,photos:[],guides:[],results:[]});
const uid=()=>globalThis.crypto?.randomUUID?.()||`local-${Date.now()}-${Math.random().toString(36).slice(2)}`;
const fail=text=>{throw Error(text);};
const checkId=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,96}$/.test(value)?value:fail('收藏識別碼無效');
const jsonSize=value=>new TextEncoder().encode(JSON.stringify(value)).length;
function cleanJSON(value,max=32768){
  function visit(v,depth=0){
    if(depth>12)fail('收藏資料層級過深');
    if(v===null||typeof v==='boolean')return;
    if(typeof v==='number'){if(!Number.isFinite(v))fail('收藏數值無效');return;}
    if(typeof v==='string'){if(v.length>8192)fail('收藏文字過長');return;}
    if(typeof v!=='object'||(!Array.isArray(v)&&Object.getPrototypeOf(v)!==Object.prototype))fail('收藏資料格式無效');
    if(Object.keys(v).length>1024)fail('收藏資料項目過多');
    for(const [key,item]of Object.entries(v)){if(['__proto__','constructor','prototype'].includes(key))fail('收藏欄位無效');visit(item,depth+1);}
  }
  visit(value);if(jsonSize(value)>max)fail('收藏資料過大');return JSON.parse(JSON.stringify(value));
}
const same=(a,b)=>!!a.hash&&a.hash===b.hash&&JSON.stringify(a.metadata)===JSON.stringify(b.metadata)&&JSON.stringify(a.observation)===JSON.stringify(b.observation);
function checkIndex(index){
  if(index.photos.length>COLLECTION_LIMITS.photos||index.results.length>COLLECTION_LIMITS.results)fail('收藏數量已達上限，請先匯出備份');
  if(index.photos.reduce((n,p)=>n+p.bytes,0)>COLLECTION_LIMITS.total)fail('原圖總容量已達 80 MiB；不會自動刪除舊照片');
  if(jsonSize(index)>COLLECTION_LIMITS.index)fail('收藏文字資料已達上限，請先匯出備份');
}
async function photo(input){
  if(!(input.blob instanceof Blob)||!['image/png','image/jpeg'].includes(input.blob.type)||input.blob.size>COLLECTION_LIMITS.image)fail('僅支援 12 MiB 以下 PNG／JPEG 原圖');
  const metadata=cleanJSON(input.metadata??{});if(!metadata||Array.isArray(metadata)||typeof metadata!=='object')fail('照片資料格式無效');
  const observation=input.observation==null?null:cleanJSON(input.observation);
  if(observation&&(!categories.includes(observation.category)||metadata.cameraMode!=='onboard'))fail('圖鑑僅接受機載視角的有效觀測');
  const bytes=new Uint8Array(await input.blob.arrayBuffer());
  const signature=input.blob.type==='image/png'?[137,80,78,71,13,10,26,10].every((v,i)=>bytes[i]===v):bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
  if(!bytes.length||!signature)fail('照片格式無效');
  // SHA is identity/deduplication, not an authorization token. On insecure
  // browser origins without SubtleCrypto, preserve colliding IDs as copies.
  const hash=globalThis.crypto?.subtle?Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',bytes)),v=>v.toString(16).padStart(2,'0')).join(''):null;
  const createdAt=typeof input.createdAt==='string'&&Number.isFinite(Date.parse(input.createdAt))?new Date(input.createdAt).toISOString():new Date().toISOString();
  return {record:{id:input.id?checkId(input.id):uid(),createdAt,metadata,observation,mime:input.blob.type,bytes:input.blob.size,hash},blob:input.blob};
}
function result(input){const value=cleanJSON(input,65536);if(!value||Array.isArray(value)||typeof value!=='object')fail('工程紀錄格式無效');return {...value,id:value.id?checkId(value.id):uid(),createdAt:typeof value.createdAt==='string'&&Number.isFinite(Date.parse(value.createdAt))?new Date(value.createdAt).toISOString():new Date().toISOString()};}
function addPhoto(index,image){
  const existing=index.photos.find(p=>p.id===image.record.id);if(existing&&same(existing,image.record))return {record:existing,added:false};
  if(existing){const priorCopy=index.photos.find(p=>same(p,image.record));if(priorCopy)return {record:priorCopy,added:false};}
  if(existing)image.record.id=uid();index.photos.push(image.record);
  const category=image.record.observation?.category;
  if(category&&!index.guides.some(g=>g.category===category))index.guides.push({category,photoId:image.record.id,unlockedAt:image.record.createdAt});
  return {record:image.record,added:true};
}
let databasePromise,queue=Promise.resolve();
const serial=work=>{const job=queue.then(work);queue=job.catch(()=>{});return job;};
function database(){
  if(!databasePromise)databasePromise=new Promise((resolve,reject)=>{
    const request=indexedDB.open('rov-personal-collection',1);
    request.onupgradeneeded=()=>{request.result.createObjectStore('index');request.result.createObjectStore('photos');};
    request.onsuccess=()=>{const db=request.result;db.onversionchange=()=>{db.close();databasePromise=null;};resolve(db);};
    request.onerror=()=>{databasePromise=null;reject(request.error);};
    request.onblocked=()=>reject(Error('收藏資料庫正被其他頁面使用，請關閉舊頁面後重試'));
  });return databasePromise;
}
async function transact(write,callback){
  const db=await database();return new Promise((resolve,reject)=>{
    const tx=db.transaction(['index','photos'],write?'readwrite':'readonly'),indexStore=tx.objectStore('index'),photos=tx.objectStore('photos');let output,failure;
    const request=indexStore.get('collection');
    request.onsuccess=()=>{try{const index=request.result||empty();output=callback(index,photos);if(write){checkIndex(index);indexStore.put(index,'collection');}}catch(error){failure=error;tx.abort();}};
    tx.oncomplete=()=>resolve(output);tx.onerror=()=>reject(failure||tx.error||Error('收藏儲存失敗'));tx.onabort=()=>reject(failure||tx.error||Error('收藏儲存已取消'));
  });
}
async function desktop(method,payload){const result=await window.rovDesktop.collection(method,payload);if(!result?.ok)throw Error(result?.error||'本機收藏無法儲存');return result.value;}
const isDesktop=()=>typeof window.rovDesktop?.collection==='function';
function blobToImage(blob){return new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve({mime:blob.type,data:String(reader.result).split(',')[1]});reader.onerror=()=>reject(reader.error);reader.readAsDataURL(blob);});}
function imageToBlob(image){
  if(!image||!['image/png','image/jpeg'].includes(image.mime)||typeof image.data!=='string'||image.data.length>Math.ceil(COLLECTION_LIMITS.image/3)*4||(image.data.length%4!==0||!/^[A-Za-z0-9+/]*={0,2}$/.test(image.data)))fail('備份圖片格式無效');
  const binary=atob(image.data),bytes=new Uint8Array(binary.length);for(let i=0;i<binary.length;i++)bytes[i]=binary.charCodeAt(i);return new Blob([bytes],{type:image.mime});
}
export function downloadCollectionFile(filename,blob){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=filename;a.click();setTimeout(()=>URL.revokeObjectURL(url),5000);}
function photoFallback(input,error){
  if(!(input.blob instanceof Blob))return;
  const toast=document.createElement('section');toast.className='collection-save-fallback';toast.setAttribute('role','alert');
  Object.assign(toast.style,{position:'fixed',bottom:'18px',right:'18px',maxWidth:'380px',padding:'18px',background:'#172932',border:'1px solid #edcb64',color:'#eff5ed',zIndex:'10000',font:'14px/1.6 system-ui',boxShadow:'0 8px 30px #0008'});
  const text=document.createElement('p');text.textContent=`照片尚未存入收藏：${error.message}。請先下載原圖備份。`;toast.append(text);
  const button=document.createElement('button');button.textContent='下載原圖與拍攝資料';toast.append(button);
  const guard=e=>{e.preventDefault();e.returnValue='';};window.addEventListener('beforeunload',guard);
  button.onclick=()=>{const name=input.id||uid();downloadCollectionFile(`${name}.${input.blob.type==='image/jpeg'?'jpg':'png'}`,input.blob);downloadCollectionFile(`${name}.json`,new Blob([JSON.stringify({metadata:input.metadata,observation:input.observation??null},null,2)],{type:'application/json'}));window.removeEventListener('beforeunload',guard);toast.remove();};
  document.body.append(toast);
}
export async function savePhoto(input){
  try{return await serial(async()=>{const image=await photo(input);let saved;
    if(isDesktop()){saved=await desktop('savePhoto',{...image.record,image:await blobToImage(image.blob)});}
    else saved=await transact(true,(index,photos)=>{const added=addPhoto(index,image);if(added.added)photos.put(image.blob,added.record.id);const {hash,...record}=added.record;return record;});
    window.dispatchEvent(new Event('rov:collection-changed'));return saved;
  });}catch(error){photoFallback(input,error);error.fallback={blob:input.blob,metadata:input.metadata};throw error;}
}
export function saveResult(input){return serial(async()=>{const record=result(input);const saved=isDesktop()?await desktop('saveResult',record):await transact(true,index=>{const existing=index.results.find(r=>r.id===record.id);if(existing&&JSON.stringify(existing)===JSON.stringify(record))return existing;if(existing)record.id=uid();index.results.push(record);return record;});window.dispatchEvent(new Event('rov:collection-changed'));return saved;});}
export function listCollection(){return serial(async()=>isDesktop()?desktop('list'):transact(false,index=>({...index,photos:index.photos.map(({hash,...p})=>p)})));}
export async function getPhotoBlob(photoId){checkId(photoId);if(isDesktop())return imageToBlob(await desktop('readPhoto',photoId));const db=await database();return new Promise((resolve,reject)=>{const req=db.transaction('photos').objectStore('photos').get(photoId);req.onsuccess=()=>req.result?resolve(req.result):reject(Error('找不到原圖'));req.onerror=()=>reject(req.error);});}
export function setCover(category,photoId){return serial(async()=>{if(!categories.includes(category))fail('圖鑑類別無效');checkId(photoId);const saved=isDesktop()?await desktop('setCover',{category,photoId}):await transact(true,index=>{const guide=index.guides.find(g=>g.category===category);if(!guide||!index.photos.some(p=>p.id===photoId&&p.observation?.category===category))fail('此照片不是這一類的有效機載觀測');guide.photoId=photoId;return guide;});window.dispatchEvent(new Event('rov:collection-changed'));return saved;});}
export function exportCollection(){return serial(async()=>{
  let archive;
  if(isDesktop())archive=await desktop('export');
  else {const index=await transact(false,index=>index),photos=[];for(const {hash,...record}of index.photos)photos.push({...record,image:await blobToImage(await getPhotoBlob(record.id))});archive={format:'rov-personal-collection',version:1,exportedAt:new Date().toISOString(),photos,guides:index.guides,results:index.results};}
  const blob=new Blob([JSON.stringify(archive)],{type:'application/json'});if(blob.size>COLLECTION_LIMITS.archive)fail('匯出檔案超過 128 MiB');return blob;
});}
export async function importCollection(file){
  if(!(file instanceof Blob)||file.size>COLLECTION_LIMITS.archive)fail('備份檔案不可超過 128 MiB');
  const archive=JSON.parse(await file.text());
  if(archive?.format!=='rov-personal-collection'||archive.version!==1||!Array.isArray(archive.photos)||!Array.isArray(archive.guides)||!Array.isArray(archive.results)||archive.photos.length>COLLECTION_LIMITS.photos||archive.guides.length>categories.length||archive.results.length>COLLECTION_LIMITS.results)fail('不支援的收藏備份格式');
  return serial(async()=>{
    let saved;
    if(isDesktop())saved=await desktop('import',archive);
    else {
      const validEntry=entry=>{checkId(entry?.id);if(typeof entry.createdAt!=='string'||!Number.isFinite(Date.parse(entry.createdAt)))fail('備份拍攝／紀錄時間無效');return entry;};
      const images=[];for(const entry of archive.photos)images.push(await photo({...validEntry(entry),blob:imageToBlob(entry.image)}));
      const results=archive.results.map(entry=>result(validEntry(entry)));
      saved=await transact(true,(index,photos)=>{
        const mapping=new Map(),priorCategories=new Set(index.guides.map(g=>g.category));let addedPhotos=0,addedResults=0;
        for(const image of images){const oldId=image.record.id;if(mapping.has(oldId))fail('備份照片識別碼重複');const added=addPhoto(index,image);mapping.set(oldId,added.record.id);if(added.added){photos.put(image.blob,added.record.id);addedPhotos++;}}
        const guideCategories=new Set();for(const guide of archive.guides){if(guideCategories.has(guide.category)||!categories.includes(guide.category)||!mapping.has(guide.photoId)||!index.photos.some(p=>p.id===mapping.get(guide.photoId)&&p.observation?.category===guide.category))fail('備份圖鑑封面無效');guideCategories.add(guide.category);if(!priorCategories.has(guide.category))index.guides.find(g=>g.category===guide.category).photoId=mapping.get(guide.photoId);}
        for(const record of results){const existing=index.results.find(r=>r.id===record.id);if(existing&&JSON.stringify(existing)===JSON.stringify(record))continue;if(existing)record.id=uid();index.results.push(record);addedResults++;}
        return {addedPhotos,addedResults};
      });
    }
    window.dispatchEvent(new Event('rov:collection-changed'));return saved;
  });
}
