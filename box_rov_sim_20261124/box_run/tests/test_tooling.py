import unittest
from copy import deepcopy
import numpy as np
from rov01sim.engine import Simulator
from rov01sim.room import Room
from rov01sim.tooling import CATALOGUE, TOOLS, validate_loadout
from rov01sim.world import Box

class ToolingTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sim=Simulator('open_water',42,model_id='rov01_pro')

    def setUp(self):
        self.sim.tools.launched=False
        self.sim.tools.install(CATALOGUE['vehicles']['rov01_pro']['default_loadout'])

    def equip(self,tid):
        t=TOOLS[tid];mount=next(m for m in CATALOGUE['vehicles']['rov01_pro']['mounts'] if m['kind']==t['slot_kind'])
        loadout=[x for x in self.sim.tools.loadout if x['slot']!=mount['id'] and x['tool']!=tid]+[{'slot':mount['id'],'tool':tid}]
        self.sim.tools.install(loadout)

    def test_count_and_each_tool_installable_and_serializable(self):
        import json
        self.assertEqual(sum(t['counted'] for t in TOOLS.values()),24)
        for tid in TOOLS:
            with self.subTest(tool=tid):
                if tid=='camera':
                    s=Simulator('open_water',42,model_id='rov02_heavy');s.tools.install([{'slot':'internal_camera','tool':'camera'}]);s.tools.step(.05);json.dumps(s.tools.state(),allow_nan=False);continue
                self.sim.tools.install(CATALOGUE['vehicles']['rov01_pro']['default_loadout'])
                self.equip(tid);self.sim.tools.step(.05)
                self.assertIn(tid,self.sim.tools.states)
                json.dumps(self.sim.tools.state(),allow_nan=False)

    def test_invalid_install_is_atomic(self):
        previous=deepcopy(self.sim.tools.loadout);mass=self.sim.vehicle.p.mass
        bad=[{'slot':'arm','tool':'hydraulic_arm'}]
        with self.assertRaises(ValueError):self.sim.tools.install(bad)
        self.assertEqual(previous,self.sim.tools.loadout);self.assertEqual(mass,self.sim.vehicle.p.mass)
        with self.assertRaises(ValueError):validate_loadout('rov01',previous)
        with self.assertRaises(ValueError):validate_loadout('rov01_pro',[previous[0],previous[0]])

    def test_cannot_equip_after_launch(self):
        self.sim.tools.launched=True
        with self.assertRaises(ValueError):self.sim.tools.install([])

    def test_pressure_power_and_temperature_follow_pump_and_load(self):
        t=self.sim.tools;t.pump=False;t.step(.1)
        initial=t.systems['electrical']['power_w'];self.assertLess(t.pressure,1)
        t.command({'action':'tool_action','tool':'hpu','verb':'toggle'})
        self.sim.operations.target=np.array([30.,45.,50.,20.])
        for _ in range(80):t.step(.05)
        self.assertGreater(t.pressure,15);self.assertGreater(t.flow,.1)
        self.assertGreater(t.systems['electrical']['power_w'],initial)
        p=t.pressure;t.halt()
        for _ in range(50):t.step(.05)
        self.assertLess(t.pressure,p*.01);self.assertEqual(t.flow,0)
        self.assertIsNone(t.systems['electrical']['battery_pct'])

    def test_known_metal_contact_required(self):
        self.equip('ut');s=self.sim;t=s.tools
        s.vehicle.s.pos=np.array([0.,0.,2.]);s.vehicle.s.q=np.array([1.,0.,0.,0.])
        t.measure();self.assertFalse(t.states['ut']['valid'])
        p=s.vehicle.s.pos+t.pose('ut')
        s.world.obstacles.append(Box('tool_calibration_steel',tuple(p+np.array([.15,0,0])),(.03,.5,.5)))
        s.world._bounds_cache=None
        t.measure();self.assertTrue(t.states['ut']['valid'])
        rec=t.command(dict(action='tool_action',tool='ut',verb='record'))['record']
        self.assertEqual(rec['tool'],'ut');self.assertEqual(rec['position'],s.vehicle.s.pos.tolist())
        s.world.obstacles.pop();s.world._bounds_cache=None

    def test_sampling_completes_once_and_is_shared(self):
        self.equip('water');s=self.sim;t=s.tools
        s.vehicle.s.pos[2]=3;t.command(dict(action='tool_action',tool='water',verb='sample'))
        before=len(getattr(s.world,'tool_records',[]))
        for _ in range(100):t.step(.05)
        self.assertEqual(t.states['water']['progress'],1)
        self.assertEqual(len(s.world.tool_records),before+1)
        with self.assertRaises(ValueError):t.command(dict(action='tool_action',tool='water',verb='sample'))

    def test_measurements_depend_on_shared_position(self):
        self.equip('ph');t=self.sim.tools;t.measure();first=t.states['ph']['reading']
        self.sim.vehicle.s.pos[0]+=80;t.measure();self.assertNotEqual(first,t.states['ph']['reading'])

    def test_repeated_install_does_not_accumulate_mass(self):
        self.equip('light');mass=self.sim.vehicle.p.mass
        for _ in range(3):self.equip('light')
        self.assertEqual(mass,self.sim.vehicle.p.mass)
        self.sim.tools.install(CATALOGUE['vehicles']['rov01_pro']['default_loadout'])
        self.assertEqual(self.sim.vehicle.p.mass,60)

    def test_disconnect_preserves_configuration_stops_tools(self):
        room=Room(Simulator('open_water',42,model_id='rov01_pro'),'tool-test')
        p=room.join('A',model_id='rov01_pro');s=room.vehicles[p.vehicle_id];s.tools.pump=True
        config=deepcopy(s.tools.loadout);room.disconnect(p,p.generation,now=1)
        self.assertFalse(s.tools.pump)
        p2=room.join('A',resume_token=p.token,now=2)
        self.assertEqual(p.id,p2.id);self.assertEqual(s.tools.loadout,config)

if __name__=='__main__':unittest.main()
