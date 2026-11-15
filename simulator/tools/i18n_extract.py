"""Extract literal STRINGS without executing modules; audit locale keys and export translator CSV."""
import argparse
import ast
import csv
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ROOT / 'viewer/i18n/locales'


def extract():
    script = r"""
const fs = require('node:fs');
const vm = require('node:vm');
const fleetSource = fs.readFileSync(process.argv[1], 'utf8');
const fleet = vm.runInNewContext('(' + fleetSource.match(/const STRINGS = (\{[\s\S]*?\});/)[1] + ')');
const files = JSON.parse(fs.readFileSync(0, 'utf8'));
const output = {};
for (const file of files) {
  const source = fs.readFileSync(file, 'utf8');
  const match = source.match(/const STRINGS\s*=\s*(?:localize\([^,]+,\s*)?(\{[\s\S]*?\})\)?;/);
  if (!match) continue;
  const context = {
    vehicleName: function vehicleName(id) { return fleet.models[id]?.name || id; },
    vehicleRole: function vehicleRole(id) { return fleet.models[id]?.role || id; },
  };
  output[file] = vm.runInNewContext('(' + match[1] + ')', context, {timeout: 1000});
}
process.stdout.write(JSON.stringify(output));
"""
    files = sorted(str(p) for p in (ROOT / 'viewer').rglob('*.js'))
    result = subprocess.run(['node', '-e', script, str(ROOT / 'viewer/fleet_names.js')],
                            input=json.dumps(files), text=True,
                            capture_output=True, check=True)
    tables = {str(Path(p).relative_to(ROOT / 'viewer').with_suffix('')).replace('/', '.'):
              value for p, value in json.loads(result.stdout).items()}
    for path in sorted((ROOT / 'qysim').rglob('*.py')):
        for node in ast.walk(ast.parse(path.read_text(encoding='utf8'))):
            if not isinstance(node, ast.Assign):
                continue
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.endswith('STRINGS'):
                    namespace = '.'.join(path.relative_to(ROOT).with_suffix('').parts)
                    tables[f'{namespace}.{target.id}'] = ast.literal_eval(node.value)
    return json.loads(json.dumps(tables, ensure_ascii=False))


def flatten(value, prefix=''):
    if isinstance(value, (dict, list)):
        entries = value.items() if isinstance(value, dict) else enumerate(value)
        return {key: text for name, child in entries
                for key, text in flatten(child, f'{prefix}.{name}' if prefix else str(name)).items()}
    return {prefix: value}


def report_changed_sources(path, baseline):
    """List keys whose source text changed: their translations are looked up by key and are now stale."""
    if not path.exists():
        return
    previous = flatten(json.loads(path.read_text(encoding='utf8')))
    for key, text in flatten(baseline).items():
        if key in previous and previous[key] != text:
            print(f'  source changed, retranslate: {key}: {previous[key]!r} -> {text!r}')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--csv', type=Path)
    parser.add_argument('--check', action='store_true', help='Audit without updating the baseline')
    parser.add_argument('--integrated', action='store_true', help='Audit only the namespaces loaded by the viewer')
    args = parser.parse_args()
    tables = extract()
    if args.integrated:
        active = json.loads((LOCALES.parent / 'namespaces.json').read_text(encoding='utf8'))
        tables = {name: tables[name] for name in active}
    errors = 0
    rows = []
    for namespace, baseline in tables.items():
        path = LOCALES / 'zh-Hant' / f'{namespace}.json'
        if not args.check:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(json.dumps(baseline, ensure_ascii=False, indent=2) + '\n', encoding='utf8')
        elif not path.exists() or json.loads(path.read_text(encoding='utf8')) != baseline:
            print(f'Stale baseline: {namespace}')
            report_changed_sources(path, baseline)
            errors += 1
        keys = flatten(baseline)
        translations = {}
        for language in ('en', 'zh-Hans', 'ja'):
            target = LOCALES / language / path.name
            translated = flatten(json.loads(target.read_text(encoding='utf8'))) if target.exists() else {}
            translations[language] = translated
            missing = sorted(keys.keys() - translated.keys())
            extra = sorted(translated.keys() - keys.keys())
            if missing or extra:
                print(f'{language}/{namespace}: missing={missing}, extra={extra}')
                errors += 1
        for key, value in keys.items():
            rows.append([namespace, key, value, *(translations[lang].get(key, '')
                                                 for lang in ('en', 'zh-Hans', 'ja'))])
    if args.csv:
        with args.csv.open('w', encoding='utf-8-sig', newline='') as stream:
            writer = csv.writer(stream)
            writer.writerow(['namespace', 'key', 'zh-Hant', 'en', 'zh-Hans', 'ja'])
            writer.writerows(rows)
    print(f'{len(tables)} namespaces; {errors} locale/baseline differences')
    return bool(errors) if args.check else 0


if __name__ == '__main__':
    raise SystemExit(main())
