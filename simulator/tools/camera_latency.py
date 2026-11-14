"""Compare two running revisions; save 1600x900 screenshots and ten seconds of pose samples."""
import argparse
import json
from pathlib import Path
from playwright.sync_api import sync_playwright


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--output', default='/tmp/t03-evidence')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=True, args=['--enable-unsafe-swiftshader'])
        for name, port, ws in [('before', 8093, 8793), ('after', 8092, 8792)]:
            page = browser.new_page(viewport={'width': 1600, 'height': 900})
            url = f'http://127.0.0.1:{port}/?ws=ws://127.0.0.1:{ws}&play=1&nointro&room=latency&cam=onboard'
            page.goto(url)
            page.wait_for_function('window.__viewer?.S?.vehicle_id', timeout=180000)
            page.evaluate("document.querySelector('#btnReset').click()")
            page.wait_for_timeout(500)
            page.evaluate("""for (const key of ['surface','mid','bottom']) {
                document.querySelector('#c_'+key+'_kn').value=0;
            }
            document.querySelector('#c_turbulence').value=0;
            document.querySelector('#btnCur').click();""")
            page.wait_for_timeout(3000)
            page.screenshot(path=str(output / f'{name}.png'))
            page.evaluate('window.__viewer.rc.rc_lock=0')
            page.wait_for_timeout(700)
            page.evaluate('''window.measureRows=[];
                window.measureStart=performance.now();
                window.addEventListener('keydown', function start(e) {
                    if (e.code==='ArrowUp') window.measureStart=performance.now();
                }, {once:true});
                function measure() {
                    const viewer=window.__viewer;
                    window.measureRows.push([performance.now()-window.measureStart,...viewer.rovG.position.toArray()]);
                    if (performance.now()-window.measureStart<10000) requestAnimationFrame(measure);
                }
                requestAnimationFrame(measure);''')
            page.keyboard.down('ArrowUp')
            page.wait_for_timeout(10500)
            page.keyboard.up('ArrowUp')
            rows = page.evaluate('window.measureRows')
            (output / f'{name}.json').write_text(json.dumps(rows))
            base = rows[0][1:]
            latency = next((row[0] for row in rows if
                            sum((row[i+1]-base[i])**2 for i in [0, 2])**.5 > .02), None)
            print(name, 'latency_ms_20mm', latency, 'frames', len(rows), flush=True)
            page.close()
        browser.close()


if __name__ == '__main__':
    main()
