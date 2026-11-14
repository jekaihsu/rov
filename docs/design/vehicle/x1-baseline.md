# X1 training model: the quality bar

`simulator/viewer/models/rov.glb` is the internal training edition's X1 reconstruction. The user set it as
the minimum quality for any vehicle model. These figures were measured on the file at `main` (`afc3319`)
by reading the GLB JSON chunk (`cad/pack_observation_rov.py` → `describe()`) and by loading it through
`createVehicleModel()` in Chromium (`simulator/tools/render_vehicle_compare.py`).

## Numbers

| Measure | X1 `rov.glb` |
|---|---|
| File size | 1,378,116 bytes (1.38 MB) |
| Compression | `EXT_meshopt_compression` + `KHR_mesh_quantization` (glTF-Transform 4.5.1) |
| Unique triangles (one count per mesh) | 297,788 |
| Triangles drawn (every node instance) | 486,000 |
| Meshes / nodes / nodes with a mesh | 269 / 482 / 466 |
| Draw calls, front three-quarter view | 468 |
| Materials | 15, all constant factors (`KHR_materials_specular` on three) |
| Textures | none: no base colour, normal, roughness/metalness or occlusion maps |
| Bounding box after viewer centring (W × H × L) | 0.600 × 0.415 × 0.790 m |
| Rotor nodes | 6 (`ROTOR <name> \| animate local Z`, `role: rotor`, no `thruster_index`; the viewer matches them to thrusters spatially because the names are L/R swapped) |

## What is modelled

Triangles drawn per subsystem (node-name prefix, every instance counted):

| Subsystem | Triangles | Detail |
|---|---:|---|
| Six thrusters | 237,624 (6 × 39,604) | open aluminium nozzle with rolled lip and shroud seam, brushless motor can with gaskets and rounded end, 7-blade impeller with hub nose, hub bolts, clamp strap, yellow motor saddle, nozzle support, protective cage rails and outer hoop, mount screws, motor power cable |
| Moulded hull envelope | 75,776 | one continuous graphite shell |
| Downward DVL / forward DVL | 15,472 / 9,972 | transducer faces, metal rim, socket-head fasteners |
| Two LED lamps | 25,632 | COB emitter, concave reflector, protective glass, bezel ring with screws, moulded socket |
| Two cameras (front, lower) | 23,280 | bezel, curved lens, lens barrel and rings, clear cover, rubber seal |
| Nose / front fascia | 18,916 | laser wells and lens, sensor body, drainage aperture, service seam |
| Buoyancy blocks | 17,832 | port/starboard syntactic foam with M8 stainless inserts |
| Rear | 11,472 | access cover, tether strain-relief gland with ribs, short tether lead, cover fixings |
| Connector interfaces | 19,792 | four sealed connectors with flange, gasket, hex locking nut, rubber caps |
| Top | 11,960 | foldaway carry handle and feet, accessory latch base and shoe, latch and service plate with captive screws |
| Chassis | 8,920 | underbody longitudinal beams, vertical mounts, internal harness, fixings |
| Trim and bumpers | 4,720 | side bumpers, white longitudinal trim |
| Other | 4,632 | belly fairing, recessed fixing wells, reference housing (translucent) |
| **Total** | **486,000** | |

## Where the bar is high and where it is low

- **High:** geometric detail. Thrusters carry real 7-blade impellers, wire cages and fasteners; lamps and
  cameras have bezels, reflectors and glass; the hull is smooth, with no faceting at gameplay distances.
  Every socket-head screw has a hex recess.
- **Low:** surface. There is no texture of any kind, so there are no seams beyond modelled grooves, no
  wear, grime, machining marks or ambient occlusion; every surface is a flat colour. Large areas (hull,
  buoyancy) read as untextured plastic in close-up.
- **Cost:** 486k triangles drawn and 468 draw calls for one vehicle, six times the T11 hero budget
  (80k triangles). It is a single LOD.

A replacement therefore meets the bar if, side by side under the same camera and lights, it shows comparable
modelled detail (bladed rotors with guards, fasteners, lamp and camera optics, connectors, tether gland,
handles) and adds what the X1 lacks (PBR textures, wear, AO), within the T11 budget.
