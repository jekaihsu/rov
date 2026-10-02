"""Build editable, unbranded study models in Blender (not factory CAD).

blender --background --python cad/build_vehicle_fleet.py -- PROJECT_ROOT
Vehicle origins stay at CG. GLB local axes are Three.js: +Z forward, +Y up.
"""
import math
import sys
from pathlib import Path

import bpy
from mathutils import Vector

ROOT = Path(sys.argv[sys.argv.index('--') + 1]).resolve()
bpy.context.preferences.filepaths.save_version = 0
sys.path.insert(0, str(ROOT / 'simulator'))
from qysim.vehicles import get_vehicle_definition


def point(frd):
    x, y, z = frd
    return Vector((-y, -x, -z))


def material(name, rgb, metallic=0., rough=.5):
    m = bpy.data.materials.new(name)
    m.diffuse_color = (*rgb, 1)
    m.use_nodes = True
    bsdf = m.node_tree.nodes.get('Principled BSDF')
    bsdf.inputs['Base Color'].default_value = (*rgb, 1)
    bsdf.inputs['Metallic'].default_value = metallic
    bsdf.inputs['Roughness'].default_value = rough
    return m


def finish(o, name, mat):
    o.name = name
    o.data.materials.append(mat)
    return o


def box(name, centre, size, mat, bevel=.008):
    bpy.ops.mesh.primitive_cube_add(size=1, location=point(centre))
    o = finish(bpy.context.object, name, mat)
    o.dimensions = (size[1], size[0], size[2])
    bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
    if bevel:
        mod = o.modifiers.new('Machined edges', 'BEVEL')
        mod.width = bevel
        mod.segments = 3
        o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o


def cylinder(name, centre, radius, length, axis, mat, vertices=32):
    bpy.ops.mesh.primitive_cylinder_add(vertices=vertices, radius=radius, depth=length, location=point(centre))
    o = finish(bpy.context.object, name, mat)
    o.rotation_mode = 'QUATERNION'
    o.rotation_quaternion = Vector((0, 0, 1)).rotation_difference(point(axis).normalized())
    bevel = o.modifiers.new('Edge finish', 'BEVEL'); bevel.width=.002; bevel.segments=2
    o.modifiers.new('Weighted normals', 'WEIGHTED_NORMAL')
    return o


def ring(name, centre, radius, axis, mat, thickness=.008):
    bpy.ops.mesh.primitive_torus_add(major_radius=radius, minor_radius=thickness,
                                   major_segments=40, minor_segments=8, location=point(centre))
    o = finish(bpy.context.object, name, mat)
    o.rotation_mode='QUATERNION'
    o.rotation_quaternion=Vector((0,0,1)).rotation_difference(point(axis).normalized())
    for p in o.data.polygons: p.use_smooth=True
    return o


def rod(name, a, b, radius, mat):
    a, b = Vector(a), Vector(b)
    return cylinder(name, (a+b)/2, radius, (b-a).length, b-a, mat, 16)


def duct(name, centre, radius, axis, mat):
    # An actual hollow annular casing, with no caps covering the propeller.
    n=40; vertices=[]; faces=[]
    rotation=Vector((0,0,1)).rotation_difference(point(axis).normalized())
    origin=point(centre)
    for r,z in ((radius+.005,-.05),(radius+.005,.05),(radius-.006,.05),(radius-.006,-.05)):
        for i in range(n):
            angle=i*2*math.pi/n
            vertices.append(origin+rotation@Vector((r*math.cos(angle),r*math.sin(angle),z)))
    for ring_i in range(4):
        following=(ring_i+1)%4
        for i in range(n):
            j=(i+1)%n
            faces.append((ring_i*n+i,ring_i*n+j,following*n+j,following*n+i))
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    o=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(o);o.data.materials.append(mat)
    for poly in mesh.polygons:poly.use_smooth=True
    o.modifiers.new('Duct normals','WEIGHTED_NORMAL')
    return o


