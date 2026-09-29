import bpy, bmesh, sys, math
from mathutils import Vector, Matrix
S=sys.argv[-2]; ZBOT=150; BOLTS=((155,-147),(146,40),(132,222)); tops={}; bpy.ops.wm.open_mainfile(filepath=sys.argv[-1])
sc=bpy.context.scene; dg=bpy.context.evaluated_depsgraph_get()
mm=0.001
coll=bpy.data.collections.new('05 | Buoyancy Rev B (syntactic foam)'); sc.collection.children.link(coll)
coll_old=bpy.data.collections.new('98 | Replaced by Rev B - hidden'); sc.collection.children.link(coll_old)

# materials
def mat(name,rgba,rough=0.55,alpha=1.0):
    m=bpy.data.materials.get(name) or bpy.data.materials.new(name); m.use_nodes=True
    b=m.node_tree.nodes['Principled BSDF']; b.inputs['Base Color'].default_value=rgba; b.inputs['Roughness'].default_value=rough
    if alpha<1: b.inputs['Alpha'].default_value=alpha; m.blend_method='BLEND' if hasattr(m,'blend_method') else None
    m.diffuse_color=rgba; return m
m_foam=mat('20 | Syntactic foam, yellow polyurea skin',(0.95,0.72,0.05,1),0.6)
m_ins=mat('21 | Insert 316 stainless',(0.7,0.7,0.72,1),0.3); m_ins.node_tree.nodes['Principled BSDF'].inputs['Metallic'].default_value=1
m_house=mat('22 | Reference housing (translucent)',(0.4,0.7,0.9,1),0.2,0.35)

def link(o,c=coll):
    for c0 in o.users_collection: c0.objects.unlink(o)
    c.objects.link(o)
def box(name,mn,mx):
    me=bpy.data.meshes.new(name); bm=bmesh.new()
    bmesh.ops.create_cube(bm,size=1.0)
    for v in bm.verts: v.co=Vector([ (mn[i]+mx[i])/2*mm + v.co[i]*(mx[i]-mn[i])*mm for i in range(3)])
    bm.to_mesh(me); bm.free(); o=bpy.data.objects.new(name,me); sc.collection.objects.link(o); return o
def cyl(name,r,depth,loc,direction=(0,0,1),seg=48):
    me=bpy.data.meshes.new(name); bm=bmesh.new()
    bmesh.ops.create_cone(bm,cap_ends=True,segments=seg,radius1=r*mm,radius2=r*mm,depth=depth*mm)
    rot=Vector((0,0,1)).rotation_difference(Vector(direction).normalized()).to_matrix().to_4x4()
    bm.transform(Matrix.Translation(Vector(loc)*mm)@rot); bm.to_mesh(me); bm.free()
    o=bpy.data.objects.new(name,me); sc.collection.objects.link(o); return o
def boolean(target,cutter,op):
    md=target.modifiers.new('b','BOOLEAN'); md.operation=op; md.solver='EXACT'; md.object=cutter
    bpy.context.view_layer.objects.active=target
    with bpy.context.temp_override(object=target,active_object=target): bpy.ops.object.modifier_apply(modifier=md.name)
    bpy.data.objects.remove(cutter)
def volume(o):
    bm=bmesh.new(); bm.from_mesh(o.data); bm.transform(o.matrix_world)
    v=bm.calc_volume(); 
    # centroid via tetra decomposition
    bmesh.ops.triangulate(bm,faces=bm.faces); c=Vector(); V=0
    for f in bm.faces:
        a,b,d=[x.co for x in f.verts]; dv=a.dot(b.cross(d))/6; V+=dv; c+=dv*(a+b+d)/4
    bm.free(); return abs(v)*1e3, (c/V)*1000

