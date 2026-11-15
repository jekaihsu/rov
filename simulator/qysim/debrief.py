"""Debrief event extraction and printable training reports for instructor review.

Optional recording fields (PROTOCOL.md): a clip or top-level ``debrief`` object may carry
precomputed ``events`` and instructor ``notes``. Frames may include ``sensors`` / ``link``;
absent fields keep legacy replay behaviour. All assessment wording is provisional.
"""
from __future__ import annotations

from copy import deepcopy
from html import escape
import math

# Lead-in when jumping to an event on the timeline (seconds of simulation time).
SEEK_LEAD_S = 5.0
# Near-full silt index treated as a white-out discussion point (provisional).
SILT_WHITEOUT = 0.85

EVENT_KINDS = (
    'instructor_inject',
    'collision',
    'tether_warn',
    'tether_snag',
    'tether_break',
    'silt_whiteout',
    'dvl_lost',
    'comms_loss',
    'objective_done',
    'penalty',
)

# Report / UI copy. Keep in sync with viewer/debrief/strings.js labels for the same keys.
STRINGS = {
    'title': '教官講評報告',
    'subtitle': '訓練講評 / DEBRIEF',
    'provisional': '門檻暫定 · 非 IMCA 認證等效 · 僅供公司內部訓練討論',
    'score': '分數',
    'elapsed': '時長',
    'vehicle': '載具',
    'events': '事件清單',
    'notes': '教官註記',
    'notesPlaceholder': '（尚無註記）',
    'screenshots': '關鍵時刻',
    'noScreenshot': '（此匯出未附截圖）',
    'seconds': 's',
    'viewpointBanner': '講評視角，非學員畫面',
    'studentView': '學員機載畫面',
    'godView': '上帝視角',
    'instructor_inject': '教官注入',
    'collision': '碰撞',
    'tether_warn': '纜線警示',
    'tether_snag': '纜線勾纏',
    'tether_break': '斷纜',
    'silt_whiteout': '揚沙全白',
    'dvl_lost': 'DVL 失鎖',
    'comms_loss': '通訊中斷',
    'objective_done': '任務目標完成',
    'penalty': '考核扣分',
    'missing': '—',
    'colTime': '時間',
    'colKind': '事件',
    'colDetail': '說明',
}


def seek_time(event_t, lead_s=SEEK_LEAD_S, start_t=0.0):
    """Jump target for an event marker: a few seconds before the event, not before the clip start."""
    if not isinstance(event_t, (int, float)) or not math.isfinite(event_t):
        raise ValueError('event_t must be finite')
    if not isinstance(lead_s, (int, float)) or not math.isfinite(lead_s) or lead_s < 0:
        raise ValueError('lead_s must be a non-negative finite number')
    return max(float(start_t), float(event_t) - float(lead_s))


def _event(kind, t, detail='', **extra):
    row = {'kind': kind, 't': round(float(t), 3), 'detail': detail}
    row.update(extra)
    return row


def _rising(prev, now):
    return (not prev) and bool(now)


