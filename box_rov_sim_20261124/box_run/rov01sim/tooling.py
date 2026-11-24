"""Authoritative civilian payloads, shared measurements and coupled instruments.

Hydraulics/electrical/thermal coefficients are educational estimates. No real
vehicle commands are emitted. Geometry measurements use the simulated world.
"""
from copy import deepcopy
import json
import math
from pathlib import Path
import numpy as np
from .physics import G, RHO, q_rot, q_conj

CATALOGUE = json.loads((Path(__file__).resolve().parents[1]/'viewer/tool_catalogue.json').read_text(encoding='utf8'))
TOOLS = {t['id']: t for t in CATALOGUE['tools']}

def validate_loadout(model, value):
    vehicle = CATALOGUE['vehicles'][model]
    if not isinstance(value, list) or len(value)>len(vehicle['mounts']):
        raise ValueError('裝備配置格式或數量無效')
    mounts={m['id']:m for m in vehicle['mounts']}
    used=set(); ids=set(); result=[]; mass=power=0.
    for item in value:
        if not isinstance(item,dict): raise ValueError('裝備項目無效')
        slot,tid=item.get('slot'),item.get('tool')
        if not isinstance(slot,str) or not isinstance(tid,str) or slot not in mounts or tid not in TOOLS:
            raise ValueError('未知工具或掛點')
        t,m=TOOLS[tid],mounts[slot]
        if slot in used or tid in ids: raise ValueError('工具或掛點重複')
        if model not in t['models'] or m['kind']!=t['slot_kind']: raise ValueError('工具與機型或掛點不相容')
        if t['mass_kg']>m['max_mass_kg']: raise ValueError('掛點超過負載限制')
        mass+=t['mass_kg'];power+=t['power_w'];used.add(slot);ids.add(tid)
        result.append({'slot':slot,'tool':tid})
    if mass>vehicle['payload_kg']: raise ValueError('總搭載重量超過模擬配置限制')
    if power>vehicle['power_budget_w']: raise ValueError('工具功率超過供電預算')
    if any(dep not in ids for tid in ids for dep in TOOLS[tid]['requires']): raise ValueError('液壓機械臂需要液壓動力組')
    return result

def number(v,low,high):
    if isinstance(v,bool) or not isinstance(v,(float,int)) or not math.isfinite(v): raise ValueError('工具參數必須為有限數字')
    return min(high,max(low,float(v)))

