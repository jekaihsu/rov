"""Fly a fresh career with keyboard inputs and audit visible story cues and rendered frame intervals.

Install Playwright and Chromium; the full JPEG gallery also requires Pillow.
From simulator/, start python -m qysim.server, then run
ROV_HTTP_PORT=8080 ROV_WS_PORT=8765 python tools/playtest_audit.py.
The browser harness can also start a private server: python tools/run_browser_checks.py playtest_audit
runs the opening and first interactive part of induction. A full run writes a local report, trace and
JPEGs in output/playtest-audit/<UTC date> at the repository root and a review gallery in docs/design.
"""
import argparse
import base64
import datetime
import json
import math
import time
from pathlib import Path
from urllib.parse import parse_qs, urlencode, urlsplit

ROOT = Path(__file__).resolve().parents[2]
CATALOG = ROOT / 'simulator/viewer/career/contracts.json'
TODAY = datetime.datetime.now(datetime.timezone.utc).date().isoformat()
MOVES = dict(zip(('move_前', 'move_後', 'move_右', 'move_左', 'move_下', 'move_上'),
                 ('w', 's', 'd', 'a', 'ArrowDown', 'ArrowUp')))


def analyze(events, end):
    """A disappearing cue, an input or a frame cannot restart the silence or progress clocks."""
    last_cue = progress = 0
    beat = None
    previous = set()
    gaps, stalls, overlaps = [], [], []
    multiple = ()
    for event in events:
        t = event['t']
        cues = set(event['radio'] + event['hints'])
        changed = event['beat'] != beat
        if changed or cues - previous:
            if t - last_cue > 30:
                gaps.append((last_cue, t))
            last_cue = t
        if changed or event.get('advanced'):
            if t - progress >= 120:
                stalls.append((progress, t))
            progress = t
            beat = event['beat']
        simultaneous = tuple(event['hints']) if len(event['hints']) >= 2 else ()
        if simultaneous and simultaneous != multiple:
            overlaps.append((t, simultaneous))
        previous = cues
        multiple = simultaneous
    if end - progress >= 120:
        stalls.append((progress, end))
    if end - last_cue > 30:
        gaps.append((last_cue, end))
    return gaps, stalls, overlaps


def controls(s, contract):
    beat = s['beat']
    if s['type'] == 'dialogue' and not s['cold'] and beat not in ('loading', 'results') and '/' not in beat:
        return [], 'Enter'
    if beat in MOVES:
        axis, index = {'前': ('surge', 0), '後': ('surge', 1), '右': ('sway', 0),
                       '左': ('sway', 1), '下': ('heave', 1), '上': ('heave', 0)}[beat[-1]]
        keys = s['controls'][axis]['keys']
        return [keys[index]] if keys else [MOVES[beat]], None
    if beat in ('depth', 'light', 'photo'):
        return [], {'depth': 'h', 'light': 'l', 'photo': 'p'}[beat]
    if s['locked'] and (s['goal'] or beat in ('unlock', 'approach', 'transit')):
        return [], 'Space'
    if beat == 'incident':
        return ([s['controls']['surge']['keys'][1]] if s['coldHint'] == 'reverse' else []), None
    target = next((d for d in contract.get('deliverables', []) if d['id'] == s['goal']), {})
    point = target.get('point')
    if target.get('kind') == 'lift':
        if s.get('held'):
            return [s['controls']['heave']['keys'][0]], None
        if s.get('fish'):
            north, east, depth = s['fish']
            point = [north, east, depth - .4]
    if beat == 'approach':
        point = s['point']
    if beat == 'transit':
        point = [50, s['pos'][1], 12]
    if not point or not s['pos']:
        return [], 'h' if s['goal'] == 'depth_hold' else None
    n, e, z = [a - b for a, b in zip(point, s['pos'])]
    heading = (math.degrees(math.atan2(e, n)) - s['heading'] + 180) % 360 - 180
    dist = math.hypot(n, e)
    stop = sum(target.get('standoff', [0, 0])) / 2 or 0.5
    if target.get('kind') == 'lift':
        stop = 1.0
    axes = s['controls'] or {}

    def key(axis, index, fallback):
        codes = axes.get(axis, {}).get('keys') or []
        return codes[index] if len(codes) > index else fallback
    held = []
    # Counter the vehicle's way before reaching the requested depth or standoff.
    surge, sway, heave = s.get('velocity') or [0, 0, 0]
    vertical = z - heave * 1.5
    if abs(vertical) > .35:
        held.append(key('heave', int(vertical > 0), 'ArrowDown' if vertical > 0 else 'ArrowUp'))
    facing = target.get('face') if target.get('kind') == 'inspect' and dist < target.get('radius', 1.5) else None
    if facing:
        direction = math.degrees(math.atan2(facing[1] - s['pos'][1], facing[0] - s['pos'][0]))
        heading = (direction - s['heading'] + 180) % 360 - 180
    if abs(heading) > 10 and dist > .4:
        held.append(key('yaw', int(heading < 0), 'ArrowRight' if heading > 0 else 'ArrowLeft'))
    if abs(heading) < 35:
        forward = dist - stop - 1.5 * surge
        if forward > .15:
            held.append(key('surge', 0, 'w'))
        elif forward < -.2:
            held.append(key('surge', 1, 's'))
    if target.get('kind') == 'station_keep' and dist < 2:
        bow = math.radians(s['heading'])
        ahead = n * math.cos(bow) + e * math.sin(bow) - surge * 1.5
        side = e * math.cos(bow) - n * math.sin(bow) - sway * 1.5
        held = [code for code in held if code in axes.get('heave', {}).get('keys', [])]
        if abs(ahead) > .16:
            held.append(key('surge', int(ahead < 0), 'w' if ahead > 0 else 's'))
        if abs(side) > .16:
            if axes.get('sway', {}).get('keys'):
                held.append(key('sway', int(side < 0), 'd' if side > 0 else 'a'))
            elif abs(heading) > 15:
                held.append(key('yaw', int(heading < 0), 'ArrowRight' if heading > 0 else 'ArrowLeft'))
    shutter = s['coldHint'] == 'photo' or (target.get('kind') == 'photo' and dist <= stop + 1)
    return held, (axes.get('photo', {}).get('keys', ['p'])[0] if shutter else None)


