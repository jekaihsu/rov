import json, socket, subprocess, sys, time
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
proc=subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd="/workspace/rov_sim/box_run",stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
from websockets.sync.client import connect
time.sleep(4)
try:
  with connect(f"ws://127.0.0.1:{w}", max_size=2**24) as ws:
    ws.send(json.dumps({"type":"join","room_id":"training","name":"d","model_id":"rov01"}))
    t=time.time(); n=0
    while True:
        m=json.loads(ws.recv(timeout=4))
        if m["type"]=="state":
            n+=1
            if n==5:
                sz={k:len(json.dumps(v)) for k,v in m.items()}; print(sorted(sz.items(),key=lambda x:-x[1])[:8])
                w1=m.get("wave1") or {}; print("wave1:",sorted({k:len(json.dumps(v)) for k,v in w1.items()}.items(),key=lambda x:-x[1])[:8])
                su=w1.get("simready_usd",{}); print("simready:",{k:len(json.dumps(v)) for k,v in su.items()})
                cc=w1.get("cable_campaign",{}); print("campaign:",sorted({k:len(json.dumps(v)) for k,v in cc.items()}.items(),key=lambda x:-x[1])[:5])
            if time.time()-t>3: print("state rate",n/(time.time()-t)); break
finally: proc.terminate()
