"""Shared local/CI test tiers and conservative path selection."""
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
# Standard automated checks. Performance and visual review scripts are not pass/fail checks
# and browser_expedition_perf.py starts its own fixture server, so they only run when named explicitly.
# browser_input_smoke.py asserts RC packets carry no assist fields, which needs a host that predates flight
# assistance; run it by name against such a host. browser_collection_storage.py needs the archive written by
# `node desktop/test_collection_store.cjs`, and browser_campaign_smoke.py records video (Playwright ffmpeg).
DEFAULT_CHECKS = (
    'browser_smoke',
    'browser_menu_smoke',
    'browser_rebind_smoke',
    'browser_menu_gamepad_smoke',
    'browser_feedback_smoke',
    'browser_gamepad_matrix_smoke',
    # Four PlayStation profiles (standard and raw, DualSense and DualShock 4), each from title to dive and back.
    'browser_playstation_smoke',
    'browser_slow_render_smoke',
    'browser_connection_smoke',
    'browser_hud_smoke',
    'browser_overlay_smoke',
    'browser_camera_smoke',
    'browser_camera_input_smoke',
    'browser_attitude_smoke',
    'browser_pilot_guide_smoke',
    'browser_collection_storage',
    'browser_audio_smoke',
    'browser_audio_review_smoke',
    'browser_music_smoke',
    'browser_debrief_smoke',
    'browser_mission_smoke',
    'browser_gameplay_smoke',
    'browser_expedition_smoke',
    'browser_paint_smoke',
    'browser_campaign_smoke',
    'browser_results_smoke',
    'browser_objective_card_smoke',
    # Fresh profile: launch cinematic and its pad skip, then the new-player hints over two dives.
    'browser_onboarding_smoke',
    # Fresh profile: the title's 開始 plays the new-game cold open, flown by keyboard and by pad, into the prologue.
    'browser_cold_open_smoke',
    'browser_prologue_smoke',
    'browser_career_smoke',
    # Chapter 1 C1-1…C1-4 documentary beats + physics turns (parameterized --mission).
    'browser_chapter1_smoke',
    'observation_smoke',
    # Starts its own server with a private instructor code so it can inject link faults.
    'browser_link_smoke',
    'browser_vehicle_assets_smoke',
    'browser_brand_smoke',
)

# Per-script time limits above run_browser_checks' --timeout default, for checks that walk several full dives.
SCRIPT_TIMEOUTS = {
    'browser_playstation_smoke': 3600,
    'browser_cold_open_smoke': 5400,
    'browser_chapter1_smoke': 3600,
}

TIERS = {
    'quick': {
        'units': ('test_encoding', 'test_protocol_doc', 'test_vendor_manifest', 'test_power', 'test_thermal'),
        'browser': ('browser_hud_smoke',),
    },
    'full': {'units': None, 'browser': DEFAULT_CHECKS},
}
# Narrow islands with known coverage. Other viewer changes conservatively run the tier's entire set.
BROWSER_PATHS = {
    'simulator/viewer/hud/': ('browser_hud_smoke', 'browser_overlay_smoke', 'browser_attitude_smoke'),
    # Identity marks decorate the launch menu; the chapter title card runs when a campaign chapter starts.
    'simulator/viewer/brand/': ('browser_brand_smoke', 'browser_menu_smoke', 'browser_menu_gamepad_smoke',
                                'browser_campaign_smoke'),
    'simulator/viewer/feedback/': ('browser_feedback_smoke', 'browser_menu_smoke', 'browser_hud_smoke',
                                   'browser_menu_gamepad_smoke'),
}


def changed_paths(base='origin/main'):
    """Include branch commits, staged/unstaged edits, deletions and untracked files."""
    merge_base = subprocess.check_output(['git', 'merge-base', base, 'HEAD'], cwd=ROOT, text=True).strip()
    tracked = subprocess.check_output(['git', 'diff', '--no-renames', '--name-only', '-z', merge_base], cwd=ROOT)
    untracked = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard', '-z'], cwd=ROOT)
    return sorted(set(p.decode() for p in (tracked + untracked).split(b'\0') if p))


def browser_checks(tier, paths=None):
    names = list(TIERS[tier]['browser'])
    if paths is None:
        return names
    viewer = [p for p in paths if p.startswith('simulator/viewer/')]
    if not viewer:
        return []
    shared = ('simulator/qysim/', 'simulator/sdk_mock/', 'simulator/requirements')
    if any(path.startswith(shared) for path in paths):
        return names
    selected = set()
    for path in viewer:
        matches = [checks for prefix, checks in BROWSER_PATHS.items() if path.startswith(prefix)]
        if not matches:
            return names
        for checks in matches:
            selected.update(checks)
    return [name for name in names if name in selected]


def inert_for_python(path):
    """True only for paths no Python test reads: prose docs and Node test files.

    Python tests also read viewer files, PROTOCOL.md, campaign/example data and
    docs/reference scripts, so anything not listed here selects the tier's whole set.
    """
    if path.startswith('docs/reference/'):
        return False
    if path.startswith('docs/'):
        return True
    if path.startswith('simulator/tests/') and path.endswith('.mjs'):
        return True
    return '/' not in path and path.endswith('.md')


def changed_test_module(path):
    """Return the module name for a changed simulator/tests/test_*.py file, else None."""
    name = Path(path).name
    if path.startswith('simulator/tests/') and name.startswith('test_') and name.endswith('.py'):
        return name.removesuffix('.py')
    return None


def unit_checks(tier, paths=None):
    all_names = sorted(p.stem for p in (ROOT / 'simulator/tests').glob('test_*.py'))
    names = list(TIERS[tier]['units'] or all_names)
    if paths is None:
        return names
    changed = {changed_test_module(p) for p in paths} - {None}
    product = [p for p in paths if not inert_for_python(p) and changed_test_module(p) is None]
    selected = set(names) if product else set()
    selected.update(name for name in changed if name in all_names)
    return [n for n in all_names if n in selected]
