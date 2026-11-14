"""Compare repeated keyboard-axis to rendered-pose latency trials on two running revisions."""
import argparse
import json
import statistics
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/tmp/t03-evidence')
    parser.add_argument('--runs', type=int, default=7)
    parser.add_argument('--presentation', choices=['real', 'assisted'], default='assisted')
    parser.add_argument('--only', choices=['before', 'after', 'both'], default='both')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader'])
        for name, port, ws in [('before', 8093, 8793), ('after', 8092, 8792)]:
            if args.only != 'both' and name != args.only:
                continue
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            url = (f'http://127.0.0.1:{port}/?ws=ws://127.0.0.1:{ws}&play=1&nointro'
                   f'&room=latency&cam=onboard&presentation={args.presentation}')
            page.goto(url)
            page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=180000)
            values = []
            for trial in range(args.runs):
                page.evaluate("document.querySelector('#btnReset').click()")
                page.wait_for_timeout(500)
                page.evaluate("""for (const key of ['surface','mid','bottom']) {
                    document.querySelector('#c_'+key+'_kn').value=0;
                }
                document.querySelector('#c_turbulence').value=0;
                document.querySelector('#btnCur').click();""")
                page.wait_for_timeout(3000)
                neutral = page.evaluate("""() => new Promise(resolve => {
                    const samples = [];
                    function sample() {
                        samples.push([performance.now(),...window.__viewer.rovG.position.toArray()]);
                        if (samples.length<8) requestAnimationFrame(sample);
                        else resolve(samples);
                    }
                    requestAnimationFrame(sample);
                })""")
                rows = page.evaluate("""neutral => new Promise(resolve => {
                    const viewer = window.__viewer;
                    const last = neutral.at(-1);
                    const first = neutral[0];
                    const base = viewer.rovG.position.clone();
                    const vx = (last[1]-first[1])/(last[0]-first[0]);
                    const vz = (last[3]-first[3])/(last[0]-first[0]);
                    const rows = [];
                    viewer.rc.rc_lock = 0;
                    const start = performance.now();
                    document.body.dispatchEvent(new KeyboardEvent('keydown',
                        {code:'ArrowUp', bubbles:true}));
                    function measure() {
                        const elapsed = performance.now()-start;
                        const pos = viewer.rovG.position;
                        rows.push([elapsed,...pos.toArray()]);
                        if (Math.hypot(pos.x-base.x-vx*elapsed,pos.z-base.z-vz*elapsed)>.02 || elapsed>5000) {
                            document.body.dispatchEvent(new KeyboardEvent('keyup',
                                {code:'ArrowUp', bubbles:true}));
                            resolve({rows,latency:elapsed>5000?null:elapsed});
                        } else requestAnimationFrame(measure);
                    }
                    requestAnimationFrame(measure);
                })""", neutral)
                if rows['latency'] is None:
                    raise RuntimeError(f'{name} trial {trial+1}: no movement within 5s')
                rows['neutral'] = neutral
                values.append(rows['latency'])
                (output / f'{name}-{trial+1}.json').write_text(json.dumps(rows))
                print(name, 'trial', trial+1, 'latency_ms_20mm', rows['latency'], flush=True)
            result = {'values_ms': values, 'median_ms': statistics.median(values),
                      'min_ms': min(values), 'max_ms': max(values)}
            (output / f'{name}-summary.json').write_text(json.dumps(result, indent=2))
            print(name, result, flush=True)
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
