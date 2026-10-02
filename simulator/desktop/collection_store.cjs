// Local collection only. Renderer IDs never become filesystem paths.
const fs=require('node:fs/promises');
const path=require('node:path');
const {randomUUID,createHash}=require('node:crypto');
const CATEGORIES=['coral','seastar','seagrass','kelp','fish_school'];
const LIMITS={image:12*1024*1024,total:80*1024*1024,index:4*1024*1024,archive:128*1024*1024,photos:500,results:2000};
const empty=()=>({version:1,photos:[],guides:[],results:[]});
const fail=message=>{throw Error(message);};
const id=value=>typeof value==='string'&&/^[A-Za-z0-9_-]{1,96}$/.test(value)?value:fail('收藏識別碼無效');
function json(value,max=32768){
  const visit=(v,depth=0)=>{
    if(depth>12)fail('收藏資料層級過深');
    if(v===null||typeof v==='boolean')return;
    if(typeof v==='number'){if(!Number.isFinite(v))fail('收藏資料數值無效');return;}
    if(typeof v==='string'){if(v.length>8192)fail('收藏文字過長');return;}
    if(typeof v!=='object'||(!Array.isArray(v)&&Object.getPrototypeOf(v)!==Object.prototype))fail('收藏資料格式無效');
    if(Object.keys(v).length>1024)fail('收藏資料項目過多');
    for(const [key,item]of Object.entries(v)){if(['__proto__','constructor','prototype'].includes(key))fail('收藏欄位無效');visit(item,depth+1);}
  };
  visit(value);const text=JSON.stringify(value);if(Buffer.byteLength(text)>max)fail('收藏資料過大');return JSON.parse(text);
}
function observation(value,metadata){
  if(value===null||value===undefined)return null;
  const clean=json(value);
  if(!CATEGORIES.includes(clean.category)||metadata.cameraMode!=='onboard')fail('圖鑑僅接受機載視角的有效觀測');
  return clean;
}
function photo(input){
  if(!input||typeof input!=='object')fail('照片格式無效');
  const metadata=json(input.metadata??{});if(!metadata||Array.isArray(metadata)||typeof metadata!=='object')fail('照片資料格式無效');const obs=observation(input.observation,metadata),image=input.image;
  if(!image||!['image/png','image/jpeg'].includes(image.mime)||typeof image.data!=='string'||image.data.length>Math.ceil(LIMITS.image/3)*4||(image.data.length%4!==0||!/^[A-Za-z0-9+/]*={0,2}$/.test(image.data)))fail('僅支援 12 MiB 以下 PNG／JPEG 原圖');
  const bytes=Buffer.from(image.data,'base64');
  const signature=image.mime==='image/png'?bytes.subarray(0,8).equals(Buffer.from([137,80,78,71,13,10,26,10])):bytes[0]===255&&bytes[1]===216&&bytes[2]===255;
  if(!signature||!bytes.length||bytes.length>LIMITS.image)fail('照片格式或大小無效');
  const createdAt=typeof input.createdAt==='string'&&Number.isFinite(Date.parse(input.createdAt))?new Date(input.createdAt).toISOString():new Date().toISOString();
  return {record:{id:input.id?id(input.id):randomUUID(),createdAt,metadata,observation:obs,mime:image.mime,bytes:bytes.length,hash:createHash('sha256').update(bytes).digest('hex')},data:bytes};
}
function result(input){const clean=json(input,65536);return {...clean,id:clean.id?id(clean.id):randomUUID(),createdAt:typeof clean.createdAt==='string'&&Number.isFinite(Date.parse(clean.createdAt))?new Date(clean.createdAt).toISOString():new Date().toISOString()};}
function equivalent(a,b){return a.hash===b.hash&&JSON.stringify(a.metadata)===JSON.stringify(b.metadata)&&JSON.stringify(a.observation)===JSON.stringify(b.observation);}
function validateIndex(index){
  if(index?.version!==1||!Array.isArray(index.photos)||!Array.isArray(index.guides)||!Array.isArray(index.results))fail('收藏索引格式無效');
  if(index.photos.length>LIMITS.photos||index.results.length>LIMITS.results)fail('收藏數量已達上限，請先匯出備份');
  const seen=new Set();let size=0;
  for(const p of index.photos){id(p.id);if(seen.has(p.id)||!/^([a-f0-9]{64})$/.test(p.hash)||!['image/png','image/jpeg'].includes(p.mime)||!Number.isInteger(p.bytes)||p.bytes<=0||p.bytes>LIMITS.image)fail('收藏照片索引無效');seen.add(p.id);size+=p.bytes;json(p.metadata);observation(p.observation,p.metadata);}
  if(size>LIMITS.total)fail('原圖總容量已達 80 MiB；不會自動刪除舊照片');
  const categories=new Set();for(const guide of index.guides){if(categories.has(guide.category)||!CATEGORIES.includes(guide.category)||!index.photos.some(p=>p.id===guide.photoId&&p.observation?.category===guide.category))fail('圖鑑封面資料無效');categories.add(guide.category);}
  const resultIds=new Set();for(const r of index.results){result(r);if(resultIds.has(r.id))fail('工程紀錄識別碼重複');resultIds.add(r.id);}
  if(Buffer.byteLength(JSON.stringify(index))>LIMITS.index)fail('收藏文字資料已達上限，請先匯出備份');
  return index;
}

