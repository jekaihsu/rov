"""Live console acceptance; use the same QYSIM_INSTRUCTOR_CODE as the running server."""
import json
import os
import sys
import uuid
from pathlib import Path
ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / 'tools'))
OUT = ROOT / 'output' / 'instructor'
OUT.mkdir(parents=True, exist_ok=True)
from _browser import launch,http_base,ws_base
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser=launch(p)
    page=browser.new_page(viewport={'width':1600,'height':900})
    errors=[]
    page.on('pageerror',lambda error: errors.append(str(error)))
    page.goto(http_base(8080) + '/instructor/instructor.html?ws_port=' + ws_base(8765).rsplit(':', 1)[1])
    room_id = 'd2-' + uuid.uuid4().hex[:8]
    page.evaluate('''async ({url, room}) => {
      window.pilots = [];
      for (const name of ['學員 01', '學員 02']) {
        await new Promise((resolve, reject) => {
          const ws = new WebSocket(url);
          window.pilots.push(ws);
          const timer = setTimeout(() => reject(new Error('pilot join timeout')), 15000);
          ws.onopen = () => ws.send(JSON.stringify({type:'join', room_id:room,name,model_id:'falcon'}));
          ws.onmessage = e => {
            const m = JSON.parse(e.data);
            if (m.type === 'session') {
              clearTimeout(timer);
              resolve();
            }
            if (m.type === 'error') reject(new Error(m.message));
          };
        });
      }
    }''',{'url':ws_base(8765), 'room':room_id})
    page.locator('#room').fill(room_id)
    page.locator('#code').fill(os.environ['QYSIM_INSTRUCTOR_CODE'])
    page.get_by_role('button',name='連線',exact=True).click()
    page.wait_for_function("document.querySelectorAll('.student').length === 2")
    page.wait_for_function("document.querySelector('.active-events').textContent.includes('目前沒有')")
    page.locator('#duration').fill('60')
    page.get_by_role('button',name='注入故障',exact=True).click()
    page.wait_for_selector('.active-event')
    page.wait_for_function("document.querySelector('.student').classList.contains('caution')")
    page.get_by_role('button',name='放大',exact=True).click()
    page.get_by_role('button',name='全域',exact=True).click()
    assert page.evaluate('''() => {
      const lower = document.querySelector('.assessment').getBoundingClientRect().top;
      return [...document.querySelectorAll('.dashboard > section')]
        .every(n => n.getBoundingClientRect().bottom <= lower);
    }''')
    page.screenshot(path=str(OUT / 'after.png'))
    with page.expect_download() as d:
        page.get_by_role('button',name='下載 JSON',exact=True).click()
    d.value.save_as(str(OUT / 'training.json'))
    data = json.loads((OUT / 'training.json').read_text())
    assert len(data['matrix'])==5 and data['events'] and data['trajectory']
    assert 'original' not in data['supervision']['active'][0]
    with page.expect_download() as d:
        page.get_by_role('button',name='可列印 HTML',exact=True).click()
    d.value.save_as(str(OUT / 'training.html'))
    with page.expect_download() as d:
        page.get_by_role('button',name='軌跡 CSV',exact=True).click()
    d.value.save_as(str(OUT / 'trajectory.csv'))
    page.get_by_role('button',name='提前結束',exact=True).click()
    page.wait_for_function("document.querySelectorAll('.active-event').length === 0")
    page.wait_for_function("document.querySelector('.timeline').textContent.includes('已恢復')")
    page.wait_for_function("document.querySelector('.student').classList.contains('normal')")
    page.locator('#target').select_option('v2')
    page.wait_for_function("document.querySelector('.assessment-toolbar .mono').textContent.includes('v2')")
    page.locator('#kind').select_option('freeze')
    page.locator('#duration').fill('1')
    page.get_by_role('button',name='注入故障',exact=True).click()
    page.wait_for_function("document.querySelector('.timeline').textContent.includes('凍結載具')")
    page.wait_for_function("document.querySelectorAll('.active-event').length === 0")
    page.set_viewport_size({'width':1280,'height':720})
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth')
    page.set_viewport_size({'width':1600,'height':900})
    page.locator('#code').fill('wrong')
    page.get_by_role('button',name='連線',exact=True).click()
    page.wait_for_function("document.querySelector('output').textContent.includes('authentication failed')")
    assert page.get_by_role('button',name='注入故障',exact=True).is_disabled()
    assert not errors,errors
    print('PASS: two pilots, authenticated console, telemetry, zoom, injection, early restore, expiry, target switch')
    print('PASS: five-phase report, JSON/CSV/HTML downloads, 1280px overflow, authentication rejection, no JS errors')
    print('Screenshot: after.png (1600x900); report samples:',len(data['trajectory']))
    browser.close()
