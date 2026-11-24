"""E/G/button interact + OUT_OF_RANGE hint E2E for Deep Link campaign (box_run, headless Chromium).
Truth = the campaign the HUD renders (window.__viewer.S, fed by the pilot's own WebSocket session),
cross-checked against HTTP /api/campaign/state (room "training" seat v1 = this pilot)."""
import json, re, socket, subprocess, sys, time, urllib.request
from pathlib import Path
from playwright.sync_api import sync_playwright
SCEN = sys.argv[1] if len(sys.argv) > 1 else "open_water"
BOX = Path("/workspace/rov_sim/box_run"); OUT = Path(__file__).parent / "out" / SCEN; OUT.mkdir(parents=True, exist_ok=True)
for f in OUT.glob("*.png"): f.unlink()
def ports(n):
    ss=[socket.socket() for _ in range(n)]
    for s in ss: s.bind(("127.0.0.1",0))
    ps=[s.getsockname()[1] for s in ss]
    for s in ss: s.close()
    return ps
h,w,r = ports(3); base=f"http://127.0.0.1:{h}"
def http_state(): return json.loads(urllib.request.urlopen(f"{base}/api/campaign/state", timeout=10).read())["campaign"]
KEYS=("stage_num","waypoint_rings_cleared","cable_grabbed","cable_seated_in_saddle","repair_progress_pct","cable_energized","campaign_completed","campaign_rank","last_rejection","target_distance_m","can_interact","drill_mode")
snap=lambda c:{k:(c or {}).get(k) for k in KEYS}
proc = subprocess.Popen([sys.executable,"-u","-m","rov01sim.server","--scenario",SCEN,"--seed","42","--http-port",str(h),"--ws-port",str(w),"--rpc-port",str(r),"--release-mode"],
                        cwd=BOX, stdout=open(OUT/"server.log","w"), stderr=subprocess.STDOUT)
