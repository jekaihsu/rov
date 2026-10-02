"""Real Chrome / Three.js observation tests using deterministic rendered fixtures."""
import base64
import functools
import http.server
import json
from pathlib import Path
import threading
import sys
from playwright.sync_api import sync_playwright

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
OUT=ROOT/'output'/'observation-validation'

def main():
    from qysim.engine import Simulator
    worlds=[Simulator(key,seed=42).world_description() for key in ('coral_reef','seagrass_meadow')]
    OUT.mkdir(parents=True,exist_ok=True)
    handler=functools.partial(http.server.SimpleHTTPRequestHandler,directory=str(ROOT/'viewer'))
    server=http.server.ThreadingHTTPServer(('127.0.0.1',0),handler)
    threading.Thread(target=server.serve_forever,daemon=True).start()
    try:
        with sync_playwright() as p:
            browser=p.chromium.launch(channel='chrome',headless=True,args=['--enable-unsafe-swiftshader'])
            page=browser.new_page(viewport={'width':960,'height':640})
            errors=[]
            page.on('pageerror',lambda e:errors.append(str(e)))
            page.route('**/observation-harness',lambda r:r.fulfill(content_type='text/html',body='<html><head><script type="importmap">{"imports":{"three":"/vendor/three/build/three.module.js"}}</script></head><body style="margin:0"></body></html>'))
            page.goto(f'http://127.0.0.1:{server.server_port}/observation-harness')
            result=page.evaluate((ROOT/'tools'/'observation_smoke.js').read_text(encoding='utf-8'),{'worlds':worlds})
            assert not errors,errors
            png=page.evaluate('window.__observationScreenshot')
            (OUT/'rendered-coral-fixture.png').write_bytes(base64.b64decode(png.split(',',1)[1]))
            (OUT/'results.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
            browser.close()
            print(f'{len(result)} real-browser observation cases passed. {OUT}')
    finally:server.shutdown();server.server_close()

if __name__=='__main__':main()
