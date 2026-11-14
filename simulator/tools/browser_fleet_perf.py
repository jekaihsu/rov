"""Compare unchanged peer cable work, and verify new packets still update it."""
import json
import argparse
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base

parser = argparse.ArgumentParser()
parser.add_argument('--url', default=f'{http_base(8093)}/')
parser.add_argument('--snapshot', type=Path)
args = parser.parse_args()

out = Path(__file__).resolve().parents[1] / 'output' / 'fleet-performance'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page()
    page.goto(args.url)
    page.wait_for_function('window.__menu?.ready')
    result = page.evaluate('''async()=>{
      const THREE=await import('three'),{Fleet}=await import('./fleet.js');
      const scene=new THREE.Scene(), fleet=new Fleet(scene);
      fleet.reset({vehicle_catalogue:[{id:'falcon',model:'models/falcon.glb'}]});
      const vehicle=(id,offset)=>({id,model_id:'falcon',pos:[0,offset,3],q:[1,0,0,0],
        tether:{nodes:Array.from({length:30},(_,i)=>[i*.1,offset,3+Math.sin(i*.2)])}});
      const packet={vehicle_id:'v1',t:1,vehicles:[vehicle('v2',2),vehicle('v3',4)]};
      fleet.ingest(packet);
      await new Promise(resolve=>setTimeout(resolve,1000));
      let updates=0;for(const peer of fleet.peers.values()){
        const original=peer.cable.update.bind(peer.cable);
        peer.cable.update=(...args)=>{updates++;return original(...args);};
      }
      // Warm both code paths, then compare the same 120 display frames.
      for(let i=0;i<30;i++){for(const peer of fleet.peers.values())peer.cableDirty=true;fleet.update(1/60);}
      updates=0;let start=performance.now();
      for(let i=0;i<120;i++){for(const peer of fleet.peers.values())peer.cableDirty=true;fleet.update(1/60);}
      const previousMs=performance.now()-start,previousUpdates=updates;
      fleet.ingest(packet);updates=0;start=performance.now();
      for(let i=0;i<120;i++)fleet.update(1/60);
      const optimizedMs=performance.now()-start,optimizedUpdates=updates;
      const before=Array.from(fleet.peers.get('v2').cable.pos);
      packet.t=2;packet.vehicles[0].tether.nodes[15][2]+=1;
      fleet.ingest(packet);fleet.update(1/60);
      const after=Array.from(fleet.peers.get('v2').cable.pos);
      const geometryChanged=before.some((v,i)=>v!==after[i]);
      const finalUpdates=updates;
      fleet.reset(null);
      return {previousMs,optimizedMs,previousUpdates,optimizedUpdates,finalUpdates,
        geometryChanged,peersDisposed:fleet.peers.size===0};
    }''')
    result['bufferFrames'] = page.evaluate("""async captured => {
      const {StateBuffer} = await import('./state_buffer.js');
      const local = new StateBuffer();
      const remote = new StateBuffer();
      const nodes = Array.from({length:60}, (_, i) => [i*.1, 0, 3]);
      function vehicle(id) {
        return {id, pos:[0,0,3], q:[1,0,0,0], vel:[.1,0,0], tether:{nodes},
          telemetry:{samples:Array.from({length:500}, (_, i) => i), name:'training'}};
      }
      const packet = captured || {...vehicle('v1'), vehicle_id:'v1', t:0,
        vehicles:['v1','v2','v3'].map(vehicle),
        operations:{objects:Array.from({length:20}, (_, id) => ({...vehicle(id), tether:undefined}))},
        environment:{fish_schools:Array.from({length:20}, (_, id) => ({id, pos:[id,0,3], vel:[.1,0,0]}))}};
      const times = [];
      for (let frame=0; frame<660; frame++) {
        const now = frame/60;
        const start = performance.now();
        if (frame%3===0) {
          const snapshot = {...packet, t:now};
          local.push(snapshot, now+100);
          remote.push(snapshot, now+100);
        }
        local.sample(now+100, true);
        remote.sample(now+100);
        if (frame>=60) times.push(performance.now()-start);
      }
      times.sort((a,b) => a-b);
      return {vehicles:3, frames:times.length, meanMs:times.reduce((a,b) => a+b, 0)/times.length,
        medianMs:times[Math.floor(times.length/2)], p95Ms:times[Math.floor(times.length*.95)]};
    }""", json.loads(args.snapshot.read_text()) if args.snapshot else None)
    quality = page.evaluate('''async()=>{
      const {configureRenderQuality,updateRenderQuality,renderQualityInfo}=await import('./render_quality.js');
      const renderer=window.__menu.renderer,canvas=renderer.domElement;
      configureRenderQuality(renderer,'auto');
      const css=canvas.style.width,initial=canvas.width;
      for(let i=0;i<600;i++)updateRenderQuality(renderer,1/30);
      const reduced=canvas.width,low=renderQualityInfo(renderer).scale;
      for(let i=0;i<1200;i++)updateRenderQuality(renderer,1/60,{suspended:true});
      const suspended=renderQualityInfo(renderer).scale;
      for(let i=0;i<4800;i++)updateRenderQuality(renderer,1/60);
      const info=renderQualityInfo(renderer),recovered=info.scale;
      configureRenderQuality(renderer,'high');
      const fixed=canvas.width;
      for(let i=0;i<600;i++)updateRenderQuality(renderer,1/30);
      const unchanged=canvas.width===fixed;
      configureRenderQuality(renderer,'auto');
      return {initial,reduced,low,suspended,recovered,unchanged,cssUnchanged:canvas.style.width===css,
        floor:Math.round(info.hardwareProfile.floor*100),ceiling:Math.round(info.hardwareProfile.ceiling*100),
        hardwareTier:info.hardwareTier,hardwareRenderer:info.hardwareRenderer,hardwareLabel:info.hardwareLabel};
    }''')
    assert quality['reduced'] < quality['initial'], quality
    assert quality['low'] == quality['suspended'] == quality['floor'], quality
    assert quality['recovered'] == quality['ceiling'] and quality['unchanged'] and quality['cssUnchanged'], quality
    result['adaptiveResolution'] = quality
    assert result['previousUpdates'] == 240, result
    assert result['optimizedUpdates'] == 2, result
    assert result['finalUpdates'] == 4 and result['geometryChanged'], result
    assert result['peersDisposed'], result
    (out/'results.json').write_text(json.dumps(result, indent=2), encoding='utf-8')
    browser.close()
print(json.dumps(result, indent=2))
