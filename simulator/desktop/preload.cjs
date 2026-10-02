const {contextBridge,ipcRenderer}=require('electron');
contextBridge.exposeInMainWorld('rovDesktop',Object.freeze({
  collection(method,payload){if(!['list','readPhoto','savePhoto','saveResult','setCover','export','import'].includes(method))return Promise.reject(Error('不支援的收藏操作'));return ipcRenderer.invoke('rov:collection',method,payload);},
  rememberQuality(quality){if(['auto','performance','medium','high'].includes(quality))ipcRenderer.send('rov:quality-selected',quality);},
  rememberModel(model){if(['x1','bluerov2_heavy','falcon'].includes(model))ipcRenderer.send('rov:model-selected',model);}
}));
