"""Exercise screen, capture, offscreen, resize and camera pass lifecycle on real WebGL."""
import json
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path='/usr/bin/chromium', headless=True,
                                args=['--enable-unsafe-swiftshader'])
    page = browser.new_page()
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.on('console', lambda message: errors.append(message.text) if 'THREE.WebGLProgram: Shader Error' in message.text else None)
    page.route('**/fixture.html', lambda r: r.fulfill(body='''<script type="importmap">{"imports":{"three":"/vendor/three/build/three.module.js","three/addons/":"/vendor/three/examples/jsm/"}}</script>''', content_type='text/html'))
    page.goto('http://127.0.0.1:8093/fixture.html')
    result = page.evaluate('''async()=>{
      const T=await import('three');
      const {installUnderwaterPipeline}=await import('./fx/pipeline.js');
      const {applyUnderwaterLighting}=await import('./underwater_lighting.js');
      const {configureRenderQuality}=await import('./render_quality.js');
      const r=new T.WebGLRenderer({preserveDrawingBuffer:true}), scene=new T.Scene(), camera=new T.PerspectiveCamera(60,1,.01,100);
      camera.position.set(0,-2,3);camera.lookAt(0,-2,0);
      scene.fog=new T.Fog(0x102a30,.3,4);
      const mesh=new T.Mesh(new T.BoxGeometry(),new T.MeshStandardMaterial({color:0xff4020}));
      mesh.position.y=-2;scene.add(mesh,new T.HemisphereLight(0xffffff,0x112233,2));
      applyUnderwaterLighting(scene);
      const surface=new T.Mesh(new T.PlaneGeometry(50,50),new T.MeshBasicMaterial());
      surface.rotation.x=-Math.PI/2;scene.add(surface);
      const fx=installUnderwaterPipeline(r,{surface});
      configureRenderQuality(r,'performance');applyUnderwaterLighting(scene,null,r);fx.setEnhancements(true);r.render(scene,camera);
      const lowBypass=fx.composer===null;
      configureRenderQuality(r,'high');applyUnderwaterLighting(scene,null,r);r.render(scene,camera);
      const composed=!!fx.composer;
      const geometryIgnored=surface.userData.observationIgnore===true &&
        scene.getObjectByName('water-suspension').userData.observationIgnore===true;
      let calls=0;
      const {ShaderPass}=await import('three/addons/postprocessing/ShaderPass.js');
      const pass=new ShaderPass({uniforms:{tDiffuse:{value:null}},
        vertexShader:'varying vec2 vUv; void main(){vUv=uv;gl_Position=projectionMatrix*modelViewMatrix*vec4(position,1.);}',
        fragmentShader:'uniform sampler2D tDiffuse;varying vec2 vUv;void main(){gl_FragColor=texture2D(tDiffuse,vUv);}'});
      const render=pass.render.bind(pass);pass.render=function(...args){calls++;render(...args);};
      fx.setCameraPass(pass);r.render(scene,camera);
      r.setPixelRatio(.7);r.setSize(640,360);r.render(scene,camera);
      const size=r.getDrawingBufferSize(new T.Vector2());
      const resized=fx.width===size.x&&fx.height===size.y;
      const target=new T.WebGLRenderTarget(64,64);r.setRenderTarget(target);r.render(scene,camera);
      const offscreenPreserved=r.getRenderTarget()===target&&calls===2;r.setRenderTarget(null);
      const blob=await new Promise(resolve=>r.domElement.toBlob(resolve));
      fx.setCameraPass(null);pass.dispose();fx.setEnhancements(false);r.render(scene,camera);
      const bypassAgain=calls===2;
      fx.dispose();target.dispose();
      return {lowBypass,composed,geometryIgnored,resized,offscreenPreserved,bypassAgain,png:blob.type==='image/png'};
    }''')
    assert all(result.values()), result
    assert not errors, errors
    print(json.dumps(result))
    browser.close()
