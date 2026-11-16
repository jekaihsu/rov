"""Shared browser launch and server address helpers for the smoke scripts in this directory.

Environment variables (all optional):
  ROV_BROWSER_LOCALE        browser test locale (default zh-TW, matching existing Chinese assertions)
  ROV_CHROMIUM              absolute path of the Chromium/Chrome executable to use
  ROV_HOST                  simulator host, default 127.0.0.1
  ROV_HTTP_PORT             simulator HTTP port, overrides each script's own default
  ROV_WS_PORT               simulator WebSocket port, overrides each script's own default
  ROV_BEFORE_HTTP_PORT / ROV_BEFORE_WS_PORT  comparison server used by browser_audio_smoke.py
  ROV_BROWSER_TIMEOUT_SCALE multiplier for timeouts obtained through timeout(); when unset and the
                            host is CPU-saturated, timeout() auto-scales (assertions unchanged)
  ROV_BROWSER_GL            software (default) or gpu: software forces SwiftShader; gpu keeps hardware
                            acceleration (pair with ROV_CHROMIUM pointing at a local Chrome build)
  ROV_BROWSER_EXTRA_ARGS    space-separated extra Chromium flags appended after the GL mode args
"""
import os
import time
from pathlib import Path
from shutil import which

# Every script defaults to software GL so results do not depend on the host GPU.
SOFTWARE_GL_ARGS = ('--enable-unsafe-swiftshader',)
# Hardware path for real-GPU benches: ignore the blocklist so older GPUs still report acceleration.
GPU_GL_ARGS = ('--enable-gpu', '--ignore-gpu-blocklist')
FALLBACK_CHROMIUM = Path('/opt/pw-browsers/chromium')
_resolved = {}
_timeout_scale = None
# Soft-GL smokes under a fully busy host still check the same conditions; they only need more wall time.
_AUTO_LOAD_SCALE = 3.0


class BrowserNotFound(RuntimeError):
    """No usable Chromium executable was found."""


def gl_mode():
    """Return 'software' or 'gpu' from ROV_BROWSER_GL (default software)."""
    value = (os.environ.get('ROV_BROWSER_GL') or 'software').strip().lower()
    return 'gpu' if value in ('gpu', 'hardware', 'hw') else 'software'


def _extra_env_args():
    raw = os.environ.get('ROV_BROWSER_EXTRA_ARGS') or ''
    return [part for part in raw.split() if part]


def _merged_args(extra):
    mode = gl_mode()
    base = list(GPU_GL_ARGS if mode == 'gpu' else SOFTWARE_GL_ARGS)
    skip = set(SOFTWARE_GL_ARGS if mode == 'gpu' else GPU_GL_ARGS)
    for value in list(extra or ()) + _extra_env_args():
        if value in skip or value in base:
            continue
        base.append(value)
    return base


def _candidates():
    """Yield (label, executable_path) in priority order; None means Playwright's own default."""
    configured = os.environ.get('ROV_CHROMIUM')
    if configured:
        yield 'ROV_CHROMIUM', configured
        return
    yield 'playwright default', None
    system = which('google-chrome') or which('chromium') or which('google-chrome-stable')
    if system:
        yield 'system browser', system
    if FALLBACK_CHROMIUM.exists():
        yield 'fallback', str(FALLBACK_CHROMIUM)


def launch(playwright, **kwargs):
    """Launch Chromium with the configured GL mode, trying each known executable location in turn."""
    kwargs.pop('executable_path', None)
    kwargs.pop('channel', None)
    kwargs.setdefault('headless', True)
    kwargs['args'] = _merged_args(kwargs.get('args'))
    if 'path' in _resolved:
        return _start(playwright, _resolved['path'], kwargs)
    failures = []
    for label, path in _candidates():
        if path is not None and not Path(path).is_file():
            failures.append(f'{label}: {path} does not exist')
            continue
        try:
            browser = _start(playwright, path, kwargs)
        except Exception as error:  # Playwright raises its own Error type for a missing or broken build.
            failures.append(f'{label}: {str(error).splitlines()[0]}')
            continue
        _resolved['path'] = path
        return browser
    raise BrowserNotFound(
        'Could not launch Chromium. Set ROV_CHROMIUM to the absolute path of a Chromium or Chrome executable '
        '(for example ROV_CHROMIUM=/opt/pw-browsers/chromium), or install a browser build matching the '
        'installed Playwright package.\nTried:\n  ' + '\n  '.join(failures))


def _start(playwright, path, kwargs):
    if path is None:
        browser = playwright.chromium.launch(**kwargs)
    else:
        browser = playwright.chromium.launch(executable_path=path, **kwargs)
    original_page = browser.new_page
    original_context = browser.new_context

    def new_page(**options):
        options.setdefault('locale', os.environ.get('ROV_BROWSER_LOCALE', 'zh-TW'))
        return original_page(**options)

    def new_context(**options):
        options.setdefault('locale', os.environ.get('ROV_BROWSER_LOCALE', 'zh-TW'))
        return original_context(**options)

    browser.new_page = new_page
    browser.new_context = new_context
    return browser


