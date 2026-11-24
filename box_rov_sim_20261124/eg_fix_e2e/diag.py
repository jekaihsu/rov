import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
BOX=Path("/workspace/rov_sim/box_run")
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
base=f"http://127.0.0.1:{h}"
proc=subprocess.Popen([sys.executable,"-u","/workspace/rov_sim/eg_fix_e2e/dbg_server.py","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd=BOX,stdout=open("/tmp/dbg.log","w"),stderr=subprocess.STDOUT)
st=lambda: json.loads(urllib.request.urlopen(f"{base}/api/campaign/state").read())["campaign"]
try:
    for _ in range(120):
        try: urllib.request.urlopen(f"{base}/index.html",timeout=1); break
        except Exception: time.sleep(0.25)
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--use-gl=swiftshader"]); pg=b.new_page()
        pg.add_init_script("""(()=>{const O=WebSocket;window.WebSocket=function(...a){const ws=new O(...a);window.__ws=ws;(window.__urls=window.__urls||[]).push(String(a[0]));ws.addEventListener('close',e=>{(window.__closes=window.__closes||[]).push([String(a[0]),e.code,e.reason]);});ws.addEventListener('message',ev=>{try{const m=JSON.parse(ev.data);window.__types=window.__types||{};window.__types[m.type]=(window.__types[m.type]||0)+1;if(m.type==='state'){window.__vid=m.vehicle_id;window.__pos=m.pos;} if(m.type==='session'){window.__sess=m;} const c=m&&m.wave1&&m.wave1.cable_campaign;if(c){window.__camp=c;window.__campFrom=m.type;}}catch(e){}});return ws;};window.WebSocket.prototype=O.prototype;Object.assign(window.WebSocket,{OPEN:1,CLOSED:3,CONNECTING:0,CLOSING:2});})()""")
        pg.goto(f"{base}/index.html?play=1&ws=ws://127.0.0.1:{w}&model=rov01&nointro=1"); pg.wait_for_timeout(6000)
        print("types",pg.evaluate("()=>window.__types"),"vid",pg.evaluate("()=>window.__vid"))
        pg.evaluate("()=>window.__ws.send(JSON.stringify({type:'wave1',action:'campaign_action',sub_action:'set_stage',stage_num:2}))"); pg.wait_for_timeout(800)
        c=pg.evaluate("()=>window.__camp"); print("WS camp", c["stage_num"], c["target_distance_m"], pg.evaluate("()=>window.__campFrom"), pg.evaluate("()=>window.__pos"))
        print("urls",pg.evaluate("()=>window.__urls"),"closes",pg.evaluate("()=>window.__closes"),"types",pg.evaluate("()=>window.__types"));print("HTTP camp", st()["stage_num"], st()["target_distance_m"])
        for i in range(5):
            pg.wait_for_timeout(500); c=pg.evaluate("()=>window.__camp"); print("t",i, "ws d",c["target_distance_m"], "pos",pg.evaluate("()=>window.__pos"))
        b.close()
finally: proc.terminate()
