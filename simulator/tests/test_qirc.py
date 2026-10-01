"""Real USB frame fixture, stream corruption and simulator input ownership."""
import unittest

from qysim.engine import Simulator
from qysim.qirc import AXES, ChannelDecoder, QircControls, axes_from_channels
from qysim.rc import RCState
from qysim.server import SimHost

# One response captured from the user's Q-iRC, all sticks and wheels centred.
FRAME = bytes.fromhex(
    "fd40000094ffbeb15200dc05dc05dc05dc05e803e803dc05dc05"
    "e803e803e803e803e803e803e803e803dc05dc05dc05e803e803"
    "e803e803e803e803e803e803e803e803e803e803e8030bea"
)


class TestDecoder(unittest.TestCase):
    def test_real_controller_frame_in_fragments(self):
        decoder = ChannelDecoder()
        self.assertEqual(decoder.feed(b"noise" + FRAME[:17]), [])
        samples = decoder.feed(FRAME[17:])
        self.assertEqual(len(samples), 1)
        self.assertEqual(axes_from_channels(samples[0]), dict.fromkeys(AXES, 1500))

    def test_corrupt_frame_is_rejected_and_next_frame_recovers(self):
        bad = bytearray(FRAME)
        bad[10] ^= 1
        self.assertEqual(len(ChannelDecoder().feed(bytes(bad) + FRAME)), 1)

    def test_coalesced_frames(self):
        self.assertEqual(len(ChannelDecoder().feed(FRAME * 3)), 3)

    def test_physical_xy_channels_map_to_simulator_ud_lr(self):
        values = (1100, 1200, 1300, 1400, 1000, 1000, 1600, 1700) + (1000,) * 15
        self.assertEqual(axes_from_channels(values), {
            "left_lr": 1100, "left_ud": 1200, "right_lr": 1300,
            "right_ud": 1400, "left_wave": 1600, "right_wave": 1700,
        })


class TestPhysicalButtons(unittest.TestCase):
    def setUp(self):
        self.raw = list(ChannelDecoder().feed(FRAME)[0])
        self.mapper = QircControls()
        self.rc = RCState()
        self.mapper.update(self.raw, self.rc)

    def test_lights_and_mode_follow_three_positions(self):
        for pwm, expected in ((1500, 1), (2000, 2), (1000, 0)):
            self.raw[4] = self.raw[5] = pwm
            values = self.mapper.update(self.raw, self.rc)
            self.assertEqual((values['left_switch'], values['right_switch']), (expected, expected))
        self.assertNotIn('right_switch', self.mapper.update(self.raw, self.rc))

    def test_lock_and_depth_toggle_once_per_press_using_current_state(self):
        for index, key in ((14, 'rc_lock'), (15, 'keep_depth')):
            before = getattr(self.rc, key)
            self.raw[index] = 2000
            values = self.mapper.update(self.raw, self.rc)
            self.assertEqual(values[key], 1-before)
            setattr(self.rc, key, values[key])
            self.assertNotIn(key, self.mapper.update(self.raw, self.rc))
            self.raw[index] = 1000
            self.mapper.update(self.raw, self.rc)
            self.raw[index] = 2000
            self.assertEqual(self.mapper.update(self.raw, self.rc)[key], before)

    def test_held_buttons_on_reconnect_require_release(self):
        self.mapper.reset()
        for index in (8, 9, 14, 15):
            self.raw[index] = 2000
        for _ in range(3):
            values = self.mapper.update(self.raw, self.rc)
            self.assertNotIn('rc_lock', values)
            self.assertNotIn('keep_depth', values)
            self.assertEqual((values['photo'], values['record']), (0, 0))
        for index in (8, 9, 14, 15):
            self.raw[index] = 1000
        self.mapper.update(self.raw, self.rc)
        self.raw[14] = 2000
        self.assertEqual(self.mapper.update(self.raw, self.rc)['rc_lock'], 0)


