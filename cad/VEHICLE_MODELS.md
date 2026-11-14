# ROV model provenance and rebuilding

The X1 uses the existing project reconstruction. The first generic Falcon approximation has been superseded by `build_falcon_reference.py`, reconstructed against official Saab photographs of the Falcon with a five-function manipulator skid. Its distinguishing geometry includes white polypropylene side plates with three upper slots, sculpted twin yellow shoulders with vent bores, red deck castings and bumpers, black thruster shrouds with red propellers, a high central camera, two lower LED lamps, an equipment skid and a scanning-sonar cage. This is still a photograph-based reconstruction; factory dimensional CAD has not been supplied. BlueROV2 Heavy currently remains an estimated study model pending replacement with verified manufacturer geometry.

The Falcon arm is now an articulated GLB hierarchy containing pantograph plates, hydraulic cylinders, hoses and hooked jaws. The viewer animates the authored joints rather than drawing a generic arm. Joint distances and mount coordinates are checked against the server mechanics. Link motion, loads and internal equipment dimensions remain simulation estimates.

Authoritative topology references:

- [Blue Robotics Heavy configuration](https://bluerobotics.com/introducing-bluerov2-heavy/): four horizontal vectored and four vertical thrusters, six controlled degrees of freedom.
- [BlueROV2 technical specifications](https://bluerobotics.com/store/rov/bluerov2/): base platform dimensions and component construction. The 13.5 kg Heavy weight here is a configured estimate, not the base vehicle specification.
- [Saab Seaeye Falcon specifications](https://www.saabseaeye.com/solutions/underwater-vehicles/falcon): five thrusters, approximately 1.0 × 0.6 × 0.5 m, 60 kg, depth/heading automation. Four horizontal thrusters and one vertical provide surge, sway, heave and yaw control; this simulator does not add active roll or pitch authority.
- Official photograph reference set: [port quarter](https://www.saabseaeye.com/uploads/falcon2.jpg), [starboard quarter](https://www.saabseaeye.com/uploads/falcon1_%281%29.jpg), [front](https://www.saabseaeye.com/uploads/falcon-front-on.jpg), [skid and manipulator](https://www.saabseaeye.com/uploads/seaeye-falcon-with-skid-and-manip_%281%29.jpg). Photographs are reference-only and are not embedded in the distributed models.

Mass/size for Falcon and propulsion topology are grounded in those references. Individual thruster placement/force, inertia, added mass, drag, flotation offset, collision proxies, camera/light/arm anchors and controller response are estimates for simulation. Matching motor counts does not imply validated real-vehicle handling. X1 coefficients remain compatible with the existing project tests.

Run from repository root:

```powershell
& 'C:/Users/asus/AppData/Local/Programs/Blender/blender-4.5.9-windows-x64/blender.exe' --background --factory-startup --python cad/build_vehicle_fleet.py -- (Get-Location).Path
```

Outputs: `cad/bluerov2_heavy.blend`, `cad/falcon.blend`, and matching `simulator/viewer/models/*.glb`. The reproducible source is `build_vehicle_fleet.py`, with physical definitions in `simulator/qysim/vehicles.py`. No manufacturer logos or downloaded proprietary CAD are included. Coordinates originate at the defined centre of gravity; GLB +Z is forward and +Y is up. `thruster_index` extras provide stable rotor-to-motor mapping. The visual dimensions are approximations and should be refined against approved orthographic references before claiming replica fidelity.

## T11a opt-in observation prototype

`build_original_vehicles.py` is the editable Blender source for one original
Observation ROV. No photographs, manufacturer CAD or external textures were used.
The previous work/open-frame drafts have been withdrawn pending acceptance of
this first vehicle. Existing training assets remain the default in all distributions.
Use `?assets=generic&model=x1` explicitly to inspect the prototype.

Build from repository root with Blender 4.3.2, Node 22,
`@gltf-transform/cli` 4.4.0 and KTX-Software 4.4.2 (`toktx`) on PATH:

```sh
python simulator/tools/build_assets.py
python simulator/tools/build_assets.py --check
```

The pipeline exports three LODs, encodes embedded 2048² surface maps as KTX2 UASTC,
then applies meshopt. Temporary uncompressed exports stay in `.runtime/assets`.
Blender's texture multiplication does not preserve tint in glTF, so the pipeline
restores authored linear material factors from exported material extras before
compression. Roughness and AO share an ORM image; metalness is the authored
material scalar. `assets-report.json` reads actual KTX2 dimensions and reports
triangles, file bytes and conservative RGBA8 GPU texture memory including mipmaps.
Texture memory is per asset instance without cross-LOD deduplication.

The observation prototype includes segmented buoyancy cassettes, retaining straps,
fasteners, lifting handles, end-cap bolts, wet-mate connectors and harnesses,
thruster lips/stators/rotors, panel seams and an original service plate. These are
engineering assumptions for a generic vehicle, not measured X1 details. Materials
use procedural machining grain, scratches and seam masks; AO is not a baked cavity
map and wear is not physically validated. Artistic acceptance remains with review.

Per `docs/reference/real-rov-research.md`, visual fidelity must not imply a validated
physical twin. X1-specific geometry/coefficients remain provisional; the own-data
directory cited by AGENTS.md is absent from this checkout. No physical, camera FOV,
latency, lighting photometry, controller or SDK parameters change here. Existing
FRD motor anchors and collision spheres are retained exactly. Third-person captures
are a training/asset-inspection aid, not the real pilot's view.

KTX2 uses the caller's existing renderer via `configureAssetRenderer`; no probe
WebGL context is created. The vendor manifest explicitly includes the runtime
Basis JS/WASM files. Both showcase formats include the new modules and assets.

The preview offers LOD, wireframe, PBR channels, collision spheres and camera/lamp
pivot controls. Runtime still uses LOD0. Reproduce side-by-side captures and actual
in-game loading checks with `CHROME_PATH=/path/to/chrome python
simulator/tools/browser_assets.py`; default Chrome is used if CHROME_PATH is unset.
