"""Check analytical box center and oracle degradation; capture overlay evidence."""
from pathlib import Path
from shutil import which
from playwright.sync_api import sync_playwright

out = Path(__file__).resolve().parents[2] / "output/vision"
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = p.chromium.launch(executable_path=which("chromium"), args=["--enable-unsafe-swiftshader"])
    page = browser.new_page(viewport={"width": 1600, "height": 900}, record_video_dir=str(out))
    errors = []
    page.on("pageerror", lambda error: errors.append(str(error)))
    page.goto("http://127.0.0.1:8080/?play=1&nointro&cam=onboard&vision")
    page.wait_for_function("window.__viewer?.S && window.rovVision")
    result = page.evaluate("""async () => {
        const {THREE} = window.__viewer;
        const {inspectObservation} = await import('./observation_camera.js');
        const {OracleDetector} = await import('./vision/detector.js');
        const scene = new THREE.Scene();
        const camera = new THREE.PerspectiveCamera(70,1600/900,.01,100);
        const mesh = new THREE.Mesh(new THREE.BoxGeometry(1,1,1),new THREE.MeshBasicMaterial());
        mesh.position.z = -3;
        scene.add(mesh);
        const context = {scene,camera,camMode:'onboard',all:true,
            targets:[{entity_id:'test',category:'engineering',mesh}]};
        const truth = inspectObservation(context);
        if (truth.length !== 1) throw Error('missing analytical target');
        const box = truth[0].box;
        const error = Math.hypot((box[0]+box[2]/2-.5)*1600,(box[1]+box[3]/2-.5)*900);
        if (error >= 2) throw Error('box center error '+error);
        let seed=13;
        function random() {seed=(1664525*seed+1013904223)>>>0;return seed/4294967296;}
        const detector = new OracleDetector({miss:.3,falsePositive:.2,random});
        let missed=0, falsePositives=0;
        for(let i=0;i<10000;i++) {
            const detections = await detector.detect({truth});
            if(!detections.some(d=>d.entity_id==='test')) missed++;
            if(detections.some(d=>d.cls==='unknown')) falsePositives++;
        }
        if(Math.abs(missed/10000-.3)>.02 || Math.abs(falsePositives/10000-.2)>.02)
            throw Error('oracle distribution');
        // Show a controlled visible fixture using the same renderer and production overlay.
        const viewer=window.__viewer;
        window.__skipRender=true;
        const rendererCanvas=document.querySelector('#vp canvas');
        const testRenderer = new THREE.WebGLRenderer({canvas:document.createElement('canvas')});
        testRenderer.setSize(rendererCanvas.width,rendererCanvas.height);
        const light=new THREE.AmbientLight(0xffffff,1);
        scene.add(light);
        testRenderer.render(scene,camera);
        window.rovVision.update=()=>{};
        window.rovVision.overlay.width=1600;
        window.rovVision.overlay.height=900;
        const ctx=window.rovVision.overlay.getContext('2d');
        ctx.drawImage(testRenderer.domElement,0,0,1600,900);
        window.__fixtureTruth=truth;
        return {error,missRate:missed/10000,falsePositiveRate:falsePositives/10000};
    }""")
    page.screenshot(path=str(out / "before.png"))
    page.evaluate("""async () => {
        const {drawDetections} = await import('./vision/overlay.js');
        const canvas=window.rovVision.overlay;
        drawDetections(canvas.getContext('2d'),window.__fixtureTruth.map(t=>({...t,cls:t.category,score:1})),1600,900);
    }""")
    page.wait_for_timeout(200)
    page.screenshot(path=str(out / "after.png"))
    page.wait_for_timeout(1000)
    assert not errors, errors
    print(result)
    page.close()
    browser.close()