# 1. outer shell = hull surface pushed out 2 mm (coating proud of graphite envelope)
hull=bpy.data.objects['Hull | continuous molded graphite envelope']
me=bpy.data.meshes.new_from_object(hull.evaluated_get(dg))
bm=bmesh.new(); bm.from_mesh(me); bm.normal_update()
for v in bm.verts: v.co+=v.normal*(2*mm/ max(hull.matrix_world.to_scale()))
bm.to_mesh(me); bm.free()
results={}
for side,sg in (('PORT',-1),('STBD',1)):
    o=bpy.data.objects.new(f'BUOY {side} | syntactic foam block',me.copy()); o.matrix_world=hull.matrix_world.copy(); sc.collection.objects.link(o)
    x0,x1=(82,200)
    boolean(o,box('reg',(min(sg*x0,sg*x1),-262,ZBOT),(max(sg*x0,sg*x1),318,345)),'INTERSECT')
    # thruster clearance: cylinder along each thruster axis, nozzle hoop r~72 + 12 clearance
    for t in ('FRONT','AFT','LONG'):
        th=bpy.data.objects[f'THRUSTER {side}_{t} | fixed assembly']; ax=(th.matrix_world.to_3x3()@Vector((0,0,1))).normalized()
        c=th.matrix_world.translation*1000
        boolean(o,cyl('clr',86,260,c,ax),'DIFFERENCE')
    # clearance for the vertical chassis mounts / fixings under the blocks
    for yc in (-180,182):
        boolean(o,box('chassis',(min(sg*105,sg*145),yc-25,60),(max(sg*105,sg*145),yc+25,190)),'DIFFERENCE')
    # through-bolt holes M8 (dia 9) + counterbore dia 18 x 14 deep from the local top surface
    inv=o.matrix_world.inverted(); tops[side]=[]
    for (xb,yb) in BOLTS:
        hit,loc,*_=o.ray_cast(inv@(Vector((sg*xb,yb,600))*mm),(inv.to_3x3()@Vector((0,0,-1))).normalized())
        zt=(o.matrix_world@loc).z*1000 if hit else 330
        tops[side].append(zt)
        boolean(o,cyl('hole',6.1,400,(sg*xb,yb,250)),'DIFFERENCE')
        boolean(o,cyl('cb',9,60,(sg*xb,yb,zt-14+30)),'DIFFERENCE')
    # cable raceway on inboard face (14 x 14 mm) along Y
    boolean(o,box('groove',(min(sg*82,sg*96),-270,205),(max(sg*82,sg*96),330,219)),'DIFFERENCE')
    # two trim pockets on underside (60 x 44 x 25) for trim foam / lead shot
    for yc in (-110,90):
        boolean(o,box('pocket',(min(sg*108,sg*152),yc-30,ZBOT-10),(max(sg*108,sg*152),yc+30,ZBOT+25)),'DIFFERENCE')
    o.data.materials.clear(); o.data.materials.append(m_foam)
    for p in o.data.polygons: p.use_smooth=False
    wn=o.modifiers.new('WN','WEIGHTED_NORMAL'); wn.keep_sharp=True
    link(o); results[side]=volume(o)
    # stainless inserts (sleeves) in holes
    for i,(xb,yb) in enumerate(BOLTS):
        zt=tops[side][i]-14; zb=ZBOT
        s=cyl(f'BUOY {side} | 316 sleeve insert M8 .{i:03d}',6,zt-zb,(sg*xb,yb,(zt+zb)/2)); s.data.materials.append(m_ins); link(s)
# reference pressure housing (6" class, dia 150 x 540)
h=cyl('REF | electronics housing dia150 x 540 (assumed)',75,540,(0,-10,252),(0,1,0),64); h.data.materials.append(m_house); link(h)
# retire old yellow fairing skins
for n in ('Port | yellow buoyancy fairing','Starboard | yellow buoyancy fairing'):
    o=bpy.data.objects[n]; link(o,coll_old)
coll_old.hide_render=True; bpy.context.view_layer.layer_collection.children[coll_old.name].hide_viewport=True
bpy.data.meshes.remove(me)
# notes
tot=sum(v for v,_ in results.values())
txt=bpy.data.texts.new('READ ME | Buoyancy Rev B')
lines=["Buoyancy Rev B - syntactic foam shoulder blocks (port/stbd)",
 "Material: syntactic foam, design density 0.40 g/cc (verify supplier datasheet, rated >= 1.2x working depth)",
 "Skin: 1-2 mm yellow polyurea/epoxy coating. Fasteners: M8 316 through-bolts in 316 sleeves.",
 f"Volume PORT {results['PORT'][0]:.2f} L, STBD {results['STBD'][0]:.2f} L, total {tot:.2f} L",
 f"Centroid PORT {[round(x) for x in results['PORT'][1]]} mm, STBD {[round(x) for x in results['STBD'][1]]} mm",
 f"Net lift in seawater (1.025): {tot*(1.025-0.40):.2f} kgf ; foam mass {tot*0.40:.2f} kg",
 "Inboard face x=+-82 mm leaves 7 mm clearance to an assumed dia150 electronics housing (REF object).",
 "Thruster clearance: dia172 mm cylinders along each thruster axis. Trim pockets 60x40x25 underside, 2 per block.",
 "Old yellow fairing skins moved to collection 98 (hidden)."]
txt.write("\n".join(lines))
print("\n".join(lines))
for side in ('PORT','STBD'):
    o=bpy.data.objects[f'BUOY {side} | syntactic foam block']
    print(side,'dims mm',[round(d*1000) for d in o.dimensions],'verts',len(o.data.vertices), 'manifold', all(e.is_manifold for e in bmesh.from_edit_mesh(o.data).edges) if False else '')
bpy.ops.wm.save_as_mainfile(filepath=f"{S}/X1-buoyancy-revB.blend",compress=True)
# STL export per block
for side in ('PORT','STBD'):
    o=bpy.data.objects[f'BUOY {side} | syntactic foam block']
    for x in bpy.context.view_layer.objects: x.select_set(False)
    o.select_set(True); bpy.context.view_layer.objects.active=o
    bpy.ops.wm.stl_export(filepath=f"{S}/buoy_{side.lower()}_revB.stl",export_selected_objects=True,global_scale=1000.0,apply_modifiers=True)
