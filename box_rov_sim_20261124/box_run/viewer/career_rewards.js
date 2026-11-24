import {loadCareer} from './career_store.js';
export function installCareerRewards({readOnly=false}={}){
  if(readOnly)return;
  const css=document.createElement('link');css.rel='stylesheet';css.href=new URL('./career.css',import.meta.url);document.head.append(css);
  const toast=document.createElement('div');toast.className='career-toast';toast.hidden=true;toast.setAttribute('role','status');document.body.append(toast);
  let previous=null,queue=Promise.resolve(),timer;
  const update=()=>{queue=queue.then(async()=>{const {summary}=await loadCareer();if(previous&&summary.earned>previous.earned){
    const unlocked=summary.achievements.filter(a=>a.unlocked&&!previous.achievements.find(p=>p.id===a.id)?.unlocked);
    toast.textContent=`探索點數 +${summary.earned-previous.earned}${unlocked.length?' · 成就：'+unlocked.map(a=>a.name).join('、'):''}`;toast.hidden=false;clearTimeout(timer);timer=setTimeout(()=>toast.hidden=true,6500);
  }previous=summary;}).catch(error=>console.warn('Career status:',error.message));};
  update();window.addEventListener('rov:collection-changed',update);
}