def thruster(index, position, direction, radius, mats):
    p = Vector(position); axis = Vector(direction).normalized()
    quat = Vector((0,0,1)).rotation_difference(point(axis))
    for sign in (-1,1):
        ring(f'T{index+1} duct rim', p+axis*(sign*.052), radius, axis, mats['black'])
    duct(f'T{index+1} open duct',p,radius,axis,mats['black'])
    cylinder(f'T{index+1} motor hub', p, radius*.26, .095, axis, mats['metal'])
    bpy.ops.object.empty_add(type='PLAIN_AXES', location=point(p))
    rotor=bpy.context.object; rotor.name=f'Rotor_{index}'; rotor.rotation_mode='QUATERNION'; rotor.rotation_quaternion=quat
    rotor['role']='rotor'; rotor['thruster_index']=index; rotor['local_axis']=[0.,0.,1.]
    for k in range(3):
        ang=k*2*math.pi/3
        bpy.ops.mesh.primitive_cube_add(size=1)
        blade=finish(bpy.context.object, f'T{index+1} propeller blade {k}', mats['prop'])
        blade.parent=rotor; blade.location=(math.cos(ang)*radius*.45,math.sin(ang)*radius*.45,0)
        blade.rotation_euler=(.24,0,ang); blade.scale=(radius*.78,radius*.19,.006)
        bevel=blade.modifiers.new('Rounded blade', 'BEVEL'); bevel.width=.12; bevel.segments=3
    # Motor support struts, behind the turning blades.
    for k in range(3):
        angle=k*2*math.pi/3
        offset=quat @ Vector((math.cos(angle)*radius*.85,math.sin(angle)*radius*.85,-.043))
        a=point(p)+quat@Vector((0,0,-.043)); b=point(p)+offset
        bpy.ops.mesh.primitive_cylinder_add(vertices=10,radius=.004,depth=(b-a).length,location=(a+b)/2)
        o=finish(bpy.context.object,f'T{index+1} support',mats['metal']); o.rotation_mode='QUATERNION'; o.rotation_quaternion=Vector((0,0,1)).rotation_difference(b-a)


