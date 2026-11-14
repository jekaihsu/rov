# T10 release configuration and verification gaps

steamworks.js 0.4.0 is MIT (license shipped in node_modules/steamworks.js/LICENSE).
No viewer dependency or asset was added. Three.js remains MIT.
Set STEAM_APP_ID externally for development (use Valve's shared test application).
Alternatively place steam_appid.txt next to the executable; never distribute this
file or commit real IDs. Release launches use Steam's environment. Missing Steam
is caught and falls back to offline mode. No authentication credentials are needed.

## Backend configuration table

`achievements.json` is the authoritative event/API/display-name mapping (15 rows).
Create each achievement with the exact `api` name; set progress stat to
`STAT_` plus upper-case `event`, type INT, default 0, client-set, increment-only.
Artwork, localized descriptions and final observation category names need product review.
The preload bridge accepts `steamEvent(event, integerValue)` and returns whether
Steam stored it. `steamStatus()` returns player, language, cloudPath and availability.
Events are not yet wired into gameplay: viewer changes are outside this PR's scope.
No achievement unlock or screenshot has been verified against Steam.

## Auto-Cloud

Windows root: WinAppData, subdirectory `ROV Simulator`; verify the actual Electron
userData path returned by steamStatus before enabling this rule in the partner site.
Include preferences.json, window.json and collection/** recursively; exclude logs,
numba-cache and local-backups/**. Configure user-specific root overrides before
allowing different Steam accounts on the same machine. Photos dominate size: reserve
1 GiB / 10,000 files per user initially (500 photos at 2 MiB plus metadata).
No photo deletion, recompression or quota enforcement is implemented. Warn users
and size real sessions before release. Auto-Cloud conflict decisions occur before
launch; a launch snapshot preserves only data still present at that time. Steam's
conflict dialog and a manual collection export remain necessary; this is not a
complete conflict-recovery guarantee. Snapshots are local and currently unbounded.

## Steam Input defaults and checks

For Xbox, PlayStation, Switch Pro and Steam Deck select Valve's built-in
**Gamepad** template, enable Steam Input for each family, and publish each as the
recommended configuration. Use joystick move/look, standard ABXY, triggers and
bumpers with no keyboard or mouse emulation; disable Nintendo button swapping
for the standard positional mapping. These are setup instructions, not uploaded
controller configurations. A verified exported VDF still needs real controllers.
In Electron DevTools verify navigator.getGamepads(): mapping === 'standard',
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

CI currently produces INTERNAL TRAINING artifacts only. Steam edition is blocked:
existing vehicle assets and viewer/controller text contain vendor references and
qysim.server imports the USB module. Removing just documents or excluding the USB
module would leave branding or break imports. A reviewed Steam content manifest
and dependency boundary are required before enabling Steam uploads. No upload is
performed. SDK files are not intentionally added by the current PyInstaller recipe.
Real Windows launches with/without Steam, achievement unlocks, CSP rendering,
backend crash/retry, display behavior and artifact contents are all unverified.

## Review follow-up after merging main

The obsolete standalone input_guard.js was removed; preload executeInMainWorld is
now the only implementation. T02 input preferences IPC remains available alongside
Steam/display IPC. Intentional window closure and before-quit suppress backend
failure dialogs, including readiness errors during shutdown. An unexpected backend
exit with code zero is still a failure while a simulator window is active.

Windows packaging is workflow_dispatch only, with timeout and cancel-in-progress
concurrency. Main's split backend/frontend/browser workflows are retained. This
month's CI budget is exhausted; validation is local and no new CI success is claimed.

`ELECTRON_ZIP_DIR=/path/to/downloaded/zips node simulator/desktop/audit_package.cjs`
compares old and current production packaging filters on Linux. It writes full
before/after file lists to a temporary directory. The audit deliberately omits the
Python backend extraResource and does not launch the application. It checks release
documents/templates are absent while the achievement catalog and native Steam
bindings remain. It does not certify Windows packaging or runtime behavior.

AGENTS.md and real-rov-research.md were reread. This change does not alter thrust,
physics, camera modes, DVL requirements or training assists. The existing desktop
focus/Shift+Tab pause-and-click-to-resume behavior is a desktop safety assumption,
not a measured real-controller behavior; own/ measurement data is absent. Steam
Input mappings and Deck display defaults remain platform proposals, not verified
real ROV equivalents. No substitute vehicle data is introduced as X1 fact.
