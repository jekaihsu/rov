"""Falcon rebuild from the official Saab front/quarter photographs.

Reference images (not distributed): saabseaeye.com/uploads/falcon2.jpg,
falcon1_(1).jpg, falcon-front-on.jpg, seaeye-falcon-with-skid-and-manip_(1).jpg.
This source measures the visible silhouette against the published 1.0/.6/.5 m
envelope. Internal dimensions not published by Saab remain estimates.
"""
import math
import sys
from pathlib import Path
import bpy
import bmesh
from mathutils import Vector

ROOT=Path(sys.argv[sys.argv.index('--')+1]).resolve()
sys.path.insert(0,str(ROOT/'cad'))
from build_vehicle_fleet import point, material, box, cylinder, ring, rod, thruster
sys.path.insert(0,str(ROOT/'simulator'))
from qysim.vehicles import get_vehicle_definition

bpy.ops.object.select_all(action='SELECT');bpy.ops.object.delete(use_global=False)
bpy.context.preferences.filepaths.save_version=0
m={
 'white':material('White polypropylene side frame',(.82,.85,.84),0,.40),
 'yellow':material('Falcon yellow moulded buoyancy cover',(.68,.48,.0005),0,.34),
 'red':material('Red deck and propellers',(.65,.004,.008),0,.32),
 'black':material('Black polymer motor and shroud',(.015,.018,.022),.08,.28),
 'metal':material('Stainless machined fixtures',(.43,.48,.51),.90,.23),
 'magenta':material('Bumper wear insert',(.23,.065,.16),.03,.48),
 'glass':material('Camera lens optical coating',(.008,.018,.028),.65,.08),
 'led':material('White LED emitters',(.92,.95,.91),.1,.18),
 'cable':material('Orange red power cable',(.72,.035,.015),0,.46),
 'rubber':material('Hydraulic hose',(.008,.01,.012),0,.56),
 'label':material('Safety yellow labels',(.97,.79,.025),0,.6),
}


def mesh_object(name,vertices,faces,mat):
    mesh=bpy.data.meshes.new(name);mesh.from_pydata(vertices,[],faces);mesh.update()
    bm=bmesh.new();bm.from_mesh(mesh);bmesh.ops.recalc_face_normals(bm,faces=bm.faces);bm.to_mesh(mesh);bm.free()
    obj=bpy.data.objects.new(name,mesh);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    return obj


