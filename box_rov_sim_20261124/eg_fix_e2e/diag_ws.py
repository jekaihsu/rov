import json, socket, subprocess, sys, time, urllib.request, traceback
sys.path.insert(0,"/workspace/rov_sim/box_run")
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
proc=subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd="/workspace/rov_sim/box_run",stdout=open("/tmp/diagws.log","w"),stderr=subprocess.STDOUT)
from websockets.sync.client import connect
time.sleep(4)
try:
  with connect(f"ws://127.0.0.1:{w}", max_size=2**24) as ws:
    ws.send(json.dumps({"type":"join","room_id":"training","name":"d","model_id":"rov01"}))
    ws.send(json.dumps({"type":"wave1","action":"campaign_action","sub_action":"set_stage","stage_num":2}))
    t=time.time(); seen={}
    while time.time()-t<4:
        try: raw=ws.recv(timeout=4)
        except Exception as e: print("recv err",repr(e)); break
        m=json.loads(raw); seen[m["type"]]=seen.get(m["type"],0)+1
        if m["type"]=="wave1_result": print("RESULT len",len(raw), m["campaign"]["stage_num"] if "campaign" in m else None); 
        if m["type"]=="error": print("ERR",m)
        if m["type"]=="state" and seen["state"]%20==0: c=(m.get("wave1") or {}).get("cable_campaign"); print("state", m.get("vehicle_id"), c and c["stage_num"], c and c["target_distance_m"], m.get("pos"), "len",len(raw))
    print(seen)
finally: proc.terminate()
