"""Export the Korean Castle wreck scene for the simulator (run inside Blender 4.x).

    blender -b Korean_Castle_Display.blend --python tools/wreck_blender_export.py -- OUT_DIR
    (or: python -c "import bpy" style with the bpy module:  python wreck_blender_export.py SRC.blend OUT_DIR)

Writes to OUT_DIR:
    korean_castle_raw.glb   visual collections 01_BOW..05_SEABED (hull, encrustation, seabed)
    collision_tris.npy      09_COLLISION triangles, Blender frame (X bow->stern, Y transverse, Z up)
    route_verts.npy         10_ROV_ROUTE preview path vertices
    labels.json             engineering label texts
Then run tools/build_wreck.py to make the distance field and compress the GLB.
"""
import bpy, sys, json
import numpy as np
from mathutils import Vector
src, outdir = sys.argv[-2], sys.argv[-1]
bpy.ops.wm.open_mainfile(filepath=src)
dg = bpy.context.evaluated_depsgraph_get()
VIS = ['01_BOW', '02_MID', '03_STERN', '04_ENCRUSTATION', '05_SEABED']

def tris_of(o):
    ev = o.evaluated_get(dg); me = ev.to_mesh(); me.calc_loop_triangles()
    M = o.matrix_world
    V = np.array([tuple(M @ v.co) for v in me.vertices], float)
    T = np.array([tuple(t.vertices) for t in me.loop_triangles], int)
    ev.to_mesh_clear()
    return V, T

# collision triangles
cols = []
for o in bpy.data.collections['09_COLLISION'].objects:
    V, T = tris_of(o); cols.append((o.name, V[T]))
tri = np.concatenate([c[1] for c in cols])
np.save(outdir + '/collision_tris.npy', tri.astype(np.float32))
print('collision tris', tri.shape, 'objects', [(n, len(t)) for n, t in cols])

# inspection labels: centre of each text object's evaluated geometry
labels = []
for o in bpy.data.collections['08_ENGINEERING'].objects:
    if o.type != 'FONT': continue
    ev = o.evaluated_get(dg); me = ev.to_mesh()
    P = np.array([tuple(o.matrix_world @ v.co) for v in me.vertices]); ev.to_mesh_clear()
    if len(P): labels.append({'name': o.data.body, 'pos': [round(float(x), 2) for x in P.mean(0)], 'rot': [round(float(r), 3) for r in o.rotation_euler]})
print('labels', len(labels), labels[:3], labels[-2:])

# route: vertices of the preview path mesh
r = bpy.data.objects['Preview_ROV_path']
V, T = tris_of(r)
np.save(outdir + '/route_verts.npy', V)
print('route verts', V.shape, V[:6].round(2).tolist())

# camera + ROV lamp for reference
for o in list(bpy.data.collections['07_CAMERAS'].objects):
    print('cam', o.name, [round(v, 1) for v in o.matrix_world.translation])
json.dump({'labels': labels}, open(outdir + '/labels.json', 'w'))

# visual export
for o in bpy.data.objects: o.select_set(False)
keep = set()
for cn in VIS:
    for o in bpy.data.collections[cn].all_objects: keep.add(o.name)
for o in bpy.data.objects:
    if o.name in keep: o.select_set(True)
print('export objects', len(keep))
for m in bpy.data.materials:
    print('mat', m.name, [n.type for n in m.node_tree.nodes][:12] if m.use_nodes else None)
bpy.ops.export_scene.gltf(filepath=outdir + '/korean_castle_raw.glb', export_format='GLB', use_selection=True,
                          export_image_format='JPEG', export_image_quality=82, export_apply=True)
