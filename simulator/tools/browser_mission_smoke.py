"""Check real arm controls, exported media, and round-trip local replay."""
import json
from pathlib import Path
from PIL import Image, ImageStat
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parents[1]/'output'/'mission-validation'
out.mkdir(parents=True,exist_ok=True)
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1600,'height':1000},accept_downloads=True)
    errors=[]
    page.on('pageerror',lambda e:errors.append(str(e)))
    page.add_init_script("""window.__mediaLog=[];const Original=window.MediaRecorder;window.MediaRecorder=class extends Original{constructor(stream,options){super(stream,options);window.__mediaLog.push({event:'created',tracks:stream.getTracks().map(t=>({kind:t.kind,settings:t.getSettings(),readyState:t.readyState}))});for(const name of ['start','stop','error','dataavailable'])this.addEventListener(name,e=>window.__mediaLog.push({event:name,time:performance.now(),size:e.data?.size,error:e.error?.message}));}};""")
    page.goto('http://127.0.0.1:8092/?ws=ws://127.0.0.1:8792&room=training&model=falcon&nointro&play=1')
    page.wait_for_function('window.__viewer?.S?.model_id==="falcon" && window.__loadedModelId==="falcon" && window.__modelLoaded')
    page.locator('#armPanel summary').click()
    page.locator('#armJoint0').evaluate('(el)=>{el.value="20";el.dispatchEvent(new Event("change",{bubbles:true}));}')
    page.wait_for_function('Math.abs(window.__viewer.S.operations.arm.joints[0]-20)<.5')
    page.click('#gripClose')
    page.wait_for_function('window.__viewer.S.operations.arm.grip<.1')
    page.click('#gripOpen')
    page.wait_for_function('window.__viewer.S.operations.arm.grip>.9')
    print('Arm controls passed',flush=True)
    page.locator('details').filter(has=page.locator('#savePhoto')).locator('summary').click()
    with page.expect_download(predicate=lambda d:d.suggested_filename.endswith('.png')) as download:
        page.click('#savePhoto')
    photo=out/'inspection.png';download.value.save_as(photo)
    with Image.open(photo) as im:
        extrema=im.getchannel('A').getextrema() if im.mode=='RGBA' else (255,255)
        variance=ImageStat.Stat(im.convert('RGB')).stddev
        assert extrema[1]>0 and max(variance)>8,(extrema,variance)
    page.click('#saveVideo')
    page.wait_for_function('window.__mediaLog.filter(e=>e.event==="dataavailable" && e.size>1000).length>=4',timeout=20000)
    print('Recording diagnostics:',page.evaluate('({media:window.__mediaLog,visibility:document.visibilityState,meta:document.querySelector("#meta")?.textContent})'),flush=True)
    with page.expect_download(predicate=lambda d:d.suggested_filename.endswith('.webm')) as download:
        page.click('#saveVideo')
    video=out/'inspection.webm';download.value.save_as(video)
    print('Video bytes:',video.stat().st_size,flush=True)
    assert video.stat().st_size>1000,page.evaluate('window.__mediaLog')
    page.evaluate("""()=>{const input=document.createElement('input');input.type='file';input.id='verifyVideo';input.hidden=true;document.body.append(input);}""")
    page.set_input_files('#verifyVideo',str(video))
    decoded=page.evaluate("""async()=>{
      const video=document.createElement('video'),source=URL.createObjectURL(document.querySelector('#verifyVideo').files[0]);video.muted=true;video.src=source;
      const event=name=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Video '+name+' timed out')),15000);video.addEventListener(name,()=>{clearTimeout(timer);resolve();},{once:true});video.addEventListener('error',()=>{clearTimeout(timer);reject(Error(video.error?.message||'Video decode failed'));},{once:true});});
      await event('loadeddata');const canvas=document.createElement('canvas');canvas.width=160;canvas.height=90;const context=canvas.getContext('2d',{willReadFrequently:true});
      async function frame(t){const ready=event('seeked');video.currentTime=t;await ready;context.drawImage(video,0,0,160,90);return context.getImageData(0,0,160,90).data;}
      const a=await frame(.3),b=await frame(2);let sum=0,squares=0,change=0,n=0;for(let i=0;i<a.length;i++){if(i%4===3)continue;sum+=b[i];squares+=b[i]*b[i];change+=Math.abs(a[i]-b[i]);n++;}
      const result={width:video.videoWidth,height:video.videoHeight,stddev:Math.sqrt(squares/n-(sum/n)**2),mean_frame_change:change/n};video.removeAttribute('src');video.load();URL.revokeObjectURL(source);document.querySelector('#verifyVideo').remove();return result;
    }""")
    assert decoded['width']>0 and decoded['height']>0 and decoded['stddev']>8,decoded
    assert decoded['mean_frame_change']>.001,decoded
    print('Photo and decoded moving video passed:',decoded,flush=True)
    page.click('#recordFlight');page.wait_for_timeout(2200)
    with page.expect_download(predicate=lambda d:d.suggested_filename.startswith('ROV-mission-')) as download:
        page.click('#recordFlight')
    mission=out/'mission.json';download.value.save_as(mission)
    data=json.loads(mission.read_text(encoding='utf8'))
    assert len(data['clips'][0]['frames'])>=2
    page.set_input_files('#loadReplay',str(mission))
    page.wait_for_function('window.__replay?.() && window.__loadedModelId==="falcon" && window.__modelLoaded')
    assert 'local%3A' in page.url
    assert page.locator('#recordFlight').is_disabled()
    page.reload()
    page.wait_for_function('window.__replay?.() && window.__loadedModelId==="falcon" && window.__modelLoaded')
    page.screenshot(path=str(out/'replay.png'))
    page.click('#returnMenu')
    page.wait_for_selector('#launchMenu')
    assert 'replay=' not in page.url and 'play=1' not in page.url
    page.locator('#menuIntro').evaluate('(el)=>{el.checked=false;el.dispatchEvent(new Event("change",{bubbles:true}));}')
    page.click('#startDive')
    page.wait_for_function('window.__viewer?.S?.vehicle_id && !window.__replay?.()')
    assert 'replay=' not in page.url
    assert not errors,errors
    (out/'results.json').write_text(json.dumps({'arm':True,'photo_stddev':variance,'video_bytes':video.stat().st_size,'video_decoded':decoded,'frames':len(data['clips'][0]['frames']),'replay_reload':True,'return_to_menu':True,'menu_start_to_live':True,'errors':errors},indent=2),encoding='utf8')
    browser.close()
print('Mission round trip passed:',out)
