"""Report terminology differences in viewer translations and story dialogue for editorial review."""
import csv
import json
import re
from pathlib import Path

from i18n_extract import flatten

ROOT = Path(__file__).resolve().parents[2]
LANGUAGES = ('en', 'zh-Hans', 'ja')
LOCALES = ROOT / 'simulator/viewer/i18n/locales'


def read_terms():
    terms = []
    section = ''
    for line in (ROOT / 'docs/i18n/glossary.md').read_text(encoding='utf8').splitlines():
        if line.startswith('## '):
            section = line[3:]
        if not line.startswith('| ') or line.startswith('| 繁中 '):
            continue
        source, english, chinese, japanese, _basis = (cell.strip() for cell in line.strip('|').split('|'))
        terms.append((source, {'en': english, 'zh-Hans': chinese, 'ja': japanese}, section))
    return terms


def entries():
    for source_file in sorted((LOCALES / 'zh-Hant').glob('*.json')):
        source = flatten(json.loads(source_file.read_text(encoding='utf8')))
        for language in LANGUAGES:
            target = LOCALES / language / source_file.name
            if target.exists():
                for key, translated in flatten(json.loads(target.read_text(encoding='utf8'))).items():
                    yield f'{source_file.stem}.{key}', source.get(key), language, translated
    with (ROOT / 'docs/story/lines.csv').open(encoding='utf-8-sig', newline='') as stream:
        for row in csv.DictReader(stream):
            for language, column in zip(LANGUAGES, ('英文', '簡中', '日文')):
                yield row['id'], row['繁中文字'], language, row[column]


def uses_term(text, forms, language, exact):
    alternatives = forms.split('／')
    if exact:
        return any(text.casefold() == form.casefold() for form in alternatives)
    for form in alternatives:
        if language == 'en':
            # "disarm" must never satisfy "arm". Allow ordinary English plurals in running text.
            if re.search(r'\b' + re.escape(form) + r's?\b', text, re.IGNORECASE):
                return True
        elif form in text:
            return True
    return False


def main():
    terms = read_terms()
    count = 0
    for location, original, language, text in entries():
        if not isinstance(original, str) or not isinstance(text, str):
            continue
        for source, translations, section in terms:
            # UI commands and the ship name can have different meanings inside a sentence or call sign.
            exact = section == '固定介面標籤' or source == '向潮'
            forms = source.split('／')
            matches = original in forms if exact else any(form in original for form in forms)
            if not matches:
                continue
            preferred = translations[language]
            if not uses_term(text, preferred, language, section == '固定介面標籤'):
                print(f'{language} {location}: {source} → {preferred} | {text}')
                count += 1
    print(f'{count} terminology differences for editorial review (advisory).')


if __name__ == '__main__':
    main()
