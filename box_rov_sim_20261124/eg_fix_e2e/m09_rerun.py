"""M_09 Deep Link gate E2E: live rov01sim.server (box_run) + headless Chromium."""
import json, socket, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
from websockets.sync.client import connect as ws_connect
BOX_RUN = Path("/workspace/rov_sim/box_run"); OUT = Path("/workspace/rov_sim/eg_fix_e2e/out/m09_rerun"); OUT.mkdir(parents=True, exist_ok=True)
def ports(n):
    ss=[socket.socket() for _ in range(n)]
    for s in ss: s.bind(("127.0.0.1",0))
    ps=[s.getsockname()[1] for s in ss]
    for s in ss: s.close()
    return ps
def post(base, body):
    r=urllib.request.Request(f"{base}/api/campaign/action", data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.loads(urllib.request.urlopen(r, timeout=10).read())["campaign"]
PG=None
def page_action(sub, **extra):
    PG.evaluate("(m) => window.__ws.send(JSON.stringify(m))", {"type":"wave1","action":"campaign_action","sub_action":sub, **extra}); PG.wait_for_timeout(700)
    return PG.evaluate("() => window.__camp")
def ws_action(wsurl, sub, **extra):
    with ws_connect(wsurl, max_size=2**22) as ws:
        ws.send(json.dumps({"type":"join","name":"M09-E2E"}))
        ws.send(json.dumps({"type":"wave1","action":"campaign_action","sub_action":sub, **extra}))
        t=time.time()
        while time.time()-t<6:
            m=json.loads(ws.recv(timeout=6))
            if m.get("type")=="wave1_result" and m.get("wave1"): return m["wave1"]["cable_campaign"]
    raise RuntimeError("no wave1_result")
def get(base): return json.loads(urllib.request.urlopen(f"{base}/api/campaign/state", timeout=10).read())["campaign"]
h,w,r = ports(3)
proc = subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario","mission_2_hull_ut","--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"], cwd=BOX_RUN, stdout=open("/workspace/rov_sim/eg_fix_e2e/out/m09_rerun/server.log","w"), stderr=subprocess.STDOUT)
base=f"http://127.0.0.1:{h}"; WSU=f"ws://127.0.0.1:{w}"; res={"checks":{}}
try:
    for _ in range(100):
        try: urllib.request.urlopen(f"{base}/index.html", timeout=1); break
        except Exception: time.sleep(0.25)
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"])
        pg=b.new_page(viewport={"width":1600,"height":900}); errs=[]; PG=pg
        pg.add_init_script("""(() => { window.__sent=[]; window.__camp=null; const O=window.WebSocket;
          window.WebSocket=function(...a){ const ws=new O(...a); (window.__socks=window.__socks||[]).push(String(a[0])); if (!window.__ws || String(a[0]).includes('ws=')===false && String(a[0]).startsWith('ws://127.0.0.1:' + (new URLSearchParams(location.search).get('ws')||'').split(':').pop())) window.__ws=ws; ws.addEventListener('message', ev => { try { const m=JSON.parse(ev.data); window.__types=window.__types||{}; window.__types[m.type]=(window.__types[m.type]||0)+1; const c=m && m.wave1 && m.wave1.cable_campaign; if (c) window.__camp=c; } catch(e){} }); return ws; };
          window.WebSocket.prototype=O.prototype; Object.assign(window.WebSocket, {OPEN:1, CLOSED:3, CONNECTING:0, CLOSING:2});
          const o=O.prototype.send; O.prototype.send=function(d){ try{ const m=JSON.parse(d); if(m.sub_action) window.__sent.push(m.sub_action);}catch(e){} return o.call(this,d); }; })()""")
        pg.on("pageerror", lambda e: errs.append(str(e)+" @ "+(e.stack or "")[:300]))
        pg.goto(f"{base}/index.html?play=1&ws=ws://127.0.0.1:{w}&model=rov01&nointro=1", wait_until="load"); pg.wait_for_timeout(6000)
        fps = pg.evaluate("""() => new Promise(res => {let f=0;const t0=performance.now();function k(n){f++; if(n-t0<3000) requestAnimationFrame(k); else res(+(f/((n-t0)/1000)).toFixed(1));} requestAnimationFrame(k);})""")
        res["fps"]=fps; res["socks"]=pg.evaluate("() => window.__socks"); res["types"]=pg.evaluate("() => window.__types")
        page_action("reset"); pg.wait_for_timeout(600)
        # A: TLC counterexample replay — extract from Stage 1 over the real API
        a=page_action("extract_complete"); pg.wait_for_timeout(800); print(json.dumps({"socks":res["socks"],"types":pg.evaluate("() => window.__types")}))
        ov=lambda: pg.evaluate("() => { const o=document.getElementById('deepLinkVictoryOverlay'); return o ? !o.hidden : null; }")
        res["checks"]["A_stage1_extract_rejected"]= (a["campaign_completed"] is False and a["stage_num"]==1 and a["last_rejection"].startswith("WRONG_STAGE_1") and ov() is False)
        res["A"]={k:a[k] for k in ("stage_num","campaign_completed","campaign_rank","last_rejection")}; res["A"]["overlay_visible"]=ov()
        pg.screenshot(path=str(OUT/"m09_A_stage1_extract_rejected.png"))
        # B: UI stage pill jump to 4 -> drill, no victory
        pill=pg.locator('#dlStagePills .dl-spill[data-stage="4"]')
        res["pill_count"]=pill.count()
        if pill.count(): pill.first.click(force=True)
        else: ws_action(WSU,"set_stage",stage_num=4)
        pg.wait_for_timeout(500); bst=page_action("state_probe")
        res["checks"]["B_jump4_is_drill_not_completed"]=(bst["drill_mode"] is True and bst["campaign_completed"] is False and ov() is False)
        res["B"]={k:bst.get(k) for k in ("stage_num","drill_mode","campaign_completed","campaign_rank","can_interact","target_distance_m","last_rejection","cable_energized","repair_progress_pct")}; res["B"]["overlay_visible"]=ov()
        pg.screenshot(path=str(OUT/"m09_B_jump4_drill_no_victory.png"))
        # C: real interaction key G in TMS radius -> completed as DRILL, overlay edge-opens
        pg.keyboard.press("KeyG"); pg.wait_for_timeout(1500); cst=page_action("state_probe")
        glyph=pg.evaluate("() => document.getElementById('dlVictoryRank')?.textContent")
        res["checks"]["C_dock_completes_drill_rank_overlay"]=(cst["campaign_completed"] is True and cst["campaign_rank"].startswith("DRILL") and ov() is True and glyph=="練")
        res["C"]={k:cst.get(k) for k in ("campaign_completed","campaign_rank","campaign_score","drill_mode","last_rejection","cable_energized","repair_progress_pct","stage_num","target_distance_m")}; res["C"].update(overlay_visible=ov(), rank_glyph=glyph, page_sent=pg.evaluate("() => window.__sent"))
        pg.screenshot(path=str(OUT/"m09_C_tms_dock_drill_victory.png"))
        # D: double extraction refused
        d=page_action("extract_complete")
        res["checks"]["D_double_extract_refused"]= d["last_rejection"]=="CAMPAIGN_ALREADY_COMPLETED"
        txt=pg.evaluate("() => document.body.innerText + ' ' + document.documentElement.outerHTML")
        import re
        res["brand_hits"]=len(re.findall(r"qysea|fifish|鰭源|\bx1\b", txt, re.I))
        res["checks"]["E_zero_brand_in_live_dom"]=res["brand_hits"]==0
        res["checks"]["F_no_page_errors"]=len(errs)==0
        res["hud_stage_title"]=pg.evaluate("() => document.getElementById('dlStageTitle')?.textContent")
        res["pageerrors"]=errs[:5]
        b.close()
finally:
    proc.terminate(); proc.wait(5)
res["overall_pass"]=all(res["checks"].values())
(OUT/"m09_e2e_result.json").write_text(json.dumps(res,ensure_ascii=False,indent=2)); print(json.dumps(res,ensure_ascii=False,indent=1))