def build(model_id):
    bpy.ops.object.select_all(action='SELECT'); bpy.ops.object.delete(use_global=False)
    d=get_vehicle_definition(model_id); heavy=model_id=='bluerov2_heavy'
    mats=dict(black=material('Black polymer',(.022,.031,.042),.05,.42),
              metal=material('Brushed stainless',(.37,.42,.46),.8,.3),
              buoy=material('Blue buoyancy foam' if heavy else 'Yellow buoyancy',(.025,.22,.65) if heavy else (.98,.73,.035),.03,.48),
              prop=material('Propeller polymer',(.16,.18,.21),.2,.42),
              lens=material('Camera optical glass',(.012,.027,.038),.5,.08),
              lamp=material('LED diffuser',(.84,.92,.99),.25,.16),
              orange=material('Umbilical jacket',(.91,.30,.025),0,.65))
    L,W,H=(.46,.34,.31) if heavy else (.86,.50,.48)
    # Rails, posts, skids, cross members and fasteners; no solid enclosing box.
    for side in (-1,1):
        y=side*W/2
        box('Skid rail', (0,y,H/2), (L+.06,.035,.032), mats['black'])
        box('Upper frame rail',(0,y,-H*.34),(L,.025,.025),mats['black'])
        for x in (-L*.43,L*.43):
            box('Frame upright',(x,y,0),(.025,.025,H),mats['black'])
            for z in (-H*.34,H*.43):
                cylinder('Frame hex bolt',(x,y+side*.018,z),.009,.008,(0,1,0),mats['metal'],6)
        box('Buoyancy shoulder',(0,side*(W/2-.03 if heavy else W/2-.015),-H*.43),(L*.88,.085 if heavy else .17,.085 if heavy else .15),mats['buoy'],.020)
        if heavy:
            for x in (-.13,.13):
                rod('Vertical thruster outrigger',(x,side*.17,-.07),(x,side*.24,-.07),.008,mats['metal'])
    for x in (-L*.4,0,L*.4):
        box('Deck cross member',(x,0,H*.3),(.025,W,.024),mats['metal'])
    # Longitudinal pressure bottles with end cap rings and lens.
    housing_z=-.025 if heavy else .035
    cylinder('Electronics pressure housing',(0,0,housing_z),.054 if heavy else .075,L*.82,(1,0,0),mats['metal'])
    for x in (-L*.41,L*.41):
        cylinder('Pressure end cap',(x,0,housing_z),.060 if heavy else .082,.018,(1,0,0),mats['black'])
        ring('End cap sealing ring',(x,0,housing_z),.052 if heavy else .074,(1,0,0),mats['metal'],.003)
    cylinder('Battery housing',(-.03,0,H*.26),.042 if heavy else .063,L*.66,(1,0,0),mats['black'])
    for i,(name,pos,axis) in enumerate(d.thrusters):
        thruster(i,pos,axis,.047 if heavy else .080,mats)
    for i,p in enumerate(d.lamp_body):
        cylinder(f'LED housing {i}',p,.029 if heavy else .04,.08,(1,0,0),mats['metal'])
        lens=Vector(p)+Vector((.041,0,0))
        cylinder(f'LED lens {i}',lens,.023 if heavy else .034,.008,(1,0,0),mats['lamp'])
        for j in range(6):
            ang=j*math.pi/3
            cylinder('LED emitter',(lens.x+.005,lens.y+math.cos(ang)*.014,lens.z+math.sin(ang)*.014),.004,.003,(1,0,0),mats['lamp'],12)
    cylinder('Camera gimbal',d.camera_body,.04 if heavy else .055,.075,(0,1,0),mats['black'])
    cylinder('Camera lens',Vector(d.camera_body)+Vector((.045 if heavy else .061,0,0)),.024 if heavy else .035,.024,(1,0,0),mats['lens'])
    # Umbilical strain relief and exposed routed hoses.
    p=Vector(d.gland_body)
    rod('Umbilical feedthrough',(-L*.36,0,housing_z),p,.012,mats['black'])
    cylinder('Tether strain relief',p,.016,.11,(1,0,0),mats['orange'])
    for i in range(6): ring('Strain relief rib',p+Vector((i*.014-.035,0,0)),.018,(1,0,0),mats['black'],.002)
    for side in (-1,1):
        path=[(-L*.4,side*W*.25,-H*.17),(-L*.1,side*W*.32,-H*.21),(L*.3,side*W*.35,-H*.12)]
        for a,b in zip(path,path[1:]): rod('Exposed power cable',a,b,.006,mats['black'])
    if not heavy:
        box('Upper buoyancy bridge',(-.04,0,-H*.46),(.65,.42,.10),mats['buoy'],.025)
        # Clear central aperture for the single vertical thruster.
        # Bridge split around thruster, preserving actual topology.
        bpy.data.objects.remove(bpy.data.objects['Upper buoyancy bridge'],do_unlink=True)
        for x in (-.28,.28): box('Upper buoyancy bridge',(x,0,-H*.44),(.20,.45,.09),mats['buoy'],.018)
        for x in (-.33,.33): rod('Lift handle',(x,-.14,-H*.56),(x,.14,-H*.56),.014,mats['metal'])
    for key,pos in [('camera',d.camera_body),('tether',d.gland_body),('arm_mount',d.arm_mount_body)]+[(f'lamp_{i}',p) for i,p in enumerate(d.lamp_body)]:
        bpy.ops.object.empty_add(type='PLAIN_AXES', location=point(pos)); bpy.context.object.name=f'anchor_{key}'; bpy.context.object['anchor']=key
    bpy.context.scene.unit_settings.system='METRIC'
    bpy.context.scene['model_notes']='Unbranded visual reconstruction; dimensions and dynamics approximate. See VEHICLE_MODELS.md.'
    out=ROOT/'simulator'/'viewer'/'models'/f'{model_id}.glb'
    bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'cad'/f'{model_id}.blend'))
    bpy.ops.export_scene.gltf(filepath=str(out),export_format='GLB',export_extras=True,export_apply=True,export_yup=True,export_cameras=False,export_lights=False)
    print('Built',model_id, 'objects',len(bpy.context.scene.objects), 'bytes',out.stat().st_size)


if __name__ == '__main__':
    build('bluerov2_heavy')
    import runpy
    runpy.run_path(str(ROOT/'cad'/'build_falcon_reference.py'),run_name='__main__')
