"""Alternating idle-render A/B in one actual app page and one fixed scene.

Reuses the deterministic photo host; vehicle dynamics are frozen, network
telemetry remains live. Measures UI/render frame cadence, not physics or pilot
performance. Renderer identity and fixed canvas size are recorded honestly.
"""
import asyncio
import json
from pathlib import Path
import statistics
import expedition_photo_fixture as fixture
from playwright.sync_api import sync_playwright

OUT=Path(__file__).resolve().parents[1]/'output'/'expedition-performance'

def benchmark():
    OUT.mkdir(parents=True,exist_ok=True)
    with sync_playwright() as p:
        browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
        page=browser.new_page(viewport={'width':1440,'height':900})
        page.add_init_script('''window.__benchSockets=[];const Native=window.WebSocket;window.WebSocket=class extends Native{constructor(...args){super(...args);window.__benchSockets.push(this);}};window.__benchCPU=null;const raf=window.requestAnimationFrame.bind(window);window.requestAnimationFrame=callback=>raf(t=>{if(callback.name!=='frame'){callback(t);return;}const start=performance.now();callback(t);if(window.__benchCPU)window.__benchCPU.push(performance.now()-start);});''')
        page.goto('http://127.0.0.1:8096/?ws=ws://127.0.0.1:8796&room=training&model=falcon&mission=expedition&play=1&nointro&quality=medium')
        try:
            page.wait_for_function('window.__modelLoaded && window.__viewer?.S?.mission?.mode==="expedition"',timeout=90000)
            page.request.post('http://127.0.0.1:8096/__fixture__/phase',data={'phase':'biology'})
            page.locator('.exp-onboard').click()
            page.evaluate('window.__viewer.rc.right_switch=1')
            page.wait_for_function('window.__viewer.performance().mode==="medium"')
            page.wait_for_timeout(3000)
            samples=[]
            # ABBA order limits a monotonic thermal/cache drift bias.
            for mode in ('free_explore','expedition','expedition','free_explore'):
                page.evaluate('(mode)=>window.__benchSockets.find(s=>s.readyState===1).send(JSON.stringify({type:"operation",action:"mission_mode",mode}))',mode)
                page.wait_for_function('(m)=>window.__viewer.S.mission.mode===m',arg=mode)
                page.wait_for_timeout(1500)
                page.evaluate('window.__benchCPU=[]')
                result=page.evaluate('''()=>new Promise(resolve=>{const dt=[];let last=null,start=null;function step(t){if(start===null)start=t;if(last!==null)dt.push(t-last);last=t;if(t-start>=5000)resolve({dt,performance:window.__viewer.performance(),pose:window.__viewer.S.pos,canvas:{width:document.querySelector('#vp canvas').width,height:document.querySelector('#vp canvas').height}});else requestAnimationFrame(step);}requestAnimationFrame(step);})''')
                frames=result.pop('dt');result.update(mode=mode,frames=len(frames),mean_frame_ms=statistics.mean(frames),median_frame_ms=statistics.median(frames),p95_frame_ms=sorted(frames)[int((len(frames)-1)*.95)])
                cpu=page.evaluate('()=>{const values=window.__benchCPU;window.__benchCPU=null;return values;}')
                result.update(cpu_samples=len(cpu),mean_callback_ms=statistics.mean(cpu),p95_callback_ms=sorted(cpu)[int((len(cpu)-1)*.95)])
                samples.append(result);print(json.dumps(result,ensure_ascii=False),flush=True)
            means={mode:statistics.mean(s['mean_frame_ms'] for s in samples if s['mode']==mode) for mode in ('free_explore','expedition')}
            delta=(means['expedition']/means['free_explore']-1)*100
            cpu_means={mode:statistics.mean(s['mean_callback_ms'] for s in samples if s['mode']==mode) for mode in ('free_explore','expedition')}
            cpu_delta=(cpu_means['expedition']/cpu_means['free_explore']-1)*100
            report={'method':'one Chrome page; fixed onboard camera and medium quality; 3 s warmup; 1.5 s settle then 5 s requestAnimationFrame intervals; ABBA','scope':'idle UI/render; fixture freezes physics; live telemetry; callback time includes JS and GL submission but not all asynchronous GPU work; vsync caps cadence; not controlled hardware performance certification','samples':samples,'means_ms':means,'relative_change_percent':delta,'observed_cadence_within_5_percent':delta<=5,'callback_means_ms':cpu_means,'callback_change_percent':cpu_delta,'hardware':samples[0]['performance']['hardwareRenderer']}
            (OUT/'results.json').write_text(json.dumps(report,ensure_ascii=False,indent=2),encoding='utf-8')
            print('A/B frame time relative change: %.2f%%'%delta,flush=True)
        finally:browser.close()

if __name__=='__main__':
    fixture.browser_test=benchmark
    asyncio.run(fixture.fixture_main())
