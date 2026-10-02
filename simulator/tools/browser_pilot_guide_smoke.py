"""Browser validation of telemetry-driven guide, mappings and persisted dismissal."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1]/'output'/'pilot-guide-validation'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True)
    page = browser.new_page(viewport={'width': 1280, 'height': 800})
    errors = []
    page.on('pageerror', lambda e: errors.append(str(e)))
    page.route('**/__pilot-guide-test', lambda route: route.fulfill(content_type='text/html', body='''
      <html lang="zh-Hant"><head><meta charset="utf-8"><link rel="stylesheet" href="/style.css"></head>
      <body><aside style="width:290px;padding:16px"><div class="mission-tools"><div class="session-summary">Falcon · 驗證場景</div></div></aside></body></html>'''))
    page.goto('http://127.0.0.1:8092/__pilot-guide-test')
    result = page.evaluate('''async()=>{
      const {installPilotGuide}=await import('/pilot_guide.js');
      const assert=(v,m)=>{if(!v)throw Error(m);};
      localStorage.removeItem('rov.pilotGuide.dismissed.v1');
      let s={vehicle_id:'v1',model_id:'falcon',t:0,locked:true,operation_mode:'UAV_CHN',pos:[0,0,2],rc:{left_ud:1500,right_switch:0},thrust:[0,0,0,0,0]};
      const options={getState:()=>s,getWorld:()=>({scenario:{name:'珊瑚礁'}})};
      let guide=installPilotGuide(options);
      const done=step=>document.querySelector(`[data-step="${step}"]`).dataset.complete==='true';
      const hint=()=>document.querySelector('.pilot-context').textContent;
      const update=extra=>{s={...s,...extra,t:s.t+.1};guide.update(s);};
      assert(!document.querySelector('#pilotGuideBody').hidden,'First dive should open');
      assert(hint().includes('Space'),'Locked guidance missing');
      update({locked:false});assert(done('unlock'),'Unlock not detected');
      update({pos:[2,0,2]});assert(!done('move'),'Idle drift counted as piloting');
      update({rc:{left_ud:1800,right_switch:0},thrust:[.4,.4,.4,.4,0],pos:[2.1,0,2]});
      assert(!done('move'),'Old idle drift credited when input started');
      update({pos:[2.3,0,2]});update({pos:[2.5,0,2]});assert(done('move'),'Controlled travel not detected');
      update({keep_depth:true,depth_hold:null});assert(!done('depth'),'No depth setpoint credited');
      update({depth_hold:2});assert(done('depth'),'Actual depth hold not detected');
      update({rc:{left_ud:1500,right_switch:1}});assert(done('light'),'Light state not detected');
      assert(document.querySelector('.pilot-count').textContent==='4 / 4','Wrong progress');
      const mappings={ROV_USA:'↑ / ↓',ROV_JPN:'W / S',ROV_CHN:'W / S',UAV_USA:'↑ / ↓',UAV_JPN:'W / S',UAV_CHN:'W / S'};
      for(const [mode,key] of Object.entries(mappings)){update({operation_mode:mode});assert(document.querySelector('dd').textContent.includes(key),'Wrong forward mapping '+mode);}
      update({controller:{connected:false}});assert(hint().includes('USB'),'Disconnected USB hint missing');
      assert(!document.querySelector('dd').textContent.includes('W / S'),'USB axis claims keyboard control');
      document.querySelector('#pilotGuideDismiss').click();assert(document.querySelector('#pilotGuideBody').hidden,'Dismiss failed');
      guide.dispose();assert(!document.querySelector('#pilotGuide'),'Dispose left DOM');
      guide=installPilotGuide(options);assert(document.querySelector('#pilotGuideBody').hidden,'Dismiss not remembered');
      document.querySelector('#pilotGuideToggle').click();assert(!document.querySelector('#pilotGuideBody').hidden,'Help reopen failed');
      update({t:-5,locked:true,controller:undefined});assert(!done('move'),'Scenario reset kept progress');
      guide.dispose();guide=installPilotGuide({...options,readOnly:true});
      guide.update({...s,locked:false,keep_depth:true,depth_hold:2,rc:{right_switch:2}});
      assert(document.querySelector('.pilot-count').textContent==='回放','Replay progress should be disabled');
      assert(document.querySelector('.pilot-guide ol').hidden,'Replay checklist visible');
      guide.dispose();guide=installPilotGuide(options);document.querySelector('#pilotGuideToggle').click();
      if(document.querySelector('#pilotGuideBody').hidden)document.querySelector('#pilotGuideToggle').click();
      document.querySelector('.pilot-guide details').open=true;
      return {telemetry_progress:true,idle_drift_excluded:true,mappings:6,usb_guidance:true,dismiss_reopen:true,reset:true,readonly:true,dispose:true};
    }''')
    page.screenshot(path=str(out/'guide.png'))
    assert not errors, errors
    result['errors'] = errors
    (out/'results.json').write_text(json.dumps(result, indent=2), encoding='utf8')
    browser.close()
print(json.dumps(result, indent=2))
