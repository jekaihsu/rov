"""Mock of the remote-controller manage layer: take over the RC and drive sticks/buttons.

Sticks and wheels are PWM 1000..2000 (1500 centre). Stick/button setters return None,
like the real SDK. Calls are forwarded to the qysim simulator.
"""

from qysea.sdk._client import Remote, fail_none


class QYRovControllerManage(Remote):
    """Virtual remote controller."""

    _CLS = "QYRovControllerManage"

    def set_remote_control_status(self, status):
        return self._call("set_remote_control_status", status)

    def set_left_joystick_up_down(self, value):
        self._call("set_left_joystick_up_down", value, on_fail=fail_none)

    def set_left_joystick_left_right(self, value):
        self._call("set_left_joystick_left_right", value, on_fail=fail_none)

    def set_right_joystick_up_down(self, value):
        self._call("set_right_joystick_up_down", value, on_fail=fail_none)

    def set_right_joystick_left_right(self, value):
        self._call("set_right_joystick_left_right", value, on_fail=fail_none)

    def set_left_wave_left_right(self, value):
        self._call("set_left_wave_left_right", value, on_fail=fail_none)

    def set_right_wave_left_right(self, value):
        self._call("set_right_wave_left_right", value, on_fail=fail_none)

    def set_rc_lock_button(self, value):
        self._call("set_rc_lock_button", value, on_fail=fail_none)

    def set_keep_depth_button(self, value):
        self._call("set_keep_depth_button", value, on_fail=fail_none)

    def set_left_switch(self, value):
        self._call("set_left_switch", value, on_fail=fail_none)

    def set_right_switch(self, value):
        self._call("set_right_switch", value, on_fail=fail_none)

    def set_record_button(self, value):
        self._call("set_record_button", value, on_fail=fail_none)

    def set_photo_button(self, value):
        self._call("set_photo_button", value, on_fail=fail_none)
