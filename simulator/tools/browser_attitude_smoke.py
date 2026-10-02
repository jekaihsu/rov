"""Validate the ROV attitude instrument's signs, data and laptop panel size."""
import json
import math
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

out=Path(__file__).resolve().parents[1]/'output'/'attitude-validation'
out.mkdir(parents=True,exist_ok=True)
angles=[(0,0,0),(20,0,90),(-20,0,180),(0,30,270),(0,-30,359),(20,-30,45),(0,179,370),(0,-179,-10)]
with sync_playwright() as p:
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
    page=browser.new_page(viewport={'width':1366,'height':768})
    errors=[];page.on('pageerror',lambda error:errors.append(str(error)))
    page.goto(f'http://127.0.0.1:8094/?ws=ws://127.0.0.1:8794&room=attitude_{int(time.time())}&play=1&nointro&model=falcon')
    page.wait_for_function('window.__viewer?.S?.vehicle_id && window.__modelLoaded',timeout=90000)
    page.wait_for_function('document.querySelector("#adi").getAttribute("aria-label")?.includes("ROV")')
    page.screenshot(path=str(out/'live-laptop-panel.png'))
    # Keep the live application's drawing reference intact, but replace the DOM
    # canvas with a same-size clone for stable, explicit angle fixture captures.
    page.evaluate("""()=>{const original=document.querySelector('#adi'),copy=original.cloneNode(false);original.replaceWith(copy);}""")
    cases=[]
    for pitch,roll,heading in angles:
        case=page.evaluate("""async([pitch,roll,heading])=>{
          const {drawROVAttitude}=await import('./attitude_indicator.js');
          const canvas=document.querySelector('#adi'),ctx=canvas.getContext('2d'),rotations=[],texts=[];
          const rotate=ctx.rotate,fillText=ctx.fillText;
          ctx.rotate=function(a){rotations.push(a);return rotate.call(this,a);};
          ctx.fillText=function(text,...args){texts.push({text,font:this.font});return fillText.call(this,text,...args);};
          try{drawROVAttitude(canvas,{pitch,roll,heading});}
          finally{ctx.rotate=rotate;ctx.fillText=fillText;}
          const rect=canvas.getBoundingClientRect(),rack=canvas.closest('aside').getBoundingClientRect();
          return {dataset:{...canvas.dataset},aria:canvas.getAttribute('aria-label'),role:canvas.getAttribute('role'),rotations,texts,
            rect:{x:rect.x,y:rect.y,width:rect.width,height:rect.height},withinRack:rect.left>=rack.left&&rect.right<=rack.right,
            minimumFontCSS:Math.min(...texts.map(t=>Number(t.font.match(/([\\d.]+)px/)[1])))*rect.width/520};
        }""",[pitch,roll,heading])
        assert float(case['dataset']['pitch'])==pitch,case
        assert float(case['dataset']['roll'])==roll,case
        assert int(case['dataset']['heading'])==heading%360,case
        assert case['role']=='img' and '側視' in case['aria'] and '艉視' in case['aria'],case
        assert any(math.isclose(a,-math.radians(pitch),abs_tol=1e-10) for a in case['rotations']),case
        assert any(math.isclose(a,math.radians(roll),abs_tol=1e-10) for a in case['rotations']),case
        assert case['withinRack'] and case['rect']['x']+case['rect']['width']<=1366,case
        texts=[item['text'] for item in case['texts']]
        assert ('抬頭' if pitch>0 else '低頭' if pitch<0 else '水平') in texts,case
        assert ('右舷下沉' if roll>0 else '左舷下沉' if roll<0 else '水平') in texts,case
        cases.append({'pitch':pitch,'roll':roll,'heading':heading,**case})
        page.locator('#adi').screenshot(path=str(out/f'pitch_{pitch}_roll_{roll}.png'))
        if pitch==20 and roll==-30:page.screenshot(path=str(out/'known-angle-laptop-panel.png'))
    invalid=page.evaluate("""async()=>{const {drawROVAttitude}=await import('./attitude_indicator.js');const canvas=document.querySelector('#adi');drawROVAttitude(canvas,{pitch:NaN,roll:0,heading:0});return {dataset:{...canvas.dataset},aria:canvas.getAttribute('aria-label')};}""")
    assert invalid['dataset']['pitch']==invalid['dataset']['roll']==invalid['dataset']['heading']=='',invalid
    assert '等待' in invalid['aria'],invalid
    assert not errors,errors
    result={'viewport':[1366,768],'cases':cases,'invalid':invalid,'errors':errors}
    (out/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf8')
    browser.close()
print(json.dumps({'passed':len(cases),'minimumFontCSS':cases[0]['minimumFontCSS'],'panel':cases[0]['rect'],'errors':errors},ensure_ascii=False))
