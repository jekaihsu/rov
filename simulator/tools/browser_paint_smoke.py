"""Real-browser surface paint, multiplayer appearance and recorded replay smoke."""
import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base, timeout, pump_until
from _menu import open_settings_tab, set_intro, soft_click, to_briefing

OUT = Path(__file__).resolve().parents[1] / 'output' / 'paint-validation'
OUT.mkdir(parents=True, exist_ok=True)
BASE = f'{http_base(8093)}/'
QUERY = (
    f'?ws={ws_base(8793)}&room=paint_{int(time.time())}&model=bluerov2_heavy'
    f'&scene=seagrass_meadow&quality=performance'
)
PAINT_COUNT = "window.__viewer.scene.getObjectByName('Shared surface paint')?.userData.markCount||0"
STICKER_COUNT = "(()=>{let count=0;window.__viewer.scene.traverse(o=>{if(o.name==='Vehicle stickers')count+=o.children.length;});return count;})()"
results = {}

with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width':1440,'height':1000}, accept_downloads=True)
    peer = browser.new_page(viewport={'width':900,'height':700})
    errors = []
    for tab in [page, peer]:
        tab.on('pageerror', lambda error: errors.append(str(error)))
        tab.set_default_timeout(timeout(90000))
    try:
        page.goto(BASE+QUERY)
        page.wait_for_function('window.__menu?.ready', timeout=timeout(120000))
        open_settings_tab(page, 'controls')
        page.select_option('#menuPad','keyboard')
        page.select_option('#menuControl','ROV_USA')
        page.evaluate('window.__menu.go("main")')
        to_briefing(page, mode='free_explore', site='seagrass_meadow', sticker='hazard')
        page.wait_for_function('window.__menu.stickerMeshes>0', timeout=timeout(90000))
        results['menu_sticker_meshes'] = page.evaluate('window.__menu.stickerMeshes')
        page.screenshot(path=str(OUT/'sticker-preview.png'))
        set_intro(page, False)
        soft_click(page, '#startDive')
        page.wait_for_function(
            'window.__viewer?.S?.appearance?.sticker==="hazard" && window.__modelLoaded && window.__viewer.W.scenario.key==="seagrass_meadow"',
            timeout=timeout(120000))
        page.wait_for_function(STICKER_COUNT+'>0', timeout=timeout(90000))
        results['live_sticker_meshes'] = page.evaluate(STICKER_COUNT)
        peer.goto(BASE+QUERY+'&play=1&nointro&sticker=dive')
        peer.wait_for_function('window.__viewer?.S?.vehicles?.length===2 && window.__modelLoaded',
                               timeout=timeout(120000))
        page.wait_for_function('window.__viewer.S.vehicles.length===2', timeout=timeout(120000))
        peer.wait_for_function(STICKER_COUNT+'>=4', timeout=timeout(120000))
        results['peer_sticker_meshes'] = peer.evaluate(STICKER_COUNT)
        results['peer_appearance'] = peer.evaluate('window.__viewer.S.vehicles.map(v=>v.appearance.sticker)')
        print('Menu, own and peer stickers passed', flush=True)

        page.bring_to_front()
        peer.evaluate('window.__skipRender = true')
        soft_click(page, '#flightDrawer')
        soft_click(page, '.surface-paint-tools summary')
        soft_click(page, '.paint-toggle')
        # Let the real top-camera spring settle; a same-turn lookAt snap can leave the ray with no hit.
        page.evaluate("window.__viewer.setCam('top')")
        pump_until(page, """() => {
          const v = window.__viewer;
          if (!v?.S || !(v.S.sensors?.altitude > 3)) return false;
          v.setCam('top');
          const meshes = [];
          v.scene.traverse(o => { if (o.isMesh && o.userData.paintable && o.visible) meshes.push(o); });
          const ray = new v.THREE.Raycaster();
          ray.setFromCamera(new v.THREE.Vector2(0, 0), v.camera);
          const hit = ray.intersectObjects(meshes, false)[0];
          if (!hit || hit.distance < 5) return false;
          const canvas = document.querySelector('.viewport canvas');
          const rect = canvas.getBoundingClientRect();
          const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
          canvas.dispatchEvent(new PointerEvent('pointerdown', {
            button: 0, clientX: x, clientY: y, pointerId: 1, bubbles: true
          }));
          canvas.dispatchEvent(new PointerEvent('pointerup', {
            button: 0, clientX: x, clientY: y, pointerId: 1, bubbles: true
          }));
          return (document.querySelector('.paint-status')?.textContent || '').includes('距離太遠');
        }""", timeout_ms=timeout(60000), allies=(peer,))
        assert page.evaluate('window.__viewer.S.paint_marks.length') == 0
        results['far_surface_rejected'] = True
        # Drive heave through touch + rc_lock so blur/visibility failsafe cannot cancel the dive mid-wait.
        peer.evaluate('window.__skipRender = true')
        page.bring_to_front()
        page.locator('.viewport canvas').first.click(force=True, no_wait_after=True)
        pump_until(page, """() => {
          const v = window.__viewer;
          if (!v?.S || !v.touch) return false;
          v.rc.rc_lock = 0;
          v.touch.left_wave = -1;
          const altitude = v.S.sensors?.altitude;
          if (Number.isFinite(altitude) && altitude < 2.2) return true;
          const start = new v.THREE.Vector3(-v.S.pos[1], -v.S.pos[2], v.S.pos[0]);
          const meshes = [];
          v.scene.traverse(o => { if (o.isMesh && o.userData.paintable && o.visible) meshes.push(o); });
          const hits = new v.THREE.Raycaster(start, new v.THREE.Vector3(0, -1, 0)).intersectObjects(meshes, false);
          return !!(hits.length && hits[0].distance < 2.2);
        }""", timeout_ms=timeout(180000), allies=(peer,))
        page.evaluate("""() => {
          const v = window.__viewer;
          if (!v) return;
          v.touch.left_wave = 0;
          v.rc.rc_lock = 1;
        }""")
        soft_click(page, '#btnPause')
        pump_until(page, '() => window.__viewer.S.paused', timeout_ms=timeout(60000), allies=(peer,))
        results['paint_vehicle_position'] = page.evaluate('window.__viewer.S.pos')

        def spray_center_with_top_cam(view_offset_x=0, height=8):
            """Snap top cam and spray at NDC centre in one turn so the spring follow cannot move the ray."""
            return page.evaluate("""({offsetX, height}) => {
              const v = window.__viewer, p = v.rovG.position;
              v.setCam('top');
              if (v.camera.clearViewOffset) v.camera.clearViewOffset();
              v.camera.up.set(0, 0, 1);
              v.camera.position.set(p.x, p.y + height, p.z);
              v.camera.lookAt(p);
              const canvas = document.querySelector('.viewport canvas');
              const rect = canvas.getBoundingClientRect();
              if (offsetX) v.camera.setViewOffset(rect.width, rect.height, offsetX, 0, rect.width, rect.height);
              v.camera.updateProjectionMatrix();
              document.activeElement?.blur?.();
              const x = rect.left + rect.width / 2, y = rect.top + rect.height / 2;
              canvas.dispatchEvent(new PointerEvent('pointerdown', {
                button: 0, clientX: x, clientY: y, pointerId: 1, bubbles: true
              }));
              canvas.dispatchEvent(new PointerEvent('pointerup', {
                button: 0, clientX: x, clientY: y, pointerId: 1, bubbles: true
              }));
              return document.querySelector('.paint-status')?.textContent || '';
            }""", {'offsetX': view_offset_x, 'height': height})

        # Close-in top view: centre ray must hit the hull (occlusion).
        status = spray_center_with_top_cam(0, height=8)
        assert '擋住' in status, status
        assert page.evaluate('window.__viewer.S.paint_marks.length') == 0
        results['vehicle_occlusion_rejected'] = True
        # Higher top view + offset, matching the original smoke geometry onto exposed sand.
        status = spray_center_with_top_cam(35, height=22)
        assert '已送出' in status or '確認' in status, status
        pump_until(page, '() => window.__viewer.S.paint_marks.length===1',
                   timeout_ms=timeout(120000), allies=(peer,))
        page.wait_for_function(PAINT_COUNT+'===1', timeout=timeout(120000))
        peer.bring_to_front()
        pump_until(peer, '() => window.__viewer.S.paint_marks.length===1',
                   timeout_ms=timeout(120000), allies=(page,))
        peer.wait_for_function(PAINT_COUNT+'===1', timeout=timeout(120000))
        page.bring_to_front()
        results['shared_first_mark'] = page.evaluate('window.__viewer.S.paint_marks[0]')
        assert results['shared_first_mark'] == peer.evaluate('window.__viewer.S.paint_marks[0]')
        print('Real terrain F paint and peer rendering passed', flush=True)

        # Engineering drawer must not cover the HUD tool that toggles it closed.
        assert page.evaluate("""() => {
          const btn = document.querySelector('#flightDrawer');
          const panel = document.querySelector('#engineering');
          if (!btn || !panel || panel.hidden) return false;
          const r = btn.getBoundingClientRect();
          const top = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
          return !!(top && (top === btn || btn.contains(top)));
        }"""), 'open #engineering covered #flightDrawer'
        soft_click(page, '#flightDrawer')
        assert page.evaluate('document.querySelector("#engineering").hidden')
        canvas=page.locator('.viewport canvas').first
        box=canvas.bounding_box()
        page.mouse.move(box['x']+box['width']/2,box['y']+box['height']/2)
        page.mouse.down();page.mouse.move(box['x']+box['width']/2+40,box['y']+box['height']/2+20);page.mouse.up()
        assert page.evaluate('window.__viewer.S.paint_marks.length')==1
        canvas.click(position={'x':box['width']/2+8,'y':box['height']/2}, force=True, no_wait_after=True)
        page.wait_for_function('window.__viewer.S.paint_marks.length===2', timeout=timeout(120000))
        page.wait_for_function(PAINT_COUNT+'===2', timeout=timeout(120000))
        peer.wait_for_function(PAINT_COUNT+'===2', timeout=timeout(120000))
        results['click_and_drag_filter'] = True
        results['flight_drawer_above_engineering'] = True
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

        soft_click(page, '#flightDrawer')
        page.locator('details').filter(has=page.locator('#recordFlight')).locator('summary').evaluate(
            'el => el.click()')
        page.locator('#recordFlight').evaluate('el => el.click()')
        page.locator('#btnPause').evaluate('el => el.click()')
        page.wait_for_timeout(1500)
        with page.expect_download(
                predicate=lambda d: d.suggested_filename.startswith('ROV-mission-'),
                timeout=timeout(60000)) as download:
            page.locator('#recordFlight').evaluate('el => el.click()')
        mission = OUT / 'paint-mission.json'
        download.value.save_as(mission)
        data = json.loads(mission.read_text(encoding='utf8'))
        assert any(len(f.get('paint_marks', [])) == 2 for f in data['clips'][0]['frames'])
        page.set_input_files('#loadReplay', str(mission))
        page.wait_for_function('window.__replay?.() && window.__modelLoaded', timeout=timeout(120000))
        page.wait_for_function(PAINT_COUNT + '===2', timeout=timeout(120000))
        assert not page.locator('.surface-paint-tools').is_visible()
        page.keyboard.press('f')
        assert page.evaluate(PAINT_COUNT) == 2
        results['replay_readonly_and_marks'] = True
        page.screenshot(path=str(OUT / 'paint-replay.png'))
        assert not errors, errors
        results['errors'] = errors
        (OUT / 'results.json').write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding='utf8')
        print(json.dumps(results, ensure_ascii=False), flush=True)
    except Exception:
        print('Diagnostics',page.evaluate("({status:document.querySelector('.paint-status')?.textContent,notice:document.querySelector('#operationNotice')?.textContent,state:window.__viewer?.S,errors:[]})"),flush=True)
        page.screenshot(path=str(OUT/'failure.png'))
        raise
    finally:
        browser.close()
