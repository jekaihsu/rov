# L1 locale layer

```js
import { localize, subscribe } from '../i18n/index.js';
const STRINGS = localize('menu.example', { title: '標題', count: '共 {n} 項' });
```

Keep STRINGS at the top of its module. Add its namespace to `namespaces.json`, run the extractor,
and translate its three JSON files. Arrays retain their shape; nested references remain live.
Destructured primitive strings are snapshots: read them again on render. Keep existing `.replace()` calls.
Never translate internal IDs. `subscribe(listener)` returns an unsubscribe function.

The browser loads dictionaries before module rendering, and again when the display preference changes.
Exact static labels update without destroying focus. Composed/cached strings retain their normal lifecycle;
the localized notice asks the player to return to the main menu for those.

`core.js` has no browser dependencies. Its synchronous `setLanguage()` selects registered dictionaries;
`registerTranslations()` supports tests and other hosts. Browser code should use
`getDisplayPrefs().set('language', value)` to load dictionaries and refresh mounted labels.
An explicit URL `lang` remains authoritative even after saving a different preference.

Priority: query, saved language, `steamStatus().language`, browser languages, zh-Hant.
Unsupported values are ignored; Steam names and common BCP 47 tags are normalized.
Unavailable dictionaries fall back per leaf to the original source. No protocol or simulation changes.

```sh
python simulator/tools/i18n_extract.py --csv /tmp/translations.csv
python simulator/tools/i18n_extract.py --check --integrated
node --test simulator/tests/test_i18n.mjs
python simulator/tools/run_browser_checks.py browser_i18n_runtime browser_i18n_smoke
```

Run from repository root. The full audit intentionally reports missing translations for deferred modules.
`--integrated` checks only L1's 27 namespaces. CSV includes namespace, dotted key and all four languages.
The extractor uses Python AST for backend dictionaries and evaluates captured frontend STRINGS objects in a
fresh Node VM with a timeout; it does not import application modules. Keep STRINGS declarative.