def extract_events_from_frames(frames, injections=None):
    """Build a debrief timeline from recorded viewer frames (qysim-replay clips).

    Older recordings without ``sensors`` / ``link`` still yield collision, tether, silt,
    objective and penalty markers from the fields they already store.
    """
    events = []
    for item in injections or ():
        start = item.get('start', item.get('t'))
        if start is None:
            continue
        kind = item.get('kind', 'inject')
        events.append(_event('instructor_inject', start,
                             detail=str(kind), injection=kind,
                             vehicle_id=item.get('vehicle_id')))
    prev_broken = False
    prev_warn = False
    prev_wrap = False
    prev_silt = False
    prev_dvl_lost = False
    prev_comms = False
    prev_done = {}
    seen_collision = set()
    seen_penalty = set()
    for frame in frames or ():
        t = float(frame.get('t', 0))
        for contact in frame.get('events') or ():
            if not isinstance(contact, dict):
                continue
            key = (contact.get('t'), contact.get('obstacle'), contact.get('severity'),
                   contact.get('where'))
            if key in seen_collision:
                continue
            seen_collision.add(key)
            when = contact.get('t', t)
            detail = f"{contact.get('obstacle', '')} · {contact.get('severity', '')}"
            events.append(_event('collision', when, detail=detail.strip(' ·'),
                                 severity=contact.get('severity'),
                                 obstacle=contact.get('obstacle')))
        tether = frame.get('tether') or {}
        wraps = tether.get('wraps') or {}
        snagged = bool(wraps) or bool(tether.get('snagged_on'))
        warn = bool(tether.get('warn'))
        broken = bool(tether.get('broken'))
        if _rising(prev_warn, warn):
            events.append(_event('tether_warn', t, detail=f"{tether.get('tension_max', '')} N"))
        if _rising(prev_wrap, snagged):
            names = list(wraps) if isinstance(wraps, dict) else []
            events.append(_event('tether_snag', t, detail=', '.join(names) or 'snag'))
        if _rising(prev_broken, broken):
            events.append(_event('tether_break', t))
        prev_warn, prev_wrap, prev_broken = warn, snagged, broken
        silt = float(frame.get('silt') or 0)
        white = silt >= SILT_WHITEOUT
        if _rising(prev_silt, white):
            events.append(_event('silt_whiteout', t, detail=f'silt={silt:.2f}'))
        prev_silt = white
        sensors = frame.get('sensors') or {}
        dvl = sensors.get('dvl') or {}
        dvl_lost = dvl.get('status') == 'lost'
        if _rising(prev_dvl_lost, dvl_lost):
            events.append(_event('dvl_lost', t, detail=str(dvl.get('reason') or '')))
        prev_dvl_lost = dvl_lost
        link = frame.get('link') or {}
        lost = link.get('state') == 'lost'
        if _rising(prev_comms, lost):
            events.append(_event('comms_loss', t, detail=str(link.get('cause') or '')))
        prev_comms = lost
        score = frame.get('score') or {}
        for index, objective in enumerate(score.get('objectives') or ()):
            done = bool(objective.get('done'))
            if _rising(prev_done.get(index), done):
                events.append(_event('objective_done', t,
                                     detail=str(objective.get('label') or index)))
            prev_done[index] = done
        for penalty in score.get('penalties') or ():
            key = (penalty.get('t'), penalty.get('reason'), penalty.get('points'))
            if key in seen_penalty:
                continue
            seen_penalty.add(key)
            events.append(_event('penalty', penalty.get('t', t),
                                 detail=str(penalty.get('reason') or ''),
                                 points=penalty.get('points')))
    events.sort(key=lambda row: (row['t'], row['kind']))
    return events


def extract_events_from_report(report):
    """Timeline markers from an instructor ``training_report`` (T17 evidence)."""
    report = report or {}
    events = []
    for item in report.get('events') or ():
        if 'restored_at' in item:
            continue
        if item.get('kind') == 'control_response':
            continue
        start = item.get('start', item.get('injection_start'))
        if start is None:
            continue
        events.append(_event('instructor_inject', start, detail=str(item.get('kind')),
                             injection=item.get('kind'),
                             vehicle_id=item.get('vehicle_id')))
    for contact in report.get('collisions') or ():
        if not isinstance(contact, dict):
            continue
        events.append(_event('collision', contact.get('t', 0),
                             detail=f"{contact.get('obstacle', '')} · {contact.get('severity', '')}"
                             .strip(' ·'),
                             severity=contact.get('severity'),
                             obstacle=contact.get('obstacle')))
    wraps_seen = False
    for sample in report.get('trajectory') or ():
        t = sample.get('t', 0)
        if sample.get('wraps') and not wraps_seen:
            wraps_seen = True
            events.append(_event('tether_snag', t, detail=str(sample.get('wraps'))))
        for contact in sample.get('collisions') or ():
            if isinstance(contact, dict):
                events.append(_event('collision', contact.get('t', t),
                                     detail=str(contact.get('obstacle', '')),
                                     severity=contact.get('severity')))
    completion = report.get('completion') or {}
    for penalty in completion.get('penalties') or ():
        events.append(_event('penalty', penalty.get('t', 0),
                             detail=str(penalty.get('reason') or ''),
                             points=penalty.get('points')))
    for objective in completion.get('objectives') or ():
        if objective.get('done'):
            events.append(_event('objective_done', completion.get('elapsed', report.get('elapsed', 0)),
                                 detail=str(objective.get('label') or '')))
    if completion.get('failed'):
        events.append(_event('penalty', completion.get('elapsed', report.get('elapsed', 0)),
                             detail=str(completion.get('failed'))))
    events.sort(key=lambda row: (row['t'], row['kind']))
    return events