def rounded_plate(name,centre,L,H,thickness,r,mat):
    cx,cy,cz=centre;outline=[]
    for sx,sz,start in ((1,1,0),(-1,1,90),(-1,-1,180),(1,-1,270)):
        for k in range(9):
            a=math.radians(start+k*90/8)
            outline.append((sx*(L/2-r)+r*math.cos(a),sz*(H/2-r)+r*math.sin(a)))
    n=len(outline)
    verts=[point((cx+x,cy+y,cz+z)) for y in (-thickness/2,thickness/2) for x,z in outline]
    faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]
    faces += [(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    return mesh_object(name,verts,faces,mat)


def cut(obj,cutter):
    bpy.context.view_layer.objects.active=obj
    mod=obj.modifiers.new('Machined opening','BOOLEAN');mod.operation='DIFFERENCE';mod.solver='EXACT';mod.object=cutter
    bpy.ops.object.modifier_apply(modifier=mod.name)
    bpy.data.objects.remove(cutter,do_unlink=True)


def soften(obj,width=.003):
    bevel=obj.modifiers.new('Soft mould edge','BEVEL');bevel.width=width;bevel.segments=3
    obj.modifiers.new('Surface normals','WEIGHTED_NORMAL')


def hose(name,points,radius,mat):
    curve=bpy.data.curves.new(name,'CURVE');curve.dimensions='3D';curve.bevel_depth=radius;curve.bevel_resolution=3
    spline=curve.splines.new('BEZIER');spline.bezier_points.add(len(points)-1)
    for knot,p in zip(spline.bezier_points,points):
        knot.co=point(p);knot.handle_left_type='AUTO';knot.handle_right_type='AUTO'
    obj=bpy.data.objects.new(name,curve);bpy.context.collection.objects.link(obj);obj.data.materials.append(mat)
    return obj


def bolt(name,p,axis=(0,1,0),r=.004):
    cylinder(name,p,r,.004,axis,m['metal'],6)
    ring(name+' washer',p,r*1.3,axis,m['metal'],.0008)


# The characteristic PP side frames are plates with cutouts, never tubular rails.
for sign in (-1,1):
    y=sign*.287
    plate=rounded_plate('PP side frame',(0,y,0),1.0,.50,.021,.065,m['white'])
    cut(plate,rounded_plate('Large lower aperture',(0,y,.065),.886,.304,.06,.037,m['white']))
    for x in (-.315,0,.315):
        cut(plate,rounded_plate('Upper lifting slot',(x,y,-.182),.235,.038,.06,.012,m['white']))
    soften(plate,.003)
    for x in (-.425,-.31,-.19,-.06,.06,.19,.31,.425):
        bolt('Frame upper fastener',(x,y+sign*.012,-.122),(0,1,0),.0037)
    for x in (-.425,-.31,.31,.425):
        bolt('Frame lower fastener',(x,y+sign*.012,.224),(0,1,0),.0037)
    # Aluminium C-channels and cross braces are below the thrusters.
    box('Lower channel web',(0,sign*.174,.216),(.96,.035,.009),m['metal'],.001)
    for dy in (-.0175,.0175):box('Lower channel flange',(0,sign*.174+dy,.205),(.96,.004,.025),m['metal'],.001)
    for x in (-.40,.40):
        rod('Diagonal support sleeve',(x,sign*.246,.202),(x*.48,sign*.09,-.09),.010,m['black'])
        rod('Diagonal stainless tie',(x,sign*.246,.202),(x*.48,sign*.09,-.09),.005,m['metal'])
for x in (-.438,.438):
    box('PP cross frame',(x,0,.223),(.035,.57,.026),m['white'],.004)
    for y in (-.225,-.10,.10,.225):bolt('Crossframe fixing',(x,y,.207),(0,0,1))


def float_lobe(sign):
    # Long rounded cover: flattened crown, swollen nose/side shoulders, thin lip.
    # Superellipse sections, then taper only the leading/rear longitudinal ends.
    sections=[(-.492,.015,.001),(-.485,.40,.04),(-.465,.70,.087),(-.445,.91,.12),(-.39,1.,.135),(-.27,1.,.14),
              (.16,1.,.14),(.30,1.,.137),(.385,.95,.125),(.438,.80,.096),(.475,.46,.041),(.492,.015,.001)]
    ring_count=25;vertices=[];centre=sign*.152
    for x,scale,height in sections:
        for k in range(ring_count):
            t=math.pi*k/(ring_count-1)
            # Clipped lower half gives a broad flat lower lip and rounded crown.
            y=centre+math.copysign(abs(math.cos(t))**.78,math.cos(t))*.124*scale
            z=-.118-height*max(0,math.sin(t))**.72
            vertices.append(point((x,y,z)))
    faces=[]
    for j in range(len(sections)-1):
        for k in range(ring_count):faces.append((j*ring_count+k,j*ring_count+(k+1)%ring_count,(j+1)*ring_count+(k+1)%ring_count,(j+1)*ring_count+k))
    faces.extend([tuple(range(ring_count-1,-1,-1)),tuple((len(sections)-1)*ring_count+i for i in range(ring_count))])
    obj=mesh_object('Sculpted buoyancy shoulder',vertices,faces,m['yellow'])
    for p in obj.data.polygons:p.use_smooth=True
    # Ventilation ports are through holes, visible on the sloped nose and sides.
    for y in (centre-.071,centre,centre+.071):
        cutter=cylinder('Nose ventilation bore',(.394,y,-.199),.014,.20,(.8,0,-.6),m['black'],24)
        cut(obj,cutter)
    for x in (-.34,-.23,-.12,.0,.12,.24):
        cutter=cylinder('Side ventilation bore',(x,centre+sign*.105,-.19),.012,.13,(0,sign,-.25),m['black'],24)
        cut(obj,cutter)
    soften(obj,.0015)
    # Silver cover fasteners on both domes.
    for x in (-.33,.31):bolt('Cover captive screw',(x,centre,-.251),(0,0,1),.006)
    return obj


for sign in (-1,1):float_lobe(sign)
# The rear deck joins the two shoulders; the front leaves a shaped camera trough.
bridge=box('Buoyancy rear bridge',(-.19,0,-.219),(.48,.36,.069),m['yellow'],.029)
for x in (-.05,-.27):
    cutter=cylinder('Deck instrument aperture',(x,0,-.21),.040,.20,(0,0,1),m['black'],40)
    cut(bridge,cutter)

# Red under-deck castings and black polyurethane bumpers.
for sign in (-1,1):
    y=sign*.152
    box('Red longitudinal deck',(0,y,-.091),(.94,.247,.061),m['red'],.018)
    box('Rounded red forward apron',(.418,y,-.077),(.102,.252,.087),m['red'],.027)
    hose('Black nose bumper',[(.474,y-.102,-.080),(.481,y-.06,-.079),(.484,y,-.079),(.481,y+.06,-.079),(.474,y+.102,-.080)],.015,m['black'])
    hose('Bumper magenta rubbing strip',[(.489,y-.086,-.081),(.494,y,-.081),(.489,y+.086,-.081)],.010,m['magenta'])

d=get_vehicle_definition('falcon')
for i,(_,pos,axis) in enumerate(d.thrusters):
    radius=.107 if i<4 else .092
    thruster(i,pos,axis,radius,{'black':m['black'],'metal':m['black'],'prop':m['red']})
    p=Vector(pos);a=Vector(axis).normalized()
    cylinder(f'T{i+1} rear motor cylinder',p-a*.079,.043,.12,axis,m['black'])
    # Real photo shows two vertical guard bars across the open front of each duct.
    if i<4:
        rod('Thruster vertical guard',p+Vector((0,0,-radius)),p+Vector((0,0,radius)),.005,m['black'])
        cylinder('Thruster lower pivot',p+Vector((0,0,radius+.007)),.011,.016,(0,0,1),m['metal'])

# Forward camera is high in the centre between the two buoyancy noses.
camera=Vector(d.camera_body)
cylinder('Black forward camera pressure tube',camera-Vector((.10,0,0)),.050,.22,(1,0,0),m['black'])
for dx in (-.17,-.044):ring('Camera stainless securing band',camera+Vector((dx,0,0)),.052,(1,0,0),m['metal'],.003)
for dx,r in ((-.009,.053),(.0,.047),(.006,.039),(.010,.030),(.013,.019)):
    cylinder('Camera concentric optical bezel',camera+Vector((dx,0,0)),r,.009,(1,0,0),m['metal'] if r>.046 else m['glass'])
for side in (-1,1):
    box('Camera tilt yoke',camera+Vector((-.083,side*.058,.045)),(.15,.010,.052),m['metal'],.002)
    cylinder('Camera tilt trunnion',camera+Vector((-.085,side*.059,0)),.013,.022,(0,1,0),m['metal'])
box('Camera tilt platform',camera+Vector((-.09,0,.071)),(.14,.13,.011),m['white'],.004)

# Twin lower LED lamps, detailed front optics and their PP mounting blocks.
for i,anchor in enumerate(d.lamp_body):
    p=Vector(anchor)
    box('White LED mounting saddle',p+Vector((-.045,0,-.055)),(.095,.103,.050),m['white'],.009)
    cylinder('White LED pressure body',p-Vector((.046,0,0)),.041,.078,(1,0,0),m['white'])
    cylinder('Black LED front bezel',p+Vector((.005,0,0)),.042,.032,(1,0,0),m['black'])
    for side in (-1,1):bolt('LED bracket pivot',p+Vector((-.047,side*.055,-.05)),(0,1,0),.006)
    ring('LED aluminium bezel',p+Vector((.017,0,0)),.036,(1,0,0),m['metal'],.002)
    cylinder('LED diffuser',p+Vector((.019,0,0)),.032,.004,(1,0,0),m['glass'])
    for j in range(20):
        t=j*math.pi/10
        cylinder('Individual LED',p+Vector((.022,math.cos(t)*.023,math.sin(t)*.023)),.0038,.003,(1,0,0),m['led'],10)
    cylinder('LED centre reflector',p+Vector((.023,0,0)),.011,.003,(1,0,0),m['led'],20)

# Dense lower electronics and visible routed power cables (not a central silver tube).
for y in (-.066,.066):
    cylinder('Lower pressure housing',(-.08,y,.13),.042,.38,(1,0,0),m['black'])
    for x in (-.27,.11):ring('Housing end ring',(x,y,.13),.045,(1,0,0),m['metal'],.003)
cylinder('Vertical junction housing',(-.025,0,.10),.050,.18,(0,0,1),m['black'])
hose('Red front power loop',[(.20,-.08,-.09),(.35,-.035,.14),(.29,.075,.18),(.17,.10,.03)],.009,m['cable'])
for side in (-1,1):
    hose('Thruster power harness',[(-.36,side*.12,-.08),(-.23,side*.18,.04),(.04,side*.10,.15),(.28,side*.16,.075)],.004,m['rubber'])
    hose('Lamp cable',[(.15,side*.11,-.09),(.34,side*.20,-.04),(.40,side*.24,.01)],.0035,m['rubber'])
# Yellow umbilical departs upward near the aft crown, with black spring relief.
gland=Vector(d.gland_body)
hose('Yellow tether neck',[gland+Vector((0,0,.005)),gland+Vector((-.028,0,-.075)),gland+Vector((-.07,0,-.13))],.006,m['yellow'])
rod('Tether spring core',gland+Vector((-.028,0,-.075)),gland+Vector((-.12,0,-.22)),.009,m['black'])
for k in range(12):ring('Umbilical spring coil',gland+Vector((-.028-.0075*k,0,-.075-.012*k)),.011,(-.53,0,-.848),m['black'],.002)
ring('Stainless lifting eye',(-.23,0,-.278),.018,(0,1,0),m['metal'],.004)
# The selected official skid/manipulator configuration carries a small scanning
# sonar on the aft shoulder: a black transducer window in a white protective cage.
sonar=Vector((-.27,-.145,-.303))
cylinder('Scanning sonar black transducer',sonar,.031,.085,(0,0,1),m['black'])
for z in (-.351,-.257):
    cylinder('Sonar white end cap',(-.27,-.145,z),.038,.014,(0,0,1),m['white'])
for sx,sy in ((1,1),(-1,1),(1,-1),(-1,-1)):
    box('Sonar protective cage post',sonar+Vector((sx*.026,sy*.026,0)),(.012,.012,.085),m['white'],.002)

# White accessory skid and black hydraulic/electrical package visible in the
# manufacturer's five-function manipulator photograph.
for side in (-1,1):
    sideplate=rounded_plate('Manipulator skid side',(0,side*.286,.334),.98,.205,.018,.035,m['white'])
    cut(sideplate,rounded_plate('Skid side aperture',(-.035,side*.286,.313),.74,.09,.05,.016,m['white']))
    soften(sideplate,.002)
box('Manipulator skid bottom',(0,0,.427),(.93,.56,.015),m['white'],.007)
box('Skid hydraulic power unit',(-.10,.125,.34),(.65,.22,.145),m['black'],.012)
box('Skid manifold enclosure',(.11,-.13,.31),(.39,.22,.072),m['black'],.009)
for x in (-.02,.20):
    for y in (-.21,-.045):bolt('Manipulator manifold fitting',(x,y,.269),(0,0,1),.007)
hose('Skid hydraulic supply',[(-.32,-.09,.28),(-.12,-.24,.30),(.12,-.22,.33),(.30,-.12,.38)],.005,m['rubber'])


def arm_empty(name,location,parent=None):
    bpy.ops.object.empty_add(type='PLAIN_AXES',location=point(location))
    o=bpy.context.object;o.name=name;o['arm_node']=name
    bpy.context.view_layer.update()
    if parent:
        matrix=o.matrix_world.copy();o.parent=parent;o.matrix_world=matrix
    bpy.context.view_layer.update()
    return o


def attach_new(before,parent):
    bpy.context.view_layer.update()
    for o in set(bpy.context.scene.objects)-before:
        matrix=o.matrix_world.copy();o.parent=parent;o.matrix_world=matrix
    bpy.context.view_layer.update()


base=Vector(d.arm_mount_body)
yaw=arm_empty('arm_yaw',base)
shoulder=arm_empty('arm_shoulder',base,yaw)
elbow=arm_empty('arm_elbow',base+Vector((.32,0,0)),shoulder)
wrist=arm_empty('arm_wrist',base+Vector((.62,0,0)),elbow)
for joint,start,length in ((shoulder,0,.32),(elbow,.32,.30),(wrist,.62,.12)):
    before=set(bpy.context.scene.objects);p=base+Vector((start,0,0))
    cylinder('Manipulator sealed joint',p,.040,.088,(0,1,0),m['black'])
    for side in (-1,1):
        cylinder('Joint stainless pivot',p+Vector((0,side*.046,0)),.012,.008,(0,1,0),m['metal'])
        box('Black pantograph arm plate',p+Vector((length/2,side*.036,0)),(length,.018,.038),m['black'],.008)
        # Bright hinge pins and thin parallel rods match the photographed linkage.
        rod('Pantograph tie rod',p+Vector((.035,side*.035,-.024)),p+Vector((length-.025,side*.035,-.024)),.003,m['metal'])
    cylinder('Hydraulic actuator barrel',p+Vector((length*.40,0,-.025)),.018,length*.48,(1,0,0),m['black'])
    cylinder('Actuator polished piston',p+Vector((length*.70,0,-.025)),.006,length*.25,(1,0,0),m['metal'])
    for k in range(3):
        hose('Arm hydraulic hose',[p+Vector((0,-.054-k*.005,.026)),p+Vector((length*.5,-.053-k*.005,.035)),p+Vector((length,-.052-k*.005,.025))],.002,m['rubber'])
    if joint==wrist:
        box('Thick rectangular wrist valve housing',p+Vector((.027,0,0)),(.054,.108,.082),m['black'],.006)
        cylinder('Wrist hydraulic barrel',p+Vector((.060,0,0)),.031,.020,(1,0,0),m['black'])
        ring('Wrist barrel retaining collar',p+Vector((.068,0,0)),.032,(1,0,0),m['metal'],.002)
        for dx in (.012,.042):
            for sy in (-1,1):bolt('Wrist housing cover screw',p+Vector((dx,sy*.035,-.044)),(0,0,1),.003)
    attach_new(before,joint)
before=set(bpy.context.scene.objects)
cylinder('Manipulator rotating pedestal',base+Vector((0,0,.016)),.075,.047,(0,0,1),m['black'])
ring('Pedestal steel bearing',base+Vector((0,0,-.009)),.065,(0,0,1),m['metal'],.002)
attach_new(before,yaw)
for side,label in ((-1,'left'),(1,'right')):
    jaw=arm_empty('arm_jaw_'+label,base+Vector((.695,side*.030,0)),wrist)
    before=set(bpy.context.scene.objects)
    # Hooked jaw plates instead of rectangular fingers.
    xs=(0,.032,.067,.097,.101,.074,.044,.008);ys=(0,side*.023,side*.044,side*.031,side*.012,side*.023,side*.009,side*-.012)
    vertices=[point(base+Vector((.695+x,side*.030+y,z))) for z in (-.012,.012) for x,y in zip(xs,ys)]
    n=len(xs);faces=[tuple(range(n-1,-1,-1)),tuple(range(n,2*n))]+[(i,(i+1)%n,(i+1)%n+n,i+n) for i in range(n)]
    hook=mesh_object('Hooked manipulator finger',vertices,faces,m['black']);soften(hook,.003)
    for dx in (.015,.045):bolt('Jaw pivot screw',base+Vector((.695+dx,side*.030,-.015)),(0,0,1),.004)
    attach_new(before,jaw)
tip=arm_empty('arm_tip',base+Vector((.74,0,0)),wrist)
yaw['arm_axis']='yaw';shoulder['arm_axis']='bend';elbow['arm_axis']='bend';wrist['arm_axis']='bend'
# Default parked pose follows the server's four bounded joint angles.
shoulder.rotation_euler.x=math.radians(-15);elbow.rotation_euler.x=math.radians(30);wrist.rotation_euler.x=math.radians(-15)

for key,pos in [('camera',d.camera_body),('tether',d.gland_body),('arm_mount',d.arm_mount_body)]+[(f'lamp_{i}',p) for i,p in enumerate(d.lamp_body)]:
    o=arm_empty('anchor_'+key,pos);o['anchor']=key
bpy.context.scene.unit_settings.system='METRIC'
bpy.context.scene['reference']='Official Saab Falcon 300 m + five-function manipulator skid; see source URLs in build_falcon_reference.py'
bpy.context.scene['precision']='Visible construction reconstructed from official photographs; no dimensional factory CAD supplied'
bpy.ops.wm.save_as_mainfile(filepath=str(ROOT/'cad'/'falcon.blend'))
bpy.ops.export_scene.gltf(filepath=str(ROOT/'simulator/viewer/models/falcon.glb'),export_format='GLB',export_extras=True,export_apply=True,export_yup=True,export_cameras=False,export_lights=False)
print('Reference Falcon exported:',len(bpy.context.scene.objects),'objects')