rep={"scenario":SCEN,"checks":{},"steps":{},"latency_ms":{}}; C=rep["checks"]; S=rep["steps"]; L=rep["latency_ms"]
try:
    for _ in range(120):
        try: urllib.request.urlopen(f"{base}/index.html", timeout=1); break
        except Exception: time.sleep(0.25)
    with sync_playwright() as p:
        b=p.chromium.launch(args=["--use-gl=swiftshader","--enable-webgl","--ignore-gpu-blocklist"])
        pg=b.new_page(viewport={"width":1600,"height":900}); errs=[]; posts=[]
        pg.add_init_script("""(()=>{window.__sent=[];window.__socks=[];const O=WebSocket;
          window.WebSocket=function(...a){const ws=new O(...a);window.__socks.push(ws);return ws;};
          window.WebSocket.prototype=O.prototype;Object.assign(window.WebSocket,{OPEN:1,CLOSED:3,CONNECTING:0,CLOSING:2});
          const o=O.prototype.send;O.prototype.send=function(d){try{const m=JSON.parse(d);if(m.sub_action)window.__sent.push(m.sub_action);}catch(e){}return o.call(this,d);};})()""")
        pg.on("pageerror", lambda e: errs.append(str(e)))
        pg.on("request", lambda q: posts.append(q.url) if "/api/campaign/action" in q.url else None)
        pg.goto(f"{base}/index.html?play=1&ws=ws://127.0.0.1:{w}&model=rov01&nointro=1", wait_until="load"); pg.wait_for_timeout(6000)
        hud_c=lambda: pg.evaluate("() => window.__viewer?.S?.wave1?.cable_campaign || null")
        sub=lambda: pg.evaluate("() => document.getElementById('dlReticleSub')?.textContent || ''")
        C["hud_present"]=pg.evaluate("() => !!document.getElementById('deepLinkObjectiveBar') && !!document.getElementById('btnDlInteract')")
        rep["vehicle_id"]=pg.evaluate("() => window.__viewer?.S?.vehicle_id")
        def wait(pred, ms=4000):
            t=time.time()
            while (time.time()-t)*1000<ms:
                c=hud_c()
                if c and pred(c): return c, int((time.time()-t)*1000)
                pg.wait_for_timeout(60)
            return hud_c(), None
        def pill(n):
            pg.locator(f'#dlStagePills .dl-spill[data-stage="{n}"]').first.click(force=True)
            c,_=wait(lambda c: c["stage_num"]==n and not c["campaign_completed"]); pg.wait_for_timeout(700); return hud_c()
        def act(fn, pred, label):
            n=len(pg.evaluate("() => window.__sent")); fn(); c,ms=wait(pred); L[label]=ms
            sent=pg.evaluate("() => window.__sent")[n:]; return c, sent
        # ---- Stage 1: jump puts ROV 2 m from ring 1 -> [E] clears it
        a=pill(1); c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: c["waypoint_rings_cleared"]>=1, "stage1_E")
        S["stage1_E"]={"before":snap(a),"after":snap(c),"ws_sent":sent}
        C["stage1_E_clears_ring"]= a["stage_num"]==1 and a["waypoint_rings_cleared"]==0 and c["waypoint_rings_cleared"]==1 and sent==["advance_ring"]
        pg.screenshot(path=str(OUT/"stage1_after_E.png"))
        # ---- OUT_OF_RANGE: ring 2 is ~3.7 m away (> 3.2 m) -> rejected, HUD shows the distance hint
        c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: str(c["last_rejection"]).startswith("OUT_OF_RANGE"), "out_of_range_reply")
        pg.wait_for_timeout(150); t=sub()
        S["out_of_range"]={"after":snap(c),"hud_sub":t,"ws_sent":sent}
        C["out_of_range_rejected_by_server"]= str(c["last_rejection"]).startswith("OUT_OF_RANGE") and c["waypoint_rings_cleared"]==1
        C["out_of_range_hint_visible"]= "距離太遠" in t and "OUT OF RANGE" in t and bool(re.search(r"需 ≤3\.2m", t))
        pg.screenshot(path=str(OUT/"out_of_range_hint.png"))
        pg.wait_for_timeout(4500); t2=sub(); S["out_of_range"]["hud_sub_after_4_5s"]=t2
        C["out_of_range_hint_expires_back_to_prompt"]= "距離太遠" not in t2 and "[E] / [G]" in t2
        # ---- Stage 2: cable already in gripper after jump -> [E] seats it into the saddle -> Stage 3
        a=pill(2); c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: c["stage_num"]==3, "stage2_E")
        S["stage2_E"]={"before":snap(a),"after":snap(c),"ws_sent":sent}
        C["stage2_E_seats_cable_to_stage3"]= a["stage_num"]==2 and c["stage_num"]==3 and c["cable_seated_in_saddle"] is True and sent==["grab_cable"]
        pg.screenshot(path=str(OUT/"stage2_after_E.png"))
        # ---- Stage 3: jump (68 %) -> [E] -> 100 %, energized, Stage 4
        a=pill(3); c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: c["stage_num"]==4, "stage3_E")
        S["stage3_E"]={"before":snap(a),"after":snap(c),"ws_sent":sent}
        C["stage3_E_finishes_repair"]= a["stage_num"]==3 and c["repair_progress_pct"]==100.0 and c["cable_energized"] is True and sent==["repair_step"]
        pg.screenshot(path=str(OUT/"stage3_after_E.png"))
        # ---- [G] once (Stage 3 repair)
        a=pill(3); c,sent=act(lambda: pg.keyboard.press("KeyG"), lambda c: c["stage_num"]==4, "stage3_G")
        S["stage3_G"]={"before":snap(a),"after":snap(c),"ws_sent":sent}
        C["stage3_G_finishes_repair"]= c["stage_num"]==4 and c["cable_energized"] is True and sent==["repair_step"]
        # ---- Stage 4: jump -> [E] docks in TMS -> completed (drill rank), victory overlay
        a=pill(4); c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: c["campaign_completed"], "stage4_E")
        pg.wait_for_timeout(300)
        ov=pg.evaluate("() => { const o=document.getElementById('deepLinkVictoryOverlay'); return o ? !o.hidden : null; }")
        S["stage4_E"]={"before":snap(a),"after":snap(c),"ws_sent":sent,"victory_overlay":ov}
        C["stage4_E_completes_campaign"]= a["stage_num"]==4 and c["campaign_completed"] is True and str(c["campaign_rank"]).startswith("DRILL") and ov is True and sent==["extract_complete"]
        pg.screenshot(path=str(OUT/"stage4_after_E.png"))
        pg.evaluate("() => { const o=document.getElementById('deepLinkVictoryOverlay'); if (o) o.hidden=true; }")
        # ---- Button + reticle-card clicks
        pill(3); c,sent=act(lambda: pg.locator("#btnDlInteract").click(force=True), lambda c: c["stage_num"]==4, "btn_click")
        C["button_btnDlInteract_works"]= c["stage_num"]==4 and sent==["repair_step"]
        pill(2); c2,sent2=act(lambda: pg.locator("#dlReticleCard").click(force=True), lambda c: c["stage_num"]==3, "card_click")
        C["reticle_card_click_works"]= c2["stage_num"]==3 and sent2==["grab_cable"]
        S["clicks"]={"btn_after":snap(c),"btn_sent":sent,"card_after":snap(c2),"card_sent":sent2}
        pg.screenshot(path=str(OUT/"click_reticle_stage2_to_3.png"))
        # ---- Reset, then [E] from wherever the ROV is -> must give feedback (ring cleared or distance hint)
        pg.evaluate("() => window.__socks.at(-1).send(JSON.stringify({type:'wave1',action:'campaign_action',sub_action:'reset'}))")
        wait(lambda c: c["stage_num"]==1 and c["waypoint_rings_cleared"]==0); pg.wait_for_timeout(500)
        c,sent=act(lambda: pg.keyboard.press("KeyE"), lambda c: c["waypoint_rings_cleared"]==1 or bool(c["last_rejection"]), "reset_then_E")
        pg.wait_for_timeout(150); tr=sub(); S["reset_then_E"]={"after":snap(c),"hud_sub":tr}
        C["reset_then_E_gives_feedback"]= (c["waypoint_rings_cleared"]==1 and not c["last_rejection"]) or ("距離太遠" in tr)
        pg.screenshot(path=str(OUT/"reset_then_E_hint.png"))
        # ---- HUD vs server agree (old desync: HUD Stage 4 while backend Stage 1)
        pg.wait_for_timeout(800); hc=hud_c(); sc=http_state()
        S["sync"]={"hud":snap(hc),"server":snap(sc)}
        C["hud_matches_server_campaign"]= all(hc[k]==sc[k] for k in ("stage_num","waypoint_rings_cleared","cable_seated_in_saddle","cable_energized","campaign_completed"))
        C["all_replies_under_2s"]= all(v is not None and v < 2000 for v in L.values())
        C["no_http_campaign_writes"]= len(posts)==0
        txt=pg.evaluate("() => document.body.innerText + ' ' + document.documentElement.outerHTML")
        rep["brand_hits"]=len(re.findall(r"qysea|fifish|鰭源|\bx1\b", txt, re.I))
        C["zero_brand_in_live_dom"]= rep["brand_hits"]==0
        rep["pageerrors"]=errs[:10]; C["no_page_errors"]= not errs
        rep["ws_sent_all"]=pg.evaluate("() => window.__sent")
        b.close()
finally:
    proc.terminate(); proc.wait(5)
rep["passed"]=sum(bool(v) for v in C.values()); rep["total"]=len(C); rep["all_pass"]=rep["passed"]==rep["total"]
(OUT/"report.json").write_text(json.dumps(rep, ensure_ascii=False, indent=2))
print(json.dumps({"checks":C,"passed":rep["passed"],"total":rep["total"],"latency_ms":L,"brand_hits":rep.get("brand_hits"),"pageerrors":rep.get("pageerrors")}, ensure_ascii=False, indent=1))
