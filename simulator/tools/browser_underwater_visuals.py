"""Deterministic 1600x900 scene fixtures (not piloting or physical GPU certification).
Uses server world descriptions, Environment and material shaders, frozen time and camera.
Usage: python tools/browser_underwater_visuals.py REPO OUTPUT [QUALITY]
"""
import json
import subprocess
import sys
import time
from pathlib import Path
from playwright.sync_api import sync_playwright
root = Path(sys.argv[1]).resolve()
out = Path(sys.argv[2]).resolve()
quality = sys.argv[3] if len(sys.argv) > 3 else 'medium'
sys.path.insert(0, str(root/'simulator'))
from qysim.engine import Simulator
from qysim.server import dumps
out.mkdir(parents=True, exist_ok=True)
server = subprocess.Popen([sys.executable, '-m', 'http.server', '8097', '--directory', str(root/'simulator/viewer')], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
try:
    time.sleep(1)
    with sync_playwright() as p:
        browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                    args=['--enable-unsafe-swiftshader'])
        page = browser.new_page(viewport={'width':1600,'height':900})
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda m: errors.append(m.text) if 'Shader Error' in m.text else None)
        page.route('**/fixture.html', lambda r: r.fulfill(body='''<style>body{margin:0}</style>
          <script type="importmap">{"imports":{"three":"/vendor/three/build/three.module.js","three/addons/":"/vendor/three/examples/jsm/"}}</script>''', content_type='text/html'))
        page.goto('http://127.0.0.1:8097/fixture.html')
        for name, scenario, lamps in [('reef','coral_reef',1),('grass','seagrass_meadow',1),
                                      ('harbor','harbor_inspection',1),('wreck-lit','korean_castle',2),
                                      ('wreck-dark','korean_castle',0)]:
            if len(sys.argv)>4 and name!=sys.argv[4]:
                continue
            world=json.loads(dumps(Simulator(scenario,seed=42).world_description()))
            result=page.evaluate('''async({world:w,quality,lamps})=>{
              const T=await import('three'), {Environment}=await import('./environment.js');
              const {applyUnderwaterLighting}=await import('./underwater_lighting.js');
              const {configureRenderQuality}=await import('./render_quality.js');
              const scene=new T.Scene();
              scene.background=new T.Color(0x071b20);scene.fog=new T.Fog(0x071b20,.3,w.scenario.visibility_m*1.35);
              const r=new T.WebGLRenderer({antialias:true,preserveDrawingBuffer:true});
              r.setSize(1600,900);configureRenderQuality(r,quality);r.toneMapping=T.ACESFilmicToneMapping;
              document.body.replaceChildren(r.domElement);r.domElement.style.width='1600px';r.domElement.style.height='900px';
              const env=new Environment(scene,w);
              const P=p=>new T.Vector3(-p[1],-p[2],p[0]);
              for(const ob of w.obstacles||[]){
                if(ob.type==='model') {
                  const {loadGLTF}=await import('./glb.js');
                  const gltf=await loadGLTF(ob.model);
                  const holder=new T.Group();holder.position.copy(P(ob.origin));
                  const a=ob.heading_deg*Math.PI/180;
                  holder.rotation.y=Math.atan2(-Math.cos(a),-Math.sin(a));
                  holder.add(gltf.scene);scene.add(holder);continue;
                }
                if(ob.kind==='habitat')continue;
                const material=new T.MeshStandardMaterial({color:0x625648,roughness:.9});
                if(ob.type==='cylinder') {
                  const a=P(ob.p0),b=P(ob.p1);
                  const mesh=new T.Mesh(new T.CylinderGeometry(ob.radius,ob.radius,a.distanceTo(b),24),material);
                  mesh.position.copy(a).add(b).multiplyScalar(.5);
                  mesh.quaternion.setFromUnitVectors(new T.Vector3(0,1,0),b.clone().sub(a).normalize());
                  scene.add(mesh);continue;
                }
                if(ob.type==='wall') {
                  const a=ob.normal_deg*Math.PI/180,h=w.seabed_depth-ob.top;
                  const mesh=new T.Mesh(new T.BoxGeometry(ob.width,h,.6),material);
                  mesh.position.copy(P([ob.point[0],ob.point[1],(ob.top+w.seabed_depth)/2]));
                  mesh.position.addScaledVector(new T.Vector3(-Math.sin(a),0,Math.cos(a)),-.3);
                  mesh.rotation.y=-a;scene.add(mesh);continue;
                }
                if(ob.type!=='box')continue;
                const size=ob.half.map(x=>x*2);
                const mesh=new T.Mesh(new T.BoxGeometry(size[1],size[2],size[0]),new T.MeshStandardMaterial({color:0x625648,roughness:.9}));
                mesh.position.copy(P(ob.center));mesh.rotation.y=-ob.yaw_deg*Math.PI/180;scene.add(mesh);
              }
              const subject=w.habitat?.entities.find(e=>e.kind===(w.scenario.key==='coral_reef'?'coral':'seagrass'));
              const target=P(subject?.pos||w.objectives?.[0]?.point||[w.start_pos[0]+5,w.start_pos[1],w.seabed_depth-1]);
              const eye=target.clone().add(new T.Vector3(0,1,-3));
              const camera=new T.PerspectiveCamera(65,1600/900,.02,500);
              camera.position.copy(eye);camera.lookAt(target);
              scene.background.set('#1d6378').lerp(new T.Color('#01070b'),1-Math.exp(-Math.max(0,-eye.y)/13));
              scene.fog.color.copy(scene.background);
              scene.add(new T.HemisphereLight(0xcdefff,0x123037,1.5));
              const sun=new T.DirectionalLight(0xcdefff,1.6);sun.position.set(3,10,2);scene.add(sun);
              const lamp=new T.SpotLight(0xfff2dc,lamps*130,22,Math.PI/3,.8,2);
              lamp.position.copy(eye);lamp.target.position.copy(target);scene.add(lamp,lamp.target);
              env.update(0,camera,new T.Vector3(.1,0,.05));applyUnderwaterLighting(scene,null,r);
              try {const {installUnderwaterPipeline}=await import('./fx/pipeline.js');installUnderwaterPipeline(r);}catch(e){if(!String(e).includes('Failed to fetch'))throw e;}
              r.render(scene,camera);
              const samples=[];
              for(let i=0;i<12;i++){const start=performance.now();r.render(scene,camera);r.getContext().finish();samples.push(performance.now()-start);}
              window.__fixtureCleanup=()=>{env.dispose();r.userData?.underwaterPipeline?.dispose();r.dispose();};
              return {eye:eye.toArray(),target:target.toArray(),samples,quality};
            }''', {'world':world,'quality':quality,'lamps':lamps})
            page.screenshot(path=str(out/(name+'.jpg')), type='jpeg', quality=85)
            page.evaluate('window.__fixtureCleanup()')
            (out/(name+'.json')).write_text(json.dumps(result,indent=2))
        assert not errors, errors
        browser.close()
finally:
    server.terminate()
    server.wait()
print('Five fixed scene captures and synchronized render samples passed; no shader errors.')