def merge_recording_events(recording):
    """Return debrief events for a replay document, preferring optional stored events."""
    stored = (recording or {}).get('debrief', {}).get('events')
    if stored:
        return deepcopy(stored)
    events = []
    for clip in (recording or {}).get('clips') or ():
        clip_events = (clip.get('debrief') or {}).get('events')
        if clip_events:
            events.extend(deepcopy(clip_events))
            continue
        injections = (clip.get('debrief') or {}).get('injections') or recording.get('debrief', {}).get('injections')
        for row in extract_events_from_frames(clip.get('frames') or (), injections):
            row = dict(row)
            row['clip'] = clip.get('key') or clip.get('title')
            events.append(row)
    events.sort(key=lambda row: (row['t'], row['kind']))
    return events


def attach_debrief(recording, notes='', injections=None):
    """Add optional ``debrief`` metadata without removing legacy clip fields."""
    data = deepcopy(recording) if recording else {'format': 'qysim-replay-2', 'clips': []}
    events = merge_recording_events({**data, 'debrief': {'injections': injections or []}})
    if injections:
        # Recompute with injections applied at the top level.
        events = []
        for clip in data.get('clips') or ():
            for row in extract_events_from_frames(clip.get('frames') or (), injections):
                row = dict(row)
                row['clip'] = clip.get('key') or clip.get('title')
                events.append(row)
        events.sort(key=lambda row: (row['t'], row['kind']))
    data['debrief'] = {
        'version': 1,
        'events': events,
        'notes': notes or data.get('debrief', {}).get('notes', ''),
        'seek_lead_s': SEEK_LEAD_S,
    }
    return data


def grade_summary(report):
    """Count green/yellow/red cells in the T17 assessment matrix."""
    counts = {'green': 0, 'yellow': 0, 'red': 0, 'ungraded': 0}
    matrix = (report or {}).get('matrix') or {}
    for phase in matrix.values():
        for flow in (phase or {}).values():
            for metric in (flow or {}).values():
                if not metric:
                    counts['ungraded'] += 1
                    continue
                grade = metric.get('grade')
                if grade in counts:
                    counts[grade] += 1
                else:
                    counts['ungraded'] += 1
    return counts


def build_html_report(report=None, events=None, notes='', screenshots=None, strings=None):
    """Single-page HTML suitable for browser print-to-PDF. All visible labels come from STRINGS."""
    s = dict(STRINGS)
    if strings:
        s.update(strings)
    report = report or {}
    events = list(events if events is not None else extract_events_from_report(report))
    completion = report.get('completion') or {}
    score = completion.get('score', report.get('score', s['missing']))
    elapsed = report.get('elapsed', completion.get('elapsed', s['missing']))
    vehicle = report.get('vehicle_id', s['missing'])
    grades = grade_summary(report)
    note_text = notes or report.get('debrief', {}).get('notes') or s['notesPlaceholder']
    rows = []
    for event in events:
        label = s.get(event['kind'], event['kind'])
        rows.append(
            f"<tr><td>{escape(str(event.get('t', '')))} {escape(s['seconds'])}</td>"
            f"<td>{escape(label)}</td><td>{escape(str(event.get('detail') or ''))}</td></tr>"
        )
    shots = []
    for shot in screenshots or ():
        caption = escape(str(shot.get('caption') or shot.get('t') or ''))
        if shot.get('src'):
            shots.append(
                f"<figure><img src=\"{escape(shot['src'])}\" alt=\"{caption}\">"
                f"<figcaption>{caption}</figcaption></figure>"
            )
        else:
            shots.append(f"<figure><figcaption>{caption} — {escape(s['noScreenshot'])}</figcaption></figure>")
    if not shots:
        shots.append(f"<p>{escape(s['noScreenshot'])}</p>")
    body = f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<title>{escape(s['title'])}</title>
