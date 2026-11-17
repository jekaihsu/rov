"""Frame-cost profile and budget check for browser_gpu_bench.py (--profile, --check).

--profile  measures every requested scene (menu stage per tier, the deploy intro on the deck, and each dive site
           onboard and in third person per tier) with tools/perf_probe.js and writes
           output/gpu-bench/<machine>/profile.json and profile.md.
--check    measures the scenes listed in tools/perf_budgets.json and fails when a scene exceeds its budget for
           draw calls, triangles, render passes, full-screen passes, shader programs or texture memory. The budgets
           are counts, not milliseconds, so the check means the same on software GL and on a real GPU.

A scene key is ``menu:<tier>``, ``intro:<site>:<tier>`` or ``dive:<site>:<tier>:<view>`` (view onboard / third).
Dive scenes of the same site and tier share one page (onboard first, then the chase camera).
"""
from __future__ import annotations

import json
import time

import _perf_scenes as scenes

# Probe fields a budget may limit (upper bounds).
BUDGET_FIELDS = ('draws', 'triangles', 'passes', 'fullScreenPasses', 'programs', 'textureMB')
TABLE_FIELDS = (
    ('fps', 'fps'), ('draws', 'draw calls'), ('triangles', 'triangles'), ('passes', 'passes'),
    ('fullScreenPasses', 'full-screen'), ('textureMB', 'texture MB'), ('programs', 'programs'),
    ('jsMsMedian', 'rAF JS ms'), ('script_ms', 'script ms/frame'), ('layout_ms', 'layout ms/frame'),
    ('style_ms', 'style ms/frame'),
)


def _group(keys):
    """Order scene keys so that dive views of one site and tier are measured on one page."""
    pages = []
    dives = {}
    for key in keys:
        parts = key.split(':')
        if parts[0] == 'dive':
            dives.setdefault((parts[1], parts[2]), []).append(parts[3])
        else:
            pages.append((key, None))
    for (site, tier), views in dives.items():
        pages.append((f'dive:{site}:{tier}', sorted(set(views), key=('onboard', 'third').index)))
    return pages


def measure(browser, keys, size, seconds=4.0, warmup=3.0, attribute=False, log=print):
    """Measure scene keys; returns {key: row}."""
    rows = {}
    for index, (key, views) in enumerate(_group(keys)):
        parts = key.split(':')
        room = f'pp{index}{int(time.time()) % 100000}'
        page = None
        try:
            if parts[0] == 'menu':
                page, errors, expr = scenes.open_menu(browser, parts[1], size, room)
                rows[key] = {**scenes.sample(page, expr, seconds, warmup, attribute), 'errors': errors[:3]}
                log(json.dumps({key: rows[key]}, ensure_ascii=False))
                continue
            if parts[0] == 'intro':
                page, errors, expr = scenes.open_intro(browser, parts[1], parts[2], size, room)
                rows[key] = {**scenes.sample(page, expr, seconds, warmup, attribute), 'errors': errors[:3]}
                log(json.dumps({key: rows[key]}, ensure_ascii=False))
                continue
            page, errors, expr = scenes.open_dive(browser, parts[1], parts[2], 'third', size, room)
            for view in views:
                page.evaluate(f'window.__viewer.setCam("{"onboard" if view == "onboard" else "chase"}")')
                full = f'{key}:{view}'
                rows[full] = {**scenes.sample(page, expr, seconds, warmup, attribute), 'errors': errors[:3]}
                log(json.dumps({full: rows[full]}, ensure_ascii=False))
        except Exception as error:  # noqa: BLE001 — one broken scene must not hide the others
            rows[key] = {'error': str(error).splitlines()[0][:300]}
            log(json.dumps({key: rows[key]}, ensure_ascii=False))
        finally:
            if page is not None:
                page.close()
    return rows


def profile_keys(sites, tiers, views, menu_tiers=('performance', 'medium', 'high'), intro=None):
    keys = [f'menu:{tier}' for tier in menu_tiers]
    for site, tier in intro or ():
        keys.append(f'intro:{site}:{tier}')
    for site in sites:
        for tier in tiers:
            for view in views:
                keys.append(f'dive:{site}:{tier}:{view}')
    return keys


def markdown(rows):
    head = '| scene | ' + ' | '.join(label for _, label in TABLE_FIELDS) + ' |'
    lines = [head, '|---|' + '---:|' * len(TABLE_FIELDS)]
    for key, row in rows.items():
        if 'error' in row:
            lines.append(f'| {key} | error: {row["error"]} |')
            continue
        lines.append(f'| {key} | ' + ' | '.join(str(row.get(field)) for field, _ in TABLE_FIELDS) + ' |')
    return '\n'.join(lines) + '\n'


def check(rows, budgets):
    """Return a list of human-readable budget violations (empty when everything fits)."""
    failures = []
    for key, limits in budgets.items():
        row = rows.get(key)
        if row is None or 'error' in row:
            failures.append(f'{key}: not measured ({(row or {}).get("error", "missing")})')
            continue
        if row.get('errors'):
            failures.append(f'{key}: page errors {row["errors"]}')
        for field in BUDGET_FIELDS:
            if field in limits and row.get(field) is not None and row[field] > limits[field]:
                failures.append(f'{key}: {field} {row[field]} > budget {limits[field]}')
    return failures
