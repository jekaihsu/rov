import sys, traceback
sys.path.insert(0, "/workspace/rov_sim/box_run")
from rov01sim import server as S
orig = S.SimHost.handle_viewer
def hv(self, msg, *a, **k):
    if msg.get("type") not in ("rc", "latency_probe"):
        print("IN", msg.get("type"), msg.get("action"), msg.get("sub_action"), "player", getattr(k.get("player"), "vehicle_id", None), "room", getattr(k.get("room"), "id", None), flush=True)
    try:
        r = orig(self, msg, *a, **k)
    except Exception as e:
        print("EXC", repr(e), flush=True); raise
    if msg.get("type") == "wave1": print("OUT", r and r.get("type"), flush=True)
    return r
S.SimHost.handle_viewer = hv
origvh = S.SimHost.viewer_handler
async def vh(self, ws, *a, **k):
    real_send = ws.send
    async def send(data, *aa, **kk):
        big = isinstance(data, str) and '"wave1_result"' in data[:40]
        try:
            r = await real_send(data, *aa, **kk)
            if big: print("SENT wave1_result", len(data), flush=True)
            return r
        except Exception as e:
            print("SEND EXC", repr(e), len(data), flush=True); raise
    ws.send = send
    try:
        return await origvh(self, ws, *a, **k)
    finally:
        print("HANDLER EXIT", flush=True)
S.SimHost.viewer_handler = vh
S.main(sys.argv[1:])
