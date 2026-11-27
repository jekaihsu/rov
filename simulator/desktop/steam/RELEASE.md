# T10 / S4 release configuration and verification gaps

steamworks.js 0.4.0 is MIT (license shipped in node_modules/steamworks.js/LICENSE).
No viewer dependency or asset was added. Three.js remains MIT.
Set STEAM_APP_ID externally for development (use Valve's shared test application).
Alternatively place steam_appid.txt next to the executable; never distribute this
file or commit real IDs. Release launches use Steam's environment. Missing Steam
or a missing App ID uses the local mock backend (`userData/steam-mock/state.json`),
visible in the engineering drawer's Steam developer panel. No authentication
credentials are needed.

`ROV_BUILD_EDITION=steam` selects Steam packaging settings (product name
`ROV Solution`, baked `steam/build_edition.json` in the package copy via
`packageAfterCopy`, instructor UI omitted from the
frozen viewer). Internal training builds keep `edition !== 'steam'` so achievements
and Rich Presence stay hidden. Windows packaging remains `workflow_dispatch` only.


## Backend configuration table

`achievements.json` is the authoritative event/API/display-name mapping (22 skill
rows; see `docs/store/steam/achievements.md`). Create each achievement with the exact
`api` name; set progress stat to `STAT_` plus upper-case `event`, type INT, default 0,
client-set, increment-only. Artwork needs product review.
The preload bridge accepts `steamEvent`, `steamPresence`, `steamMock`, and
`steamStatus` (includes `edition`, `backend`, `cloud`, `mockPath`). Viewer trigger
logic lives in `viewer/play/achievements.js`. No unlock has been verified against a
real Steam App ID yet.

## Auto-Cloud

See `docs/store/steam/cloud.md` and `steam/cloud_paths.cjs`. Windows root: WinAppData;
subdirectory matches the Electron product name (`ROV Simulator` internal,
`ROV Solution` Steam). Verify `steamStatus().cloudPath` before enabling Partner
rules. Include preferences.json, window.json, saves/** (versioned localStorage
mirrors — career, campaign, fidelity, display, audio, input, …; see
docs/design/saves.md), collection/** and steam-mock/**; exclude logs, numba-cache,
saves/corrupt/**, local-backups/** and reports/**. Photos dominate size: reserve
1 GiB / 10,000 files per user initially. No photo deletion, recompression or quota
enforcement is implemented. Auto-Cloud conflict decisions occur before launch.
Desktop write path for `saves/*.json`, `preferences.json` and `window.json` is
atomic (temp file + fsync + rename) via `desktop/save_files.cjs`.

## Steam Input defaults and checks

See `docs/steam/steam-input.md` and the action-set template
`simulator/desktop/steam/game_actions_TEMPLATE.vdf` (rename to `game_actions_<AppID>.vdf`
before upload). For Xbox, PlayStation, Switch Pro and Steam Deck select Valve's built-in
**Gamepad** template, enable Steam Input for each family, and publish each as the
recommended configuration. Use joystick move/look, standard face buttons, triggers and
bumpers with no keyboard or mouse emulation; disable Nintendo button swapping
for the standard positional mapping. A verified exported configuration still needs real
controllers. In Electron DevTools verify navigator.getGamepads(): mapping === 'standard',
axes 0..3 and buttons 0..16 against the physical controller on all four families.

Focus loss and Shift+Tab conservatively neutralize outgoing desktop RC packets;
click after returning to resume. steamworks.js does not expose the overlay callback:
overlayActive is null, never a fabricated false. Overlay opened through another
shortcut is an unresolved gap. Input gate startup timing also needs renderer testing.

## Display and Steam Deck

`rovDesktop.display()` enumerates displays and reports refresh rate;
`display({mode,display,width,height})` saves settings. Modes are windowed,
borderless (bounds without native exclusive mode) and fullscreen. Alt+Enter toggles.
Vsync remains Electron's default. OS refresh-rate changes and a settings UI are
not implemented. Borderless window decoration still needs platform-specific work.
Steam Deck detection selects fullscreen 1280x800, performance quality, zoom 1.
Deck Verified remains unverified: Proton launch, fonts at 800p, keyboard prompts,
controller-only navigation, suspend/resume, offline saves, overlay and performance.
Linux native needs an ELF PyInstaller backend and Linux Forge maker; Proton may
run the Windows bundle but native Steamworks/overlay and graphics need testing.
macOS needs per-architecture Python builds, Forge maker, signing/notarization,
Steam dylib packaging and controller validation. Neither target is implemented.

## Security and release blocker

contextIsolation=true, nodeIntegration=false, sandbox=true. Native operations use
main-frame, exact loopback origin validation and allowlisted IPC. New windows are
denied; navigation stays on the allocated local origin. Response CSP denies objects,
frames, external scripts and base URLs; inline styles remain for existing viewer
styles. Network connections allow ws/wss/https for remote rooms.

CI currently produces INTERNAL TRAINING artifacts by default. Steam packaging
settings can be selected with `ROV_BUILD_EDITION=steam` on the manual Windows
workflow, but Steam edition content is still blocked for upload: existing vehicle
assets and viewer/controller text contain vendor references and qysim.server
imports the USB module. A reviewed Steam content manifest and dependency boundary
are required before enabling Steam uploads. No upload is performed. SDK files are
not intentionally added by the current PyInstaller recipe. Real Windows launches
with/without Steam, achievement unlocks, CSP rendering, backend crash/retry,
display behavior and artifact contents are all unverified.

## Review follow-up after merging main

The Windows workflow is manual-only with a timeout and concurrency cancellation;
no runner was triggered for this review update because the monthly budget is exhausted.
The obsolete monolithic CI workflow stays deleted; desktop tests live in frontend.yml.
Only preload installs the desktop input guard; tests execute that actual preload source.
The guard is a simulator safety policy, not a measured behavior of a real vehicle.
It preserves depth/mode fields and controller-generation metadata and does not add
velocity control, position hold or a DVL assumption. Research was re-read in
`docs/reference/real-rov-research.md`; `docs/reference/own/` is absent in this checkout.
No vehicle-specific behavior or measurement is inferred from another vehicle.

Electron packaging now uses an explicit runtime file allowlist. Achievement catalog,
edition bake file and cloud path helpers are retained from the steam directory.
Production npm dependencies and their licenses/native libraries stay present, while
Electron Packager prunes devDependencies. `packaging_audit.cjs BEFORE_ASAR AFTER_ASAR`
checks the actual file lists, sizes and unchanged unpacked native-library bytes.
Linux cross-packaging checks only the Windows Electron shell when no frozen
backend is available; it does not validate a complete Windows simulation build.

## Additional retained audit tooling

`ELECTRON_ZIP_DIR=/path/to/downloaded/zips node simulator/desktop/audit_package.cjs`
compares old and current production packaging filters on Linux. It writes full
before/after file lists to a temporary directory. The audit deliberately omits the
Python backend extraResource and does not launch the application. It checks release
documents/templates are absent while the achievement catalog and native Steam
bindings remain. It does not certify Windows packaging or runtime behavior.

## AI-generated content disclosure (K2 radio voice)

Radio voice clips under `simulator/viewer/audio/voice/` are pre-generated with an AI text-to-speech
service (see `simulator/viewer/models/CREDITS.md`); nothing is generated at runtime. Before a Steam
build ships with these clips, declare "pre-generated AI content" in the Steamworks content survey,
state it in the store page description, and show the same sentence in an in-game credits screen
(none exists yet). The service terms also require telling players the voice is AI-generated.
