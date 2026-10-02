"""Real-browser surface paint, multiplayer appearance and recorded replay smoke."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parents[1] / 'output' / 'paint-validation'
OUT.mkdir(parents=True, exist_ok=True)
BASE = 'http://127.0.0.1:8093/'
QUERY = f'?ws=ws://127.0.0.1:8793&room=paint_{int(time.time())}&model=bluerov2_heavy&scene=seagrass_meadow'
PAINT_COUNT = "window.__viewer.scene.getObjectByName('Shared surface paint')?.userData.markCount||0"
STICKER_COUNT = "(()=>{let count=0;window.__viewer.scene.traverse(o=>{if(o.name==='Vehicle stickers')count+=o.children.length;});return count;})()"
results = {}

with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    peer = browser.new_page(viewport={'width':900,'height':700})
    errors = []
    for tab in [page, peer]:
        tab.on('pageerror', lambda error: errors.append(str(error)))
        tab.set_default_timeout(90000)
    try:
        page.goto(BASE+QUERY)
        page.wait_for_function('window.__menu?.ready')
        page.select_option('#menuSticker','hazard')
        page.wait_for_function('window.__menu.stickerMeshes>0')
        results['menu_sticker_meshes'] = page.evaluate('window.__menu.stickerMeshes')
        page.screenshot(path=str(OUT/'sticker-preview.png'))
        page.select_option('#menuScene','seagrass_meadow')
        page.locator('details').filter(has=page.locator('#menuPad')).locator('summary').click()
        page.select_option('#menuPad','keyboard')
        page.select_option('#menuControl','ROV_USA')
        page.uncheck('#menuIntro')
        page.click('#startDive')
        page.wait_for_function('window.__viewer?.S?.appearance?.sticker==="hazard" && window.__modelLoaded && window.__viewer.W.scenario.key==="seagrass_meadow"')
        page.wait_for_function(STICKER_COUNT+'>0')
        results['live_sticker_meshes'] = page.evaluate(STICKER_COUNT)
        peer.goto(BASE+QUERY+'&play=1&nointro&sticker=dive')
        peer.wait_for_function('window.__viewer?.S?.vehicles?.length===2 && window.__modelLoaded')
        page.wait_for_function('window.__viewer.S.vehicles.length===2')
        peer.wait_for_function(STICKER_COUNT+'>=4')
        results['peer_sticker_meshes'] = peer.evaluate(STICKER_COUNT)
        results['peer_appearance'] = peer.evaluate('window.__viewer.S.vehicles.map(v=>v.appearance.sticker)')
        print('Menu, own and peer stickers passed', flush=True)

        page.bring_to_front()
        page.click('.surface-paint-tools summary')
        page.click('.paint-toggle')
        page.evaluate("window.__viewer.setCam('top')")
        # At deployment the actual seabed is too far: no server mark may appear.
        page.locator('canvas').first.click(position={'x':20,'y':20})
        page.keyboard.press('f')
        assert '距離太遠' in page.locator('.paint-status').inner_text()
        assert page.evaluate('window.__viewer.S.paint_marks.length') == 0
        results['far_surface_rejected'] = True
        page.click('#bLock')
        page.keyboard.down('q')
        page.wait_for_function("""()=>{
          const v=window.__viewer;if(!v?.S)return false;
          const start=new v.THREE.Vector3(-v.S.pos[1],-v.S.pos[2],v.S.pos[0]);
          const meshes=[];v.scene.traverse(o=>{if(o.isMesh&&o.userData.paintable&&o.visible)meshes.push(o);});
          const hits=new v.THREE.Raycaster(start,new v.THREE.Vector3(0,-1,0)).intersectObjects(meshes,false);
          return hits.length&&hits[0].distance<2.2;
        }""", timeout=180000)
        page.keyboard.up('q')
        page.click('#bLock')
        page.click('#btnPause')
        page.wait_for_function('window.__viewer.S.paused')
        results['paint_vehicle_position'] = page.evaluate('window.__viewer.S.pos')
        # Blur controls before F, as typing in a button/form must never spray.
        page.evaluate('document.activeElement.blur()')
        page.keyboard.press('f')
        assert '擋住' in page.locator('.paint-status').inner_text()
        assert page.evaluate('window.__viewer.S.paint_marks.length') == 0
        results['vehicle_occlusion_rejected'] = True
        # Shift the real top camera's projection off the ROV onto exposed sand.
        # Its direction still follows the normal viewer camera update.
        page.evaluate("""()=>{
          const c=window.__viewer.camera,rect=document.querySelector('.viewport canvas').getBoundingClientRect();
          c.setViewOffset(rect.width,rect.height,35,0,rect.width,rect.height);
        }""")
        page.keyboard.press('f')
        page.wait_for_function('window.__viewer.S.paint_marks.length===1')
        page.wait_for_function(PAINT_COUNT+'===1')
        peer.wait_for_function('window.__viewer.S.paint_marks.length===1')
        peer.wait_for_function(PAINT_COUNT+'===1')
        results['shared_first_mark'] = page.evaluate('window.__viewer.S.paint_marks[0]')
        assert results['shared_first_mark'] == peer.evaluate('window.__viewer.S.paint_marks[0]')
        print('Real terrain F paint and peer rendering passed', flush=True)

        canvas=page.locator('.viewport canvas').first
        box=canvas.bounding_box()
        page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
        page.mouse.down();page.mouse.move(box['x']+box['width']/2+40,box['y']+box['height']/2+20);page.mouse.up()
        assert page.evaluate('window.__viewer.S.paint_marks.length')==1
        canvas.click(position={'x':box['width']/2+8,'y':box['height']/2})
        page.wait_for_function('window.__viewer.S.paint_marks.length===2')
        page.wait_for_function(PAINT_COUNT+'===2')
        peer.wait_for_function(PAINT_COUNT+'===2')
        results['click_and_drag_filter'] = True
        page.screenshot(path=str(OUT/'terrain-paint.png'))

        results['paint_performance'] = page.evaluate("""async()=>{
          const {installSurfacePaint}=await import('./surface_paint.js');
          const v=window.__viewer,scene=new v.THREE.Scene(),targets=[];
          v.scene.traverseVisible(o=>{if(o.isMesh&&o.userData.paintable)targets.push(o);});
          const module=installSurfacePaint({THREE:v.THREE,scene,camera:v.camera,renderer:{domElement:document.querySelector('.viewport canvas')},getState:()=>v.S,getTargets:()=>targets,send:()=>{throw Error('Readonly emitted');},readOnly:true});
          const colors=['#f0c75e','#ee704f','#62cfe2','#eef3e8'];
          const marks=Array.from({length:300},(_,i)=>({...v.S.paint_marks[0],id:'bench-'+i,color:colors[i%4]}));
          try{
            const group=scene.getObjectByName('Shared surface paint'),start=performance.now();
            let peakBatchMs=0,batches=0;
            const advance=()=>{const before=performance.now();module.update({paint_marks:marks});peakBatchMs=Math.max(peakBatchMs,performance.now()-before);batches++;};
            advance();const firstBatch=group.userData.markCount;
            for(let i=0;i<1000&&group.userData.markCount<300;i++)advance();
            const buildMs=performance.now()-start,materials=new Set(group.children.map(m=>m.material)).size;
            const drawCalls=group.children.length,mergeCount=group.userData.mergeCount,mergeTotalMs=group.userData.mergeTotalMs;
            const vertices=group.children[0].geometry.getAttribute('position').count,verticesPerMark=vertices/300;
            const colors=new Set(),attribute=group.children[0].geometry.getAttribute('color');
            for(let i=0;i<attribute.count;i++)colors.add([attribute.getX(i),attribute.getY(i),attribute.getZ(i)].join(','));
            if(firstBatch>24||group.userData.markCount!==300||drawCalls>4||materials!==1||colors.size!==4)throw Error('Decal batch/material regression');
            const stableStart=performance.now();
            for(let i=0;i<200;i++)module.update({paint_marks:marks});
            const stableMeanMs=(performance.now()-stableStart)/200;
            if(group.userData.mergeCount!==mergeCount)throw Error('Unchanged marks rebuilt GPU geometry');
            module.update({paint_marks:marks.slice(1)});
            if(group.userData.markCount!==299||group.children.length>4||group.children[0].geometry.getAttribute('position').count!==verticesPerMark*299)throw Error('Removing one mark lost the batch');
            // Replay can reuse IDs with changed color/position: retained records
            // must rebuild the affected geometry rather than trusting IDs alone.
            module.update({paint_marks:[{...marks[1],color:'#f0c75e'}]});
            const replacementColor=new v.THREE.Color('#f0c75e');
            if(group.userData.markCount!==1||group.children.length!==1||group.children[0].geometry.getAttribute('position').count!==verticesPerMark||Math.abs(group.children[0].geometry.getAttribute('color').getX(0)-replacementColor.r)>1e-6)throw Error('Replay replacement failed');
            module.update(null);
            if(group.children.length||group.userData.markCount)throw Error('Reset did not clear decals');
            let rays=0;const originals=targets.map(m=>m.raycast);
            targets.forEach((mesh,i)=>{mesh.raycast=function(...args){rays++;return originals[i].apply(this,args);};});
            let initialMissRays,repeatedMissRays;
            try{
              const missing={...marks[0],pos:[10000,10000,10000]};
              module.update({paint_marks:[missing]});initialMissRays=rays;rays=0;
              for(let i=0;i<100;i++)module.update({paint_marks:[missing]});
              repeatedMissRays=rays;
            }finally{targets.forEach((mesh,i)=>{mesh.raycast=originals[i];});}
            if(!initialMissRays||repeatedMissRays)throw Error('Missing-surface retry was not throttled');
            return {marks:300,firstBatch,batches,peakBatchMs,materials,drawCalls,vertices,colors:colors.size,mergeCount,mergeTotalMs,buildMs,stableMeanMs,initialMissRays,repeatedMissRays};
          }finally{module.dispose();}
        }""")

        page.locator('details').filter(has=page.locator('#recordFlight')).locator('summary').click()
        page.click('#recordFlight')
        page.click('#btnPause')
        page.wait_for_timeout(1500)
        with page.expect_download(predicate=lambda d:d.suggested_filename.startswith('ROV-mission-')) as download:
            page.click('#recordFlight')
        mission=OUT/'paint-mission.json';download.value.save_as(mission)
        data=json.loads(mission.read_text(encoding='utf8'))
        assert any(len(f.get('paint_marks',[]))==2 for f in data['clips'][0]['frames'])
        page.set_input_files('#loadReplay',str(mission))
        page.wait_for_function('window.__replay?.() && window.__modelLoaded')
        page.wait_for_function(PAINT_COUNT+'===2')
        assert not page.locator('.surface-paint-tools').is_visible()
        page.keyboard.press('f')
        assert page.evaluate(PAINT_COUNT)==2
        results['replay_readonly_and_marks'] = True
        page.screenshot(path=str(OUT/'paint-replay.png'))
        assert not errors,errors
        results['errors'] = errors
        (OUT/'results.json').write_text(json.dumps(results,indent=2,ensure_ascii=False),encoding='utf8')
        print(json.dumps(results,ensure_ascii=False),flush=True)
    except Exception:
        print('Diagnostics',page.evaluate("({status:document.querySelector('.paint-status')?.textContent,notice:document.querySelector('#operationNotice')?.textContent,state:window.__viewer?.S,errors:[]})"),flush=True)
        page.screenshot(path=str(OUT/'failure.png'))
        raise
    finally:
        browser.close()