<style>
body{{font:15px/1.45 system-ui,sans-serif;color:#102018;background:#f4f7f5;margin:24px}}
h1{{font-size:28px;margin:0 0 4px}}
.eyebrow{{letter-spacing:.12em;text-transform:uppercase;color:#4a6a58;font-size:12px}}
.meta{{display:flex;gap:18px;flex-wrap:wrap;margin:16px 0}}
.meta div{{background:#fff;border:1px solid #c5d5cb;padding:10px 14px;min-width:120px}}
.meta strong{{display:block;font-size:22px}}
table{{border-collapse:collapse;width:100%;background:#fff}}
th,td{{border:1px solid #c5d5cb;padding:8px;text-align:left}}
th{{background:#e4eee7}}
.notes{{white-space:pre-wrap;background:#fff;border:1px solid #c5d5cb;padding:12px;min-height:4em}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px}}
figure{{margin:0;background:#fff;border:1px solid #c5d5cb;padding:8px}}
img{{max-width:100%;height:auto;display:block}}
.banner{{background:#1c3a2c;color:#e8f5ec;padding:8px 12px;margin:12px 0}}
@media print{{body{{background:#fff;margin:12px}}}}
</style>
</head>
<body>
<p class="eyebrow">{escape(s['subtitle'])}</p>
<h1>{escape(s['title'])}</h1>
<p>{escape(s['provisional'])}</p>
<div class="banner">{escape(s['viewpointBanner'])}</div>
<section class="meta">
  <div><span>{escape(s['vehicle'])}</span><strong>{escape(str(vehicle))}</strong></div>
  <div><span>{escape(s['score'])}</span><strong>{escape(str(score))}</strong></div>
  <div><span>{escape(s['elapsed'])}</span><strong>{escape(str(elapsed))} {escape(s['seconds'])}</strong></div>
  <div><span>G/Y/R</span><strong>{grades['green']}/{grades['yellow']}/{grades['red']}</strong></div>
</section>
<h2>{escape(s['events'])}</h2>
<table>
<thead><tr><th>{escape(s['colTime'])}</th><th>{escape(s['colKind'])}</th><th>{escape(s['colDetail'])}</th></tr></thead>
<tbody>
{''.join(rows) or f"<tr><td colspan='3'>{escape(s['missing'])}</td></tr>"}
</tbody>
</table>
<h2>{escape(s['notes'])}</h2>
<div class="notes">{escape(note_text)}</div>
<h2>{escape(s['screenshots'])}</h2>
<div class="grid">{''.join(shots)}</div>
</body>
</html>
"""
    return body


def report_to_replay(report, title='講評回放'):
    """Build a minimal qysim-replay-2 document from a training report trajectory.

    Sparse 1 Hz samples become frames; optional ``debrief.events`` are attached. Old clients
    that only read ``clips[].frames`` keep working.
    """
    report = report or {}
    world = ((report.get('supervision') or {}).get('world')) or {}
    frames = []
    for sample in report.get('trajectory') or ():
        pos = sample.get('pos') or [0, 0, 0]
        frames.append({
            't': sample.get('t', 0),
            'pos': pos,
            'q': [1, 0, 0, 0],
            'euler': [0, 0, 0],
            'vel': [0, 0, 0],
            'speed_kn': 0,
            'thrust': [],
            'health': [],
            'rc': {},
            'tether': {
                'nodes': [],
                'length': 0,
                'tension_rov': sample.get('tension', 0),
                'tension_max': sample.get('tension', 0),
                'warn': False,
                'broken': False,
                'wraps': sample.get('wraps') or {},
            },
            'events': sample.get('collisions') or [],
            'silt': 0,
            'score': sample.get('completion') or report.get('completion') or {},
            'current_kn': 0.1 if sample.get('current') else 0,
            'current_here': [0, 0, 0],
            'nav': {},
            'log': [],
            'damage': [],
        })
    if not frames:
        frames = [{'t': 0, 'pos': [0, 0, 0], 'q': [1, 0, 0, 0], 'euler': [0, 0, 0],
                   'vel': [0, 0, 0], 'speed_kn': 0, 'thrust': [], 'health': [], 'rc': {},
                   'tether': {'nodes': [], 'length': 0, 'tension_rov': 0, 'tension_max': 0,
                              'warn': False, 'broken': False, 'wraps': {}},
                   'events': [], 'silt': 0, 'score': report.get('completion') or {},
                   'current_kn': 0, 'current_here': [0, 0, 0], 'nav': {}, 'log': [], 'damage': []}]
    recording = {
        'format': 'qysim-replay-2',
        'hz': 1.0,
        'clips': [{'key': 'debrief', 'title': title, 'world': world, 'frames': frames, 'script': []}],
    }
    return attach_debrief(recording, notes=(report.get('debrief') or {}).get('notes', ''),
                          injections=[e for e in report.get('events') or ()
                                      if 'restored_at' not in e and e.get('kind') != 'control_response'])