def host():
    return os.environ.get('ROV_HOST', '127.0.0.1')


def http_port(default=8092, env='ROV_HTTP_PORT'):
    return int(os.environ.get(env) or default)


def ws_port(default=8792, env='ROV_WS_PORT'):
    return int(os.environ.get(env) or default)


def http_base(default=8092, env='ROV_HTTP_PORT'):
    """Server origin without a trailing slash, e.g. http://127.0.0.1:8092."""
    return f'http://{host()}:{http_port(default, env)}'


def ws_base(default=8792, env='ROV_WS_PORT'):
    """WebSocket address, e.g. ws://127.0.0.1:8792."""
    return f'ws://{host()}:{ws_port(default, env)}'


def ws_query():
    """'&ws=...' for scripts that rely on the viewer's built-in WebSocket default unless ROV_WS_PORT is set."""
    return f'&ws={ws_base()}' if os.environ.get('ROV_WS_PORT') else ''


def _host_cpu_saturated(spin_s=0.01, stretch_limit=0.022, trials=6):
    """Same busy-host probe as the SDK wall-clock FPS skip: stretched busy-wait or high loadavg."""
    spins = []
    for _ in range(trials):
        start = time.perf_counter()
        target = start + spin_s
        while time.perf_counter() < target:
            pass
        spins.append(time.perf_counter() - start)
    spins.sort()
    median = spins[len(spins) // 2]
    if median > stretch_limit:
        return True, f"busy-wait({spin_s}) median {median:.3f}s"
    if hasattr(os, "getloadavg"):
        load1 = os.getloadavg()[0]
        cpus = os.cpu_count() or 1
        if load1 >= max(1.0, cpus * 0.85):
            return True, f"loadavg1={load1:.2f} cpus={cpus}"
    return False, ""


def timeout_scale():
    """Effective ROV_BROWSER_TIMEOUT_SCALE, with a one-shot auto bump when the host is saturated."""
    global _timeout_scale
    if _timeout_scale is not None:
        return _timeout_scale
    configured = os.environ.get('ROV_BROWSER_TIMEOUT_SCALE')
    if configured:
        _timeout_scale = float(configured)
        return _timeout_scale
    saturated, reason = _host_cpu_saturated()
    if saturated:
        _timeout_scale = _AUTO_LOAD_SCALE
        print(f'ROV_BROWSER_TIMEOUT_SCALE auto={_timeout_scale} ({reason})', flush=True)
    else:
        _timeout_scale = 1.0
    return _timeout_scale


def timeout(milliseconds):
    """Scale a timeout for slow machines; software rendering can run at a few frames per second."""
    return int(milliseconds * timeout_scale())


def skip_render(page, enabled=True):
    """Toggle the viewer's __skipRender flag so waits can pump sockets/input without soft-GL cost."""
    page.evaluate('(on) => { window.__skipRender = !!on; }', enabled)


class without_render:
    """Context manager: keep the animation/input loop, skip WebGL draws for the duration."""

    def __init__(self, *pages):
        self.pages = pages

    def __enter__(self):
        for page in self.pages:
            skip_render(page, True)
        return self.pages[0] if len(self.pages) == 1 else self.pages

    def __exit__(self, exc_type, exc, tb):
        for page in self.pages:
            try:
                skip_render(page, False)
            except Exception:
                pass
        return False


def pump_until(page, expression, *, timeout_ms, arg=None, allies=(), skip_page_render=True):
    """Bring page forward, skip soft-GL on allies, and poll until expression is truthy.

    Under a fully busy host, background software-GL tabs can starve the active tab's socket
    and input pumps for minutes. Assertions stay the same; only scheduling changes.
    Set skip_page_render=False when the wait itself needs the active tab's animation/camera
    update (for example a spring settle); allies still skip draw.
    """
    deadline = time.monotonic() + (timeout_ms / 1000)
    for ally in allies:
        try:
            skip_render(ally, True)
        except Exception:
            pass
    if skip_page_render:
        skip_render(page, True)
    page.bring_to_front()
    last_error = None
    try:
        while time.monotonic() < deadline:
            page.bring_to_front()
            try:
                if arg is None:
                    if page.evaluate(expression):
                        return True
                elif page.evaluate(expression, arg):
                    return True
            except Exception as error:
                last_error = error
            page.wait_for_timeout(100)
    finally:
        if skip_page_render:
            try:
                skip_render(page, False)
            except Exception:
                pass
        for ally in allies:
            try:
                skip_render(ally, False)
            except Exception:
                pass
    if last_error:
        raise last_error
    raise TimeoutError(f'pump_until exceeded {timeout_ms} ms')
