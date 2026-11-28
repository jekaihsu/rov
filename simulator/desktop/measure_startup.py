"""Measure a new-profile desktop launch. Pass the Electron binary followed by any platform flags."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time

from playwright.sync_api import sync_playwright

DESKTOP = Path(__file__).resolve().parent
# Measure the CPU-visible cost of shader submission and status checks without forcing a GPU fence.
PROBE = """
window.shaderTimes = {beforeMenu: 0, total: 0};
for (const proto of [WebGLRenderingContext.prototype, WebGL2RenderingContext.prototype]) {
  for (const name of ['compileShader', 'linkProgram', 'getProgramParameter']) {
    const original = proto[name];
    proto[name] = function(...args) {
      const start = performance.now();
      try {
        return original.apply(this, args);
      } finally {
        const elapsed = performance.now() - start;
        window.shaderTimes.total += elapsed;
        if (!performance.getEntriesByName('rov-menu-interactive').length) window.shaderTimes.beforeMenu += elapsed;
      }
    };
  }
}
"""


def measure(binary, flags):
    with tempfile.TemporaryDirectory() as profile, sync_playwright() as playwright:
        port_file = Path(profile) / 'DevToolsActivePort'
        start = time.time_ns() / 1e6
        proc = subprocess.Popen([binary, *flags, '--remote-debugging-port=0', '--user-data-dir=' + profile, DESKTOP],
                                env={**os.environ, 'ROV_DESKTOP_BENCH': '1'})
        try:
            deadline = time.monotonic() + 30
            while not port_file.exists():
                if proc.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Desktop debugging endpoint did not start')
                time.sleep(.02)
            port = port_file.read_text(encoding='utf-8').splitlines()[0]
            browser = playwright.chromium.connect_over_cdp(f'http://127.0.0.1:{port}')
            context = browser.contexts[0]
            context.add_init_script(PROBE)
            page = context.pages[0] if context.pages else context.wait_for_event('page')
            page.wait_for_function("window.__menu?.ready && performance.getEntriesByName('rov-model-first-render').length",
                                   polling=100, timeout=120000)
            result = page.evaluate("""start => {
              const menu = performance.getEntriesByName('rov-menu-interactive')[0].startTime;
              return {totalMs: performance.timeOrigin - start + menu, viewerMs: menu,
                firstModelRenderMs: performance.getEntriesByName('rov-model-first-render')[0].duration,
                shaderMs: window.shaderTimes};
            }""", start)
            if not result.get('shaderMs'):
                raise RuntimeError('Shader probe missed navigation')
            print(json.dumps(result, indent=2))
            page.close()
        finally:
            if proc.poll() is None:
                proc.terminate()
            proc.wait(timeout=10)


if __name__ == '__main__':
    measure(sys.argv[1], sys.argv[2:])
