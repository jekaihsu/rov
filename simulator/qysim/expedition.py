"""Persistent shared expedition contracts and validated observation records.

All positions are NED. Photo admission checks geometry, not image recognition.
Physics and the real manipulator remain authoritative for engineering tasks.
"""
import math
import secrets
from datetime import datetime, timezone
import numpy as np
from .physics import q_rot, q_conj

SCENES = {'coral_reef', 'seagrass_meadow', 'harbor_inspection'}
LABELS = {'inspect':'定點巡檢', 'recover':'海底物件回收', 'deploy':'觀測儀部署'}
BIOLOGY = {'coral':'珊瑚', 'seastar':'海星', 'kelp':'海帶', 'seagrass':'海草', 'fish_school':'魚群'}


def _vector(value, size):
    value = np.asarray(value, dtype=float)
    if value.shape != (size,) or not np.isfinite(value).all():
        raise ValueError('Invalid finite camera vector')
    return value


class Expedition:
    def __init__(self, sim):
        self.dive_id = secrets.token_hex(8)
        self.active = None
        self.results, self.discoveries, self.markers = [], [], []
        self.last_observation = None
        self.requests, self.photos = {}, {}
        self._dwell = {}
        self._contributors = set()
        self._participants = {}
        self._eligible_participants = {}
        self._started = 0.
        self._event_index = 0
        self._settled = 0.
        self._last_tick = -1.

    @staticmethod
    def _online(sim):
        room = getattr(sim, 'room', None)
        if room is None:
            return [sim]
        ids = {p.vehicle_id for p in room.players.values() if p.connected}
        return [v for key,v in room.vehicles.items() if key in ids]

    @staticmethod
    def _identity(sim):
        room = getattr(sim,'room',None)
        if room:
            return next((p.id for p in room.players.values() if p.vehicle_id==sim.vehicle_id),str(sim.vehicle_id))
        return str(sim.vehicle_id)

    def _credit(self, sim):
        self._contributors.add(str(sim.vehicle_id))
        self._participants[self._identity(sim)] = str(sim.vehicle_id)

    def available(self, sim):
        supported = sim.scenario.key in SCENES
        arm = any(v.model_id == 'falcon' for v in self._online(sim))
        limit=sum(ob.get('task_kind')=='deploy' and ob.get('task_id') is None for ob in sim.world.work_objects.values())>=20
        offered=[dict(kind=kind, label=label, enabled=supported and (kind=='inspect' or arm),
                     reason='' if supported and (kind=='inspect' or arm) else
                        '此海域尚未提供工程合約' if not supported else '需要一台在線 Falcon 機械臂 ROV')
                for kind,label in LABELS.items()]
        if limit:
            offered[2].update(enabled=False,reason='本次潛航已部署 20 台觀測儀，請重開場景後再部署')
        return offered

    @staticmethod
    def _path_clear(world, points):
        for a,b in zip(points, points[1:]):
            for point in np.linspace(a,b,max(2,math.ceil(np.linalg.norm(b-a)/.4)+1)):
                if point[2] < .8 or world.sdf(point)[0] < .8:
                    return False
        return True

    def _sites(self, sim, count=3):
        # Route is explicit: travel at the deployment depth, then descend.
        # A 0.8 m clearance envelope exceeds the Falcon hull extent in FRD.
        origin = np.asarray(sim.scenario.start_pos, float)
        from .operations import arm_points
        reach=arm_points([0.,45.,-15.,0.])[-1]
        sites = []
        for radius in (5., 8., 12., 16.):
            for angle in np.linspace(0,2*math.pi,24,endpoint=False):
                xy = origin + [radius*math.cos(angle),radius*math.sin(angle),0.]
                depth = sim.world.depth_at(xy)
                approach = xy.copy(); approach[2] = depth-1.0
                if any(np.linalg.norm(approach-s) < 4. for s in sites):
                    continue
                if self._path_clear(sim.world,[origin,xy,approach]):
                    # Keep the entire arm's horizontal reach clear of habitat
                    # and structures, rather than clearing/removing nature.
                    if any(o.sdf(approach)[0] < 3.5 for o in sim.world.obstacles):
                        continue
                    inspect_stance=approach-np.array([2.2,0.,0.])
                    object_point=approach.copy();object_point[2]=depth-.15
                    pickup_stance=object_point-reach
                    stances=(inspect_stance,pickup_stance)
                    if not all(self._path_clear(sim.world,[origin,np.array([s[0],s[1],origin[2]]),s]) for s in stances):
                        continue
                    sites.append(approach)
                    if len(sites) == count:
                        return sites
        raise ValueError('無法在此海域找到安全可達的工程位置')

    def command(self, sim, action, msg):
        if action == 'observation_photo':
            return self.observe(sim,msg)
        if action == 'expedition_mark':
            return self.mark(sim,msg)
        request_id = msg.get('request_id')
        if not isinstance(request_id,str) or not 1 <= len(request_id) <= 100:
            raise ValueError('request_id is required')
        key = f'{self._identity(sim)}:{action}:{request_id}'
        if key in self.requests:
            return dict(self.requests[key])
        if len(self.requests)>=2048:
            raise ValueError('本次潛航合約操作紀錄已滿，請重開場景')
        if action == 'expedition_start':
            kind = msg.get('contract')
            offered = next((a for a in self.available(sim) if a['kind']==kind), None)
            if offered is None or not offered['enabled']:
                raise ValueError(offered['reason'] if offered else 'Unknown contract')
            if self.active is not None:
                raise ValueError('請先完成或取消目前合約')
            sites = self._sites(sim)
            contract_id = secrets.token_hex(6)
            steps = [dict(id=f'{contract_id}-{i}',label=f'巡檢站 {i+1}',point=p.tolist(),
                          radius=1.5,hold_s=3.,progress=0.,completed=False,completed_by=None)
                     for i,p in enumerate(sites)] if kind=='inspect' else []
            self.active = dict(id=contract_id,kind=kind,label=LABELS[kind],status='active',steps=steps,
                               target_object_id=None,delivery_point=None,elapsed=0.)
            if kind == 'inspect':
                for index,(step,site) in enumerate(zip(steps,sites)):
                    object_id = f'expedition-{contract_id}-inspect-{index}'
                    target = site.copy();target[2] = sim.world.depth_at(site)-.22
                    stance = site.copy();stance[0]-=2.2
                    step.update(entity_id=object_id,object_id=object_id,target_point=target.tolist(),point=stance.tolist(),role='photo')
                    sim.world.work_objects[object_id] = dict(id=object_id,label=f'工程檢查標牌 {index+1}',
                        pos=target,vel=np.zeros(3),mass=3.,buoyancy_kg=1.,radius=.18,held_by=None,
                        task_id=contract_id,task_kind=kind,anchored=True,graspable=False)
            if kind != 'inspect':
                from .operations import arm_points
                source,destination = sites[:2] if kind=='recover' else sites[1::-1]
                object_position = source.copy(); object_position[2] = sim.world.depth_at(source)-.15
                delivery = destination.copy(); delivery[2] = sim.world.depth_at(destination)-.15
                # A documented reachable stance with real arm joint limits.
                reach = arm_points([0.,45.,-15.,0.])[-1]
                pickup_approach = object_position-reach
                delivery_approach = delivery-reach
                object_id = f'expedition-{contract_id}'
                sim.world.work_objects[object_id] = dict(id=object_id,label='待回收工具箱' if kind=='recover' else '海底觀測儀',
                    pos=object_position,vel=np.zeros(3),mass=2.5,buoyancy_kg=1.8,radius=.12,
                    held_by=None,task_id=contract_id,task_kind=kind,ever_carried=False,released=False)
                self.active.update(target_object_id=object_id,delivery_point=delivery.tolist(),
                    pickup_point=object_position.tolist(),pickup_approach=pickup_approach.tolist(),
                    delivery_approach=delivery_approach.tolist(),settled_s=0.,suggested_joints=[0.,45.,-15.,0.])
                common=dict(entity_id=object_id,object_id=object_id,progress=0.)
                self.active['steps'] = [dict(**common,id=f'{contract_id}-pick',role='pickup',label='以機械臂夾取物件',point=pickup_approach.tolist(),target_point=object_position.tolist(),completed=False),
                    dict(**common,id=f'{contract_id}-place',role='place',label='運送至目的地並放開，保持穩定 2 秒',point=delivery_approach.tolist(),target_point=delivery.tolist(),completed=False)]
                photo_step=dict(**common,id=f'{contract_id}-photo',role='photo',completed=False,
                    label='拍攝回收前物件照片' if kind=='recover' else '拍攝部署完成照片',
                    point=(source if kind=='recover' else destination).tolist(),target_point=(object_position if kind=='recover' else delivery).tolist())
                if kind=='recover':
                    self.active['steps'].insert(0,photo_step)
                else:
                    self.active['steps'].append(photo_step)
                self.active.update(initial_photo=False,placement_ready=False)
            self._started,self._event_index = sim.t,len(sim.world.events)
            self._dwell,self._contributors,self._participants = {},set(),{}
            self._eligible_participants={self._identity(v):str(v.vehicle_id) for v in self._online(sim)}
            self._settled,self._last_tick = 0.,-1.
            response = dict(ok=True,action=action,request_id=request_id,contract_id=contract_id)
        elif action == 'expedition_cancel':
            contract_id = self.active['id'] if self.active else None
            if self.active:
                self._cleanup(sim)
                self.active = None
            response = dict(ok=True,action=action,request_id=request_id,contract_id=contract_id)
        else:
            raise ValueError('Unknown expedition action')
        self.requests[key] = response
        return dict(response)

    @staticmethod
    def _placement_valid(sim, task, ob):
        good = (ob.get('ever_carried') and ob.get('released') and ob['held_by'] is None
                and np.linalg.norm(ob['pos']-np.asarray(task['delivery_point']))<=2.
                and np.linalg.norm(ob['vel'])<=.2)
        if task['kind']=='deploy':
            good = good and abs(sim.world.depth_at(ob['pos'])-ob['pos'][2]-ob['radius'])<=.2
        return bool(good)

    def _cleanup(self, sim):
        if not self.active:
            return
        object_ids = [key for key,ob in sim.world.work_objects.items() if ob.get('task_id')==self.active['id']]
        room = getattr(sim,'room',None)
        vehicles = room.vehicles.values() if room else [sim]
        for vehicle in vehicles:
            if vehicle.operations.held in object_ids:
                vehicle.operations.release()
        for object_id in object_ids:
            sim.world.work_objects.pop(object_id,None)

    def grasp(self, sim, object_id):
        if self.active and self.active.get('target_object_id') == object_id:
            ob = sim.world.work_objects[object_id]
            ob['ever_carried'],ob['released'] = True,False
            self._credit(sim)
            next(s for s in self.active['steps'] if s['role']=='pickup')['completed'] = True

    def release(self, sim, object_id):
        if self.active and self.active.get('target_object_id') == object_id:
            ob = sim.world.work_objects.get(object_id)
            if ob and ob.get('ever_carried'):
                ob['released'] = True

    def update(self, sim, dt):
        if not self.active:
            return
        self._eligible_participants.update({self._identity(v):str(v.vehicle_id) for v in self._online(sim)})
        task = self.active
        task['elapsed'] = round(max(0.,sim.t-self._started),2)
        if task['kind']=='inspect':
            progress = self._dwell.setdefault(self._identity(sim),{})
            for step in task['steps']:
                eligible = (not sim.tether.broken and np.linalg.norm(sim.vehicle.s.pos-np.asarray(step['point']))<=1.5
                    and np.linalg.norm(sim.vehicle.world_velocity())<=.35)
                progress[step['id']] = min(3.,progress.get(step['id'],0.)+dt) if eligible else 0.
                step['progress'] = round(max(p.get(step['id'],0.) for p in self._dwell.values())/3,3)
        elif sim.t > self._last_tick+1e-9:
            self._last_tick = sim.t
            ob = sim.world.work_objects.get(task['target_object_id'])
            if ob is None:
                return
            good = self._placement_valid(sim,task,ob)
            self._settled = self._settled+dt if good else 0.
            task['settled_s'] = round(self._settled,2)
            task['placement_ready'] = self._settled>=2.-1e-8
            step = next(s for s in task['steps'] if s['role']=='place')
            step['progress'] = min(1.,self._settled/2.)
            if self._settled>=2.-1e-8:
                step['completed'] = True
                if task['kind']=='recover' and task['initial_photo']:
                    self._finish(sim)
            elif not good:
                step['completed'] = False

    def inspection_photo(self, sim, entity_id):
        if not self.active or self.active['kind']!='inspect':
            return False
        for step in self.active['steps']:
            if (step['entity_id']==entity_id and not step['completed'] and self._dwell.get(self._identity(sim),{}).get(step['id'],0.)>=3.-1e-8
                    and np.linalg.norm(sim.vehicle.s.pos-np.asarray(step['point']))<=1.5
                    and np.linalg.norm(sim.vehicle.world_velocity())<=.35 and not sim.tether.broken):
                step.update(completed=True,completed_by=str(sim.vehicle_id))
                self._credit(sim)
                if all(s['completed'] for s in self.active['steps']):
                    self._finish(sim)
                return True
        return False

    def _finish(self, sim):
        task = self.active
        collisions = len(sim.world.events[self._event_index:])
        self.results.append(dict(id=task['id'],kind=task['kind'],label=task['label'],status='completed',
            scene=sim.scenario.key,created_at=datetime.now(timezone.utc).isoformat(),
            contributors=sorted(self._contributors),elapsed=round(max(0.,sim.t-self._started),2),
            participant_ids=sorted(self._eligible_participants),participants=[{'player_id':p,'vehicle_id':v} for p,v in self._eligible_participants.items()],
            contributor_player_ids=sorted(self._participants),contributor_vehicle_ids=sorted(self._contributors),
            collision_count=collisions,grade='精準完成' if collisions==0 else '完成',completed_at=round(sim.t,2)))
        self.results = self.results[-50:]
        if task['kind'] in ('recover','inspect'):
            self._cleanup(sim)
        else:
            ob=sim.world.work_objects[task['target_object_id']]
            ob.update(anchored=True,graspable=False,task_id=None,label='已部署海底觀測儀')
            ob['vel'][:]=0.
        self.active = None

    @staticmethod
    def _entity(sim, entity_id):
        expedition=getattr(sim.world,'expedition',None)
        ob=getattr(sim.world,'work_objects',{}).get(entity_id)
        if ob and expedition and expedition.active and ob.get('task_id')==expedition.active['id']:
            return 'engineering',np.asarray(ob['pos'],float),float(ob['radius'])
        for entity in sim.world.habitat_entities:
            if entity['id']==entity_id and entity['kind'] in BIOLOGY:
                pos=np.asarray(entity['pos'],float).copy()
                scale=float(entity['scale'])
                pos[2] -= .035 if entity['kind']=='seastar' else scale*.5
                return entity['kind'],pos,max(.06,scale*.5)
        for school in sim.world.fish_schools:
            if school['id']==entity_id:
                return 'fish_school',np.asarray(school['pos'],float),1.2
        raise ValueError('Unknown observable marine entity')

    def _camera(self, sim, msg):
        if msg.get('view')!='onboard' or msg.get('visible') is not True:
            raise ValueError('請使用機載相機，並讓目標清楚出現在畫面中')
        camera=msg.get('camera',{})
        if not isinstance(camera,dict):
            raise ValueError('Invalid camera payload')
        pos,q=_vector(camera.get('pos'),3),_vector(camera.get('q'),4)
        fov,aspect=float(camera.get('fov')),float(camera.get('aspect'))
        coverage=float(msg.get('coverage',0.))
        if not all(math.isfinite(v) for v in (fov,aspect,coverage)) or not 60<=fov<=80 or not .3<=aspect<=4 or not .00002<=coverage<=1:
            raise ValueError('目標太小，或相機視野資料無效')
        if not .98<=np.linalg.norm(q)<=1.02:
            raise ValueError('Invalid camera attitude')
        q=q/np.linalg.norm(q)
        expected=sim.vehicle.s.pos+q_rot(sim.vehicle.s.q,np.asarray(sim.vehicle.definition.camera_body))
        if np.linalg.norm(pos-expected)>.75 or abs(float(np.dot(q,sim.vehicle.s.q)))<math.cos(math.radians(12)):
            raise ValueError('相機位置與目前機載視角不符，請重新拍照')
        return pos,q,math.tan(math.radians(fov/2)),aspect

    def observe(self, sim, msg):
        photo_id=msg.get('photo_id')
        if not isinstance(photo_id,str) or not 1<=len(photo_id)<=100:
            raise ValueError('photo_id is required')
        key=f'{self._identity(sim)}:{photo_id}'
        if key in self.photos:
            return dict(self.photos[key])
        if len(self.photos)>=2000:
            return dict(ok=True,action='observation_photo',photo_id=photo_id,
                        observation=dict(accepted=False,reason='本次潛航照片驗證紀錄已滿，請重開場景'))
        accepted,entry=False,None
        try:
            pos,q,tan_fov,aspect=self._camera(sim,msg)
            entity_id=msg.get('entity_id')
            if entity_id is None:
                raise ValueError('照片已保留；畫面中沒有可確認的生物或工程目標')
            else:
                category,target,radius=self._entity(sim,entity_id)
                delta=target-pos; distance=float(np.linalg.norm(delta))
                body=q_rot(q_conj(q),delta)
                if not .1<distance<=min(15.,sim.scenario.visibility_m) or body[0]<=0:
                    raise ValueError('目標超出可辨識距離或位於鏡頭後方')
                if abs(body[1])>body[0]*tan_fov*aspect+radius or abs(body[2])>body[0]*tan_fov+radius:
                    raise ValueError('目標不在目前機載鏡頭範圍')
                if sim.world.raycast(pos,delta,max_range=distance)<distance-radius-.15:
                    raise ValueError('目標受到地形或物體遮擋')
                if sim.world.silt_at(pos)>.75:
                    raise ValueError('揚沙過濃，請等待視野恢復')
                entry=dict(id=f'{self.dive_id}:{secrets.token_hex(6)}',photo_id=photo_id,entity_id=entity_id,
                    category=category,label=BIOLOGY.get(category,'工程紀錄'),scene=sim.scenario.key,depth=round(float(target[2]),2),
                    created_at=datetime.now(timezone.utc).isoformat(),sim_time=round(sim.t,2),
                    photographer=str(sim.vehicle_id),point=target.round(4).tolist())
                entry['photographer_player_id']=self._identity(sim)
                if category != 'engineering':
                    self.discoveries.append(entry);self.discoveries=self.discoveries[-200:]
                accepted,reason=True,'生態觀察已加入本次潛航紀錄'
                if category=='engineering':
                    reason='工程照片已確認，並檢查合約條件'
                    task=self.active
                    if task['kind']=='inspect':
                        if not self.inspection_photo(sim,entity_id):
                            reason='工程照片已保留；須在本站以低速穩定 3 秒才完成巡檢'
                    elif entity_id==task['target_object_id']:
                        ob=sim.world.work_objects[entity_id]
                        if task['kind']=='recover' and ob['held_by'] is None and np.linalg.norm(ob['pos']-np.asarray(task['pickup_point']))<=2.:
                            task['initial_photo']=True
                            next(s for s in task['steps'] if s['role']=='photo')['completed']=True
                            self._credit(sim)
                        elif task['kind']=='deploy' and task['placement_ready'] and self._placement_valid(sim,task,ob):
                            self._credit(sim)
                            next(s for s in task['steps'] if s['role']=='photo')['completed']=True
                            self._finish(sim)
        except (ValueError,TypeError,OverflowError) as error:
            reason=str(error)
        observation=dict(accepted=accepted,reason=reason)
        if entry is not None:
            observation['entry']=entry
        self.last_observation=dict(photo_id=photo_id,**observation)
        response=dict(ok=True,action='observation_photo',photo_id=photo_id,observation=observation)
        self.photos[key]=response
        return dict(response)

    def mark(self, sim, msg):
        entity_id=msg.get('entity_id')
        category,point,_=self._entity(sim,entity_id)
        if np.linalg.norm(point-sim.vehicle.s.pos)>20.:
            raise ValueError('目標離 ROV 太遠，請先靠近再標記')
        marker=dict(id=f'mark-{entity_id}',entity_id=entity_id,label=BIOLOGY.get(category,'工程目標'),point=point.tolist(),
                    marked_by=str(sim.vehicle_id),created_at=round(sim.t,2))
        self.markers=[m for m in self.markers if m['entity_id']!=entity_id][-49:]+[marker]
        return dict(ok=True,action='expedition_mark',marker=marker)

    def state(self, sim):
        active=None
        if self.active:
            steps=[]
            for step in self.active['steps']:
                own=self._dwell.get(self._identity(sim),{}).get(step['id'],0.)/3 if self.active['kind']=='inspect' else step.get('progress',0.)
                steps.append({**step,'own_progress':1. if step['completed'] else min(1.,own)})
            active={**self.active,'steps':steps}
        return dict(dive_id=self.dive_id,active=active,available=self.available(sim),
                    discoveries=self.discoveries,markers=self.markers,results=self.results,last_observation=self.last_observation)


def ensure_expedition(sim):
    if not hasattr(sim.world,'expedition'):
        sim.world.expedition=Expedition(sim)
    return sim.world.expedition
