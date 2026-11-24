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
        pg.goto(f"{base}/index.html?play=1&ws=ws://127.0.0.1:{w}&model=rov01&nointro=1"); t0=time.time()
        for i in range(8):
            pg.wait_for_timeout(3000)
            st=(i%4)+1
            fps=pg.evaluate("""() => new Promise(res => {let f=0;const t0=performance.now();function k(n){f++; if(n-t0<1000) requestAnimationFrame(k); else res(f);} requestAnimationFrame(k);})""")
            pg.evaluate(f"() => window.__wave1.jumpToCampaignStage({st})"); t=time.time(); ms=None
            while time.time()-t<8:
                c=pg.evaluate("() => window.__viewer?.S?.wave1?.cable_campaign")
                if c and c['stage_num']==st and c['target_distance_m']<3.6: ms=int((time.time()-t)*1000); break
                pg.wait_for_timeout(50)
            simt=pg.evaluate("() => window.__viewer?.S?.t")
            print(f"t+{time.time()-t0:.0f}s fps={fps} stage{st} hud_ms={ms} sim_t={simt}", flush=True)
        b.close()
finally: proc.terminate()
