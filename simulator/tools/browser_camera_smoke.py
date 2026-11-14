"""Exercise the camera rig in real Three.js without a simulation or GPU workload."""
from playwright.sync_api import sync_playwright

with sync_playwright() as playwright:
    browser = playwright.chromium.launch(headless=True)
    page = browser.new_page()
    page.route('**/camera-harness', lambda route: route.fulfill(
        content_type='text/html', body='''<script type="importmap">
        {"imports":{"three":"/vendor/three/build/three.module.js"}}</script>'''))
    page.goto('http://127.0.0.1:8092/camera-harness')
    result = page.evaluate('''async () => {
      const THREE = await import('three');
      const {createCameraRig} = await import('/camera_rig.js');
      const camera = new THREE.PerspectiveCamera(55, 1, .01, 1000);
      const rovG = new THREE.Group();
      rovG.position.y = -5;
      const controls = {target:new THREE.Vector3(), update(){this.object.lookAt(this.target);}};
      const rig = createCameraRig({camera, controls, rovG,
        renderer:{domElement:document.createElement('canvas')}, params:new URLSearchParams(),
        getAnchor:()=>new THREE.Vector3(0,0,.3), getObstacles:()=>[], onMode(){}});
      if (rig.mode!=='onboard') throw Error('real default must be onboard');
      rovG.rotation.z=.5;
      for (let i=0;i<144;i++) rig.update(1/144);
      const physical=rovG.quaternion.clone().multiply(new THREE.Quaternion(0,1,0,0));
      if(camera.quaternion.angleTo(physical)>.001) throw Error('real default must retain roll');
      const actions={};
      rig.bindInput({registerActions(definitions){Object.assign(actions,definitions);}});
      if(actions.cameraGimbal.keys.includes('KeyG')) throw Error('profile key conflict');
      actions.cameraGimbal.run();
      for (const mode of ['chase','top','orbit','cine','onboard']) {
        rig.setMode(mode);
        for (let i=0;i<144;i++) rig.update(1/144);
        if (![...camera.position.toArray(),...camera.quaternion.toArray()].every(Number.isFinite))
          throw Error('nonfinite '+mode);
      }
      rig.setMode('orbit');
      for (let i=0;i<144;i++) rig.update(1/144);
      const beforeOrbit=camera.position.clone();
      actions.cameraOrbitX.run(.6,.1);
      for (let i=0;i<144;i++) rig.update(1/144);
      if(camera.position.distanceTo(beforeOrbit)<.01) throw Error('orbit action');
      rig.setMode('onboard');
      for (let i=0;i<144;i++) rig.update(1/144);
      const up = new THREE.Vector3(0,1,0).applyQuaternion(camera.quaternion);
      if (Math.abs(up.x)>.001) throw Error('gimbal roll');
      const saved=camera.quaternion.clone();
      const restore=rig.physicalCapture({pos:[0,0,5],q:[1,0,0,0]});
      if (Math.abs(camera.quaternion.y-1)>.001) throw Error('physical pose');
      restore();
      if (camera.quaternion.angleTo(saved)>.001) throw Error('restore');
      return 'Real onboard default, input actions, orbit, gimbal and physical capture restore passed';
    }''')
    print(result)
    browser.close()
