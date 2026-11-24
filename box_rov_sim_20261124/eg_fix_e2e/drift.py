import json, socket, subprocess, sys, time
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
proc=subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd="/workspace/rov_sim/box_run",stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
from websockets.sync.client import connect
time.sleep(4); out={}
try:
  with connect(f"ws://127.0.0.1:{w}", max_size=2**24) as ws:
    ws.send(json.dumps({"type":"join","room_id":"training","name":"d","model_id":"rov01"}))
    for st in (1,2,3,4):
        ws.send(json.dumps({"type":"wave1","action":"campaign_action","sub_action":"set_stage","stage_num":st}))
        t=time.time(); ds=[]; got=False
        while time.time()-t<4:
            m=json.loads(ws.recv(timeout=4))
            if m["type"]=="wave1_result": got=True
            if got and m["type"]=="state":
                c=m["wave1"]["cable_campaign"]
                if c["stage_num"]==st: ds.append((round(time.time()-t,1),c["target_distance_m"]))
        out[st]=ds[::15]
finally: proc.terminate()
print(json.dumps(out))
