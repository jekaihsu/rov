"""HTTP /api/campaign/action regression: each action still works right after set_stage, and M_09 gates still refuse skips."""
import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path
scen = sys.argv[1] if len(sys.argv) > 1 else "open_water"
ss=[socket.socket() for _ in range(3)]
for s in ss: s.bind(("127.0.0.1",0))
h,w,r=[s.getsockname()[1] for s in ss]; [s.close() for s in ss]
base=f"http://127.0.0.1:{h}"
proc=subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario",scen,"--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],cwd="/workspace/rov_sim/box_run",stdout=subprocess.DEVNULL,stderr=subprocess.STDOUT)
def post(**b):
    q=urllib.request.Request(f"{base}/api/campaign/action",data=json.dumps(b).encode(),headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(q,timeout=10).read())["campaign"]
C={}
try:
    for _ in range(120):
        try: urllib.request.urlopen(f"{base}/index.html",timeout=1); break
        except Exception: time.sleep(0.25)
    post(sub_action="reset"); c=post(sub_action="extract_complete")
    C["gate_stage1_extract_refused"]=c["last_rejection"].startswith("WRONG_STAGE_1") and not c["campaign_completed"]
    post(sub_action="set_stage",stage_num=1); time.sleep(0.5); c=post(sub_action="advance_ring")
    C["advance_ring_after_set_stage1"]=c["waypoint_rings_cleared"]==1 and not c["last_rejection"]
    c=post(sub_action="advance_ring"); C["ring2_from_jump_point_out_of_range"]=c["last_rejection"].startswith("OUT_OF_RANGE") and c["waypoint_rings_cleared"]==1
    post(sub_action="set_stage",stage_num=2); time.sleep(0.5); c=post(sub_action="grab_cable",place_in_saddle=True)
    C["seat_after_set_stage2"]=c["stage_num"]==3 and c["cable_seated_in_saddle"]
    post(sub_action="set_stage",stage_num=3); time.sleep(0.5); c=post(sub_action="repair_step",step_delta_pct=34)
    C["repair_after_set_stage3"]=c["stage_num"]==4 and c["cable_energized"] and c["repair_progress_pct"]==100.0
    post(sub_action="set_stage",stage_num=4); time.sleep(0.5); c=post(sub_action="extract_complete")
    C["extract_after_set_stage4_is_drill"]=c["campaign_completed"] and c["campaign_rank"].startswith("DRILL")
    c=post(sub_action="extract_complete"); C["double_extract_refused"]=c["last_rejection"]=="CAMPAIGN_ALREADY_COMPLETED"
    post(sub_action="set_stage",stage_num=2); c=post(sub_action="repair_step"); C["stage2_repair_refused"]=c["last_rejection"].startswith("WRONG_STAGE_2")
    # stay-in-range: 3 s after each jump the ROV is still inside the [E] radius
    hold={}
    for st in (1,2,3,4):
        post(sub_action="set_stage",stage_num=st); time.sleep(3.0)
        c=json.loads(urllib.request.urlopen(f"{base}/api/campaign/state").read())["campaign"]; hold[st]=(c["target_distance_m"],c["can_interact"],c["stage_num"])
    C["in_range_3s_after_each_jump"]=all(v[1] for v in hold.values())
finally: proc.terminate()
out={"scenario":scen,"checks":C,"hold_3s":hold,"passed":sum(C.values()),"total":len(C)}
Path(__file__).parent.joinpath("out",f"api_regression_{scen}.json").write_text(json.dumps(out,ensure_ascii=False,indent=1)); print(json.dumps(out,ensure_ascii=False))
