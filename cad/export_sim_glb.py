import bpy, sys
from mathutils import Vector
OUT = sys.argv[-2]
bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])

# drop studio / references / replaced skins / third-party lettering
drop = []
for o in bpy.data.objects:
    cn = o.users_collection[0].name if o.users_collection else ''
    if cn.startswith(('90', '98', '99')) or 'marking' in o.name:
        drop.append(o)
for o in drop:
    bpy.data.objects.remove(o, do_unlink=True)

T = {'PORT_FRONT': 'thrPF', 'STBD_FRONT': 'thrSF', 'PORT_AFT': 'thrPA',
     'STBD_AFT': 'thrSA', 'PORT_LONG': 'thrPL', 'STBD_LONG': 'thrSL'}
M = {'Hull': 'hull', 'Fairing': 'hull', 'Rear cover': 'hull', 'Belly': 'belly',
     'Nose': 'nose', 'Front': 'dvlF', 'Forward DVL': 'dvlF', 'Downward DVL': 'dvlD',
     '4K FRONT CAMERA': 'camF', '4K LOWER CAMERA': 'camL',
     'LED PORT': 'ledP', 'LED STARBOARD': 'ledS',
     'Latch': 'top', 'Top': 'top', 'Top plate': 'top', 'Rear': 'tether',
     'PORT': 'chassis', 'STBD': 'chassis', 'BUOY PORT': 'buoyP', 'BUOY STBD': 'buoyS',
     'REF': 'housing'}

def to3(v):  # Blender Z-up (fwd -Y) -> three.js Y-up (fwd +Z)
    return [round(v.x, 5), round(v.z, 5), round(-v.y, 5)]

for o in bpy.data.objects:
    pre = o.name.split(' | ')[0]
    g = None
    for k, v in T.items():
        if pre in (k, 'ROTOR ' + k, 'THRUSTER ' + k):
            g = v
    if g is None:
        g = M.get(pre) or ('top' if pre.startswith('Q interface') else None)
    if g:
        o['grp'] = g
    if pre.startswith(('ROTOR ', 'THRUSTER ')):
        ax = (o.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
        o['axis'] = to3(ax)
        o['pos'] = to3(o.matrix_world.translation)
        o['role'] = 'rotor' if pre.startswith('ROTOR') else 'thruster'
    if o.type == 'MESH' and o.data.materials:
        m = o.data.materials[0]
        if m and m.name.startswith('22'):
            o['xray'] = 1

bpy.ops.export_scene.gltf(filepath=OUT, export_format='GLB', export_extras=True,
                          export_apply=True, export_yup=True, export_cameras=False,
                          export_lights=False, export_animations=False)
print('exported', OUT)
