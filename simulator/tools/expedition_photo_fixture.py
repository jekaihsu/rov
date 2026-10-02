"""End-to-end photo integration fixture; NOT a pilot or physics performance test.

Serves the unmodified app and SimHost on 8096/8796/9796. Only this harness
freezes vehicle dynamics and positions the vehicle for repeatable photography.
Real GLBs, ecology, camera projection, screenshots, socket validation and local
collection storage are used. Fixture endpoints are never part of the product.
"""
import asyncio
import base64
import json
import math
from pathlib import Path
import socketserver
import sys
import threading
import time
import numpy as np
from playwright.sync_api import sync_playwright
import websockets

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from qysim.engine import Simulator
from qysim.server import SimHost,_Static,dumps
from qysim.physics import q_from_euler,q_rot
from qysim.expedition import ensure_expedition

OUT=ROOT/'output'/'expedition-photo-validation'

def place(sim,point,stance=None):
    point=np.asarray(point,float)
    if stance is None:
        stance=point-np.array([2.7,0.,0.])
        stance[2]=min(stance[2],sim.world.depth_at(stance)-1.0)
    stance=np.asarray(stance,float)
    q=q_from_euler(0.,0.,0.)
    for _ in range(5):
        lens=stance+q_rot(q,np.asarray(sim.vehicle.definition.camera_body))
        delta=point-lens
        q=q_from_euler(0.,-math.atan2(delta[2],math.hypot(delta[0],delta[1])),math.atan2(delta[1],delta[0]))
    sim.vehicle.s.pos[:]=stance;sim.vehicle.s.q[:]=q
    sim.vehicle.s.vel[:]=0;sim.vehicle.s.omega[:]=0
    sim.controller.reset_holds()
    # The fixture cable is not simulated; keep its displayed endpoint honest.
    sim.tether.x[-1]=stance+q_rot(q,np.asarray(sim.vehicle.definition.gland_body))
    return {'pos':stance.tolist(),'q':q.tolist(),'target':point.tolist()}

async def fixture_main():
    OUT.mkdir(parents=True,exist_ok=True)
    sim=Simulator('coral_reef',seed=42,model_id='falcon')
    sim.operations.command({'action':'mission_mode','mode':'expedition'})
    host=SimHost(sim,view_hz=15)
    loop=asyncio.get_running_loop()
    async def fixture_phase(phase):
        async with host.lock:
            if phase=='biology':
                entity=next(e for e in sim.world.habitat_entities if e['kind']=='coral' and e['variant']==0)
                _,point,_=ensure_expedition(sim)._entity(sim,entity['id'])
                info={'entity_id':entity['id'],**place(sim,point)}
            elif phase=='engineering':
                step=next(s for s in ensure_expedition(sim).active['steps'] if not s['completed'])
                info={'entity_id':step['entity_id'],**place(sim,step['target_point'],step['point'])}
            else:raise ValueError(phase)
            host.room._snapshot=None
            return info
    class Handler(_Static):
        def do_POST(self):
            if self.path!='/__fixture__/phase':self.send_error(404);return
            try:
                data=json.loads(self.rfile.read(int(self.headers['Content-Length'])))
                info=asyncio.run_coroutine_threadsafe(fixture_phase(data['phase']),loop).result(timeout=20)
                encoded=dumps(info).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(encoded)
            except Exception as e:self.send_error(500,str(e))
    socketserver.ThreadingTCPServer.allow_reuse_address=True
    http=socketserver.ThreadingTCPServer(('127.0.0.1',8096),Handler)
    threading.Thread(target=http.serve_forever,daemon=True).start()
    rpc=await asyncio.start_server(host.rpc_client,'127.0.0.1',9796)
    ws=await websockets.serve(host.viewer_handler,'127.0.0.1',8796,max_size=2**16)
    async def fixture_clock():
        while True:
            await asyncio.sleep(.05)
            async with host.lock:
                sim.t+=.05
                ensure_expedition(sim).update(sim,.05)
                host.room.tick+=1
    clock=asyncio.create_task(fixture_clock())
    try:await asyncio.to_thread(browser_test)
    finally:
        clock.cancel();await asyncio.gather(clock,return_exceptions=True)
        ws.close();await ws.wait_closed();rpc.close();await rpc.wait_closed();http.shutdown();http.server_close()