class ToolSystem:
    def __init__(self,sim,loadout=None):
        self.sim=sim; self.model=sim.model_id; self.profile=CATALOGUE['vehicles'][self.model]
        self.mounts={m['id']:m for m in self.profile['mounts']}
        self.launched=False; self.pressure=0.; self.flow=0.; self.oil_temp=24.; self.internal_temp=25.
        self.motor_temp=np.full(len(sim.vehicle.thrusters),24.); self.elapsed=0.; self.next_measurement=0.
        self.energy_wh=0.; self.pump=False; self.counter=0; self.records=[]; self.systems={}; self.last_motion=0.
        v=sim.vehicle
        self.base=dict(mass=v.p.mass,net=v.p.net_buoyancy,I=v.I.copy(),M=v.M.copy(),drag=v.quad_drag.copy())
        self.install(self.profile['default_loadout'] if loadout is None else loadout)

    def install(self,loadout):
        if self.launched: raise ValueError('請返回準備區後換裝')
        checked=validate_loadout(self.model,loadout)
        if hasattr(self.sim,'operations'): self.sim.operations.release()
        self.loadout=checked
        self.states={x['tool']:dict(enabled=x['tool'] not in ('hydraulic_arm','gripper','sediment','water','hpu'),level=.7,zoom=1.,progress=0.,reading=None,unit=TOOLS[x['tool']]['unit'],valid=False,status='待機',estimated=True) for x in checked}
        self.pump=False;self.pressure=self.flow=0.; self.next_measurement=0.
        baseids={x['tool'] for x in self.profile['default_loadout']}
        ids=set(self.states)
        delta=sum(TOOLS[i]['mass_kg'] for i in ids)-sum(TOOLS[i]['mass_kg'] for i in baseids)
        wet=sum(TOOLS[i]['submerged_mass_kg'] for i in ids)-sum(TOOLS[i]['submerged_mass_kg'] for i in baseids)
        v=self.sim.vehicle;v.p.mass=self.base['mass']+delta;v.p.net_buoyancy=self.base['net']-wet*G
        v.M=self.base['M']+delta;v._inv_mass=1/v.M
        moment=np.zeros(3); inertia=np.zeros(3)
        for sign,items in [(1,checked),(-1,self.profile['default_loadout'])]:
            for item in items:
                r=np.array(self.mounts[item['slot']]['position']);t=TOOLS[item['tool']]
                moment+=sign*r*t['submerged_mass_kg'];inertia+=sign*t['mass_kg']*(np.dot(r,r)-r*r)
        self.offset_moment=moment
        v.I=np.maximum(.15,self.base['I']+inertia);v._inv_inertia=1/v.I
        v.quad_drag=self.base['drag']*(1+max(0,delta)*.025)
        self.total_mass=sum(TOOLS[i]['mass_kg'] for i in ids)
        self.cg=(moment/max(1,v.p.mass)).tolist()
        self.collision_spheres=[]
        for item in checked:
            if item['tool'] in ('hydraulic_arm','gripper','sediment'):continue
            t=TOOLS[item['tool']];length,width,height=t['dimensions_m'];r=max(width,height)/2
            origin=self.pose(item['tool'])
            axis=np.array([0.,0.,1.]) if item['tool'] in ('altimeter','ins') else np.array([1.,0.,0.])
            for fraction in (.25,.75):self.collision_spheres.append((origin+axis*length*fraction,min(.20,max(.015,r))))

    def pose(self,tid):
        item=next(x for x in self.loadout if x['tool']==tid)
        return np.array(self.mounts[item['slot']]['position'],float)

    def halt(self):
        self.pump=False
        self.flow=0.
        # Keep the published snapshot consistent even when a safety trip occurs
        # after step() built it. Residual pressure still decays in the integrator.
        hydraulic=self.systems.get('hydraulic')
        if hydraulic is not None:
            hydraulic.update(pump=False,flow_lpm=0.,return_bar=0.,
                             differential_bar=round(self.pressure,2))
        for tid in ('hpu','hydraulic_arm','gripper','water','sediment'):
            if tid in self.states:self.states[tid]['enabled']=False

    def command(self,msg):
        action=msg.get('action')
        if action=='loadout_set':
            self.install(msg.get('loadout'));return dict(ok=True,action=action,loadout=self.loadout)
        tid=msg.get('tool')
        if tid not in self.states:raise ValueError('尚未安裝此工具')
        s=self.states[tid];verb=msg.get('verb','toggle')
        if verb=='toggle':
            s['enabled']=not s['enabled']
            if tid=='hpu':self.pump=s['enabled']
        elif verb=='level':s['level']=number(msg.get('value'),0,1)
        elif verb=='zoom':s['zoom']=number(msg.get('value'),1,5)
        elif verb=='arm':
            if tid!='hydraulic_arm' or not self.pump:raise ValueError('請先啟動液壓泵浦')
            r=self.sim.operations.command(dict(action='arm',joints=msg.get('joints'),grip=msg.get('grip',1),from_tool=True))
            if not r.get('ok'):raise ValueError(r.get('message','關節指令無效'))
            s['enabled']=True
        elif verb=='grip':
            if tid not in ('gripper','sediment','hydraulic_arm'):raise ValueError('此工具沒有夾爪')
            if tid=='hydraulic_arm' and not self.pump:raise ValueError('請先啟動液壓泵浦')
            self.sim.operations.grip_target=number(msg.get('value'),0,1);s['enabled']=True
        elif verb=='sample':
            if tid not in ('water','sediment'):raise ValueError('此工具不支援採樣')
            if s['progress']>=1:raise ValueError('採樣容器已滿，請返航更換')
            s['enabled']=True
            if tid=='sediment':self.sim.operations.grip_target=0.
        elif verb=='record':
            if not s['valid']:raise ValueError('尚未取得有效讀值')
            return dict(ok=True,action=action,record=self.record(tid))
        else:raise ValueError('未知工具操作')
        return dict(ok=True,action=action,tool=tid)

    def record(self,tid):
        sim=self.sim
        if not hasattr(sim.world,'tool_records'):sim.world.tool_records=[]
        self.counter+=1
        rec=dict(id=f'{sim.vehicle_id}-{int(sim.t*1000)}-{self.counter}',tool=tid,product=TOOLS[tid]['product'],vehicle_id=sim.vehicle_id,
                 t=round(sim.t,3),position=sim.vehicle.s.pos.tolist(),reading=deepcopy(self.states[tid]['reading']),unit=TOOLS[tid]['unit'],estimated=True,
                 data={k:deepcopy(self.states[tid][k]) for k in ('points','scan','bottom_lock','ranges') if k in self.states[tid]})
        sim.world.tool_records.append(rec);sim.world.tool_records=sim.world.tool_records[-200:]
        self.records.append(rec);self.records=self.records[-100:]
        return rec

    def measure(self):
        sim=self.sim;v=sim.vehicle;p=v.s.pos; q=v.s.q
        alt=max(0.,sim.world.depth_at(p)-p[2]); temp=26-.15*p[2]
        wave=math.sin(p[0]*.023+float(sim.scenario.seed or 0)*.01)*math.cos(p[1]*.03)
        for tid,s in self.states.items():
            if not s['enabled'] and tid not in ('water','sediment','hpu','gripper','hydraulic_arm'):
                s.update(valid=False,status='關閉',reading=None);continue
            s.update(valid=True,status='運作中' if s['enabled'] else '待機')
            if tid in ('camera','zoom'):s['reading']=sim.camera.counter-1 if tid=='camera' else s['zoom']
            elif tid=='light':s['reading']=round(100*s['level'])
            elif tid=='altimeter':s['reading']=round(sim.world.raycast(p+q_rot(q,self.pose(tid)),q_rot(q,np.array([0.,0.,1.])),50.),3)
            elif tid=='dvl':s.update(reading=[round(float(x),3) for x in v.world_velocity()],bottom_lock=bool(alt<50),valid=bool(alt<50),status='底部鎖定' if alt<50 else '失去底部鎖定')
            elif tid=='usbl':s['reading']=[round(float(x),2) for x in p-np.array(sim.scenario.spool_pos)]
            elif tid=='ins':s['reading']=[round(math.degrees(x),2) for x in v.euler]
            elif tid=='ctd':s['reading']=[round(temp,2),round(34.5+.25*wave,3),round(float(p[2]),3)]
            elif tid=='turbidity':s['reading']=round(max(0.,1.5+.4*wave+sim.world.silt_at(p)*35),2)
            elif tid=='oxygen':s['reading']=round(7.7-.03*p[2]+.2*wave,3)
            elif tid=='ph':s['reading']=round(8.05+.035*wave-.0008*p[2],3)
            elif tid=='chlorophyll':s['reading']=round(max(.01,2.1*math.exp(-p[2]/25)+.2*wave),3)
            elif tid=='current':s['reading']=[round(float(x),3) for x in v.current_ned]
            elif tid in ('ping360','oculus','scanner'):
                origin=p+q_rot(q,self.pose(tid));width=math.pi*2 if tid=='ping360' else math.radians(120 if tid=='oculus' else 65)
                scan=[]
                for a in np.linspace(-width/2,width/2,24):
                    direction=q_rot(q,np.array([math.cos(a),math.sin(a),.06 if tid=='scanner' else 0.]))
                    limit=8 if tid=='scanner' else 30
                    distance=sim.world.raycast(origin,direction,limit,step=.12)
                    scan.append([round(float(a),4),round(float(distance),3)])
                s['scan']=scan;s['reading']=len([x for x in scan if x[1]<8]) if tid=='scanner' else round(min(x[1] for x in scan),2)
                if tid=='scanner':s['points']=[(origin+q_rot(q,np.array([math.cos(a),math.sin(a),.06]))*d).round(3).tolist() for a,d in scan if d<8]
            elif tid in ('ut','cp','stereo','laser'):
                origin=p+q_rot(q,self.pose(tid));direction=q_rot(q,np.array([1.,0.,0.]))
                distance=sim.world.raycast(origin,direction,12,step=.025)
                _,_,entity=sim.world.sdf(origin+direction*distance)
                site=getattr(sim.world,'inspection_site',None) or {}
                geometry=site.get('geometry',[])
                is_metal=entity=='tool_calibration_steel' or any(g.get('name')==entity and g.get('material')=='steel' for g in geometry)
                valid=distance<10 if tid in ('stereo','laser') else distance<.18 and is_metal
                val=distance if tid=='stereo' else .10 if tid=='laser' else 12.+wave if tid=='ut' else -850+12*wave
                s.update(reading=round(float(val),3) if valid else None,valid=valid,distance_m=round(distance,3),status='有效量測' if valid else '請對準目標' if tid in ('stereo','laser') else '探頭未接觸金屬試片')
                if tid=='laser':
                    points=[];ranges=[]
                    for lateral in (-.05,.05):
                        start=origin+q_rot(q,np.array([0.,lateral,0.]))
                        d=sim.world.raycast(start,direction,12,step=.025);ranges.append(round(d,3))
                        if d<12:points.append((start+direction*d).round(4).tolist())
                    s.update(points=points,ranges=ranges,valid=len(points)==2,reading=round(float(np.linalg.norm(np.array(points[0])-points[1])),4) if len(points)==2 else None)
                if tid=='stereo':
                    points=[]
                    for yaw in (-.14,0.,.14):
                        for pitch in (-.1,0.,.1):
                            ray=np.array([1.,yaw,pitch]);ray/=np.linalg.norm(ray);ray=q_rot(q,ray)
                            d=sim.world.raycast(origin,ray,12,step=.08)
                            if d<12:points.append((origin+ray*d).round(3).tolist())
                    s['points']=points
            elif tid=='water':s['reading']=round(s['progress']*100,1)
            elif tid=='sediment':s['reading']=round(s['progress']*300,1)
            elif tid=='gripper':s['reading']=round(self.sim.operations.grip*100,1)
            elif tid=='hydraulic_arm':s['reading']=self.sim.operations.joints.round(2).tolist()
            elif tid=='hpu':s['reading']=round(self.pressure,2)
            if tid in ('water','sediment'):
                if s['progress']>=1:s['status']='採樣完成'
                elif s['enabled']:
                    pos=p+q_rot(q,self.pose(tid))
                    allowed=sim.depth>.5 if tid=='water' else abs(sim.world.depth_at(pos)-pos[2])<.40
                    s['status']='採樣中' if allowed else '請潛入水中' if tid=='water' else '請接近海床'

    def step(self,dt):
        sim=self.sim;v=sim.vehicle
        self.elapsed+=dt
        if sim.rc.rc_lock==0:self.launched=True
        if sim.tether.broken:self.halt()
        if self.oil_temp>60:self.halt()
        o=sim.operations
        demand=min(1.,float(np.linalg.norm(o.target-o.joints))/20+abs(o.grip_target-o.grip)) if 'hydraulic_arm' in self.states else 0.
        held=next((ob for ob in getattr(sim.world,'work_objects',{}).values() if ob.get('id')==o.held),None)
        load=min(1.,(float(held['mass'])/10 if held else 0.)+.3*demand)
        target_p=(12+52*load+12*demand) if self.pump else 0.
        self.pressure+=(target_p-self.pressure)*(1-math.exp(-dt/.35))
        self.flow=((.08+1.3*demand) if self.pump else 0.)
        hydraulic_w=(25+self.pressure*self.flow/600*1000/.68) if self.pump else 0.
        temp=26-.15*sim.depth
        self.oil_temp+=dt*(hydraulic_w*.12-2.5*(self.oil_temp-temp))/550
        tools_w=sum(t['power_w']*(self.states[tid]['level'] if tid=='light' else 1.) for tid,t in TOOLS.items() if tid in self.states and self.states[tid]['enabled'] and tid!='hpu')+hydraulic_w
        thrust=np.abs(v.s.thrust)/v.p.thruster_max
        motor_w=18+220*thrust**1.5
        self.motor_temp+=dt*(motor_w*.15-3*(self.motor_temp-temp))/300
        total=35+float(sum(motor_w))+tools_w
        nominal=self.profile['voltage_v'];voltage=nominal*(.92+.08*sim.battery/100) if self.profile['source']=='battery' else nominal
        self.energy_wh+=total*dt/3600
        if self.profile['source']=='battery':sim.battery=max(0.,100*(1-self.energy_wh/self.profile['battery_wh']))
        self.internal_temp+=dt*(total*.025-2*(self.internal_temp-temp))/800
        self.systems=dict(electrical=dict(source=self.profile['source'],voltage_v=round(voltage,2),current_a=round(total/voltage,2),power_w=round(total,1),tool_power_w=round(tools_w,1),energy_wh=round(self.energy_wh,3),battery_pct=round(sim.battery,2) if self.profile['source']=='battery' else None,remaining_min=round(max(0,self.profile['battery_wh']-self.energy_wh)/total*60,1) if self.profile['source']=='battery' else None),
            hydraulic=dict(available='hpu' in self.states,pump=self.pump,supply_bar=round(self.pressure,2),return_bar=round(self.flow*.8,2),differential_bar=round(max(0,self.pressure-self.flow*.8),2),flow_lpm=round(self.flow,3),oil_c=round(self.oil_temp,2),reservoir_pct=round(94-4*o.grip,1),filter_dp_bar=round(.18*self.flow,3),load_pct=round(load*100,1)),
            hull=dict(temperature_c=round(self.internal_temp,2),leak=False),
            environment=dict(water_c=round(temp,2),ambient_bar_abs=round(1.01325+RHO*G*max(0,sim.depth)/1e5,3),altitude_m=round(max(0,sim.world.depth_at(v.s.pos)-sim.depth),3)),
            motors=[dict(current_a=round(float(w)/voltage,2),rpm=round(float(t)*3600),temperature_c=round(float(c),2)) for t,w,c in zip(thrust,motor_w,self.motor_temp)],
            payload=dict(mass_kg=round(self.total_mass,3),cg_offset_m=self.cg),estimated=True,alarms=[])
        alarms=self.systems['alarms']
        if self.oil_temp>60:alarms.append('液壓油溫過高');self.halt()
        if self.internal_temp>65:alarms.append('艙內溫度過高')
        if sim.depth>300:alarms.append('超過模擬耐壓限制')
        if sim.battery<15 and self.profile['source']=='battery':alarms.append('電量不足')
        if sim.battery<=0 and self.profile['source']=='battery':sim.rc_physical.rc_lock=sim.rc_sdk.rc_lock=1;self.halt()
        for tid in ('water','sediment'):
            s=self.states.get(tid)
            if not s or not s['enabled'] or s['progress']>=1:continue
            pos=v.s.pos+q_rot(v.s.q,self.pose(tid))
            allowed=tid=='water' and sim.depth>.5 or tid=='sediment' and abs(sim.world.depth_at(pos)-pos[2])<.40
            if allowed:
                s['progress']=min(1.,s['progress']+dt/4)
                if s['progress']>=1:
                    self.measure();self.record(tid);s['enabled']=False;s['status']='採樣完成'
            else:s['status']='請接近海床' if tid=='sediment' else '請潛入水中'
        if self.elapsed>=self.next_measurement:
            self.measure();self.next_measurement=self.elapsed+.5
        # Offset submerged payloads create a body moment; mass/inertia are updated at installation.
        return np.r_[np.zeros(3),np.cross(self.offset_moment,q_rot(q_conj(v.s.q),np.array([0.,0.,G])))]

    def state(self):
        return dict(loadout=deepcopy(self.loadout),tool_states=deepcopy(self.states),systems=deepcopy(self.systems),tool_records=deepcopy(getattr(self.sim.world,'tool_records',[])))
