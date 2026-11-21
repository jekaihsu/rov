"""Produce the local audit evidence and a compact, size-limited review gallery."""
import collections
import json

from playtest_audit import analyze


def frame_stats(frames):
    """Group by frame end on the page clock. Empty seconds explicitly contain zero rendered frames."""
    buckets = collections.defaultdict(list)
    long = []
    for t, dt, beat in frames:
        buckets[int(t)].append(dt)
        if round(dt * 1000000) > 200000:
            long.append((t, dt, beat))
    means = {}
    if buckets:
        for second in range(min(buckets), max(buckets) + 1):
            values = buckets[second]
            mean = round(1000 * sum(values) / len(values), 2) if values else None
            means[second] = [len(values), mean]
    return means, long


def report(runs, out, summary=None, browser_info=None):
    if summary:
        from browser_cold_open_smoke import contact_sheet
        from PIL import Image
    table = ['# 自動試玩稽核', '', '1600×900，鍵盤。時間單位為實際秒數。卡關表示連續 120 秒沒有換節拍，目標進度也沒有增加。',
             '工具或連線失敗（無法連線、載入超時、伺服器斷線）記為「工具失敗」，不算卡關。',
             '未解鎖的工單使用獨立瀏覽器存檔，配給工單指定裝備，從水中開始。原職涯保留在看板。',
             '空白合計整段安靜區間。長幀含截圖成本，以兩次動畫影格相隔超過 200 ms 計。',
             '每關依卡關、錯誤、提示並存、空白長度及長幀數選出三張證據圖。',
             '', '|關卡|結果|時長|空白總和|最長空白|多重提示|卡關|長幀|錯誤|',
             '|---|---|---:|---:|---:|---:|---:|---:|---:|']
    if browser_info:
        table[2:2] = [browser_info, '']
    detail, gallery, tiles = [], [], []
    for name, run in runs.items():
        row = [name, run['status']]
        if 'events' not in run:
            table.append('|' + '|'.join(row + ['—'] * 7) + '|')
            continue
        events = run['events']
        gaps, stalls, overlap = analyze(events, run['end'])
        if run.get('harness') or str(run.get('status', '')).startswith('工具失敗'):
            stalls = []
        lengths = [b - a for a, b in gaps]
        frames = run['frames']
        means, long = frame_stats(frames)
        row.extend([f'{run["end"]:.1f}', f'{sum(lengths):.1f}', f'{max(lengths, default=0):.1f}',
                    str(len(overlap)), str(len(stalls)), str(len(long)), str(len(run['errors']))])
        table.append('|' + '|'.join(row) + '|')
        detail.extend(['', f'## {name}', ''])
        if 'outcome' in run:
            detail.extend(['遊戲結算記錄', '', '```json', json.dumps(run['outcome'], ensure_ascii=False), '```', ''])
        if run.get('stalled_at'):
            detail.extend(['卡關遙測', '', '```json', json.dumps(run['stalled_at'], ensure_ascii=False), '```', ''])
        sampled = {e['beat'] for e in events if 'shot' in e}
        missed = sorted({beat for _, _, beat in frames if beat and beat not in sampled})
        if missed:
            detail.append('渲染時出現但未能截圖的短節拍：' + '、'.join(missed))
            gallery.extend(['', name + ' 有短節拍漏拍：' + '、'.join(missed)])
        for e in events:
            line = f"- {e['t']:.2f}s {e['beat']} · {' / '.join(e['radio'])} · {' / '.join(e['hints'])}"
            if e.get('shot'):
                label = '同版本補拍畫面' if e.get('supplemental_capture') else '畫面'
                line += f" [{label}]({e['shot']})"
            if 'capture_s' in e:
                line += f"（截圖耗時 {e['capture_s']:.2f}s）"
            detail.append(line)
        for title, data in [('空白區間', gaps), ('卡關區間', stalls), ('提示並存', overlap),
                            ('輸入', run['inputs']), ('錯誤', run['errors']), ('長幀（頁面秒、秒、節拍）', long),
                            ('每秒幀時間（頁面秒 → [影格數, 平均 ms]）', means)]:
            detail.extend(['', title, '', '```json', json.dumps(data, ensure_ascii=False), '```'])
        if not summary:
            continue
        assets = summary.parent / summary.stem
        assets.mkdir(parents=True, exist_ok=True)
        shots = [e for e in events if 'shot' in e]
        starts = [e['t'] for e in shots] + [run['end']]

        def severity(index):
            a, b = starts[index:index + 2]
            silence = max((min(y, b) - max(x, a) for x, y in gaps), default=0)
            errors = sum(a <= entry[0] < b for entry in run['errors'])
            stalled = 0 if run.get('harness') or str(run.get('status', '')).startswith('工具失敗') else (
                any(a <= y <= b for _, y in stalls))
            return (stalled, errors, any(a <= t < b for t, _ in overlap),
                    max(0, silence), sum(beat == shots[index]['beat'] for _, _, beat in long))
        gallery.extend(['', f'### {name}', ''])
        for index in sorted(range(len(shots)), key=severity, reverse=True)[:3]:
            event = shots[index]
            target = assets / event['shot']
            with Image.open(out / target.name) as img:
                for quality in range(75, 4, -5):
                    img.save(target, quality=quality, optimize=True)
                    if target.stat().st_size <= 300000:
                        break
            tiles.append((target, name + ' ' + event['beat']))
            gallery.append(f"![{event['beat']} {event['t']:.1f}s]({summary.stem}/{target.name})")
    (out / 'report.md').write_text('\n'.join(table + detail) + '\n', encoding='utf-8')
    if summary:
        if tiles:
            contact_sheet(tiles, assets / 'contact.jpg')
            table.extend(['', f'[聯絡表]({summary.stem}/contact.jpg)'])
        summary.parent.mkdir(parents=True, exist_ok=True)
        summary.write_text('\n'.join(table + gallery) + '\n', encoding='utf-8')
