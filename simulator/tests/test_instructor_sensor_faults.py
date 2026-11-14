"""Instructor sensor-fault injections: they act on the sensor layer, expire, cancel and leave truth alone."""
import unittest

from qysim.engine import Simulator
from qysim.instructor import SENSOR_FAULTS
from qysim.room import Room
from qysim.sensors import SensorConfig


class InstructorSensorFaultTests(unittest.TestCase):
    def test_each_fault_reaches_the_sensor_layer_and_expires(self):
        for kind in SENSOR_FAULTS:
            with self.subTest(kind=kind):
                room = Room(Simulator())
                sim = room.primary
                truth = sim.vehicle.s.pos.copy()
                room.instructor.inject({'kind': kind, 'strength': .8, 'duration': .5})
                self.assertEqual(sim.sensors.faults, {kind: .8})
                self.assertIn(kind, sim.viewer_state()['sensors']['faults'])
                self.assertEqual(sim.vehicle.s.pos.tobytes(), truth.tobytes())
                room.instructor.update(.6)
                self.assertEqual(sim.sensors.faults, {})
                self.assertIn('restored_at', room.instructor.events[-1])

    def test_dvl_fault_drops_lock_and_cancel_restores_it(self):
        room = Room(Simulator('jacket_inspection'))
        sim = room.primary
        sim.rc_physical.rc_lock = 0
        room.instructor.inject({'kind': 'dvl', 'duration': 60})
        sim.step()
        self.assertEqual(sim.sdk_status()['Accessories_Status']['DVL_Status'], 'OffLine')
        self.assertEqual(sim.viewer_state()['sensors']['dvl']['reason'], 'fault')
        room.instructor.inject({'kind': 'dvl', 'cancel_start': 0})
        self.assertNotIn('dvl', sim.sensors.faults)

    def test_compass_fault_shifts_the_reported_heading(self):
        room = Room(Simulator('open_water'))
        sim = room.primary
        before = sim.sensors.frame.yaw
        room.instructor.inject({'kind': 'compass', 'strength': 1, 'duration': 120})
        for _ in range(4000):
            sim.sensors.step(.01, sim)
        self.assertGreater(abs(sim.sensors.frame.yaw - before), 0.3)

    def test_sensor_faults_need_the_realistic_layer(self):
        room = Room(Simulator(sensor_config=SensorConfig(ideal=True)))
        with self.assertRaises(ValueError):
            room.instructor.inject({'kind': 'compass'})
        self.assertEqual(room.instructor.active, [])


if __name__ == '__main__':
    unittest.main()
