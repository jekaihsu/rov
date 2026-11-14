"""Exercise gesture activation and render a 30-second Web Audio + canvas review clip."""
import base64
from pathlib import Path
from playwright.sync_api import sync_playwright
from _browser import launch, http_base, ws_base

OUT = Path(__file__).resolve().parents[1] / 'output' / 'audio-validation'
OUT.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    browser = launch(p, headless=True, args=['--enable-unsafe-swiftshader'])
    page = browser.new_page(viewport={'width': 1600, 'height': 900})
    errors = []
    page.on('pageerror', lambda error: errors.append(str(error)))
    page.goto(f"{http_base(8093, 'ROV_BEFORE_HTTP_PORT')}/?ws={ws_base(8793, 'ROV_BEFORE_WS_PORT')}&nointro")
    page.wait_for_selector('#launchForm')
    page.screenshot(path=str(OUT / 'before.png'))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&nointro')
    page.wait_for_selector('#launchForm')
    page.get_by_text('音效', exact=True).click()
    page.screenshot(path=str(OUT / 'after.png'))
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&room=audio')
    page.wait_for_function('window.__viewer?.S?.vehicle_id')
    assert page.evaluate("import('./audio/engine.js').then(m => !m.installAudio().ctx)")
    page.locator('canvas.gl').click(position={'x': 20, 'y': 20})
    page.wait_for_function("import('./audio/engine.js').then(m => m.installAudio().ctx?.state === 'running')")
    page.evaluate('''async () => {
      const engine = (await import('./audio/engine.js')).installAudio();
      const analyser = engine.ctx.createAnalyser();
      engine.master.connect(analyser);
      window.audioAnalyser = analyser;
      const destination = engine.ctx.createMediaStreamDestination();
      engine.master.connect(destination);
      const canvas = window.__viewer.renderer?.domElement || document.querySelector('canvas.gl');
      const stream = canvas.captureStream(15);
      stream.addTrack(destination.stream.getAudioTracks()[0]);
      const chunks = [];
      const recorder = new MediaRecorder(stream, {mimeType: 'video/webm;codecs=vp9,opus',
        videoBitsPerSecond: 220000, audioBitsPerSecond: 64000});
      recorder.ondataavailable = event => chunks.push(event.data);
      recorder.onstop = async () => {
        const bytes = new Uint8Array(await new Blob(chunks).arrayBuffer());
        let binary = '';
        for (const byte of bytes) binary += String.fromCharCode(byte);
        window.audioClip = btoa(binary);
      };
      recorder.start();
      window.__viewer.rc.rc_lock = 0;
      window.__viewer.rc.left_ud = 1650;
      setTimeout(() => { window.__viewer.rc.right_switch = 2; }, 6000);
      setTimeout(() => { window.__viewer.setCam('onboard'); }, 12000);
      setTimeout(() => { window.__viewer.rc.keep_depth = 1; }, 18000);
      setTimeout(() => { window.__viewer.rc.left_ud = 1500; }, 24000);
      setTimeout(() => recorder.stop(), 30000);
    }''')
    page.wait_for_timeout(1500)
    peak = page.evaluate('''() => {
      const samples = new Float32Array(window.audioAnalyser.fftSize);
      window.audioAnalyser.getFloatTimeDomainData(samples);
      return Math.max(...samples.map(Math.abs));
    }''')
    assert peak > 0, peak
    page.wait_for_function('window.audioClip', timeout=45000)
    (OUT / 'audio-30s.webm').write_bytes(base64.b64decode(page.evaluate('window.audioClip')))
    assert not errors, errors
    page.goto(f'{http_base(8092)}/?ws={ws_base(8792)}&play=1&nointro&mute')
    page.wait_for_function('window.__viewer?.S')
    page.locator('canvas.gl').click(position={'x': 20, 'y': 20})
    assert page.evaluate("import('./audio/engine.js').then(m => !m.installAudio().ctx)")
    browser.close()
    print(f'Audio smoke passed: gesture, nonzero waveform (peak={peak:.4f}), mute, no page errors; {OUT}')
