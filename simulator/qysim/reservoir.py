"""Generic reservoir geometry and photo evidence. All dimensions are training assumptions, NED metres."""
import math
import numpy as np
from .world import Box, Cylinder, CurrentProfile
from .regional_flow import RegionalFlow

STRINGS = dict(name='水庫進水口', brief='沿護坡下潛，拍攝攔污柵堵塞，再返回碼頭。留意吸入流與沉木勾纜。',
               descend='沿護坡下潛到進水口', photo='檢查攔污柵並拍下堵塞處', home='回到碼頭')
CAMERAS = dict(embankment_overlook=dict(eye=[-16,-18,-12], target=[16,0,-1]),
               dock_equipment=dict(eye=[1,-5,-2.3], target=[5,-2,-.6]))
CAMERAS['reservoir_overlook'] = CAMERAS['embankment_overlook']
CAMERAS['reservoir_equipment'] = CAMERAS['dock_equipment']
TARGET = (19.3,0.,10.)


def layout():
    obs = []
    def box(name, c, h, kind='concrete'):
        obs.append(Box(name,c,h,0,'res_'+kind))
    def rod(name, a, b, radius, kind='steel', snag=False):
        ob = Cylinder(name,a,b,radius,'res_'+kind)
        if snag:
            ob.snag_hold = (100.,260.)
        obs.append(ob)
    for i in range(64):
        x = -16+i*.5
        depth = (x+2)*.5
        box(f'slope-{i}', (x,0,(depth+19)/2), (.25,22,(19-depth)/2))
    for y in (-3,3):
        box(f'intake-pier-{y}',(21,y,9),(2,.55,5))
        box(f'gate-slot-{y}',(20,y*.77,10),(.18,.12,3),'steel')
    box('lintel',(21,0,5),(2,3,.5))
    box('closed-gate',(22.5,0,10),(.2,2.5,4),'steel')
    for i in range(17):
        y = (i-8)*.29
        rod(f'rack-{i}',(19.8,y,6),(19.8,y,14),.065,snag=True)
    for z in (6,10,14):
        rod(f'crossbar-{z}',(19.8,-2.5,z),(19.8,2.5,z),.08)
    for i in range(7):
        rod(f'blocked-branch-{i}',(19.6,-1+i*.18,9+i*.15),(19.5,1.3-i*.12,10.6+i*.1),.07,'wood',True)
    box('trapped-bag',(19.45,.8,10.2),(.06,.24,.3),'white')
    rod('fallen-tree',(12,7,8.3),(19,10,12),.3,'wood',True)
    for i in range(4):
        rod(f'limb-{i}',(13+i,7.5+i*.4,9+i*.4),(13.5+i,5.5+i*.3,8.5+i*.5),.09,'wood',True)
    for y,color in ((-2,'orange'),(2,'blue')):
        for i in range(20):
            for j in range(1):
                box(f'float-{y}-{i}-{j}',(i*.5,y,-.15),(.245,.74,.22),color)
        for side in (-.8,.8):
            for i in range(6):
                rod(f'post-{y}-{side}-{i}',(i*1.8,y+side,-.35),(i*1.8,y+side,-1.3),.035,'white')
            rod(f'rope-{y}-{side}',(0,y+side,-1.15),(9,y+side,-1.15),.018,'white')
    box('control-case',(4,-2,-.65),(.42,.3,.28),'steel')
    box('screen',(4,-2,-.95),(.31,.22,.025),'blue')
    box('toolbox',(6,-2,-.6),(.35,.24,.22),'orange')
    for coil in range(9):
        for j in range(24):
            a,b = j*math.tau/24,(j+1)*math.tau/24
            radius = .4+coil*.012
            rod(f'cable-{coil}-{j}',(7+radius*math.cos(a),-2+radius*math.sin(a),-.4-coil*.02),
                (7+radius*math.cos(b),-2+radius*math.sin(b),-.4-coil*.02),.014,'lime')
    for y in (-5,5):
        for side in (-.75,.75):
            rod(f'pontoon-{y}-{side}',(3,y+side,0),(7,y+side,0),.35,'white')
        box(f'deck-{y}',(5,y,-.35),(2,.9,.15),'blue')
        box(f'console-{y}',(6,y,-.8),(.3,.35,.35),'white')
        if y == 5:
            box('canopy',(5,y,-2.3),(2,1.1,.07),'white')
            for x in (3.3,6.7):
                for side in (-.85,.85):
                    rod(f'canopy-post-{x}-{side}',(x,y+side,-.5),(x,y+side,-2.3),.035)
    for i in range(30):
        box(f'stair-{i}',(-12+i*.4,-7,-5.7+i*.2),(.2,1,.12),'white')
    rod('gauge',(-5,-9,1),(-5,-9,-5),.12,'white')
    for i in range(30):
        box(f'gauge-tick-{i}',(-5.13,-9,-5+i*.2),(.02,.13,.045),'orange' if i%5==0 else 'steel')
    return obs


def scenario():
    from .scenarios import Scenario, Objective
    # Sheltered relative turbulence coefficient; zero ambient speed still gives exactly zero fluctuations.
    return Scenario('reservoir_intake',STRINGS['name'],STRINGS['brief'],seabed_depth=19,
        obstacles=[o for o in layout() if o.aabb()[1][2] >= 0],current=CurrentProfile(0,0,0,0,0,0,.08),
        water='fresh',water_type='fresh_green',
        biome='reservoir',visibility_m=3,seabed_type='mud',start_pos=(3,0,1.5),spool_pos=(3,-1,-.6),
        tether_length=4,regional_flows=[RegionalFlow((19,0,10),(4,4,4),(.35,0,0))],
        objectives=[Objective('checkpoint',STRINGS['descend'],(17,0,9),1.5),
                    Objective('reservoir_photo',STRINGS['photo'],(18,0,10),1.5),
                    Objective('surface',STRINGS['home'],(3,0,.5),2)])


def photo(sim):
    if sim.scenario.key != 'reservoir_intake' or sim.scorer.current_index != 1:
        return
    from .physics import q_rot
    pos = sim.vehicle.s.pos
    delta = np.array(TARGET)-pos
    distance = np.linalg.norm(delta)
    if not .6 < distance < 2.8:
        return
    if np.dot(delta/distance,q_rot(sim.vehicle.s.q,np.array([1.,0.,0.]))) < .94:
        return
    if any(sim.world.sdf(pos+delta*t)[0] < -.01 for t in np.linspace(.05,.95,25)):
        return
    sim.scenario.objectives[1].done = True
    sim.scenario.objectives[1].progress = 1.
