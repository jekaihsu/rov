// Narrow renderer bridge; all privileged requests are checked again in main.
const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('rovDesktop',Object.freeze({
  display(settings){return ipcRenderer.invoke('rov:display',settings);},
  steamStatus(){return ipcRenderer.invoke('rov:steam','status');},
  steamEvent(id){return ipcRenderer.invoke('rov:steam','event',id);},
  steamStat(name,value){return ipcRenderer.invoke('rov:steam','stat',name,value);},
  collection(method,payload){if(!['list','readPhoto','savePhoto','saveResult','setCover','export','import'].includes(method))return Promise.reject(Error('不支援的收藏操作'));return ipcRenderer.invoke('rov:collection',method,payload);},
  rememberQuality(quality){if(['auto','performance','medium','high'].includes(quality))ipcRenderer.send('rov:quality-selected',quality);},
  rememberModel(model){if(['x1','bluerov2_heavy','falcon'].includes(model))ipcRenderer.send('rov:model-selected',model);}
}));
