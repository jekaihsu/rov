"""Shared, abstract cooperative maintenance exhibit; not a field repair procedure."""
from copy import deepcopy
import time
import numpy as np

ROLES={'survey':'巡檢員','service':'維護員','verify':'復檢員'}
STAGES=[('survey','確認展示損傷',5.),('service','整理展示工作區',5.),
        ('service','安裝展示保護套',8.),('verify','完成復檢紀錄',5.)]

def ensure_repair(sim):
    config=(getattr(sim.scenario, 'inspection_site', None) or {}).get('repair')
    if not config:return None
    if not hasattr(sim.world,'repair_run'):sim.world.repair_run=RepairRun(config)
    return sim.world.repair_run

class RepairRun:
    def __init__(self,config):
        self.config=deepcopy(config);self.roles={};self.assisting=set();self.phase=0
        self.progress=0.;self.active=None;self.records=[];self.message='選擇分工，前往展示工作區'
        self.completed=False
        self.last_wall=None

    def advance(self,dt,vehicles):
        # Exhibit task timing follows elapsed time even if expensive physics
        # frames run slowly. A paused/disconnected interval cannot skip a task.
        now=time.monotonic();elapsed=dt if self.last_wall is None else min(.1,max(0.,now-self.last_wall))
        self.last_wall=now;self.step(elapsed,vehicles)

    def connected(self,sim):
        room=getattr(sim,'room',None)
        if room:return {p.vehicle_id for p in room.players.values() if p.connected}
        return {sim.vehicle_id}

    def command(self,sim,msg):
        verb=msg.get('verb');vid=sim.vehicle_id;connected=self.connected(sim)
        if verb=='role':
            role=msg.get('role')
            if role not in ROLES:raise ValueError('未知維修分工')
            occupied=self.roles.get(role)
            if occupied and occupied!=vid and occupied in connected:raise ValueError('這個分工已有其他玩家')
            if self.active==vid:raise ValueError('請先暫停工作再切換分工')
            self.roles={r:v for r,v in self.roles.items() if v!=vid};self.roles[role]=vid
            self.message=f'{ROLES[role]}已就位'
        elif verb=='assist':
            if vid in self.assisting:self.assisting.remove(vid)
            else:self.assisting.add(vid)
        elif verb=='stop':
            if self.active==vid:self.active=None;self.message='工作已暫停，進度保留'
        elif verb=='start':
            if self.completed:raise ValueError('此輪維修展示已完成')
            if self.active and self.active!=vid:raise ValueError('隊友正在執行此工作')
            role,label,_=STAGES[self.phase]
            if self.roles.get(role)!=vid:raise ValueError(f'此工作需要{ROLES[role]}')
            if not self.near(sim):raise ValueError('請先進入畫面標示的展示工作區')
            self.active=vid;self.message=label
        else:raise ValueError('未知維修操作')
        return dict(ok=True,action='repair',repair=self.state(sim))

    def near(self,sim):
        return float(np.linalg.norm(sim.vehicle.s.pos-np.array(self.config['point'])))<self.config['radius']

    def step(self,dt,vehicles):
        if self.completed or self.active is None:return
        sim=vehicles.get(self.active)
        if sim is None:self.active=None;return
        connected=self.connected(sim)
        if self.active not in connected:self.active=None;self.message='操作者離線，等待接手';return
        if not self.near(sim):self.message='離開工作區，進度暫停';return
        helpers=[v for v in self.assisting if v!=self.active and v in connected and v in vehicles and self.near(vehicles[v])]
        if self.phase==2 and len(connected)>1 and not helpers:
            self.message='等待另一位隊友在工作區按下支援照明';return
        role,label,duration=STAGES[self.phase];self.message=label
        self.progress=min(1.,self.progress+dt/duration)
        if self.progress>=1.:
            self.records.append(dict(stage=self.phase,label=label,operator=self.active,helpers=helpers,t=round(sim.t,2)))
            self.phase+=1;self.active=None;self.progress=0.
            self.completed=self.phase==len(STAGES)
            self.message='維修展示完成：保護套與復檢紀錄已同步' if self.completed else '上一項已完成，請下一位分工接手'

    def state(self,sim):
        return dict(phase=self.phase,progress=round(self.progress,3),active=self.active,roles=dict(self.roles),
                    assisting=sorted(self.assisting),completed=self.completed,message=self.message,
                    stages=[dict(role=r,label=l) for r,l,_ in STAGES],point=self.config['point'],
                    radius=self.config['radius'],near=self.near(sim),records=deepcopy(self.records),
                    mode='cooperative' if len(self.connected(sim))>1 else 'solo_demo',abstract_demo=True)
