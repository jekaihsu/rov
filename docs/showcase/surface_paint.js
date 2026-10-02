import {DecalGeometry} from 'three/addons/geometries/DecalGeometry.js';
import {mergeGeometries} from 'three/addons/utils/BufferGeometryUtils.js';

const PALETTE = [['#f0c75e','黃色'],['#ee704f','橘紅'],['#62cfe2','青色'],['#eef3e8','白色']];

// NED positions and normals share the same rigid coordinate conversion.
export function installSurfacePaint({THREE, scene, camera, renderer, getState, getTargets, send, readOnly=false}) {
  const group = new THREE.Group(); group.name = 'Shared surface paint'; scene.add(group);
  group.userData.markCount=0;group.userData.mergeCount=0;group.userData.mergeMs=0;group.userData.mergeTotalMs=0;
  const records = new Map(), ray = new THREE.Raycaster(), pointer = new THREE.Vector2();
  const toWorld = p => new THREE.Vector3(-p[1], -p[2], p[0]);
  const toNED = p => [p.z, -p.x, -p.y];
  const canvas = renderer.domElement;
  let enabled=false, color=PALETTE[0][0], radius=.12, down=null, disposed=false;
  let cachedRoots=[], cachedTargets=[], targetScanAt=-Infinity;
  let batch=null,batchDirty=false;

  const stamp = document.createElement('canvas'); stamp.width=stamp.height=128;
  const ctx=stamp.getContext('2d');
  const gradient=ctx.createRadialGradient(64,64,42,64,64,63);
  gradient.addColorStop(0,'rgba(255,255,255,.94)');
  gradient.addColorStop(.7,'rgba(255,255,255,.85)');
  gradient.addColorStop(1,'rgba(255,255,255,0)');
  ctx.fillStyle=gradient;ctx.fillRect(0,0,128,128);
  const texture=new THREE.CanvasTexture(stamp); texture.colorSpace=THREE.SRGBColorSpace;
  const material=new THREE.MeshStandardMaterial({color:0xffffff,vertexColors:true,map:texture,transparent:true,opacity:.94,depthWrite:false,polygonOffset:true,polygonOffsetFactor:-4,roughness:1,metalness:0});

  const panel=document.createElement('details'); panel.className='surface-paint-tools';
  panel.innerHTML=`<summary>表面噴漆</summary><button type="button" class="paint-toggle" aria-pressed="false">噴漆標記：關閉</button>
    <div class="paint-colors" role="group" aria-label="噴漆顏色"></div>
    <label>半徑 <output>12 cm</output><input class="paint-radius" type="range" min="3" max="30" value="12" aria-label="噴漆半徑（公分）"></label>
    <p class="hint paint-status" role="status">靠近海床或結構物 3 m 內，再點選表面；F 標記畫面中央。</p>`;
  const style=document.createElement('style');
  style.textContent=`.surface-paint-tools{border-top:1px solid #263c48;margin-top:10px;padding-top:8px}.surface-paint-tools summary{cursor:pointer;font-size:13px;padding:4px 0}.surface-paint-tools .paint-toggle{width:100%;margin-top:8px}.surface-paint-tools .paint-toggle[aria-pressed="true"]{border-color:#f0c75e;color:#f0c75e}.surface-paint-tools .paint-colors{display:flex;gap:8px;margin:10px 0}.surface-paint-tools .paint-swatch{width:30px;height:26px;padding:0;border:2px solid transparent;border-radius:4px;box-shadow:inset 0 0 0 1px #0005}.surface-paint-tools .paint-swatch[aria-pressed="true"]{outline:2px solid #dff4ff;outline-offset:2px}.surface-paint-tools label{display:block;font-size:12px}.surface-paint-tools output{float:right}.surface-paint-tools input[type="range"]{display:block;width:100%}.surface-paint-reticle{position:absolute;left:50%;top:50%;width:16px;height:16px;margin:-8px;border:1px solid #f0c75e;border-radius:50%;pointer-events:none;z-index:3;box-shadow:0 0 3px #000}.surface-paint-reticle::after{content:'';position:absolute;left:7px;top:7px;width:2px;height:2px;background:#f0c75e}.surface-paint-reticle[hidden]{display:none}`;
  document.head.append(style);
  const host=document.querySelector('.mission-tools') || document.querySelector('aside');
  host?.append(panel);
  const toggle=panel.querySelector('.paint-toggle'), status=panel.querySelector('.paint-status');
  const reticle=document.createElement('div');reticle.className='surface-paint-reticle';reticle.hidden=true;canvas.parentElement?.append(reticle);
  function setEnabled(value){enabled=value&&!readOnly;toggle.setAttribute('aria-pressed',String(enabled));toggle.textContent=`噴漆標記：${enabled?'開啟':'關閉'}`;reticle.hidden=!enabled;}
  toggle.onclick=()=>setEnabled(!enabled);
  for(const [value,label] of PALETTE){
    const button=document.createElement('button');button.type='button';button.className='paint-swatch';button.style.background=value;
    button.setAttribute('aria-label',label);button.title=label;button.setAttribute('aria-pressed',String(value===color));
    button.onclick=()=>{color=value;panel.querySelectorAll('.paint-swatch').forEach(b=>b.setAttribute('aria-pressed',String(b===button)));};
    panel.querySelector('.paint-colors').append(button);
  }
  panel.querySelector('.paint-radius').oninput=e=>{radius=Number(e.target.value)/100;panel.querySelector('output').value=`${e.target.value} cm`;};
  if(readOnly){panel.hidden=true;}

  // Static receiving surfaces change on scene reset; the slow refresh also
  // catches asynchronously loaded scenery. Moving occluders are queried only
  // when the operator actually sprays, never on each network state.
  function targets(force=false){
    const roots=getTargets()||[],now=performance.now();
    if(!force&&now-targetScanAt<1000&&roots.length===cachedRoots.length&&roots.every((root,i)=>root===cachedRoots[i]))return cachedTargets;
    const result=[];const seen=new Set();
    for(const root of roots){root.traverse(object=>{if(object.isMesh&&object.userData.paintable===true&&!seen.has(object)){
      let visible=true;for(let ancestor=object;ancestor;ancestor=ancestor.parent)if(!ancestor.visible){visible=false;break;}
      if(visible){seen.add(object);object.updateWorldMatrix(true,false);result.push(object);}
    }});}
    cachedRoots=roots.slice();cachedTargets=result;targetScanAt=now;return result;
  }
  function blockedBefore(hit){
    const blockers=[];
    scene.traverseVisible(object=>{
      if(!object.isMesh||object===hit.object||object.userData.paintOcclusion===false)return;
      const mats=Array.isArray(object.material)?object.material:[object.material];
      // Ignore water, light cones, paint decals and other visual overlays.
      if(!mats.some(material=>material?.visible!==false&&material?.depthWrite!==false&&material?.opacity>.25))return;
      object.updateWorldMatrix(true,false);blockers.push(object);
    });
    ray.far=Math.max(0,hit.distance-.003);
    const blocked=ray.intersectObjects(blockers,false).length>0;
    ray.far=Infinity;return blocked;
  }
  function spray(x,y){
    if(!enabled||readOnly||disposed)return;
    const state=getState();if(!state?.pos){status.textContent='等待潛航連線。';return;}
    pointer.set(x,y);ray.setFromCamera(pointer,camera);
    const hit=ray.intersectObjects(targets(true),false)[0];
    if(!hit?.face){status.textContent='請對準海床或結構物表面；海水與生物無法噴漆。';return;}
    if(hit.point.distanceTo(toWorld(state.pos))>3){status.textContent='距離太遠：請移動到表面 3 m 內。';return;}
    if(blockedBefore(hit)){status.textContent='視線被機身、生物或其他物件擋住，請對準空曠表面。';return;}
    const normal=hit.face.normal.clone().applyNormalMatrix(new THREE.Matrix3().getNormalMatrix(hit.object.matrixWorld)).normalize();
    if(hit.point.y>=0){status.textContent='請在水下標記表面。';return;}
    send({type:'operation',action:'paint',pos:toNED(hit.point),normal:toNED(normal),radius,color});
    status.textContent='已送出表面標記，等待伺服器確認。';
  }
  function pointerDown(e){if(e.button===0)down={x:e.clientX,y:e.clientY,id:e.pointerId};}
  function pointerUp(e){const start=down;down=null;if(!start||start.id!==e.pointerId||Math.hypot(e.clientX-start.x,e.clientY-start.y)>5)return;
    const rect=canvas.getBoundingClientRect();spray((e.clientX-rect.left)/rect.width*2-1,1-(e.clientY-rect.top)/rect.height*2);
  }
  const cancel=()=>{down=null;};
  function keydown(e){if(e.code!=='KeyF'||e.repeat||e.ctrlKey||e.metaKey||e.altKey||!enabled)return;
    if(e.target instanceof Element && e.target.closest('input,select,textarea,button,[contenteditable="true"]'))return;
    e.preventDefault();spray(0,0);
  }
  canvas.addEventListener('pointerdown',pointerDown);canvas.addEventListener('pointerup',pointerUp);canvas.addEventListener('pointercancel',cancel);canvas.addEventListener('lostpointercapture',cancel);
  window.addEventListener('keydown',keydown);

  function remove(id){const old=records.get(id);if(old){if(old.geometry){old.geometry.dispose();batchDirty=true;group.userData.markCount--;}records.delete(id);}}
  function rebuildBatch(marks=[]){
    if(!batchDirty)return;
    const started=performance.now(),geometries=[];
    // Preserve server/replay order even when an earlier mark finished loading
    // later. One vertex-colored draw preserves cross-color alpha layering.
    for(const mark of marks){const geometry=records.get(mark.id)?.geometry;if(geometry)geometries.push(geometry);}
    if(batch){group.remove(batch);batch.geometry.dispose();batch=null;}
    if(geometries.length){
      const geometry=mergeGeometries(geometries,false);
      batch=new THREE.Mesh(geometry,material);batch.name='Surface paint batch';batch.renderOrder=2;group.add(batch);
    }
    batchDirty=false;group.userData.mergeCount++;
    group.userData.mergeMs=performance.now()-started;group.userData.mergeTotalMs+=group.userData.mergeMs;
  }
  const sameMark=(a,b)=>a&&a.color===b.color&&a.radius===b.radius&&a.pos[0]===b.pos[0]&&a.pos[1]===b.pos[1]&&a.pos[2]===b.pos[2]&&a.normal[0]===b.normal[0]&&a.normal[1]===b.normal[1]&&a.normal[2]===b.normal[2];
  function update(state){
    if(disposed)return;
    if(!state){for(const id of records.keys())remove(id);rebuildBatch();cachedRoots=[];cachedTargets=[];targetScanAt=-Infinity;return;}
    const marks=state.paint_marks||[],keep=new Set(),now=performance.now();let added=false,surfaces=null,built=0;
    for(const mark of marks){
      if(!mark||!Array.isArray(mark.pos)||!Array.isArray(mark.normal)||mark.pos.length!==3||mark.normal.length!==3||!mark.pos.every(Number.isFinite)||!mark.normal.every(Number.isFinite)||!Number.isFinite(mark.radius)||mark.radius<.03||mark.radius>.3||!PALETTE.some(([value])=>value===mark.color))continue;
      keep.add(mark.id);
      const prior=records.get(mark.id);
      if(sameMark(prior?.mark,mark)&&(prior.geometry||now<prior.retryAt))continue;
      // Yield between indivisible decal projections to keep bulk joins/replays
      // responsive. A single complex projection may itself exceed this budget.
      if(built>=24||(built>0&&performance.now()-now>=6))continue;
      built++;
      remove(mark.id);
      const record={mark:{pos:mark.pos.slice(),normal:mark.normal.slice(),color:mark.color,radius:mark.radius},geometry:null,retryAt:now+1000};
      records.set(mark.id,record);
      const position=toWorld(mark.pos),normal=toWorld(mark.normal).normalize();
      const orientation=new THREE.Euler().setFromQuaternion(new THREE.Quaternion().setFromUnitVectors(new THREE.Vector3(0,0,1),normal));
      ray.set(position.clone().addScaledVector(normal,.08),normal.clone().negate());ray.near=0;ray.far=.18;
      surfaces ||= targets();
      const surface=ray.intersectObjects(surfaces,false)[0];ray.far=Infinity;
      if(!surface)continue; // Retry after the scene geometry becomes available.
      const geometry=new DecalGeometry(surface.object,position,orientation,new THREE.Vector3(mark.radius*2,mark.radius*2,.06));
      if(!geometry.attributes.position.count){geometry.dispose();continue;}
      const tint=new THREE.Color(mark.color),colors=new Float32Array(geometry.attributes.position.count*3);
      for(let i=0;i<colors.length;i+=3){colors[i]=tint.r;colors[i+1]=tint.g;colors[i+2]=tint.b;}
      geometry.setAttribute('color',new THREE.BufferAttribute(colors,3));
      record.geometry=geometry;batchDirty=true;group.userData.markCount++;added=true;
    }
    for(const id of records.keys())if(!keep.has(id))remove(id);
    rebuildBatch(marks);
    if(added&&!readOnly)status.textContent=`表面標記已同步 · 共 ${marks.length} 筆`;
  }
  function dispose(){disposed=true;for(const id of records.keys())remove(id);rebuildBatch();material.dispose();texture.dispose();scene.remove(group);panel.remove();style.remove();reticle.remove();
    canvas.removeEventListener('pointerdown',pointerDown);canvas.removeEventListener('pointerup',pointerUp);canvas.removeEventListener('pointercancel',cancel);canvas.removeEventListener('lostpointercapture',cancel);window.removeEventListener('keydown',keydown);
  }
  return {update,dispose};
}
