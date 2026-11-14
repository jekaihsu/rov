# T10 integration status and release checklist

This is an integration foundation, **not a Steam release candidate**. The Windows
artifact is explicitly an internal training build. Do not upload it to a public depot.

## API and backend setup

`steamworks.js` is MIT, pinned in package-lock.json. Its native binaries are unpacked
from ASAR. Steam initialization is optional and never restarts the training app.
Provide `STEAM_APP_ID` at runtime or an untracked `steam_appid.txt` in the launch
working directory. Obtain the development test identifier from Steamworks; no
identifier or credential is committed here. Do not ship that file in a depot.

The trusted main frame can call `rovDesktop.steamStatus()`, `steamEvent(event)` and
`steamStat('dives_completed', integer)`. Calls return false offline; there is no
persistent offline achievement queue yet. `achievements.json` is the backend setup
mapping: each row's `api` is the Steam achievement API Name, `event` is the renderer
notification key. Configure all fifteen as client-set achievements; the integer
stat `dives_completed` has default/minimum zero and is client-set. Labels and icons
still need editorial review. No game event is automatically wired in this PR.

`overlayActive` is deliberately null (unknown), not false. The pinned binding does
not expose GameOverlayActivated. Overlay rendering and input neutralization require
a supported callback binding and real Steam acceptance tests before release.

## Cloud storage proposal

`steamStatus().cloudPath` returns Electron's existing userData directory. Keeping
this path preserves offline collections and preferences. Auto-Cloud should use the
Windows AppData roaming root, subdirectory `ROV Simulator`, recursive patterns
`collection/*`, `preferences.json`, and `display.json`. Exclude backend.log,
numba-cache and all smoke data. Use a per-account subdirectory before enabling
multi-account synchronization; the current shared directory is not account-isolated.

Budget: 500 photos at 2 MiB each plus indexes/preferences: about 1 GiB and 1,100
files; request at least 2 GiB and 2,000 files, then enforce a local photo quota.
Auto-Cloud can replace files before launch. Conflict preservation/merge and backups
are not implemented, so keep Auto-Cloud disabled until those are implemented and
conflict tests pass. Do not advertise cloud support yet.

## Input and Deck acceptance procedure

For Xbox, PlayStation, Switch Pro and Steam Deck, start with Steam's built-in
**Gamepad** template, mapping sticks, triggers, D-pad and face buttons to standard
XInput equivalents. Enable Steam Input for each family in Steamworks. These are
recommended templates, not tested or exported controller configuration files.
For each controller, run the viewer controller check under Steam, verify
`mapping === 'standard'`, axes signs/ranges, trigger values, face buttons, reconnect,
then test held input during overlay, Alt+Tab and focus loss. No such hardware test
has been run. Overlay and focus gamepad neutralization remain release blockers.

`SteamDeck=1` selects fullscreen and performance quality by default. Display IPC
supports 1280×800, zoom and display selection; it does not force physical monitor
modes. Deck Verified remains unverified: text size, virtual keyboard, controller-only
navigation, suspend/resume, overlay, Proton video/audio, stable frame rate and battery.

`rovDesktop.display()` reads settings/displays; passing
`{mode:'fullscreen', width:1280, height:800, display:0, zoom:1}` applies and persists
them. Modes: windowed, borderless (display-sized window), fullscreen. Borderless
still retains OS window decoration; true frameless recreation is outstanding.
Alt+Enter toggles fullscreen for the current session. Refresh rates are reported,
not selectable; Chromium's default VSync remains enabled with no user toggle.

## Builds and security

Windows CI runs npm ci, vendor, pinned Python dependencies, PyInstaller, frozen
backend smoke, Forge make, and ZIP artifact upload. Manual dispatch generates VDFs
from `STEAM_APP_ID` / `STEAM_DEPOT_ID` secrets; it does not upload to Steam.
Generated descriptors live in out/steam and reference the adjacent portable folder.

Security: contextIsolation=true, nodeIntegration=false, sandbox=true; collection,
Steam and display IPC require the local main frame. New windows are denied and
navigation is restricted to the backend origin. Response CSP limits scripts to
self, blocks frames/objects and permits remote room connections. CSP has not had a
packaged renderer regression run; remote room/connect permissions merit further review.

Single-instance locking and crash retry/relaunch are present. Existing startup page
has no measured progress. Spawn errors and readiness timeouts still terminate with
a dialog rather than offering retry. Windows lifecycle behavior is unverified.

Steam-only content filtering/build flag is outstanding: qysim.server statically
imports qysim.qirc, so merely excluding the module breaks startup. A separate
packaged entry or staged package with a compatible disabled adapter is needed.
SDK directories are not explicitly added today, but there is no audited exclusion
manifest for transitive imports or vendor documents/assets. All artifacts here are
internal training artifacts until that audit and split are complete.

Linux native: binding supports x64, but launcher currently names rov-sim.exe,
Forge maker is Windows-only, and PyInstaller must run on Linux with bundled shared
libraries reviewed. Proton: evaluate Windows artifact with Steam overlay/Input and
backend process shutdown under Proton; no compatibility is claimed. macOS: binding
supports Intel/ARM, but each architecture needs its own frozen backend, packaging,
signing/notarization and controller tests. No Linux/Proton/macOS build was run.
