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

The Windows workflow is manual-only with a timeout and concurrency cancellation;
no runner was triggered for this review update because the monthly budget is exhausted.
The obsolete monolithic CI workflow stays deleted; desktop tests live in frontend.yml.
Only preload installs the desktop input guard; tests execute that actual preload source.
The guard is a simulator safety policy, not a measured behavior of a real vehicle.
It preserves depth/mode fields and controller-generation metadata and does not add
velocity control, position hold or a DVL assumption. Research was re-read in
`docs/reference/real-rov-research.md`; `docs/reference/own/` is absent in this checkout.
No vehicle-specific behavior or measurement is inferred from another vehicle.

Electron packaging now uses an explicit runtime file allowlist. Only
steam/achievements.json is retained from the release directory. Production npm
dependencies and their licenses/native libraries stay present, while Electron
Packager prunes devDependencies. `packaging_audit.cjs BEFORE_ASAR AFTER_ASAR`
checks the actual file lists, sizes and unchanged unpacked native-library bytes.
Linux cross-packaging checks only the Windows Electron shell when no frozen
backend is available; it does not validate a complete Windows simulation build.
