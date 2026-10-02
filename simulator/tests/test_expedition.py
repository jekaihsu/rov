import copy
import unittest
import numpy as np
from qysim.engine import Simulator
from qysim.server import SimHost
from qysim.expedition import ensure_expedition
from qysim.operations import arm_points
from qysim.physics import q_rot, q_from_euler
from qysim.world import Box, ContactEvent


class TestExpedition(unittest.TestCase):
    def setUp(self):
        self.host=SimHost(Simulator('coral_reef',42))
        self.room=self.host.room
        self.players=[self.room.join('Pilot '+str(i),model_id=model) for i,model in enumerate(('x1','bluerov2_heavy','falcon'))]
        self.sim=self.room.primary
        self.falcon=self.room.vehicles[self.players[2].vehicle_id]
        self.send('mission_mode',mode='expedition')
        self.run=ensure_expedition(self.sim)

    def send(self, action, player=None, **values):
        return self.host.handle_viewer(dict(type='operation',action=action,**values),room=self.room,player=player or self.players[0])

    def start(self, kind):
        reply=self.send('expedition_start',contract=kind,request_id='start-'+kind)
        self.assertTrue(reply['ok'],reply)
        return self.run.active

    def photo(self, sim, entity_id, photo_id='photo',position=True):
        if position:
            _,target,_=self.run._entity(sim,entity_id)
            sim.vehicle.s.pos[:]=target-[2.2,0,.75]
            sim.vehicle.s.q[:]=[1,0,0,0]
            sim.vehicle.s.vel[:]=0.
        msg=dict(action='observation_photo',photo_id=photo_id,entity_id=entity_id,view='onboard',visible=True,coverage=.03,
            camera=dict(pos=(sim.vehicle.s.pos+q_rot(sim.vehicle.s.q,np.asarray(sim.vehicle.definition.camera_body))).tolist(),
                        q=sim.vehicle.s.q.tolist(),fov=70,aspect=1.6))
        return self.run.observe(sim,msg),msg

    def grab(self, task):
        falcon=self.falcon
        falcon.vehicle.s.q[:]=[1,0,0,0]
        falcon.vehicle.s.vel[:]=0.
        falcon.vehicle.s.pos[:]=task['pickup_approach']
        falcon.operations.joints[:]=task['suggested_joints']
        falcon.operations.target[:]=task['suggested_joints']
        falcon.operations.grip=falcon.operations.grip_target=0.
        falcon.operations.step(.01)
        self.assertEqual(falcon.operations.held,task['target_object_id'])

    def place(self, task, settle=True):
        self.falcon.vehicle.s.pos[:]=task['delivery_approach']
        self.falcon.operations.step(.01)
        self.falcon.operations.release()
        if settle:
            for _ in range(201):
                self.falcon.t+=.01
                self.run.update(self.falcon,.01)

    def test_host_permissions_idempotence_and_refresh(self):
        denied=self.send('expedition_start',player=self.players[1],contract='inspect',request_id='guest')
        self.assertEqual(denied['code'],'host_only')
        task=self.start('inspect')
        count=len(self.sim.world.work_objects)
        repeat=self.send('expedition_start',contract='inspect',request_id='start-inspect')
        self.assertEqual(repeat['contract_id'],task['id'])
        self.assertEqual(len(self.sim.world.work_objects),count)
        dive=self.run.dive_id
        self.send('mission_mode',mode='expedition')
        self.assertEqual(ensure_expedition(self.sim).dive_id,dive)
        self.assertIs(self.run.active,task)
        self.room.reset('seagrass_meadow',9)
        self.assertNotEqual(ensure_expedition(self.sim).dive_id,dive)

    def test_real_arm_recovery_requires_initial_photo_and_releases_on_expiration(self):
        task=self.start('recover')
        self.grab(task)
        self.place(task)
        self.assertIsNotNone(self.run.active)
        self.assertFalse(task['initial_photo'])
        self.send('expedition_cancel',request_id='cancel')
        self.assertNotIn(task['target_object_id'],self.sim.world.work_objects)
        task=self.send('expedition_start',contract='recover',request_id='new-recover')
        task=self.run.active
        result,_=self.photo(self.sim,task['target_object_id'])
        self.assertTrue(result['observation']['accepted'],result)
        self.assertTrue(task['initial_photo'])
        self.grab(task)
        object_id=task['target_object_id']
        player=self.players[2]
        # Expiry must release even if caller marks a lease disconnected directly.
        player.connected=False;player.disconnected_at=0
        self.room.expire(now=31)
        self.assertIsNone(self.sim.world.work_objects[object_id]['held_by'])
        self.assertFalse(next(a for a in self.run.available(self.sim) if a['kind']=='recover')['enabled'])

    def test_recovery_result_records_participants_and_whole_team_collisions(self):
        task=self.start('recover')
        self.photo(self.sim,task['target_object_id'])
        self.grab(task)
        self.sim.world.events.append(ContactEvent(0,'test',.1,'touch','front',self.players[1].vehicle_id))
        self.place(task)
        self.assertIsNone(self.run.active)
        result=self.run.results[-1]
        self.assertEqual(result['collision_count'],1)
        self.assertEqual(result['grade'],'完成')
        self.assertEqual(set(result['participant_ids']),{p.id for p in self.players})
        self.assertEqual(set(result['contributor_player_ids']),{self.players[0].id,self.players[2].id})
        self.assertIn('T',result['created_at'])

    def test_deployment_requires_final_photo_and_stays_anchored(self):
        task=self.start('deploy')
        self.photo(self.sim,task['target_object_id'])
        self.grab(task)
        self.place(task)
        self.assertIsNotNone(self.run.active)
        self.assertTrue(task['placement_ready'])
        response,_=self.photo(self.sim,task['target_object_id'],photo_id='final')
        self.assertTrue(response['observation']['accepted'],response)
        self.assertIsNone(self.run.active)
        ob=self.sim.world.work_objects[task['target_object_id']]
        self.assertTrue(ob['anchored'])
        self.assertIsNone(ob['task_id'])
        self.assertEqual(self.run.results[-1]['grade'],'精準完成')

    def test_all_engineering_stances_are_physically_reachable_in_supported_scenes(self):
        for scene in ('coral_reef','seagrass_meadow','harbor_inspection'):
            self.room.reset(scene,42)
            self.run=ensure_expedition(self.sim)
            task=self.start('recover')
            stance=np.asarray(task['pickup_approach'])
            points=stance+arm_points(task['suggested_joints'])
            ob=self.sim.world.work_objects[task['target_object_id']]
            np.testing.assert_allclose(points[-1],ob['pos'],atol=1e-12)
            self.assertGreater(self.sim.world.sdf(stance)[0],.8)
            for a,b in zip(points,points[1:]):
                for point in np.linspace(a,b,10):
                    self.assertGreater(self.sim.world.sdf(point)[0],.035)
            self.assertLess(ob['mass'],10.)
            self.grab(task)
            self.send('expedition_cancel',request_id='cancel-'+scene)

    def test_photo_geometry_and_duplicate_validation(self):
        task=self.start('inspect')
        entity=task['steps'][0]['entity_id']
        response,msg=self.photo(self.sim,entity)
        self.assertTrue(response['observation']['accepted'],response)
        self.assertFalse(task['steps'][0]['completed'])
        self.assertEqual(self.run.discoveries,[])  # Engineering is not biology.
        self.assertEqual(self.run.observe(self.sim,msg),response)
        for field,value in (('view','orbit'),('entity_id','invented'),('visible',False),('camera',None)):
            bad=copy.deepcopy(msg);bad[field]=value;bad['photo_id']=field
            self.assertFalse(self.run.observe(self.sim,bad)['observation']['accepted'])
        spoof=copy.deepcopy(msg);spoof['photo_id']='spoof';spoof['camera']['pos'][0]+=10
        self.assertFalse(self.run.observe(self.sim,spoof)['observation']['accepted'])
        target=self.sim.world.work_objects[entity]['pos']
        origin=np.asarray(msg['camera']['pos'])
        self.sim.world.obstacles.append(Box('遮擋物',tuple((target+origin)/2),(.2,1.,1.)))
        blocked=copy.deepcopy(msg);blocked['photo_id']='blocked'
        self.assertFalse(self.run.observe(self.sim,blocked)['observation']['accepted'])

    def test_inspection_requires_real_target_photo_not_sdk_file(self):
        task=self.start('inspect')
        step=task['steps'][0]
        self.sim.vehicle.s.pos[:]=step['point'];self.sim.vehicle.s.vel[:]=0.
        for _ in range(301):
            self.sim.t+=.01;self.run.update(self.sim,.01)
        self.sim._take_photo()
        self.assertFalse(step['completed'])
        result,_=self.photo(self.sim,step['entity_id'],position=False)
        self.assertTrue(result['observation']['accepted'],result)
        self.assertTrue(step['completed'])

    def test_three_players_do_not_triple_placement_dwell_and_cancel_only_owns_task(self):
        task=self.start('deploy')
        unrelated=set(self.sim.world.work_objects)-{task['target_object_id']}
        self.grab(task)
        self.place(task,settle=False)
        for tick in range(100):
            for sim in self.room.vehicles.values():
                sim.t=(tick+1)*.01
                self.run.update(sim,.01)
        self.assertAlmostEqual(task['settled_s'],1.,places=5)
        self.assertFalse(task['placement_ready'])
        self.send('expedition_cancel',request_id='cancel-task')
        self.assertEqual(set(self.sim.world.work_objects),unrelated)
        repeated=self.send('expedition_cancel',request_id='cancel-task')
        self.assertTrue(repeated['ok'])

    def test_biology_admission_and_mark_use_authoritative_entity_position(self):
        point=[0.,0.,self.sim.world.depth_at([0.,0.,0.])]
        self.sim.world.habitat_entities.append(dict(id='fixture-seastar',kind='seastar',pos=point,scale=.2,yaw=0,variant=0))
        result,msg=self.photo(self.sim,'fixture-seastar')
        self.assertTrue(result['observation']['accepted'],result)
        self.assertEqual(result['observation']['entry']['category'],'seastar')
        self.assertEqual(len(self.run.discoveries),1)
        again=self.run.observe(self.sim,msg)
        self.assertEqual(again,result)
        self.assertEqual(len(self.run.discoveries),1)
        marker=self.run.mark(self.sim,dict(entity_id='fixture-seastar',point=[999,999,999]))['marker']
        self.assertLess(np.linalg.norm(np.asarray(marker['point'])-point),.1)


if __name__=='__main__':
    unittest.main()
