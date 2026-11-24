"""Build an original primitive-only frame; preserve source FRD thruster tuples."""
import ast
import json
from pathlib import Path
import xml.etree.ElementTree as E
import numpy as np

ROOT = Path(__file__).resolve().parent
SOURCE = Path('/workspace/rov_sim/box_run/rov01sim/vehicles.py')
CYAN = '0.0235294118 0.7137254902 0.8313725490 1'
GRAY = '0.1176470588 0.1607843137 0.2313725490 1'

def build():
    tree = ast.parse(SOURCE.read_text())
    thrusters = next(ast.literal_eval(n.value) for n in tree.body if isinstance(n, ast.Assign)
                     and any(isinstance(t, ast.Name) and t.id == 'ROV01_THRUSTERS' for t in n.targets))
    root = E.Element('mujoco', model='ROV-01 original open frame')
    def add(parent, tag, **kw):
        return E.SubElement(parent, tag, {k: str(v) for k, v in kw.items()})
    def vec(x): return ' '.join(format(float(v), '.10g') for v in x)
    add(root, 'compiler', angle='radian')
    add(root, 'option', timestep='.005', gravity='0 0 -9.81', integrator='implicitfast')
    vis = add(root, 'visual')
    add(vis, 'global', offwidth='960', offheight='640')
    add(vis, 'headlight', ambient='.4 .4 .4', diffuse='.7 .7 .7', specular='.1 .1 .1')
    add(vis, 'rgba', haze=GRAY)
    world = add(root, 'worldbody')
    add(world, 'light', pos='0 -4 10', dir='0 0 -1', directional='true')
    add(world, 'geom', name='seabed', type='plane', size='50 30 .1', rgba=GRAY)
    add(world, 'geom', name='inspection_cable', type='cylinder', fromto='-8 0 .035 30 0 .035', size='.025', rgba=CYAN)
    # Seabed scale marks use only the same two requested colors.
    for x in range(-6, 31, 2):
        add(world, 'geom', type='capsule', fromto=f'{x} -2 .008 {x} 2 .008', size='.006', rgba=CYAN, contype='0', conaffinity='0')
    add(world, 'site', name='surface_anchor', pos='9 0 10', size='.09', rgba=CYAN)
    rov = add(world, 'body', name='rov', pos='0 0 1.06', quat='0 1 0 0')
    add(rov, 'freejoint', name='rov_free')
    add(rov, 'inertial', pos='0 0 0', mass='12', diaginertia='.38 .65 .72')
    # Local z points down (FRD); float blocks and buoyancy center lie at negative z.
    for z in [-.22, .22]:
        for y in [-.34, .34]:
            add(rov, 'geom', type='capsule', fromto=vec([-.49,y,z,.49,y,z]), size='.024', rgba=GRAY)
        for x in [-.49,.49]:
            add(rov, 'geom', type='capsule', fromto=vec([x,-.34,z,x,.34,z]), size='.024', rgba=GRAY)
    for x in [-.49,.49]:
        for y in [-.34,.34]:
            add(rov, 'geom', type='capsule', fromto=vec([x,y,-.22,x,y,.22]), size='.024', rgba=CYAN)
    for y in [-.27,.27]:
        add(rov, 'geom', type='box', pos=vec([0,y,-.25]), size='.39 .095 .065', rgba=CYAN)
    add(rov, 'geom', type='cylinder', fromto='-.28 0 0 .28 0 0', size='.075', rgba=GRAY)
    add(rov, 'site', name='buoyancy_center', pos='0 0 -.085', size='.008', rgba=CYAN)
    add(rov, 'site', name='tether_attach', pos='-.20 0 -.22', size='.025', rgba=CYAN)
    act = add(root, 'actuator')
    for name, p, axis in thrusters:
        label=name.split()[0]
        add(rov,'site',name=label,pos=vec(p),size='.014',rgba=CYAN)
        # Site axes remain FRD: no site rotation, no normalization of source gear.
        add(act,'motor',name=label,site=label,gear=vec([*axis,0,0,0]),ctrllimited='true',ctrlrange='-45 45')
        p=np.array(p); d=np.array(axis); d=d/np.linalg.norm(d)
        add(rov,'geom',name=label+'_housing',type='cylinder',fromto=vec([*(p-.08*d),*(p+.08*d)]),size='.067',rgba=GRAY)
        add(rov,'geom',name=label+'_rotor',type='cylinder',fromto=vec([*(p+.081*d),*(p+.085*d)]),size='.048',rgba=CYAN)
    tendon=add(root,'tendon')
    rope=add(tendon,'spatial',name='umbilical',width='.009',rgba=GRAY,stiffness='3',damping='1.5',springlength='0 11')
    add(rope,'site',site='surface_anchor'); add(rope,'site',site='tether_attach')
    E.indent(root)
    E.ElementTree(root).write(ROOT/'rov01.xml',encoding='unicode',xml_declaration=True)
    (ROOT/'thruster_geometry.json').write_text(json.dumps({'source':str(SOURCE),'frame':'FRD','thrusters':thrusters},indent=2)+'\n')

if __name__ == '__main__': build()
