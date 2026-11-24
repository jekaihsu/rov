import unittest
from rov01sim.engine import Simulator
from rov01sim.room import Room
from rov01sim.repair import ensure_repair

class RepairTests(unittest.TestCase):
    def setUp(self):
        self.room=Room(Simulator('cooperative_cable_repair',42),'repair-test')
        self.players=[self.room.join(n,model_id=m) for n,m in zip(('A','B','C'),('rov01','rov01_pro','rov02_heavy'))]
        self.sims=[self.room.vehicles[p.vehicle_id] for p in self.players]
        for i,s in enumerate(self.sims):s.vehicle.s.pos[:]=[7.,-i,10.8]
        self.run=ensure_repair(self.sims[0])
        for s,role in zip(self.sims,('survey','service','verify')):self.run.command(s,{'verb':'role','role':role})

    def finish(self,index):
        self.run.command(self.sims[index],{'verb':'start'})
        for _ in range(100):self.run.step(.1,self.room.vehicles)

    def test_shared_roles_and_complete_three_person_workflow(self):
        self.finish(0);self.finish(1)
        self.run.command(self.sims[1],{'verb':'start'})
        self.run.step(1,self.room.vehicles)
        self.assertEqual(self.run.progress,0)
        self.run.command(self.sims[0],{'verb':'assist'})
        for _ in range(90):self.run.step(.1,self.room.vehicles)
        self.finish(2)
        self.assertTrue(self.run.completed)
        self.assertEqual(len(self.run.records),4)
        self.assertEqual(self.run.records[2]['helpers'],[self.sims[0].vehicle_id])
        for s in self.sims:self.assertEqual(ensure_repair(s).state(s)['records'],self.run.records)

    def test_wrong_role_and_duplicate_claim_rejected(self):
        with self.assertRaises(ValueError):self.run.command(self.sims[2],{'verb':'start'})
        with self.assertRaises(ValueError):self.run.command(self.sims[2],{'verb':'role','role':'survey'})
        self.assertEqual(self.run.phase,0)

    def test_leaving_zone_pauses_and_disconnect_releases_work(self):
        s=self.sims[0];self.run.command(s,{'verb':'start'});self.run.step(1,self.room.vehicles)
        before=self.run.progress;s.vehicle.s.pos[0]=80;self.run.step(1,self.room.vehicles)
        self.assertEqual(before,self.run.progress)
        self.room.disconnect(self.players[0],self.players[0].generation,now=1)
        self.run.step(.1,self.room.vehicles);self.assertIsNone(self.run.active)
        self.run.command(self.sims[2],{'verb':'role','role':'survey'})
        self.assertEqual(self.run.roles['survey'],self.sims[2].vehicle_id)

    def test_scene_reset_clears_shared_progress(self):
        self.finish(0);self.room.reset()
        self.assertEqual(ensure_repair(self.room.primary).phase,0)

if __name__=='__main__':unittest.main()
