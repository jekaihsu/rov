export const toolCatalogue=await (await fetch('tool_catalogue.json')).json();
export const toolsById=new Map(toolCatalogue.tools.map(t=>[t.id,t]));
let saved={version:1,models:{}};
try{saved=window.rovDesktop?.toolPresets?await window.rovDesktop.toolPresets('read'):JSON.parse(localStorage.getItem('rov.toolPresets')||'null')||saved;}catch{}
const copy=v=>JSON.parse(JSON.stringify(v));
export function getLoadout(model){const value=saved.models?.[model]?.current;return copy(Array.isArray(value)&&!checkLoadout(model,value)?value:toolCatalogue.vehicles[model].default_loadout);}
export function getPresets(model){return copy(saved.models?.[model]?.presets||{});}
export function checkLoadout(model,loadout){
  const def=toolCatalogue.vehicles[model],seen=new Set(),ids=new Set();let mass=0,power=0;
  for(const item of loadout){const tool=toolsById.get(item.tool),mount=def.mounts.find(m=>m.id===item.slot);
    if(!tool||!mount||seen.has(item.slot)||ids.has(item.tool))return '工具或掛點重複';
    if(!tool.models.includes(model)||tool.slot_kind!==mount.kind)return '工具與掛點不相容';
    if(tool.mass_kg>mount.max_mass_kg)return '掛點負載超限';
    seen.add(item.slot);ids.add(item.tool);mass+=tool.mass_kg;power+=tool.power_w;
  }
  if(mass>def.payload_kg)return `搭載重量超過 ${def.payload_kg} kg`;
  if(power>def.power_budget_w)return `工具功率超過 ${def.power_budget_w} W`;
  if(loadout.some(i=>toolsById.get(i.tool).requires.some(r=>!ids.has(r))))return '液壓機械臂需要液壓動力組';
  return null;
}
export async function saveLoadout(model,loadout,name){
  const error=checkLoadout(model,loadout);if(error)throw Error(error);
  const next=copy(saved);next.version=1;next.models??={};next.models[model]??={presets:{}};
  next.models[model].current=copy(loadout);
  if(name){if(Object.keys(next.models[model].presets).length>=12&&!next.models[model].presets[name])throw Error('每機型最多 12 組配置');next.models[model].presets[name.slice(0,40)]=copy(loadout);}
  if(window.rovDesktop?.toolPresets)await window.rovDesktop.toolPresets('write',next);
  else localStorage.setItem('rov.toolPresets',JSON.stringify(next));
  saved=next;dispatchEvent(new CustomEvent('rov:loadout-changed',{detail:{model,loadout:copy(loadout)}}));
}