class CollectionStore{
  constructor(directory){this.directory=path.resolve(directory);this.indexPath=path.join(this.directory,'index.json');this.photoDirectory=path.join(this.directory,'photos');this.queue=Promise.resolve();}
  serial(work){const job=this.queue.then(work);this.queue=job.catch(()=>{});return job;}
  async read(){try{const stat=await fs.stat(this.indexPath);if(stat.size>LIMITS.index)fail('收藏索引過大');return validateIndex(JSON.parse(await fs.readFile(this.indexPath,'utf8')));}catch(error){if(error.code==='ENOENT')return empty();throw error;}}
  photoPath(record){return path.join(this.photoDirectory,`${record.hash}.${record.mime==='image/png'?'png':'jpg'}`);}
  async commit(index,images=[]){
    validateIndex(index);await fs.mkdir(this.photoDirectory,{recursive:true});
    const created=[],temporary=`${this.indexPath}.tmp-${randomUUID()}`;
    try{
      for(const image of images){
        const destination=this.photoPath(image.record);
        try{const existing=await fs.readFile(destination);if(existing.length!==image.data.length||createHash('sha256').update(existing).digest('hex')!==image.record.hash)fail('既有原圖不完整，請保留備份後修復收藏');continue;}catch(error){if(error.code!=='ENOENT')throw error;}
        const imageTemporary=`${destination}.tmp-${randomUUID()}`;
        try{const handle=await fs.open(imageTemporary,'wx');try{await handle.writeFile(image.data);await handle.sync();}finally{await handle.close();}await fs.rename(imageTemporary,destination);created.push(destination);}catch(error){await fs.unlink(imageTemporary).catch(()=>{});throw error;}
      }
      const handle=await fs.open(temporary,'wx');try{await handle.writeFile(JSON.stringify(index));await handle.sync();}finally{await handle.close();}
      await fs.rename(temporary,this.indexPath);
    }catch(error){await fs.unlink(temporary).catch(()=>{});for(const filename of created)await fs.unlink(filename).catch(()=>{});throw error;}
  }
  add(index,image){
    const existing=index.photos.find(p=>p.id===image.record.id);
    if(existing&&equivalent(existing,image.record))return {record:existing,added:false};
    if(existing){const priorCopy=index.photos.find(p=>equivalent(p,image.record));if(priorCopy)return {record:priorCopy,added:false};}
    if(existing)image.record.id=randomUUID();
    index.photos.push(image.record);
    const category=image.record.observation?.category;
    if(category&&!index.guides.some(g=>g.category===category))index.guides.push({category,photoId:image.record.id,unlockedAt:image.record.createdAt});
    return {record:image.record,added:true};
  }
  list(){return this.serial(async()=>{const value=await this.read();return {...value,photos:value.photos.map(({hash,...p})=>p)};});}
  readPhoto(photoId){return this.serial(async()=>{const value=await this.read(),record=value.photos.find(p=>p.id===id(photoId));if(!record)fail('找不到照片');const bytes=await fs.readFile(this.photoPath(record));if(bytes.length!==record.bytes||createHash('sha256').update(bytes).digest('hex')!==record.hash)fail('照片檔案不完整');return {mime:record.mime,data:bytes.toString('base64')};});}
  savePhoto(input){return this.serial(async()=>{const image=photo(input),index=await this.read(),added=this.add(index,image);if(added.added)await this.commit(index,[image]);const {hash,...record}=added.record;return record;});}
  saveResult(input){return this.serial(async()=>{const index=await this.read(),record=result(input),existing=index.results.find(r=>r.id===record.id);if(existing&&JSON.stringify(existing)===JSON.stringify(record))return existing;if(existing)record.id=randomUUID();index.results.push(record);await this.commit(index);return record;});}
  setCover({category,photoId}){return this.serial(async()=>{const index=await this.read();if(!CATEGORIES.includes(category)||!index.photos.some(p=>p.id===id(photoId)&&p.observation?.category===category))fail('此照片不是這一類的有效機載觀測');const guide=index.guides.find(g=>g.category===category);if(!guide)fail('此圖鑑尚未解鎖');guide.photoId=photoId;await this.commit(index);return guide;});}
  export(){return this.serial(async()=>{const index=await this.read(),photos=[];for(const {hash,...p}of index.photos){const record=index.photos.find(item=>item.id===p.id),data=await fs.readFile(this.photoPath(record));if(data.length!==p.bytes||createHash('sha256').update(data).digest('hex')!==hash)fail('原圖檔案不完整，無法匯出');photos.push({...p,image:{mime:p.mime,data:data.toString('base64')}});}const archive={format:'rov-personal-collection',version:1,exportedAt:new Date().toISOString(),photos,guides:index.guides,results:index.results};if(Buffer.byteLength(JSON.stringify(archive))>LIMITS.archive)fail('匯出檔案超過 128 MiB');return archive;});}
  import(archive){return this.serial(async()=>{
    if(Buffer.byteLength(JSON.stringify(archive))>LIMITS.archive||archive?.format!=='rov-personal-collection'||archive.version!==1||!Array.isArray(archive.photos)||!Array.isArray(archive.guides)||!Array.isArray(archive.results)||archive.photos.length>LIMITS.photos||archive.guides.length>CATEGORIES.length||archive.results.length>LIMITS.results)fail('不支援的收藏備份格式或檔案過大');
    const entry=record=>{id(record?.id);if(typeof record.createdAt!=='string'||!Number.isFinite(Date.parse(record.createdAt)))fail('備份拍攝／紀錄時間無效');return record;};
    const images=archive.photos.map(p=>photo(entry(p))),results=archive.results.map(r=>result(entry(r))),index=await this.read(),mapping=new Map(),writes=[],priorCategories=new Set(index.guides.map(g=>g.category));let addedResults=0;
    for(const image of images){const oldId=image.record.id;if(mapping.has(oldId))fail('備份照片識別碼重複');const added=this.add(index,image);mapping.set(oldId,added.record.id);if(added.added)writes.push(image);}
    const guideCategories=new Set();for(const guide of archive.guides){if(guideCategories.has(guide.category)||!CATEGORIES.includes(guide.category)||!mapping.has(guide.photoId)||!index.photos.some(p=>p.id===mapping.get(guide.photoId)&&p.observation?.category===guide.category))fail('備份圖鑑封面無效');guideCategories.add(guide.category);if(!priorCategories.has(guide.category))index.guides.find(g=>g.category===guide.category).photoId=mapping.get(guide.photoId);}
    for(const record of results){const existing=index.results.find(r=>r.id===record.id);if(existing&&JSON.stringify(existing)===JSON.stringify(record))continue;if(existing)record.id=randomUUID();index.results.push(record);addedResults++;}
    await this.commit(index,writes);return {addedPhotos:writes.length,addedResults};
  });}
}
module.exports={CollectionStore,CATEGORIES,LIMITS};
