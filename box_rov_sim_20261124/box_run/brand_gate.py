#!/usr/bin/env python3
"""ROV-01 Brand-Neutrality Gate (static source + live HTTP/DOM).

Scans shipped source trees (rov01sim, viewer, p260, desktop, SOP reports)
and optionally live HTTP endpoints for any forbidden vendor or third-party
brand tokens:
  qysea | fifish | x1 | 鰭源 | qy | q-irc | qirc | qic |
  v6p | ego_self_test | bluerov | blue robotics | saab | seaeye | falcon

Exits 0 iff zero unauthorized matches remain.
"""
from __future__ import annotations

import argparse
import fnmatch
import pathlib
import re
import sys
import urllib.request

PATTERN = re.compile(
    r"qysea|fifish|(?<![0-9a-z_])x1(?![0-9a-z_])|鰭源|(?<![a-z0-9])qy|q-?irc|(?<![0-9a-z_])qic(?![0-9a-z_])"
    r"|v6p|ego_self_test|bluerov|blue robotics|saab|seaeye|falcon",
    re.IGNORECASE,
)

TEXT_EXTS = {".py", ".js", ".mjs", ".html", ".css", ".json", ".md", ".txt"}
SKIP_DIRS = {
    "__pycache__", ".git", "node_modules", "vendor",
    "tests",
}


def load_allowlist(path: pathlib.Path) -> list[tuple[str, re.Pattern[str], str]]:
    rules: list[tuple[str, re.Pattern[str], str]] = []
    if not path.exists():
        return rules
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = line.split("\t")
        if len(parts) >= 2:
            rules.append((parts[0], re.compile(parts[1]), parts[2] if len(parts) > 2 else ""))
    return rules


def is_allowed(rel_posix: str, line_text: str, rules: list[tuple[str, re.Pattern[str], str]]) -> bool:
    for glob_pat, line_re, _ in rules:
        if fnmatch.fnmatch(rel_posix, glob_pat) and line_re.search(line_text):
            return True
    return False


def resolve_shipped_roots(root: pathlib.Path) -> list[pathlib.Path]:
    candidates = [
        root / "box_run" / "rov01sim",
        root / "box_run" / "viewer",
        root / "rov01sim",
        root / "viewer",
        root / "p260",
        root / "p260_capture_demo_v2",
        root / "desktop",
        root / "PROTOCOL.md",
        root / "README.md",
        root / "ARENA_HUD_BAKEOFF_REPORT.md",
        root / "steam_assets",
        root / "sop_evaluation_report.json",
        root / "sop_evaluation_report.html",
    ]
    # Also check sibling p260_capture_demo_v2 on laptop layout
    sibling_p260 = root.parent.parent / "output" / "p260_capture_demo_v2"
    if sibling_p260.exists():
        candidates.append(sibling_p260)
    seen = set()
    out = []
    for c in candidates:
        if c.exists():
            rc = c.resolve()
            if rc not in seen:
                seen.add(rc)
                out.append(c)
    return out


def scan_tree(root: pathlib.Path, rules: list[tuple[str, re.Pattern[str], str]]) -> tuple[list[str], int, int]:
    violations: list[str] = []
    allowed_hits = 0
    files_scanned = 0
    for sr in resolve_shipped_roots(root):
        paths = [sr] if sr.is_file() else sorted(sr.rglob("*"))
        for p in paths:
            if not p.is_file():
                continue
            try:
                rel = p.relative_to(root)
                rel_posix = rel.as_posix()
            except ValueError:
                rel_posix = p.as_posix()
            if any(part in SKIP_DIRS for part in p.parts):
                continue
            if p.suffix.lower() not in TEXT_EXTS:
                continue
            files_scanned += 1
            text = p.read_text(encoding="utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), 1):
                for m in PATTERN.finditer(line):
                    if is_allowed(rel_posix, line, rules):
                        allowed_hits += 1
                    else:
                        snippet = line.strip()[:120]
                        violations.append(f"{rel_posix}:{lineno} [{m.group(0)}] -> {snippet}")
    return violations, allowed_hits, files_scanned


def scan_live_http(urls: list[str]) -> list[str]:
    violations: list[str] = []
    for url in urls:
        with urllib.request.urlopen(url, timeout=5) as resp:
            body = resp.read().decode("utf-8", errors="replace")
        for lineno, line in enumerate(body.splitlines(), 1):
            for m in PATTERN.finditer(line):
                violations.append(f"{url}:{lineno} [{m.group(0)}] -> {line.strip()[:120]}")
    return violations


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="ROV-01 brand-neutrality gate")
    ap.add_argument("--root", type=pathlib.Path, default=pathlib.Path(__file__).resolve().parent)
    ap.add_argument("--allowlist", type=pathlib.Path, default=None)
    ap.add_argument("--live-url", action="append", default=[], help="Live HTTP URL to scan")
    ap.add_argument("--live-http", action="store_true", help="Automatically start or probe live HTTP server and scan endpoints")
    args = ap.parse_args(argv)

    root = args.root.resolve()
    allowlist_path = args.allowlist or (root / "brand_gate_allowlist.tsv")
    rules = load_allowlist(allowlist_path)
    violations, allowed_hits, files_scanned = scan_tree(root, rules)

    live_urls = list(args.live_url)
    temp_proc = None
    if args.live_http and not live_urls:
        import socket, subprocess, time
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            hport = s.getsockname()[1]
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            wport = s.getsockname()[1]
        with socket.socket() as s:
            s.bind(("127.0.0.1", 0))
            rport = s.getsockname()[1]
        sim_cwd = root / "box_run" if (root / "box_run" / "rov01sim").exists() else root
        temp_proc = subprocess.Popen(
            [sys.executable, "-m", "rov01sim.server", "--scenario", "mission_1_pool",
             "--http-port", str(hport), "--ws-port", str(wport), "--rpc-port", str(rport), "--release-mode"],
            cwd=str(sim_cwd),
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        base = f"http://127.0.0.1:{hport}"
        for _ in range(30):
            try:
                urllib.request.urlopen(f"{base}/index.html", timeout=1).read()
                break
            except Exception:
                time.sleep(0.15)
        live_urls = [
            f"{base}/index.html",
            f"{base}/app.js",
            f"{base}/wave1_hud.js",
            f"{base}/arena_hud_themes.js",
            f"{base}/vehicle_models.js",
            f"{base}/rov01_mesh.js",
            f"{base}/input_shaping.js",
            f"{base}/tool_catalogue.json",
        ]

    try:
        if live_urls:
            violations.extend(scan_live_http(live_urls))
    finally:
        if temp_proc is not None:
            temp_proc.terminate()
            try:
                temp_proc.wait(timeout=3)
            except Exception:
                temp_proc.kill()

    print(f"[brand_gate] root={root} files_scanned={files_scanned} live_urls={len(live_urls)} allowlisted={allowed_hits} unauthorized={len(violations)}")
    if violations:
        for v in violations[:50]:
            print(f"  VIOLATION: {v}")
        print("RESULT=FAIL")
        return 1
    print("RESULT=PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
