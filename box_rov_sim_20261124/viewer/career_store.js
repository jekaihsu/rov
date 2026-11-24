import {listCollection,readCareer,writeCareer} from './collection_store.js';
import {EMPTY_CAREER,validateCareer,careerSummary,changeCareer} from './career_rules.js';
export async function loadCareer(){const collection=await listCollection(),profile=validateCareer(await readCareer()||EMPTY_CAREER());return {profile,summary:careerSummary(collection,profile),collection};}
let queue=Promise.resolve();
export function updateCareer(action){
  const job=queue.then(async()=>{
    for(let retry=0;retry<4;retry++){
      const {profile,collection}=await loadCareer(),next=changeCareer(profile,collection,action);
      if(next.revision===profile.revision)return loadCareer();
      if(await writeCareer(next,profile.revision)){window.dispatchEvent(new Event('rov:career-changed'));return loadCareer();}
    }
    throw Error('另一個視窗正在更新生涯，請再試一次');
  });queue=job.catch(()=>{});return job;
}
