"""Synchronize release metadata from the root VERSION; --check is read-only."""
import argparse
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
version = (ROOT / "VERSION").read_text().strip()
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--check", action="store_true")
args = parser.parse_args()
for name in ("package.json", "package-lock.json"):
    file = ROOT / "simulator/desktop" / name
    data = json.loads(file.read_text())
    data["version"] = version
    if "packages" in data:
        data["packages"][""]["version"] = version
    text = json.dumps(data, indent=2) + "\n"
    if args.check:
        assert file.read_text() == text, f"Stale version: {file}"
    else:
        file.write_text(text)
file = ROOT / "simulator/viewer/index.html"
text = re.sub(r"ROV 模擬器 [0-9.]+", f"ROV 模擬器 {version}", file.read_text())
if args.check:
    assert text == file.read_text(), "Stale viewer version"
else:
    file.write_text(text)
