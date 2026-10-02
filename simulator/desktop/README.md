# Windows desktop build

The portable folder contains Electron, the Python simulation backend, local Three.js
modules and the vehicle assets. Open `out/ROV Simulator-win32-x64/ROV Simulator.exe`.
Keep its neighbouring files and `resources` directory together. No Python or Node
installation is required on the player's machine.

Launch opens an animated main menu with live vehicle and scene previews. Select
the vehicle, sticker, scene, room/server, controller and settings there, then
press Start Dive. Return to the menu to change the setup. The in-game Surface
Paint tool marks underwater seabed and structures within 3 m; marks are shared
with room peers and included in recordings. Scene resets clear paint marks.

Version 0.3 shows hardware-aware quality at the top of the menu and keeps Start
Dive visible at the bottom. Window size respects the primary display work area.
Quality and model preferences persist across launches. Gameplay modes include
free exploration, shared three-station inspection and original scenario training;
context-sensitive pilot guidance lives in the side panel.

Ocean exploration and engineering adds optional inspection, recovery and sensor
deployment contracts in reef, seagrass and harbor scenes. One to three pilots can
work together; recovery and deployment need an online Falcon. Valid onboard
photographs unlock five observation categories. Photos, guide covers and completed
contracts persist in userData/collection independently of the launch ports.
The collection is available from the main menu and cockpit, with export/import
backup. Third-person photos remain souvenirs. No account or cloud storage is needed.

The current folder build passed a packaged Electron rendering/live-state check.
The ZIP step ran out of disk space; that incomplete ZIP was removed. The folder
is the available artifact. A ZIP can be built later when sufficient space is free.

The app starts a local backend on three available loopback ports and stops it when
the app closes. Backend logs and the optional Numba compilation cache are stored
in the application's user data directory. The first simulation can take longer
while the cable solver compiles. Remote rooms use the viewer's server connection
controls; this build does not provide a public relay or Steam networking.
Enter `ws://HOST:8765` for a LAN server, or `https://YOUR-DOMAIN` for the supplied
Caddy deployment, then choose the same room code as the other players and join.
The last accepted vehicle selection is saved in `preferences.json` in user data,
so changing local server ports on the next launch does not lose that preference.

## Rebuild

Use a clean Python 3.11 virtual environment with `numpy==1.24.4`,
`numba==0.57.1`, `llvmlite==0.40.1`, `websockets==15.0.1` and
`pyinstaller==6.22.3`. From the project root, run:

```powershell
Set-Location simulator/desktop
npm ci
npm run vendor
Set-Location ../..
<venv-python> simulator/desktop/build_backend.py
<venv-python> simulator/desktop/smoke_backend.py
Set-Location simulator/desktop
npm run make
```

Allow at least 2 GB free for a full packaging pass: Forge keeps
the backend, an expanded Electron package and the ZIP concurrently.

Forge writes the portable folder and ZIP under
`out/`. Dependency notices are included in `resources/backend/rov-sim/licenses`
and `resources/backend/rov-sim/_internal/viewer/CREDITS.md`.

Set `ROV_DESKTOP_SMOKE` to an absolute JSON file path before launching the packaged
executable to run the hidden renderer check. It writes model/state loading results
and a neighbouring `.png`, then closes. The backend smoke script separately verifies
local assets and a live Falcon multiplayer session using the frozen executable.

For a small launcher/viewer-only change, `node refresh_portable.cjs` refreshes the
existing portable archive and viewer without downloading or duplicating Electron.
Backend Python changes still require rebuilding the frozen backend. Set
`ROV_DESKTOP_SMOKE_MODEL=falcon` to test switching the packaged app to Falcon and
saving the preference; relaunch with the same user-data directory and without
that override to check persistence across launches.
