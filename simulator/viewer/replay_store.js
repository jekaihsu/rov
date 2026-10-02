// Keep the most recently imported mission locally so navigating away from the
// file picker does not invalidate a document-owned blob URL.
function database(){return new Promise((resolve,reject)=>{
  const request=indexedDB.open('rov-replays',1);
  request.onupgradeneeded=()=>request.result.createObjectStore('missions');
  request.onsuccess=()=>resolve(request.result);request.onerror=()=>reject(request.error);
});}
export async function saveReplay(data){
  const db=await database(),id=crypto.randomUUID();
  try{await new Promise((resolve,reject)=>{
    const tx=db.transaction('missions','readwrite');
    tx.objectStore('missions').clear();tx.objectStore('missions').put(data,id);
    tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);tx.onabort=()=>reject(tx.error||Error('回放儲存已中止'));
  });return id;}finally{db.close();}
}
export async function readReplay(id){
  const db=await database();
  try{return await new Promise((resolve,reject)=>{
    const request=db.transaction('missions').objectStore('missions').get(id);
    request.onsuccess=()=>request.result?resolve(request.result):reject(Error('找不到此回放，請重新匯入任務檔案。'));
    request.onerror=()=>reject(request.error);
  });}finally{db.close();}
}
