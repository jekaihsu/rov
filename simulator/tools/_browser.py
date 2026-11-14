"""Shared browser launch and server address helpers for the smoke scripts in this directory.

Environment variables (all optional):
  ROV_CHROMIUM              absolute path of the Chromium/Chrome executable to use
  ROV_HOST                  simulator host, default 127.0.0.1
  ROV_HTTP_PORT             simulator HTTP port, overrides each script's own default
  ROV_WS_PORT               simulator WebSocket port, overrides each script's own default
  ROV_BEFORE_HTTP_PORT / ROV_BEFORE_WS_PORT  comparison server used by browser_audio_smoke.py
  ROV_BROWSER_TIMEOUT_SCALE multiplier for timeouts obtained through timeout(), default 1
"""
import os
from pathlib import Path
from shutil import which

# Every script renders with software GL so results do not depend on the host GPU.
SOFTWARE_GL_ARGS = ('--enable-unsafe-swiftshader',)
FALLBACK_CHROMIUM = Path('/opt/pw-browsers/chromium')
_resolved = {}


class BrowserNotFound(RuntimeError):
    """No usable Chromium executable was found."""


def _merged_args(extra):
    merged = list(SOFTWARE_GL_ARGS)
    for value in extra or ():
        if value not in merged:
            merged.append(value)
    return merged


def _candidates():
    """Yield (label, executable_path) in priority order; None means Playwright's own default."""
    configured = os.environ.get('ROV_CHROMIUM')
    if configured:
        yield 'ROV_CHROMIUM', configured
        return
    yield 'playwright default', None
    system = which('google-chrome') or which('chromium')
    if system:
        yield 'system browser', system
    if FALLBACK_CHROMIUM.exists():
        yield 'fallback', str(FALLBACK_CHROMIUM)


def launch(playwright, **kwargs):
    """Launch headless Chromium with software GL, trying each known executable location in turn."""
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
        return playwright.chromium.launch(**kwargs)
    return playwright.chromium.launch(executable_path=path, **kwargs)


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


def timeout(milliseconds):
    """Scale a timeout for slow machines; software rendering can run at a few frames per second."""
    return int(milliseconds * float(os.environ.get('ROV_BROWSER_TIMEOUT_SCALE') or 1))
