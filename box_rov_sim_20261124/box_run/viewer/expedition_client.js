import {savePhoto,saveResult} from './collection_store.js';
const uniqueId=()=>globalThis.crypto?.randomUUID?.()||`photo-${Date.now()}-${Math.random().toString(36).slice(2)}`;

// Photos remain local. Only a small visibility report crosses the room socket.
export function installExpeditionClient({send,capture,getState,getWorld,getSession,notify,readOnly=false}){
  const pending=new Map(),recorded=new Set();
  let busy=false;
  function receive(message){
    const id=message.photo_id||message.observation?.photo_id;
    if(id&&pending.has(id)){
      const request=pending.get(id);clearTimeout(request.timer);pending.delete(id);request.resolve(message);
    }
  }
  async function takePhoto({download=false,recordCamera=true}={}){
    if(busy)return;busy=true;
    const state=getState(),world=getWorld(),photoId=uniqueId();
    try{
      const shot=await capture();
      if(!shot.blob)throw Error('照片擷取失敗，請再試一次。');
      const metadata=JSON.parse(JSON.stringify({createdAt:new Date().toISOString(),cameraMode:shot.view,scene:world?.scenario?.key,
        sceneName:world?.scenario?.name,depth:state?.depth??state?.pos?.[2],vehicle_id:state?.vehicle_id,model_id:state?.model_id,pos:state?.pos,
        photographer:getSession()?.player_id,pose:{t:state?.t,pos:state?.pos,q:state?.q}}));
      let observation=null,reason=shot.evidence?.reason||'已保存紀念照片。';
      if(!readOnly&&state?.mission?.mode==='expedition'){
        if(shot.view==='onboard'&&shot.evidence?.ok){
          notify('正在確認取景與觀测目標…');
          const response=await new Promise(resolve=>{
            const timer=setTimeout(()=>{pending.delete(photoId);resolve({message:'觀測確認逾時，照片已保留為紀念照。'});},10000);
            pending.set(photoId,{resolve,timer});
            if(!send({type:'operation',action:'observation_photo',photo_id:photoId,...shot.evidence})){
              clearTimeout(timer);pending.delete(photoId);resolve({message:'目前離線，照片保留為紀念照。'});
            }
          });
          const result=response.observation;
          if(result?.accepted&&['coral','seastar','seagrass','kelp','fish_school'].includes(result.entry?.category))observation=result.entry;
          reason=result?.reason||response.message||'已保存照片。';
        }
      }else if(!readOnly&&recordCamera){
        send({type:'operation',action:'mission_photo'});
      }
      await savePhoto({id:photoId,blob:shot.blob,metadata,observation});
      notify(observation?'觀測成功，已登錄圖鑑與照片。':reason);
      if(download){
        downloadBlob(`ROV-${photoId}.png`,shot.blob);
        downloadBlob(`ROV-${photoId}-pose.json`,new Blob([JSON.stringify(metadata.pose,null,2)],{type:'application/json'}));
      }
      return {id:photoId,observation,reason};
    }catch(error){notify(error.message||'照片保存失敗，請下載原圖。');}
    finally{busy=false;}
  }
  function update(state){
    if(readOnly)return;
    for(const result of state.expedition?.results||[]){
      if(!result.id||recorded.has(result.id))continue;
      const playerId=getSession()?.player_id;
      const members=result.participant_ids||result.player_ids||[];
      if(members.length&&!members.includes(playerId))continue;
      recorded.add(result.id);
      const entry=JSON.parse(JSON.stringify({...result,title:result.label,scenario:result.scene,duration_s:result.elapsed,createdAt:result.created_at,success:true,rating:result.grade}));
      saveResult(entry).catch(error=>{notify('工程紀錄尚未保存：'+error.message);setTimeout(()=>recorded.delete(result.id),30000);});
    }
  }
  return {takePhoto,receive,update,get busy(){return busy;}};
}

function downloadBlob(name,blob){
  const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download=name;a.click();
  setTimeout(()=>URL.revokeObjectURL(url),5000);
}