class Audit:
    def __init__(self, page, out):
        self.page = page
        self.out = out
        self.runs = {}
        self.active = None
        self.session = page.context.new_cdp_session(page)
        page.add_init_script(path=Path(__file__).with_name('playtest_probe.js'))
        page.on('pageerror', lambda err: self.error(str(err)))
        page.on('console', self.console)
        # Chromium reports both direct and worker sockets here, once per wire frame.
        page.on('websocket', lambda ws: ws.on('framereceived', self.packet))

    def console(self, message):
        if message.type == 'error':
            self.error(message.text)
        elif message.type == 'debug' and message.text.startswith('playtest-beat '):
            self.boundary(json.loads(message.text.removeprefix('playtest-beat ')))

    def boundary(self, sample):
        """Capture the compositor as soon as a rendered node enters, even between pilot inputs."""
        from playwright.sync_api import Error
        if self.active is None or sample['level'] != self.name:
            return
        events = self.active['events']
        t = max(0, round(sample['wall'] - self.wall_start, 3))
        path = self.out / f'{self.name}-{len(events):03}.jpg'
        event = dict(t=t, beat=sample['beat'], hints=sample['hints'], radio=sample['radio'], capture=True)
        events.append(event)
        try:
            pic = self.session.send('Page.captureScreenshot', {'format': 'jpeg', 'quality': 65})
            path.write_bytes(base64.b64decode(pic['data']))
            event['shot'] = path.name
        except Error as error:
            self.error(f"節拍截圖 {sample['beat']}: {error}")
        print(self.name, sample['beat'], t, flush=True)

    def packet(self, raw):
        if isinstance(raw, str) and 'invalid_command' in raw:
            try:
                packet = json.loads(raw)
            except ValueError:
                return
            if isinstance(packet, dict) and packet.get('code') == 'invalid_command':
                self.error(raw[:1500])

    def error(self, message):
        if self.active:
            self.active['errors'].append([self.elapsed(), message])

    def click(self, selector):
        t = self.elapsed()
        self.page.click(selector)
        self.active['inputs'].append([t, 'click', selector])

    def elapsed(self):
        return round(time.monotonic() - self.start, 3)

    def begin(self, name):
        self.name = name
        self.wall_start = time.time()
        self.start = time.monotonic()
        self.active = dict(events=[], frames=[], inputs=[], errors=[], end=0, status='進行中')
        self.runs[name] = self.active

    def finish(self, status):
        self.active['events'].sort(key=lambda item: item['t'])
        self.active.update(status=status, end=self.elapsed())
        self.active = None
        # Preserve completed levels if a later page or the browser process fails.
        trace = self.out / 'trace.json'
        temporary = trace.with_suffix('.tmp')
        temporary.write_text(json.dumps(self.runs, ensure_ascii=False), encoding='utf-8')
        temporary.replace(trace)

    def fly(self, name, contract, quick=False):
        from playwright.sync_api import Error
        run = self.active
        held = set()
        previous = None
        last_click = None
        last_progress = last_tap = high_water = 0
        while True:
            if name == 'cold_open' and 'p0_induction' in parse_qs(urlsplit(self.page.url).query).get('contract', []):
                status = '完成'
                break
            try:
                s = self.page.evaluate('window.auditSample?.()')
            except Error as error:
                if 'context was destroyed' not in str(error):
                    raise
                continue
            t = self.elapsed()
            if not s:
                if t - last_progress >= 120:
                    status = '卡關'
                    break
                self.page.wait_for_timeout(200)
                continue
            if s.get('outcome') is not None:
                run['outcome'] = s['outcome']
            beat = s['beat']
            run['frames'].extend(s['frames'])
            cue = [beat, s['radio'], s['hints']]
            entered = previous is None or beat != previous[0]
            if entered:
                high_water = 0
            score = s.get('progress', 0)
            advanced = score > high_water
            if entered or advanced:
                high_water = score
                last_progress = t
            if entered and not any(e['beat'] == beat and e.get('capture') for e in run['events']):
                # Navigation may deliver the first animation frame before ownership moves to the next level.
                self.boundary(dict(level=name, beat=beat, hints=s['hints'], radio=s['radio'], wall=time.time()))
            if cue != previous or advanced:
                event = dict(t=t, beat=beat, radio=s['radio'], hints=s['hints'], advanced=advanced)
                run['events'].append(event)
                previous = cue
            first_deck_action = beat.startswith('checks/') and s.get('walked')
            if quick and name == 'p0_induction' and (first_deck_action or beat == 'move'):
                status = '完成序章首段'
                break
            if beat == 'results':
                status = '結算'
                break
            if t - last_progress >= 120:
                run['stalled_at'] = {k: s.get(k) for k in ('beat', 'pos', 'velocity', 'heading', 'locked', 'goal')}
                status = '卡關'
                break
            keys, tap = controls(s, contract)
            wanted = set(keys)
            for key in sorted(held - wanted):
                self.page.keyboard.up(key)
                run['inputs'].append([t, 'up', key])
            for key in sorted(wanted - held):
                self.page.keyboard.down(key)
                run['inputs'].append([t, 'down', key])
            held = wanted
            if t - last_tap > 1:
                point = s.get('click')
                click = (beat, point[2]) if point else None
                if point and (click != last_click or t - last_tap > 10):
                    self.page.mouse.click(point[0], point[1])
                    last_click = click
                    run['inputs'].append([t, 'click', point[2]])
                    last_tap = t
                elif tap:
                    self.page.keyboard.press(tap, delay=100)
                    run['inputs'].append([t, 'press', tap])
                    last_tap = t
            self.page.wait_for_timeout(200)
        for key in held:
            self.page.keyboard.up(key)
        self.finish(status)