def browser_test():
    def wait_collection(page,count):
        until=time.monotonic()+25
        while time.monotonic()<until:
            value=page.evaluate('async()=>await(await import("/collection_store.js")).listCollection()')
            if len(value['photos'])==count:return value
            page.wait_for_timeout(100)
        raise AssertionError({'collection_timeout':value})
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        errors=[];wire=[]
        page.on('pageerror',lambda e:errors.append(str(e)))
        def socket(ws):
            def frame(text):
                try:
                    message=json.loads(text)
                    if message.get('type') in ('error','operation_result'):wire.append(message)
                except Exception:pass
            ws.on('framereceived',frame)
        page.on('websocket',socket)
        page.goto('http://127.0.0.1:8096/?ws=ws://127.0.0.1:8796&room=training&model=falcon&mission=expedition&play=1&nointro',wait_until='domcontentloaded')
        try:
            page.wait_for_function('window.__viewer?.S?.mission?.mode==="expedition" && window.__modelLoaded && window.__loadedModelId==="falcon"',timeout=90000)
            setup=page.request.post('http://127.0.0.1:8096/__fixture__/phase',data={'phase':'biology'}).json()
            page.locator('.exp-onboard').click()
            page.evaluate('window.__viewer.rc.right_switch=2')
            page.wait_for_function('(p)=>Math.hypot(...window.__viewer.S.pos.map((v,i)=>v-p[i]))<.01',arg=setup['pos'])
            page.wait_for_timeout(1300)
            page.locator('.exp-photo').click()
            collection=wait_collection(page,1)
            assert len(collection['guides'])==1,{'collection':collection,'wire':wire,'feedback':page.locator('.exp-feedback').inner_text()}
            assert collection['photos'][0]['observation']['category']=='coral'
            assert any(m.get('observation',{}).get('accepted') for m in wire),wire
            photo=page.evaluate('async()=>{const s=await import("/collection_store.js"),c=await s.listCollection(),b=await s.getPhotoBlob(c.photos[0].id);return Array.from(new Uint8Array(await b.arrayBuffer()));}')
            assert bytes(photo[:8])==b'\x89PNG\r\n\x1a\n'
            (OUT/'accepted-onboard-coral.png').write_bytes(bytes(photo))
            page.screenshot(path=str(OUT/'accepted-coral-ui.png'))
            page.locator('.exp-available select').select_option('inspect')
            page.locator('.exp-available button').click()
            page.wait_for_function('window.__viewer.S.expedition.active?.kind==="inspect"')
            engineering=page.request.post('http://127.0.0.1:8096/__fixture__/phase',data={'phase':'engineering'}).json()
            page.wait_for_function('(id)=>window.__viewer.S.expedition.active.steps.find(s=>s.entity_id===id)?.progress>=1',arg=engineering['entity_id'],timeout=15000)
            page.wait_for_timeout(500)
            page.locator('.exp-photo').click()
            page.wait_for_function('window.__viewer.S.expedition.active.steps[0].completed',timeout=15000)
            collection=wait_collection(page,2)
            assert len(collection['guides'])==1
            page.screenshot(path=str(OUT/'accepted-engineering-ui.png'))
            page.locator('.exp-collection').click()
            page.wait_for_function('document.querySelectorAll(".collection-panel .collection-photo-button").length===1')
            page.wait_for_function('document.querySelector(".collection-panel img")?.naturalWidth>0')
            assert page.locator('.collection-panel .collection-locked').count()==4
            page.screenshot(path=str(OUT/'collection-one-guide.png'))
            page.locator('.collection-photo-button').click()
            page.wait_for_selector('.collection-original')
            page.screenshot(path=str(OUT/'collection-photo-detail.png'))
            page.locator('[data-tab="photos"]').click()
            assert page.locator('.collection-photo-button').count()==2
            page.locator('.collection-close').click()
            assert not page.locator('.collection-panel').is_visible()
            assert not errors,errors
            (OUT/'result.json').write_text(json.dumps({'status':'passed','fixture':'frozen test poses, no piloting claim','biology_pose':setup,'engineering_pose':engineering,'collection':collection,'wire':wire,'errors':errors},ensure_ascii=False,indent=2),encoding='utf-8')
            print('Real onboard photograph accepted; guide unlocked; real engineering photograph completed inspection station.',flush=True)
        except Exception:
            (OUT/'failure.json').write_text(json.dumps({'wire':wire,'errors':errors,'state':page.evaluate('window.__viewer?.S'),'feedback':page.locator('.exp-feedback').inner_text()},ensure_ascii=False,indent=2),encoding='utf-8')
            page.screenshot(path=str(OUT/'failed-ui.png'));raise
        finally:browser.close()

if __name__=='__main__':asyncio.run(fixture_main())
