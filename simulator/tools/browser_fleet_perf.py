"""Compare unchanged peer cable work, and verify new packets still update it."""
import json
from pathlib import Path
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[1] / 'output' / 'fleet-performance'
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(channel='chrome', headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page()
    page.goto('http://127.0.0.1:8093/')
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