def fly_contract(audit, base, job, quick=False):
    from _browser import http_base, ws_base
    from _menu import wait_ready
    page = audit.page
    name = job['id']
    if name != 'p0_induction' or 'contract=p0_induction' not in page.url:
        page.goto(base + '&menu=board')
        wait_ready(page)
        tab = page.locator('#board-tab-' + job['chapter'])
        if not tab.count():
            audit.runs[name] = {'status': '本版本看板沒有此章節'}
            return
        tab.click()
        tile = page.locator(f'[data-contract="{name}"]')
        if not tile.count():
            audit.runs[name] = {'status': '看板未提供'}
            return
        if tile.get_attribute('data-status') == 'locked':
            # Keep the fresh career intact. Open the playable scene in a disposable profile
            # with its specified equipment so later chapters still get actual flight coverage.
            browser = page.context.browser
            # Release the board's 3D preview before benchmarking the isolated dive.
            page.goto('about:blank')
            trial = browser.new_page(viewport=dict(width=1600, height=900))
            fixture = Audit(trial, audit.out)
            fixture.runs = audit.runs
            try:
                equipment = json.dumps({'version': 1, 'owned': job.get('equipment', [])})
                trial.add_init_script('localStorage.setItem("rov.career.v1", ' + json.dumps(equipment) + ')')
                query = dict(play=1, nointro=1, contract=name, scenario=job.get('launchScenario', job['scenario']),
                             model=job['vehicles'][0], mission='free_explore', seed=42)
                if job.get('exam'):
                    query.update(exam=1, fidelity='real')
                fixture.begin(name)
                trial.goto(f'{http_base()}/?ws={ws_base()}&quality=performance&room=trial{time.time_ns()}&'
                           + urlencode(query))
                fixture.fly(name, job)
                audit.runs[name]['status'] += '（未解鎖，獨立試飛）'
            finally:
                if fixture.active:
                    fixture.finish('稽核中斷')
                trial.close()
            return
        tile.click()
        audit.begin(name)
        audit.click('#contractAccept')
        confirm = page.locator('#contractAccept[data-confirming="true"]')
        if confirm.is_visible():
            audit.click('#contractAccept[data-confirming="true"]')
        page.wait_for_url(f'**contract={name}**')
    if audit.active is None:
        audit.begin(name)
    audit.fly(name, job, quick)


