from pathlib import Path
from playwright.sync_api import sync_playwright
out=Path('/workspace/rov/simulator/output/t16')
with sync_playwright() as p:
 b=p.chromium.launch(executable_path='/usr/bin/chromium',args=['--enable-unsafe-swiftshader'])
 page=b.new_page(viewport=dict(width=1600,height=900))
 page.goto('http://127.0.0.1:8092/?play=1&nointro&quality=performance&ws=ws://127.0.0.1:8792&room=evidence')
 page.wait_for_function('window.__viewer?.S?.pos && document.querySelector("#flightCable")',timeout=90000)
 page.screenshot(path=str(out/'after-flight-1600x900.png'),timeout=120000)
 page.route('**/hud/hud.css',lambda r:r.fulfill(path='/tmp/t16-before.css',content_type='text/css'))
 page.route('**/hud/flight_hud.js',lambda r:r.fulfill(path='/tmp/t16-before.js',content_type='text/javascript'))
 page.reload()
 page.wait_for_function('window.__viewer?.S?.pos && document.querySelector("#flightCable")',timeout=90000)
 page.screenshot(path=str(out/'before-flight-1600x900.png'),timeout=120000)
 page.unroute('**/hud/hud.css')
 page.unroute('**/hud/flight_hud.js')
 page.goto('http://127.0.0.1:8092/?replay=demo_recording.json&nointro&quality=performance')
 page.wait_for_function('window.__replay?.() && document.querySelector("#flightCable")',timeout=90000)
 for w,h in [(1280,720),(1920,1080)]:
  page.set_viewport_size(dict(width=w,height=h))
  box=page.locator('#rpPlay').bounding_box()
  x,y=box['x']+box['width']/2,box['y']+box['height']/2
  page.mouse.move(x,y)
  page.mouse.click(x,y)
  page.wait_for_function('document.querySelector("#rpPlay").textContent === "▶"',timeout=90000)
  page.screenshot(path=str(out/f'replay-{w}x{h}.png'),timeout=120000)
  page.mouse.click(x,y)
 b.close()
print('Evidence screenshots captured')