class TestControllerOwnership(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.host = SimHost(Simulator("open_water", 42), qirc=True)
        self.axes = dict.fromkeys(AXES, 1500)
        self.axes["right_ud"] = 1900
        await self.host.controller_sample(self.axes, ())

    async def test_browser_heartbeat_cannot_overwrite_usb_axes(self):
        self.host.handle_viewer({"type": "rc", "rc": {"right_ud": 1500, "rc_lock": 0},
                                 "controller_generation": self.host.controller_generation})
        self.assertEqual(self.host.sim.rc_physical.right_ud, 1900)
        self.assertEqual(self.host.sim.rc_physical.rc_lock, 0)

    async def test_timeout_centres_locks_and_rejects_old_unlock(self):
        generation = self.host.controller_generation
        self.host.sim.rc_physical.rc_lock = 0
        self.host.check_controller(self.host.controller_last_sample + 0.61)
        self.assertFalse(self.host.controller_connected)
        self.assertEqual(self.host.sim.rc_physical.right_ud, 1500)
        self.assertEqual(self.host.sim.rc_physical.rc_lock, 1)
        await self.host.controller_sample(self.axes, ())
        self.host.handle_viewer({"type": "rc", "rc": {"rc_lock": 0},
                                 "controller_generation": generation})
        self.assertEqual(self.host.sim.rc_physical.rc_lock, 1)

    async def test_sdk_remote_still_has_priority(self):
        self.host.sim.sdk_call("QYRovControllerManage", "set_remote_control_status", ["ON"], {})
        self.host.sim.sdk_call("QYRovControllerManage", "set_right_joystick_up_down", [1200], {})
        raw = list(ChannelDecoder().feed(FRAME)[0])
        await self.host.controller_sample(self.axes, raw)
        raw[8] = raw[9] = raw[14] = raw[15] = 2000
        await self.host.controller_sample(self.axes, raw)
        self.assertEqual(self.host.sim.rc.right_ud, 1200)
        self.assertEqual(self.host.sim.camera.files, [])
        self.assertIsNone(self.host.sim.camera.recording_since)
        self.assertEqual(self.host.sim.rc.rc_lock, 1)
        self.assertEqual(self.host.sim.rc.keep_depth, 0)

    async def test_keyboard_still_works_without_usb_mode(self):
        self.host.qirc_enabled = False
        self.host.handle_viewer({"type": "rc", "rc": {"right_ud": 1700, "rc_lock": 0}})
        self.assertEqual(self.host.sim.rc_physical.right_ud, 1700)
        self.assertEqual(self.host.sim.rc_physical.rc_lock, 0)

    async def test_idle_second_tab_cannot_relock_active_pilot(self):
        idle_tab = self.host.sim.rc_physical.as_dict()
        pilot_tab = dict(idle_tab)
        generation = self.host.controller_generation
        self.host.handle_viewer({"type": "rc", "rc": {"rc_lock": 0},
                                 "controller_generation": generation}, pilot_tab)
        self.host.handle_viewer({"type": "rc", "rc": {"rc_lock": 1},
                                 "controller_generation": generation}, idle_tab)
        self.assertEqual(self.host.sim.rc_physical.rc_lock, 0)

    async def test_camera_edges_survive_coalesced_usb_frames(self):
        raw = list(ChannelDecoder().feed(FRAME)[0])
        await self.host.controller_sample(self.axes, raw)
        raw[8] = raw[9] = 2000
        await self.host.controller_sample(self.axes, raw)
        await self.host.controller_sample(self.axes, raw)
        self.assertIsNotNone(self.host.sim.camera.recording_since)
        self.assertEqual(len(self.host.sim.camera.files), 1)
        raw[8] = raw[9] = 1000
        await self.host.controller_sample(self.axes, raw)
        raw[8] = 2000
        await self.host.controller_sample(self.axes, raw)
        self.assertIsNone(self.host.sim.camera.recording_since)
        self.assertEqual(len(self.host.sim.camera.files), 2)

    async def test_hardware_and_browser_photo_holds_do_not_cancel_each_other(self):
        raw = list(ChannelDecoder().feed(FRAME)[0])
        await self.host.controller_sample(self.axes, raw)
        raw[9] = 2000
        await self.host.controller_sample(self.axes, raw)
        self.host.handle_viewer({'type':'rc', 'rc':{'photo':0},
                                'controller_generation':self.host.controller_generation})
        self.assertEqual(self.host.sim.rc_physical.photo, 1)
        self.assertEqual(len(self.host.sim.camera.files), 1)


if __name__ == "__main__":
    unittest.main()