def play(audit, quick):
    from playwright.sync_api import Error
    from _browser import http_base, ws_base
    from _menu import wait_ready
    page = audit.page
    base = f'{http_base()}/?ws={ws_base()}&quality=performance&room=audit{time.time_ns()}'
    chapters = ('prologue', 'ch1', 'ch2')
    catalog = json.loads(CATALOG.read_text(encoding='utf-8'))['contracts']
    jobs = sorted((job for job in catalog if job['chapter'] in chapters),
                  key=lambda job: (chapters.index(job['chapter']), job['order']))
    audit.begin('cold_open')
    page.goto(base)
    wait_ready(page)
    audit.click('#titleStart')
    page.wait_for_function('''() => {
      const q = new URLSearchParams(location.search);
      return q.has('coldOpen') || q.has('contract') || window.__menu?.screen === 'main';
    }''')
    if 'coldOpen' in parse_qs(urlsplit(page.url).query):
        audit.fly('cold_open', {})
    else:
        audit.finish('此版本新遊戲未提供開場')
    for job in jobs:
        if quick and job['id'] != 'p0_induction':
            continue
        try:
            fly_contract(audit, base, job, quick)
        except Error as error:
            if audit.active:
                audit.finish('稽核中斷')
            run = audit.runs.setdefault(job['id'], {})
            run['status'] = '稽核中斷'
            run.setdefault('errors', []).append([run.get('end', 0), str(error)])
            print(job['id'], str(error), flush=True)
            if page.is_closed():
                raise
        if quick:
            break
    planned = ['p0_induction'] if quick else [
        'p0_induction', 'p1_pool_checkout', 'p2_open_water', 'c1_pier_level1', 'c1_pier_level2',
        'c1_hull_fouling', 'c1_dropped_object', 'c1_signoff_exam', 'c2_net_inspection',
        'c2_mort_recovery', 'c2_escape_event',
    ]
    for name in planned:
        audit.runs.setdefault(name, {'status': '設計表有列，尚無工單'})


def main():
    from playwright.sync_api import sync_playwright
    from _browser import gl_mode, launch, timeout
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--quick', action='store_true', help='stop after the first interactive prologue segment')
    parser.add_argument('--out', type=Path, default=ROOT / 'output/playtest-audit' / TODAY)
    parser.add_argument('--summary', type=Path, help='Markdown review gallery path (full run by default)')
    args = parser.parse_args()
    if args.quick:
        args.out = args.out / 'quick'
    elif not args.summary:
        args.summary = ROOT / 'docs/design/playtest-audit' / (TODAY + '.md')
    args.out.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = launch(pw)
        page = browser.new_page(cold_open=True, viewport=dict(width=1600, height=900))
        page.set_default_timeout(timeout(30000))
        audit = Audit(page, args.out)
        try:
            play(audit, args.quick)
        finally:
            if audit.active:
                audit.finish('稽核中斷')
            (args.out / 'trace.json').write_text(json.dumps(audit.runs, ensure_ascii=False), encoding='utf-8')
            from playtest_report import report
            report(audit.runs, args.out, args.summary, f'Chromium {browser.version} · {gl_mode()} GL')
            browser.close()
    return int(any(run['status'].startswith(('卡關', '稽核中斷')) or run.get('errors')
                   for run in audit.runs.values()))


if __name__ == '__main__':
    raise SystemExit(main())
