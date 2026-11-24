import json, socket, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
base=f"http://127.0.0.1:{h}"
proc=subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd="/workspace/rov_sim/box_run",stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
try:
    for _ in range(120):
        try: urllib.request.urlopen(f"{base}/index.html",timeout=1); break
        except Exception: time.sleep(0.25)
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"]); pg=b.new_page(viewport={"width":1600,"height":900})
        pg.add_init_script("""(()=>{window.__log=[];window.__lt=[];const O=WebSocket;window.WebSocket=function(...a){const ws=new O(...a);ws.addEventListener('message',ev=>{const d=ev.data;const ty=(d.slice(0,40).match(/"type":"(\\w+)"/)||[])[1];window.__log.push([performance.now()|0,ty,d.length]);});return ws;};window.WebSocket.prototype=O.prototype;Object.assign(window.WebSocket,{OPEN:1,CLOSED:3,CONNECTING:0,CLOSING:2});
        try{new PerformanceObserver(l=>{for(const e of l.getEntries())window.__lt.push([e.startTime|0,e.duration|0]);}).observe({entryTypes:['longtask']});}catch(e){} })()""")
        pg.goto(f"{base}/index.html?play=1&ws=ws://127.0.0.1:{w}&model=rov01&nointro=1")
        pg.wait_for_timeout(20000)
        log=pg.evaluate("()=>window.__log"); lt=pg.evaluate("()=>window.__lt")
        from collections import Counter
        print("types", Counter(x[1] for x in log))
        for sec in range(0,21,2):
            n=[x for x in log if sec*1000<=x[0]<(sec+2)*1000]; print(sec, len(n), Counter(x[1] for x in n))
        print("longtasks>200ms", [x for x in lt if x[1]>200][:20], "total longtask ms", sum(x[1] for x in lt))
        b.close()
finally: proc.terminate()
